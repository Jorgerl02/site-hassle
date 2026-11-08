"""Web delivery of a post-processed candidate: light Draco GLB, USDZ for AR Quick Look and a
``viewer.html`` built on ``<model-viewer>``.

Runs ``bpy_deliver.py`` through the core Blender launcher on ``<cand_dir>/model_post.glb``.
If ``model_web.glb`` exceeds ``size_limit_bytes`` it retries ONCE with half the triangles
and textures clamped to 1024 px; the final ``deliver_meta.json`` records every attempt.

model-viewer docs consulted on 2026-11-08 (modelviewer.dev via Context7): ``ar``,
``ar-modes`` (webxr / scene-viewer / quick-look), ``ios-src`` (USDZ for Quick Look),
``ar-scale="fixed"`` (no rescaling in AR: the piece keeps its real size). The version is
pinned (4.4.0 = current release on unpkg, ``@google/model-viewer``).
"""

from __future__ import annotations

import html
import json
import shutil
import string
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harness.core.blender import BlenderRun, run_blender_script
from harness.core.models import Piece
from harness.post.bpy_deliver import DEFAULT_JPEG_QUALITY, DEFAULT_MAX_TEX, DEFAULT_MAX_TRIS

BPY_DELIVER_SCRIPT = Path(__file__).with_name("bpy_deliver.py")
VIEWER_TEMPLATE = Path(__file__).with_name("viewer_template.html")
INPUT_GLB_FILENAME = "model_post.glb"
WEB_GLB_FILENAME = "model_web.glb"
USDZ_FILENAME = "model.usdz"
VIEWER_FILENAME = "viewer.html"
DELIVER_META_FILENAME = "deliver_meta.json"
DELIVER_LOG_FILENAME = "deliver_blender.log"
TMP_DIRNAME = ".deliver_tmp"  # re-encoded textures, removed after the run
DEFAULT_SIZE_LIMIT_BYTES = 5_000_000
RETRY_MAX_TEX = 1024
DEFAULT_TIMEOUT_S = 600
LOG_TAIL_CHARS = 4000
MODEL_VIEWER_VERSION = "4.4.0"
MODEL_VIEWER_SRC = (
    f"https://unpkg.com/@google/model-viewer@{MODEL_VIEWER_VERSION}/dist/model-viewer.min.js"
)


class BlenderDeliverError(RuntimeError):
    """Blender exited with an error or did not produce the expected outputs."""

    def __init__(self, message: str, log: str = "") -> None:
        super().__init__(f"{message}\n--- log Blender (final) ---\n{log[-LOG_TAIL_CHARS:]}")
        self.log = log


@dataclass
class DeliverResult:
    out_dir: Path
    glb_path: Path
    usdz_path: Path | None  # None when the USD export failed (see ``usdz_error``)
    viewer_path: Path
    meta_path: Path
    glb_bytes: int
    usdz_bytes: int | None
    tris_before: int
    tris_after: int
    max_tris: int  # limits of the attempt that produced the final files
    max_tex: int
    textures: list[dict[str, Any]]
    size_limit_bytes: int = DEFAULT_SIZE_LIMIT_BYTES
    attempts: list[dict[str, Any]] = field(default_factory=list)
    usdz_error: str | None = None
    seconds: float = 0.0
    log: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def within_limit(self) -> bool:
        return self.glb_bytes <= self.size_limit_bytes

    @property
    def retried(self) -> bool:
        return len(self.attempts) > 1


def build_args(
    glb_in: Path,
    out_glb: Path,
    out_usdz: Path,
    meta_path: Path,
    *,
    max_tris: int = DEFAULT_MAX_TRIS,
    max_tex: int = DEFAULT_MAX_TEX,
    jpeg_quality: int = DEFAULT_JPEG_QUALITY,
    tmp_dir: Path | None = None,
) -> list[str]:
    """Arguments passed to ``bpy_deliver.py`` after ``--``."""
    args = [
        "--in", str(glb_in),
        "--out-glb", str(out_glb),
        "--out-usdz", str(out_usdz),
        "--meta", str(meta_path),
        "--max-tris", str(max_tris),
        "--max-tex", str(max_tex),
        "--jpeg-quality", str(jpeg_quality),
    ]  # fmt: skip
    if tmp_dir is not None:
        args += ["--tmp-dir", str(tmp_dir)]
    return args


