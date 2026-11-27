"""In-memory stand-in for the parts of Supabase the API uses.

Mimics the project's security rules closely enough for API tests: each token
belongs to one user, users only see their own rows, analyses can only link the
user's own animals, photos need consent, and storage paths must start with the
user's id.
"""

from __future__ import annotations

import itertools
import json
import uuid
from urllib.parse import unquote

import httpx

from app.supabase import Supabase

USERS = {
    "token-a": {"id": "00000000-0000-4000-8000-0000000000a1", "email": "a@example.test"},
    "token-b": {"id": "00000000-0000-4000-8000-0000000000b1", "email": "b@example.test"},
}


def _err(status: int, code: str, message: str) -> httpx.Response:
    return httpx.Response(status, json={"code": code, "message": message})


class FakeSupabase:
    def __init__(self):
        self.tables: dict[str, list[dict]] = {"animals": [], "analyses": []}
        self.files: dict[str, bytes] = {}
        self._clock = itertools.count(1)

    def client(self) -> Supabase:
        return Supabase("https://fake.supabase.co", "publishable-key", client=httpx.Client(transport=httpx.MockTransport(self)))

    # httpx calls the transport with each request
    def __call__(self, request: httpx.Request) -> httpx.Response:
        user = USERS.get(request.headers.get("authorization", "").removeprefix("Bearer "))
        path = unquote(request.url.path)
        if path == "/auth/v1/user":
            return httpx.Response(200, json=user) if user else _err(401, "bad_jwt", "invalid JWT")
        if user is None:
            return _err(401, "PGRST301", "JWT invalid")
        if path.startswith("/rest/v1/"):
            return self._rest(request, path.removeprefix("/rest/v1/"), user["id"])
        if path.startswith("/storage/v1/object/"):
            return self._storage(request, path.removeprefix("/storage/v1/object/"), user["id"])
        return httpx.Response(404)

    # -- database ---------------------------------------------------------------------

    def _visible(self, table: str, uid: str) -> list[dict]:
        return [r for r in self.tables[table] if r["owner_id"] == uid]

    @staticmethod
    def _filter(rows: list[dict], params) -> list[dict]:
        for k, v in params.items():
            if k in ("select", "order", "limit") or not v.startswith("eq."):
                continue
            rows = [r for r in rows if str(r.get(k)) == v[3:]]
        if params.get("order", "").endswith(".desc"):
            rows = sorted(rows, key=lambda r: r["created_at"], reverse=True)
        if "limit" in params:
            rows = rows[: int(params["limit"])]
        return rows

    def _rest(self, request: httpx.Request, table: str, uid: str) -> httpx.Response:
        params = dict(request.url.params)
        if request.method == "GET":
            return httpx.Response(200, json=self._filter(self._visible(table, uid), params))
        if request.method == "POST":
            row = json.loads(request.content)
            if row.get("owner_id", uid) != uid:
                return _err(403, "42501", "new row violates row-level security policy")
            if table == "analyses":
                if row.get("animal_id") and not any(a["id"] == row["animal_id"] for a in self._visible("animals", uid)):
                    return _err(403, "42501", "new row violates row-level security policy")
                if row.get("photos") and not row.get("photo_consent"):
                    return _err(400, "23514", "violates check constraint photos_need_consent")
            if table == "animals" and row.get("tag_id") and any(
                    a["tag_id"] == row["tag_id"] for a in self._visible("animals", uid)):
                return _err(409, "23505", "duplicate key value")
            row = {"id": str(uuid.uuid4()), **row, "owner_id": uid, "created_at": next(self._clock)}
            self.tables[table].append(row)
            return httpx.Response(201, json=[row])
        if request.method == "PATCH":
            rows = self._filter(self._visible(table, uid), params)
            for r in rows:
                r.update(json.loads(request.content))
            return httpx.Response(200, json=rows)
        return httpx.Response(405)

    # -- storage ----------------------------------------------------------------------

    def _storage(self, request: httpx.Request, rest: str, uid: str) -> httpx.Response:
        if rest.startswith("sign/"):
            path = rest.removeprefix("sign/").split("/", 1)[1]
            if not path.startswith(uid + "/") or path not in self.files:
                return httpx.Response(400, json={"statusCode": "404", "error": "not_found", "message": "Object not found"})
            return httpx.Response(200, json={"signedURL": f"/object/sign/animal-photos/{path}?token=t"})
        bucket, _, path = rest.partition("/")
        if request.method == "POST":
            if path.split("/")[0] != uid:
                return httpx.Response(403, json={"statusCode": "403", "error": "Unauthorized",
                                                 "message": "new row violates row-level security policy"})
            self.files[path] = request.content
            return httpx.Response(200, json={"Key": f"{bucket}/{path}"})
        if request.method == "DELETE":
            for p in json.loads(request.content)["prefixes"]:
                if p.split("/")[0] == uid:
                    self.files.pop(p, None)
            return httpx.Response(200, json=[])
        return httpx.Response(405)
