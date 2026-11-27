import numpy as np
import pytest

from gopalan_ml.keypoints import (
    BACK_POINTS,
    SIDE_POINTS,
    TOP_POINTS,
    place_points,
)


def side_cow(facing: str = "left") -> np.ndarray:
    """A blocky cow seen from the side: trunk, 4 legs, lowered head and a tail."""
    m = np.zeros((400, 800), dtype=bool)
    m[120:261, 200:651] = True  # trunk: back at y=120, belly at y=260
    for x1, x2 in ((250, 281), (300, 331), (560, 591), (600, 631)):
        m[260:381, x1:x2] = True  # legs down to y=380
    for i in range(80):  # neck sloping down towards the head
        x = 200 - i
        m[130 + i // 2 : 200 + i // 2, x] = True
    m[180:251, 60:141] = True  # head, nose at x=60
    m[140:301, 650:661] = True  # tail, rump end at x=660
    return m if facing == "left" else m[:, ::-1].copy()


def test_side_points_facing_left():
    r = place_points(side_cow("left"), "side")
    p = r.points
    assert set(p) == set(SIDE_POINTS)
    assert r.facing == "left"
    assert p["nose"].x < 70
    assert p["tail"].x > 650
    assert p["back"].y == pytest.approx(120, abs=3)
    assert p["belly"].y == pytest.approx(260, abs=5)
    assert p["hoof"].y == pytest.approx(380, abs=3)
    assert 245 <= p["hoof"].x <= 335  # a front leg
    assert p["belly"].y < p["knee"].y < p["hoof"].y
    assert p["rib_top_left"].x < p["rib_bottom_right"].x
    assert p["back"].y < p["rib_top_left"].y < p["rib_bottom_right"].y < p["belly"].y


def test_side_points_facing_right_mirrors():
    r = place_points(side_cow("right"), "side")
    p = r.points
    assert r.facing == "right"
    assert p["nose"].x > 730
    assert p["tail"].x < 150
    assert 465 <= p["hoof"].x <= 555  # mirrored front legs


def test_side_points_forced_facing():
    r = place_points(side_cow("left"), "side", facing="right")
    assert r.facing == "right"
    assert r.points["nose"].x > 650


def test_confidence_in_range():
    r = place_points(side_cow(), "side")
    assert all(0.0 <= p.confidence <= 1.0 for p in r.points.values())


def top_cow() -> np.ndarray:
    """Seen from above: wide body ellipse with a narrow head on the left."""
    yy, xx = np.mgrid[0:400, 0:900]
    body = ((xx - 500) / 300) ** 2 + ((yy - 200) / 100) ** 2 <= 1
    head = (xx >= 100) & (xx < 220) & (yy >= 170) & (yy < 231)
    return body | head


def test_top_points_near_rump():
    r = place_points(top_cow(), "top")
    left, right = r.points["rump_left"], r.points["rump_right"]
    assert set(r.points) == set(TOP_POINTS)
    for p in (left, right):
        assert p.x > 550  # tail half, away from the head
    width = abs(left.y - right.y)
    assert 100 < width < 200


def back_cow() -> np.ndarray:
    """Seen from behind: hips are widest near the top, legs below."""
    m = np.zeros((500, 400), dtype=bool)
    m[50:100, 120:281] = True   # top of the rump
    m[100:150, 80:321] = True   # hips (widest)
    m[150:300, 100:301] = True  # thighs
    m[300:480, 110:161] = True
    m[300:480, 240:291] = True
    return m


def test_back_points_widest_hip_row():
    r = place_points(back_cow(), "back")
    left, right = r.points["hip_left"], r.points["hip_right"]
    assert set(r.points) == set(BACK_POINTS)
    assert left.x == 80 and right.x == 320
    assert 100 <= left.y < 150


def test_scaled_copy():
    r = place_points(back_cow(), "back").scaled(2.0)
    assert r.points["hip_left"].x == 160


@pytest.mark.parametrize("bad", [np.zeros((10, 10)), np.zeros((50, 50, 3))])
def test_invalid_masks(bad):
    with pytest.raises(ValueError):
        place_points(bad, "side")


def test_unknown_view():
    with pytest.raises(ValueError):
        place_points(side_cow(), "front")
