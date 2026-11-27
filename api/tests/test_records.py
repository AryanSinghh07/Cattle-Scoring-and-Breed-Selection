import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app
from app.models import ModelRegistry
from tests.conftest import make_client
from tests.fake_supabase import USERS, FakeSupabase
from tests.test_analysis import FakeBreed, FakeDetector, side_photo_bytes

A = {"Authorization": "Bearer token-a"}
B = {"Authorization": "Bearer token-b"}
UID_A = USERS["token-a"]["id"]


@pytest.fixture
def fake():
    return FakeSupabase()


@pytest.fixture
def api(settings, fake):
    reg = ModelRegistry(detector=FakeDetector(), breed=FakeBreed())
    with TestClient(create_app(settings, reg, supabase=fake.client())) as c:
        yield c


def analyze(api) -> dict:
    r = api.post("/analyze", files={"side": ("s.png", side_photo_bytes(), "image/png")}, data={"marker_cm": "20"})
    assert r.status_code == 200
    return r.json()


def save_payload(first: dict, **extra) -> dict:
    return {
        "analysis_id": first["analysis_id"],
        "points": {"side": first["views"]["side"]["points"]},
        "scales": {"side": first["views"]["side"]["marker"]["cm_per_px"]},
        "rib_visibility": first["measurements"]["rib_visibility"],
        "breed": {"breed": "gir", "confidence": 0.88, "unsure": False, "top": []},
        **extra,
    }


def save(api, headers, payload, photo: bytes | None = None):
    files = {"side": ("side.jpg", photo, "image/jpeg")} if photo else None
    return api.post("/analyses", headers=headers, data={"data": json.dumps(payload)}, files=files)


def jpeg_with_gps() -> bytes:
    img = Image.open(io.BytesIO(side_photo_bytes())).convert("RGB")
    exif = img.getexif()
    exif[0x8825] = {2: (28.0, 36.0, 0.0)}  # GPS info block
    exif[0x010F] = "PhoneMaker"
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    return buf.getvalue()


# ----------------------------------------------------------------------------- auth


def test_saving_requires_sign_in(api):
    r = api.get("/animals")
    assert r.status_code == 401 and r.json()["error"] == "not_signed_in"
    r = api.get("/animals", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_analyze_still_works_without_sign_in(api):
    assert analyze(api)["bcs"] is not None


def test_saving_unavailable_without_supabase_settings(settings):
    with make_client(settings, ModelRegistry(detector=FakeDetector())) as c:
        r = c.get("/animals", headers=A)
    assert r.status_code == 503 and r.json()["error"] == "saving_unavailable"


# -------------------------------------------------------------------------- animals


def test_animals_are_private(api):
    r = api.post("/animals", headers=A, json={"species": "cow", "name": "Gauri", "tag_id": "A-1", "breed_slug": "gir"})
    assert r.status_code == 201, r.text
    animal = r.json()
    assert animal["owner_id"] == UID_A

    assert [a["id"] for a in api.get("/animals", headers=A).json()] == [animal["id"]]
    assert api.get("/animals", headers=B).json() == []
    assert api.get(f"/animals/{animal['id']}", headers=B).status_code == 404
    assert api.patch(f"/animals/{animal['id']}", headers=B, json={"name": "x"}).status_code == 404

    r = api.patch(f"/animals/{animal['id']}", headers=A, json={"name": "Gauri 2"})
    assert r.status_code == 200 and r.json()["name"] == "Gauri 2" and r.json()["tag_id"] == "A-1"


def test_animal_validation(api):
    assert api.post("/animals", headers=A, json={"species": "goat"}).status_code == 422
    assert api.post("/animals", headers=A, json={"species": "cow", "breed_slug": "jersey"}).status_code == 422
    api.post("/animals", headers=A, json={"species": "cow", "tag_id": "T1"})
    r = api.post("/animals", headers=A, json={"species": "cow", "tag_id": "T1"})
    assert r.status_code == 409 and r.json()["error"] == "duplicate"


# ------------------------------------------------------------------------- analyses


def test_save_without_consent_stores_no_photos(api, fake):
    first = analyze(api)
    r = save(api, A, save_payload(first), photo=jpeg_with_gps())
    assert r.status_code == 201, r.text
    saved = r.json()["analysis"]
    assert saved["photo_consent"] is False and saved["photos"] == {}
    assert fake.files == {}
    assert any("consent" in w for w in r.json()["warnings"])


def test_scores_are_computed_by_the_server(api):
    first = analyze(api)
    payload = save_payload(first, bcs={"score": 5.0}, bcs_score=5.0, measurements={"body_length_cm": 999})
    saved = save(api, A, payload).json()["analysis"]
    assert saved["bcs_score"] == first["bcs"]["score"]
    assert saved["measurements"]["body_length_cm"] == first["measurements"]["body_length_cm"]
    assert saved["breed_slug"] == "gir" and saved["model_versions"]["detector"]["loaded"] is True


def test_save_with_consent_uploads_clean_jpeg(api, fake):
    first = analyze(api)
    animal = api.post("/animals", headers=A, json={"species": "cow"}).json()
    r = save(api, A, save_payload(first, photo_consent=True, animal_id=animal["id"]), photo=jpeg_with_gps())
    assert r.status_code == 201, r.text
    saved = r.json()["analysis"]
    path = saved["photos"]["side"]
    assert path == f"{UID_A}/{saved['id']}/side.jpg"
    stored = Image.open(io.BytesIO(fake.files[path]))
    assert stored.format == "JPEG"
    assert len(stored.getexif()) == 0  # GPS and camera metadata removed

    history = api.get(f"/animals/{animal['id']}/analyses", headers=A).json()
    assert [h["id"] for h in history] == [saved["id"]]
    detail = api.get(f"/analyses/{saved['id']}", headers=A).json()
    assert detail["photo_urls"]["side"].startswith("https://fake.supabase.co/storage/v1/object/sign/")
    assert api.get(f"/analyses/{saved['id']}", headers=B).status_code == 404
    assert api.get("/analyses", headers=B).json() == []


def test_cannot_save_to_someone_elses_animal_and_photos_are_cleaned_up(api, fake):
    first = analyze(api)
    b_animal = api.post("/animals", headers=B, json={"species": "buffalo"}).json()
    r = save(api, A, save_payload(first, photo_consent=True, animal_id=b_animal["id"]), photo=jpeg_with_gps())
    assert r.status_code == 403 and r.json()["error"] == "not_allowed"
    assert fake.files == {}  # uploaded photo removed again


def test_unsure_breed_is_saved_without_slug(api):
    first = analyze(api)
    payload = save_payload(first, breed={"breed": "unsure", "confidence": 0.3, "unsure": True, "top": []})
    saved = save(api, A, payload).json()["analysis"]
    assert saved["breed_slug"] is None and saved["breed_unsure"] is True


@pytest.mark.parametrize("data", [
    "not json",
    json.dumps({"points": {}}),
    json.dumps({"points": {"side": {}}, "breed": {"breed": "jersey", "confidence": 0.9}}),
])
def test_save_rejects_invalid_data(api, data):
    r = api.post("/analyses", headers=A, data={"data": data})
    assert r.status_code == 422 and r.json()["error"] == "invalid_request"
