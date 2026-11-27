import numpy as np
import pytest
from PIL import Image

from gopalan_ml.breed_data import (
    BREEDS,
    dhash,
    duplicate_groups,
    load_checked,
    prepare,
    read_manifest,
    scan,
    slug_for_folder,
    write_manifest,
)


def photo(seed: int, size=(200, 160)) -> Image.Image:
    """A smooth random 'photo' (low-frequency structure plus a little grain)."""
    rng = np.random.default_rng(seed)
    small = Image.fromarray(rng.integers(0, 255, (5, 6, 3), dtype=np.uint8))
    img = np.asarray(small.resize(size, Image.BICUBIC), dtype=np.int16)
    img = np.clip(img + rng.integers(-12, 12, img.shape), 0, 255).astype(np.uint8)
    return Image.fromarray(img)


def save(img: Image.Image, path, **kw):
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, **kw)
    return path


@pytest.mark.parametrize("folder,slug", [
    ("Gir", "gir"), ("Red_Sindhi", "red-sindhi"), ("Malnad_gidda", "malnad-gidda"),
    ("Jaffrabadi", "jafarabadi"), ("Jaffarabadi", "jafarabadi"), ("bhadwari", "bhadawari"),
    ("Bhadawari", "bhadawari"), ("nili-ravi", "nili-ravi"), ("Nili_Ravi", "nili-ravi"),
    ("Holstein_Friesian", None), ("Chhattisgarhi", None),
])
def test_slug_for_folder(folder, slug):
    assert slug_for_folder(folder) == slug


def test_sixteen_website_breeds():
    assert len(BREEDS) == 16
    assert sum(t == "buffalo" for _, t in BREEDS.values()) == 8


def test_scan_only_known_breeds(tmp_path):
    save(photo(1), tmp_path / "ds" / "Gir" / "a.jpg")
    save(photo(2), tmp_path / "ds" / "Jersey" / "b.jpg")
    (tmp_path / "ds" / "Gir" / "notes.txt").write_text("not an image")
    items = scan([tmp_path / "ds"])
    assert [(i.slug, i.path.name) for i in items] == [("gir", "a.jpg")]


def test_load_checked_by_content(tmp_path):
    assert load_checked(save(photo(1), tmp_path / "ok.jpg", quality=95))[1] == "ok"
    assert load_checked(save(photo(1), tmp_path / "jpeg_named.gif", format="JPEG", quality=95))[1] == "ok"
    assert load_checked(save(photo(1, (40, 40)), tmp_path / "small.png"))[1] in ("too_small_file", "too_small_image")
    assert load_checked(save(photo(1), tmp_path / "anim.gif"))[1] == "gif"
    bad = tmp_path / "fake.jpg"
    bad.write_bytes(b"<html>" + b"x" * 6000)
    assert load_checked(bad)[1] == "unreadable"


def test_dhash_survives_resize_but_differs_between_photos():
    a = photo(1)
    assert bin(dhash(a) ^ dhash(a.resize((150, 120)))).count("1") <= 3
    assert bin(dhash(a) ^ dhash(photo(2))).count("1") > 10


def test_duplicate_groups():
    groups = duplicate_groups([0b0, 0b1, 0b1111_1111_1111, 0b1111_1111_1110])
    assert sorted(sorted(g) for g in groups) == [[0, 1], [2, 3]]


def test_prepare_dedupes_drops_conflicts_and_splits(tmp_path):
    root = tmp_path / "ds"
    for k in range(20):
        save(photo(100 + k), root / "Gir" / f"{k}.jpg", quality=95)
        save(photo(200 + k), root / "Murrah" / f"{k}.jpg", quality=95)
    save(photo(100).resize((180, 144)), root / "Gir" / "dup.jpg", quality=95)  # same-label copy
    save(photo(999), root / "Gir" / "x.jpg", quality=95)
    save(photo(999), root / "Sahiwal" / "x.jpg", quality=95)  # same photo, different breed

    items, report = prepare([root], seed=1)
    assert report.duplicates_removed == 1
    assert report.conflicting_removed == 2
    assert len(items) == 40
    assert {i.slug for i in items} == {"gir", "murrah"}
    for slug in ("gir", "murrah"):
        splits = [i.split for i in items if i.slug == slug]
        assert splits.count("test") == 3 and splits.count("val") == 3 and splits.count("train") == 14

    again, _ = prepare([root], seed=1)
    assert {(i.path, i.split) for i in items} == {(i.path, i.split) for i in again}


def test_manifest_roundtrip(tmp_path):
    root = tmp_path / "ds"
    for k in range(4):
        save(photo(k), root / "Toda" / f"{k}.jpg", quality=95)
    items, _ = prepare([root])
    write_manifest(items, tmp_path / "m.csv")
    back = read_manifest(tmp_path / "m.csv")
    assert {(str(i.path), i.slug, i.split) for i in back} == {(str(i.path), i.slug, i.split) for i in items}
