"""Overlay configuration API routes.

Provides GET/POST endpoints for the overlay subprocess to poll
and for the main window to update overlay settings.
"""

from typing import List, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/overlay", tags=["overlay"])

VALID_COLUMNS = [
    "profit", "run_time", "total_profit", "total_time",
    "map_hr", "total_hr", "run_count", "contract",
]

DEFAULT_CONFIG = {
    "opacity": 0.9,
    "scale": 1.0,
    "visible": True,
    "locked": True,
    "visible_columns": list(VALID_COLUMNS),
    "text_shadow": True,
    "bg_opacity": 0.7,
    "preset": 1,
}


class OverlayConfigUpdate(BaseModel):
    opacity: Optional[float] = None
    scale: Optional[float] = None
    visible: Optional[bool] = None
    locked: Optional[bool] = None
    visible_columns: Optional[List[str]] = None
    text_shadow: Optional[bool] = None
    bg_opacity: Optional[float] = None
    preset: Optional[int] = None


def _get_config(request: Request) -> dict:
    """Get or initialize overlay config from app state."""
    config = getattr(request.app.state, "overlay_config", None)
    if config is None:
        config = dict(DEFAULT_CONFIG)
        request.app.state.overlay_config = config
    # Ensure new fields exist (migration from older config)
    for key, default_val in DEFAULT_CONFIG.items():
        if key not in config:
            config[key] = default_val
    return config


@router.get("/config")
def get_overlay_config(request: Request) -> dict:
    """Get current overlay configuration."""
    return _get_config(request)


@router.post("/config")
def update_overlay_config(request: Request, updates: OverlayConfigUpdate) -> dict:
    """Update overlay configuration (partial updates supported)."""
    config = _get_config(request)

    if updates.opacity is not None:
        config["opacity"] = max(0.1, min(1.0, updates.opacity))
    if updates.scale is not None:
        config["scale"] = max(0.8, min(1.5, updates.scale))
    if updates.visible is not None:
        config["visible"] = updates.visible
    if updates.locked is not None:
        config["locked"] = updates.locked
    if updates.visible_columns is not None:
        config["visible_columns"] = [
            c for c in updates.visible_columns if c in VALID_COLUMNS
        ]
    if updates.text_shadow is not None:
        config["text_shadow"] = updates.text_shadow
    if updates.bg_opacity is not None:
        config["bg_opacity"] = max(0.0, min(1.0, updates.bg_opacity))
    if updates.preset is not None:
        config["preset"] = max(1, min(3, updates.preset))

    request.app.state.overlay_config = config
    return config
