from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("sklearn")
pytest.importorskip("timm")

from gopalan_ml.breed_data import Item  # noqa: E402
from gopalan_ml.breed_train import CLASSES, choose_threshold, class_weights, evaluate, limit_items  # noqa: E402


def probs_for(labels, correct_conf, wrong_conf, wrong_every=0):
    n = len(labels)
    p = np.full((n, 16), 0.0)
    for i, y in enumerate(labels):
        if wrong_every and i % wrong_every == 0:
            p[i, (y + 1) % 16] = wrong_conf
        else:
            p[i, y] = correct_conf
    rest = (1 - p.sum(axis=1, keepdims=True)) / 15
    return np.where(p == 0, rest, p)


def test_choose_threshold_filters_low_confidence_mistakes():
    labels = np.arange(100) % 16
    probs = probs_for(labels, correct_conf=0.9, wrong_conf=0.4, wrong_every=4)  # 25% wrong, all low-confidence
    t = choose_threshold(probs, labels, 0.9)
    assert 0.4 < t <= 0.9
    conf = probs.max(1)
    assert (probs.argmax(1)[conf >= t] == labels[conf >= t]).mean() >= 0.9


def test_evaluate_reports_everything():
    labels = np.arange(64) % 16
    m = evaluate(probs_for(labels, 0.8, 0.0), labels, 0.5)
    assert m["accuracy"] == 1.0 and m["top3_accuracy"] == 1.0 and m["macro_f1"] == 1.0
    assert m["answered_share"] == 1.0
    assert set(m["per_breed"]) == set(CLASSES)
    assert len(m["confusion_matrix"]) == 16


def test_limit_items_per_class_and_split():
    items = [Item(Path(f"{s}{k}.jpg"), s, "x", split=sp) for s in ("gir", "toda") for sp in ("train", "val") for k in range(10)]
    out = limit_items(items, 4, seed=0)
    assert sum(1 for i in out if i.slug == "gir" and i.split == "train") == 4
    assert sum(1 for i in out if i.slug == "gir" and i.split == "val") == 2
    assert limit_items(items, None, 0) is items


def test_class_weights_favour_rare_breeds():
    items = [Item(Path("a"), "gir", "x")] * 100 + [Item(Path("b"), "toda", "x")] * 4
    w = class_weights(items)
    assert w[CLASSES.index("toda")] > w[CLASSES.index("gir")]
    assert float(w.mean()) == pytest.approx(1.0)
