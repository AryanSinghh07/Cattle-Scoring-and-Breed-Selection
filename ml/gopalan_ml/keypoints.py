"""Place body points on a binary animal mask.

The points match the ones the original Gradio analyzer asked users to click:

* side view: nose, tail, back, belly, knee, hoof and a rib box (2 corners)
* top view:  rump left, rump right
* back view: hip left, hip right

Everything here is geometry on the mask, so it is fast, needs no training data
and no deep-learning libraries. The points are a starting guess: the user is
expected to drag any point that is off, which is why every point carries a
confidence value the UI can use to highlight the ones worth checking.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

SIDE_POINTS = ("nose", "tail", "back", "belly", "knee", "hoof", "rib_top_left", "rib_bottom_right")
TOP_POINTS = ("rump_left", "rump_right")
BACK_POINTS = ("hip_left", "hip_right")
VIEWS = ("side", "top", "back")

MIN_MASK_PIXELS = 500

# Positions along the body, measured from the head (0.0) to the tail (1.0).
_MID_TRUNK = 0.55
_BELLY_RANGE = (0.40, 0.70)
_FRONT_LEG_RANGE = (0.15, 0.50)
_RIB_RANGE = (0.35, 0.55)
_RUMP_POSITION = 0.80
_END_FRACTION = 0.15


@dataclass
class Point:
    x: float
    y: float
    confidence: float

    def to_dict(self) -> dict:
        return {"x": round(self.x, 1), "y": round(self.y, 1), "confidence": round(self.confidence, 2)}


@dataclass
class KeypointResult:
    view: str
    points: dict[str, Point]
    facing: str | None = None
    warnings: list[str] = field(default_factory=list)

    def scaled(self, factor: float) -> "KeypointResult":
        """Return a copy with coordinates multiplied by ``factor``."""
        points = {k: Point(p.x * factor, p.y * factor, p.confidence) for k, p in self.points.items()}
        return KeypointResult(self.view, points, self.facing, list(self.warnings))

    def to_dict(self) -> dict:
        return {
            "view": self.view,
            "facing": self.facing,
            "points": {k: p.to_dict() for k, p in self.points.items()},
            "warnings": self.warnings,
        }


def place_points(mask: np.ndarray, view: str, facing: str = "auto") -> KeypointResult:
    """Place the body points for ``view`` on ``mask`` (2-D, truthy = animal)."""
    mask = _validate_mask(mask)
    if view == "side":
        return side_points(mask, facing)
    if view == "top":
        return top_points(mask)
    if view == "back":
        return back_points(mask)
    raise ValueError(f"Unknown view {view!r}; expected one of {VIEWS}")


# --------------------------------------------------------------------------- side


def side_points(mask: np.ndarray, facing: str = "auto") -> KeypointResult:
    mask = _validate_mask(mask)
    warnings: list[str] = []
    ys, xs = np.nonzero(mask)
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    width, height = x1 - x0 + 1, y1 - y0 + 1

    tops, run_bottoms, bottoms = _column_profiles(mask, x0, x1)

    if facing == "auto":
        facing, facing_conf = _guess_facing(mask[:, x0 : x1 + 1].sum(axis=0))
        if facing_conf < 0.4:
            warnings.append("Could not tell which way the animal faces; check nose and tail.")
    elif facing in ("left", "right"):
        facing_conf = 1.0
    else:
        raise ValueError("facing must be 'auto', 'left' or 'right'")

    def col_at(u: float) -> int:
        """Column index (relative to x0) at fraction ``u`` from head to tail."""
        u = min(max(u, 0.0), 1.0)
        rel = u * (width - 1)
        return int(round(rel if facing == "left" else (width - 1) - rel))

    def cols_between(a: float, b: float) -> np.ndarray:
        c1, c2 = sorted((col_at(a), col_at(b)))
        return np.arange(c1, c2 + 1)

    # Nose and tail: the extreme columns on each end, at the middle of the mask there.
    end_band = max(1, int(round(width * 0.01)))
    head_cols = np.arange(0, end_band) if facing == "left" else np.arange(width - end_band, width)
    tail_cols = np.arange(width - end_band, width) if facing == "left" else np.arange(0, end_band)
    nose = _end_point(mask, x0, head_cols)
    tail = _end_point(mask, x0, tail_cols)
    end_conf = 0.4 + 0.5 * facing_conf

    # Back: top of the mask at mid trunk.
    mid = col_at(_MID_TRUNK)
    back_y = float(tops[mid]) if tops[mid] >= 0 else float(y0)

    # Belly: bottom of the first solid run from the top, ignoring columns that run
    # straight to the ground (those are legs).
    belly_cols = cols_between(*_BELLY_RANGE)
    ground_limit = y1 - 0.08 * height
    rb = run_bottoms[belly_cols]
    candidates = rb[(rb >= 0) & (rb < ground_limit)]
    if candidates.size >= max(3, belly_cols.size // 10):
        belly_y = float(np.median(candidates))
        belly_conf = 0.8
    else:
        belly_y = back_y + 0.6 * (y1 - back_y)
        belly_conf = 0.3
        warnings.append("Belly line not visible between the legs; belly point is an estimate.")
    if belly_y <= back_y:
        belly_y = back_y + 0.5 * (y1 - back_y)
        belly_conf = 0.2

    # Hoof: lowest point of the front legs (head half of the body).
    leg_cols = cols_between(*_FRONT_LEG_RANGE)
    leg_bottoms = bottoms[leg_cols]
    valid = leg_bottoms >= 0
    if valid.any():
        lowest = leg_bottoms[valid].max()
        near_ground = leg_cols[valid][leg_bottoms[valid] >= lowest - 0.03 * height]
        hoof_x = float(x0 + np.median(near_ground))
        hoof_y = float(lowest)
        hoof_conf = 0.7 if lowest >= y1 - 0.05 * height else 0.4
    else:
        hoof_x, hoof_y, hoof_conf = float(x0 + col_at(0.3)), float(y1), 0.2

    # Knee (carpus): roughly halfway between the belly line and the hoof.
    knee_y = belly_y + 0.5 * (hoof_y - belly_y)

    # Rib box: behind the shoulder, middle band of the barrel.
    rib_c1, rib_c2 = sorted((col_at(_RIB_RANGE[0]), col_at(_RIB_RANGE[1])))
    rib_mid = (rib_c1 + rib_c2) // 2
    rib_back = float(tops[rib_mid]) if tops[rib_mid] >= 0 else back_y
    depth = max(belly_y - rib_back, 1.0)

    points = {
        "nose": Point(nose[0], nose[1], end_conf),
        "tail": Point(tail[0], tail[1], end_conf),
        "back": Point(float(x0 + mid), back_y, 0.85),
        "belly": Point(float(x0 + mid), belly_y, belly_conf),
        "knee": Point(hoof_x, knee_y, min(hoof_conf, belly_conf) * 0.6),
        "hoof": Point(hoof_x, hoof_y, hoof_conf),
        "rib_top_left": Point(float(x0 + rib_c1), rib_back + 0.30 * depth, 0.5),
        "rib_bottom_right": Point(float(x0 + rib_c2), rib_back + 0.80 * depth, 0.5),
    }
    return KeypointResult("side", points, facing, warnings)


def _column_profiles(mask: np.ndarray, x0: int, x1: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per column: first mask row, end of the first solid run, last mask row (-1 if empty)."""
    n = x1 - x0 + 1
    tops = np.full(n, -1, dtype=np.int64)
    run_bottoms = np.full(n, -1, dtype=np.int64)
    bottoms = np.full(n, -1, dtype=np.int64)
    for i in range(n):
        rows = np.flatnonzero(mask[:, x0 + i])
        if rows.size == 0:
            continue
        tops[i] = rows[0]
        bottoms[i] = rows[-1]
        gaps = np.flatnonzero(np.diff(rows) > 1)
        run_bottoms[i] = rows[gaps[0]] if gaps.size else rows[-1]
    return tops, run_bottoms, bottoms


