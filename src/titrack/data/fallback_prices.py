"""Fallback prices loader - loads user-provided price data for items not in cloud."""

import json
import re
import sys
from pathlib import Path
from typing import Optional

_fallback_prices: dict[int, float] = {}
_fallback_names: dict[int, str] = {}
_loaded = False


def _get_base_path() -> Path:
    """Get base path for PyInstaller or normal execution."""
    if getattr(sys, 'frozen', False):
        # Running in PyInstaller bundle
        return Path(sys._MEIPASS)
    return Path(__file__).parent


def load_fallback_prices(filepath: Optional[str] = None) -> int:
    """
    Load fallback prices from user-provided JSON file.
    
    The file format is expected to be:
    {
        "config_base_id": { "name": "...", "price": 123.45, ... },
        ...
    }
    
    Search paths:
    1. User-provided filepath
    2. ~/.titrack/fallback_prices.json (user data directory)
    3. ~/.titrack/prices.json
    4. attached_assets/*.txt (development)
    5. Current directory fallback_prices.json
    
    Returns the number of prices loaded.
    """
    global _fallback_prices, _fallback_names, _loaded
    
    if filepath is None:
        user_data_dir = Path.home() / ".titrack"
        base_path = _get_base_path()
        default_paths = [
            user_data_dir / "fallback_prices.json",
            user_data_dir / "prices.json",
            base_path / "titrack" / "data" / "items_ko.json",
            base_path / "items_ko.json",
            Path(__file__).parent / "items_ko.json",
            Path("attached_assets/full_table_1770098221535.json"),
            Path("attached_assets/20260203_1770098236610.txt"),
            Path("attached_assets/20260203_1770094460787.txt"),
            Path("data/fallback_prices.json"),
            Path("fallback_prices.json"),
        ]
        for p in default_paths:
            if p.exists():
                filepath = str(p)
                break
    
    if filepath is None or not Path(filepath).exists():
        _loaded = True
        return 0
    
    try:
        content = Path(filepath).read_text(encoding="utf-8")
        content = content.strip()
        if not content.startswith("{"):
            content = "{" + content
        if not content.endswith("}"):
            content = content + "}"
        content = re.sub(r",(\s*[}\]])", r"\1", content)
        
        data = json.loads(content)
        
        count = 0
        for config_id_str, item_data in data.items():
            try:
                config_id = int(config_id_str)
                price = item_data.get("price", 0)
                if price is None:
                    price = 0
                _fallback_prices[config_id] = float(price)
                
                name = item_data.get("name", "")
                if name:
                    _fallback_names[config_id] = name
                count += 1
            except (ValueError, TypeError, AttributeError):
                continue
        
        _loaded = True
        return count
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Failed to load fallback prices from {filepath}: {e}")
        _loaded = True
        return 0


def get_fallback_price(config_base_id: int) -> Optional[float]:
    """Get fallback price for an item, or None if not available."""
    global _loaded
    if not _loaded:
        load_fallback_prices()
    
    price = _fallback_prices.get(config_base_id)
    if price is not None and price > 0:
        return price
    return None


def get_fallback_name(config_base_id: int) -> Optional[str]:
    """Get fallback Korean name for an item."""
    global _loaded
    if not _loaded:
        load_fallback_prices()
    
    return _fallback_names.get(config_base_id)


def get_all_fallback_prices() -> dict[int, float]:
    """Get all loaded fallback prices."""
    global _loaded
    if not _loaded:
        load_fallback_prices()
    return _fallback_prices.copy()


def get_fallback_count() -> int:
    """Get number of fallback prices loaded."""
    global _loaded
    if not _loaded:
        load_fallback_prices()
    return len(_fallback_prices)


def is_loaded() -> bool:
    """Check if fallback prices have been loaded."""
    return _loaded
