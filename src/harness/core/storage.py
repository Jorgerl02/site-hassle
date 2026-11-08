"""Output layout helpers.

runs/<run_id>/<piece_id>/<variant>/cand_<n>/{model.glb, model_post.glb, renders/*.png, meta.json}
runs/<run_id>/eval/{scores.jsonl, blind_sheet.csv, blind_key.csv, report.md}

Directory helpers create the directory they return. Candidate indices start at 1.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

RUNS_ROOT = Path("runs")
META_FILENAME = "meta.json"


def _mkdir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_dir(run_id: str, root: Path = RUNS_ROOT) -> Path:
    return _mkdir(Path(root) / run_id)


def variant_dir(run_id: str, piece_id: str, variant: str, root: Path = RUNS_ROOT) -> Path:
    """Workdir handed to ``Variant.run``."""
    return _mkdir(run_dir(run_id, root) / piece_id / variant)


def candidate_dir(workdir: Path, index: int) -> Path:
    return _mkdir(Path(workdir) / f"cand_{index}")


def model_path(cand_dir: Path) -> Path:
    return Path(cand_dir) / "model.glb"


def model_post_path(cand_dir: Path) -> Path:
    return Path(cand_dir) / "model_post.glb"


def renders_dir(cand_dir: Path) -> Path:
    return _mkdir(Path(cand_dir) / "renders")


def eval_dir(run_id: str, root: Path = RUNS_ROOT) -> Path:
    return _mkdir(run_dir(run_id, root) / "eval")


def scores_path(run_id: str, root: Path = RUNS_ROOT) -> Path:
    return eval_dir(run_id, root) / "scores.jsonl"


def blind_sheet_path(run_id: str, root: Path = RUNS_ROOT) -> Path:
    return eval_dir(run_id, root) / "blind_sheet.csv"


def blind_key_path(run_id: str, root: Path = RUNS_ROOT) -> Path:
    return eval_dir(run_id, root) / "blind_key.csv"


def report_path(run_id: str, root: Path = RUNS_ROOT) -> Path:
    return eval_dir(run_id, root) / "report.md"


def write_meta(directory: Path, data: dict[str, Any]) -> Path:
    """Write ``meta.json`` into ``directory`` (Paths are serialised as strings)."""
    path = _mkdir(Path(directory)) / META_FILENAME
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path


def read_meta(directory: Path) -> dict[str, Any]:
    """Read ``meta.json`` from ``directory``; returns ``{}`` if it does not exist."""
    path = Path(directory) / META_FILENAME
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
