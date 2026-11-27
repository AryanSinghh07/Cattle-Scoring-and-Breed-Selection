"""Prepare breed images for training: find, check, de-duplicate and split.

Works on any folder tree where images sit in one folder per breed, such as
the two Kaggle datasets used for v2:

* ``lukex9442/indian-bovine-breeds`` (CC0)
* ``atharvadarpude/indian-buffalo-dataset`` (CC0)

Folder names are matched to the 16 breeds on the website (``src/data/breeds.ts``
slugs), including spelling variants. Other breeds are ignored.

Duplicates: both datasets were collected from Google Images and overlap.
Near-identical images are found with a 64-bit difference hash (dHash). One
copy is kept; if copies carry *different* breed labels, all are dropped as
label noise. This happens before splitting, so the same photo can never sit in
both training and test data.
"""

from __future__ import annotations

import csv
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

# slug -> (display name, animal type); must match src/data/breeds.ts
BREEDS: dict[str, tuple[str, str]] = {
    "gir": ("Gir", "cow"),
    "sahiwal": ("Sahiwal", "cow"),
    "ongole": ("Ongole", "cow"),
    "hallikar": ("Hallikar", "cow"),
    "rathi": ("Rathi", "cow"),
    "red-sindhi": ("Red Sindhi", "cow"),
    "kankrej": ("Kankrej", "cow"),
    "malnad-gidda": ("Malnad Gidda", "cow"),
    "murrah": ("Murrah", "buffalo"),
    "nili-ravi": ("Nili-Ravi", "buffalo"),
    "surti": ("Surti", "buffalo"),
    "jafarabadi": ("Jafarabadi", "buffalo"),
    "mehsana": ("Mehsana", "buffalo"),
    "bhadawari": ("Bhadawari", "buffalo"),
    "toda": ("Toda", "buffalo"),
    "nagpuri": ("Nagpuri", "buffalo"),
}

# Spelling variants seen in the datasets (keys are normalised: lowercase letters only).
ALIASES = {
    "jaffrabadi": "jafarabadi",
    "jaffarabadi": "jafarabadi",
    "bhadwari": "bhadawari",
    "malnadgidda": "malnad-gidda",
    "redsindhi": "red-sindhi",
    "niliravi": "nili-ravi",
}

IMAGE_EXT = {".jpg", ".jpeg", ".jpe", ".png", ".webp", ".bmp", ".gif"}
MIN_BYTES = 5_000
MIN_SIDE = 64
# dHash distance at or below this counts as the same photo. 5 linked a few
# unrelated images (e.g. a photo and a text slide); 3 still catches resized copies.
DUPLICATE_BITS = 3


def norm(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.lower())


_LOOKUP = {norm(s): s for s in BREEDS} | ALIASES


def slug_for_folder(name: str) -> str | None:
    """Website slug for a dataset folder name, or None if it's not one of our breeds."""
    return _LOOKUP.get(norm(name))


@dataclass
class Item:
    path: Path
    slug: str
    source: str
    hash: int = 0
    split: str = ""


@dataclass
class Report:
    found: int = 0
    rejected: Counter = field(default_factory=Counter)
    duplicates_removed: int = 0
    conflicting_removed: int = 0
    per_class: dict[str, dict[str, int]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "found": self.found,
            "rejected": dict(self.rejected),
            "duplicates_removed": self.duplicates_removed,
            "conflicting_labels_removed": self.conflicting_removed,
            "kept": sum(sum(v.values()) for v in self.per_class.values()),
            "per_class": self.per_class,
        }


def scan(roots: list[Path]) -> list[Item]:
    """Every image file inside a folder named after one of our breeds."""
    items = []
    for root in roots:
        root = Path(root)
        for folder in sorted(p for p in root.rglob("*") if p.is_dir()):
            slug = slug_for_folder(folder.name)
            if slug is None:
                continue
            for f in sorted(folder.iterdir()):
                if f.is_file() and f.suffix.lower() in IMAGE_EXT:
                    items.append(Item(f, slug, root.name))
    return items


