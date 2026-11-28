import io

import cv2
import numpy as np
import pytest
from PIL import Image

from app.cache import PhotoCache
from app.models import ModelRegistry
from gopalan_ml.detect import Detection
from tests.conftest import make_client

DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)


def cow_mask() -> np.ndarray:
    """Blocky cow seen from the side (head left, back y=120, belly y=260, hooves y=380)."""
    m = np.zeros((400, 800), dtype=bool)
    m[120:261, 200:651] = True
    for x1, x2 in ((250, 281), (300, 331), (560, 591), (600, 631)):
        m[260:381, x1:x2] = True
    for i in range(80):
        m[130 + i // 2 : 200 + i // 2, 200 - i] = True
    m[180:251, 60:141] = True
    m[140:301, 650:661] = True
    return m


def side_photo_bytes(with_marker=True) -> bytes:
    mask = cow_mask()
    img = np.full(mask.shape + (3,), 230, np.uint8)
    img[mask] = (120, 70, 40)
    img[150:240, 380:520][::6] = (60, 30, 15)  # "rib" stripes for the rib check
    if with_marker:
        m = cv2.aruco.generateImageMarker(DICT, 3, 100)  # 100 px = 20 cm
        img[10:110, 680:780] = cv2.cvtColor(m, cv2.COLOR_GRAY2RGB)
    buf = io.BytesIO()
    Image.fromarray(img).save(buf, "PNG")
    return buf.getvalue()


class FakeDetector:
    def __init__(self, found=True):
        self.found = found

    def detect(self, image):
        if not self.found:
            return None
        mask = cow_mask()
        ys, xs = np.nonzero(mask)
        return Detection("cow", 0.97, (float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())), mask)


class FakeBreed:
    def __init__(self):
        self.boxes = []
        self.species = []

    def predict(self, image, box=None, top_k=3, species=None):
        self.boxes.append(box)
        self.species.append(species)
        return {"breed": "gir", "name": "Gir", "type": "cow", "confidence": 0.88, "unsure": False, "top": []}


@pytest.fixture
def breed():
    return FakeBreed()


@pytest.fixture
def api(settings, breed):
    reg = ModelRegistry(detector=FakeDetector(), breed=breed)
    with make_client(settings, reg) as c:
        yield c


def analyze(client, **files):
    files = {k: (f"{k}.png", v, "image/png") for k, v in files.items()}
    return client.post("/analyze", files=files, data={"marker_cm": "20"})


def test_analyze_full_result(api, breed):
    r = analyze(api, side=side_photo_bytes())
    assert r.status_code == 200, r.text
    body = r.json()
    side = body["views"]["side"]
    assert side["animal"]["label"] == "cow"
    assert side["facing"] == "left"
    assert len(side["points"]) == 8
    assert side["marker"]["cm_per_px"] == pytest.approx(0.2, rel=0.03)
    assert abs(body["measurements"]["body_length_cm"] - 120) < 6
    assert 1.0 <= body["bcs"]["score"] <= 5.0 and body["bcs"]["beta"] is True
    assert body["breed"]["breed"] == "gir"
    assert breed.boxes[0] is None  # whole photo by default (better on the test set, #28)
    assert body["analysis_id"] and body["expires_in_seconds"] == 1800
    assert body["models"]["detector"]["loaded"] is True


def test_analyze_passes_species_to_breed_model(api, breed):
    files = {"side": ("s.png", side_photo_bytes(), "image/png")}
    assert api.post("/analyze", files=files, data={"species": "buffalo"}).status_code == 200
    assert api.post("/analyze", files=files).status_code == 200
    assert breed.species == ["buffalo", None]
    assert api.post("/analyze", files=files, data={"species": "goat"}).status_code == 422


def test_analyze_without_marker_and_without_animal(settings):
    with make_client(settings, ModelRegistry(detector=FakeDetector(found=False))) as c:
        body = analyze(c, side=side_photo_bytes(with_marker=False)).json()
    assert body["views"]["side"]["animal"] is None
    assert body["bcs"] is None and body["breed"] is None and body["analysis_id"] is None
    assert any("No cow or buffalo" in w for w in body["views"]["side"]["warnings"])
    assert any("Breed prediction is not available" in w for w in body["warnings"])


