"""Run animal detection + side-view points on a sample of dataset images.

Picks N images per breed folder (fixed random seed), saves annotated previews
and writes a summary (JSON + Markdown) so results can be checked by eye.

    python scripts/eval_detection.py --data-dir <dataset folder> [--data-dir ...] \
        --breeds Gir Sahiwal Murrah --per-class 3 --out outputs/eval
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gopalan_ml.detect import AnimalDetector, analyze_image, draw_preview, load_image, save_image  # noqa: E402

IMAGE_EXT = {".jpg", ".jpeg", ".jpe", ".png", ".webp", ".bmp"}
MIN_BYTES = 5_000


def norm(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.lower())


def pick_images(data_dirs: list[Path], breeds: list[str] | None, per_class: int, seed: int) -> list[tuple[str, Path]]:
    wanted = {norm(b) for b in breeds} if breeds else None
    by_class: dict[str, list[Path]] = {}
    for root in data_dirs:
        for folder in sorted(p for p in root.rglob("*") if p.is_dir()):
            files = [f for f in folder.iterdir() if f.suffix.lower() in IMAGE_EXT and f.stat().st_size >= MIN_BYTES]
            if not files or (wanted is not None and norm(folder.name) not in wanted):
                continue
            by_class.setdefault(folder.name, []).extend(sorted(files))
    rng = random.Random(seed)
    picked = []
    for cls in sorted(by_class):
        files = by_class[cls]
        picked += [(cls, f) for f in rng.sample(files, min(per_class, len(files)))]
    return picked


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", action="append", required=True, type=Path)
    ap.add_argument("--breeds", nargs="*", help="Breed folder names to include (default: all)")
    ap.add_argument("--per-class", type=int, default=3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=Path("outputs/eval"))
    args = ap.parse_args()

    images = pick_images(args.data_dir, args.breeds, args.per_class, args.seed)
    if not images:
        print("No images found.", file=sys.stderr)
        return 1
    args.out.mkdir(parents=True, exist_ok=True)

    detector = AnimalDetector()
    rows = []
    t0 = time.time()
    for n, (cls, path) in enumerate(images, 1):
        try:
            image = load_image(path)
            result = analyze_image(image, detector, "side")
            preview = args.out / f"{n:03d}_{norm(cls)}.jpg"
            save_image(preview, draw_preview(image, result))
            animal = result["animal"]
            rows.append({
                "n": n, "breed": cls, "file": path.name, "found": animal is not None,
                "label": animal["label"] if animal else None, "score": animal["score"] if animal else None,
                "facing": result["facing"], "points": len(result["points"]),
                "warnings": result["warnings"], "preview": preview.name,
            })
        except Exception as e:  # keep going; report the failure
            rows.append({"n": n, "breed": cls, "file": path.name, "found": False, "error": str(e)})
        print(f"[{n}/{len(images)}] {cls}: {'found' if rows[-1]['found'] else 'NOT found'}", flush=True)

    found = sum(r["found"] for r in rows)
    as_cow = sum(r.get("label") == "cow" for r in rows)
    secs = (time.time() - t0) / len(rows)
    summary = {"images": len(rows), "found": found, "found_rate": round(found / len(rows), 3),
               "labelled_cow": as_cow, "seconds_per_image": round(secs, 2), "rows": rows}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = [f"Found an animal in **{found}/{len(rows)}** images ({found / len(rows):.0%}); "
             f"{as_cow} detected as 'cow'. Average {secs:.1f} s per image on this machine.", "",
             "| # | Breed | Found | Label | Score | Facing | Warnings |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        warn = "; ".join(r.get("warnings", [])) or r.get("error", "")
        lines.append(f"| {r['n']} | {r['breed']} | {'yes' if r['found'] else 'no'} | {r.get('label') or ''} | "
                     f"{r.get('score') or ''} | {r.get('facing') or ''} | {warn} |")
    (args.out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n" + lines[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
