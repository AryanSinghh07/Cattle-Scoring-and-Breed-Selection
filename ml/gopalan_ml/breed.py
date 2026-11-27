"""Predict the breed from a photo with the exported ONNX model.

The model and its ``labels.json`` come from the Kaggle training notebook
(``ml/notebooks/train_breed_classifier.ipynb``). Inference only needs
``onnxruntime``, ``numpy`` and ``Pillow``, not PyTorch.

When the model isn't sure (top probability below the threshold chosen on the
validation set), the result is ``"unsure"`` with the top guesses listed, so
the app can ask the user to pick or skip instead of showing a wrong breed.

Command line::

    python -m gopalan_ml.breed photo.jpg --model breed_classifier.onnx --labels labels.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from .breed_data import BREEDS

_RESAMPLE = {"bicubic": Image.BICUBIC, "bilinear": Image.BILINEAR, "nearest": Image.NEAREST}


def preprocess(image_rgb: np.ndarray, cfg: dict) -> np.ndarray:
    """Same as timm's eval transform: resize shorter side, centre crop, normalise."""
    size = int(cfg["input_size"][-1])
    crop_pct = float(cfg.get("crop_pct", 0.875))
    resample = _RESAMPLE.get(cfg.get("interpolation", "bicubic"), Image.BICUBIC)
    im = Image.fromarray(image_rgb)
    scale_size = math.floor(size / crop_pct)
    w, h = im.size
    # Match torchvision exactly: the long side is truncated, crop offsets are rounded.
    if w <= h:
        nw, nh = scale_size, int(scale_size * h / w)
    else:
        nw, nh = int(scale_size * w / h), scale_size
    im = im.resize((nw, nh), resample)
    left, top = int(round((nw - size) / 2.0)), int(round((nh - size) / 2.0))
    im = im.crop((left, top, left + size, top + size))
    x = np.asarray(im, dtype=np.float32) / 255.0
    x = (x - np.array(cfg["mean"], np.float32)) / np.array(cfg["std"], np.float32)
    return x.transpose(2, 0, 1)[None]


def softmax(logits: np.ndarray) -> np.ndarray:
    z = logits - logits.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


class BreedClassifier:
    def __init__(self, model_path: str | Path, labels_path: str | Path, session: Any = None):
        self.labels = json.loads(Path(labels_path).read_text(encoding="utf-8"))
        self.classes: list[str] = self.labels["classes"]
        self.threshold: float = float(self.labels.get("unsure_threshold", 0.5))
        if session is None:
            import onnxruntime as ort

            session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        self.session = session
        self.input_name = session.get_inputs()[0].name

    def predict(self, image_rgb: np.ndarray, box: tuple[float, float, float, float] | None = None, top_k: int = 3) -> dict:
        """Breed prediction for an RGB image. ``box`` (x1, y1, x2, y2) crops to the animal first."""
        if box is not None:
            x1, y1, x2, y2 = (int(round(v)) for v in box)
            h, w = image_rgb.shape[:2]
            mx, my = int(0.1 * (x2 - x1)), int(0.1 * (y2 - y1))
            image_rgb = image_rgb[max(0, y1 - my) : min(h, y2 + my), max(0, x1 - mx) : min(w, x2 + mx)]
        logits = self.session.run(None, {self.input_name: preprocess(image_rgb, self.labels)})[0]
        probs = softmax(np.asarray(logits, dtype=np.float64))[0]
        order = np.argsort(-probs)[:top_k]
        top = [self._entry(self.classes[i], float(probs[i])) for i in order]
        best = top[0]
        unsure = best["confidence"] < self.threshold
        return {
            "breed": "unsure" if unsure else best["slug"],
            "name": None if unsure else best["name"],
            "type": None if unsure else best["type"],
            "confidence": round(best["confidence"], 3),
            "unsure": unsure,
            "threshold": self.threshold,
            "top": top,
        }

    @staticmethod
    def _entry(slug: str, p: float) -> dict:
        name, kind = BREEDS.get(slug, (slug, None))
        return {"slug": slug, "name": name, "type": kind, "confidence": round(p, 3)}


def main(argv: list[str] | None = None) -> int:
    from .detect import load_image

    ap = argparse.ArgumentParser(description="Predict the breed of a cow or buffalo.")
    ap.add_argument("image")
    ap.add_argument("--model", required=True, help="breed_classifier.onnx")
    ap.add_argument("--labels", required=True, help="labels.json")
    args = ap.parse_args(argv)
    result = BreedClassifier(args.model, args.labels).predict(load_image(args.image))
    json.dump(result, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
