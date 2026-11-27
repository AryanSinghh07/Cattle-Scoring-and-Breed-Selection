"""Saved data: animals, analyses and history (signed-in users only).

All database and storage calls run with the user's own token, so the
database security rules decide what each user may read or write.
"""

from __future__ import annotations

import io
import json
import uuid
from datetime import date
from typing import Any, Literal

import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.security import HTTPAuthorizationCredentials
from PIL import Image
from pydantic import BaseModel, Field, ValidationError, field_validator

from gopalan_ml.breed_data import BREEDS

from .analysis import _read, compute_from_points
from .auth import User, bearer, current_user, get_supabase
from .schemas import RecomputeRequest
from .supabase import Supabase, SupabaseError

router = APIRouter(tags=["saved data"])

HISTORY_FIELDS = ("id,created_at,animal_id,bcs_score,bcs_confidence,breed_slug,breed_confidence,"
                  "breed_unsure,measurements,photo_consent")


def signed_in(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> User:
    return current_user(request, creds)


def _fail(e: SupabaseError) -> HTTPException:
    messages = {
        403: ("not_allowed", "You can only use your own animals and analyses."),
        409: ("duplicate", "An animal with this tag already exists."),
        422: ("invalid_data", str(e)),
    }
    error, message = messages.get(e.status, ("storage_error", "Saving failed; please try again."))
    status = e.status if e.status in messages or e.status == 401 else 502
    return HTTPException(status, detail={"error": error, "message": message})


def _check_breed(slug: str | None) -> str | None:
    if slug is not None and slug not in BREEDS:
        raise ValueError(f"Unknown breed '{slug}'")
    return slug


# ---------------------------------------------------------------------------- animals


class AnimalIn(BaseModel):
    species: Literal["cow", "buffalo"]
    name: str | None = Field(None, max_length=80)
    tag_id: str | None = Field(None, max_length=40)
    breed_slug: str | None = None
    sex: Literal["female", "male", "unknown"] = "unknown"
    birth_date: date | None = None
    notes: str | None = Field(None, max_length=1000)

    _breed = field_validator("breed_slug")(_check_breed)


class AnimalUpdate(BaseModel):
    species: Literal["cow", "buffalo"] | None = None
    name: str | None = Field(None, max_length=80)
    tag_id: str | None = Field(None, max_length=40)
    breed_slug: str | None = None
    sex: Literal["female", "male", "unknown"] | None = None
    birth_date: date | None = None
    notes: str | None = Field(None, max_length=1000)

    _breed = field_validator("breed_slug")(_check_breed)


@router.post("/animals", status_code=201, summary="Add an animal")
def create_animal(body: AnimalIn, user: User = Depends(signed_in), sb: Supabase = Depends(get_supabase)):
    try:
        return sb.insert(user.token, "animals", body.model_dump(mode="json"))
    except SupabaseError as e:
        raise _fail(e) from None


@router.get("/animals", summary="List my animals")
def list_animals(user: User = Depends(signed_in), sb: Supabase = Depends(get_supabase)):
    try:
        return sb.select(user.token, "animals", {"select": "*", "order": "created_at.desc"})
    except SupabaseError as e:
        raise _fail(e) from None


def _get_one(sb: Supabase, token: str, table: str, row_id: uuid.UUID, what: str) -> dict:
    try:
        rows = sb.select(token, table, {"select": "*", "id": f"eq.{row_id}"})
    except SupabaseError as e:
        raise _fail(e) from None
    if not rows:  # missing, or someone else's: the database hides both the same way
        raise HTTPException(404, detail={"error": "not_found", "message": f"{what} not found."})
    return rows[0]


@router.get("/animals/{animal_id}", summary="Get one of my animals")
def get_animal(animal_id: uuid.UUID, user: User = Depends(signed_in), sb: Supabase = Depends(get_supabase)):
    return _get_one(sb, user.token, "animals", animal_id, "Animal")


@router.patch("/animals/{animal_id}", summary="Update one of my animals")
def update_animal(animal_id: uuid.UUID, body: AnimalUpdate, user: User = Depends(signed_in),
                  sb: Supabase = Depends(get_supabase)):
    values = body.model_dump(mode="json", exclude_unset=True)
    if not values:
        return _get_one(sb, user.token, "animals", animal_id, "Animal")
    try:
        rows = sb.update(user.token, "animals", {"id": str(animal_id)}, values)
    except SupabaseError as e:
        raise _fail(e) from None
    if not rows:
        raise HTTPException(404, detail={"error": "not_found", "message": "Animal not found."})
    return rows[0]


@router.get("/animals/{animal_id}/analyses", summary="History of one animal")
def animal_history(animal_id: uuid.UUID, limit: int = Query(50, ge=1, le=200), user: User = Depends(signed_in),
                   sb: Supabase = Depends(get_supabase)):
    _get_one(sb, user.token, "animals", animal_id, "Animal")
    try:
        return sb.select(user.token, "analyses", {"select": HISTORY_FIELDS, "animal_id": f"eq.{animal_id}",
                                                  "order": "created_at.desc", "limit": str(limit)})
    except SupabaseError as e:
        raise _fail(e) from None


# --------------------------------------------------------------------------- analyses


class BreedIn(BaseModel):
    breed: str = Field(description="Breed slug, or 'unsure'")
    confidence: float = Field(ge=0, le=1)
    unsure: bool = False
    top: list[dict[str, Any]] = Field(default_factory=list, max_length=5)

    @field_validator("breed")
    @classmethod
    def known(cls, v: str) -> str:
        return v if v == "unsure" else _check_breed(v)


class SaveAnalysisRequest(RecomputeRequest):
    animal_id: uuid.UUID | None = None
    photo_consent: bool = Field(False, description="Store the photos and allow them to improve Gopalan AI")
    breed: BreedIn | None = None


def _jpeg(image: np.ndarray, max_side: int) -> bytes:
    """Re-encode as JPEG: smaller files and no hidden metadata (EXIF, GPS)."""
    im = Image.fromarray(image)
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90)
    return buf.getvalue()


