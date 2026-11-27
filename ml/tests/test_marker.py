import cv2
import numpy as np
import pytest

from gopalan_ml.marker import MarkerError, find_marker_scale, to_gray

DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)


def canvas_with_markers(specs, size=(800, 1000)):
    """specs: list of (marker_id, side_px, x, y). Returns an RGB image."""
    img = np.full(size + (3,), 255, np.uint8)
    for mid, side, x, y in specs:
        m = cv2.aruco.generateImageMarker(DICT, mid, side)
        img[y : y + side, x : x + side] = cv2.cvtColor(m, cv2.COLOR_GRAY2RGB)
    return img


def test_scale_from_single_marker():
    img = canvas_with_markers([(3, 200, 100, 100)])
    ms = find_marker_scale(img, 20.0)
    assert ms.marker_id == 3
    assert ms.side_px == pytest.approx(200, rel=0.03)
    assert ms.cm_per_px == pytest.approx(0.1, rel=0.03)
    assert ms.warnings == []


def test_old_bug_8_largest_of_several_markers_is_used():
    img = canvas_with_markers([(1, 80, 50, 50), (2, 240, 400, 300)])
    ms = find_marker_scale(img, 20.0)
    assert ms.marker_id == 2
    assert ms.cm_per_px == pytest.approx(20 / 240, rel=0.03)
    assert any("markers found" in w for w in ms.warnings)


def test_no_marker_gives_clear_error():
    with pytest.raises(MarkerError, match="No ArUco marker"):
        find_marker_scale(np.full((300, 300, 3), 255, np.uint8))


def test_old_bug_5_tiny_marker_rejected():
    img = canvas_with_markers([(0, 14, 50, 50)], size=(200, 200))
    try:
        find_marker_scale(img)
    except MarkerError as e:
        assert "too small" in str(e) or "No ArUco" in str(e)
    else:
        pytest.fail("a 14 px marker must not be accepted")


def test_old_bug_5_steeply_tilted_marker_rejected():
    img = canvas_with_markers([(5, 300, 200, 200)])
    src = np.float32([[200, 200], [500, 200], [500, 500], [200, 500]])
    dst = np.float32([[200, 200], [500, 260], [500, 440], [200, 500]])  # right side squashed
    warped = cv2.warpPerspective(img, cv2.getPerspectiveTransform(src, dst), (1000, 800), borderValue=(255, 255, 255))
    with pytest.raises(MarkerError, match="angle"):
        find_marker_scale(warped)


def test_old_bug_6_rgb_is_converted_as_rgb():
    red = np.zeros((2, 2, 3), np.uint8)
    red[..., 0] = 255  # pure red in RGB order
    assert int(to_gray(red)[0, 0]) == 76  # 0.299 * 255; BGR handling would give 29


def test_invalid_marker_size():
    with pytest.raises(ValueError):
        find_marker_scale(canvas_with_markers([(0, 200, 10, 10)]), marker_size_cm=0)
