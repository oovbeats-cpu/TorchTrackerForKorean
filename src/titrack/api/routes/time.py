"""Time tracking API routes."""

from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Optional

from titrack.config.preferences import load_preferences, save_preferences


router = APIRouter(prefix="/api/time", tags=["time"])


class PauseSettingsModel(BaseModel):
    bag: bool = True
    pet: bool = True
    talent: bool = True
    settings: bool = True
    skill: bool = True
    auction: bool = True


class TimeState(BaseModel):
    total_play_state: str
    total_play_seconds: float
    mapping_play_state: str
    mapping_play_seconds: float
    auto_pause_on_inventory: bool
    surgery_count: int = 0
    avg_surgery_time_seconds: float = 0.0
    pause_settings: PauseSettingsModel = PauseSettingsModel()
    surgery_prep_start_ts: Optional[float] = None
    surgery_total_seconds: float = 0.0
    current_map_play_seconds: float = 0.0


class ToggleResponse(BaseModel):
    new_state: str
    total_play_seconds: float


class AutoPauseRequest(BaseModel):
    enabled: bool


@router.get("", response_model=TimeState)
def get_time_state(request: Request) -> TimeState:
    """Get current time tracking state."""
    time_tracker = getattr(request.app.state, "time_tracker", None)
    if not time_tracker:
        return TimeState(
            total_play_state="stopped",
            total_play_seconds=0,
            mapping_play_state="stopped",
            mapping_play_seconds=0,
            auto_pause_on_inventory=False,
            surgery_count=0,
            avg_surgery_time_seconds=0.0,
            pause_settings=PauseSettingsModel(),
            surgery_prep_start_ts=None,
            surgery_total_seconds=0.0,
        )
    
    state = time_tracker.get_state()
    ps = state.pause_settings
    surgery_prep_ts = None
    if state.surgery_prep_start_time:
        surgery_prep_ts = state.surgery_prep_start_time.timestamp()
    return TimeState(
        total_play_state=state.total_play_state.value,
        total_play_seconds=state.total_play_seconds,
        mapping_play_state=state.mapping_play_state.value,
        mapping_play_seconds=state.mapping_play_seconds,
        auto_pause_on_inventory=state.auto_pause_on_inventory,
        surgery_count=state.surgery_count,
        avg_surgery_time_seconds=state.avg_surgery_time_seconds,
        pause_settings=PauseSettingsModel(
            bag=ps.bag if ps else True,
            pet=ps.pet if ps else True,
            talent=ps.talent if ps else True,
            settings=ps.settings if ps else True,
            skill=ps.skill if ps else True,
            auction=ps.auction if ps else True,
        ),
        surgery_prep_start_ts=surgery_prep_ts,
        surgery_total_seconds=state.surgery_total_seconds,
        current_map_play_seconds=state.current_map_play_seconds,
    )


@router.post("/toggle", response_model=ToggleResponse)
def toggle_play(request: Request) -> ToggleResponse:
    """Toggle play/pause state for total play time."""
    time_tracker = getattr(request.app.state, "time_tracker", None)
    if not time_tracker:
        return ToggleResponse(new_state="stopped", total_play_seconds=0)
    
    new_state = time_tracker.toggle_total_play()
    return ToggleResponse(
        new_state=new_state.value,
        total_play_seconds=time_tracker.total_play_seconds,
    )


@router.post("/start")
def start_play(request: Request) -> dict:
    """Start total play time tracking."""
    time_tracker = getattr(request.app.state, "time_tracker", None)
    if time_tracker:
        time_tracker.start_total_play()
    return {"success": True}


@router.post("/stop")
def stop_play(request: Request) -> dict:
    """Stop total play time tracking."""
    time_tracker = getattr(request.app.state, "time_tracker", None)
    if time_tracker:
        time_tracker.stop_total_play()
    return {"success": True}


@router.post("/pause")
def pause_play(request: Request) -> dict:
    """Pause total play time tracking."""
    time_tracker = getattr(request.app.state, "time_tracker", None)
    if time_tracker:
        time_tracker.pause_total_play()
    return {"success": True}


@router.post("/resume")
def resume_play(request: Request) -> dict:
    """Resume total play time tracking."""
    time_tracker = getattr(request.app.state, "time_tracker", None)
    if time_tracker:
        time_tracker.resume_total_play()
    return {"success": True}


@router.post("/auto-pause", response_model=dict)
def set_auto_pause(request: Request, body: AutoPauseRequest) -> dict:
    """Enable/disable auto-pause on inventory open."""
    time_tracker = getattr(request.app.state, "time_tracker", None)
    if time_tracker:
        time_tracker.set_auto_pause_on_inventory(body.enabled)
    return {"success": True, "auto_pause_on_inventory": body.enabled}


@router.post("/pause-settings", response_model=dict)
def set_pause_settings(request: Request, body: PauseSettingsModel) -> dict:
    """Update which views trigger auto-pause."""
    time_tracker = getattr(request.app.state, "time_tracker", None)
    if time_tracker:
        time_tracker.set_pause_settings(
            bag=body.bag,
            pet=body.pet,
            talent=body.talent,
            settings=body.settings,
            skill=body.skill,
            auction=body.auction,
        )
    
    # Save to preferences file for persistence across restarts
    prefs = load_preferences()
    prefs.pause_bag = body.bag
    prefs.pause_pet = body.pet
    prefs.pause_talent = body.talent
    prefs.pause_settings = body.settings
    prefs.pause_skill = body.skill
    prefs.pause_auction = body.auction
    save_preferences(prefs)
    
    return {
        "success": True,
        "pause_settings": body.dict(),
    }


@router.post("/reset/mapping")
def reset_mapping_time(request: Request) -> dict:
    """Reset mapping time counter."""
    time_tracker = getattr(request.app.state, "time_tracker", None)
    if time_tracker:
        time_tracker.reset_mapping_time()
    return {"success": True}


@router.post("/reset/total")
def reset_total_time(request: Request) -> dict:
    """Reset total play time counter."""
    time_tracker = getattr(request.app.state, "time_tracker", None)
    if time_tracker:
        time_tracker.reset_total_time()
    return {"success": True}


@router.post("/reset/all")
def reset_all_time(request: Request) -> dict:
    """Reset all time counters."""
    time_tracker = getattr(request.app.state, "time_tracker", None)
    if time_tracker:
        time_tracker.reset_all()
    return {"success": True}
