"""Tests for Supabase cloud API endpoints."""

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from titrack.api.app import create_app
from titrack.db.connection import Database
from titrack.db.repository import Repository
from titrack.sync.manager import SyncManager, SyncStatus, SyncStatusInfo


@pytest.fixture
def test_db():
    """Create a test database in memory."""
    db = Database(":memory:")
    db.initialize()
    return db


@pytest.fixture
def test_repo(test_db):
    """Create a test repository."""
    return Repository(test_db)


@pytest.fixture
def test_app(test_repo):
    """Create a test FastAPI app."""
    app = create_app(test_repo)
    return app


@pytest.fixture
def test_client(test_app):
    """Create a test client."""
    return TestClient(test_app)


class TestCloudStatus:
    """Tests for GET /api/cloud/status endpoint."""

    def test_get_cloud_status_no_manager(self, test_client):
        """Test status when sync_manager is not available."""
        # sync_manager is None by default in test app
        response = test_client.get("/api/cloud/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "disabled"
        assert data["enabled"] is False
        assert data["cloud_available"] is False

    def test_get_cloud_status_disabled(self, test_app, test_client, mock_sync_manager):
        """Test status when sync_manager is disabled."""
        # Mock disabled state
        mock_sync_manager.is_enabled = False
        status_info = SyncStatusInfo(
            status=SyncStatus.DISABLED,
            enabled=False,
            upload_enabled=True,
            download_enabled=True,
            queue_pending=0,
            queue_failed=0,
            cloud_available=False,
        )
        mock_sync_manager.get_status_info.return_value = status_info

        # Attach sync_manager to app state
        test_app.state.sync_manager = mock_sync_manager

        response = test_client.get("/api/cloud/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "disabled"
        assert data["enabled"] is False
        assert data["cloud_available"] is False

    def test_get_cloud_status_enabled(self, test_app, test_client, mock_sync_manager):
        """Test status when sync_manager is enabled and connected."""
        # Attach sync_manager to app state
        test_app.state.sync_manager = mock_sync_manager

        response = test_client.get("/api/cloud/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "connected"
        assert data["enabled"] is True
        assert data["cloud_available"] is True
        assert data["queue_pending"] == 0
        assert data["queue_failed"] == 0
        assert data["last_upload"] is not None
        assert data["last_download"] is not None


class TestCloudToggle:
    """Tests for POST /api/cloud/toggle endpoint."""

    def test_toggle_cloud_sync_enable(self, test_app, test_client, mock_sync_manager):
        """Test enabling cloud sync."""
        test_app.state.sync_manager = mock_sync_manager

        response = test_client.post("/api/cloud/toggle", json={"enabled": True})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["enabled"] is True
        assert data["error"] is None

        mock_sync_manager.enable.assert_called_once()

    def test_toggle_cloud_sync_disable(self, test_app, test_client, mock_sync_manager):
        """Test disabling cloud sync."""
        test_app.state.sync_manager = mock_sync_manager

        response = test_client.post("/api/cloud/toggle", json={"enabled": False})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["enabled"] is False

        mock_sync_manager.disable.assert_called_once()

    def test_toggle_no_manager(self, test_client):
        """Test toggle when sync_manager is not available."""
        response = test_client.post("/api/cloud/toggle", json={"enabled": True})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["enabled"] is False
        assert data["error"] == "Cloud sync not available"

    def test_toggle_enable_fails(self, test_app, test_client, mock_sync_manager):
        """Test toggle when enable() fails."""
        test_app.state.sync_manager = mock_sync_manager

        # Mock enable failure
        mock_sync_manager.enable.return_value = False
        error_status = SyncStatusInfo(
            status=SyncStatus.ERROR,
            enabled=False,
            upload_enabled=True,
            download_enabled=True,
            queue_pending=0,
            queue_failed=0,
            last_error="Connection failed",
            cloud_available=False,
        )
        mock_sync_manager.get_status_info.return_value = error_status

        response = test_client.post("/api/cloud/toggle", json={"enabled": True})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["enabled"] is False
        assert "Connection failed" in data["error"]


class TestCloudSync:
    """Tests for POST /api/cloud/sync endpoint."""

    def test_trigger_sync_success(self, test_app, test_client, mock_sync_manager):
        """Test successful manual sync."""
        test_app.state.sync_manager = mock_sync_manager

        response = test_client.post("/api/cloud/sync")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["uploaded"] == 5
        assert data["downloaded"] == 10
        assert data["error"] is None

        mock_sync_manager.trigger_sync.assert_called_once()

    def test_trigger_sync_not_enabled(self, test_app, test_client, mock_sync_manager):
        """Test sync fails when cloud sync is disabled."""
        test_app.state.sync_manager = mock_sync_manager
        mock_sync_manager.is_enabled = False

        response = test_client.post("/api/cloud/sync")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "Cloud sync not enabled"

    def test_trigger_sync_no_manager(self, test_client):
        """Test sync fails when sync_manager is not available."""
        response = test_client.post("/api/cloud/sync")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "Cloud sync not available"

    def test_trigger_sync_error(self, test_app, test_client, mock_sync_manager):
        """Test sync handles errors."""
        test_app.state.sync_manager = mock_sync_manager

        # Mock sync error
        mock_sync_manager.trigger_sync.return_value = {
            "success": False,
            "error": "Network error",
        }

        response = test_client.post("/api/cloud/sync")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "Network error"


class TestCloudPrices:
    """Tests for cloud prices endpoints."""

    def test_get_cloud_prices(self, test_app, test_client, mock_sync_manager):
        """Test fetching cached cloud prices."""
        test_app.state.sync_manager = mock_sync_manager

        response = test_client.get("/api/cloud/prices")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["prices"]) == 1
        assert data["prices"][0]["config_base_id"] == 100300
        assert data["prices"][0]["price_fe_median"] == 1.0

    def test_get_cloud_prices_no_manager(self, test_client):
        """Test prices returns empty list when sync_manager is not available."""
        response = test_client.get("/api/cloud/prices")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["prices"]) == 0

    def test_get_price_history(self, test_app, test_client, mock_sync_manager):
        """Test fetching price history for an item."""
        test_app.state.sync_manager = mock_sync_manager

        response = test_client.get("/api/cloud/prices/100300/history")

        assert response.status_code == 200
        data = response.json()
        assert data["config_base_id"] == 100300
        assert data["season_id"] == 0  # Default from test_repo
        assert len(data["history"]) == 2
        assert data["history"][0]["hour_bucket"] == "2026-02-12T08:00:00Z"
        assert data["history"][0]["price_fe_median"] == 1.0

    def test_get_price_history_no_manager(self, test_client):
        """Test history returns empty list when sync_manager is not available."""
        response = test_client.get("/api/cloud/prices/100300/history")

        assert response.status_code == 200
        data = response.json()
        assert data["config_base_id"] == 100300
        assert len(data["history"]) == 0
