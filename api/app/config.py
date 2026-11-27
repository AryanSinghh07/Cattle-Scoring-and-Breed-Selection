"""Settings, read from environment variables (or a local ``api/.env`` file).

Every setting has the prefix ``GOPALAN_``, e.g. ``GOPALAN_MAX_UPLOAD_MB=8``.
See ``api/.env.example`` for the full list.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GOPALAN_", env_file=".env", extra="ignore")

    # Website origins allowed to call the API from a browser.
    allowed_origins: list[str] = Field(
        default=["http://localhost:8080", "http://localhost:5173", "https://gopalanai.netlify.app"]
    )
    # Netlify deploy previews (deploy-preview-<n>--gopalanai.netlify.app).
    allowed_origin_regex: str = r"https://deploy-preview-\d+--gopalanai\.netlify\.app"

    # Uploads
    max_upload_mb: float = 10.0
    max_image_pixels: int = 40_000_000  # ~ 7,300 x 5,500; guards against decompression bombs

    # Models
    load_models: bool = True
    detection_threshold: float = 0.5
    breed_model_path: str = "models/breed_classifier.onnx"
    breed_labels_path: str = "models/labels.json"

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb * 1024 * 1024)


@lru_cache
def get_settings() -> Settings:
    return Settings()