def load_checked(path: Path) -> tuple[Image.Image | None, str]:
    """Open by real content (not extension). Returns (RGB image or None, reason)."""
    try:
        if path.stat().st_size < MIN_BYTES:
            return None, "too_small_file"
        with Image.open(path) as im:
            if im.format == "GIF":
                return None, "gif"
            im = im.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError):
        return None, "unreadable"
    if min(im.size) < MIN_SIDE:
        return None, "too_small_image"
    return im, "ok"


def dhash(image: Image.Image, size: int = 8) -> int:
    """64-bit difference hash: robust to resizing and recompression."""
    g = np.asarray(image.convert("L").resize((size + 1, size), Image.BILINEAR), dtype=np.int16)
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    return int(np.packbits(bits).view(">u8")[0])


_POPCOUNT = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint8)


def duplicate_groups(hashes: list[int], max_bits: int = DUPLICATE_BITS) -> list[list[int]]:
    """Group indices whose hashes differ by at most ``max_bits`` bits (union-find)."""
    h = np.array(hashes, dtype=np.uint64)
    n = len(h)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for start in range(0, n, 256):
        block = h[start : start + 256]
        x = (block[:, None] ^ h[None, :]).view(np.uint8).reshape(len(block), n, 8)
        dist = _POPCOUNT[x].sum(axis=2)
        for bi, j in zip(*np.nonzero(dist <= max_bits)):
            i = start + bi
            if j > i:
                ri, rj = find(i), find(int(j))
                if ri != rj:
                    parent[rj] = ri

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    return [g for g in groups.values()]


def stratified_split(items: list[Item], val: float = 0.15, test: float = 0.15, seed: int = 42) -> None:
    """Set ``item.split`` to train/val/test, per breed, reproducibly."""
    by_slug: dict[str, list[Item]] = defaultdict(list)
    for it in items:
        by_slug[it.slug].append(it)
    rng = random.Random(seed)
    for slug in sorted(by_slug):
        group = sorted(by_slug[slug], key=lambda it: str(it.path))
        rng.shuffle(group)
        n = len(group)
        n_test = max(1, round(n * test)) if n >= 3 else 0
        n_val = max(1, round(n * val)) if n >= 3 else 0
        for k, it in enumerate(group):
            it.split = "test" if k < n_test else "val" if k < n_test + n_val else "train"


def prepare(roots: list[Path], val: float = 0.15, test: float = 0.15, seed: int = 42, progress: bool = False) -> tuple[list[Item], Report]:
    """Scan, check, de-duplicate and split. Returns (kept items, report)."""
    report = Report()
    found = scan(roots)
    report.found = len(found)

    checked: list[Item] = []
    sizes: list[int] = []
    for k, it in enumerate(found):
        im, reason = load_checked(it.path)
        if im is None:
            report.rejected[reason] += 1
            continue
        it.hash = dhash(im)
        checked.append(it)
        sizes.append(im.size[0] * im.size[1])
        if progress and k % 500 == 0:
            print(f"checked {k}/{len(found)}", flush=True)

    kept: list[Item] = []
    for group in duplicate_groups([it.hash for it in checked]):
        labels = {checked[i].slug for i in group}
        if len(labels) > 1:
            report.conflicting_removed += len(group)
            continue
        best = max(group, key=lambda i: sizes[i])  # keep the largest copy
        kept.append(checked[best])
        report.duplicates_removed += len(group) - 1

    stratified_split(kept, val, test, seed)
    for it in kept:
        report.per_class.setdefault(it.slug, {"train": 0, "val": 0, "test": 0})[it.split] += 1
    report.per_class = dict(sorted(report.per_class.items()))
    return kept, report


def write_manifest(items: list[Item], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["path", "slug", "split", "source"])
        for it in sorted(items, key=lambda it: (it.split, it.slug, str(it.path))):
            w.writerow([str(it.path), it.slug, it.split, it.source])


def read_manifest(path: Path) -> list[Item]:
    with Path(path).open(encoding="utf-8") as f:
        return [Item(Path(r["path"]), r["slug"], r["source"], split=r["split"]) for r in csv.DictReader(f)]
