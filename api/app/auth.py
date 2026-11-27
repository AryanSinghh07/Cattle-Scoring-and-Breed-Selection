"""Who is calling? Resolves the Supabase access token sent as ``Authorization: Bearer``."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .supabase import Supabase, SupabaseError

bearer = HTTPBearer(auto_error=False, description="Supabase access token of the signed-in user")


@dataclass
class User:
    id: str
    token: str
    email: str | None = None


def get_supabase(request: Request) -> Supabase:
    sb = getattr(request.app.state, "supabase", None)
    if sb is None:
        raise HTTPException(503, detail={"error": "saving_unavailable",
                                         "message": "Saving is not set up on this server (Supabase settings missing)."})
    return sb


def current_user(request: Request, creds: HTTPAuthorizationCredentials | None) -> User:
    if creds is None or not creds.credentials:
        raise HTTPException(401, detail={"error": "not_signed_in", "message": "Sign in to save and view your animals."},
                            headers={"WWW-Authenticate": "Bearer"})
    sb = get_supabase(request)
    try:
        info = sb.get_user(creds.credentials)
    except SupabaseError as e:
        raise HTTPException(e.status if e.status in (401, 403) else 502,
                            detail={"error": "not_signed_in" if e.status == 401 else "auth_error", "message": str(e)}) from None
    return User(id=info["id"], token=creds.credentials, email=info.get("email"))
