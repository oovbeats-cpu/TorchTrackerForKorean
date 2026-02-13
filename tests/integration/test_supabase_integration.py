"""Integration tests for real Supabase connection.

These tests require actual Supabase credentials to be set in environment variables:
- TITRACK_SUPABASE_URL
- TITRACK_SUPABASE_KEY

Tests are skipped if credentials are not configured.
"""

import os

import pytest

from titrack.sync.client import CloudClient


# Skip all tests if Supabase is not configured
pytestmark = pytest.mark.skipif(
    not os.getenv("TITRACK_SUPABASE_URL"),
    reason="Supabase not configured (TITRACK_SUPABASE_URL not set)",
)


class TestRealSupabaseConnection:
    """Integration tests with real Supabase backend."""

    def test_real_supabase_connection(self):
        """Test connecting to real Supabase instance."""
        client = CloudClient()

        # Check if Supabase SDK is available
        assert client.is_available, "Supabase SDK not installed"

        # Try to connect
        result = client.connect()

        assert result is True, "Failed to connect to Supabase"
        assert client.is_connected is True

        # Disconnect
        client.disconnect()
        assert client.is_connected is False

    def test_fetch_prices_from_cloud(self):
        """Test fetching prices from real Supabase."""
        client = CloudClient()

        # Connect
        assert client.connect(), "Failed to connect"

        try:
            # Fetch prices for season 1
            prices = client.fetch_prices_delta(season_id=1)

            # Verify we got a list (may be empty if no data)
            assert isinstance(prices, list)

            # If we have prices, verify structure
            if prices:
                first_price = prices[0]
                assert hasattr(first_price, "config_base_id")
                assert hasattr(first_price, "season_id")
                assert hasattr(first_price, "price_fe_median")
                assert isinstance(first_price.config_base_id, int)
                assert isinstance(first_price.season_id, int)
                assert isinstance(first_price.price_fe_median, (int, float))

        finally:
            client.disconnect()

    def test_fetch_price_history_from_cloud(self):
        """Test fetching price history from real Supabase."""
        client = CloudClient()

        # Connect
        assert client.connect(), "Failed to connect"

        try:
            # Fetch price history for season 1
            history = client.fetch_price_history(season_id=1, hours=72)

            # Verify we got a list (may be empty if no data)
            assert isinstance(history, list)

            # If we have history, verify structure
            if history:
                first_point = history[0]
                assert hasattr(first_point, "config_base_id")
                assert hasattr(first_point, "season_id")
                assert hasattr(first_point, "hour_bucket")
                assert hasattr(first_point, "price_fe_median")
                assert isinstance(first_point.config_base_id, int)
                assert isinstance(first_point.season_id, int)
                assert isinstance(first_point.price_fe_median, (int, float))

        finally:
            client.disconnect()

    def test_submit_price_to_cloud(self):
        """Test submitting a price to real Supabase."""
        client = CloudClient()

        # Connect
        assert client.connect(), "Failed to connect"

        try:
            # Submit a test price
            result = client.submit_price(
                device_id="test-device-integration",
                config_base_id=100300,
                season_id=1,
                price_fe=1.0,
                prices_array=[0.9, 1.0, 1.1],
            )

            # Verify result structure
            assert hasattr(result, "success")
            assert hasattr(result, "error")
            assert hasattr(result, "rate_limited")

            # Success or rate limited (both are acceptable in integration test)
            if not result.success:
                if result.rate_limited:
                    pytest.skip("Rate limited - expected in integration test")
                else:
                    pytest.fail(f"Price submission failed: {result.error}")

        finally:
            client.disconnect()


class TestRealSupabaseWithEnvVars:
    """Tests that explicitly check environment variable handling."""

    def test_get_config_from_env(self):
        """Test that config is read from environment variables."""
        # Ensure env vars are set (test should be skipped if not)
        assert os.getenv("TITRACK_SUPABASE_URL") is not None

        client = CloudClient()
        url, key = client.get_config()

        assert url is not None
        assert key is not None
        assert url.startswith("https://")

    def test_connect_uses_env_config(self):
        """Test that connection uses environment config."""
        client = CloudClient()

        # Get config
        url, key = client.get_config()
        assert url is not None, "TITRACK_SUPABASE_URL not set"

        # Connect should succeed with env config
        result = client.connect()
        assert result is True

        client.disconnect()