@router.post("/analyses", status_code=201, summary="Save an analysis")
def save_analysis(
    request: Request,
    data: str = Form(..., description="JSON: points, scales, analysis_id, animal_id, photo_consent, breed"),
    side: UploadFile | None = File(None, description="Side photo (stored only with photo_consent)"),
    top: UploadFile | None = File(None),
    back: UploadFile | None = File(None),
    user: User = Depends(signed_in),
    sb: Supabase = Depends(get_supabase),
):
    """Saves the final (possibly user-adjusted) points. Measurements and BCS are
    **recomputed on the server** from those points. Photos are stored only when
    `photo_consent` is true."""
    try:
        body = SaveAnalysisRequest.model_validate_json(data)
    except ValidationError as e:
        raise HTTPException(422, detail={"error": "invalid_request", "message": "The analysis data is not valid.",
                                         "details": json.loads(e.json(include_url=False))}) from None

    settings = request.app.state.settings
    computed = compute_from_points(body, request.app.state.photo_cache)
    warnings = list(computed.warnings)
    analysis_id = str(uuid.uuid4())

    files = {"side": side, "top": top, "back": back}
    photos: dict[str, str] = {}
    if body.photo_consent:
        for view, f in files.items():
            if f is None:
                continue
            path = f"{user.id}/{analysis_id}/{view}.jpg"
            try:
                sb.upload(user.token, settings.photo_bucket, path, _jpeg(_read(f, settings), settings.photo_max_side),
                          "image/jpeg")
            except SupabaseError as e:
                _cleanup(sb, user, settings.photo_bucket, list(photos.values()))
                raise _fail(e) from None
            photos[view] = path
    elif any(f is not None for f in files.values()):
        warnings.append("Photos were not stored because photo consent was not given.")

    bcs = computed.bcs or {}
    breed = body.breed
    row = {
        "id": analysis_id,
        "animal_id": str(body.animal_id) if body.animal_id else None,
        "photo_consent": body.photo_consent,
        "photos": photos,
        "points": {v: {k: p.model_dump() for k, p in pts.items()} for v, pts in body.points.items()},
        "marker": {v: s for v, s in body.scales.items() if s is not None},
        "measurements": computed.measurements,
        "bcs": computed.bcs,
        "bcs_score": bcs.get("score"),
        "bcs_confidence": bcs.get("confidence"),
        "breed": breed.model_dump() if breed else None,
        "breed_slug": None if breed is None or breed.breed == "unsure" else breed.breed,
        "breed_confidence": breed.confidence if breed else None,
        "breed_unsure": (breed.unsure or breed.breed == "unsure") if breed else None,
        "model_versions": request.app.state.registry.health(),
    }
    try:
        saved = sb.insert(user.token, "analyses", row)
    except SupabaseError as e:
        _cleanup(sb, user, settings.photo_bucket, list(photos.values()))
        raise _fail(e) from None
    return {"analysis": saved, "warnings": warnings}


def _cleanup(sb: Supabase, user: User, bucket: str, paths: list[str]) -> None:
    if paths:
        try:
            sb.remove(user.token, bucket, paths)
        except SupabaseError:
            pass  # best effort; the user can't see orphaned files anyway


@router.get("/analyses", summary="My recent analyses")
def list_analyses(limit: int = Query(50, ge=1, le=200), user: User = Depends(signed_in),
                  sb: Supabase = Depends(get_supabase)):
    try:
        return sb.select(user.token, "analyses", {"select": HISTORY_FIELDS, "order": "created_at.desc",
                                                  "limit": str(limit)})
    except SupabaseError as e:
        raise _fail(e) from None


@router.get("/analyses/{analysis_id}", summary="One saved analysis, with temporary photo links")
def get_analysis(analysis_id: uuid.UUID, request: Request, user: User = Depends(signed_in),
                 sb: Supabase = Depends(get_supabase)):
    row = _get_one(sb, user.token, "analyses", analysis_id, "Analysis")
    settings = request.app.state.settings
    urls = {}
    for view, path in (row.get("photos") or {}).items():
        try:
            urls[view] = sb.signed_url(user.token, settings.photo_bucket, path, settings.signed_url_seconds)
        except SupabaseError:
            pass
    return {**row, "photo_urls": urls}
