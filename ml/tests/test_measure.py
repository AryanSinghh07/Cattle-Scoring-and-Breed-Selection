import cv2
import numpy as np
import pytest

from gopalan_ml.measure import Measurements, distance_cm, measure, rib_visibility

SIDE = {
    "nose": {"x": 0, "y": 100}, "tail": {"x": 1000, "y": 100},
    "back": {"x": 500, "y": 0}, "belly": {"x": 500, "y": 400},
    "knee": {"x": 300, "y": 500}, "hoof": {"x": 300, "y": 700},
    "rib_top_left": {"x": 350, "y": 120}, "rib_bottom_right": {"x": 550, "y": 320},
}


def striped(h=400, w=600, period=12, low=60, high=180):
    """Grey image with vertical stripes, like visible ribs."""
    img = np.full((h, w), low, np.uint8)
    for x in range(0, w, period):
        img[:, x : x + period // 2] = high
    return cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)


def test_distance_cm_accepts_dicts_and_objects():
    class P:
        def __init__(self, x, y):
            self.x, self.y = x, y

    assert distance_cm({"x": 0, "y": 0}, {"x": 3, "y": 4}, 2.0) == pytest.approx(10.0)
    assert distance_cm(P(0, 0), P(6, 8), 0.5) == pytest.approx(5.0)


def test_measure_side_top_back():
    img = striped(800, 1100)
    m = measure(
        {"side": 0.2, "top": 0.1, "back": 0.1},
        side_points=SIDE, side_image=img,
        top_points={"rump_left": {"x": 0, "y": 0}, "rump_right": {"x": 500, "y": 0}},
        back_points={"hip_left": {"x": 0, "y": 0}, "hip_right": {"x": 500, "y": 0}},
    )
    assert m.body_length_cm == pytest.approx(200)
    assert m.body_depth_cm == pytest.approx(80)
    assert m.leg_length_cm == pytest.approx(40)
    assert m.rump_width_cm == pytest.approx(50)
    assert m.depth_ratio == pytest.approx(0.4)
    assert m.rump_hip_ratio == pytest.approx(1.0)
    assert 0 < m.rib_visibility <= 1


def test_old_bug_1_input_image_is_not_modified():
    img = striped()
    before = img.copy()
    rib_visibility(img, {"x": 10, "y": 10}, {"x": 300, "y": 300})
    assert np.array_equal(img, before)


def test_old_bug_1_drawn_markings_would_change_the_result():
    """Documents why rib visibility must use the clean photo."""
    clean = np.full((300, 300, 3), 120, np.uint8)
    drawn = clean.copy()
    cv2.circle(drawn, (150, 150), 20, (255, 0, 0), -1)
    cv2.putText(drawn, "Rib TL", (60, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    box = ({"x": 20, "y": 20}, {"x": 280, "y": 280})
    assert rib_visibility(drawn, *box) > rib_visibility(clean, *box)


def test_old_bug_4_brightness_and_resolution_matter_little():
    base = rib_visibility(striped(), {"x": 0, "y": 0}, {"x": 600, "y": 400})
    darker = rib_visibility(striped(low=20, high=70), {"x": 0, "y": 0}, {"x": 600, "y": 400})
    big = striped(800, 1200, period=24)
    bigger = rib_visibility(big, {"x": 0, "y": 0}, {"x": 1200, "y": 800})
    assert darker == pytest.approx(base, rel=0.15)
    assert bigger == pytest.approx(base, rel=0.15)


def test_old_bug_7_empty_or_tiny_rib_box_is_safe():
    img = striped()
    assert rib_visibility(img, {"x": 50, "y": 50}, {"x": 50, "y": 50}) is None
    assert rib_visibility(img, {"x": 50, "y": 50}, {"x": 60, "y": 200}) is None
    m = measure({"side": 1.0}, side_points={**SIDE, "rib_bottom_right": SIDE["rib_top_left"]}, side_image=striped(800, 1100))
    assert m.rib_visibility is None
    assert any("Rib box" in w for w in m.warnings)


def test_rib_box_outside_image_is_clipped():
    assert rib_visibility(striped(), {"x": -100, "y": -100}, {"x": 5000, "y": 5000}) is not None


def test_ratios_none_when_missing():
    m = Measurements(body_length_cm=100)
    assert m.depth_ratio is None and m.rump_hip_ratio is None
    assert m.to_dict()["depth_ratio"] is None
