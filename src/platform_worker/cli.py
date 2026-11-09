"""``platform-worker``: claims queued pieces from Supabase and processes them one by one.

    platform-worker run [--once] [--poll-seconds 10] [--provider fake|tripo|fal]
    platform-worker piece <id> [--provider …]

Settings come from ``platform_worker.config.load_settings``: the process environment over
``.env`` (or ``WORKER_ENV_FILE``): ``SUPABASE_URL``, ``SUPABASE_SERVICE_ROLE_KEY``, ``PROVIDER``,
``TRIPO_API_KEY``, ``FAL_KEY``, ``FAL_MODEL``, ``BLENDER_BIN``, ``WORKER_DAILY_BUDGET_USD``,
``AUTO_PUBLISH`` (default on) and ``ANTHROPIC_API_KEY`` (VLM judge of automatic publishing).

"""

from __future__ import annotations

import os
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console

from platform_worker import providers
from platform_worker.config import load_settings
from platform_worker.db import WorkerDB
from platform_worker.pipeline import (
    STATUS_QUEUED,
    STATUS_READY,
    STATUS_REVIEW,
    STATUS_SUPERSEDED,
    piece_workdir,
    process_piece,
)
from platform_worker.storage import Storage

DEFAULT_WORKDIR = Path("runs/platform")
# A piece longer than this without a heartbeat (``claimed_at`` is refreshed before every
# candidate and delivery) is taken for orphaned. Run ONE worker only: the queue is safe
# against two, but the daily budget and the stale sweep assume a single process.
STALE_MINUTES = 90
REQUEUE_EVERY_CYCLES = 10
# ``piece <id>`` only re-runs pieces that have no result waiting for review or the client;
# ``generating`` (maybe another worker is on it) needs ``--force``.
RETRYABLE_STATUSES = frozenset({"queued", "failed"})
FORCE_STATUSES = frozenset({"generating"})
CONFIG_EXIT_CODE = 2
# Workdirs hold photos, meshes and renders: delete them once the result is stored. Those of
# ``failed`` / ``needs_photos`` pieces stay for debugging until this many days old.
CLEANUP_STATUSES = frozenset({STATUS_READY, STATUS_REVIEW, STATUS_SUPERSEDED})
KEEP_WORKDIR_DAYS = 3

