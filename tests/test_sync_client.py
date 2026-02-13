"""Tests for Supabase cloud client."""

import os
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from titrack.sync.client import CloudClient, CloudPrice, CloudPriceHistory, SubmitResult


def create_mock_result(data):
    """Helper to create a mock Supabase result with data."""
    return SimpleNamespace(data=data)


class TestCloudClientConnection:
    """Tests for CloudClient connection management."""

    @patch("titrack.sync.client.SUPABASE_AVAILABLE", True)
    @patch("titrack.sync.client.create_client")
    def test_connect_success(self, mock_create_client):
        """Test successful connection to Supabase."""
        mock_client = Mock()
        mock_create_client.return_value = mock_client

        client = CloudClient()
        assert client.is_available is True
        assert client.is_connected is False

        # Connect with default config
        result = client.connect()

        assert result is True
        assert client.is_connected is True
        mock_create_client.assert_called_once()

    @patch("titrack.sync.client.SUPABASE_AVAILABLE", True)
    def test_connect_no_config(self):
        """Test connection fails when config is missing."""
        client = CloudClient()

        # Clear environment variables
        with patch.dict(os.environ, {}, clear=True):
            # Mock get_config to return None
            with patch.object(client, "get_config", return_value=(None, None)):
                result = client.connect()

                assert result is False
                assert client.is_connected is False

    @patch("titrack.sync.client.SUPABASE_AVAILABLE", False)
    def test_connect_not_available(self):
        """Test connection fails when Supabase SDK is not installed."""
        client = CloudClient()

        assert client.is_available is False

        result = client.connect()

        assert result is False
        assert client.is_connected is False

    @patch("titrack.sync.client.SUPABASE_AVAILABLE", True)
    @patch("titrack.sync.client.create_client")
    def test_connect_exception(self, mock_create_client):
        """Test connection handles exceptions gracefully."""
        mock_create_client.side_effect = Exception("Connection error")

        client = CloudClient()
        result = client.connect()

        assert result is False
        assert client.is_connected is False

    def test_disconnect(self):
        """Test disconnection."""
        client = CloudClient()
        client._connected = True
        client._client = Mock()

        assert client.is_connected is True

        client.disconnect()

        assert client.is_connected is False
        assert client._client is None


class TestCloudClientPriceFetch:
    """Tests for fetching prices from cloud."""

    def test_fetch_prices_delta_success(self, sample_prices):
        """Test successful price fetch."""
        client = CloudClient()
        client._connected = True

        # Mock the Supabase client
        mock_supabase = Mock()
        mock_query = Mock()

        # Set up the chain
        mock_query.execute.return_value = create_mock_result(sample_prices)
        mock_query.eq.return_value = mock_query
        mock_query.gt.return_value = mock_query
        mock_supabase.table.return_value = mock_query

        client._client = mock_supabase

        prices = client.fetch_prices_delta(season_id=1)

        assert len(prices) == 2
        assert prices[0].config_base_id == 100300
        assert prices[0].price_fe_median == 1.0
        assert prices[1].config_base_id == 200100
        assert prices[1].price_fe_median == 150.0

    def test_fetch_prices_delta_since(self):
        """Test price fetch with since parameter."""
        client = CloudClient()
        client._connected = True

        since = datetime(2026, 2, 12, 9, 30, 0)

        mock_supabase = Mock()
        mock_query = Mock()
        mock_data = [
            {
                "config_base_id": 100300,
                "season_id": 1,
                "price_fe_median": 1.0,
                "updated_at": "2026-02-12T10:00:00Z",
            }
        ]

        # Set up the chain
        mock_query.execute.return_value = create_mock_result(mock_data)
        mock_query.eq.return_value = mock_query
        mock_query.gt.return_value = mock_query
        mock_supabase.table.return_value = mock_query

        client._client = mock_supabase

        prices = client.fetch_prices_delta(season_id=1, since=since)

        assert len(prices) == 1
        # Verify .gt() was called with since timestamp
        mock_query.gt.assert_called_once()

    def test_fetch_prices_delta_empty(self):
        """Test price fetch returns empty list when no data."""
        client = CloudClient()
        client._connected = True

        mock_supabase = Mock()
        mock_query = Mock()

        # Set up the chain with empty data
        mock_query.execute.return_value = create_mock_result([])
        mock_query.eq.return_value = mock_query
        mock_query.gt.return_value = mock_query
        mock_supabase.table.return_value = mock_query

        client._client = mock_supabase

        prices = client.fetch_prices_delta(season_id=1)

        assert len(prices) == 0

    def test_fetch_prices_delta_error(self):
        """Test price fetch handles errors gracefully."""
        client = CloudClient()
        client._connected = True

        # Mock exception
        mock_supabase = Mock()
        mock_query = Mock()
        mock_query.eq.side_effect = Exception("Network error")
        mock_supabase.table.return_value = mock_query

        client._client = mock_supabase

        prices = client.fetch_prices_delta(season_id=1)

        assert len(prices) == 0

    def test_fetch_prices_delta_not_connected(self):
        """Test fetch returns empty list when not connected."""
        client = CloudClient()
        assert client.is_connected is False

        prices = client.fetch_prices_delta(season_id=1)

        assert len(prices) == 0