def _guess_facing(thickness: np.ndarray) -> tuple[str, float]:
    """Which end is the head?

    Seen from the side, the head end of the outline is thin (just head and
    neck), while the rear end is tall (rump down to the hocks). Comparing the
    top line instead does not work for zebu cattle, whose hump and horns make
    the front end higher.
    """
    n = max(1, int(round(thickness.size * _END_FRACTION)))
    left = float(thickness[:n].mean())
    right = float(thickness[-n:].mean())
    if max(left, right) == 0:
        return "left", 0.0
    ratio = min(left, right) / max(left, right)
    confidence = min(1.0, (1.0 - ratio) / 0.4)
    return ("left" if left < right else "right"), confidence


def _end_point(mask: np.ndarray, x0: int, cols: np.ndarray) -> tuple[float, float]:
    xs, ys = [], []
    for c in cols:
        rows = np.flatnonzero(mask[:, x0 + c])
        if rows.size:
            xs.append(x0 + c)
            ys.append(rows.mean())
    if not xs:
        return float(x0 + cols.mean()), float(mask.shape[0] / 2)
    return float(np.mean(xs)), float(np.mean(ys))


# ---------------------------------------------------------------------------- top


def top_points(mask: np.ndarray) -> KeypointResult:
    """Rump width across the body, about 80% of the way from head to tail."""
    mask = _validate_mask(mask)
    warnings: list[str] = []
    ys, xs = np.nonzero(mask)
    pts = np.column_stack([xs, ys]).astype(np.float64)
    center = pts.mean(axis=0)
    cov = np.cov((pts - center).T)
    eigvals, eigvecs = np.linalg.eigh(cov)
    major = eigvecs[:, np.argmax(eigvals)]
    minor = np.array([-major[1], major[0]])

    t = (pts - center) @ major
    s = (pts - center) @ minor
    bins = 50
    edges = np.linspace(t.min(), t.max(), bins + 1)
    idx = np.clip(np.digitize(t, edges) - 1, 0, bins - 1)
    s_min = np.full(bins, np.nan)
    s_max = np.full(bins, np.nan)
    for b in range(bins):
        sel = s[idx == b]
        if sel.size:
            s_min[b], s_max[b] = sel.min(), sel.max()
    widths = s_max - s_min

    n_end = max(1, int(bins * 0.15))
    start_w = np.nanmean(widths[:n_end])
    end_w = np.nanmean(widths[-n_end:])
    head_at_start = start_w < end_w  # the head and neck are narrower than the rump
    ratio = min(start_w, end_w) / max(start_w, end_w) if max(start_w, end_w) > 0 else 1.0
    confidence = float(np.clip(0.3 + (1.0 - ratio), 0.3, 0.8))
    if ratio > 0.85:
        warnings.append("Head and tail ends look alike from above; check the rump points.")

    rump_bin = int(round((_RUMP_POSITION if head_at_start else 1 - _RUMP_POSITION) * (bins - 1)))
    rump_bin = _nearest_filled(widths, rump_bin)
    t_mid = (edges[rump_bin] + edges[rump_bin + 1]) / 2
    a = center + t_mid * major + s_min[rump_bin] * minor
    b = center + t_mid * major + s_max[rump_bin] * minor
    left, right = sorted((a, b), key=lambda p: (p[0], p[1]))

    points = {
        "rump_left": Point(float(left[0]), float(left[1]), confidence),
        "rump_right": Point(float(right[0]), float(right[1]), confidence),
    }
    return KeypointResult("top", points, None, warnings)


