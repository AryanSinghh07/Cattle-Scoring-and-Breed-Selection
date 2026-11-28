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
        default=["http://localhost:3000", "http://localhost:8080", "http://localhost:5173",
                 "https://gopalanai.netlify.app"]
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
    # If the files above don't exist, download them from this public Hugging Face model repo.
    breed_model_repo: str | None = None
    breed_model_revision: str | None = None  # branch, tag or commit; None = latest
    breed_crop_to_animal: bool = True  # classify the detected animal, not the whole photo

    # Supabase (saving). Only the URL and the *publishable* key are needed:
    # requests run with each user's own token, so database security rules apply.
    supabase_url: str | None = None
    supabase_publishable_key: str | None = None
    photo_bucket: str = "animal-photos"
    photo_max_side: int = 2048
    signed_url_seconds: int = 3600

    # Side photos kept in memory (never on disk) so /recompute can re-check ribs
    cache_ttl_minutes: float = 30
    cache_max_entries: int = 32
    cache_max_side: int = 1600

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb * 1024 * 1024)


@lru_cache
def get_settings() -> Settings:
    return Settings()
