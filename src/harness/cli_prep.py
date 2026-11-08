"""``bakeoff requisitos`` and ``bakeoff validar``: input photo requirements and checks."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from harness.cli import _select_pieces, app, console
from harness.core.models import DEFAULT_SAMPLE_CSV, load_pieces
from harness.prep.requirements import PHOTO_REQUIREMENTS

REQUIREMENTS_EPILOG = "Requisitos de la foto: " + " · ".join(PHOTO_REQUIREMENTS)


@app.command(epilog=REQUIREMENTS_EPILOG)
def requisitos() -> None:
    """Muestra los requisitos de la foto de entrada."""
    console.print("[bold]Requisitos de la foto:[/bold]")
    for req in PHOTO_REQUIREMENTS:
        console.print(f"  · {req}")


def _photo_problems(photo: Path) -> list[str]:
    """``validate_input`` issues; an unreadable file becomes a problem, not a traceback."""
    from PIL import Image, UnidentifiedImageError

    from harness.prep.clean import validate_input

    if not photo.is_file():
        return [f"No existe el archivo {photo}"]
    try:
        return validate_input(photo)
    except (UnidentifiedImageError, Image.DecompressionBombError) as exc:
        return [f"La imagen no se puede leer (formato no admitido o archivo dañado): {exc}"]
    except (OSError, ValueError, SyntaxError) as exc:  # truncated/corrupt data inside Pillow
        return [f"La imagen no se puede leer (archivo dañado): {exc}"]


@app.command(epilog=REQUIREMENTS_EPILOG)
def validar(
    fotos: Annotated[
        list[Path] | None, typer.Argument(help="Fotos a comprobar (además de --pieces)")
    ] = None,
    pieces: Annotated[
        str | None, typer.Option(help="'all' o ids: comprueba las fotos de esas piezas")
    ] = None,
    sample: Annotated[Path, typer.Option(help="CSV de la muestra")] = DEFAULT_SAMPLE_CSV,
) -> None:
    """Comprueba que las fotos cumplen los requisitos de entrada (sale con 1 si alguna no)."""
    photos = list(fotos or [])
    if pieces:
        selected = _select_pieces(load_pieces(sample), pieces)
        photos += [Path(img) for p in selected for img in p.images]
    if not photos:
        raise typer.BadParameter("indica fotos o --pieces")
    from harness.prep.requirements import explain

    bad = 0
    for photo in photos:
        problems = _photo_problems(photo)
        if problems:
            bad += 1
            console.print(f"[red]✗[/red] {photo}")
            console.print(explain(problems), markup=False)
        else:
            console.print(f"[green]✓[/green] {photo}")
    console.print(f"{len(photos) - bad}/{len(photos)} fotos cumplen los requisitos")
    if bad:
        raise typer.Exit(1)