def parse_deliver_meta(meta_path: Path, log: str = "") -> dict[str, Any]:
    """Load ``deliver_meta.json`` and validate the keys the wrapper relies on."""
    meta_path = Path(meta_path)
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        for key in ("glb_bytes", "tris_before", "tris_after"):
            int(data[key])
        list(data.get("textures", []))
        return data
    except FileNotFoundError as exc:
        raise BlenderDeliverError(f"Blender no escribió {meta_path}", log) from exc
    except (KeyError, TypeError, ValueError) as exc:
        raise BlenderDeliverError(f"{meta_path} inválido: {exc!r}", log) from exc


def format_dimensions(piece: Piece) -> str:
    """``"Ancho 120 × alto 75 × fondo 60 cm"`` with a decimal comma."""

    def cm(value: float) -> str:
        return f"{value:g}".replace(".", ",")

    return (
        f"Ancho {cm(piece.width_cm)} × alto {cm(piece.height_cm)} × fondo {cm(piece.depth_cm)} cm"
    )


def render_viewer(
    piece: Piece,
    *,
    glb_name: str = WEB_GLB_FILENAME,
    usdz_name: str | None = USDZ_FILENAME,
    template_path: Path = VIEWER_TEMPLATE,
) -> str:
    """HTML of the viewer page; paths are relative to the page (same folder)."""
    esc = lambda value: html.escape(str(value), quote=True)  # noqa: E731
    ios_src = f'ios-src="{esc(usdz_name)}"' if usdz_name else ""
    template = string.Template(template_path.read_text(encoding="utf-8"))
    return template.substitute(
        title=esc(f"{piece.name} · 3D"),
        name=esc(piece.name),
        dimensions=esc(format_dimensions(piece)),
        alt=esc(f"Modelo 3D de {piece.name}"),
        glb=esc(glb_name),
        ios_src_attr=ios_src,
        model_viewer_src=esc(MODEL_VIEWER_SRC),
    )


def _log_text(run: BlenderRun) -> str:
    return f"$ {' '.join(run.cmd)}\n[exit {run.returncode}]\n{run.stdout}\n{run.stderr}"


def _run_once(
    glb_in: Path,
    out_dir: Path,
    *,
    max_tris: int,
    max_tex: int,
    timeout: int,
    blender_bin: Path | None,
) -> tuple[dict[str, Any], str]:
    out_glb, out_usdz = out_dir / WEB_GLB_FILENAME, out_dir / USDZ_FILENAME
    meta_path = out_dir / DELIVER_META_FILENAME
    for stale in (out_glb, out_usdz, meta_path):
        stale.unlink(missing_ok=True)  # never parse outputs from a previous run
    args = build_args(
        glb_in, out_glb, out_usdz, meta_path,
        max_tris=max_tris, max_tex=max_tex, tmp_dir=out_dir / TMP_DIRNAME,
    )  # fmt: skip
    run = run_blender_script(BPY_DELIVER_SCRIPT, args, timeout=timeout, blender_bin=blender_bin)
    log = _log_text(run)
    if not run.ok:
        raise BlenderDeliverError(f"bpy_deliver.py terminó con código {run.returncode}", log)
    if not out_glb.is_file():
        raise BlenderDeliverError(f"Blender no escribió {out_glb}", log)
    return parse_deliver_meta(meta_path, log), log


