"""Find the cow or buffalo in a photo, outline it and place the body points.

Uses torchvision's Mask R-CNN pretrained on COCO (BSD licence). COCO has a
"cow" class, so no custom training is needed. Buffaloes are usually detected as
"cow"; a few similar classes are accepted as a fallback with a warning.

Command line::

    python -m gopalan_ml.detect photo.jpg --view side --out preview.jpg
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from .keypoints import VIEWS, KeypointResult, place_points

# Work on images no larger than this (longest side) for speed; results are
# scaled back to the original image size.
MAX_SIDE = 1024

PRIMARY_LABEL = "cow"
FALLBACK_LABELS = ("horse", "sheep", "elephant", "bear")

# Preview colours (BGR): nose blue, tail yellow.
END_COLOURS = {"nose": (255, 80, 0), "tail": (0, 220, 255)}


@dataclass
class Detection:
    label: str
    score: float
    box: tuple[float, float, float, float]  # x1, y1, x2, y2 in working-image pixels
    mask: np.ndarray  # bool, working-image size
    warnings: list[str] = field(default_factory=list)


def load_image(path: str | Path) -> np.ndarray:
    """Load any common image format as RGB, honouring phone EXIF rotation."""
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        if getattr(im, "is_animated", False):
            im.seek(0)
        return np.array(im.convert("RGB"))


def resize_for_work(image: np.ndarray, max_side: int = MAX_SIDE) -> tuple[np.ndarray, float]:
    """Downscale so the longest side is at most ``max_side``. Returns (image, scale)."""
    h, w = image.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    if scale < 1.0:
        image = cv2.resize(image, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
    return image, scale


def select_animal(
    labels: list[str],
    scores: np.ndarray,
    areas: np.ndarray,
    score_threshold: float = 0.5,
) -> tuple[int | None, list[str]]:
    """Choose which detection is "the animal".

    Prefers the largest confident "cow"; otherwise the largest confident
    fallback class (with a warning). Returns (index or None, warnings).
    """
    warnings: list[str] = []
    scores = np.asarray(scores, dtype=float)
    areas = np.asarray(areas, dtype=float)

    def best(allowed: tuple[str, ...]) -> int | None:
        idx = [i for i, l in enumerate(labels) if l in allowed and scores[i] >= score_threshold]
        return max(idx, key=lambda i: areas[i]) if idx else None

    i = best((PRIMARY_LABEL,))
    if i is None:
        i = best(FALLBACK_LABELS)
        if i is not None:
            warnings.append(f"Animal detected as '{labels[i]}', not 'cow'; check that the photo shows cattle or buffalo.")
    if i is not None:
        others = [j for j, l in enumerate(labels) if l == PRIMARY_LABEL and scores[j] >= score_threshold and j != i]
        if others:
            warnings.append("More than one animal in the photo; using the largest one.")
    return i, warnings


class AnimalDetector:
    """Lazy-loading wrapper around torchvision Mask R-CNN."""

    def __init__(self, device: str = "cpu", score_threshold: float = 0.5):
        import torch
        from torchvision.models.detection import (
            MaskRCNN_ResNet50_FPN_V2_Weights,
            maskrcnn_resnet50_fpn_v2,
        )

        self._torch = torch
        weights = MaskRCNN_ResNet50_FPN_V2_Weights.DEFAULT
        self.categories: list[str] = weights.meta["categories"]
        self.model = maskrcnn_resnet50_fpn_v2(weights=weights).eval().to(device)
        self.device = device
        self.score_threshold = score_threshold

    def detect(self, image_rgb: np.ndarray) -> Detection | None:
        torch = self._torch
        tensor = torch.from_numpy(image_rgb).permute(2, 0, 1).float().div(255.0).to(self.device)
        with torch.inference_mode():
            out = self.model([tensor])[0]
        labels = [self.categories[int(i)] for i in out["labels"].cpu()]
        scores = out["scores"].cpu().numpy()
        masks = (out["masks"].cpu().numpy()[:, 0] >= 0.5) if len(labels) else np.zeros((0,) + image_rgb.shape[:2], bool)
        areas = masks.reshape(len(labels), -1).sum(axis=1) if len(labels) else np.zeros(0)
        i, warnings = select_animal(labels, scores, areas, self.score_threshold)
        if i is None:
            return None
        box = tuple(float(v) for v in out["boxes"][i].cpu().numpy())
        return Detection(labels[i], float(scores[i]), box, masks[i], warnings)


def outline_from_mask(mask: np.ndarray, detail: float = 0.002) -> list[list[float]]:
    """Simplified outer contour of the mask as [[x, y], ...]."""
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return []
    c = max(contours, key=cv2.contourArea)
    c = cv2.approxPolyDP(c, detail * cv2.arcLength(c, True), True)
    return c.reshape(-1, 2).astype(float).tolist()


def analyze_image(
    image_rgb: np.ndarray,
    detector: AnimalDetector,
    view: str = "side",
    facing: str = "auto",
) -> dict:
    """Detect the animal and place the points. Coordinates are in original pixels."""
    if view not in VIEWS:
        raise ValueError(f"view must be one of {VIEWS}")
    h, w = image_rgb.shape[:2]
    work, scale = resize_for_work(image_rgb)
    result: dict = {"view": view, "image": {"width": w, "height": h}, "animal": None, "outline": [], "facing": None, "points": {}, "warnings": []}

    det = detector.detect(work)
    if det is None:
        result["warnings"].append("No cow or buffalo found in this photo.")
        return result

    back = 1.0 / scale
    result["animal"] = {"label": det.label, "score": round(det.score, 3), "box": [round(v * back, 1) for v in det.box]}
    result["outline"] = [[round(x * back, 1), round(y * back, 1)] for x, y in outline_from_mask(det.mask)]
    result["warnings"].extend(det.warnings)

    try:
        kp: KeypointResult = place_points(det.mask, view, facing).scaled(back)
    except ValueError as e:
        result["warnings"].append(str(e))
        return result
    # Point confidence also depends on how sure the detector was about the animal.
    for p in kp.points.values():
        p.confidence *= min(1.0, det.score + 0.1)
    result["facing"] = kp.facing
    result["points"] = {k: p.to_dict() for k, p in kp.points.items()}
    result["warnings"].extend(kp.warnings)
    return result


def draw_preview(image_rgb: np.ndarray, result: dict) -> np.ndarray:
    """Return a BGR image with the outline (green) and points (red) drawn on a copy."""
    img = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR).copy()
    size = max(img.shape[:2])
    thick = max(2, size // 400)
    if result["outline"]:
        cv2.polylines(img, [np.array(result["outline"], dtype=np.int32)], True, (0, 200, 0), thick)
    for name, p in result["points"].items():
        x, y = int(p["x"]), int(p["y"])
        colour = (0, 0, 255) if p["confidence"] >= 0.5 else (0, 165, 255)  # red, or orange if unsure
        radius = thick * 3
        if name in END_COLOURS:  # make head/tail direction obvious at a glance
            colour, radius = END_COLOURS[name], thick * 6
        cv2.circle(img, (x, y), radius, colour, -1)
        cv2.putText(img, name, (x + thick * 4, y - thick * 2), cv2.FONT_HERSHEY_SIMPLEX, size / 1600, (255, 255, 255), thick, cv2.LINE_AA)
    return img


def save_image(path: str | Path, bgr: np.ndarray) -> None:
    """Write an image; works with non-ASCII Windows paths."""
    ok, buf = cv2.imencode(Path(path).suffix or ".jpg", bgr)
    if not ok:
        raise ValueError(f"Could not encode image for {path}")
    buf.tofile(str(path))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Find the animal and place body points.")
    ap.add_argument("image", help="Path to a photo")
    ap.add_argument("--view", choices=VIEWS, default="side")
    ap.add_argument("--facing", choices=("auto", "left", "right"), default="auto", help="Side view only")
    ap.add_argument("--out", help="Save an annotated preview image here")
    ap.add_argument("--threshold", type=float, default=0.5, help="Minimum detection score")
    ap.add_argument("--no-outline", action="store_true", help="Leave the outline out of the JSON")
    args = ap.parse_args(argv)

    image = load_image(args.image)
    detector = AnimalDetector(score_threshold=args.threshold)
    result = analyze_image(image, detector, args.view, args.facing)
    if args.out:
        save_image(args.out, draw_preview(image, result))
    if args.no_outline:
        result.pop("outline")
    json.dump(result, sys.stdout, indent=2)
    print()
    return 0 if result["animal"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
