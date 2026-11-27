"""Minimal Supabase client that acts **as the signed-in user**.

Every request carries the user's own access token, so the database's
row-level security rules (``supabase/migrations``) decide what they can read or
write. The API only needs the project URL and the *publishable* key, never the
secret/service-role key.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx


class SupabaseError(Exception):
    def __init__(self, status: int, message: str, code: str | None = None):
        super().__init__(message)
        self.status = status
        self.code = code


class Supabase:
    def __init__(self, url: str, publishable_key: str, client: httpx.Client | None = None, timeout: float = 15.0):
        self.url = url.rstrip("/")
        self.key = publishable_key
        self.http = client or httpx.Client(timeout=timeout)

    # -- helpers ------------------------------------------------------------------

    def _headers(self, token: str, **extra: str) -> dict[str, str]:
        return {"apikey": self.key, "Authorization": f"Bearer {token}", **extra}

    @staticmethod
    def _raise(r: httpx.Response) -> None:
        if r.is_success:
            return
        try:
            body = r.json()
        except ValueError:
            body = {}
        code = str(body.get("code") or body.get("error") or "") or None
        message = body.get("message") or body.get("msg") or body.get("error_description") or r.text[:200]
        status = r.status_code
        if code == "42501":  # row-level security / permission denied
            status = 403
        elif code == "23505":  # unique violation
            status = 409
        elif code in ("23514", "22P02", "23503"):  # check / invalid input / foreign key
            status = 422
        raise SupabaseError(status, message, code)

    # -- auth ---------------------------------------------------------------------

    def get_user(self, token: str) -> dict:
        r = self.http.get(f"{self.url}/auth/v1/user", headers=self._headers(token))
        if r.status_code in (401, 403):
            raise SupabaseError(401, "Your session is invalid or has expired; please sign in again.")
        self._raise(r)
        return r.json()

    # -- database (PostgREST) -------------------------------------------------------

    def select(self, token: str, table: str, params: dict[str, str]) -> list[dict]:
        r = self.http.get(f"{self.url}/rest/v1/{table}", params=params, headers=self._headers(token))
        self._raise(r)
        return r.json()

    def insert(self, token: str, table: str, row: dict[str, Any]) -> dict:
        r = self.http.post(f"{self.url}/rest/v1/{table}", json=row,
                           headers=self._headers(token, Prefer="return=representation"))
        self._raise(r)
        return r.json()[0]

    def update(self, token: str, table: str, match: dict[str, str], values: dict[str, Any]) -> list[dict]:
        params = {k: f"eq.{v}" for k, v in match.items()}
        r = self.http.patch(f"{self.url}/rest/v1/{table}", params=params, json=values,
                            headers=self._headers(token, Prefer="return=representation"))
        self._raise(r)
        return r.json()

    # -- storage --------------------------------------------------------------------

    def upload(self, token: str, bucket: str, path: str, data: bytes, content_type: str) -> None:
        r = self.http.post(f"{self.url}/storage/v1/object/{bucket}/{quote(path)}", content=data,
                           headers=self._headers(token, **{"Content-Type": content_type, "x-upsert": "false"}))
        self._raise(r)

    def remove(self, token: str, bucket: str, paths: list[str]) -> None:
        r = self.http.request("DELETE", f"{self.url}/storage/v1/object/{bucket}", json={"prefixes": paths},
                              headers=self._headers(token))
        self._raise(r)

    def signed_url(self, token: str, bucket: str, path: str, expires_in: int) -> str:
        r = self.http.post(f"{self.url}/storage/v1/object/sign/{bucket}/{quote(path)}", json={"expiresIn": expires_in},
                           headers=self._headers(token))
        self._raise(r)
        signed = r.json().get("signedURL") or r.json().get("signedUrl")
        return f"{self.url}/storage/v1{signed}" if signed.startswith("/") else signed
