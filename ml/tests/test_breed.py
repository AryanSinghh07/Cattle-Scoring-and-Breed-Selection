import json

import numpy as np

from gopalan_ml.breed import BreedClassifier, preprocess, softmax
from gopalan_ml.breed_data import BREEDS

CLASSES = sorted(BREEDS)
CFG = {
    "classes": CLASSES,
    "input_size": [3, 224, 224],
    "mean": [0.485, 0.456, 0.406],
    "std": [0.229, 0.224, 0.225],
    "crop_pct": 0.875,
    "interpolation": "bicubic",
    "unsure_threshold": 0.6,
}


class FakeSession:
    """Stands in for onnxruntime: returns fixed logits and records the input."""

    def __init__(self, logits):
        self.logits = np.array([logits], dtype=np.float32)
        self.last = None

    def get_inputs(self):
        return [type("I", (), {"name": "image"})()]

    def run(self, _, feeds):
        self.last = feeds["image"]
        return [self.logits]


def classifier(tmp_path, logits):
    p = tmp_path / "labels.json"
    p.write_text(json.dumps(CFG))
    return BreedClassifier("unused.onnx", p, session=FakeSession(logits))


def test_preprocess_shape_and_normalisation():
    x = preprocess(np.full((300, 500, 3), 255, np.uint8), CFG)
    assert x.shape == (1, 3, 224, 224) and x.dtype == np.float32
    assert np.allclose(x[0, 0], (1 - 0.485) / 0.229, atol=1e-5)


def test_confident_prediction(tmp_path):
    logits = [0.0] * 16
    logits[CLASSES.index("gir")] = 8.0
    r = classifier(tmp_path, logits).predict(np.zeros((100, 120, 3), np.uint8))
    assert r["breed"] == "gir" and r["name"] == "Gir" and r["type"] == "cow"
    assert r["unsure"] is False and r["confidence"] > 0.9
    assert len(r["top"]) == 3 and r["top"][0]["slug"] == "gir"


def test_low_confidence_is_unsure_with_suggestions(tmp_path):
    logits = [0.0] * 16
    logits[CLASSES.index("murrah")] = 1.0
    logits[CLASSES.index("surti")] = 0.9
    r = classifier(tmp_path, logits).predict(np.zeros((100, 120, 3), np.uint8))
    assert r["breed"] == "unsure" and r["unsure"] is True and r["name"] is None
    assert [t["slug"] for t in r["top"][:2]] == ["murrah", "surti"]


def test_box_crops_before_classifying(tmp_path):
    clf = classifier(tmp_path, [0.0] * 16)
    img = np.zeros((400, 400, 3), np.uint8)
    img[100:300, 100:300] = 255  # white animal box on black
    clf.predict(img, box=(100, 100, 300, 300))
    centre = clf.session.last[0, :, 112, 112]
    assert centre[0] > 2.0  # white after normalisation


def test_softmax_rows_sum_to_one():
    p = softmax(np.array([[1.0, 2.0, 3.0], [1000.0, 0.0, -1000.0]]))
    assert np.allclose(p.sum(axis=1), 1.0)
