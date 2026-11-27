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
| Photos that are a usable side view | 17 | 15 | 32 |
| Head/tail direction correct (usable side views) | 17/17 | 15/15 | **32/32** |
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

## Measurements and BCS v2 (beta)

```bash
python -m gopalan_ml.analyze --side side.jpg [--top top.jpg] [--back back.jpg] [--marker-cm 20]
```

Runs the whole chain: animal → points → marker scale → measurements → BCS.
Only the side photo is required.

### Marker (`marker.py`)

Printed ArUco marker, dictionary `DICT_4X4_50`, **20 cm** by default
(`--marker-cm` to change). It must be flat, fully visible, and at about the
same distance from the camera as the animal. The largest marker is used if
there are several. Markers under 20 px are rejected, and so are markers seen
at a steep angle (longest/shortest side above 1.25).
Without a usable marker the BCS is still estimated, because its signals are
ratios, but centimetre values are left empty.

### Measurements (`measure.py`)

| Measurement | From |
|---|---|
| Body length | nose → tail (side) |
| Body depth | back → belly (side) |
| Leg length | knee → hoof (side): **rough**, because the knee point is an estimate |
| Rump width | top view |
| Hip width | back view |
| Rib visibility | edge density in the rib box (side), 0–1 |

Rib visibility is computed on the clean photo, on a fixed-size patch with
normalised contrast and adaptive edge thresholds.

### BCS v2 (`bcs.py`)

Dairy standard **1–5 in 0.25 steps**, plus a farmer score rounded to 0.5,
a label (Very thin / Thin / Ideal / Fat / Obese), a confidence (capped at
0.9), and the signals that pushed the score up or down.

| Signal | Thin anchor | Fat anchor | Weight |
|---|---|---|---|
| Depth ratio (depth ÷ length) | 0.28 | 0.48 | 0.50 |
| Rib visibility | 0.12 | 0.02 | 0.25 |
| Rump ÷ hip width | 0.85 | 1.05 | 0.25 |

Signal values on the 32 usable side views from the detection check:

| Signal | 10th pct | Median | 90th pct |
|---|---|---|---|
| Depth ratio | 0.27 | 0.38 | 0.48 |
| Rib visibility | 0.00 | 0.06 | 0.12 |

The depth-ratio and rib anchors come from this range. **The old analyzer used
0.22 / 0.30 for the depth ratio, so it rated almost every Indian cow and
buffalo as fat.** Rib visibility depends heavily on photo sharpness (blurry
video stills score about 0), so it gets a lower weight.

**Limits:** the anchors set the range of the scale, not its accuracy. Without
expert-scored animals the score cannot be validated, so every result is
marked `beta`. Reviewer-confirmed scores collected by the app are meant to
recalibrate these anchors.

### Fixes compared with the old Gradio analyzer

| Old problem | Fix |
|---|---|
| Rib edges measured on the image with dots and labels drawn on it | Measured on the clean photo; the input is never modified |
| Uncalibrated thresholds | Anchors from measured breed photos, configurable, documented as beta |
| Only 1, 1.5, 2.5, 3.5, 4.5 or 5 possible | 0.25 steps across 1–5 |
| Rib signal swayed by light, coat and resolution | Fixed-size patch, contrast normalisation, adaptive thresholds |
| No marker checks | Size and tilt checks with clear messages |
| RGB converted as BGR | RGB conversion |
| Empty rib box → division by zero | Returns no value plus a warning |
| Only the first marker used | Largest marker used, warning if several |

## Licences

| Component | Licence |
|---|---|
| This code | MIT |
| torchvision | BSD-3-Clause |
| Mask R-CNN pretrained weights | Trained by torchvision on COCO (annotations CC BY 4.0) |
| OpenCV | Apache-2.0 |

Datasets and model weights are never committed (see `.gitignore`).
