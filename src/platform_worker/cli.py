"""``platform-worker``: claims queued pieces from Supabase and processes them one by one.

    platform-worker run [--once] [--poll-seconds 10] [--provider fake|tripo|fal]
    platform-worker piece <id> [--provider …]

Settings come from ``platform_worker.config.load_settings``: the process environment over
``.env`` (or ``WORKER_ENV_FILE``): ``SUPABASE_URL``, ``SUPABASE_SERVICE_ROLE_KEY``, ``PROVIDER``,
``TRIPO_API_KEY``, ``FAL_KEY``, ``FAL_MODEL`` and ``BLENDER_BIN``.
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console

from platform_worker import providers
from platform_worker.config import load_settings
from platform_worker.db import WorkerDB
from platform_worker.pipeline import STATUS_QUEUED, process_piece
from platform_worker.storage import Storage

DEFAULT_WORKDIR = Path("runs/platform")
STALE_MINUTES = 30
REQUEUE_EVERY_CYCLES = 10
# ``piece <id>`` only re-runs pieces that have no result waiting for review or the client;
# ``generating`` (maybe another worker is on it) needs ``--force``.
RETRYABLE_STATUSES = frozenset({"queued", "failed"})
FORCE_STATUSES = frozenset({"generating"})
CONFIG_EXIT_CODE = 2

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
    return status


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
            "las orgánicas quedarán como fallidas con el motivo.[/yellow]"
        )
    processed = 0
    cycle = 0
    while max_cycles is None or cycle < max_cycles:
        if cycle % REQUEUE_EVERY_CYCLES == 0:
            _requeue_stale(db)
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


@app.command()
def run(
    once: Annotated[bool, typer.Option("--once", help="Procesa una pieza y termina.")] = False,
    poll_seconds: Annotated[
        float, typer.Option("--poll-seconds", help="Espera entre consultas con la cola vacía.")
    ] = 10.0,
    provider: ProviderOpt = None,
    workdir: WorkdirOpt = DEFAULT_WORKDIR,
) -> None:
    """Reclama piezas en cola y las procesa en bucle."""
    ctx = build_context(provider)
    try:
        run_loop(ctx, once=once, poll_seconds=poll_seconds, workdir=workdir)
    except KeyboardInterrupt:
        console.print("Worker detenido.")


@app.command()
def piece(
    piece_id: Annotated[str, typer.Argument(help="Id de la pieza.")],
    provider: ProviderOpt = None,
    workdir: WorkdirOpt = DEFAULT_WORKDIR,
    force: Annotated[
        bool,
        typer.Option("--force", help="Reprocesa también una pieza en generación (huérfana)."),
    ] = False,
) -> None:
    """Procesa una pieza concreta (reintento manual), sin pasar por la cola."""
    ctx = build_context(provider)
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
