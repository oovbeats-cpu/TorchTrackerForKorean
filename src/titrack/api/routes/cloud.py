"""Cloud sync API routes."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from titrack.api.dependencies import get_repository
from titrack.db.repository import Repository
from titrack.sync.manager import SyncManager, SyncStatus

router = APIRouter(prefix="/api/cloud", tags=["cloud"])


def _get_sync_manager(request: Request) -> Optional[SyncManager]:
    """Get sync manager from app state."""
    return getattr(request.app.state, "sync_manager", None)


class CloudStatusResponse(BaseModel):
    """Cloud sync status information."""

    status: str
    enabled: bool
    upload_enabled: bool
    download_enabled: bool
    queue_pending: int
    queue_failed: int
    last_upload: Optional[str] = None
    last_download: Optional[str] = None
    last_error: Optional[str] = None
    cloud_available: bool


class CloudToggleRequest(BaseModel):
    """Request to enable/disable cloud sync."""

    enabled: bool


class CloudToggleResponse(BaseModel):
    """Response for toggle operation."""

    success: bool
    enabled: bool
    error: Optional[str] = None


class CloudSyncResponse(BaseModel):
    """Response for manual sync trigger."""

    success: bool
    uploaded: int = 0
    downloaded: int = 0
    error: Optional[str] = None


class CloudPriceResponse(BaseModel):
    """A single cloud price entry."""

    config_base_id: int
    season_id: int
    price_fe_median: float
    price_fe_p10: Optional[float] = None
    price_fe_p90: Optional[float] = None
    submission_count: Optional[int] = None
    unique_devices: Optional[int] = None
    cloud_updated_at: Optional[str] = None
    cached_at: Optional[str] = None


class CloudPriceListResponse(BaseModel):
    """List of cloud prices."""

    prices: list[CloudPriceResponse]
    total: int


class PriceHistoryPoint(BaseModel):
    """A single price history point."""

    hour_bucket: str
    price_fe_median: float
    price_fe_p10: Optional[float] = None
    price_fe_p90: Optional[float] = None
    submission_count: Optional[int] = None


class CloudPriceHistoryResponse(BaseModel):
    """Price history for an item."""

    config_base_id: int
    season_id: int
    history: list[PriceHistoryPoint]


class ItemsSyncResponse(BaseModel):
    """Response for items sync operation."""

    success: bool
    synced_count: int = 0
    last_sync: Optional[str] = None
    error: Optional[str] = None


class ItemsLastSyncResponse(BaseModel):
    """Response for items last sync query."""

    last_sync: Optional[str] = None
    total_items: int = 0


@router.get("/status", response_model=CloudStatusResponse)
def get_cloud_status(
    request: Request,
    repo: Repository = Depends(get_repository),
) -> CloudStatusResponse:
    """Get current cloud sync status."""
    sync_manager = _get_sync_manager(request)

    if sync_manager is None:
        # No sync manager - return disabled status
        return CloudStatusResponse(
            status="disabled",
            enabled=False,
            upload_enabled=True,
            download_enabled=True,
            queue_pending=0,
            queue_failed=0,
            cloud_available=False,
        )

    info = sync_manager.get_status_info()

    return CloudStatusResponse(
        status=info.status.value,
        enabled=info.enabled,
        upload_enabled=info.upload_enabled,
        download_enabled=info.download_enabled,
        queue_pending=info.queue_pending,
        queue_failed=info.queue_failed,
        last_upload=info.last_upload.isoformat() if info.last_upload else None,
        last_download=info.last_download.isoformat() if info.last_download else None,
        last_error=info.last_error,
        cloud_available=info.cloud_available,
    )


@router.post("/toggle", response_model=CloudToggleResponse)
def toggle_cloud_sync(
    request_body: CloudToggleRequest,
    request: Request,
    repo: Repository = Depends(get_repository),
) -> CloudToggleResponse:
    """Enable or disable cloud sync."""
    sync_manager = _get_sync_manager(request)

    if sync_manager is None:
        return CloudToggleResponse(
            success=False,
            enabled=False,
            error="Cloud sync not available",
        )

    if request_body.enabled:
        success = sync_manager.enable()
        if not success:
            return CloudToggleResponse(
                success=False,
                enabled=False,
                error=sync_manager.get_status_info().last_error or "Failed to enable",
            )
        return CloudToggleResponse(success=True, enabled=True)
    else:
        sync_manager.disable()
        return CloudToggleResponse(success=True, enabled=False)


@router.post("/sync", response_model=CloudSyncResponse)
def trigger_sync(
    request: Request,
    repo: Repository = Depends(get_repository),
) -> CloudSyncResponse:
    """Trigger an immediate sync."""
    sync_manager = _get_sync_manager(request)

    if sync_manager is None:
        return CloudSyncResponse(success=False, error="Cloud sync not available")

    if not sync_manager.is_enabled:
        return CloudSyncResponse(success=False, error="Cloud sync not enabled")

    result = sync_manager.trigger_sync()

    return CloudSyncResponse(
        success=result.get("success", False),
        uploaded=result.get("uploaded", 0),
        downloaded=result.get("downloaded", 0),
        error=result.get("error"),
    )


@router.get("/prices", response_model=CloudPriceListResponse)
def get_cloud_prices(
    request: Request,
    repo: Repository = Depends(get_repository),
) -> CloudPriceListResponse:
    """Get cached cloud prices."""
    sync_manager = _get_sync_manager(request)

    if sync_manager is None:
        return CloudPriceListResponse(prices=[], total=0)

    # Get season from repository context
    season_id = repo._current_season_id

    prices = sync_manager.get_cached_cloud_prices(season_id)

    return CloudPriceListResponse(
        prices=[
            CloudPriceResponse(
                config_base_id=p["config_base_id"],
                season_id=p["season_id"],
                price_fe_median=p["price_fe_median"],
                price_fe_p10=p.get("price_fe_p10"),
                price_fe_p90=p.get("price_fe_p90"),
                submission_count=p.get("submission_count"),
                unique_devices=p.get("unique_devices"),
                cloud_updated_at=p.get("cloud_updated_at"),
                cached_at=p.get("cached_at"),
            )
            for p in prices
        ],
        total=len(prices),
    )


@router.get("/debug")
def get_cloud_debug(
    request: Request,
    repo: Repository = Depends(get_repository),
) -> dict:
    """Debug endpoint to diagnose cloud sync issues."""
    sync_manager = _get_sync_manager(request)

    result = {
        "repo_season_id": repo._current_season_id,
        "repo_player_id": repo._current_player_id,
    }

    if sync_manager:
        result["sync_manager_season_id"] = sync_manager._season_id
        result["cloud_last_price_sync"] = repo.get_setting("cloud_last_price_sync")

        # Try to fetch directly from cloud to compare
        if sync_manager.client.is_connected and sync_manager._season_id:
            # Fetch without 'since' filter to see all available data
            try:
                all_prices = sync_manager.client.fetch_prices_delta(
                    sync_manager._season_id, since=None
                )
                result["cloud_prices_available"] = len(all_prices)
                if all_prices:
                    result["cloud_prices_sample"] = [
                        {"id": p.config_base_id, "updated_at": p.updated_at.isoformat() if p.updated_at else None}
                        for p in all_prices[:5]
                    ]
            except Exception as e:
                result["cloud_fetch_error"] = str(e)

        # Check local cache
        cache_count = repo.db.fetchone(
            "SELECT COUNT(*) FROM cloud_price_cache WHERE season_id = ?",
            (sync_manager._season_id or 0,)
        )
        result["local_cache_count"] = cache_count[0] if cache_count else 0

    return result


@router.get("/prices/{config_base_id}/history", response_model=CloudPriceHistoryResponse)
def get_cloud_price_history(
    config_base_id: int,
    request: Request,
    repo: Repository = Depends(get_repository),
) -> CloudPriceHistoryResponse:
    """Get price history for an item (for sparklines and charts)."""
    sync_manager = _get_sync_manager(request)

    season_id = repo._current_season_id or 0

    if sync_manager is None:
        return CloudPriceHistoryResponse(
            config_base_id=config_base_id,
            season_id=season_id,
            history=[],
        )

    history = sync_manager.get_cached_price_history(config_base_id, season_id)

    return CloudPriceHistoryResponse(
        config_base_id=config_base_id,
        season_id=season_id,
        history=[
            PriceHistoryPoint(
                hour_bucket=h["hour_bucket"],
                price_fe_median=h["price_fe_median"],
                price_fe_p10=h.get("price_fe_p10"),
                price_fe_p90=h.get("price_fe_p90"),
                submission_count=h.get("submission_count"),
            )
            for h in history
        ],
    )


@router.post("/items/sync", response_model=ItemsSyncResponse)
def sync_items_from_cloud(
    request: Request,
    repo: Repository = Depends(get_repository),
) -> ItemsSyncResponse:
    """
    Sync item metadata from Supabase to local database.

    Fetches all items or only items updated since last sync (delta sync).
    Updates local SQLite items table with latest metadata.

    Returns:
        ItemsSyncResponse with success status, synced count, and last sync timestamp
    """
    sync_manager = _get_sync_manager(request)

    if sync_manager is None:
        return ItemsSyncResponse(
            success=False,
            error="Cloud sync not available (Supabase SDK not installed)",
        )

    if not sync_manager.client.is_connected:
        # Try to connect
        if not sync_manager.client.connect():
            return ItemsSyncResponse(
                success=False,
                error="Failed to connect to Supabase (check URL/Key configuration)",
            )

    try:
        # Get last sync timestamp for delta sync
        last_sync_str = repo.get_setting("items_last_sync")
        since = None
        if last_sync_str:
            try:
                since = datetime.fromisoformat(last_sync_str)
            except ValueError:
                # Invalid timestamp, do full sync
                pass

        # Fetch items from Supabase
        items = sync_manager.client.fetch_items_from_cloud(since=since)

        if not items:
            # No new items, but still successful
            return ItemsSyncResponse(
                success=True,
                synced_count=0,
                last_sync=last_sync_str,
            )

        # Sync to local database
        synced_count = repo.sync_items_from_cloud(items)

        # Update last sync timestamp
        now = datetime.utcnow().isoformat()
        repo.set_setting("items_last_sync", now)

        return ItemsSyncResponse(
            success=True,
            synced_count=synced_count,
            last_sync=now,
        )

    except Exception as e:
        return ItemsSyncResponse(
            success=False,
            error=f"Failed to sync items: {str(e)}",
        )


@router.get("/items/last-sync", response_model=ItemsLastSyncResponse)
def get_items_last_sync(
    repo: Repository = Depends(get_repository),
) -> ItemsLastSyncResponse:
    """
    Get last item sync timestamp and total item count.

    Returns:
        ItemsLastSyncResponse with last sync timestamp (ISO 8601) and total items in local DB
    """
    last_sync = repo.get_setting("items_last_sync")
    total_items = repo.get_item_count()

    return ItemsLastSyncResponse(
        last_sync=last_sync,
        total_items=total_items,
    )
