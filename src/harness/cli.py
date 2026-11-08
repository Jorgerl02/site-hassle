"""``bakeoff`` command line: run variants, evaluate and report."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console

from harness.core import storage
from harness.core.models import DEFAULT_SAMPLE_CSV, Piece, load_pieces
from harness.core.registry import get_variant

app = typer.Typer(help="Bake-off de pipelines foto→3D.", no_args_is_help=True)
console = Console()


def _select_pieces(pieces: list[Piece], spec: str) -> list[Piece]:
    if spec.strip().lower() == "all":
        return pieces
    wanted = [s.strip() for s in spec.split(",") if s.strip()]
    by_id = {p.id: p for p in pieces}
    unknown = [w for w in wanted if w not in by_id]
    if unknown:
        raise typer.BadParameter(f"Piezas desconocidas: {', '.join(unknown)}")
    return [by_id[w] for w in wanted]


@app.command()
def run(
    variants: Annotated[str, typer.Option(help="Variantes separadas por comas, p. ej. A,B")],
    pieces: Annotated[str, typer.Option(help="'all' o ids separados por comas")] = "all",
    candidates: Annotated[int, typer.Option(min=1, help="Candidatos por pieza y variante")] = 2,
    run_id: Annotated[str | None, typer.Option(help="Id de la ejecución")] = None,
    sample: Annotated[Path, typer.Option(help="CSV de la muestra")] = DEFAULT_SAMPLE_CSV,
    runs_root: Annotated[Path, typer.Option(help="Carpeta raíz de salidas")] = storage.RUNS_ROOT,
) -> None:
    """Ejecuta las variantes sobre las piezas y escribe meta.json por candidato y por run."""
    run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    selected = _select_pieces(load_pieces(sample), pieces)
    if not selected:
        console.print(f"[red]No hay piezas en {sample}.[/red]")
        raise typer.Exit(1)
    try:
        resolved = [get_variant(name) for name in variants.split(",") if name.strip()]
    except KeyError as exc:
        raise typer.BadParameter(str(exc.args[0])) from exc

    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for piece in selected:
        for variant in resolved:
            workdir = storage.variant_dir(run_id, piece.id, variant.name, runs_root)
            console.print(f"[bold]{piece.id}[/bold] · variante {variant.name}")
            try:
                result = variant.run(piece, workdir, candidates)
            except Exception as exc:  # one failing piece/variant must not stop the run
                console.print(f"  [red]error:[/red] {exc}")
                errors.append({"piece_id": piece.id, "variant": variant.name, "error": repr(exc)})
                continue
            for cand in result.candidates:
                cand_dir = storage.candidate_dir(workdir, cand.index)
                meta = storage.read_meta(cand_dir)
                meta.update(
                    piece_id=piece.id, variant=result.variant, **cand.model_dump(mode="json")
                )
                storage.write_meta(cand_dir, meta)
            results.append(result.model_dump(mode="json"))

    total = sum(c["cost_usd"] for r in results for c in r["candidates"])
    storage.write_meta(
        storage.run_dir(run_id, runs_root),
        {
            "run_id": run_id,
            "created_at": datetime.now(UTC).isoformat(),
            "variants": [v.name for v in resolved],
            "pieces": [p.id for p in selected],
            "candidates": candidates,
            "total_cost_usd": total,
            "results": results,
            "errors": errors,
        },
    )
    console.print(
        f"Run [bold]{run_id}[/bold]: {len(results)} resultados, {len(errors)} errores, "
        f"coste {total:.2f} USD"
    )


def _eval_module():
    try:
        import harness.eval as eval_module
    except ModuleNotFoundError as exc:
        if exc.name != "harness.eval":
            raise
        console.print(
            "[red]El módulo de evaluación (harness.eval) aún no existe; "
            "se implementa en la Tarea 6.[/red]"
        )
        raise typer.Exit(1) from None
    return eval_module


@app.command("eval")
def eval_(run_id: Annotated[str, typer.Option(help="Id de la ejecución")]) -> None:
    """Evalúa una ejecución (geometría, renders, juez VLM, hoja ciega)."""
    _eval_module().evaluate_run(run_id)


@app.command()
def report(run_id: Annotated[str, typer.Option(help="Id de la ejecución")]) -> None:
    """Genera el informe de una ejecución evaluada."""
    _eval_module().build_report(run_id)


if __name__ == "__main__":
    app()
