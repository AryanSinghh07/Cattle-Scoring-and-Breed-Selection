"""End-to-end pipeline test with a stand-in detector (no neural network needed)."""

import cv2
import numpy as np

from gopalan_ml.analyze import analyze_photos
from gopalan_ml.detect import Detection
from tests.test_keypoints import side_cow

DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)


class FakeDetector:
    def __init__(self, mask):
        self.mask = mask

    def detect(self, image):
        ys, xs = np.nonzero(self.mask)
        return Detection("cow", 0.95, (xs.min(), ys.min(), xs.max(), ys.max()), self.mask)


def side_photo(with_marker: bool) -> tuple[np.ndarray, np.ndarray]:
    mask = side_cow()
    img = np.full(mask.shape + (3,), 230, np.uint8)
    img[mask] = (120, 70, 40)
    if with_marker:
        m = cv2.aruco.generateImageMarker(DICT, 7, 100)  # 100 px = 20 cm -> 0.2 cm/px
        img[10:110, 680:780] = cv2.cvtColor(m, cv2.COLOR_GRAY2RGB)
    return img, mask


def test_full_pipeline_with_marker():
    img, mask = side_photo(with_marker=True)
    out = analyze_photos(FakeDetector(mask), img)
    side = out["views"]["side"]
    assert side["marker"]["marker_id"] == 7
    m = out["measurements"]
    assert abs(m["body_length_cm"] - 600 * 0.2) < 6  # nose x~60 to tail x~660
    assert abs(m["body_depth_cm"] - 140 * 0.2) < 3  # back y=120 to belly y=260
    bcs = out["bcs"]
    assert 1.0 <= bcs["score"] <= 5.0 and bcs["beta"] is True


def test_measure_and_score_reuses_rib_value_without_photo():
    from gopalan_ml.analyze import measure_and_score

    img, mask = side_photo(with_marker=True)
    out = analyze_photos(FakeDetector(mask), img)
    pts = {"side": out["views"]["side"]["points"]}
    scale = {"side": out["views"]["side"]["marker"]["cm_per_px"]}
    rib = out["measurements"]["rib_visibility"]

    meas, bcs, _ = measure_and_score(pts, scale, rib_visibility=rib)
    assert meas == out["measurements"]
    assert bcs["score"] == out["bcs"]["score"]

    # Moving the belly down makes the body deeper -> the score can't go down.
    moved = {k: dict(v) for k, v in pts["side"].items()}
    moved["belly"]["y"] += 40
    meas2, bcs2, _ = measure_and_score({"side": moved}, scale, rib_visibility=rib)
    assert meas2["body_depth_cm"] > meas["body_depth_cm"]
    assert bcs2["score"] >= bcs["score"]


def test_pipeline_without_marker_still_scores_but_no_cm():
    img, mask = side_photo(with_marker=False)
    out = analyze_photos(FakeDetector(mask), img)
    assert out["views"]["side"]["marker"] is None
    assert any("No ArUco marker" in w for w in out["views"]["side"]["warnings"])
    assert out["measurements"]["body_length_cm"] is None
    assert out["measurements"]["depth_ratio"] is not None
    assert out["bcs"] is not None
