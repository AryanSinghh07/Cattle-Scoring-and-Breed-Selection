"""Body Condition Score (BCS) v2 from body measurements. BETA.

Scale: the dairy standard 1–5 in 0.25 steps (1 = very thin, 5 = obese).

How it works: each available signal is placed on a 0..1 position between a
"thin" anchor and a "fat" anchor, the positions are averaged with weights, and
the average is mapped onto 1–5 (0.5 -> BCS 3.0) and rounded to 0.25.

| Signal | Needs | Thin anchor | Fat anchor | Weight |
|---|---|---|---|---|
| depth ratio (body depth / body length) | side photo | 0.28 | 0.48 | 0.50 |
| rib visibility (edge density in rib box) | side photo | 0.12 | 0.02 | 0.25 |
| rump / hip width ratio | top + back photos | 0.85 | 1.05 | 0.25 |

The depth-ratio and rib anchors are the 10th/90th percentiles measured on 32
side-view photos of the 16 supported breeds (see ml/README.md). The old
analyzer's depth-ratio thresholds (0.22 / 0.30) rated nearly every Indian cow
and buffalo as fat. The rump/hip anchors are carried over from the old
analyzer. **None of this is calibrated against expert BCS scores yet**: the
result is an estimate and is always marked as beta. Reviewer-confirmed scores
collected by the app are meant to replace these anchors later.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field

from .measure import Measurements

MIN_SCORE, MAX_SCORE, STEP = 1.0, 5.0, 0.25
MAX_CONFIDENCE = 0.9  # never claim more without calibration data


@dataclass(frozen=True)
class Anchor:
    thin: float
    fat: float
    weight: float


DEFAULT_ANCHORS: dict[str, Anchor] = {
    "depth_ratio": Anchor(thin=0.28, fat=0.48, weight=0.50),
    "rib_visibility": Anchor(thin=0.12, fat=0.02, weight=0.25),
    "rump_hip_ratio": Anchor(thin=0.85, fat=1.05, weight=0.25),
}

SIGNAL_TEXT = {
    "depth_ratio": "Body depth compared with body length",
    "rib_visibility": "How visible the ribs are",
    "rump_hip_ratio": "Rump width compared with hip width",
}


@dataclass
class Signal:
    name: str
    value: float
    position: float  # 0 = thin anchor, 1 = fat anchor
    weight: float
    effect: str  # "thinner", "fatter" or "neutral"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": SIGNAL_TEXT.get(self.name, self.name),
            "value": round(self.value, 3),
            "position": round(self.position, 2),
            "weight": self.weight,
            "effect": self.effect,
        }


@dataclass
class BCSResult:
    score: float  # 1.0–5.0 in 0.25 steps
    farmer_score: float  # same, rounded to 0.5 for simple display
    label: str
    confidence: float  # 0..MAX_CONFIDENCE
    signals: list[Signal]
    warnings: list[str] = field(default_factory=list)
    beta: bool = True

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "farmer_score": self.farmer_score,
            "label": self.label,
            "confidence": round(self.confidence, 2),
            "scale": "1-5 (dairy standard, 0.25 steps)",
            "beta": self.beta,
            "note": "Estimated from body shape. Not yet calibrated against expert scores.",
            "signals": [s.to_dict() for s in self.signals],
            "warnings": self.warnings,
        }


def round_to_step(x: float, step: float = STEP) -> float:
    """Round half up to the nearest ``step`` (deterministic, unlike banker's rounding)."""
    return math.floor(x / step + 0.5) * step


def label_for(score: float) -> str:
    if score < 2.0:
        return "Very thin"
    if score < 3.0:
        return "Thin"
    if score < 4.0:
        return "Ideal"
    if score < 5.0:
        return "Fat"
    return "Obese"


def estimate_bcs(
    m: Measurements,
    anchors: dict[str, Anchor] | None = None,
    point_confidence: float | None = None,
) -> BCSResult:
    """Estimate BCS from ``m``. Raises ``ValueError`` if no signal is available."""
    anchors = anchors or DEFAULT_ANCHORS
    values = {
        "depth_ratio": m.depth_ratio,
        "rib_visibility": m.rib_visibility,
        "rump_hip_ratio": m.rump_hip_ratio,
    }

    signals: list[Signal] = []
    for name, value in values.items():
        if value is None or name not in anchors:
            continue
        a = anchors[name]
        pos = (value - a.thin) / (a.fat - a.thin)
        pos = min(1.0, max(0.0, pos))
        effect = "thinner" if pos < 0.4 else "fatter" if pos > 0.6 else "neutral"
        signals.append(Signal(name, float(value), pos, a.weight, effect))

    if not signals:
        raise ValueError("Not enough measurements to estimate BCS; a side-view photo is needed.")

    total_w = sum(s.weight for s in signals)
    avg = sum(s.position * s.weight for s in signals) / total_w
    raw = MIN_SCORE + (MAX_SCORE - MIN_SCORE) * avg
    score = min(MAX_SCORE, max(MIN_SCORE, round_to_step(raw)))
    farmer = min(MAX_SCORE, max(MIN_SCORE, round_to_step(score, 0.5)))

    # Confidence: how much of the evidence we have, and whether signals agree.
    coverage = total_w / sum(a.weight for a in anchors.values())
    spread = statistics.pstdev([s.position for s in signals]) if len(signals) > 1 else 0.25
    agreement = max(0.0, 1.0 - 1.5 * spread)
    confidence = 0.2 + 0.7 * coverage * agreement
    if point_confidence is not None:
        confidence *= 0.5 + 0.5 * max(0.0, min(1.0, point_confidence))
    confidence = min(MAX_CONFIDENCE, max(0.05, confidence))

    warnings = list(m.warnings)
    if len(signals) == 1:
        warnings.append("Score is based on a single measurement; add top and back photos for a better estimate.")
    if any(s.position in (0.0, 1.0) for s in signals):
        warnings.append("A measurement is outside the usual range; check the photo angle and the body points.")

    # The label follows the number farmers see, so "3.0" is never shown as "Thin".
    return BCSResult(score, farmer, label_for(farmer), confidence, signals, warnings)
