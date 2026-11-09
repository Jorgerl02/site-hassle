"""Web delivery of a post-processed candidate: web GLB (KHR_mesh_quantization + WebP), USDZ
for AR Quick Look, a light public preview (GLB + USDZ) and a ``viewer.html`` built on
``<model-viewer>``.

Runs ``bpy_deliver.py`` through the core Blender launcher on ``<cand_dir>/model_post.glb``
(decimation, texture clamp, JPEG re-encode, USDZ, preview pass), then
``gltf-transform optimize --compress quantize --texture-compress webp`` (Node, via ``npx``)
on the plain GLBs Blender wrote. If ``model_web.glb`` exceeds ``size_limit_bytes`` it
retries ONCE with half the triangles and textures clamped to 1024 px; the final
``deliver_meta.json`` records every attempt.

Pietra by Bianca (``scripts/3d/README.md``) proved this combination on real devices:
quantization and ``EXT_texture_webp`` are decoded natively by model-viewer, while meshopt
failed to load on device and Draco / KTX2 fetch decoders from a CDN. USDZ keeps JPEG / PNG
(AR Quick Look accepts no WebP). The preview ships its own USDZ (``ios-src``): without it
model-viewer generates one on tap and that ``await`` breaks Safari's user activation, so AR
does not open on iPhone.

The CLI is pinned in ``tools/gltf/package.json`` + ``package-lock.json`` and installed on
the worker with ``npm ci --prefix tools/gltf`` (``scripts/setup_worker.sh``); delivery runs
``tools/gltf/node_modules/.bin/gltf-transform``, else ``npx --no-install`` of the same
pinned version (never downloads at delivery time), else ships the plain GLB with a warning
(``strict=True`` raises instead). ``deadline_s`` bounds the whole delivery (both attempts).

gltf-transform CLI 4.5.1 ``optimize --help`` read on 2026-11-09: ``--compress`` one of
draco / meshopt / quantize / false (default meshopt), ``--texture-compress`` ktx2 / webp /
avif / auto / false, ``--texture-size`` (max px, default 2048), ``--simplify`` (default
true: turned off here, the triangle budget is Blender's decimation). Docs
(gltf-transform.dev, ``quantize``): UVs outside [0, 1] are left unquantized, so tiled
material UVs survive.

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
import struct
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harness.core.blender import BlenderRun, run_blender_script
from harness.core.models import Piece
from harness.post.bpy_deliver import (
    DEFAULT_JPEG_QUALITY,
    DEFAULT_MAX_TEX,
    DEFAULT_MAX_TRIS,
    DEFAULT_PREVIEW_MAX_TEX,
    DEFAULT_PREVIEW_MAX_TRIS,
)

BPY_DELIVER_SCRIPT = Path(__file__).with_name("bpy_deliver.py")
VIEWER_TEMPLATE = Path(__file__).with_name("viewer_template.html")
INPUT_GLB_FILENAME = "model_post.glb"
WEB_GLB_FILENAME = "model_web.glb"
USDZ_FILENAME = "model.usdz"
VIEWER_FILENAME = "viewer.html"
DELIVER_META_FILENAME = "deliver_meta.json"
DELIVER_LOG_FILENAME = "deliver_blender.log"
TMP_DIRNAME = ".deliver_tmp"  # re-encoded textures and plain GLBs, removed after the run
RAW_GLB_FILENAME = "model_raw.glb"  # Blender's plain GLB, input of gltf-transform
PREVIEW_DIRNAME = "preview"
PREVIEW_GLB_FILENAME = "model_preview.glb"
PREVIEW_USDZ_FILENAME = "model_preview.usdz"
PREVIEW_RAW_GLB_FILENAME = "preview_raw.glb"
PREVIEW_MAX_TRIS = DEFAULT_PREVIEW_MAX_TRIS
PREVIEW_MAX_TEX = DEFAULT_PREVIEW_MAX_TEX
GLTF_TRANSFORM_PACKAGE = "@gltf-transform/cli@4.5.1"
REPO_ROOT = Path(__file__).resolve().parents[3]
GLTF_TOOLS_DIR = REPO_ROOT / "tools" / "gltf"
LOCAL_GLTF_TRANSFORM = GLTF_TOOLS_DIR / "node_modules" / ".bin" / "gltf-transform"
DEFAULT_DEADLINE_S = 900
OPTIMIZE_TIMEOUT_S = 600
DEFAULT_SIZE_LIMIT_BYTES = 5_000_000
RETRY_MAX_TEX = 1024
DEFAULT_TIMEOUT_S = 600
LOG_TAIL_CHARS = 4000
MODEL_VIEWER_VERSION = "4.4.0"
MODEL_VIEWER_SRC = (
    f"https://unpkg.com/@google/model-viewer@{MODEL_VIEWER_VERSION}/dist/model-viewer.min.js"
)


class DeliverError(RuntimeError):
    """Base class of the delivery failures."""


class OptimizeError(DeliverError):
    """gltf-transform failed and ``strict=True`` was requested."""


class DeliverDeadlineExceeded(DeliverError):
    """The whole delivery took longer than ``deadline_s``."""


class BlenderDeliverError(DeliverError):
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
    optimize_error: str | None = None  # gltf-transform failed: the plain GLB was shipped
    warnings: list[str] = field(default_factory=list)  # for the admin (fallbacks…)
    preview_glb_path: Path | None = None
    preview_usdz_path: Path | None = None
    preview_glb_bytes: int | None = None
    preview_usdz_bytes: int | None = None
    preview_tris_after: int | None = None

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
    preview_glb: Path | None = None,
    preview_usdz: Path | None = None,
    preview_max_tris: int = PREVIEW_MAX_TRIS,
    preview_max_tex: int = PREVIEW_MAX_TEX,
) -> list[str]:
    """Arguments passed to ``bpy_deliver.py`` after ``--``. ``out_glb`` (and
    ``preview_glb``) are the PLAIN GLBs that gltf-transform then optimizes."""
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
    if preview_glb is not None and preview_usdz is not None:
        args += [
            "--preview-glb", str(preview_glb),
            "--preview-usdz", str(preview_usdz),
            "--preview-max-tris", str(preview_max_tris),
            "--preview-max-tex", str(preview_max_tex),
        ]  # fmt: skip
    return args


def gltf_transform_command() -> list[str] | None:
    """How to launch the pinned CLI: the local install from ``tools/gltf`` (``npm ci``),
    else ``npx --no-install`` of the pinned package (only if already in npm's cache; never
    downloads), else ``None``."""
    if LOCAL_GLTF_TRANSFORM.is_file():
        return [str(LOCAL_GLTF_TRANSFORM)]
    npx = shutil.which("npx")
    if npx is not None:
        return [npx, "--no-install", GLTF_TRANSFORM_PACKAGE]
    return None


def build_optimize_args(
    src: Path, dst: Path, *, texture_size: int, runner: list[str] | None = None
) -> list[str]:
    """``gltf-transform optimize`` with the Pietra-proven flags: KHR_mesh_quantization
    (not meshopt, not Draco), WebP textures ≤ ``texture_size`` px and no simplification.
    ``runner`` is the launcher from :func:`gltf_transform_command`."""
    return [
        *(runner or [str(LOCAL_GLTF_TRANSFORM)]), "optimize", str(src), str(dst),
        "--compress", "quantize",
        "--texture-compress", "webp",
        "--texture-size", str(texture_size),
        "--simplify", "false",
    ]  # fmt: skip


def optimize_glb(
    src: Path, dst: Path, *, texture_size: int, timeout: float = OPTIMIZE_TIMEOUT_S
) -> tuple[str | None, str]:
    """Run gltf-transform on ``src`` → ``dst``. On failure (no CLI, CLI error, timeout)
    copy ``src`` to ``dst`` so delivery still has a valid (heavier) GLB and return
    ``(error, log)``; ``(None, log)`` on success."""
    runner = gltf_transform_command()
    dst.unlink(missing_ok=True)
    error: str | None = None
    log = ""
    if runner is None:
        error = (
            "gltf-transform no está instalado (npm ci --prefix tools/gltf): "
            "se entrega el GLB sin optimizar"
        )
    else:
        cmd = build_optimize_args(src, dst, texture_size=texture_size, runner=runner)
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
            log = f"$ {' '.join(cmd)}\n[exit {proc.returncode}]\n{proc.stdout}\n{proc.stderr}"
            if proc.returncode != 0 or not dst.is_file():
                error = f"gltf-transform terminó con código {proc.returncode}"
        except (OSError, subprocess.TimeoutExpired) as exc:
            error = f"gltf-transform no se pudo ejecutar: {type(exc).__name__}: {exc}"
            log = error
    if error is not None:
        shutil.copyfile(src, dst)
    return error, log


def glb_extensions(path: Path) -> list[str]:
    """``extensionsUsed`` of a GLB (reads only its JSON chunk)."""
    with open(path, "rb") as fh:
        header = fh.read(20)
        if len(header) < 20 or header[:4] != b"glTF":
            return []
        json_len = struct.unpack_from("<I", header, 12)[0]
        gltf = json.loads(fh.read(json_len))
    return sorted(gltf.get("extensionsUsed", []))


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


def _remaining(deadline: float, deadline_s: float, step: str) -> float:
    """Seconds left before ``deadline`` (monotonic); raises when nothing is left."""
    left = deadline - time.monotonic()
    if left <= 0:
        raise DeliverDeadlineExceeded(
            f"La entrega superó el plazo total de {deadline_s:g} s (antes de {step})"
        )
    return left


def _optimize_step(
    src: Path,
    dst: Path,
    *,
    texture_size: int,
    label: str,
    deadline: float,
    deadline_s: float,
    strict: bool,
    warnings: list[str],
) -> tuple[dict[str, Any], str]:
    budget = _remaining(deadline, deadline_s, f"optimizar {label}")
    error, log = optimize_glb(
        src, dst, texture_size=texture_size, timeout=min(OPTIMIZE_TIMEOUT_S, budget)
    )
    if error is not None:
        if time.monotonic() >= deadline:
            raise DeliverDeadlineExceeded(
                f"La entrega superó el plazo total de {deadline_s:g} s optimizando {label}"
            )
        if strict:
            raise OptimizeError(f"{label}: {error}\n{log[-LOG_TAIL_CHARS:]}")
        warnings.append(f"{label} sin optimizar (GLB sin cuantizar y con JPEG): {error}")
    info = {
        "glb_out": str(dst),
        "glb_bytes": dst.stat().st_size,
        "optimize_error": error,
        "compress": None if error else "quantize",
        "texture_format": None if error else "webp",
        "extensions_used": glb_extensions(dst),
    }
    return info, log


def _run_once(
    glb_in: Path,
    out_dir: Path,
    *,
    max_tris: int,
    max_tex: int,
    preview: bool,
    preview_max_tris: int,
    preview_max_tex: int,
    timeout: int,
    blender_bin: Path | None,
    deadline: float,
    deadline_s: float,
    strict: bool,
) -> tuple[dict[str, Any], str]:
    tmp_dir = out_dir / TMP_DIRNAME
    raw_glb, out_glb = tmp_dir / RAW_GLB_FILENAME, out_dir / WEB_GLB_FILENAME
    out_usdz, meta_path = out_dir / USDZ_FILENAME, out_dir / DELIVER_META_FILENAME
    preview_dir = out_dir / PREVIEW_DIRNAME
    preview_raw = tmp_dir / PREVIEW_RAW_GLB_FILENAME
    preview_glb = preview_dir / PREVIEW_GLB_FILENAME
    preview_usdz = preview_dir / PREVIEW_USDZ_FILENAME
    stale = [raw_glb, out_glb, out_usdz, meta_path, preview_raw, preview_glb, preview_usdz]
    for path in stale:
        path.unlink(missing_ok=True)  # never parse outputs from a previous run
    tmp_dir.mkdir(parents=True, exist_ok=True)
    if preview:
        preview_dir.mkdir(parents=True, exist_ok=True)
    args = build_args(
        glb_in, raw_glb, out_usdz, meta_path,
        max_tris=max_tris, max_tex=max_tex, tmp_dir=tmp_dir,
        preview_glb=preview_raw if preview else None,
        preview_usdz=preview_usdz if preview else None,
        preview_max_tris=preview_max_tris, preview_max_tex=preview_max_tex,
    )  # fmt: skip
    budget = _remaining(deadline, deadline_s, "Blender")
    blender_timeout = min(timeout, budget)
    try:
        run = run_blender_script(
            BPY_DELIVER_SCRIPT, args, timeout=blender_timeout, blender_bin=blender_bin
        )
    except subprocess.TimeoutExpired as exc:
        if budget <= timeout:  # the global deadline, not the per-run timeout, cut it
            raise DeliverDeadlineExceeded(
                f"La entrega superó el plazo total de {deadline_s:g} s dentro de Blender"
            ) from exc
        raise
    log = _log_text(run)
    if not run.ok:
        raise BlenderDeliverError(f"bpy_deliver.py terminó con código {run.returncode}", log)
    if not raw_glb.is_file():
        raise BlenderDeliverError(f"Blender no escribió {raw_glb}", log)
    meta = parse_deliver_meta(meta_path, log)
    warnings: list[str] = []

    meta["glb_raw_bytes"] = int(meta["glb_bytes"])
    info, opt_log = _optimize_step(
        raw_glb, out_glb, texture_size=max_tex, label="model_web.glb",
        deadline=deadline, deadline_s=deadline_s, strict=strict, warnings=warnings,
    )  # fmt: skip
    meta.update(info)
    logs = [log, opt_log]
    preview_meta = meta.get("preview")
    if preview and isinstance(preview_meta, dict) and preview_raw.is_file():
        preview_meta["glb_raw_bytes"] = preview_meta.get("glb_bytes")
        p_info, p_log = _optimize_step(
            preview_raw, preview_glb, texture_size=min(preview_max_tex, max_tex),
            label=f"{PREVIEW_DIRNAME}/{PREVIEW_GLB_FILENAME}",
            deadline=deadline, deadline_s=deadline_s, strict=strict, warnings=warnings,
        )  # fmt: skip
        preview_meta.update(p_info)
        logs.append(p_log)
    meta["warnings"] = warnings
    return meta, "\n\n".join(part for part in logs if part)


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
    preview: bool = True,
    preview_max_tris: int = PREVIEW_MAX_TRIS,
    preview_max_tex: int = PREVIEW_MAX_TEX,
    strict: bool = False,
    deadline_s: float = DEFAULT_DEADLINE_S,
) -> DeliverResult:
    """Build ``model_web.glb``, ``model.usdz``, ``viewer.html``, ``deliver_meta.json`` and
    (``preview=True``) ``preview/model_preview.glb`` + ``preview/model_preview.usdz``
    (≤ ``preview_max_tris`` triangles, textures ≤ ``preview_max_tex`` px) from
    ``<cand_dir>/model_post.glb`` into ``out_dir`` (default: ``cand_dir``).

    A GLB above ``size_limit_bytes`` triggers one retry with ``max_tris // 2`` and textures
    ≤ 1024 px; if it is still too big the result is returned with ``within_limit = False``
    (no exception). If gltf-transform is unavailable or fails, the plain Blender GLB is
    shipped, ``optimize_error`` says why and ``warnings`` in the meta carries it for the
    admin; with ``strict=True`` it raises ``OptimizeError`` instead. ``deadline_s`` bounds
    the whole delivery (both attempts, Blender and gltf-transform included): when it runs
    out ``DeliverDeadlineExceeded`` is raised. ``provenance`` (``run_id``, ``variant``,
    ``candidate``…) is recorded in ``deliver_meta.json`` next to ``piece_id``. Raises
    ``FileNotFoundError`` without the input GLB, ``BlenderNotAvailable`` without a binary
    and ``BlenderDeliverError`` on Blender failures.
    """
    cand_dir = Path(cand_dir)
    glb_in = cand_dir / INPUT_GLB_FILENAME
    if not glb_in.is_file():
        raise FileNotFoundError(f"No existe el GLB postprocesado: {glb_in}")
    out_dir = Path(out_dir) if out_dir is not None else cand_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if deadline_s <= 0:
        raise ValueError("deadline_s debe ser > 0")
    deadline = time.monotonic() + deadline_s
    plans = [(max_tris, max_tex), (max(1, max_tris // 2), min(max_tex, RETRY_MAX_TEX))]
    attempts: list[dict[str, Any]] = []
    logs: list[str] = []
    meta: dict[str, Any] = {}
    for tris_limit, tex_limit in plans:
        try:
            meta, log = _run_once(
                glb_in, out_dir,
                max_tris=tris_limit, max_tex=tex_limit, preview=preview,
                preview_max_tris=preview_max_tris, preview_max_tex=preview_max_tex,
                timeout=timeout, blender_bin=blender_bin,
                deadline=deadline, deadline_s=deadline_s, strict=strict,
            )  # fmt: skip
        except BaseException:
            shutil.rmtree(out_dir / TMP_DIRNAME, ignore_errors=True)
            raise
        logs.append(log)
        glb_bytes = int(meta["glb_bytes"])
        attempts.append(
            {
                "max_tris": tris_limit,
                "max_tex": tex_limit,
                "glb_bytes": glb_bytes,
                "glb_raw_bytes": meta.get("glb_raw_bytes"),
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

    preview_meta = meta.get("preview") if preview else None
    preview_glb = out_dir / PREVIEW_DIRNAME / PREVIEW_GLB_FILENAME
    preview_usdz = out_dir / PREVIEW_DIRNAME / PREVIEW_USDZ_FILENAME
    preview_glb_ok = isinstance(preview_meta, dict) and preview_glb.is_file()
    preview_usdz_ok = (
        isinstance(preview_meta, dict)
        and preview_usdz.is_file()
        and not preview_meta.get("usdz_error")
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
        optimize_error=meta.get("optimize_error"),
        warnings=list(meta.get("warnings", [])),
        preview_glb_path=preview_glb if preview_glb_ok else None,
        preview_usdz_path=preview_usdz if preview_usdz_ok else None,
        preview_glb_bytes=preview_glb.stat().st_size if preview_glb_ok else None,
        preview_usdz_bytes=preview_usdz.stat().st_size if preview_usdz_ok else None,
        preview_tris_after=(
            int(preview_meta["tris_after"]) if preview_glb_ok and preview_meta else None
        ),
    )
    for stale in ("draco", "draco_level", "jpeg_quality"):  # the web GLB is quantize + WebP
        meta.pop(stale, None)
    meta.update({k: v for k, v in (provenance or {}).items() if v is not None})
    meta.update(
        {
            "piece_id": piece.id,
            "size_limit_bytes": size_limit_bytes,
            "within_limit": result.within_limit,
            "attempts": attempts,
            "viewer": VIEWER_FILENAME,
            "model_viewer_version": MODEL_VIEWER_VERSION,
            "deadline_s": deadline_s,
            "strict": strict,
            "files": {
                "glb": WEB_GLB_FILENAME,
                "usdz": USDZ_FILENAME if usdz_ok else None,
                "viewer": VIEWER_FILENAME,
                "preview_glb": (
                    f"{PREVIEW_DIRNAME}/{PREVIEW_GLB_FILENAME}" if preview_glb_ok else None
                ),
                "preview_usdz": (
                    f"{PREVIEW_DIRNAME}/{PREVIEW_USDZ_FILENAME}" if preview_usdz_ok else None
                ),
            },
            "sizes": {
                "glb": result.glb_bytes,
                "usdz": result.usdz_bytes,
                "preview_glb": result.preview_glb_bytes,
                "preview_usdz": result.preview_usdz_bytes,
            },
        }
    )
    result.meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return result
