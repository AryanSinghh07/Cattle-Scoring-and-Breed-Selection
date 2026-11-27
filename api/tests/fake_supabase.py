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
    "token-r": {"id": "00000000-0000-4000-8000-0000000000c1", "email": "r@example.test"},
    "token-r2": {"id": "00000000-0000-4000-8000-0000000000c2", "email": "r2@example.test"},
}
ROLES = {u["id"]: "farmer" for u in USERS.values()} | {
    USERS["token-r"]["id"]: "reviewer", USERS["token-r2"]["id"]: "reviewer"}


def _err(status: int, code: str, message: str) -> httpx.Response:
    return httpx.Response(status, json={"code": code, "message": message})


class FakeSupabase:
    def __init__(self):
        self.tables: dict[str, list[dict]] = {"animals": [], "analyses": [], "reviews": []}
        self.roles = dict(ROLES)
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

    def _staff(self, uid: str) -> bool:
        return self.roles.get(uid) in ("reviewer", "admin")

    def _visible(self, table: str, uid: str) -> list[dict]:
        if table == "profiles":
            return [{"id": uid, "role": self.roles.get(uid, "farmer"), "created_at": 0}]
        if table == "analyses":
            return [r for r in self.tables[table]
                    if r["owner_id"] == uid or (r.get("photo_consent") and self._staff(uid))]
        if table == "reviews":
            mine = {a["id"] for a in self.tables["analyses"] if a["owner_id"] == uid}
            rows = [r for r in self.tables[table]
                    if r["reviewer_id"] == uid or r["analysis_id"] in mine or self.roles.get(uid) == "admin"]
            return [{**r, "analysis": next((a for a in self._visible("analyses", uid) if a["id"] == r["analysis_id"]), None)}
                    for r in rows]
        return [r for r in self.tables[table] if r["owner_id"] == uid]

    def _rpc(self, name: str, args: dict, uid: str) -> httpx.Response:
        if not self._staff(uid):
            return _err(403, "42501", "Only reviewers and admins can open the review queue")
        reviewed = {r["analysis_id"] for r in self.tables["reviews"]}
        waiting = [a for a in self.tables["analyses"] if a.get("photo_consent") and a["id"] not in reviewed]
        waiting.sort(key=lambda a: (a.get("bcs_confidence") is not None, a.get("bcs_confidence") or 0, a["created_at"]))
        if name == "review_queue":
            return httpx.Response(200, json=waiting[: args.get("p_limit", 20)])
        if name == "review_queue_size":
            return httpx.Response(200, json=len(waiting))
        return httpx.Response(404)

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
        if table.startswith("rpc/"):
            return self._rpc(table.removeprefix("rpc/"), json.loads(request.content or b"{}"), uid)
        if request.method == "GET":
            return httpx.Response(200, json=self._filter(self._visible(table, uid), params))
        if request.method == "POST" and table == "reviews":
            row = json.loads(request.content)
            target = next((a for a in self.tables["analyses"] if a["id"] == row["analysis_id"]), None)
            if not self._staff(uid) or target is None or not target.get("photo_consent"):
                return _err(403, "42501", "new row violates row-level security policy")
            if any(r["analysis_id"] == row["analysis_id"] and r["reviewer_id"] == uid for r in self.tables["reviews"]):
                return _err(409, "23505", "duplicate key value")
            row = {"id": str(uuid.uuid4()), **row, "reviewer_id": uid, "created_at": next(self._clock), "updated_at": None}
            self.tables["reviews"].append(row)
            return httpx.Response(201, json=[row])
        if request.method == "PATCH" and table == "reviews":
            rows = [r for r in self.tables["reviews"] if r["reviewer_id"] == uid and self._staff(uid)]
            rows = self._filter(rows, params)
            for r in rows:
                r.update(json.loads(request.content), updated_at=next(self._clock))
            return httpx.Response(200, json=rows)
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
            if not (path.startswith(uid + "/") or self._staff(uid)) or path not in self.files:
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
