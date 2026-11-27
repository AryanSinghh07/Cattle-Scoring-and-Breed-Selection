"""Load the ML models once and share them between requests."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("gopalan.models")


def _short_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


@dataclass
class ModelRegistry:
    """Holds the detector and the breed classifier.

    ``detector`` must have ``detect(image_rgb)`` (see ``gopalan_ml.detect``);
    ``breed`` must have ``predict(image_rgb, box=None)`` (see ``gopalan_ml.breed``).
    Either can be ``None`` when it couldn't be loaded; ``errors`` says why.
    """

    detector: Any = None
    breed: Any = None
    info: dict[str, dict] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def ready(self) -> bool:
        return self.detector is not None

    def health(self) -> dict:
        return {
            name: {"loaded": getattr(self, name) is not None, **self.info.get(name, {}),
                   **({"error": self.errors[name]} if name in self.errors else {})}
            for name in ("detector", "breed")
        }


def load_registry(detection_threshold: float, breed_model_path: str, breed_labels_path: str) -> ModelRegistry:
    """Load both models. Failures are recorded instead of crashing the API."""
    reg = ModelRegistry()

    try:
        from gopalan_ml.detect import AnimalDetector

        reg.detector = AnimalDetector(score_threshold=detection_threshold)
        reg.info["detector"] = {"name": "maskrcnn_resnet50_fpn_v2 (COCO)", "threshold": detection_threshold}
    except Exception as e:  # keep the API up so /health can report the problem
        log.exception("Detector failed to load")
        reg.errors["detector"] = f"{type(e).__name__}: {e}"

    model, labels = Path(breed_model_path), Path(breed_labels_path)
    if model.is_file() and labels.is_file():
        try:
            from gopalan_ml.breed import BreedClassifier

            reg.breed = BreedClassifier(model, labels)
            reg.info["breed"] = {
                "name": reg.breed.labels.get("model_name", "unknown"),
                "classes": len(reg.breed.classes),
                "unsure_threshold": reg.breed.threshold,
                "version": _short_hash(model),
            }
        except Exception as e:
            log.exception("Breed model failed to load")
            reg.errors["breed"] = f"{type(e).__name__}: {e}"
    else:
        reg.errors["breed"] = f"Model files not found ({model}, {labels}); breed prediction is off."
        log.warning(reg.errors["breed"])

    return reg
