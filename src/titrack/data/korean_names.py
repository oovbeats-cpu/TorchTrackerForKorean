"""Korean item name translations loader."""

import json
import sys
from pathlib import Path
from typing import Optional

_korean_names: dict[int, dict] = {}
_loaded = False


def _get_base_path() -> Path:
    """Get base path for PyInstaller or normal execution."""
    if getattr(sys, 'frozen', False):
        # Running in PyInstaller bundle
        return Path(sys._MEIPASS)
    return Path(__file__).parent


def _get_translations_path() -> Path:
    """Get path to Korean translations file."""
    base_path = _get_base_path()
    # Try PyInstaller path first
    pyinstaller_path = base_path / "titrack" / "data" / "items_ko.json"
    if pyinstaller_path.exists():
        return pyinstaller_path
    # Fallback to normal path
    return Path(__file__).parent / "items_ko.json"


def load_korean_names() -> None:
    """Load Korean item names from JSON file."""
    global _korean_names, _loaded
    
    if _loaded:
        return
        
    translations_path = _get_translations_path()
    if not translations_path.exists():
        _loaded = True
        return
        
    try:
        with open(translations_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        for config_id_str, item_data in data.items():
            try:
                config_id = int(config_id_str)
                _korean_names[config_id] = item_data
            except ValueError:
                continue
                
        _loaded = True
    except Exception as e:
        print(f"Error loading Korean translations: {e}")
        _loaded = True


def get_korean_name(config_base_id: int) -> Optional[str]:
    """Get Korean name for an item by config_base_id."""
    if not _loaded:
        load_korean_names()
        
    item_data = _korean_names.get(config_base_id)
    if item_data:
        return item_data.get("name")
    return None


def get_korean_item_data(config_base_id: int) -> Optional[dict]:
    """Get full Korean item data including name, type, price."""
    if not _loaded:
        load_korean_names()
        
    return _korean_names.get(config_base_id)


def get_all_korean_names() -> dict[int, dict]:
    """Get all Korean translations."""
    if not _loaded:
        load_korean_names()
    return _korean_names.copy()
