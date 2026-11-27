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


BREED_FILES = ("breed_classifier.onnx", "labels.json")


def fetch_breed_model(repo_id: str, revision: str | None = None) -> tuple[Path, Path]:
    """Download (or reuse from the local cache) the breed model files from Hugging Face."""
    from huggingface_hub import hf_hub_download

    model, labels = (Path(hf_hub_download(repo_id, name, revision=revision)) for name in BREED_FILES)
    return model, labels


def load_registry(detection_threshold: float, breed_model_path: str, breed_labels_path: str,
                  breed_model_repo: str | None = None, breed_model_revision: str | None = None) -> ModelRegistry:
    """Load both models. Failures are recorded instead of crashing the API.

    The breed model is read from ``breed_model_path``/``breed_labels_path``; if
    those files don't exist and ``breed_model_repo`` is set, it is downloaded
    from that Hugging Face model repo instead.
    """
    reg = ModelRegistry()
    source = "local files"
    if breed_model_repo and not (Path(breed_model_path).is_file() and Path(breed_labels_path).is_file()):
        try:
            m, lab = fetch_breed_model(breed_model_repo, breed_model_revision)
            breed_model_path, breed_labels_path = str(m), str(lab)
            source = f"huggingface.co/{breed_model_repo}" + (f"@{breed_model_revision}" if breed_model_revision else "")
        except Exception as e:
            log.exception("Breed model download failed")
            reg.errors["breed"] = f"Download from {breed_model_repo} failed: {type(e).__name__}: {e}"

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
                "source": source,
            }
        except Exception as e:
            log.exception("Breed model failed to load")
            reg.errors["breed"] = f"{type(e).__name__}: {e}"
    elif "breed" in reg.errors:
        pass  # download error already recorded
    else:
        reg.errors["breed"] = f"Model files not found ({model}, {labels}); breed prediction is off."
        log.warning(reg.errors["breed"])

    return reg
