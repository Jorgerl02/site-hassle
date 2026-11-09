"""Real PBR material library: replace a generated texture with a CC0 scan (ambientCG),
tone-matched to the photo, matte and tiled at real size.

Recipe proven in Pietra by Bianca (``scripts/3d/build-travertine-piece.mjs``): keep the
generated geometry, swap every material for a real PBR (Travertine009 there), make the
Color map's MEAN equal the photo's colour with a mild desaturation (0.95) and a per-channel
gain (brightness alone or a hard desaturation turned it grey), drop the gloss (honed stone
is matte) and tile the maps so the grain has a realistic size.

Pieces:
- ``materials.json`` (next to this module): the manifest (id, labels EN/ES, ambientCG asset
  and URL, CC0, physical tile size, matte / roughness / metallic, normal strength).
- ``scripts/fetch_materials.py`` downloads the 1K-JPG packages into ``data/materials/<id>/``
  (``Color.jpg``, ``NormalGL.jpg``, ``Roughness.jpg``; gitignored).
- :func:`apply_material` prepares the maps here (tone match, roughness remap) and runs
  ``bpy_materials.py`` in Blender to rewrite the UVs and the materials.
"""

from __future__ import annotations

import json
import re
import shutil
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from harness.core.blender import BlenderRun, run_blender_script
from harness.post.bpy_materials import repeats_per_unit  # noqa: F401 — re-exported

MANIFEST_PATH = Path(__file__).with_name("materials.json")
BPY_MATERIALS_SCRIPT = Path(__file__).with_name("bpy_materials.py")
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MATERIALS_DIR = REPO_ROOT / "data" / "materials"
MAP_NAMES = ("Color", "NormalGL", "Roughness")
DESATURATE = 0.95
TONE_ITERATIONS = 6
JPEG_QUALITY = 92
# Photo pixels outside these luminance percentiles are ignored when measuring the object's
# colour: the darkest quarter is the side in shade and the cast shadow, the top 5 % the
# highlights. What is left approximates the albedo better than the plain mean, which would
# be darkened twice (once by the photo's shading, again by the render's). Measured on the
# travertine pedestal fixture: plain mean (184, 165, 144) → render of the matched scan ≈ 0,9 ×
# that, visibly greyer than the photo; trimmed (199, 182, 163) → render ≈ the photo's mean.
PHOTO_TRIM_PERCENTILES = (25.0, 95.0)
REC709 = np.array([0.2126, 0.7152, 0.0722])
DEFAULT_TIMEOUT_S = 600
LOG_TAIL_CHARS = 4000
TMP_DIRNAME = ".materials_tmp"


class MaterialError(RuntimeError):
    """Unknown material, missing maps or a Blender failure."""

    def __init__(self, message: str, log: str = "") -> None:
        tail = f"\n--- log Blender (final) ---\n{log[-LOG_TAIL_CHARS:]}" if log else ""
        super().__init__(f"{message}{tail}")
        self.log = log


@dataclass(frozen=True)
class Material:
    id: str
    label_en: str
    label_es: str
    asset: str
    url: str
    license: str
    tile_cm: float
    matte: bool
    roughness: float
    metallic: float
    normal_strength: float
    vertical_grain: bool = False
    source_dimension_cm: float | None = None
    sha256: dict[str, str] = field(default_factory=dict)  # pinned hash per map name

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Material:
        return cls(
            id=data["id"],
            label_en=data["label"]["en"],
            label_es=data["label"]["es"],
            asset=data["asset"],
            url=data["url"],
            license=data["license"],
            tile_cm=float(data["tile_cm"]),
            matte=bool(data["matte"]),
            roughness=float(data["roughness"]),
            metallic=float(data["metallic"]),
            normal_strength=float(data["normal_strength"]),
            vertical_grain=bool(data.get("vertical_grain", False)),
            source_dimension_cm=data.get("source_dimension_cm"),
            sha256=dict(data.get("sha256") or {}),
        )

    def map_path(self, name: str, materials_dir: Path | None = None) -> Path:
        """Local path of map ``name`` (``Color``, ``NormalGL`` or ``Roughness``)."""
        return Path(materials_dir or DEFAULT_MATERIALS_DIR) / self.id / f"{name}.jpg"


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Material]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {m["id"]: Material.from_dict(m) for m in data["materials"]}


