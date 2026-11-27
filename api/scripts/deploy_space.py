"""Deploy the API to a Hugging Face Docker Space.

Copies only what the server needs (ml/gopalan_ml, api/app, requirements,
Dockerfile) into a temporary folder with Linux line endings, adds the Space
README, uploads it, and sets the Space's settings as *variables* (public
values only: Supabase URL, publishable key, model repo, allowed origins).

No secrets are uploaded. Needs a Hugging Face login with write access.

    python scripts/deploy_space.py --space <owner/name> --model-repo <owner/name>
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
COPY = [
    ("ml/requirements.txt", "ml/requirements.txt"),
    ("ml/gopalan_ml", "ml/gopalan_ml"),
    ("api/requirements.txt", "api/requirements.txt"),
    ("api/app", "api/app"),
    ("api/Dockerfile", "Dockerfile"),
]
TEXT_SUFFIXES = {".py", ".txt", ".md", ".json", ".toml", ""}

SPACE_README = """---
title: Cattle Analysis API
emoji: 🐄
colorFrom: green
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Cattle & buffalo body points, BCS (beta) and breed API
---

# Cattle Analysis API

HTTP API that analyses photos of cattle and buffalo: finds the animal, places
body points, reads an ArUco marker for real-world measurements, estimates the
body condition score (BCS, beta) and predicts the breed (16 Indian breeds).

- Health: `GET /health`
- Interactive docs: `GET /docs`
- Breed model: https://huggingface.co/{model_repo}

Source code and documentation: https://github.com/AryanSinghh07/Cattle-Scoring-and-Breed-Selection
"""


def stage(dest: Path, model_repo: str) -> None:
    for src, dst in COPY:
        s, d = ROOT / src, dest / dst
        d.parent.mkdir(parents=True, exist_ok=True)
        if s.is_dir():
            shutil.copytree(s, d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(s, d)
    (dest / "README.md").write_text(SPACE_README.format(model_repo=model_repo), encoding="utf-8")
    # Windows line endings break shell line continuations in the Dockerfile.
    for f in dest.rglob("*"):
        if f.is_file() and (f.suffix in TEXT_SUFFIXES or f.name == "Dockerfile"):
            f.write_bytes(f.read_bytes().replace(b"\r\n", b"\n"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Deploy the API to a Hugging Face Docker Space.")
    ap.add_argument("--space", required=True, help="owner/name of the Space")
    ap.add_argument("--model-repo", required=True, help="owner/name of the public breed model repo")
    ap.add_argument("--origins", default='["https://gopalanai.netlify.app","http://localhost:8080","http://localhost:5173"]',
                    help="JSON list of website origins allowed to call the API")
    ap.add_argument("--dry-run", action="store_true", help="Only build the folder and list its files")
    args = ap.parse_args()

    env = dotenv_values(ROOT / "api" / ".env")
    variables = {
        "GOPALAN_BREED_MODEL_REPO": args.model_repo,
        "GOPALAN_ALLOWED_ORIGINS": json.dumps(json.loads(args.origins)),
        "GOPALAN_SUPABASE_URL": env.get("GOPALAN_SUPABASE_URL") or "",
        "GOPALAN_SUPABASE_PUBLISHABLE_KEY": env.get("GOPALAN_SUPABASE_PUBLISHABLE_KEY") or "",
    }
    key = variables["GOPALAN_SUPABASE_PUBLISHABLE_KEY"]
    if key and not key.startswith(("sb_publishable_", "eyJ")):
        sys.exit("GOPALAN_SUPABASE_PUBLISHABLE_KEY doesn't look like a publishable key; refusing to publish it.")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        stage(tmp, args.model_repo)
        files = sorted(str(p.relative_to(tmp)).replace("\\", "/") for p in tmp.rglob("*") if p.is_file())
        print(f"{len(files)} files to upload:")
        for f in files:
            print("  ", f)
        print("Space variables:", ", ".join(f"{k}={'(set)' if v else '(empty)'}" for k, v in variables.items()))
        if args.dry_run:
            return 0

        from huggingface_hub import HfApi

        api = HfApi()
        url = api.create_repo(args.space, repo_type="space", space_sdk="docker", exist_ok=True)
        for k, v in variables.items():
            if v:
                api.add_space_variable(args.space, k, v)
        api.upload_folder(folder_path=str(tmp), repo_id=args.space, repo_type="space",
                          commit_message="Deploy API", delete_patterns=["*"])
    owner, name = args.space.split("/")
    print(f"Space: {url}")
    print(f"API:   https://{owner}-{name}.hf.space/health  (building takes a few minutes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
