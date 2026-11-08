"""Wrapper around ``bpy_post.py``: runs it through the core Blender launcher and parses
the ``post_meta.json`` it writes next to the output GLB."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harness.core.blender import BlenderRun, run_blender_script
from harness.core.models import SCALE_TOLERANCE, Piece

BPY_POST_SCRIPT = Path(__file__).with_name("bpy_post.py")
POST_META_FILENAME = "post_meta.json"
POST_LOG_FILENAME = "post_blender.log"
MAX_TRIS = 150_000
MAX_TEXTURE_PX = 2048
DEFAULT_TIMEOUT_S = 600
LOG_TAIL_CHARS = 4000


class BlenderPostError(RuntimeError):
    """Blender exited with an error or did not produce the expected outputs."""

    def __init__(self, message: str, log: str = "") -> None:
        super().__init__(f"{message}\n--- log Blender (final) ---\n{log[-LOG_TAIL_CHARS:]}")
        self.log = log


@dataclass
class PostResult:
    glb_path: Path
    meta_path: Path
    # Signed relative error keyed width/height/depth: height = vertical extent, width/depth
    # = horizontal extents paired by size (same rule as the evaluation; see bpy_post).
    errors: dict[str, float]
    tris_before: int
    tris_after: int
    textures: list[dict[str, Any]]
    seconds: float
    scale_factor: float | None = None
    errors_axis: dict[str, float] = field(default_factory=dict)  # per named axis
    draco: bool = False
    log: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def max_abs_error(self) -> float:
        return max(abs(v) for v in self.errors.values())

    @property
    def scale_ok(self) -> bool:
        return self.max_abs_error < SCALE_TOLERANCE


def build_args(
    glb_in: Path,
    glb_out: Path,
    meta_path: Path,
    piece: Piece,
    *,
    max_tris: int = MAX_TRIS,
    max_texture_px: int = MAX_TEXTURE_PX,
    draco: bool = False,
) -> list[str]:
    """Arguments passed to ``bpy_post.py`` after ``--``."""
    args = [
        "--in", str(glb_in),
        "--out", str(glb_out),
        "--meta", str(meta_path),
        "--width", repr(float(piece.width_cm)),
        "--height", repr(float(piece.height_cm)),
        "--depth", repr(float(piece.depth_cm)),
        "--max-tris", str(max_tris),
        "--max-tex", str(max_texture_px),
    ]  # fmt: skip
    if draco:
        args.append("--draco")
    return args


def parse_post_meta(meta_path: Path, glb_out: Path, log: str = "") -> PostResult:
    """Parse ``post_meta.json``; raises ``BlenderPostError`` if it is missing or malformed."""
    meta_path = Path(meta_path)
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        errors = {axis: float(data["errors"][axis]) for axis in ("width", "height", "depth")}
        return PostResult(
            glb_path=Path(glb_out),
            meta_path=meta_path,
            errors=errors,
            tris_before=int(data["tris_before"]),
            tris_after=int(data["tris_after"]),
            textures=list(data.get("textures", [])),
            seconds=float(data.get("seconds", 0.0)),
            scale_factor=(
                float(data["scale_factor"]) if data.get("scale_factor") is not None else None
            ),
            errors_axis={k: float(v) for k, v in (data.get("errors_axis") or {}).items()},
            draco=bool(data.get("draco", False)),
            log=log,
            raw=data,
        )
    except FileNotFoundError as exc:
        raise BlenderPostError(f"Blender no escribió {meta_path}", log) from exc
    except (KeyError, TypeError, ValueError) as exc:
        raise BlenderPostError(f"{meta_path} inválido: {exc!r}", log) from exc


def _log_text(run: BlenderRun) -> str:
    return f"$ {' '.join(run.cmd)}\n[exit {run.returncode}]\n{run.stdout}\n{run.stderr}"


def postprocess(
    glb_in: Path,
    glb_out: Path,
    piece: Piece,
    *,
    timeout: int = DEFAULT_TIMEOUT_S,
    blender_bin: Path | None = None,
    max_tris: int = MAX_TRIS,
    max_texture_px: int = MAX_TEXTURE_PX,
    draco: bool = False,
) -> PostResult:
    """Scale/centre/decimate ``glb_in`` into ``glb_out``.

    ``draco`` is off by default: trimesh (used by the evaluation) cannot decode
    ``KHR_draco_mesh_compression``.

    Writes ``post_meta.json`` and ``post_blender.log`` next to ``glb_out``. Raises
    ``BlenderNotAvailable`` without a binary, ``subprocess.TimeoutExpired`` on timeout and
    ``BlenderPostError`` (with the captured log) on a non-zero exit or missing outputs.
    """
    glb_in, glb_out = Path(glb_in), Path(glb_out)
    if not glb_in.is_file():
        raise FileNotFoundError(f"No existe el GLB de entrada: {glb_in}")
    glb_out.parent.mkdir(parents=True, exist_ok=True)
    meta_path = glb_out.parent / POST_META_FILENAME
    meta_path.unlink(missing_ok=True)  # never parse stale outputs from a previous run
    glb_out.unlink(missing_ok=True)

    args = build_args(
        glb_in, glb_out, meta_path, piece,
        max_tris=max_tris, max_texture_px=max_texture_px, draco=draco,
    )  # fmt: skip
    run = run_blender_script(BPY_POST_SCRIPT, args, timeout=timeout, blender_bin=blender_bin)
    log = _log_text(run)
    (glb_out.parent / POST_LOG_FILENAME).write_text(log, encoding="utf-8")

    if not run.ok:
        raise BlenderPostError(f"bpy_post.py terminó con código {run.returncode}", log)
    if not glb_out.is_file():
        raise BlenderPostError(f"Blender no escribió {glb_out}", log)
    return parse_post_meta(meta_path, glb_out, log)
