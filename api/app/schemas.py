"""Request and response shapes (also shown in /docs)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from gopalan_ml.keypoints import BACK_POINTS, SIDE_POINTS, TOP_POINTS

View = Literal["side", "top", "back"]
REQUIRED_POINTS: dict[str, tuple[str, ...]] = {"side": SIDE_POINTS, "top": TOP_POINTS, "back": BACK_POINTS}


class Point(BaseModel):
    x: float
    y: float
    confidence: float = Field(1.0, ge=0, le=1, description="1.0 for points the user placed or confirmed")


class AnalyzeResponse(BaseModel):
    analysis_id: str | None = Field(None, description="Pass to /recompute to re-check ribs after moving points")
    expires_in_seconds: int = 0
    views: dict[str, dict[str, Any]] = Field(description="Per photo: animal, outline, facing, points, marker, warnings")
    measurements: dict[str, Any] | None = None
    bcs: dict[str, Any] | None = Field(None, description="Body condition score (beta), 1-5 in 0.25 steps")
    breed: dict[str, Any] | None = Field(None, description="Breed, or 'unsure' with the top guesses")
    warnings: list[str] = []
    models: dict[str, Any] = {}
    timing_ms: int = 0


class RecomputeRequest(BaseModel):
    analysis_id: str | None = Field(None, description="From /analyze; lets the server re-check ribs on the photo")
    points: dict[View, dict[str, Point]] = Field(description="Body points per view, in original photo pixels")
    scales: dict[View, float | None] = Field(default_factory=dict, description="cm per pixel per view (marker.cm_per_px)")
    rib_visibility: float | None = Field(None, ge=0, le=1, description="Used when the photo is no longer available")

    @model_validator(mode="after")
    def check_points(self) -> "RecomputeRequest":
        if "side" not in self.points:
            raise ValueError("points.side is required")
        for view, pts in self.points.items():
            missing = [p for p in REQUIRED_POINTS[view] if p not in pts]
            if missing:
                raise ValueError(f"points.{view} is missing: {', '.join(missing)}")
        for view, s in self.scales.items():
            if s is not None and s <= 0:
                raise ValueError(f"scales.{view} must be positive")
        return self


class RecomputeResponse(BaseModel):
    measurements: dict[str, Any]
    bcs: dict[str, Any] | None
    rib_source: Literal["photo", "given", "none"]
    warnings: list[str] = []
