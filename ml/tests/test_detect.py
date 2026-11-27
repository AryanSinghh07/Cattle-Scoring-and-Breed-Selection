"""Tests for the parts of detect.py that don't need the neural network."""

import numpy as np
import pytest
from PIL import Image

from gopalan_ml.detect import (
    draw_preview,
    load_image,
    outline_from_mask,
    resize_for_work,
    select_animal,
)


def test_select_prefers_largest_cow():
    i, warnings = select_animal(["cow", "cow", "person"], [0.9, 0.8, 0.99], [100, 500, 900])
    assert i == 1
    assert any("More than one" in w for w in warnings)


def test_select_ignores_low_scores():
    i, _ = select_animal(["cow", "cow"], [0.3, 0.7], [1000, 10])
    assert i == 1


def test_select_falls_back_with_warning():
    i, warnings = select_animal(["person", "horse"], [0.9, 0.8], [100, 50])
    assert i == 1
    assert any("horse" in w for w in warnings)


def test_select_none_when_no_animal():
    assert select_animal(["person", "car"], [0.9, 0.9], [1, 1]) == (None, [])
    assert select_animal([], np.zeros(0), np.zeros(0)) == (None, [])


def test_resize_for_work_limits_longest_side():
    img = np.zeros((3000, 2000, 3), np.uint8)
    out, scale = resize_for_work(img, 1000)
    assert max(out.shape[:2]) == 1000
    assert scale == pytest.approx(1000 / 3000)
    small, s = resize_for_work(np.zeros((100, 50, 3), np.uint8), 1000)
    assert small.shape == (100, 50, 3) and s == 1.0


def test_outline_from_mask_is_polygon():
    m = np.zeros((100, 100), bool)
    m[20:80, 30:70] = True
    poly = outline_from_mask(m)
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    assert min(xs) == 30 and max(xs) == 69
    assert min(ys) == 20 and max(ys) == 79
    assert outline_from_mask(np.zeros((10, 10), bool)) == []


def test_load_image_applies_exif_rotation(tmp_path):
    img = Image.new("RGB", (40, 20), "white")
    exif = img.getexif()
    exif[0x0112] = 6  # "rotate 90° clockwise" as phones save it
    path = tmp_path / "phone.jpg"
    img.save(path, exif=exif)
    arr = load_image(path)
    assert arr.shape == (40, 20, 3)


def test_load_image_handles_png_with_alpha(tmp_path):
    path = tmp_path / "a.png"
    Image.new("RGBA", (10, 8), (255, 0, 0, 128)).save(path)
    assert load_image(path).shape == (8, 10, 3)


def test_draw_preview_does_not_modify_input():
    img = np.zeros((50, 60, 3), np.uint8)
    result = {"outline": [[5, 5], [50, 5], [50, 40]], "points": {"back": {"x": 20, "y": 10, "confidence": 0.9}}}
    out = draw_preview(img, result)
    assert out.shape == img.shape
    assert img.sum() == 0 and out.sum() > 0
