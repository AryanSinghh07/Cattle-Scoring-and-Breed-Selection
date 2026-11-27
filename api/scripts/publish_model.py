"""Publish the trained breed model to a Hugging Face model repo.

Uploads breed_classifier.onnx, labels.json, metrics.json, the charts and a
model card (README.md) generated from metrics.json.

Needs a Hugging Face login with write access (`hf auth login`).

    python scripts/publish_model.py <model folder> --repo <owner/name> [--private]
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

FILES = ("breed_classifier.onnx", "labels.json", "metrics.json", "confusion_matrix.png", "training_curves.png")


def model_card(metrics: dict, labels: dict, repo: str) -> str:
    per = metrics["per_breed"]
    names = labels.get("names", {})
    types = labels.get("types", {})
    rows = "\n".join(
        f"| {names.get(s, s)} | {types.get(s, '')} | {v['precision']:.2f} | {v['recall']:.2f} | {v['f1-score']:.2f} | {v['images']} |"
        for s, v in sorted(per.items(), key=lambda kv: -kv[1]["f1-score"])
    )
    d = metrics.get("data", {})
    answered = metrics.get("answered_share")
    return f"""---
license: mit
library_name: onnx
pipeline_tag: image-classification
tags:
- image-classification
- onnx
- cattle
- buffalo
- livestock
- agriculture
---

# Cattle & buffalo breed classifier (16 Indian breeds)

Recognises **8 Indian cattle and 8 buffalo breeds** from a photo, and says
**"unsure"** with its top guesses when its confidence is low.

- Architecture: `{labels.get('model_name')}` (ConvNeXt-Tiny, ImageNet-22k pretrained, fine-tuned)
- Format: ONNX (runs with `onnxruntime`, no PyTorch needed)
- Input: RGB, {labels['input_size'][1]}×{labels['input_size'][2]}, resize shorter side to {int(labels['input_size'][1] / labels.get('crop_pct', 0.875))} (bicubic), centre crop, ImageNet mean/std (see `labels.json`)
- Output: logits for 16 classes, in the order of `labels.json` → `classes`
- "Unsure" threshold: {labels.get('unsure_threshold')} (top probability below this → unsure)

## Results (held-out test set, {metrics['images']} photos)

| Metric | Value |
|---|---|
| Accuracy | {metrics['accuracy']:.1%} |
| Top-3 accuracy | {metrics['top3_accuracy']:.1%} |
| Macro-F1 | {metrics['macro_f1']:.2f} |
| Answered at the "unsure" threshold | {answered:.0%} of photos (threshold chosen on the validation set) |
| Correct when it answers | {metrics.get('accuracy_when_answered', 0):.1%} |

| Breed | Type | Precision | Recall | F1 | Test photos |
|---|---|---|---|---|---|
{rows}

![Confusion matrix](confusion_matrix.png)

## Training data

{d.get('kept', 'about 3,400')} images after cleaning, from two **CC0 (public domain)** Kaggle datasets:
`lukex9442/indian-bovine-breeds` and `atharvadarpude/indian-buffalo-dataset`.
Cleaning: files checked by content, tiny files and GIFs removed, near-duplicates
removed across both datasets with a difference hash, and photos filed under
different breeds dropped as label noise ({d.get('conflicting_labels_removed', '?')} images). Split 70/15/15 per
breed after de-duplication.

## Limitations

- Trained on **web photos**; accuracy on real farm photos has not been measured yet.
- **Buffalo breeds are weaker** than cattle breeds (the source folders contain
  heavy label noise). Common mix-ups: Murrah ↔ Surti, Jafarabadi → Murrah,
  Sahiwal ↔ Red Sindhi / Gir.
- Only the 16 listed breeds; crossbreeds and other breeds will be forced into one
  of them or reported as "unsure".
- Not a substitute for expert breed certification.

## Usage

```python
from gopalan_ml.breed import BreedClassifier  # from the project repository
from huggingface_hub import hf_hub_download

clf = BreedClassifier(hf_hub_download("{repo}", "breed_classifier.onnx"),
                      hf_hub_download("{repo}", "labels.json"))
print(clf.predict(rgb_image_array))
```
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Publish the breed model to Hugging Face.")
    ap.add_argument("folder", type=Path, help="Folder with breed_classifier.onnx, labels.json, metrics.json, charts")
    ap.add_argument("--repo", required=True, help="owner/name of the model repo")
    ap.add_argument("--private", action="store_true")
    args = ap.parse_args()

    from huggingface_hub import HfApi

    missing = [f for f in FILES[:3] if not (args.folder / f).is_file()]
    if missing:
        sys.exit(f"Missing in {args.folder}: {', '.join(missing)}")
    metrics = json.loads((args.folder / "metrics.json").read_text(encoding="utf-8"))
    labels = json.loads((args.folder / "labels.json").read_text(encoding="utf-8"))

    api = HfApi()
    url = api.create_repo(args.repo, repo_type="model", private=args.private, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for f in FILES:
            if (args.folder / f).is_file():
                (tmp / f).write_bytes((args.folder / f).read_bytes())
        (tmp / "README.md").write_text(model_card(metrics, labels, args.repo), encoding="utf-8", newline="\n")
        commit = api.upload_folder(folder_path=str(tmp), repo_id=args.repo, repo_type="model",
                                   commit_message="Upload breed classifier")
    print(f"Published: {url}")
    print(f"Commit: {commit.oid if hasattr(commit, 'oid') else commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
