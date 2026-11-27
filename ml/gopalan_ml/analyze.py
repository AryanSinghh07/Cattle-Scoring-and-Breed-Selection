"""Full analysis from photos: animal -> points -> marker scale -> measurements -> BCS.

Command line::

    python -m gopalan_ml.analyze --side side.jpg [--top top.jpg] [--back back.jpg]

Only the side photo is required. Without a readable marker the BCS is still
estimated (its signals are ratios, so the scale cancels out) but no
centimetre measurements are reported.
"""

from __future__ import annotations

import argparse
import json
import sys

import numpy as np

from .bcs import estimate_bcs
from .detect import AnimalDetector, analyze_image, load_image
from .marker import DEFAULT_MARKER_CM, MarkerError, find_marker_scale
from .measure import measure

CM_FIELDS = ("body_length_cm", "body_depth_cm", "leg_length_cm", "rump_width_cm", "hip_width_cm")


def analyze_photos(
    detector: AnimalDetector,
    side: np.ndarray,
    top: np.ndarray | None = None,
    back: np.ndarray | None = None,
    marker_size_cm: float = DEFAULT_MARKER_CM,
    facing: str = "auto",
) -> dict:
    views = {"side": side, "top": top, "back": back}
    out: dict = {"views": {}, "measurements": None, "bcs": None, "warnings": []}
    points: dict[str, dict] = {}
    scales: dict[str, float] = {}

    for view, image in views.items():
        if image is None:
            continue
        r = analyze_image(image, detector, view, facing if view == "side" else "auto")
        try:
            ms = find_marker_scale(image, marker_size_cm)
            r["marker"] = ms.to_dict()
            scales[view] = ms.cm_per_px
            r["warnings"].extend(ms.warnings)
        except MarkerError as e:
            r["marker"] = None
            r["warnings"].append(str(e))
        out["views"][view] = r
        if r["points"]:
            points[view] = r["points"]

    if "side" not in points:
        out["warnings"].append("No body points on the side photo, so nothing can be measured.")
        return out

    # Ratios don't depend on the scale, so use 1.0 where the marker is missing.
    m = measure(
        {v: scales.get(v, 1.0) for v in points},
        side_points=points["side"],
        side_image=side,
        top_points=points.get("top"),
        back_points=points.get("back"),
    )
    # The rump/hip ratio mixes two photos, so it needs a real scale on both.
    if ("top" in points and "back" in points) and not ("top" in scales and "back" in scales):
        m.rump_width_cm = m.hip_width_cm = None
        out["warnings"].append("Rump/hip comparison skipped: the marker must be visible in both top and back photos.")

    measurements = m.to_dict()
    for f in CM_FIELDS:
        view = "side" if f in CM_FIELDS[:3] else ("top" if f == "rump_width_cm" else "back")
        if view not in scales:
            measurements[f] = None
    out["measurements"] = measurements

    side_conf = [p["confidence"] for p in points["side"].values()]
    try:
        out["bcs"] = estimate_bcs(m, point_confidence=float(np.mean(side_conf))).to_dict()
    except ValueError as e:
        out["warnings"].append(str(e))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Measure the animal and estimate its body condition score (beta).")
    ap.add_argument("--side", required=True, help="Side-view photo (required)")
    ap.add_argument("--top", help="Top-view photo")
    ap.add_argument("--back", help="Back-view photo")
    ap.add_argument("--marker-cm", type=float, default=DEFAULT_MARKER_CM, help="Printed marker side length in cm")
    ap.add_argument("--facing", choices=("auto", "left", "right"), default="auto")
    ap.add_argument("--full", action="store_true", help="Include outlines and all point data")
    args = ap.parse_args(argv)

    images = {k: load_image(v) if v else None for k, v in (("side", args.side), ("top", args.top), ("back", args.back))}
    result = analyze_photos(AnimalDetector(), images["side"], images["top"], images["back"], args.marker_cm, args.facing)
    if not args.full:
        for r in result["views"].values():
            r.pop("outline", None)
    json.dump(result, sys.stdout, indent=2)
    print()
    return 0 if result["bcs"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