def test_analyze_needs_side_photo(api):
    assert api.post("/analyze", files={"top": ("t.png", side_photo_bytes(), "image/png")}).status_code == 422


def test_analyze_rejects_bad_file(api):
    r = analyze(api, side=b"definitely not a photo")
    assert r.status_code == 415
    assert r.json()["error"] == "invalid_image"


def test_analyze_503_when_models_missing(settings):
    with make_client(settings, None) as c:
        r = analyze(c, side=side_photo_bytes())
    assert r.status_code == 503
    assert r.json()["error"] == "models_unavailable"


def recompute_body(first: dict, **changes) -> dict:
    pts = {k: dict(v) for k, v in first["views"]["side"]["points"].items()}
    for name, (dx, dy) in changes.items():
        pts[name]["x"] += dx
        pts[name]["y"] += dy
        pts[name]["confidence"] = 1.0
    return {
        "analysis_id": first["analysis_id"],
        "points": {"side": pts},
        "scales": {"side": first["views"]["side"]["marker"]["cm_per_px"]},
        "rib_visibility": first["measurements"]["rib_visibility"],
    }


def test_recompute_same_points_same_result(api):
    first = analyze(api, side=side_photo_bytes()).json()
    r = api.post("/recompute", json=recompute_body(first))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rib_source"] == "photo"
    assert body["measurements"]["body_length_cm"] == first["measurements"]["body_length_cm"]
    assert body["measurements"]["rib_visibility"] == pytest.approx(first["measurements"]["rib_visibility"], abs=0.02)


def test_recompute_after_moving_points(api):
    first = analyze(api, side=side_photo_bytes()).json()
    body = api.post("/recompute", json=recompute_body(first, belly=(0, 40))).json()
    assert body["measurements"]["body_depth_cm"] > first["measurements"]["body_depth_cm"] + 7
    assert body["bcs"]["score"] >= first["bcs"]["score"]


def test_recompute_without_photo_uses_given_rib(api):
    first = analyze(api, side=side_photo_bytes()).json()
    req = recompute_body(first)
    req["analysis_id"] = "expired-or-unknown"
    body = api.post("/recompute", json=req).json()
    assert body["rib_source"] == "given"
    assert body["measurements"]["rib_visibility"] == first["measurements"]["rib_visibility"]
    assert any("expired" in w for w in body["warnings"])


def test_recompute_without_scale_gives_ratios_only(api):
    first = analyze(api, side=side_photo_bytes()).json()
    req = recompute_body(first)
    req["scales"] = {}
    body = api.post("/recompute", json=req).json()
    assert body["measurements"]["body_length_cm"] is None
    assert body["measurements"]["depth_ratio"] is not None
    assert body["bcs"] is not None


@pytest.mark.parametrize("bad", [
    {"points": {}},
    {"points": {"side": {"nose": {"x": 1, "y": 2}}}},
    {"points": {"top": {"rump_left": {"x": 1, "y": 1}, "rump_right": {"x": 2, "y": 1}}}},
])
def test_recompute_validates_points(api, bad):
    r = api.post("/recompute", json=bad)
    assert r.status_code == 422


def test_photo_cache_expires_and_evicts():
    now = [0.0]
    cache = PhotoCache(ttl_seconds=10, max_entries=2, max_side=100, clock=lambda: now[0])
    a = cache.put(np.zeros((400, 200, 3), np.uint8))
    assert cache.get(a).image.shape == (100, 50, 3) and cache.get(a).factor == 0.25
    b = cache.put(np.zeros((10, 10, 3), np.uint8))
    c = cache.put(np.zeros((10, 10, 3), np.uint8))
    assert cache.get(a) is None and cache.get(b) and cache.get(c)  # oldest evicted
    now[0] = 11
    assert cache.get(b) is None and len(cache) == 0  # expired
