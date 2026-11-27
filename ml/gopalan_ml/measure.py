"""Body measurements in centimetres and the rib-visibility signal.

Points use the names from :mod:`gopalan_ml.keypoints` and may be given as
``{"x": .., "y": ..}`` dicts or objects with ``x`` / ``y`` attributes.

Fixes compared with the original analyzer:

* rib visibility is computed on the clean photo passed in, never on an image
  with dots or labels drawn on it (those were counted as "rib edges");
* the rib patch is resized to a fixed size and its contrast normalised, and
  the edge thresholds adapt to the patch, so lighting, coat colour and photo
  resolution matter much less;
* an empty or tiny rib box returns ``None`` with a warning instead of
  dividing by zero.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

import cv2
import numpy as np

from .marker import to_gray

RIB_PATCH_SIZE = 128
MIN_RIB_BOX_PX = 16
LOW_DETAIL_PX = 64  # rib boxes smaller than this are upscaled and look blurry


@dataclass
class Measurements:
    body_length_cm: float | None = None  # nose -> tail (side)
    body_depth_cm: float | None = None  # back -> belly (side)
    leg_length_cm: float | None = None  # knee -> hoof (side)
    rump_width_cm: float | None = None  # top view
    hip_width_cm: float | None = None  # back view
    rib_visibility: float | None = None  # 0..1, higher = ribs more visible
    warnings: list[str] = field(default_factory=list)

    @property
    def depth_ratio(self) -> float | None:
        if self.body_depth_cm and self.body_length_cm:
            return self.body_depth_cm / self.body_length_cm
        return None

    @property
    def rump_hip_ratio(self) -> float | None:
        if self.rump_width_cm and self.hip_width_cm:
            return self.rump_width_cm / self.hip_width_cm
        return None

    def to_dict(self) -> dict:
        d = asdict(self)
        for k, v in d.items():
            if isinstance(v, float):
                d[k] = round(v, 3 if k == "rib_visibility" else 1)
        d["depth_ratio"] = None if self.depth_ratio is None else round(self.depth_ratio, 3)
        d["rump_hip_ratio"] = None if self.rump_hip_ratio is None else round(self.rump_hip_ratio, 3)
        return d


def _xy(p: Any) -> np.ndarray:
    if isinstance(p, Mapping):
        return np.array([float(p["x"]), float(p["y"])])
    return np.array([float(p.x), float(p.y)])


def _box_min_side(p1: Any, p2: Any) -> float:
    d = np.abs(_xy(p1) - _xy(p2))
    return float(d.min())


def distance_cm(p1: Any, p2: Any, cm_per_px: float) -> float:
    return float(np.linalg.norm(_xy(p1) - _xy(p2)) * cm_per_px)


def rib_visibility(image_rgb: np.ndarray, top_left: Any, bottom_right: Any) -> float | None:
    """Edge density (0..1) inside the rib box, or ``None`` if the box is too small.

    The input image is never modified.
    """
    (x1, y1), (x2, y2) = _xy(top_left), _xy(bottom_right)
    h, w = image_rgb.shape[:2]
    xa, xb = sorted((int(round(x1)), int(round(x2))))
    ya, yb = sorted((int(round(y1)), int(round(y2))))
    xa, xb = max(0, xa), min(w, xb)
    ya, yb = max(0, ya), min(h, yb)
    if xb - xa < MIN_RIB_BOX_PX or yb - ya < MIN_RIB_BOX_PX:
        return None

    patch = to_gray(image_rgb[ya:yb, xa:xb])
    patch = cv2.resize(patch, (RIB_PATCH_SIZE, RIB_PATCH_SIZE), interpolation=cv2.INTER_AREA)
    patch = cv2.GaussianBlur(patch, (3, 3), 0)
    # Stretch contrast so dark and light coats look alike.
    patch = cv2.normalize(patch, None, 0, 255, cv2.NORM_MINMAX)
    patch = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4)).apply(patch)
    # Thresholds follow the patch's own intensity instead of fixed numbers.
    med = float(np.median(patch))
    lower, upper = int(max(0, 0.66 * med)), int(min(255, 1.33 * med))
    edges = cv2.Canny(patch, lower, max(upper, lower + 1))
    return float((edges > 0).mean())


def measure(
    cm_per_px: dict[str, float],
    side_points: Mapping[str, Any] | None = None,
    side_image: np.ndarray | None = None,
    top_points: Mapping[str, Any] | None = None,
    back_points: Mapping[str, Any] | None = None,
) -> Measurements:
    """Compute every measurement available from the views given.

    ``cm_per_px`` maps a view name (``side``/``top``/``back``) to that photo's
    scale. ``side_image`` must be the original photo (nothing drawn on it).
    """
    m = Measurements()

    if side_points is not None:
        s = cm_per_px["side"]
        m.body_length_cm = distance_cm(side_points["nose"], side_points["tail"], s)
        m.body_depth_cm = distance_cm(side_points["back"], side_points["belly"], s)
        m.leg_length_cm = distance_cm(side_points["knee"], side_points["hoof"], s)
        if side_image is not None:
            m.rib_visibility = rib_visibility(side_image, side_points["rib_top_left"], side_points["rib_bottom_right"])
            if m.rib_visibility is None:
                m.warnings.append("Rib box is too small to judge rib visibility; drag the rib box corners apart.")
            elif _box_min_side(side_points["rib_top_left"], side_points["rib_bottom_right"]) < LOW_DETAIL_PX:
                m.warnings.append("The rib area is small in the photo; move closer for a more reliable rib check.")

    if top_points is not None:
        m.rump_width_cm = distance_cm(top_points["rump_left"], top_points["rump_right"], cm_per_px["top"])
    if back_points is not None:
        m.hip_width_cm = distance_cm(back_points["hip_left"], back_points["hip_right"], cm_per_px["back"])

    return m
