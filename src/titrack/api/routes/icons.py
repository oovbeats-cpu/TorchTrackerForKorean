"""Icon proxy routes - fetches icons from CDN with proper headers."""

import urllib.request
import urllib.error
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from titrack.api.dependencies import get_repository
from titrack.db.repository import Repository
from titrack.data.icon_urls import get_icon_url

router = APIRouter(prefix="/api/icons", tags=["icons"])

_icon_cache: dict[str, bytes] = {}
_failed_urls: set[str] = set()

ALLOWED_DOMAINS = {"tlidb.com", "www.tlidb.com", "cdn.tlidb.com"}
MAX_ICON_SIZE = 1024 * 1024  # 1MB
ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}

IMAGE_MAGIC_BYTES = {
    b'\x89PNG\r\n\x1a\n': "image/png",
    b'\xff\xd8\xff': "image/jpeg",
    b'RIFF': "image/webp",
    b'GIF87a': "image/gif",
    b'GIF89a': "image/gif",
}

CDN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://tlidb.com/",
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
}


def _is_valid_domain(url: str) -> bool:
    """Check if URL is from allowed domain."""
    try:
        parsed = urlparse(url)
        return parsed.hostname in ALLOWED_DOMAINS
    except Exception:
        return False


def _is_valid_image(data: bytes) -> bool:
    """Verify image by checking magic bytes."""
    if not data or len(data) < 8:
        return False
    for magic in IMAGE_MAGIC_BYTES:
        if data.startswith(magic):
            return True
    return False


def _fetch_icon(url: str) -> Optional[bytes]:
    """Fetch icon from CDN with security validation."""
    if url in _failed_urls:
        return None

    if url in _icon_cache:
        return _icon_cache[url]

    if not _is_valid_domain(url):
        _failed_urls.add(url)
        return None

    try:
        req = urllib.request.Request(url, headers=CDN_HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            content_type = resp.headers.get("Content-Type", "").split(";")[0].strip()
            if content_type and content_type not in ALLOWED_CONTENT_TYPES:
                _failed_urls.add(url)
                return None

            content_length = resp.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_ICON_SIZE:
                _failed_urls.add(url)
                return None

            data = resp.read(MAX_ICON_SIZE + 1)
            if len(data) > MAX_ICON_SIZE:
                _failed_urls.add(url)
                return None

            if not _is_valid_image(data):
                _failed_urls.add(url)
                return None

            _icon_cache[url] = data
            return data
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
        _failed_urls.add(url)
        return None


@router.get("/{config_base_id}")
def get_icon(config_base_id: int, repo: Repository = Depends(get_repository)) -> Response:
    """
    Proxy icon for an item.

    Fetches the icon from the CDN with proper headers and caches it.
    Returns 404 if no icon URL exists or the CDN returns an error.
    """
    icon_url = None
    
    item = repo.get_item(config_base_id)
    if item and item.icon_url:
        icon_url = item.icon_url
    
    if not icon_url:
        icon_url = get_icon_url(config_base_id)
    
    if not icon_url:
        raise HTTPException(status_code=404, detail="No icon available")

    icon_data = _fetch_icon(icon_url)
    if icon_data is None:
        raise HTTPException(status_code=404, detail="Icon not available from CDN")

    content_type = "image/webp"
    if icon_url.endswith(".png"):
        content_type = "image/png"
    elif icon_url.endswith(".jpg") or icon_url.endswith(".jpeg"):
        content_type = "image/jpeg"

    return FastAPIResponse(
        content=icon_data,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=86400",
        },
    )
