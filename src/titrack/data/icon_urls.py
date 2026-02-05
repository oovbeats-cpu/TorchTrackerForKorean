"""Icon URL loader from tlidb items seed data."""

import json
import sys
from pathlib import Path
from typing import Optional

_icon_urls: dict[int, str] = {}
_loaded = False


def _get_base_path() -> Path:
    """Get base path for PyInstaller or normal execution."""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent


def _get_icons_path() -> Path:
    """Get path to icons data file."""
    base_path = _get_base_path()
    pyinstaller_path = base_path / "titrack" / "data" / "items_icons.json"
    if pyinstaller_path.exists():
        return pyinstaller_path
    return Path(__file__).parent / "items_icons.json"


def load_icon_urls() -> None:
    """Load icon URLs from JSON file."""
    global _icon_urls, _loaded
    
    if _loaded:
        return
        
    icons_path = _get_icons_path()
    if not icons_path.exists():
        _loaded = True
        return
        
    try:
        with open(icons_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        items = data.get("items", [])
        for item in items:
            try:
                config_id = int(item.get("id", 0))
                img_url = item.get("img", "")
                if config_id and img_url:
                    _icon_urls[config_id] = img_url
            except (ValueError, TypeError):
                continue
                
        _loaded = True
    except Exception as e:
        print(f"Error loading icon URLs: {e}")
        _loaded = True


def get_icon_url(config_base_id: int) -> Optional[str]:
    """Get icon URL for an item by config_base_id."""
    if not _loaded:
        load_icon_urls()
        
    return _icon_urls.get(config_base_id)


def get_all_icon_urls() -> dict[int, str]:
    """Get all icon URLs."""
    if not _loaded:
        load_icon_urls()
    return _icon_urls.copy()