app = typer.Typer(
    help="Worker de la plataforma: genera los modelos 3D de las piezas en cola.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console(soft_wrap=True)
err_console = Console(stderr=True, soft_wrap=True)


def _exit_config(message: str) -> None:
    err_console.print(f"[red]{message}[/red]")
    raise typer.Exit(CONFIG_EXIT_CODE)


def startup_warnings(
    gltf_transform: Path | None = None, materials_dir: Path | None = None
) -> list[str]:
    """What the worker host lacks for the best delivery (warnings, never fatal): the local
    gltf-transform (without it every GLB ships unoptimised, with a warning for the admin)
    and the CC0 material textures (without them no library material can be applied).
    Both come from ``scripts/setup_worker.sh``."""
    from harness.post import deliver, materials

    tool = gltf_transform if gltf_transform is not None else deliver.LOCAL_GLTF_TRANSFORM
    folder = materials_dir if materials_dir is not None else materials.DEFAULT_MATERIALS_DIR
    out: list[str] = []
    if not Path(tool).is_file():
        out.append(
            f"Falta gltf-transform ({tool}): los GLB saldrán sin optimizar. "
            "Ejecuta scripts/setup_worker.sh."
        )
    if not Path(folder).is_dir() or not any(Path(folder).iterdir()):
        out.append(
            f"Faltan las texturas de materiales ({folder}): no se aplicará ningún material. "
            "Ejecuta scripts/setup_worker.sh."
        )
    return out


def build_context(provider_name: str | None) -> dict[str, Any]:
    """DB, Storage, provider and Blender from the settings; exit 2 when something is missing."""
    env = load_settings()
    url, key = env.get("SUPABASE_URL"), env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        _exit_config("Falta SUPABASE_SERVICE_ROLE_KEY en .env o en el entorno.")
    if not url:
        _exit_config("Falta SUPABASE_URL en .env o en el entorno.")
    name = provider_name if provider_name is not None else env.get("PROVIDER")
    try:
        provider = providers.make(name, env)
    except ValueError as exc:
        _exit_config(str(exc))
    blender = env.get("BLENDER_BIN")
    if not blender or not os.access(blender, os.X_OK) or not Path(blender).is_file():
        _exit_config(
            "Falta Blender: define BLENDER_BIN en .env con la ruta al ejecutable "
            "(p. ej. /Applications/Blender.app/Contents/MacOS/Blender)."
        )
    for warning in startup_warnings():
        err_console.print(f"[yellow]{warning}[/yellow]")
    return {
        "db": WorkerDB(url, key),  # type: ignore[arg-type]
        "storage": Storage(url, key),  # type: ignore[arg-type]
        "provider": provider,
        "blender_bin": Path(blender),  # type: ignore[arg-type]
    }


def _process(ctx: dict[str, Any], row: dict[str, Any], workdir: Path) -> str:
    name = row.get("name") or row["id"]
    console.print(f"Procesando «{name}» ({row['id']}, intento {row.get('attempt') or 1})…")
    start = time.monotonic()
    status = process_piece(
        ctx["db"], ctx["storage"], row,
        provider=ctx["provider"], workdir=workdir, blender_bin=ctx["blender_bin"],
    )  # fmt: skip
    seconds = f"{time.monotonic() - start:.1f}".replace(".", ",")
    console.print(f"  → estado {status} en {seconds} s")
    if status in CLEANUP_STATUSES and not ctx.get("keep_workdirs"):
        _remove_workdir(workdir, row)
    return status


def _remove_workdir(workdir: Path, row: dict[str, Any]) -> None:
    """Delete this attempt's workdir (and its piece folder when left empty). Never raises."""
    try:
        attempt = int(row.get("attempt") or 1)
        path = piece_workdir(workdir, str(row["id"]), attempt)
        shutil.rmtree(path, ignore_errors=True)
        try:
            path.parent.rmdir()  # only succeeds when empty
        except OSError:
            pass
    except Exception as exc:
        err_console.print(f"[yellow]No se pudo borrar la carpeta de trabajo: {exc}[/yellow]")


def _sweep_old_workdirs(workdir: Path, *, max_age_days: float = KEEP_WORKDIR_DAYS) -> None:
    """Delete ``<workdir>/<piece>/<attempt>`` folders untouched for more than
    ``max_age_days`` (kept after a failure). Never raises."""
    try:
        cutoff = time.time() - max_age_days * 86400
        for piece_dir in Path(workdir).iterdir():
            if not piece_dir.is_dir():
                continue
            for attempt_dir in piece_dir.iterdir():
                try:
                    if attempt_dir.is_dir() and attempt_dir.stat().st_mtime < cutoff:
                        shutil.rmtree(attempt_dir, ignore_errors=True)
                except OSError as exc:
                    err_console.print(f"[yellow]No se pudo borrar {attempt_dir}: {exc}[/yellow]")
            try:
                piece_dir.rmdir()  # only succeeds when empty
            except OSError:
                pass
    except FileNotFoundError:
        return
    except Exception as exc:
        err_console.print(f"[yellow]No se pudieron limpiar carpetas antiguas: {exc}[/yellow]")


def _requeue_stale(db: Any) -> None:
    try:
        requeued = db.requeue_stale(STALE_MINUTES)
    except Exception as exc:
        err_console.print(f"[red]No se pudieron revisar las piezas huérfanas: {exc}[/red]")
        return
    if requeued:
        console.print(f"{requeued} pieza(s) huérfana(s) devuelta(s) a la cola.")


def run_loop(
    ctx: dict[str, Any],
    *,
    once: bool,
    poll_seconds: float,
    workdir: Path,
    sleep: Any = time.sleep,
    max_cycles: int | None = None,
) -> int:
    """Requeue stale pieces (at start and every ``REQUEUE_EVERY_CYCLES`` cycles), then claim
    and process until empty (``once``) or forever. A failing piece or a DB/network error
    never stops the loop. ``max_cycles`` bounds the loop (tests). Returns the number of
    pieces processed."""
    db = ctx["db"]
    if ctx["provider"] is None:
        console.print(
            "[yellow]Sin proveedor (PROVIDER): solo se generan piezas rectilíneas; "
            "las orgánicas quedarán como fallidas con el motivo, y las dudosas, en revisión "
            "manual.[/yellow]"
        )
    processed = 0
    cycle = 0
    while max_cycles is None or cycle < max_cycles:
        if cycle % REQUEUE_EVERY_CYCLES == 0:
            _requeue_stale(db)
            if not ctx.get("keep_workdirs"):
                _sweep_old_workdirs(workdir)
        cycle += 1
        try:
            row = db.claim_next()
        except Exception as exc:  # network blip: keep the worker alive in loop mode
            if once:
                raise
            err_console.print(f"[red]No se pudo consultar la cola: {exc}[/red]")
            sleep(poll_seconds)
            continue
        if row is None:
            if once:
                if not processed:
                    console.print("No hay piezas en cola.")
                return processed
            sleep(poll_seconds)
            continue
        try:
            status = _process(ctx, row, workdir)
        except Exception as exc:  # e.g. Supabase down while recording the result
            err_console.print(f"[red]Error procesando la pieza {row.get('id')}: {exc}[/red]")
            status = None
            if not once:
                sleep(poll_seconds)
        processed += 1
        if once:
            return processed
        if status == STATUS_QUEUED:  # photos still uploading: do not re-claim it at once
            sleep(poll_seconds)
    return processed


ProviderOpt = Annotated[
    str | None,
    typer.Option("--provider", help="fake | tripo | fal (por defecto, PROVIDER de .env)."),
]
WorkdirOpt = Annotated[
    Path, typer.Option("--workdir", help="Carpeta de trabajo (una subcarpeta por pieza).")
]
KeepOpt = Annotated[
    bool,
    typer.Option(
        "--keep-workdirs", help="No borra las carpetas de trabajo (por defecto se borran)."
    ),
]


@app.command()
def run(
    once: Annotated[bool, typer.Option("--once", help="Procesa una pieza y termina.")] = False,
    poll_seconds: Annotated[
        float, typer.Option("--poll-seconds", help="Espera entre consultas con la cola vacía.")
    ] = 10.0,
    provider: ProviderOpt = None,
    workdir: WorkdirOpt = DEFAULT_WORKDIR,
    keep_workdirs: KeepOpt = False,
) -> None:
    """Reclama piezas en cola y las procesa en bucle."""
    ctx = build_context(provider)
    ctx["keep_workdirs"] = keep_workdirs
    try:
        run_loop(ctx, once=once, poll_seconds=poll_seconds, workdir=workdir)
    except KeyboardInterrupt:
        console.print("Worker detenido.")


@app.command()
def piece(
    piece_id: Annotated[str, typer.Argument(help="Id de la pieza.")],
    provider: ProviderOpt = None,
    workdir: WorkdirOpt = DEFAULT_WORKDIR,
    keep_workdirs: KeepOpt = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Reprocesa también una pieza en generación (huérfana)."),
    ] = False,
) -> None:
    """Procesa una pieza concreta (reintento manual), sin pasar por la cola."""
    ctx = build_context(provider)
    ctx["keep_workdirs"] = keep_workdirs
    row = ctx["db"].get_piece(piece_id)
    if row is None:
        err_console.print(f"[red]No existe la pieza {piece_id}.[/red]")
        raise typer.Exit(1)
    status = row.get("status")
    if status in FORCE_STATUSES and not force:
        err_console.print(
            f"[red]La pieza {piece_id} está en generación: puede que otro worker la esté "
            "procesando. Usa --force si sabes que está huérfana.[/red]"
        )
        raise typer.Exit(1)
    if status not in RETRYABLE_STATUSES | FORCE_STATUSES:
        err_console.print(
            f"[red]La pieza {piece_id} está en estado «{status}»: solo se reprocesan "
            "piezas en cola o fallidas (y en generación con --force).[/red]"
        )
        raise typer.Exit(1)
    ctx["db"].update_piece(
        piece_id, status="generating", error=None, claimed_at=datetime.now(UTC).isoformat()
    )
    _process(ctx, row, workdir)


if __name__ == "__main__":
    app()