class TestCloudClientPriceSubmit:
    """Tests for submitting prices to cloud."""

    def test_submit_price_success(self):
        """Test successful price submission."""
        client = CloudClient()
        client._connected = True

        # Mock RPC call
        mock_supabase = Mock()
        mock_rpc = Mock()
        mock_rpc.execute.return_value = Mock(data={"success": True})
        mock_supabase.rpc.return_value = mock_rpc

        client._client = mock_supabase

        result = client.submit_price(
            device_id="test-device-id",
            config_base_id=100300,
            season_id=1,
            price_fe=1.0,
            prices_array=[0.9, 1.0, 1.1],
        )

        assert result.success is True
        assert result.error is None
        assert result.rate_limited is False

    def test_submit_price_rate_limit(self):
        """Test price submission handles rate limiting."""
        client = CloudClient()
        client._connected = True

        # Mock rate limit response
        mock_supabase = Mock()
        mock_rpc = Mock()
        mock_rpc.execute.return_value = Mock(data={"rate_limited": True})
        mock_supabase.rpc.return_value = mock_rpc

        client._client = mock_supabase

        result = client.submit_price(
            device_id="test-device-id",
            config_base_id=100300,
            season_id=1,
            price_fe=1.0,
            prices_array=[0.9, 1.0, 1.1],
        )

        assert result.success is False
        assert result.error == "Rate limited"
        assert result.rate_limited is True

    def test_submit_price_exception(self):
        """Test price submission handles exceptions."""
        client = CloudClient()
        client._connected = True

        # Mock exception
        mock_supabase = Mock()
        mock_rpc = Mock()
        mock_rpc.execute.side_effect = Exception("API error 429")
        mock_supabase.rpc.return_value = mock_rpc

        client._client = mock_supabase

        result = client.submit_price(
            device_id="test-device-id",
            config_base_id=100300,
            season_id=1,
            price_fe=1.0,
            prices_array=[0.9, 1.0, 1.1],
        )

        assert result.success is False
        assert result.error == "API error 429"
        assert result.rate_limited is True  # Detected from error message

    def test_submit_price_not_connected(self):
        """Test submit returns error when not connected."""
        client = CloudClient()
        assert client.is_connected is False

        result = client.submit_price(
            device_id="test-device-id",
            config_base_id=100300,
            season_id=1,
            price_fe=1.0,
            prices_array=[0.9, 1.0, 1.1],
        )

        assert result.success is False
        assert result.error == "Not connected"
        assert result.rate_limited is False


class TestCloudClientPriceHistory:
    """Tests for fetching price history."""

    def test_fetch_price_history_success(self):
        """Test successful price history fetch."""
        client = CloudClient()
        client._connected = True

        # Mock history data
        mock_supabase = Mock()
        mock_query = Mock()
        mock_data = [
            {
                "config_base_id": 100300,
                "season_id": 1,
                "hour_bucket": "2026-02-12T08:00:00Z",
                "price_fe_median": 1.0,
                "price_fe_p10": 0.9,
                "price_fe_p90": 1.1,
                "submission_count": 100,
            },
            {
                "config_base_id": 100300,
                "season_id": 1,
                "hour_bucket": "2026-02-12T09:00:00Z",
                "price_fe_median": 1.05,
                "price_fe_p10": 0.95,
                "price_fe_p90": 1.15,
                "submission_count": 120,
            },
        ]

        # Set up the chain
        mock_query.execute.return_value = create_mock_result(mock_data)
        mock_query.eq.return_value = mock_query
        mock_query.gt.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_supabase.table.return_value = mock_query

        client._client = mock_supabase

        history = client.fetch_price_history(season_id=1, hours=72)

        assert len(history) == 2
        assert history[0].hour_bucket == datetime(2026, 2, 12, 8, 0, 0)
        assert history[0].price_fe_median == 1.0
        assert history[1].hour_bucket == datetime(2026, 2, 12, 9, 0, 0)
        assert history[1].price_fe_median == 1.05

    def test_fetch_item_history_success(self):
        """Test successful item-specific history fetch."""
        client = CloudClient()
        client._connected = True

        # Mock history data
        mock_supabase = Mock()
        mock_query = Mock()
        mock_data = [
            {
                "config_base_id": 100300,
                "season_id": 1,
                "hour_bucket": "2026-02-12T08:00:00Z",
                "price_fe_median": 1.0,
            }
        ]

        # Set up the chain
        mock_query.execute.return_value = create_mock_result(mock_data)
        mock_query.eq.return_value = mock_query
        mock_query.gt.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_supabase.table.return_value = mock_query

        client._client = mock_supabase

        history = client.fetch_item_history(
            config_base_id=100300, season_id=1, hours=72
        )

        assert len(history) == 1
        assert history[0].config_base_id == 100300
        assert history[0].price_fe_median == 1.0

    def test_fetch_price_history_error(self):
        """Test price history fetch handles errors."""
        client = CloudClient()
        client._connected = True

        # Mock exception
        mock_supabase = Mock()
        mock_query = Mock()
        mock_query.eq.side_effect = Exception("Network error")
        mock_supabase.table.return_value = mock_query

        client._client = mock_supabase

        history = client.fetch_price_history(season_id=1, hours=72)

        assert len(history) == 0

    def test_fetch_price_history_not_connected(self):
        """Test history returns empty list when not connected."""
        client = CloudClient()
        assert client.is_connected is False

        history = client.fetch_price_history(season_id=1, hours=72)

        assert len(history) == 0
