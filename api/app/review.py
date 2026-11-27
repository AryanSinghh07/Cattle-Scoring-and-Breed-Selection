"""Review: reviewers confirm or correct BCS and breed.

These checks are the "human" part of the semi-automatic system, and the
confirmed/corrected values become the training labels for the real BCS model
in v3. Only users with the ``reviewer`` or ``admin`` role can use these
endpoints; the database enforces the same rule.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator

from .auth import User, get_supabase
from .records import _check_breed, _fail, _get_one, signed_in
from .supabase import Supabase, SupabaseError

router = APIRouter(prefix="/review", tags=["review"])

QUEUE_FIELDS = ("id", "created_at", "bcs_score", "bcs_confidence", "breed_slug", "breed_confidence",
                "breed_unsure", "measurements", "photos")
EXPORT_SELECT = ("id,decision,bcs_score,breed_slug,notes,created_at,updated_at,reviewer_id,"
                 "analysis:analyses(id,created_at,photos,points,marker,measurements,bcs_score,bcs_confidence,"
                 "breed_slug,breed_confidence,breed_unsure,model_versions)")


def reviewer(user: User = Depends(signed_in), sb: Supabase = Depends(get_supabase)) -> User:
    try:
        rows = sb.select(user.token, "profiles", {"select": "role", "id": f"eq.{user.id}"})
    except SupabaseError as e:
        raise _fail(e) from None
    if not rows or rows[0].get("role") not in ("reviewer", "admin"):
        raise HTTPException(403, detail={"error": "not_reviewer",
                                         "message": "Only reviewers and admins can review results."})
    return user


def _photo_urls(sb: Supabase, user: User, request: Request, photos: dict | None) -> dict[str, str]:
    settings = request.app.state.settings
    urls = {}
    for view, path in (photos or {}).items():
        try:
            urls[view] = sb.signed_url(user.token, settings.photo_bucket, path, settings.signed_url_seconds)
        except SupabaseError:
            pass
    return urls


@router.get("/queue", summary="Results waiting for review, least confident first")
def queue(request: Request, limit: int = Query(20, ge=1, le=100), user: User = Depends(reviewer),
          sb: Supabase = Depends(get_supabase)):
    try:
        items = sb.rpc(user.token, "review_queue", {"p_limit": limit})
        waiting = sb.rpc(user.token, "review_queue_size")
    except SupabaseError as e:
        raise _fail(e) from None
    return {
        "waiting": waiting,
        "items": [{**{k: it.get(k) for k in QUEUE_FIELDS}, "photo_urls": _photo_urls(sb, user, request, it.get("photos"))}
                  for it in items],
    }


def _my_review(sb: Supabase, user: User, analysis_id: uuid.UUID) -> dict | None:
    try:
        rows = sb.select(user.token, "reviews", {"select": "*", "analysis_id": f"eq.{analysis_id}",
                                                 "reviewer_id": f"eq.{user.id}"})
    except SupabaseError as e:
        raise _fail(e) from None
    return rows[0] if rows else None


@router.get("/{analysis_id}", summary="One result to review, with photos and my review")
def get_item(analysis_id: uuid.UUID, request: Request, user: User = Depends(reviewer),
             sb: Supabase = Depends(get_supabase)):
    row = _get_one(sb, user.token, "analyses", analysis_id, "Analysis")
    return {**row, "photo_urls": _photo_urls(sb, user, request, row.get("photos")),
            "my_review": _my_review(sb, user, analysis_id)}


class ReviewIn(BaseModel):
    decision: Literal["confirmed", "corrected"]
    bcs_score: float | None = Field(None, ge=1, le=5, description="1–5 in 0.25 steps")
    breed_slug: str | None = None
    notes: str | None = Field(None, max_length=2000)

    @field_validator("bcs_score")
    @classmethod
    def quarter_steps(cls, v: float | None) -> float | None:
        if v is not None and (v * 4) != int(v * 4):
            raise ValueError("BCS must be in 0.25 steps (e.g. 2.75, 3.0, 3.25)")
        return v

    _breed = field_validator("breed_slug")(_check_breed)


@router.put("/{analysis_id}", summary="Confirm or correct a result")
def submit(analysis_id: uuid.UUID, body: ReviewIn, user: User = Depends(reviewer),
           sb: Supabase = Depends(get_supabase)):
    """`confirmed` keeps the model's BCS and breed (they're filled in for you).
    `corrected` needs a different BCS and/or breed. Submitting again updates
    your earlier review."""
    analysis = _get_one(sb, user.token, "analyses", analysis_id, "Analysis")
    model_bcs = analysis.get("bcs_score")
    model_breed = analysis.get("breed_slug")
    bcs, breed = body.bcs_score, body.breed_slug

    if body.decision == "confirmed":
        if (bcs is not None and model_bcs is not None and float(bcs) != float(model_bcs)) or \
                (breed is not None and breed != model_breed):
            raise HTTPException(422, detail={"error": "invalid_review",
                                             "message": "Values differ from the model's; use decision 'corrected'."})
        bcs = model_bcs if bcs is None else bcs
        breed = model_breed if breed is None else breed
    else:
        changed_bcs = bcs is not None and (model_bcs is None or float(bcs) != float(model_bcs))
        changed_breed = breed is not None and breed != model_breed
        if not (changed_bcs or changed_breed):
            raise HTTPException(422, detail={"error": "invalid_review",
                                             "message": "A correction needs a different BCS or breed."})
        bcs = bcs if bcs is not None else model_bcs
        breed = breed if breed is not None else model_breed

    values = {"decision": body.decision, "bcs_score": bcs, "breed_slug": breed, "notes": body.notes}
    existing = _my_review(sb, user, analysis_id)
    try:
        if existing:
            return sb.update(user.token, "reviews", {"id": existing["id"]}, values)[0]
        return sb.insert(user.token, "reviews", {"analysis_id": str(analysis_id), **values})
    except SupabaseError as e:
        raise _fail(e) from None


def export_rows(reviews: list[dict]) -> list[dict]:
    """Flatten reviews into training records: model output vs. human label."""
    out = []
    for r in reviews:
        a = r.get("analysis") or {}
        if not a:
            continue
        out.append({
            "analysis_id": a["id"],
            "analysed_at": a.get("created_at"),
            "reviewed_at": r.get("updated_at") or r.get("created_at"),
            "reviewer_id": r.get("reviewer_id"),
            "decision": r["decision"],
            "label_bcs": r.get("bcs_score"),
            "label_breed": r.get("breed_slug"),
            "model_bcs": a.get("bcs_score"),
            "model_bcs_confidence": a.get("bcs_confidence"),
            "model_breed": a.get("breed_slug"),
            "model_breed_confidence": a.get("breed_confidence"),
            "photos": a.get("photos") or {},
            "points": a.get("points"),
            "marker": a.get("marker"),
            "measurements": a.get("measurements"),
            "model_versions": a.get("model_versions"),
            "notes": r.get("notes"),
        })
    return out


@router.get("/export/labels", summary="Download reviewed results as training data")
def export(format: Literal["jsonl", "csv"] = "jsonl", user: User = Depends(reviewer),
           sb: Supabase = Depends(get_supabase)):
    """Reviewers get their own reviews; admins get everyone's. Photos are
    listed as storage paths (download them with a signed-in session)."""
    try:
        reviews = sb.select(user.token, "reviews", {"select": EXPORT_SELECT, "order": "created_at.asc"})
    except SupabaseError as e:
        raise _fail(e) from None
    rows = export_rows(reviews)
    if format == "jsonl":
        body = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
        return Response(body, media_type="application/x-ndjson",
                        headers={"Content-Disposition": 'attachment; filename="gopalan_review_labels.jsonl"'})
    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0]))
        writer.writeheader()
        for r in rows:
            writer.writerow({k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in r.items()})
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="gopalan_review_labels.csv"'})