def get_material(material_id: str, manifest: dict[str, Material] | None = None) -> Material:
    manifest = manifest if manifest is not None else load_manifest()
    try:
        return manifest[material_id]
    except KeyError as exc:
        known = ", ".join(sorted(manifest))
        raise MaterialError(f"Material desconocido: {material_id!r} (hay: {known})") from exc


# --------------------------------------------------------------------------- detection

# (material id, accent-free regexes matched as whole words). Travertine is checked before
# anything else: "mármol travertino" is travertine, not white marble.
MATERIAL_STEMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("travertine", (r"travertin[oae]s?",)),
    ("white_marble", (r"marmol(?:es)?", r"marbles?")),
    ("walnut", (r"nogal(?:es)?", r"walnuts?")),
    ("oak", (r"robles?", r"oaks?", r"oaken")),
    ("white_plaster", (
        r"lacad[oa]s?", r"lacquer(?:ed)?", r"laca", r"yesos?", r"plaster", r"estuco",
        r"stucco", r"escayola",
    )),
    ("boucle", (r"boucle", r"borreguito", r"lana", r"wool(?:en)?", r"teddy")),
    ("linen", (r"lino", r"linen")),
    ("leather", (r"piel(?:es)?", r"cuero", r"leather")),
)  # fmt: skip
PRIORITY_IDS = ("travertine",)


