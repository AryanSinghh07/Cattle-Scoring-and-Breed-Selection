"""``/analyze`` and ``/recompute``."""

from __future__ import annotations

import time
from typing import Literal

import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from gopalan_ml.analyze import analyze_photos, measure_and_score
from gopalan_ml.measure import rib_visibility

from .images import decode_image
from .models import ModelRegistry
from .schemas import AnalyzeResponse, RecomputeRequest, RecomputeResponse

router = APIRouter(tags=["analysis"])


def _read(upload: UploadFile | None, settings) -> np.ndarray | None:
    if upload is None:
        return None
    data = upload.file.read(settings.max_upload_bytes + 1)  # never read more than the limit
    return decode_image(data, settings.max_upload_bytes, settings.max_image_pixels)


@router.post("/analyze", response_model=AnalyzeResponse, summary="Analyse photos of one animal")
def analyze(
    request: Request,
    side: UploadFile = File(..., description="Side-view photo (required)"),
    top: UploadFile | None = File(None, description="Top-view photo (optional)"),
    back: UploadFile | None = File(None, description="Back-view photo (optional)"),
    marker_cm: float = Form(20.0, gt=1, le=200, description="Side length of the printed ArUco marker in cm"),
    facing: Literal["auto", "left", "right"] = Form("auto", description="Which way the animal faces in the side photo"),
):
    """Finds the animal, places body points, reads the marker, measures, scores
    BCS (beta) and predicts the breed. Problems with the photos (no animal, no
    marker) come back as `warnings`, not errors, so the app can guide the user."""
    t0 = time.perf_counter()
    settings = request.app.state.settings
    reg: ModelRegistry = request.app.state.registry
    if not reg.ready:
        raise HTTPException(503, detail={"error": "models_unavailable", "message": "The analysis model is not loaded yet; try again shortly."})

    side_img, top_img, back_img = (_read(f, settings) for f in (side, top, back))
    result = analyze_photos(reg.detector, side_img, top_img, back_img, marker_cm, facing)

    animal = result["views"]["side"].get("animal")
    breed = None
    if reg.breed is None:
        result["warnings"].append("Breed prediction is not available right now.")
    elif animal is None:
        result["warnings"].append("Breed not predicted: no animal found in the side photo.")
    else:
        box = animal["box"] if settings.breed_crop_to_animal else None
        breed = reg.breed.predict(side_img, box=box)

    analysis_id, expires = None, 0
    if result["views"]["side"].get("points"):
        analysis_id = request.app.state.photo_cache.put(side_img)
        expires = int(settings.cache_ttl_minutes * 60)

    return AnalyzeResponse(
        analysis_id=analysis_id,
        expires_in_seconds=expires,
        views=result["views"],
        measurements=result["measurements"],
        bcs=result["bcs"],
        breed=breed,
        warnings=result["warnings"],
        models=reg.health(),
        timing_ms=round((time.perf_counter() - t0) * 1000),
    )


@router.post("/recompute", response_model=RecomputeResponse, summary="Re-measure after the user moves points")
def recompute(request: Request, body: RecomputeRequest):
    """Recalculates measurements and BCS from adjusted points, without running
    detection again. With a valid `analysis_id`, rib visibility is re-checked on
    the photo (the rib box may have moved); otherwise `rib_visibility` is reused."""
    return compute_from_points(body, request.app.state.photo_cache)


def compute_from_points(body: RecomputeRequest, photo_cache) -> RecomputeResponse:
    """Measurements and BCS from (possibly user-adjusted) points. Shared by
    ``/recompute`` and saving, so stored results are always computed server-side."""
    warnings: list[str] = []
    points = {v: {k: p.model_dump() for k, p in pts.items()} for v, pts in body.points.items()}
    scales = {v: s for v, s in body.scales.items() if s is not None}

    rib, source = None, "none"
    cached = photo_cache.get(body.analysis_id) if body.analysis_id else None
    if cached is not None:
        f = cached.factor
        tl, br = points["side"]["rib_top_left"], points["side"]["rib_bottom_right"]
        rib = rib_visibility(cached.image, {"x": tl["x"] * f, "y": tl["y"] * f}, {"x": br["x"] * f, "y": br["y"] * f})
        source = "photo"
        if rib is None:
            warnings.append("Rib box is too small to judge rib visibility; drag the rib box corners apart.")
    else:
        if body.analysis_id:
            warnings.append("This analysis has expired, so ribs were not re-checked on the photo.")
        if body.rib_visibility is not None:
            rib, source = body.rib_visibility, "given"

    measurements, bcs, more = measure_and_score(points, scales, rib_visibility=rib)
    return RecomputeResponse(measurements=measurements, bcs=bcs, rib_source=source, warnings=warnings + more)
