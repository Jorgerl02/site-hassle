"""``bakeoff deliver``: web delivery (light GLB, USDZ and viewer) of chosen candidates."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Annotated

import typer

from harness.cli import PREFLIGHT_EXIT_CODE, _select_pieces, app, console
from harness.core import storage
from harness.core.blender import BlenderNotAvailable
from harness.core.models import DEFAULT_SAMPLE_CSV, load_pieces


class _UserError(Exception):
    """A problem with the user's arguments or data, printed without a traceback."""


def _candidate_indices(workdir: Path, needs: str | None = None) -> list[int]:
    indices = []
    for cand in workdir.glob("cand_*"):
        suffix = cand.name.removeprefix("cand_")
        if cand.is_dir() and suffix.isdigit() and (needs is None or (cand / needs).is_file()):
            indices.append(int(suffix))
    return sorted(indices)


def _pick_candidate(
    run_root: Path, piece_id: str, variant: str | None, candidate: int | None
) -> tuple[str, int, Path]:
    """``(variant, candidate, cand_dir)`` to deliver; ambiguity is an error, never a guess."""
    needs = storage.model_post_path(Path()).name
    piece_dir = run_root / piece_id
    if not piece_dir.is_dir():
        raise _UserError(f"{piece_id}: no hay resultados en {run_root}")
    if variant is None:
        options = sorted(
            d.name for d in piece_dir.iterdir() if d.is_dir() and _candidate_indices(d, needs)
        )
        if len(options) != 1:
            listed = ", ".join(options) or "ninguna"
            raise _UserError(f"{piece_id}: indica --variant (variantes con {needs}: {listed})")
        variant = options[0]
    workdir = piece_dir / variant
    if candidate is None:
        options_idx = _candidate_indices(workdir, needs)
        if len(options_idx) != 1:
            listed = ", ".join(map(str, options_idx)) or "ninguno"
            raise _UserError(
                f"{piece_id}/{variant}: indica --candidate (candidatos con {needs}: {listed})"
            )
        candidate = options_idx[0]
    cand_dir = storage.candidate_dir(workdir, candidate)
    if not storage.model_post_path(cand_dir).is_file():
        raise _UserError(f"{piece_id}/{variant}: no existe {storage.model_post_path(cand_dir)}")
    return variant, candidate, cand_dir


def _mb(n_bytes: int | None) -> str:
    return "—" if n_bytes is None else f"{n_bytes / 1_000_000:.2f} MB".replace(".", ",")


def _int_es(value: int) -> str:
    return f"{value:,}".replace(",", ".")


@app.command("deliver")
def deliver_cmd(
    run_id: Annotated[str, typer.Option(help="Id de la ejecución")],
    pieces: Annotated[str, typer.Option(help="Ids separados por comas, p. ej. p05,p15")],
    variant: Annotated[
        str | None, typer.Option(help="Variante; obligatoria si la pieza tiene varias")
    ] = None,
    candidate: Annotated[
        int | None, typer.Option(min=1, help="Candidato; obligatorio si hay varios")
    ] = None,
    max_tris: Annotated[int, typer.Option(min=1, help="Triángulos máximos del GLB web")] = 60_000,
    max_tex: Annotated[int, typer.Option(min=1, help="Lado máximo de las texturas (px)")] = 2048,
    size_limit: Annotated[
        int, typer.Option(min=1, help="Tamaño máximo del GLB web en bytes")
    ] = 5_000_000,
    out_dir: Annotated[
        Path | None,
        typer.Option(help="Carpeta de salida (una subcarpeta por pieza); por defecto el candidato"),
    ] = None,
    runs_root: Annotated[Path, typer.Option(help="Carpeta raíz de salidas")] = storage.RUNS_ROOT,
    sample: Annotated[Path, typer.Option(help="CSV de la muestra")] = DEFAULT_SAMPLE_CSV,
) -> None:
    """Entrega web: GLB ligero (Draco), USDZ para RA en iPhone y viewer.html por pieza."""
    from harness.post import deliver as post_deliver

    run_root = storage.run_dir(run_id, runs_root)
    if variant is not None:
        variant = variant.strip().upper()  # same convention as `run`
    selected = _select_pieces(load_pieces(sample), pieces)
    failures = over = 0
    viewer_dirs: list[Path] = []
    for piece in selected:
        try:
            var, cand, cand_dir = _pick_candidate(run_root, piece.id, variant, candidate)
        except _UserError as exc:
            console.print(f"[red]✗[/red] {exc}")
            failures += 1
            continue
        console.print(f"[bold]{piece.id}[/bold] · {var}/cand_{cand}")
        target = out_dir / piece.id if out_dir is not None else None
        try:
            result = post_deliver.deliver(
                cand_dir,
                piece,
                max_tris=max_tris,
                max_tex=max_tex,
                size_limit_bytes=size_limit,
                out_dir=target,
            )
        except BlenderNotAvailable as exc:
            console.print(f"[red]La entrega necesita Blender:[/red] {exc}")
            raise typer.Exit(PREFLIGHT_EXIT_CODE) from None
        except (post_deliver.BlenderDeliverError, FileNotFoundError, OSError) as exc:
            console.print(f"  [red]error:[/red] {exc}", markup=False)
            failures += 1
            continue
        except subprocess.TimeoutExpired as exc:
            console.print(f"  [red]timeout de Blender ({exc.timeout} s)[/red]")
            failures += 1
            continue
        status = (
            "[green]dentro del límite[/green]"
            if result.within_limit
            else f"[red]SUPERA el límite de {_mb(result.size_limit_bytes)}[/red]"
        )
        retry = " (con reintento)" if result.retried else ""
        console.print(f"  GLB web: {_mb(result.glb_bytes)} · {status}{retry}")
        usdz = _mb(result.usdz_bytes) if result.usdz_path else f"no generado ({result.usdz_error})"
        console.print(f"  USDZ: {usdz}")
        console.print(f"  Triángulos: {_int_es(result.tris_before)} → {_int_es(result.tris_after)}")
        console.print(f"  Visor: {result.viewer_path}")
        viewer_dirs.append(result.out_dir)
        over += not result.within_limit
    if viewer_dirs:
        served = out_dir if out_dir is not None else viewer_dirs[0]
        page = (viewer_dirs[0] / post_deliver.VIEWER_FILENAME).relative_to(served).as_posix()
        console.print(
            f"Para verlo: python -m http.server 8000 --directory {served} y abre "
            f"http://localhost:8000/{page} (la RA en el móvil necesita HTTPS)"
        )
    if failures or over:
        raise typer.Exit(1)
