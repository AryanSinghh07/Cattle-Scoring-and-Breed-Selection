# Gopalan AI — API

HTTP API around the ML tools in [`../ml`](../ml): animal detection and body
points, measurements, body condition score (beta) and breed.

Built with **FastAPI**. Models are loaded once at start-up and shared by all
requests.

## Endpoints

| Method | Path | What it does |
|---|---|---|
| GET | `/health` | Status and which models are loaded |
| GET | `/docs` | Interactive API documentation |

More endpoints (`/analyze`, `/recompute`, saving, reviews) are added in the
next Stage 3 issues.

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

Open http://localhost:8000/docs. The first start downloads the Mask R-CNN
weights (~180 MB) into the PyTorch cache.

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

Port 7860 and user id 1000 match Hugging Face Docker Spaces (deployment is
covered in a later issue). The Mask R-CNN weights are downloaded during the
build.

## Tests

```bash
cd api
python -m pytest
```

Tests use stand-in models: no downloads, no secrets.
