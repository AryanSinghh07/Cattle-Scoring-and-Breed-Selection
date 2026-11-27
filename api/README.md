# Gopalan AI — API

HTTP API around the ML tools in [`../ml`](../ml): animal detection and body
points, measurements, body condition score (beta) and breed.

Built with **FastAPI**. Models are loaded once at start-up and shared by all
requests.

## Endpoints

| Method | Path | What it does |
|---|---|---|
| GET | `/health` | Status and which models are loaded |
| POST | `/analyze` | Photos in → animal, body points, marker, measurements, BCS (beta), breed |
| POST | `/recompute` | Adjusted body points in → new measurements and BCS (no detection) |
| GET | `/docs` | Interactive API documentation |

Saved data (needs sign-in, see below):

| Method | Path | What it does |
|---|---|---|
| POST | `/animals` | Add an animal |
| GET | `/animals` | List my animals |
| GET / PATCH | `/animals/{id}` | Get / update one of my animals |
| GET | `/animals/{id}/analyses` | History of one animal (newest first) |
| POST | `/analyses` | Save an analysis (photos only with consent) |
| GET | `/analyses` | My recent analyses |
| GET | `/analyses/{id}` | One saved analysis, with temporary photo links |

Review (reviewers and admins only):

| Method | Path | What it does |
|---|---|---|
| GET | `/review/queue` | Consented analyses nobody has reviewed yet, least confident first, with photo links and the number waiting |
| GET | `/review/{id}` | One analysis with photos and my existing review |
| PUT | `/review/{id}` | Confirm or correct BCS and/or breed (submitting again updates my review) |
| GET | `/review/export/labels` | Reviewed results as training data (`?format=jsonl` or `csv`) |

### Review

The semi-automatic loop: the system suggests BCS and breed, and a reviewer
checks it. Reviewed values become the training labels for the learned BCS
model planned for v3.

- Only users whose `profiles.role` is `reviewer` or `admin` can use these
  endpoints (`403 not_reviewer` otherwise). Roles are set in SQL; see
  [`supabase/README.md`](../supabase/README.md).
- The queue comes from the database function `review_queue()`, so an item
  reviewed by **anyone** leaves the queue for everyone. Analyses without
  photo consent are never shown.
- `PUT /review/{id}` body:

  ```json
  {"decision": "corrected", "bcs_score": 3.25, "breed_slug": "gir", "notes": "ribs less visible than scored"}
  ```

  `confirmed` keeps the model's BCS and breed (they're filled in).
  `corrected` needs a different BCS (1–5, 0.25 steps) and/or breed.
- The export pairs the human label with the model output, plus points,
  measurements and photo storage paths. Reviewers export their own reviews;
  admins export everyone's. Read it in Python with
  `gopalan_ml.review_data.read_review_export(path)`.

### Sign-in and saving

Trying `/analyze` and `/recompute` needs **no account**, and nothing is
stored. To save, the website signs the user in with Supabase and sends their
access token:

```
Authorization: Bearer <Supabase access token>
```

The API makes every database and storage call **with that token**, so the
security rules in [`supabase/`](../supabase) decide what each user can see.
The API only needs the project URL and the **publishable** key. It never
uses the secret/service-role key.

`POST /analyses` is `multipart/form-data`:

| Field | Meaning |
|---|---|
| `data` | JSON: `points`, `scales`, `analysis_id`, `rib_visibility` (as for `/recompute`), plus `animal_id`, `photo_consent`, `breed` (from `/analyze`) |
| `side`, `top`, `back` | Photos. **Stored only when `photo_consent` is true**, re-encoded as JPEG (max 2048 px) so hidden metadata such as GPS location is removed |

- Measurements and BCS are **recomputed on the server** from the points;
  values sent by the app are ignored.
- Photos go to the private `animal-photos` bucket as
  `<user id>/<analysis id>/<view>.jpg`. If saving fails, uploaded photos are
  removed again.
- Someone else's animal or analysis returns `404` (the database hides it).
  Linking an analysis to someone else's animal returns `403`.

### `POST /analyze`

`multipart/form-data`:

| Field | Required | Meaning |
|---|---|---|
| `side` | yes | Side-view photo |
| `top`, `back` | no | Top and back photos (rump/hip comparison) |
| `marker_cm` | no (20) | Printed ArUco marker side length in cm |
| `facing` | no (`auto`) | `auto`, `left` or `right` for the side photo |

