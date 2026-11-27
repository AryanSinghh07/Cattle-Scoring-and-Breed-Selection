# Gopalan AI — ML

Python tools behind the analyzer: find the animal in a photo, outline it and
place the body points used for measurement and body condition scoring.

## What it does

1. **Find the animal**: torchvision **Mask R-CNN** pretrained on COCO
   (BSD licence). COCO already has a `cow` class, so no custom training is
   needed. Buffaloes are normally detected as `cow`; `horse`, `sheep`,
   `elephant` and `bear` are accepted as a fallback with a warning.
2. **Outline it**: the pixel mask of the animal, simplified to a polygon.
3. **Place the body points** from the outline (same points as the original
   analyzer, which made users click them by hand):

   | View | Points |
   |---|---|
   | Side | nose, tail, back, belly, knee, hoof, rib box (top-left, bottom-right) |
   | Top | rump left, rump right |
   | Back | hip left, hip right |

   Every point has a **confidence** (0–1). Low-confidence points are meant to
   be highlighted in the app so the user drags them into place. This is the
   semi-automatic step.

Photos are downscaled to 1024 px (longest side) for speed; all coordinates
are returned in the original photo's pixels. Phone EXIF rotation is applied.

## Setup

```bash
cd ml
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

The first run downloads the Mask R-CNN weights (~180 MB) into the PyTorch
cache (`~/.cache/torch`), not into the repo.

## Usage

```bash
python -m gopalan_ml.detect photo.jpg --view side --out preview.jpg
```

Prints JSON:

```json
{
  "view": "side",
  "image": {"width": 1600, "height": 1200},
  "animal": {"label": "cow", "score": 0.993, "box": [120.0, 210.5, 1480.2, 1100.0]},
  "outline": [[x, y], ...],
  "facing": "left",
  "points": {"back": {"x": 812.0, "y": 260.4, "confidence": 0.84}, ...},
  "warnings": []
}
```

The preview image shows the outline in green and points in red (orange when
the confidence is below 0.5).

## Breed classifier

Recognises the **16 website breeds** (8 cattle, 8 buffalo). Data sources,
cleaning and known issues are in [DATASETS.md](DATASETS.md).

**Train on Kaggle (free GPU):** open
[`notebooks/train_breed_classifier.ipynb`](notebooks/train_breed_classifier.ipynb)
on Kaggle, turn on GPU and Internet, add both datasets as inputs and
**Run all** (~20–30 min on a T4). The notebook calls
`gopalan_ml/breed_train.py`, which:

1. prepares the data (`breed_data.py`): breed-name mapping, file checks,
   duplicate removal across both datasets, 70/15/15 split per breed;
2. fine-tunes **ConvNeXt-Tiny** (`timm`, ImageNet-22k pretrained) with
   augmentation, label smoothing and class weights; keeps the epoch with
   the best validation macro-F1;
3. picks an **"unsure" threshold** on the validation set: the lowest
   confidence at which answered predictions are at least 80% correct;
4. reports test accuracy, top-3 accuracy, macro-F1, per-breed
   precision/recall and a confusion matrix;
5. exports **ONNX** (checked against PyTorch) plus `labels.json`.

Outputs: `breed_classifier.onnx`, `labels.json`, `metrics.json`,
`confusion_matrix.png`, `training_curves.png`, `manifest.csv`, `best.pt`.

**Predict** (needs only `onnxruntime`, not PyTorch):

```bash
python -m gopalan_ml.breed photo.jpg --model breed_classifier.onnx --labels labels.json
```

```json
{"breed": "gir", "name": "Gir", "type": "cow", "confidence": 0.93, "unsure": false,
 "top": [{"slug": "gir", "confidence": 0.93}, {"slug": "kankrej", "confidence": 0.04}, ...]}