def _nearest_filled(values: np.ndarray, i: int) -> int:
    filled = np.flatnonzero(~np.isnan(values))
    return int(filled[np.argmin(np.abs(filled - i))])


# --------------------------------------------------------------------------- back


def back_points(mask: np.ndarray) -> KeypointResult:
    """Hip width: the widest row in the upper part of the animal seen from behind."""
    mask = _validate_mask(mask)
    ys, _ = np.nonzero(mask)
    y0, y1 = int(ys.min()), int(ys.max())
    height = y1 - y0 + 1
    r1, r2 = y0 + int(0.10 * height), y0 + int(0.40 * height)

    best_row, best_w, best_lr = r1, -1, (0, 0)
    for r in range(r1, r2 + 1):
        cols = np.flatnonzero(mask[r])
        if cols.size and cols[-1] - cols[0] > best_w:
            best_row, best_w, best_lr = r, cols[-1] - cols[0], (cols[0], cols[-1])

    points = {
        "hip_left": Point(float(best_lr[0]), float(best_row), 0.6),
        "hip_right": Point(float(best_lr[1]), float(best_row), 0.6),
    }
    return KeypointResult("back", points, None, [])


# ------------------------------------------------------------------------- shared


def _validate_mask(mask: np.ndarray) -> np.ndarray:
    mask = np.asarray(mask)
    if mask.ndim != 2:
        raise ValueError("mask must be a 2-D array")
    mask = mask.astype(bool)
    if int(mask.sum()) < MIN_MASK_PIXELS:
        raise ValueError("Animal outline is too small to place points; move closer or use a larger photo.")
    return mask