```bash
curl -F side=@cow_side.jpg -F marker_cm=20 http://127.0.0.1:8000/analyze
```

Response (shortened):

```json
{
  "analysis_id": "4f0c…",
  "expires_in_seconds": 1800,
  "views": {"side": {"animal": {"label": "cow", "score": 0.99, "box": [..]},
                     "outline": [[x, y], ..], "facing": "right",
                     "points": {"nose": {"x": .., "y": .., "confidence": 0.85}, ..},
                     "marker": {"cm_per_px": 0.4, ..}, "warnings": []}},
  "measurements": {"body_length_cm": 192.3, "body_depth_cm": 67.2, "depth_ratio": 0.349, ..},
  "bcs": {"score": 2.75, "farmer_score": 3.0, "label": "Ideal", "confidence": 0.51, "beta": true, ..},
  "breed": {"breed": "gir", "name": "Gir", "confidence": 0.912, "unsure": false, "top": [..]},
  "warnings": [],
  "timing_ms": 2329
}
```

Problems with the photos (no animal, no marker, unclear direction) come back
as `warnings` with HTTP 200 so the app can guide the user. Bad files return
`413`/`415`, and `503` means the models aren't loaded yet. Breed is predicted
on the detected animal (cropped with a 10% margin); below the model's
threshold it is `"unsure"` with the top guesses.

### `POST /recompute`

For the semi-automatic step: when the user drags points, send them back to
get new measurements and BCS instantly (about 2 ms on the server).

```json
{
  "analysis_id": "4f0c…",
  "points": {"side": {"nose": {"x": 812, "y": 260, "confidence": 1.0}, "...": {}}},
  "scales": {"side": 0.4},
  "rib_visibility": 0.059
}
```

- `points.side` needs all 8 side points; `top`/`back` need their 2 points.
- `scales` are the `marker.cm_per_px` values from `/analyze`; without them
  only ratios (and the BCS) are returned, no centimetres.
- With a valid `analysis_id`, rib visibility is re-checked on the photo
  (the rib box may have moved). The side photo is kept **in memory only**,
  downscaled, for 30 minutes (`GOPALAN_CACHE_TTL_MINUTES`), never on disk.
  After that, the given `rib_visibility` is reused.

`/health` example:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "models": {
    "detector": {"loaded": true, "name": "maskrcnn_resnet50_fpn_v2 (COCO)", "threshold": 0.5},
    "breed": {"loaded": true, "name": "convnext_tiny.fb_in22k_ft_in1k", "classes": 16,
              "unsure_threshold": 0.45, "version": "a889f6020f32"}
  }
}
```

`status` is `ok` (both models), `degraded` (no breed model; analysis still
works) or `unavailable` (no detector).

## Run locally

The API reuses the ML environment, so PyTorch isn't installed twice:

```bash
cd ml
python -m venv .venv
.venv\Scripts\activate            # Windows (macOS/Linux: source .venv/bin/activate)
pip install -r ../api/requirements.txt