def deliver(
    cand_dir: Path,
    piece: Piece,
    *,
    max_tris: int = DEFAULT_MAX_TRIS,
    max_tex: int = DEFAULT_MAX_TEX,
    size_limit_bytes: int = DEFAULT_SIZE_LIMIT_BYTES,
    out_dir: Path | None = None,
    timeout: int = DEFAULT_TIMEOUT_S,
    blender_bin: Path | None = None,
    provenance: dict[str, Any] | None = None,
) -> DeliverResult:
    """Build ``model_web.glb``, ``model.usdz``, ``viewer.html`` and ``deliver_meta.json``
    from ``<cand_dir>/model_post.glb`` into ``out_dir`` (default: ``cand_dir``).

    A GLB above ``size_limit_bytes`` triggers one retry with ``max_tris // 2`` and textures
    ≤ 1024 px; if it is still too big the result is returned with ``within_limit = False``
    (no exception). ``provenance`` (``run_id``, ``variant``, ``candidate``…) is recorded in
    ``deliver_meta.json`` next to ``piece_id``. Raises ``FileNotFoundError`` without the input GLB,
    ``BlenderNotAvailable`` without a binary and ``BlenderDeliverError`` on Blender failures.
    """
    cand_dir = Path(cand_dir)
    glb_in = cand_dir / INPUT_GLB_FILENAME
    if not glb_in.is_file():
        raise FileNotFoundError(f"No existe el GLB postprocesado: {glb_in}")
    out_dir = Path(out_dir) if out_dir is not None else cand_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    plans = [(max_tris, max_tex), (max(1, max_tris // 2), min(max_tex, RETRY_MAX_TEX))]
    attempts: list[dict[str, Any]] = []
    logs: list[str] = []
    meta: dict[str, Any] = {}
    for tris_limit, tex_limit in plans:
        meta, log = _run_once(
            glb_in, out_dir,
            max_tris=tris_limit, max_tex=tex_limit, timeout=timeout, blender_bin=blender_bin,
        )  # fmt: skip
        logs.append(log)
        glb_bytes = int(meta["glb_bytes"])
        attempts.append(
            {
                "max_tris": tris_limit,
                "max_tex": tex_limit,
                "glb_bytes": glb_bytes,
                "usdz_bytes": meta.get("usdz_bytes"),
                "tris_after": int(meta["tris_after"]),
            }
        )
        if glb_bytes <= size_limit_bytes:
            break

    shutil.rmtree(out_dir / TMP_DIRNAME, ignore_errors=True)
    log = "\n\n".join(logs)
    (out_dir / DELIVER_LOG_FILENAME).write_text(log, encoding="utf-8")
    usdz_path = out_dir / USDZ_FILENAME
    usdz_ok = usdz_path.is_file() and not meta.get("usdz_error")
    viewer_path = out_dir / VIEWER_FILENAME
    viewer_path.write_text(
        render_viewer(piece, usdz_name=USDZ_FILENAME if usdz_ok else None), encoding="utf-8"
    )

    result = DeliverResult(
        out_dir=out_dir,
        glb_path=out_dir / WEB_GLB_FILENAME,
        usdz_path=usdz_path if usdz_ok else None,
        viewer_path=viewer_path,
        meta_path=out_dir / DELIVER_META_FILENAME,
        glb_bytes=int(meta["glb_bytes"]),
        usdz_bytes=int(meta["usdz_bytes"]) if usdz_ok and meta.get("usdz_bytes") else None,
        tris_before=int(meta["tris_before"]),
        tris_after=int(meta["tris_after"]),
        max_tris=attempts[-1]["max_tris"],
        max_tex=attempts[-1]["max_tex"],
        textures=list(meta.get("textures", [])),
        size_limit_bytes=size_limit_bytes,
        attempts=attempts,
        usdz_error=meta.get("usdz_error"),
        seconds=float(meta.get("seconds", 0.0)),
        log=log,
        raw=meta,
    )
    meta.update({k: v for k, v in (provenance or {}).items() if v is not None})
    meta.update(
        {
            "piece_id": piece.id,
            "size_limit_bytes": size_limit_bytes,
            "within_limit": result.within_limit,
            "attempts": attempts,
            "viewer": VIEWER_FILENAME,
            "model_viewer_version": MODEL_VIEWER_VERSION,
        }
    )
    result.meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return result
