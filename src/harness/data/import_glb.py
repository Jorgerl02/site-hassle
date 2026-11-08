"""Import an externally generated GLB (web UI, MCP, another tool) as a harness candidate.

Writes ``runs/<run_id>/<piece_id>/<variant>/cand_<n>/model.glb`` plus the same
``meta.json`` shape the CLI writes, and appends a result entry to the run meta so
``bakeoff eval`` / ``report`` treat it like any other variant. Post-processing is
NOT applied here: run ``bakeoff run --variants <variant> --run-id <run_id>`` is
not possible for imported variants, so call :func:`postprocess_imported` (or
``python -m harness.data.import_glb ... --post``) to apply the shared Blender step.
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from harness.core import storage
from harness.core.blender import BlenderNotAvailable
from harness.core.models import DEFAULT_SAMPLE_CSV, load_pieces
from harness.post.blender_post import BlenderPostError, postprocess


def import_glb(
    *,
    run_id: str,
    piece_id: str,
    variant: str,
    glb: Path,
    candidate: int = 1,
    cost_usd: float = 0.0,
    seconds: float = 0.0,
    meta: dict[str, Any] | None = None,
    runs_root: Path = storage.RUNS_ROOT,
    sample_csv: Path = DEFAULT_SAMPLE_CSV,
    post: bool = True,
) -> Path:
    pieces = {p.id: p for p in load_pieces(sample_csv)}
    piece = pieces[piece_id]
    workdir = storage.variant_dir(run_id, piece_id, variant, root=runs_root)
    cand_dir = storage.candidate_dir(workdir, candidate)
    dst = storage.model_path(cand_dir)
    shutil.copyfile(glb, dst)
    record: dict[str, Any] = {
        "piece_id": piece_id,
        "variant": variant,
        "index": candidate,
        "glb_path": str(dst),
        "cost_usd": float(cost_usd),
        "seconds": float(seconds),
        "meta": {"imported": True, "source_glb": str(glb), **(meta or {})},
    }
    if post:
        t0 = time.monotonic()
        try:
            result = postprocess(dst, storage.model_post_path(cand_dir), piece)
            record["post"] = {
                "ok": True,
                "seconds": time.monotonic() - t0,
                "errors": result.errors,
                "errors_axis": result.errors_axis,
                "scale_factor": result.scale_factor,
                "draco": result.draco,
                "triangles_before": result.tris_before,
                "triangles_after": result.tris_after,
            }
        except BlenderNotAvailable:
            record["post"] = {"ok": False, "reason": "sin Blender"}
        except BlenderPostError as exc:  # keep the candidate; eval falls back to model.glb
            record["post"] = {"ok": False, "reason": str(exc)[-2000:]}
    storage.write_meta(cand_dir, record)
    _append_run_meta(run_id, runs_root, record)
    return dst


def _append_run_meta(run_id: str, runs_root: Path, record: dict[str, Any]) -> None:
    run_dir = storage.run_dir(run_id, root=runs_root)
    path = run_dir / storage.META_FILENAME
    data: dict[str, Any] = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("run_id", run_id)
    data.setdefault("created_at", datetime.now(UTC).isoformat())
    results = [
        r
        for r in data.get("results", [])
        if not (r.get("piece_id") == record["piece_id"] and r.get("variant") == record["variant"])
    ]
    results.append(
        {
            "piece_id": record["piece_id"],
            "variant": record["variant"],
            "candidates": [record["glb_path"]],
            "cost_usd": record["cost_usd"],
            "seconds": record["seconds"],
            "imported": True,
        }
    )
    data["results"] = results
    data["total_cost_usd"] = round(
        sum(float(r.get("cost_usd", 0.0)) for r in results)
        + sum(float(e.get("cost_usd", 0.0)) for e in data.get("errors", [])),
        6,
    )
    data["updated_at"] = datetime.now(UTC).isoformat()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Importa un GLB externo como candidato del harness."
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--piece", required=True)
    parser.add_argument("--variant", required=True)
    parser.add_argument("--glb", required=True, type=Path)
    parser.add_argument("--candidate", type=int, default=1)
    parser.add_argument("--cost-usd", type=float, default=0.0)
    parser.add_argument("--seconds", type=float, default=0.0)
    parser.add_argument("--meta-json", type=str, default="{}", help="JSON extra para meta")
    parser.add_argument("--no-post", action="store_true")
    args = parser.parse_args(argv)
    dst = import_glb(
        run_id=args.run_id,
        piece_id=args.piece,
        variant=args.variant,
        glb=args.glb,
        candidate=args.candidate,
        cost_usd=args.cost_usd,
        seconds=args.seconds,
        meta=json.loads(args.meta_json),
        post=not args.no_post,
    )
    print(f"importado → {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