def normalise_text(text: str) -> str:
    """Lowercase without accents: ``"Bouclé MÁRMOL"`` → ``"boucle marmol"``."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _first_match(text: str) -> tuple[int, str] | None:
    best: tuple[int, str] | None = None
    for material_id, stems in MATERIAL_STEMS:
        for stem in stems:
            match = re.search(rf"\b{stem}\b", text)
            if match and (best is None or match.start() < best[0]):
                best = (match.start(), material_id)
    return best


def detect_material(name: str, notes: str) -> str | None:
    """Material id named in the piece's name or notes (ES/EN, accent-insensitive), or None.

    Travertine wins whenever it is mentioned; otherwise the material named first in the
    name wins (the name usually carries the main material: «Sofá de lino con patas de
    roble» → linen), then the first one in the notes.
    """
    texts = [normalise_text(name), normalise_text(notes)]
    for material_id in PRIORITY_IDS:
        stems = dict(MATERIAL_STEMS)[material_id]
        if any(re.search(rf"\b{stem}\b", t) for t in texts for stem in stems):
            return material_id
    for text in texts:
        found = _first_match(text)
        if found:
            return found[1]
    return None


# --------------------------------------------------------------------------- colour


def photo_mean_color(photo: Path) -> tuple[int, int, int]:
    """Mean sRGB colour of the object in ``photo`` (rembg mask from ``harness.prep.clean``),
    ignoring its darkest quarter and brightest 5 % (see ``PHOTO_TRIM_PERCENTILES``)."""
    from harness.prep import clean  # rembg is heavy: only loaded when a photo is measured

    with Image.open(photo) as img:
        rgb = img.convert("RGB")
    mask = np.asarray(clean._object_mask(clean._remove_background(rgb))) > 0
    return masked_mean_color(np.asarray(rgb), mask)


def masked_mean_color(rgb: np.ndarray, mask: np.ndarray) -> tuple[int, int, int]:
    """Trimmed mean colour of the ``mask`` pixels of an (H, W, 3) uint8 image."""
    pixels = np.asarray(rgb, dtype=np.float64)[np.asarray(mask, dtype=bool)]
    if pixels.size == 0:
        raise ValueError("La máscara del objeto está vacía: no se puede medir su color")
    lum = pixels @ REC709
    lo, hi = np.percentile(lum, PHOTO_TRIM_PERCENTILES)
    keep = (lum >= lo) & (lum <= hi)
    if keep.any():
        pixels = pixels[keep]
    mean = pixels.mean(axis=0)
    return int(round(mean[0])), int(round(mean[1])), int(round(mean[2]))


def tone_match(
    pixels: np.ndarray,
    target_rgb: tuple[int, int, int],
    *,
    desaturate: float = DESATURATE,
    iterations: int = TONE_ITERATIONS,
) -> np.ndarray:
    """Pietra recipe: mild desaturation (lerp towards Rec.709 luminance, ``desaturate`` of
    the chroma kept) then a per-channel gain so the image MEAN equals ``target_rgb``,
    clamped to [0, 255]. Clamping lowers the mean of bright channels, so the gain is
    re-applied a few times. Returns uint8 of the same shape."""
    img = np.asarray(pixels, dtype=np.float64)[..., :3].copy()
    lum = (img @ REC709)[..., None]
    img = lum + desaturate * (img - lum)
    target = np.asarray(target_rgb, dtype=np.float64)
    for _ in range(iterations):
        mean = img.reshape(-1, 3).mean(axis=0)
        gain = np.where(mean > 1e-6, target / np.maximum(mean, 1e-6), 1.0)
        img = np.clip(img * gain, 0.0, 255.0)
        if np.all(np.abs(img.reshape(-1, 3).mean(axis=0) - target) < 0.5):
            break
    return np.round(img).astype(np.uint8)


def remap_mean(pixels: np.ndarray, target_mean: float) -> np.ndarray:
    """Gain on a single-channel map (0–255) so its mean is ``target_mean`` (0–1)."""
    img = np.asarray(pixels, dtype=np.float64)
    target = float(target_mean) * 255.0
    for _ in range(TONE_ITERATIONS):
        mean = img.mean()
        if mean <= 1e-6:
            img = np.full_like(img, target)
            break
        img = np.clip(img * (target / mean), 0.0, 255.0)
        if abs(img.mean() - target) < 0.5:
            break
    return np.round(img).astype(np.uint8)


# --------------------------------------------------------------------------- Blender


def build_args(
    glb_in: Path,
    glb_out: Path,
    meta_path: Path,
    material: Material,
    *,
    color: Path,
    normal: Path | None,
    roughness_map: Path | None,
    matte: bool,
    real_size_cm: tuple[float, float, float] | None,
    uv_mode: str = "auto",
) -> list[str]:
    """Arguments passed to ``bpy_materials.py`` after ``--``. ``matte`` is the effective
    flag (caller's ``matte`` AND the manifest's): roughness 1, metallic 0, no map."""
    args = [
        "--in", str(glb_in),
        "--out", str(glb_out),
        "--meta", str(meta_path),
        "--material-id", material.id,
        "--color", str(color),
        "--tile-cm", f"{material.tile_cm:g}",
        "--uv-mode", uv_mode,
        "--roughness", "1" if matte else f"{material.roughness:g}",
        "--metallic", "0" if matte else f"{material.metallic:g}",
    ]  # fmt: skip
    if normal is not None and material.normal_strength > 0:
        args += ["--normal", str(normal), "--normal-strength", f"{material.normal_strength:g}"]
    if roughness_map is not None and not matte:
        args += ["--roughness-map", str(roughness_map)]
    if material.vertical_grain:
        args.append("--vertical-grain")
    if real_size_cm is not None:
        args += ["--real-size", *(f"{float(v):g}" for v in real_size_cm)]
    return args


def _prepare_maps(
    material: Material,
    materials_dir: Path,
    tmp_dir: Path,
    target_rgb: tuple[int, int, int] | None,
    matte: bool,
) -> tuple[Path, Path | None, Path | None, dict[str, Any]]:
    paths = {name: material.map_path(name, materials_dir) for name in MAP_NAMES}
    missing = [str(p) for name, p in paths.items() if name == "Color" and not p.is_file()]
    if missing:
        raise MaterialError(
            f"Faltan los mapas de {material.id} ({', '.join(missing)}): "
            "ejecuta `uv run python scripts/fetch_materials.py`"
        )
    tmp_dir.mkdir(parents=True, exist_ok=True)
    info: dict[str, Any] = {}
    color = paths["Color"]
    with Image.open(color) as img:
        src = np.asarray(img.convert("RGB"))
    info["color_mean_source"] = [round(float(v), 1) for v in src.reshape(-1, 3).mean(axis=0)]
    if target_rgb is not None:
        matched = tone_match(src, target_rgb)
        color = tmp_dir / f"{material.id}_Color.jpg"
        Image.fromarray(matched).save(color, quality=JPEG_QUALITY)
        info["color_mean"] = [round(float(v), 1) for v in matched.reshape(-1, 3).mean(axis=0)]
    info["target_rgb"] = list(target_rgb) if target_rgb is not None else None

    rough: Path | None = None
    if not matte and paths["Roughness"].is_file():
        with Image.open(paths["Roughness"]) as img:
            values = remap_mean(np.asarray(img.convert("L")), material.roughness)
        rough = tmp_dir / f"{material.id}_Roughness.jpg"
        Image.fromarray(values).save(rough, quality=JPEG_QUALITY)
    normal = paths["NormalGL"] if paths["NormalGL"].is_file() else None
    missing_maps = []
    if normal is None and material.normal_strength > 0:
        missing_maps.append("NormalGL")
    if not matte and not paths["Roughness"].is_file():
        missing_maps.append("Roughness")
    info["missing_maps"] = missing_maps
    return color, normal, rough, info


def validate_rgb(value: Any) -> tuple[int, int, int]:
    """Three integers in [0, 255]; raises ``ValueError`` otherwise."""
    try:
        r, g, b = value
    except (TypeError, ValueError) as exc:
        raise ValueError(f"target_rgb debe tener 3 componentes: {value!r}") from exc
    rgb = []
    for c in (r, g, b):
        if isinstance(c, bool) or not isinstance(c, (int, np.integer)) or not 0 <= c <= 255:
            raise ValueError(f"target_rgb debe ser 3 enteros entre 0 y 255: {value!r}")
        rgb.append(int(c))
    return rgb[0], rgb[1], rgb[2]


def _log_text(run: BlenderRun) -> str:
    return f"$ {' '.join(run.cmd)}\n[exit {run.returncode}]\n{run.stdout}\n{run.stderr}"


def apply_material(
    glb_in: Path,
    glb_out: Path,
    *,
    material_id: str,
    target_rgb: tuple[int, int, int] | None = None,
    real_size_cm: tuple[float, float, float] | None = None,
    matte: bool = True,
    blender_bin: Path | None = None,
    materials_dir: Path | None = None,
    uv_mode: str = "auto",
    timeout: int = DEFAULT_TIMEOUT_S,
) -> dict[str, Any]:
    """Replace every material of ``glb_in`` with the library material ``material_id`` and
    write ``glb_out`` (plain GLB, ready for ``deliver``).

    ``target_rgb`` (e.g. :func:`photo_mean_color`) tone-matches the Color map; ``None``
    keeps the scan's own colour. ``real_size_cm`` = (width, height, depth) of the real piece
    sets the tiling (one repeat = the material's ``tile_cm``); without it the GLB is taken
    to be in metres. ``matte`` forces roughness 1 / metallic 0 unless the manifest marks the
    material as not matte (polished marble, leather), which then keeps its Roughness map.
    Returns the Blender meta (UV decision per mesh, repeats, maps) plus the tone-match
    numbers; it is also written next to ``glb_out`` as ``<stem>_materials.json``.
    Raises ``MaterialError`` (unknown id, maps not fetched, Blender failure) and
    ``BlenderNotAvailable`` without a binary.
    """
    glb_in, glb_out = Path(glb_in), Path(glb_out)
    if not glb_in.is_file():
        raise FileNotFoundError(f"No existe el GLB: {glb_in}")
    material = get_material(material_id)
    if target_rgb is not None:
        target_rgb = validate_rgb(target_rgb)
    warnings: list[str] = []
    if real_size_cm is None:
        warnings.append(
            "Sin medidas reales (real_size_cm): el tamaño del grano supone que el GLB está "
            "en metros"
        )
    effective_matte = bool(matte and material.matte)
    materials_dir = Path(materials_dir) if materials_dir is not None else DEFAULT_MATERIALS_DIR
    glb_out.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = glb_out.parent / TMP_DIRNAME
    meta_path = glb_out.with_name(f"{glb_out.stem}_materials.json")
    try:
        color, normal, rough, info = _prepare_maps(
            material, materials_dir, tmp_dir, target_rgb, effective_matte
        )
        args = build_args(
            glb_in, glb_out, meta_path, material,
            color=color, normal=normal, roughness_map=rough, matte=effective_matte,
            real_size_cm=real_size_cm, uv_mode=uv_mode,
        )  # fmt: skip
        glb_out.unlink(missing_ok=True)
        meta_path.unlink(missing_ok=True)
        run = run_blender_script(
            BPY_MATERIALS_SCRIPT, args, timeout=timeout, blender_bin=blender_bin
        )
        log = _log_text(run)
        if not run.ok or not glb_out.is_file() or not meta_path.is_file():
            raise MaterialError(f"bpy_materials.py falló (código {run.returncode})", log)
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    meta.update(
        {
            "material": {
                "id": material.id,
                "asset": material.asset,
                "license": material.license,
                "url": material.url,
                "label": {"en": material.label_en, "es": material.label_es},
            },
            "matte": effective_matte,
            **info,
        }
    )
    warnings += [f"Falta el mapa {name} de {material.id}" for name in info["missing_maps"]]
    meta["warnings"] = warnings
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta
