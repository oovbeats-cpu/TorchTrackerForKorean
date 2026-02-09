"""User preferences management - stored as JSON file."""

import json
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, asdict, field

from titrack.config.paths import get_data_dir


PREFS_FILENAME = "preferences.json"


@dataclass
class Preferences:
    """User preferences with defaults."""
    trade_tax_enabled: bool = True
    map_costs_enabled: bool = True
    cloud_sync_enabled: bool = False
    pause_bag: bool = True
    pause_pet: bool = True
    pause_talent: bool = True
    pause_settings: bool = True
    pause_skill: bool = True
    pause_auction: bool = True
    cloud_auto_refresh: bool = True
    cloud_midnight_refresh: bool = True
    cloud_exchange_override: bool = True
    cloud_startup_refresh: bool = True
    high_run_threshold: float = 100.0  # 하이런 최소 결정 수량 (FE)
    log_directory: Optional[str] = None


def get_prefs_path() -> Path:
    """Get the path to the preferences file."""
    return get_data_dir() / PREFS_FILENAME


def load_preferences() -> Preferences:
    """Load preferences from file, returning defaults if not found."""
    prefs_path = get_prefs_path()
    
    if prefs_path.exists():
        try:
            with open(prefs_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Preferences(
                trade_tax_enabled=data.get("trade_tax_enabled", True),
                map_costs_enabled=data.get("map_costs_enabled", True),
                cloud_sync_enabled=data.get("cloud_sync_enabled", False),
                pause_bag=data.get("pause_bag", True),
                pause_pet=data.get("pause_pet", True),
                pause_talent=data.get("pause_talent", True),
                pause_settings=data.get("pause_settings", True),
                pause_skill=data.get("pause_skill", True),
                pause_auction=data.get("pause_auction", True),
                cloud_auto_refresh=data.get("cloud_auto_refresh", True),
                cloud_midnight_refresh=data.get("cloud_midnight_refresh", True),
                cloud_exchange_override=data.get("cloud_exchange_override", True),
                cloud_startup_refresh=data.get("cloud_startup_refresh", True),
                high_run_threshold=float(data.get("high_run_threshold", 100.0)),
                log_directory=data.get("log_directory"),
            )
        except (json.JSONDecodeError, IOError):
            pass
    
    return Preferences()


def save_preferences(prefs: Preferences) -> bool:
    """Save preferences to file."""
    prefs_path = get_prefs_path()
    
    try:
        prefs_path.parent.mkdir(parents=True, exist_ok=True)
        with open(prefs_path, "w", encoding="utf-8") as f:
            json.dump(asdict(prefs), f, indent=2, ensure_ascii=False)
        return True
    except IOError:
        return False


def update_preference(key: str, value: Any) -> bool:
    """Update a single preference and save."""
    prefs = load_preferences()
    
    if hasattr(prefs, key):
        setattr(prefs, key, value)
        return save_preferences(prefs)
    
    return False


def get_preference(key: str, default: Any = None) -> Any:
    """Get a single preference value."""
    prefs = load_preferences()
    return getattr(prefs, key, default)
