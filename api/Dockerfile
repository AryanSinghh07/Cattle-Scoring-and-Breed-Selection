# CPU image for the Gopalan AI API. Build from the repository root:
#   docker build -f api/Dockerfile -t gopalan-api .
#   docker run -p 7860:7860 -v "$PWD/api/models:/app/api/models" gopalan-api
# Port 7860 and user id 1000 match Hugging Face Docker Spaces.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 user

WORKDIR /app
COPY ml/requirements.txt ml/requirements.txt
COPY api/requirements.txt api/requirements.txt
RUN pip install --upgrade pip && pip install -r api/requirements.txt

COPY ml/gopalan_ml ml/gopalan_ml
COPY api/app api/app

USER user
ENV HOME=/home/user \
    TORCH_HOME=/home/user/.cache/torch \
    PYTHONPATH=/app/ml:/app/api
WORKDIR /app/api

# Download the Mask R-CNN weights at build time so the first request is fast.
RUN python -c "from torchvision.models.detection import MaskRCNN_ResNet50_FPN_V2_Weights as W; W.DEFAULT.get_state_dict(progress=False)"

EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
