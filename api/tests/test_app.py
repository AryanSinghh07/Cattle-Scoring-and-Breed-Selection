import io
import json

import numpy as np
import pytest
from PIL import Image

from app.config import Settings
from app.images import ImageError, decode_image
from app.models import ModelRegistry, load_registry
from tests.conftest import StubDetector, make_client


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["models"]["detector"]["loaded"] is True
    assert body["models"]["breed"]["loaded"] is True


def test_health_degraded_without_breed_model(settings):
    reg = ModelRegistry(detector=StubDetector(), errors={"breed": "missing"})
    with make_client(settings, reg) as c:
        body = c.get("/health").json()
    assert body["status"] == "degraded"
    assert body["models"]["breed"] == {"loaded": False, "error": "missing"}


def test_health_unavailable_when_models_disabled(settings):
    with make_client(settings, None) as c:
        assert c.get("/health").json()["status"] == "unavailable"


def test_cors_allows_site_and_previews_only(client):
    def preflight(origin):
        return client.options("/health", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})

    assert preflight("https://gopalanai.netlify.app").headers.get("access-control-allow-origin") == "https://gopalanai.netlify.app"
    assert preflight("https://deploy-preview-12--gopalanai.netlify.app").headers.get("access-control-allow-origin")
    assert "access-control-allow-origin" not in preflight("https://evil.example.com").headers


def test_openapi_docs_available(client):
    assert client.get("/openapi.json").json()["info"]["title"] == "Gopalan AI API"


def jpeg_bytes(size=(64, 48), exif_orientation=None) -> bytes:
    img = Image.new("RGB", size, "white")
    buf = io.BytesIO()
    if exif_orientation:
        exif = img.getexif()
        exif[0x0112] = exif_orientation
        img.save(buf, "JPEG", exif=exif)
    else:
        img.save(buf, "JPEG")
    return buf.getvalue()


def test_decode_image_rgb_and_exif_rotation():
    arr = decode_image(jpeg_bytes((64, 48), exif_orientation=6), 10**6, 10**7)
    assert arr.shape == (64, 48, 3) and arr.dtype == np.uint8


@pytest.mark.parametrize(
    "data,status,match",
    [
        (b"", 400, "empty"),
        (b"x" * 2000, 413, "too large"),
        (b"<html>not an image</html>", 415, "not a readable photo"),
    ],
)
def test_decode_image_rejects_bad_uploads(data, status, match):
    with pytest.raises(ImageError, match=match) as e:
        decode_image(data, 1000, 10**7)
    assert e.value.status == status


def test_decode_image_rejects_gif_and_huge_images():
    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, "GIF")
    with pytest.raises(ImageError, match="Unsupported image type GIF"):
        decode_image(buf.getvalue(), 10**6, 10**7)
    with pytest.raises(ImageError, match="too many pixels"):
        decode_image(jpeg_bytes((400, 300)), 10**6, 1000)


def test_settings_from_environment(monkeypatch):
    monkeypatch.setenv("GOPALAN_MAX_UPLOAD_MB", "2.5")
    monkeypatch.setenv("GOPALAN_ALLOWED_ORIGINS", json.dumps(["https://example.org"]))
    s = Settings(_env_file=None)
    assert s.max_upload_bytes == int(2.5 * 1024 * 1024)
    assert s.allowed_origins == ["https://example.org"]


def test_load_registry_reports_missing_breed_files(tmp_path, monkeypatch):
    import gopalan_ml.detect as det

    monkeypatch.setattr(det, "AnimalDetector", lambda score_threshold: StubDetector())
    reg = load_registry(0.5, str(tmp_path / "none.onnx"), str(tmp_path / "none.json"))
    assert reg.detector is not None and reg.breed is None
    assert "not found" in reg.errors["breed"]


def test_load_registry_survives_detector_failure(tmp_path, monkeypatch):
    import gopalan_ml.detect as det

    def boom(score_threshold):
        raise RuntimeError("no weights")

    monkeypatch.setattr(det, "AnimalDetector", boom)
    reg = load_registry(0.5, str(tmp_path / "a"), str(tmp_path / "b"))
    assert reg.detector is None and "no weights" in reg.errors["detector"]
