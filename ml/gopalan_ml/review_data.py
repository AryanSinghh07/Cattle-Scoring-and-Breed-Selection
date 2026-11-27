"""Read reviewer labels exported by the API (``GET /review/export/labels``).

Each record pairs what the model said with what a human reviewer decided,
plus the body points, measurements and photo storage paths. This is the
training data for the real (learned) BCS model planned for v3.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

from .breed_data import BREEDS

JSON_COLUMNS = ("photos", "points", "marker", "measurements", "model_versions")


@dataclass
class ReviewLabel:
    analysis_id: str
    decision: str  # "confirmed" or "corrected"
    label_bcs: float | None
    label_breed: str | None
    model_bcs: float | None
    model_breed: str | None
    photos: dict[str, str] = field(default_factory=dict)  # view -> storage path
    points: dict | None = None
    marker: dict | None = None
    measurements: dict | None = None
    model_versions: dict | None = None

    @property
    def bcs_error(self) -> float | None:
        """Model minus human BCS (positive = model scored too high)."""
        if self.label_bcs is None or self.model_bcs is None:
            return None
        return self.model_bcs - self.label_bcs


def _num(v) -> float | None:
    return None if v in (None, "") else float(v)


def read_review_export(path: str | Path) -> list[ReviewLabel]:
    """Load a ``.jsonl`` or ``.csv`` export. Invalid labels raise ``ValueError``."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8", newline="") as f:
            raw = [{k: (json.loads(v) if k in JSON_COLUMNS and v else v) for k, v in row.items()} for row in csv.DictReader(f)]
    else:
        raw = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    labels = []
    for i, r in enumerate(raw, 1):
        bcs = _num(r.get("label_bcs"))
        if bcs is not None and not (1 <= bcs <= 5 and (bcs * 4) == int(bcs * 4)):
            raise ValueError(f"record {i}: label_bcs {bcs} is not 1–5 in 0.25 steps")
        breed = r.get("label_breed") or None
        if breed is not None and breed not in BREEDS:
            raise ValueError(f"record {i}: unknown breed '{breed}'")
        if r.get("decision") not in ("confirmed", "corrected"):
            raise ValueError(f"record {i}: unknown decision '{r.get('decision')}'")
        labels.append(ReviewLabel(
            analysis_id=r["analysis_id"], decision=r["decision"], label_bcs=bcs, label_breed=breed,
            model_bcs=_num(r.get("model_bcs")), model_breed=r.get("model_breed") or None,
            photos=r.get("photos") or {}, points=r.get("points"), marker=r.get("marker"),
            measurements=r.get("measurements"), model_versions=r.get("model_versions"),
        ))
    return labels