```

Below the threshold, `breed` is `"unsure"` and `top` lists the best guesses
so the app can ask the user instead of showing a wrong breed. The
preprocessing matches timm's evaluation transform exactly (checked to 0
difference on 30 photos).

### Results: first model (2026-11-27)

Trained on Kaggle (Tesla T4, 15 epochs, ConvNeXt-Tiny, ~5 minutes) on the
3,383 cleaned images. Scored on **508 held-out test photos**. The same numbers
were reproduced locally with the exported ONNX model.

| | Result |
|---|---|
| Test accuracy (always answering) | **72.0%** |
| Top-3 accuracy (right breed among 3 guesses) | **90.4%** |
| Macro-F1 | 0.71 |
| Cattle breeds only | 82.9% (208/251) |
| Buffalo breeds only | 61.5% (158/257) |
| Cow vs buffalo (animal type) | 97.6% |
| ONNX vs PyTorch max difference | 0.000003 |

**"Unsure" threshold** (chosen on the validation set, reported on test):

| Target | Threshold | Answers | Correct when answering |
|---|---|---|---|
| 80% (default) | 0.45 | 79% of photos | 81.5% |
| 85% | 0.60 | 66% | 85.1% |
| 90% | 0.85 | 31% | 93.0% |

The first run used the 90% target and answered only 31% of photos, which is
too cautious for the app, so the default is now 80%.

Per breed (test F1): Ongole 0.91, Hallikar 0.91, Kankrej 0.90, Gir 0.85,
Toda 0.85, Malnad Gidda 0.85, Rathi 0.82, Sahiwal 0.80, Jafarabadi 0.73,
Mehsana 0.73, Nagpuri 0.63, Red Sindhi 0.57, Murrah 0.57, Nili-Ravi 0.55,
Bhadawari 0.35, Surti 0.35.

Most common mix-ups: Murrah → Surti, Jafarabadi → Murrah,
Sahiwal → Red Sindhi / Gir, Nili-Ravi → Surti / Murrah. The weak buffalo
breeds are the ones with the most label noise in the source data (see
[DATASETS.md](DATASETS.md)). Cleaner buffalo photos are the most effective
way to improve the model.

These are web photos. Accuracy on real farm photos taken with the app has
not been measured yet.

**Local smoke test** (CPU, a few minutes, checks the pipeline, not accuracy):

```bash
pip install -r requirements-train.txt
python -m gopalan_ml.breed_train --data-dir "<bovine>" --data-dir "<buffalo>" \
  --epochs 1 --limit-per-class 8 --workers 0 --out outputs/breed_smoke
```

## Tests

```bash
cd ml
python -m pytest
```

The tests use synthetic outlines and don't need the model weights.

## Checking on real photos

```bash
python scripts/eval_detection.py \
  --data-dir "<path>/Indian_bovine_breeds" \
  --data-dir "<path>/indian-buffalo-dataset" \
  --breeds Gir Sahiwal Murrah ... --per-class 3 --out outputs/eval
```

Writes annotated previews plus `summary.md` / `summary.json` to
`outputs/eval` (ignored by git).

## Detection check

Run on 2026-11-27 with 48 web photos: 3 per breed for the 16 breeds on the
website (8 cattle from `lukex9442/indian-bovine-breeds`, 8 buffalo from
`atharvadarpude/indian-buffalo-dataset`), CPU only.

| | Cattle | Buffalo | Total |
|---|---|---|---|
| Animal found | 24/24 | 24/24 | **48/48 (100%)** |
| Detected as `cow` | 24/24 | 24/24 | 48/48 |
| Photos that are a usable side view | 17 | 14 | 31 |
| Head/tail direction correct (usable side views) | 17/17 | 14/14 | **31/31** |
| Time per photo (CPU) | ~2.7 s | ~2.4 s | |

Findings:

- **Buffaloes are detected as `cow`** reliably, so no separate buffalo
  detector is needed.
- **Outlines are tight** on clear photos. With several animals in the frame,
  the largest one is chosen and a warning is returned.
- **Head/tail direction:** the first version compared the height of the two
  ends and got it wrong on many zebu cattle, because the hump and horns make
  the front end higher. It now compares how *tall* each end of the outline is
  (head and neck are thin, the rump is tall), which was correct on every
  usable side view.
- **Back, belly and hoof** land in sensible places on side views. **Knee and
  the rib box are rough estimates** (orange in previews) and are expected to
  be adjusted by the user.
- **About a third of the web photos are not side views** (front, rear,
  close-ups of the head, herds). Points on those are meaningless. The app must
  ask for a proper side view. Detecting the photo angle automatically is a
  possible follow-up.

These are web photos without an ArUco marker, so they test detection and
point placement only, not measurements in cm.

## Licences

| Component | Licence |
|---|---|
| This code | MIT |
| torchvision | BSD-3-Clause |
| Mask R-CNN pretrained weights | Trained by torchvision on COCO (annotations CC BY 4.0) |
| OpenCV | Apache-2.0 |

Datasets and model weights are never committed (see `.gitignore`).