cd ../api
copy .env.example .env            # macOS/Linux: cp .env.example .env
# Put breed_classifier.onnx and labels.json into api/models/ (git-ignored),
# or point GOPALAN_BREED_MODEL_PATH / GOPALAN_BREED_LABELS_PATH at them.
set PYTHONPATH=../ml              # macOS/Linux: export PYTHONPATH=../ml
uvicorn app.main:app --reload --port 8000
```

Open http://127.0.0.1:8000/docs. The first start downloads the Mask R-CNN
weights (~180 MB) into the PyTorch cache.

Tip for Windows: call the API at `127.0.0.1` rather than `localhost` from
scripts. Some clients try IPv6 first and wait ~2 seconds per request before
falling back.

## Settings

All settings are environment variables with the prefix `GOPALAN_` (or lines
in `api/.env`). See [`.env.example`](.env.example).

| Variable | Default | Meaning |
|---|---|---|
| `GOPALAN_ALLOWED_ORIGINS` | localhost + `https://gopalanai.netlify.app` | Website origins allowed to call the API (JSON list) |
| `GOPALAN_ALLOWED_ORIGIN_REGEX` | Netlify deploy previews | Extra allowed origins |
| `GOPALAN_MAX_UPLOAD_MB` | `10` | Largest photo accepted |
| `GOPALAN_MAX_IMAGE_PIXELS` | `40000000` | Largest image size in pixels |
| `GOPALAN_LOAD_MODELS` | `true` | Load models at start-up |
| `GOPALAN_DETECTION_THRESHOLD` | `0.5` | Minimum detection score |
| `GOPALAN_BREED_MODEL_PATH` | `models/breed_classifier.onnx` | Breed model |
| `GOPALAN_BREED_LABELS_PATH` | `models/labels.json` | Breed labels and threshold |
| `GOPALAN_BREED_MODEL_REPO` | (empty) | Hugging Face model repo to download the breed model from when the files above don't exist |
| `GOPALAN_BREED_MODEL_REVISION` | (latest) | Branch, tag or commit of that repo |
| `GOPALAN_BREED_CROP_TO_ANIMAL` | `true` | Classify the detected animal rather than the whole photo |
| `GOPALAN_SUPABASE_URL` | (empty) | Supabase project URL; saving is off without it |
| `GOPALAN_SUPABASE_PUBLISHABLE_KEY` | (empty) | Publishable (anon) key, never the secret key |
| `GOPALAN_PHOTO_BUCKET` | `animal-photos` | Storage bucket for consented photos |
| `GOPALAN_PHOTO_MAX_SIDE` | `2048` | Stored photos are resized to fit this |
| `GOPALAN_SIGNED_URL_SECONDS` | `3600` | How long photo links stay valid |
| `GOPALAN_CACHE_TTL_MINUTES` | `30` | How long `/recompute` can re-check ribs on the photo |
| `GOPALAN_CACHE_MAX_ENTRIES` | `32` | Photos kept in memory at most |
| `GOPALAN_CACHE_MAX_SIDE` | `1600` | Photos are downscaled to this size in memory |

If the breed model files are missing, the API still starts and reports
`degraded`; breed prediction is simply left out.

## Uploads

Photos are checked by their real content, not the file name: JPEG, PNG,
WEBP and BMP are accepted, GIFs and non-images are rejected (415), files over
the size limit or with too many pixels are rejected (413). Phone EXIF
rotation is applied.

## Docker

Build from the **repository root**:

```bash
docker build -f api/Dockerfile -t gopalan-api .
docker run -p 7860:7860 -v "$PWD/api/models:/app/api/models" gopalan-api
```

Port 7860 and user id 1000 match Hugging Face Docker Spaces. The Mask R-CNN
weights are downloaded during the build.

## Models and hosting

| What | Where | Status |
|---|---|---|
| Breed model (public model repo) | https://huggingface.co/thearyansingh/cattle-breed-classifier | ✅ published |
| API | Runs locally (`uvicorn`, see [Run locally](#run-locally)) | Online hosting planned on **Google Cloud Run** |

The names describe the service, not the brand, so they stay valid if the
website is renamed.

Any API instance can download the breed model from the public model repo at
start-up: set `GOPALAN_BREED_MODEL_REPO=thearyansingh/cattle-breed-classifier`
and leave the local model paths pointing at files that don't exist. No token
is needed because the repo is public.

**Publish a new model** (after a new Kaggle training run) needs a Hugging Face
login with write access (`hf auth login`):

```bash
cd api
python scripts/publish_model.py ../ml/outputs/<run>/breed_model --repo thearyansingh/cattle-breed-classifier
```

This uploads the ONNX model, `labels.json`, `metrics.json`, the charts and a
generated model card. Running APIs pick up the new model at their next restart.
Pin a version with `GOPALAN_BREED_MODEL_REVISION`.

Tip: if an upload hangs with no progress on Windows, set `HF_HUB_DISABLE_XET=1`
to use the classic upload method (it shows a progress bar).

### Hugging Face Spaces (needs PRO)

`scripts/deploy_space.py` deploys the API as a Hugging Face **Docker Space**.
It uploads only `ml/gopalan_ml`, `api/app`, the requirement files and the
Dockerfile (with Linux line endings), and sets public Space variables (Supabase
URL, publishable key, model repo, allowed origins). Since late 2026 Hugging Face
requires a **PRO** subscription for Docker Spaces (`402 Payment Required` on the
free plan), so this route is only usable with PRO:

```bash
cd api
python scripts/deploy_space.py --space thearyansingh/cattle-analysis-api \
  --model-repo thearyansingh/cattle-breed-classifier [--dry-run]
```

The API needs about 2 GB of memory (PyTorch + Mask R-CNN), so hosting tiers
with 512 MB are too small.

## Tests

```bash
cd api
python -m pytest
```

Tests use stand-in models: no downloads, no secrets.
