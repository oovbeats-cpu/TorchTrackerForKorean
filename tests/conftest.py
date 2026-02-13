"""Pytest configuration and shared fixtures."""

import json
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture
def fixtures_dir():
    """Get the fixtures directory path."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_items(fixtures_dir):
    """Load sample items from JSON fixture."""
    with open(fixtures_dir / "supabase_items.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sample_prices(fixtures_dir):
    """Load sample prices from JSON fixture."""
    with open(fixtures_dir / "supabase_prices.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def mock_supabase_client(sample_prices):
    """Create a mock Supabase client."""
    client = Mock()

    # Mock table().select() chain
    def create_mock_query():
        mock_query = Mock()
        mock_query.eq.return_value = mock_query
        mock_query.gt.return_value = mock_query
        mock_query.order.return_value = mock_query

        # Mock execute() result
        mock_result = Mock()
        mock_result.data = list(sample_prices)  # Ensure it's a list
        mock_query.execute.return_value = mock_result

        return mock_query

    # Mock table() method - create new query each time
    client.table.side_effect = lambda *args, **kwargs: create_mock_query()

    # Mock rpc() method for submit_price
    mock_rpc = Mock()
    mock_rpc.execute.return_value = Mock(data={"success": True})
    client.rpc.return_value = mock_rpc

    return client


@pytest.fixture
def mock_cloud_client(mock_supabase_client):
    """Create a mock CloudClient."""
    from titrack.sync.client import CloudClient, CloudPrice

    client = CloudClient()
    client._client = mock_supabase_client
    client._connected = True

    return client


@pytest.fixture
def mock_sync_manager():
    """Create a mock SyncManager."""
    from titrack.sync.manager import SyncManager, SyncStatus, SyncStatusInfo

    manager = Mock(spec=SyncManager)
    manager.is_enabled = True
    manager._season_id = 1

    # Mock get_status_info()
    status_info = SyncStatusInfo(
        status=SyncStatus.CONNECTED,
        enabled=True,
        upload_enabled=True,
        download_enabled=True,
        queue_pending=0,
        queue_failed=0,
        last_upload=datetime(2026, 2, 12, 10, 0, 0),
        last_download=datetime(2026, 2, 12, 9, 0, 0),
        last_error=None,
        cloud_available=True,
    )
    manager.get_status_info.return_value = status_info

    # Mock enable/disable
    manager.enable.return_value = True
    manager.disable.return_value = None

    # Mock trigger_sync
    manager.trigger_sync.return_value = {
        "success": True,
        "uploaded": 5,
        "downloaded": 10,
    }

    # Mock get_cached_cloud_prices
    manager.get_cached_cloud_prices.return_value = [
        {
            "config_base_id": 100300,
            "season_id": 1,
            "price_fe_median": 1.0,
            "price_fe_p10": 0.9,
            "price_fe_p90": 1.1,
            "submission_count": 1000,
            "unique_devices": 250,
            "cloud_updated_at": "2026-02-12T10:00:00Z",
            "cached_at": "2026-02-12T10:05:00Z",
        }
    ]

    # Mock get_cached_price_history
    manager.get_cached_price_history.return_value = [
        {
            "hour_bucket": "2026-02-12T08:00:00Z",
            "price_fe_median": 1.0,
            "price_fe_p10": 0.9,
            "price_fe_p90": 1.1,
            "submission_count": 100,
        },
        {
            "hour_bucket": "2026-02-12T09:00:00Z",
            "price_fe_median": 1.05,
            "price_fe_p10": 0.95,
            "price_fe_p90": 1.15,
            "submission_count": 120,
        },
    ]

    return manager
