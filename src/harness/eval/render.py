"""Control renders of a candidate through headless Blender (see ``bpy_render.py``)."""

from __future__ import annotations

from pathlib import Path

from harness.core.blender import run_blender_script

BPY_SCRIPT = Path(__file__).with_name("bpy_render.py")
VIEWS: tuple[str, ...] = ("front", "side", "back", "three_quarter", "top")
RENDER_SIZE = 1024


class RenderError(RuntimeError):
    """Blender ran but did not produce every view."""


def expected_renders(out_dir: Path) -> list[Path]:
    return [Path(out_dir) / f"{view}.png" for view in VIEWS]


def existing_renders(out_dir: Path) -> list[Path] | None:
    """The five view PNGs if all of them exist, else ``None``."""
    paths = expected_renders(out_dir)
    return paths if all(p.is_file() for p in paths) else None


def render_views(
    glb: Path,
    out_dir: Path,
    *,
    size: int = RENDER_SIZE,
    timeout: int = 600,
    blender_bin: Path | None = None,
) -> list[Path]:
    """Render the five views; returns their paths in ``VIEWS`` order.

    Raises ``BlenderNotAvailable`` without a Blender binary and ``RenderError`` on failure.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    run = run_blender_script(
        BPY_SCRIPT, [str(glb), str(out_dir), str(size)], timeout=timeout, blender_bin=blender_bin
    )
    paths = expected_renders(out_dir)
    missing = [p.name for p in paths if not p.is_file()]
    if not run.ok or missing:
        tail = (run.stderr or run.stdout)[-2000:]
        raise RenderError(f"Blender devolvió {run.returncode}; faltan {missing}: {tail}")
    return paths
