"""Compare breed-prediction options on the held-out test split.

For every test photo in the training manifest, finds the animal with the
detector, then scores four options:

* whole photo vs. cropped to the detected animal
* with or without the user's cow/buffalo choice (species filter)

    python scripts/eval_breed_options.py --model-dir outputs/kaggle_run1/breed_model \
        --data-dir <bovine> --data-dir <buffalo> --out outputs/breed_options.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gopalan_ml.breed import BreedClassifier  # noqa: E402
from gopalan_ml.breed_data import BREEDS  # noqa: E402
from gopalan_ml.detect import AnimalDetector, load_image, resize_for_work  # noqa: E402


def score(probs: np.ndarray, labels: np.ndarray, threshold: float) -> dict:
    pred = probs.argmax(1)
    conf = probs.max(1)
    top3 = np.argsort(-probs, axis=1)[:, :3]
    answered = conf >= threshold
    return {
        "accuracy": round(float((pred == labels).mean()), 4),
        "top3_accuracy": round(float((top3 == labels[:, None]).any(1).mean()), 4),
        "answered_share": round(float(answered.mean()), 4),
        "accuracy_when_answered": round(float((pred[answered] == labels[answered]).mean()), 4) if answered.any() else None,
        "wrong_species": round(float(np.mean([BREEDS[CLASSES[p]][1] != BREEDS[CLASSES[t]][1] for p, t in zip(pred, labels)])), 4),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", type=Path, required=True)
    ap.add_argument("--data-dir", type=Path, action="append", required=True)
    ap.add_argument("--split", default="test")
    ap.add_argument("--out", type=Path, default=Path("outputs/breed_options.json"))
    args = ap.parse_args()

    clf = BreedClassifier(args.model_dir / "breed_classifier.onnx", args.model_dir / "labels.json")
    global CLASSES
    CLASSES = clf.classes
    detector = AnimalDetector()

    local = {}
    for root in args.data_dir:
        for p in root.rglob("*"):
            if p.is_file():
                local[(p.parent.name.lower(), p.name)] = p

    rows = [r for r in csv.DictReader(open(args.model_dir / "manifest.csv", encoding="utf-8")) if r["split"] == args.split]
    whole, crop, labels, missing, no_animal = [], [], [], 0, 0
    t0 = time.time()
    for i, r in enumerate(rows, 1):
        parts = r["path"].replace("\\", "/").split("/")
        path = local.get((parts[-2].lower(), parts[-1]))
        if path is None:
            missing += 1
            continue
        image = load_image(path)
        p_whole = clf.probabilities(image)
        work, scale = resize_for_work(image)
        det = detector.detect(work)
        if det is None:
            no_animal += 1
            p_crop = p_whole  # what the API does when no animal is found: no crop
        else:
            box = tuple(v / scale for v in det.box)
            p_crop = clf.probabilities(image, box)
        whole.append(p_whole)
        crop.append(p_crop)
        labels.append(CLASSES.index(r["slug"]))
        if i % 50 == 0:
            print(f"{i}/{len(rows)}  {time.time() - t0:.0f}s", flush=True)

    labels_a = np.array(labels)
    species = [BREEDS[CLASSES[t]][1] for t in labels]
    results = {"images": len(labels), "missing_locally": missing, "no_animal_found": no_animal, "threshold": clf.threshold}
    for name, probs in (("whole", np.array(whole)), ("crop", np.array(crop))):
        results[name] = score(probs, labels_a, clf.threshold)
        restricted = np.array([clf.restrict(p, s) for p, s in zip(probs, species)])
        results[name + "+species"] = score(restricted, labels_a, clf.threshold)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
