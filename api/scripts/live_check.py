"""Live check of saving against the real Supabase project.

Signs in as a TEST user, then through the API (running in-process):
creates an animal, analyses a sample photo, saves it with photo consent,
reads the history and the photo link, checks that a request without sign-in
sees nothing, and finally deletes everything it created.

Needs in api/.env (git-ignored) or the environment:
    GOPALAN_SUPABASE_URL, GOPALAN_SUPABASE_PUBLISHABLE_KEY
    LIVE_TEST_EMAIL, LIVE_TEST_PASSWORD   (a test user, not a real account)

Run from the api folder:
    python scripts/live_check.py [path/to/side_photo.jpg]
"""

from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import dotenv_values

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE.parent.parent / "ml")]

from fastapi.testclient import TestClient  # noqa: E402

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402


def env(name: str) -> str:
    value = os.environ.get(name) or dotenv_values(HERE.parent / ".env").get(name)
    if not value:
        sys.exit(f"Missing {name} (set it in api/.env)")
    return value


def step(ok: bool, text: str) -> None:
    print(("  OK   " if ok else "  FAIL ") + text)
    if not ok:
        raise SystemExit(1)


def main() -> int:
    url, key = env("GOPALAN_SUPABASE_URL").rstrip("/"), env("GOPALAN_SUPABASE_PUBLISHABLE_KEY")
    email, password = env("LIVE_TEST_EMAIL"), env("LIVE_TEST_PASSWORD")

    r = httpx.post(f"{url}/auth/v1/token?grant_type=password", headers={"apikey": key},
                   json={"email": email, "password": password}, timeout=20)
    step(r.status_code == 200, f"sign in as test user ({r.status_code})")
    token, uid = r.json()["access_token"], r.json()["user"]["id"]
    auth = {"Authorization": f"Bearer {token}"}
    rest = {"apikey": key, "Authorization": f"Bearer {token}"}

    photo_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if photo_path is None:
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (640, 480), (120, 80, 40)).save(buf, "JPEG")
        photo = buf.getvalue()
    else:
        photo = photo_path.read_bytes()

    settings = Settings()  # reads api/.env (models, Supabase)
    created = {"animal": None, "analysis": None, "photo": None}
    try:
        with TestClient(create_app(settings)) as api:
            health = api.get("/health").json()
            print(f"  ..   models: {health['status']}")

            r = api.post("/animals", headers=auth, json={"species": "cow", "name": "Live check", "tag_id": "LIVE-CHECK"})
            step(r.status_code == 201, f"create animal ({r.status_code})")
            created["animal"] = animal = r.json()

            r = api.post("/analyze", files={"side": ("side.jpg", photo, "image/jpeg")}, data={"marker_cm": "20"})
            first = r.json()
            step(r.status_code == 200, f"analyze photo ({r.status_code}, BCS {first.get('bcs') and first['bcs']['score']})")
            points = first["views"]["side"]["points"]
            if not points:
                print("  ..   no animal found in the photo; saving needs a photo with a cow or buffalo")
                return 1
            marker = first["views"]["side"].get("marker") or {}
            payload = {"analysis_id": first["analysis_id"], "points": {"side": points},
                       "scales": {"side": marker.get("cm_per_px")}, "animal_id": animal["id"],
                       "photo_consent": True, "breed": first.get("breed")}
            r = api.post("/analyses", headers=auth, data={"data": json.dumps(payload)},
                         files={"side": ("side.jpg", photo, "image/jpeg")})
            step(r.status_code == 201, f"save analysis with photo ({r.status_code}) {r.text[:150] if r.status_code != 201 else ''}")
            created["analysis"] = saved = r.json()["analysis"]
            created["photo"] = saved["photos"].get("side")
            step(created["photo"] == f"{uid}/{saved['id']}/side.jpg", "photo stored in the user's own folder")

            history = api.get(f"/animals/{animal['id']}/analyses", headers=auth).json()
            step([h["id"] for h in history] == [saved["id"]], "history lists the saved analysis")

            detail = api.get(f"/analyses/{saved['id']}", headers=auth).json()
            link = detail["photo_urls"].get("side")
            step(bool(link) and httpx.get(link, timeout=20).status_code == 200, "temporary photo link works")
            public = httpx.get(f"{url}/storage/v1/object/public/{settings.photo_bucket}/{created['photo']}", timeout=20)
            step(public.status_code != 200, f"photo is NOT publicly readable ({public.status_code})")

            step(api.get("/animals").status_code == 401, "without sign-in: refused")
            anon = httpx.get(f"{url}/rest/v1/analyses", params={"id": f"eq.{saved['id']}"}, headers={"apikey": key}, timeout=20)
            step(anon.status_code in (401, 403) or anon.json() == [], "anonymous database read sees nothing")
    finally:
        # Clean up everything this check created (owner may delete own rows/files).
        if created["photo"]:
            httpx.request("DELETE", f"{url}/storage/v1/object/{settings.photo_bucket}", headers=rest,
                          json={"prefixes": [created["photo"]]}, timeout=20)
        if created["analysis"]:
            httpx.delete(f"{url}/rest/v1/analyses", params={"id": f"eq.{created['analysis']['id']}"}, headers=rest, timeout=20)
        if created["animal"]:
            httpx.delete(f"{url}/rest/v1/animals", params={"id": f"eq.{created['animal']['id']}"}, headers=rest, timeout=20)
        left = httpx.get(f"{url}/rest/v1/animals", params={"tag_id": "eq.LIVE-CHECK"}, headers=rest, timeout=20).json()
        print(f"  ..   cleanup: {'done' if left == [] else 'some rows remain: ' + str(left)}")
    print("Live check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
