"""Find the printed ArUco marker and turn pixels into centimetres.

The farmer places a printed ArUco marker (dictionary ``DICT_4X4_50``, 20 cm
square by default) next to the animal, at about the same distance from the
camera. Its known size gives the scale for every measurement.

Fixes compared with the original analyzer:

* images are converted to grey as RGB (the old code treated RGB as BGR);
* every detected marker is checked, the largest one is used and a warning is
  given when there are several;
* markers that are too small or seen at a steep angle are rejected with a
  clear message, because they would give a wrong scale.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

DEFAULT_MARKER_CM = 20.0
DEFAULT_DICTIONARY = cv2.aruco.DICT_4X4_50

MIN_SIDE_PX = 20.0  # smaller markers can't be measured reliably
MAX_SIDE_RATIO = 1.25  # longest / shortest side; above this the marker is too tilted
WARN_SIDE_RATIO = 1.10


class MarkerError(ValueError):
    """The marker is missing or can't be used for measuring."""


@dataclass
class MarkerScale:
    cm_per_px: float
    side_px: float
    marker_id: int
    corners: np.ndarray  # 4 x 2, image pixels
    side_ratio: float
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "cm_per_px": round(self.cm_per_px, 5),
            "side_px": round(self.side_px, 1),
            "marker_id": self.marker_id,
            "side_ratio": round(self.side_ratio, 3),
            "corners": self.corners.round(1).tolist(),
            "warnings": self.warnings,
        }


def to_gray(image_rgb: np.ndarray) -> np.ndarray:
    """Grey image from an RGB (not BGR) array; grey images pass through."""
    if image_rgb.ndim == 2:
        return image_rgb
    return cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)


def find_marker_scale(
    image_rgb: np.ndarray,
    marker_size_cm: float = DEFAULT_MARKER_CM,
    dictionary: int = DEFAULT_DICTIONARY,
) -> MarkerScale:
    """Detect the marker and return the centimetres-per-pixel scale.

    Raises :class:`MarkerError` with a farmer-friendly message when no usable
    marker is found.
    """
    if marker_size_cm <= 0:
        raise ValueError("marker_size_cm must be positive")
    detector = cv2.aruco.ArucoDetector(
        cv2.aruco.getPredefinedDictionary(dictionary), cv2.aruco.DetectorParameters()
    )
    corners, ids, _ = detector.detectMarkers(to_gray(image_rgb))
    if ids is None or len(ids) == 0:
        raise MarkerError(
            "No ArUco marker found. Place the printed marker flat next to the animal, "
            "fully visible and in good light."
        )

    candidates = []
    for c, i in zip(corners, ids.flatten()):
        quad = c.reshape(4, 2).astype(np.float64)
        sides = np.linalg.norm(quad - np.roll(quad, -1, axis=0), axis=1)
        candidates.append((float(sides.mean()), float(sides.max() / sides.min()), int(i), quad))

    warnings: list[str] = []
    if len(candidates) > 1:
        warnings.append(f"{len(candidates)} markers found; using the largest one.")
    side_px, ratio, marker_id, quad = max(candidates, key=lambda t: t[0])

    if side_px < MIN_SIDE_PX:
        raise MarkerError("The marker is too small in the photo. Move closer or use a bigger print.")
    if ratio > MAX_SIDE_RATIO:
        raise MarkerError(
            "The marker is seen at too steep an angle. Hold the camera straight at the "
            "animal's side with the marker facing the camera."
        )
    if ratio > WARN_SIDE_RATIO:
        warnings.append("The marker is slightly tilted; measurements may be a little off.")

    return MarkerScale(marker_size_cm / side_px, side_px, marker_id, quad, ratio, warnings)
