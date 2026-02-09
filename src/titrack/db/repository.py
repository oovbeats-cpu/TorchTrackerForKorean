"""Repository - CRUD operations for all entities."""

import statistics
from datetime import datetime
from pathlib import Path
from typing import Optional

from titrack.core.models import (
    EventContext,
    Item,
    ItemDelta,
    Price,
    Run,
    SlotState,
)
from titrack.db.connection import Database
from titrack.data.inventory import EXCLUDED_PAGES
from titrack.data.korean_names import get_korean_name
from titrack.data.fallback_prices import get_fallback_price


class Repository:
    """Data access layer for all entities."""

    def __init__(self, db: Database) -> None:
        self.db = db
        # Current player context for filtering (set externally)
        self._current_season_id: Optional[int] = None
        self._current_player_id: Optional[str] = None

    def set_player_context(self, season_id: Optional[int], player_id: Optional[str]) -> None:
        """Set the current player context for filtering queries."""
        self._current_season_id = season_id
        self._current_player_id = player_id

    def has_player_context(self) -> bool:
        """Return True if a player context has been set."""
        return self._current_player_id is not None

    # --- Settings ---

    def get_setting(self, key: str) -> Optional[str]:
        """Get a setting value by key."""
        row = self.db.fetchone("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else None

    def set_setting(self, key: str, value: str) -> None:
        """Set a setting value."""
        self.db.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, datetime.now().isoformat()),
        )

    # --- Runs ---

    def insert_run(self, run: Run) -> int:
        """Insert a new run and return its ID."""
        cursor = self.db.execute(
            """INSERT INTO runs (zone_signature, start_ts, end_ts, is_hub, level_id, level_type, level_uid, season_id, player_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run.zone_signature,
                run.start_ts.isoformat(),
                run.end_ts.isoformat() if run.end_ts else None,
                1 if run.is_hub else 0,
                run.level_id,
                run.level_type,
                run.level_uid,
                run.season_id,
                run.player_id,
            ),
        )
        return cursor.lastrowid

    def update_run_end(self, run_id: int, end_ts: datetime) -> None:
        """Update a run's end timestamp."""
        self.db.execute(
            "UPDATE runs SET end_ts = ? WHERE id = ?",
            (end_ts.isoformat(), run_id),
        )

    def get_run(self, run_id: int) -> Optional[Run]:
        """Get a run by ID."""
        row = self.db.fetchone("SELECT * FROM runs WHERE id = ?", (run_id,))
        if not row:
            return None
        return self._row_to_run(row)

    def get_active_run(self, season_id: Optional[int] = None, player_id: Optional[str] = None) -> Optional[Run]:
        """Get the currently active (non-ended) run, optionally filtered by season/player."""
        # Use provided values or fall back to context
        season_id = season_id if season_id is not None else self._current_season_id
        player_id = player_id if player_id is not None else self._current_player_id

        # Return None if no player context is set (awaiting character login)
        if self._current_player_id is None and player_id is None:
            return None

        if season_id is not None:
            # Filter: show data where season/player matches OR is NULL (legacy/untagged)
            # This excludes data explicitly tagged for a DIFFERENT season/player
            row = self.db.fetchone(
                """SELECT * FROM runs WHERE end_ts IS NULL
                   AND (season_id IS NULL OR season_id = ?)
                   AND (player_id IS NULL OR player_id = ?)
                   ORDER BY start_ts DESC LIMIT 1""",
                (season_id, player_id or ''),
            )
        else:
            row = self.db.fetchone(
                "SELECT * FROM runs WHERE end_ts IS NULL ORDER BY start_ts DESC LIMIT 1"
            )
        if not row:
            return None
        return self._row_to_run(row)

    def get_recent_runs(self, limit: int = 20, season_id: Optional[int] = None, player_id: Optional[str] = None) -> list[Run]:
        """Get recent runs ordered by start time descending, optionally filtered by season/player."""
        # Use provided values or fall back to context
        season_id = season_id if season_id is not None else self._current_season_id
        player_id = player_id if player_id is not None else self._current_player_id

        # Return empty list if no player context is set (awaiting character login)
        if self._current_player_id is None and player_id is None:
            return []

        if season_id is not None:
            # Filter: show data where season/player matches OR is NULL (legacy/untagged)
            # This excludes data explicitly tagged for a DIFFERENT season/player
            # Only show runs not yet assigned to a session (current session view)
            rows = self.db.fetchall(
                """SELECT * FROM runs
                   WHERE session_id IS NULL
                   AND (season_id IS NULL OR season_id = ?)
                   AND (player_id IS NULL OR player_id = ?)
                   ORDER BY start_ts DESC LIMIT ?""",
                (season_id, player_id or '', limit),
            )
        else:
            rows = self.db.fetchall(
                "SELECT * FROM runs WHERE session_id IS NULL ORDER BY start_ts DESC LIMIT ?", (limit,)
            )
        return [self._row_to_run(row) for row in rows]

    def get_max_run_id(self) -> int:
        """Get the maximum run ID."""
        row = self.db.fetchone("SELECT MAX(id) as max_id FROM runs")
        return row["max_id"] or 0

    def get_unique_zones(self, season_id: Optional[int] = None, player_id: Optional[str] = None) -> list[str]:
        """Get all unique zone signatures from runs, optionally filtered by season/player."""
        # Use provided values or fall back to context
        season_id = season_id if season_id is not None else self._current_season_id
        player_id = player_id if player_id is not None else self._current_player_id

        # Return empty list if no player context is set (awaiting character login)
        if self._current_player_id is None and player_id is None:
            return []

        if season_id is not None:
            # Filter: show data where season/player matches OR is NULL (legacy/untagged)
            # Only show zones from runs not yet assigned to a session
            rows = self.db.fetchall(
                """SELECT DISTINCT zone_signature FROM runs
                   WHERE session_id IS NULL
                   AND (season_id IS NULL OR season_id = ?)
                   AND (player_id IS NULL OR player_id = ?)
                   ORDER BY zone_signature""",
                (season_id, player_id or ''),
            )
        else:
            rows = self.db.fetchall(
                "SELECT DISTINCT zone_signature FROM runs WHERE session_id IS NULL ORDER BY zone_signature"
            )
        return [row["zone_signature"] for row in rows]

    def _row_to_run(self, row) -> Run:
        # Handle columns which may not exist in older databases
        keys = row.keys()
        level_id = row["level_id"] if "level_id" in keys else None
        level_type = row["level_type"] if "level_type" in keys else None
        level_uid = row["level_uid"] if "level_uid" in keys else None
        season_id = row["season_id"] if "season_id" in keys else None
        player_id = row["player_id"] if "player_id" in keys else None
        return Run(
            id=row["id"],
            zone_signature=row["zone_signature"],
            start_ts=datetime.fromisoformat(row["start_ts"]),
            end_ts=datetime.fromisoformat(row["end_ts"]) if row["end_ts"] else None,
            is_hub=bool(row["is_hub"]),
            level_id=level_id,
            level_type=level_type,
            level_uid=level_uid,
            season_id=season_id,
            player_id=player_id,
        )

    # --- Item Deltas ---

    def insert_delta(self, delta: ItemDelta) -> int:
        """Insert an item delta and return its ID."""
        cursor = self.db.execute(
            """INSERT INTO item_deltas
               (page_id, slot_id, config_base_id, delta, context, proto_name, run_id, timestamp, season_id, player_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                delta.page_id,
                delta.slot_id,
                delta.config_base_id,
                delta.delta,
                delta.context.name,
                delta.proto_name,
                delta.run_id,
                delta.timestamp.isoformat(),
                delta.season_id,
                delta.player_id,
            ),
        )
        return cursor.lastrowid

    def get_deltas_for_run(self, run_id: int, include_excluded: bool = False) -> list[ItemDelta]:
        """
        Get all deltas for a run.

        Args:
            run_id: The run ID to get deltas for.
            include_excluded: If True, include excluded pages (e.g., Gear).
                              Default False filters out excluded pages.
        """
        if include_excluded or not EXCLUDED_PAGES:
            rows = self.db.fetchall(
                "SELECT * FROM item_deltas WHERE run_id = ? ORDER BY timestamp",
                (run_id,),
            )
        else:
            placeholders = ",".join("?" * len(EXCLUDED_PAGES))
            rows = self.db.fetchall(
                f"SELECT * FROM item_deltas WHERE run_id = ? AND page_id NOT IN ({placeholders}) ORDER BY timestamp",
                (run_id, *EXCLUDED_PAGES),
            )
        return [self._row_to_delta(row) for row in rows]

    def get_run_summary(self, run_id: int, include_excluded: bool = False) -> dict[int, int]:
        """
        Get aggregated delta per item for a run (excludes map costs).

        Args:
            run_id: The run ID to get summary for.
            include_excluded: If True, include excluded pages (e.g., Gear).
                              Default False filters out excluded pages.

        Returns:
            Dict mapping config_base_id -> total delta
        """
        # Always exclude Spv3Open (map costs) from loot summary
        if include_excluded or not EXCLUDED_PAGES:
            rows = self.db.fetchall(
                """SELECT config_base_id, SUM(delta) as total_delta
                   FROM item_deltas
                   WHERE run_id = ? AND (proto_name IS NULL OR proto_name != 'Spv3Open')
                   GROUP BY config_base_id""",
                (run_id,),
            )
        else:
            placeholders = ",".join("?" * len(EXCLUDED_PAGES))
            rows = self.db.fetchall(
                f"""SELECT config_base_id, SUM(delta) as total_delta
                   FROM item_deltas
                   WHERE run_id = ? AND page_id NOT IN ({placeholders})
                   AND (proto_name IS NULL OR proto_name != 'Spv3Open')
                   GROUP BY config_base_id""",
                (run_id, *EXCLUDED_PAGES),
            )
        return {row["config_base_id"]: row["total_delta"] for row in rows}

    def _row_to_delta(self, row) -> ItemDelta:
        keys = row.keys()
        season_id = row["season_id"] if "season_id" in keys else None
        player_id = row["player_id"] if "player_id" in keys else None
        return ItemDelta(
            page_id=row["page_id"],
            slot_id=row["slot_id"],
            config_base_id=row["config_base_id"],
            delta=row["delta"],
            context=EventContext[row["context"]],
            proto_name=row["proto_name"],
            run_id=row["run_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            season_id=season_id,
            player_id=player_id,
        )

    # --- Slot State ---

    def upsert_slot_state(self, state: SlotState) -> None:
        """Insert or update slot state."""
        # Use empty string for NULL player_id to match PK constraint
        player_id = state.player_id if state.player_id else ""
        self.db.execute(
            """INSERT OR REPLACE INTO slot_state
               (player_id, page_id, slot_id, config_base_id, num, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                player_id,
                state.page_id,
                state.slot_id,
                state.config_base_id,
                state.num,
                state.updated_at.isoformat(),
            ),
        )

    def get_all_slot_states(self, include_excluded: bool = False, player_id: Optional[str] = None) -> list[SlotState]:
        """
        Get all slot states.

        Args:
            include_excluded: If True, include excluded pages (e.g., Gear).
                              Default False filters out excluded pages.
            player_id: Filter by player_id. If None, uses current context or returns all.
        """
        # Use provided value or fall back to context
        player_id = player_id if player_id is not None else self._current_player_id

        # Return empty list if no player context is set (awaiting character login)
        if self._current_player_id is None and player_id is None:
            return []

        player_id_filter = player_id if player_id else ""

        if include_excluded or not EXCLUDED_PAGES:
            if player_id is not None:
                rows = self.db.fetchall(
                    "SELECT * FROM slot_state WHERE player_id = ?",
                    (player_id_filter,),
                )
            else:
                rows = self.db.fetchall("SELECT * FROM slot_state")
        else:
            placeholders = ",".join("?" * len(EXCLUDED_PAGES))
            if player_id is not None:
                rows = self.db.fetchall(
                    f"SELECT * FROM slot_state WHERE player_id = ? AND page_id NOT IN ({placeholders})",
                    (player_id_filter, *EXCLUDED_PAGES),
                )
            else:
                rows = self.db.fetchall(
                    f"SELECT * FROM slot_state WHERE page_id NOT IN ({placeholders})",
                    tuple(EXCLUDED_PAGES),
                )
        return [self._row_to_slot_state(row) for row in rows]

    def get_slot_state(self, page_id: int, slot_id: int, player_id: Optional[str] = None) -> Optional[SlotState]:
        """Get state for a specific slot."""
        # Use provided value or fall back to context
        player_id = player_id if player_id is not None else self._current_player_id
        player_id_filter = player_id if player_id else ""

        row = self.db.fetchone(
            "SELECT * FROM slot_state WHERE player_id = ? AND page_id = ? AND slot_id = ?",
            (player_id_filter, page_id, slot_id),
        )
        if not row:
            return None
        return self._row_to_slot_state(row)

    def clear_page_slot_states(self, page_id: int, player_id: Optional[str] = None) -> int:
        """
        Clear all slot states for a specific inventory page and player.

        Used when receiving InitBagData events to ensure stale slots are removed.

        Returns:
            Number of slots cleared.
        """
        # Use provided value or fall back to context
        player_id = player_id if player_id is not None else self._current_player_id
        player_id_filter = player_id if player_id else ""

        cursor = self.db.execute(
            "DELETE FROM slot_state WHERE player_id = ? AND page_id = ?",
            (player_id_filter, page_id),
        )
        return cursor.rowcount

    def _row_to_slot_state(self, row) -> SlotState:
        keys = row.keys()
        player_id = row["player_id"] if "player_id" in keys else None
        # Convert empty string back to None
        if player_id == "":
            player_id = None
        return SlotState(
            page_id=row["page_id"],
            slot_id=row["slot_id"],
            config_base_id=row["config_base_id"],
            num=row["num"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
            player_id=player_id,
        )

    # --- Items ---

    def upsert_item(self, item: Item) -> None:
        """Insert or update item metadata."""
        self.db.execute(
            """INSERT OR REPLACE INTO items
               (config_base_id, name_en, name_cn, type_cn, icon_url, url_en, url_cn)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                item.config_base_id,
                item.name_en,
                item.name_cn,
                item.type_cn,
                item.icon_url,
                item.url_en,
                item.url_cn,
            ),
        )

    def upsert_items_batch(self, items: list[Item]) -> None:
        """Insert or update multiple items."""
        self.db.executemany(
            """INSERT OR REPLACE INTO items
               (config_base_id, name_en, name_cn, type_cn, icon_url, url_en, url_cn)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    item.config_base_id,
                    item.name_en,
                    item.name_cn,
                    item.type_cn,
                    item.icon_url,
                    item.url_en,
                    item.url_cn,
                )
                for item in items
            ],
        )

    def get_item(self, config_base_id: int) -> Optional[Item]:
        """Get item by ConfigBaseId."""
        row = self.db.fetchone(
            "SELECT * FROM items WHERE config_base_id = ?", (config_base_id,)
        )
        if not row:
            return None
        return self._row_to_item(row)

    def get_item_name(self, config_base_id: int) -> str:
        """Get item name, preferring Korean name, falling back to English, then Unknown <id>."""
        ko_name = get_korean_name(config_base_id)
        if ko_name:
            return ko_name
        item = self.get_item(config_base_id)
        if item and item.name_en:
            return item.name_en
        return f"알 수 없음 {config_base_id}"

    def get_all_items(self) -> list[Item]:
        """Get all items."""
        rows = self.db.fetchall("SELECT * FROM items")
        return [self._row_to_item(row) for row in rows]

    def get_item_count(self) -> int:
        """Get total number of items in database."""
        row = self.db.fetchone("SELECT COUNT(*) as cnt FROM items")
        return row["cnt"] if row else 0

    def update_item_name(self, config_base_id: int, name_en: str) -> None:
        """Update an item's English name."""
        self.db.execute(
            "UPDATE items SET name_en = ? WHERE config_base_id = ?",
            (name_en, config_base_id),
        )

    def _row_to_item(self, row) -> Item:
        return Item(
            config_base_id=row["config_base_id"],
            name_en=row["name_en"],
            name_cn=row["name_cn"],
            type_cn=row["type_cn"],
            icon_url=row["icon_url"],
            url_en=row["url_en"],
            url_cn=row["url_cn"],
        )

    # --- Prices ---

    def upsert_price(self, price: Price) -> None:
        """Insert or update a price entry."""
        # Use 0 for NULL season_id to match PK constraint
        season_id = price.season_id if price.season_id is not None else 0
        self.db.execute(
            """INSERT OR REPLACE INTO prices
               (config_base_id, season_id, price_fe, source, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                price.config_base_id,
                season_id,
                price.price_fe,
                price.source,
                price.updated_at.isoformat(),
            ),
        )

    def get_price(self, config_base_id: int, season_id: Optional[int] = None) -> Optional[Price]:
        """Get price for an item, filtered by season (no cross-season fallback)."""
        # Use provided value or fall back to context
        season_id = season_id if season_id is not None else self._current_season_id
        season_id_filter = season_id if season_id is not None else 0

        row = self.db.fetchone(
            "SELECT * FROM prices WHERE config_base_id = ? AND season_id = ?",
            (config_base_id, season_id_filter),
        )
        if not row:
            return None
        return self._row_to_price(row)

    def get_cloud_price(self, config_base_id: int, season_id: Optional[int] = None) -> Optional[float]:
        """
        Get cloud price for an item (median price from community data).

        Returns the median price in FE, or None if not available.
        Only returns prices with at least 3 unique contributors.
        """
        season_id = season_id if season_id is not None else self._current_season_id
        season_id_filter = season_id if season_id is not None else 0

        row = self.db.fetchone(
            """SELECT price_fe_median, unique_devices FROM cloud_price_cache
               WHERE config_base_id = ? AND season_id = ? AND unique_devices >= 1""",
            (config_base_id, season_id_filter),
        )
        if not row:
            return None
        return row["price_fe_median"]

    def get_effective_price(self, config_base_id: int, season_id: Optional[int] = None) -> Optional[float]:
        """
        Get the effective price for an item using cloud-first logic with fallback.

        Priority (based on timestamp comparison):
        1. Exchange price (user searched in AH) - wins if newer than cloud
        2. Cloud price (community aggregate) - wins if newer than exchange
        3. Local price (other sources) - wins if newer than cloud
        4. Fallback price from user-provided file if cloud and local are unavailable

        This allows:
        - Hourly refresh: exchange prices remain if user searched recently
        - Daily midnight refresh: cloud prices take precedence after sync updates timestamps

        Returns the price in FE, or None if no price available.
        """
        from datetime import datetime

        season_id = season_id if season_id is not None else self._current_season_id
        season_id_filter = season_id if season_id is not None else 0

        # Get cloud price with timestamp
        cloud_row = self.db.fetchone(
            """SELECT price_fe_median, cloud_updated_at, unique_devices FROM cloud_price_cache
               WHERE config_base_id = ? AND season_id = ? AND unique_devices >= 1""",
            (config_base_id, season_id_filter),
        )

        # Get local price with timestamp and source
        local_row = self.db.fetchone(
            "SELECT price_fe, updated_at, source FROM prices WHERE config_base_id = ? AND season_id = ?",
            (config_base_id, season_id_filter),
        )

        cloud_price = cloud_row["price_fe_median"] if cloud_row else None
        local_price = local_row["price_fe"] if local_row else None
        local_source = local_row["source"] if local_row else None

        # Exchange-learned price takes precedence (user searched for this item in AH)
        # Uses timestamp comparison so that daily midnight refresh can override stale exchange prices
        if local_source == "exchange" and local_price is not None:
            # If no cloud price, exchange wins
            if not cloud_row:
                return local_price
            
            cloud_updated = cloud_row["cloud_updated_at"]
            local_updated = local_row["updated_at"] if local_row else None
            if cloud_updated and local_updated:
                try:
                    cloud_dt = datetime.fromisoformat(cloud_updated.replace("Z", "+00:00"))
                    local_dt = datetime.fromisoformat(local_updated.replace("Z", "+00:00"))
                    if cloud_dt.tzinfo is not None:
                        cloud_dt = cloud_dt.replace(tzinfo=None)
                    if local_dt.tzinfo is not None:
                        local_dt = local_dt.replace(tzinfo=None)
                    # Exchange price wins only if it's newer than cloud
                    if local_dt > cloud_dt:
                        return local_price
                    # Otherwise cloud wins (e.g., after midnight refresh)
                except (ValueError, AttributeError, TypeError):
                    # If parsing fails, prefer exchange (user's data)
                    return local_price
            else:
                # No timestamps to compare, prefer exchange
                return local_price

        # If cloud and local are both missing, try fallback
        if cloud_price is None and local_price is None:
            fallback = get_fallback_price(config_base_id)
            return fallback
        
        # If only one exists, use it
        if cloud_price is None:
            return local_price
        if local_price is None:
            return cloud_price

        # Both exist - compare timestamps
        # Local overrides only if it's newer than cloud
        cloud_updated = cloud_row["cloud_updated_at"] if cloud_row else None
        local_updated = local_row["updated_at"] if local_row else None

        if cloud_updated and local_updated:
            try:
                # Parse ISO format timestamps and normalize to naive UTC for comparison
                cloud_dt = datetime.fromisoformat(cloud_updated.replace("Z", "+00:00"))
                local_dt = datetime.fromisoformat(local_updated.replace("Z", "+00:00"))

                # Strip timezone info for comparison (both treated as UTC)
                if cloud_dt.tzinfo is not None:
                    cloud_dt = cloud_dt.replace(tzinfo=None)
                if local_dt.tzinfo is not None:
                    local_dt = local_dt.replace(tzinfo=None)

                if local_dt > cloud_dt:
                    return local_price
                else:
                    return cloud_price
            except (ValueError, AttributeError, TypeError):
                # If timestamp parsing fails, prefer cloud
                return cloud_price
        elif local_updated and not cloud_updated:
            # Cloud has no timestamp, prefer local if it has one
            return local_price
        else:
            # Default to cloud
            return cloud_price

    def get_effective_price_with_source(self, config_base_id: int, season_id: Optional[int] = None) -> tuple[Optional[float], Optional[str]]:
        """
        Get the effective price and its source for an item.
        Returns (price, source) where source is 'exchange', 'cloud', 'local', or 'fallback'.
        """
        from datetime import datetime

        season_id = season_id if season_id is not None else self._current_season_id
        season_id_filter = season_id if season_id is not None else 0

        cloud_row = self.db.fetchone(
            """SELECT price_fe_median, cloud_updated_at, unique_devices FROM cloud_price_cache
               WHERE config_base_id = ? AND season_id = ? AND unique_devices >= 1""",
            (config_base_id, season_id_filter),
        )

        local_row = self.db.fetchone(
            "SELECT price_fe, updated_at, source FROM prices WHERE config_base_id = ? AND season_id = ?",
            (config_base_id, season_id_filter),
        )

        cloud_price = cloud_row["price_fe_median"] if cloud_row else None
        local_price = local_row["price_fe"] if local_row else None
        local_source = local_row["source"] if local_row else None

        # Exchange-learned price check with timestamp comparison
        if local_source == "exchange" and local_price is not None:
            if not cloud_row:
                return (local_price, "exchange")
            
            cloud_updated = cloud_row["cloud_updated_at"]
            local_updated = local_row["updated_at"] if local_row else None
            if cloud_updated and local_updated:
                try:
                    cloud_dt = datetime.fromisoformat(cloud_updated.replace("Z", "+00:00"))
                    local_dt = datetime.fromisoformat(local_updated.replace("Z", "+00:00"))
                    if cloud_dt.tzinfo is not None:
                        cloud_dt = cloud_dt.replace(tzinfo=None)
                    if local_dt.tzinfo is not None:
                        local_dt = local_dt.replace(tzinfo=None)
                    if local_dt > cloud_dt:
                        return (local_price, "exchange")
                    # Cloud is newer, continue to cloud logic below
                except (ValueError, AttributeError, TypeError):
                    return (local_price, "exchange")
            else:
                return (local_price, "exchange")

        # Fallback check
        if cloud_price is None and local_price is None:
            fallback = get_fallback_price(config_base_id)
            return (fallback, "fallback") if fallback else (None, None)
        
        # Only one exists
        if cloud_price is None:
            return (local_price, local_source or "local")
        if local_price is None:
            return (cloud_price, "cloud")

        # Both exist - compare timestamps
        cloud_updated = cloud_row["cloud_updated_at"] if cloud_row else None
        local_updated = local_row["updated_at"] if local_row else None

        if cloud_updated and local_updated:
            try:
                cloud_dt = datetime.fromisoformat(cloud_updated.replace("Z", "+00:00"))
                local_dt = datetime.fromisoformat(local_updated.replace("Z", "+00:00"))
                if cloud_dt.tzinfo is not None:
                    cloud_dt = cloud_dt.replace(tzinfo=None)
                if local_dt.tzinfo is not None:
                    local_dt = local_dt.replace(tzinfo=None)
                if local_dt > cloud_dt:
                    return (local_price, local_source or "local")
                else:
                    return (cloud_price, "cloud")
            except (ValueError, AttributeError, TypeError):
                return (cloud_price, "cloud")
        elif local_updated and not cloud_updated:
            return (local_price, local_source or "local")
        else:
            return (cloud_price, "cloud")

    def get_all_prices(self, season_id: Optional[int] = None) -> list[Price]:
        """Get all prices, filtered by season (no cross-season mixing)."""
        # Use provided value or fall back to context
        season_id = season_id if season_id is not None else self._current_season_id
        season_id_filter = season_id if season_id is not None else 0

        rows = self.db.fetchall(
            "SELECT * FROM prices WHERE season_id = ?",
            (season_id_filter,),
        )
        return [self._row_to_price(row) for row in rows]

    def get_exchange_price_ids(self, season_id: Optional[int] = None) -> list[int]:
        """Get config_base_ids that have user-learned prices from AH (source='exchange')."""
        season_id = season_id if season_id is not None else self._current_season_id
        season_id_filter = season_id if season_id is not None else 0

        rows = self.db.fetchall(
            "SELECT config_base_id FROM prices WHERE season_id = ? AND source = 'exchange'",
            (season_id_filter,),
        )
        return [row["config_base_id"] for row in rows]

    def get_price_count(self, season_id: Optional[int] = None) -> int:
        """Get total number of prices in database, filtered by season."""
        # Use provided value or fall back to context
        season_id = season_id if season_id is not None else self._current_season_id
        season_id_filter = season_id if season_id is not None else 0

        row = self.db.fetchone(
            "SELECT COUNT(*) as cnt FROM prices WHERE season_id = ?",
            (season_id_filter,),
        )
        return row["cnt"] if row else 0

    def upsert_prices_batch(self, prices: list[Price]) -> None:
        """Insert or update multiple prices."""
        self.db.executemany(
            """INSERT OR REPLACE INTO prices
               (config_base_id, season_id, price_fe, source, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            [
                (
                    price.config_base_id,
                    price.season_id if price.season_id is not None else 0,
                    price.price_fe,
                    price.source,
                    price.updated_at.isoformat(),
                )
                for price in prices
            ],
        )

    def migrate_legacy_prices(self, target_season_id: int) -> int:
        """
        Migrate legacy prices (season_id=0) to a specific season.

        Args:
            target_season_id: The season to assign legacy prices to.

        Returns:
            Number of prices migrated.
        """
        # Count legacy prices first
        row = self.db.fetchone("SELECT COUNT(*) as cnt FROM prices WHERE season_id = 0")
        count = row["cnt"] if row else 0

        if count > 0:
            # Update legacy prices to target season
            self.db.execute(
                "UPDATE prices SET season_id = ? WHERE season_id = 0",
                (target_season_id,),
            )

        return count

    def _row_to_price(self, row) -> Price:
        keys = row.keys()
        season_id = row["season_id"] if "season_id" in keys else None
        # Convert 0 back to None (legacy/unknown)
        if season_id == 0:
            season_id = None
        return Price(
            config_base_id=row["config_base_id"],
            price_fe=row["price_fe"],
            source=row["source"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
            season_id=season_id,
        )

    def get_trade_tax_multiplier(self) -> float:
        """
        Get the trade tax multiplier based on settings.

        The Torchlight trade house takes 1 FE per 8 FE (12.5% tax).
        When enabled, values are multiplied by 0.875 to show after-tax amounts.

        Returns:
            1.0 if tax disabled, 0.875 if enabled
        """
        if self.get_setting("trade_tax_enabled") == "true":
            return 0.875  # 7/8 = 87.5% after 12.5% tax
        return 1.0

    def get_run_value(self, run_id: int) -> tuple[int, float]:
        """
        Calculate total value of a run's loot.

        Returns:
            Tuple of (raw_fe_gained, total_value_fe)
            - raw_fe_gained: Just the FE currency picked up
            - total_value_fe: FE + value of other items based on prices
              (with trade tax applied to non-FE items if enabled)
        """
        from titrack.parser.patterns import FE_CONFIG_BASE_ID

        summary = self.get_run_summary(run_id)
        raw_fe = summary.get(FE_CONFIG_BASE_ID, 0)
        total_value = float(raw_fe)

        tax_multiplier = self.get_trade_tax_multiplier()

        for config_id, quantity in summary.items():
            if config_id == FE_CONFIG_BASE_ID:
                continue
            if quantity <= 0:
                continue

            # Use effective price (cloud-first, local overrides if newer)
            price_fe = self.get_effective_price(config_id)

            if price_fe and price_fe > 0:
                # Apply trade tax to non-FE items (would need to sell them)
                total_value += price_fe * quantity * tax_multiplier

        return raw_fe, total_value

    def get_run_cost(self, run_id: int) -> tuple[dict[int, int], float, list[int]]:
        """
        Get map costs for a run (Spv3Open consumption).

        Args:
            run_id: The run ID to get costs for.

        Returns:
            Tuple of (cost_summary, total_cost_fe, unpriced_config_ids)
            - cost_summary: {config_base_id: quantity} (negative values for consumption)
            - total_cost_fe: Sum of priced items only (absolute value)
            - unpriced_config_ids: List of items without known prices
        """
        rows = self.db.fetchall(
            """SELECT config_base_id, SUM(delta) as total_delta
               FROM item_deltas
               WHERE run_id = ? AND proto_name = 'Spv3Open'
               GROUP BY config_base_id""",
            (run_id,),
        )
        summary = {row["config_base_id"]: row["total_delta"] for row in rows}

        total_cost = 0.0
        unpriced: list[int] = []

        for config_id, quantity in summary.items():
            price_fe = self.get_effective_price(config_id)
            if price_fe and price_fe > 0:
                # Use absolute value since quantity is negative (consumption)
                # No trade tax - items are consumed, not sold
                total_cost += abs(quantity) * price_fe
            else:
                unpriced.append(config_id)

        return summary, total_cost, unpriced

    # --- Data Management ---

    def clear_run_data(self) -> int:
        """
        Clear all run tracking data (runs and item_deltas).

        Preserves: items, prices, settings, slot_state, log_position.

        Returns:
            Number of runs deleted.
        """
        # Get count before deletion
        row = self.db.fetchone("SELECT COUNT(*) as cnt FROM runs")
        run_count = row["cnt"] if row else 0

        # Get raw connection for direct control
        conn = self.db.connection

        # Use explicit transaction for deletion
        conn.execute("BEGIN IMMEDIATE")
        try:
            # Delete item_deltas first (foreign key reference)
            conn.execute("DELETE FROM item_deltas")
            # Delete runs
            conn.execute("DELETE FROM runs")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

        # Force WAL checkpoint to ensure changes are written to main database
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception:
            pass  # Non-critical: checkpoint will happen naturally

        return run_count

    # --- Log Position ---

    def save_log_position(self, file_path: Path, position: int, file_size: int) -> None:
        """Save current log file position for resume."""
        # Guard against oversized integers (SQLite max is 2^63-1)
        MAX_SQLITE_INT = 9223372036854775807
        if position > MAX_SQLITE_INT or file_size > MAX_SQLITE_INT:
            print(f"WARNING: Log position overflow - position={position}, file_size={file_size}")
            # Clamp to max value to avoid crash
            position = min(position, MAX_SQLITE_INT)
            file_size = min(file_size, MAX_SQLITE_INT)

        conn = self.db.connection
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                """INSERT OR REPLACE INTO log_position
                   (id, file_path, position, file_size, updated_at)
                   VALUES (1, ?, ?, ?, ?)""",
                (str(file_path), position, file_size, datetime.now().isoformat()),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        # Force checkpoint (non-critical if it fails due to concurrent access)
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception:
            pass

    def get_log_position(self) -> Optional[tuple[Path, int, int]]:
        """
        Get saved log position.

        Returns:
            Tuple of (file_path, position, file_size) or None
        """
        row = self.db.fetchone("SELECT * FROM log_position WHERE id = 1")
        if not row:
            return None
        return (Path(row["file_path"]), row["position"], row["file_size"])

    def get_cumulative_loot(
        self, season_id: Optional[int] = None, player_id: Optional[str] = None
    ) -> list[dict]:
        """
        Get cumulative loot statistics across all runs.

        Aggregates all item deltas (positive quantities only) grouped by config_base_id.
        Excludes map costs (proto_name='Spv3Open') and gear page (PageId 100).

        Args:
            season_id: Filter by season (uses context if None)
            player_id: Filter by player (uses context if None)

        Returns:
            List of dicts with keys: config_base_id, total_quantity
        """
        # Use provided values or fall back to context
        season_id = season_id if season_id is not None else self._current_season_id
        player_id = player_id if player_id is not None else self._current_player_id

        # Return empty list if no player context is set
        if self._current_player_id is None and player_id is None:
            return []

        # Build query with appropriate filters
        # Only include items picked up during map runs not yet assigned to a session
        base_query = """
            SELECT config_base_id, SUM(delta) as total_quantity
            FROM item_deltas
            WHERE run_id IN (SELECT id FROM runs WHERE session_id IS NULL)
            AND (proto_name IS NULL OR proto_name != 'Spv3Open')
        """

        params: list = []

        # Filter by season/player
        if season_id is not None:
            base_query += " AND (season_id IS NULL OR season_id = ?)"
            params.append(season_id)
            base_query += " AND (player_id IS NULL OR player_id = ?)"
            params.append(player_id or '')

        # Exclude gear page
        if EXCLUDED_PAGES:
            placeholders = ",".join("?" * len(EXCLUDED_PAGES))
            base_query += f" AND page_id NOT IN ({placeholders})"
            params.extend(EXCLUDED_PAGES)

        # Group and filter for positive quantities only
        base_query += " GROUP BY config_base_id HAVING SUM(delta) > 0"

        rows = self.db.fetchall(base_query, tuple(params))
        return [
            {"config_base_id": row["config_base_id"], "total_quantity": row["total_quantity"]}
            for row in rows
        ]

    def get_completed_run_count(
        self, season_id: Optional[int] = None, player_id: Optional[str] = None
    ) -> int:
        """
        Get count of completed (non-hub) runs.

        Args:
            season_id: Filter by season (uses context if None)
            player_id: Filter by player (uses context if None)

        Returns:
            Number of completed runs
        """
        # Use provided values or fall back to context
        season_id = season_id if season_id is not None else self._current_season_id
        player_id = player_id if player_id is not None else self._current_player_id

        # Return 0 if no player context is set
        if self._current_player_id is None and player_id is None:
            return 0

        if season_id is not None:
            row = self.db.fetchone(
                """SELECT COUNT(*) as cnt FROM runs
                   WHERE session_id IS NULL
                   AND end_ts IS NOT NULL AND is_hub = 0
                   AND (season_id IS NULL OR season_id = ?)
                   AND (player_id IS NULL OR player_id = ?)""",
                (season_id, player_id or ''),
            )
        else:
            row = self.db.fetchone(
                "SELECT COUNT(*) as cnt FROM runs WHERE session_id IS NULL AND end_ts IS NOT NULL AND is_hub = 0"
            )
        return row["cnt"] if row else 0

    def get_total_run_duration(
        self, season_id: Optional[int] = None, player_id: Optional[str] = None
    ) -> float:
        """
        Get total duration of all completed (non-hub) runs in seconds.

        Args:
            season_id: Filter by season (uses context if None)
            player_id: Filter by player (uses context if None)

        Returns:
            Total duration in seconds
        """
        # Use provided values or fall back to context
        season_id = season_id if season_id is not None else self._current_season_id
        player_id = player_id if player_id is not None else self._current_player_id

        # Return 0 if no player context is set
        if self._current_player_id is None and player_id is None:
            return 0.0

        if season_id is not None:
            row = self.db.fetchone(
                """SELECT SUM(
                       (julianday(end_ts) - julianday(start_ts)) * 86400
                   ) as total_seconds
                   FROM runs
                   WHERE session_id IS NULL
                   AND end_ts IS NOT NULL AND is_hub = 0
                   AND (season_id IS NULL OR season_id = ?)
                   AND (player_id IS NULL OR player_id = ?)""",
                (season_id, player_id or ''),
            )
        else:
            row = self.db.fetchone(
                """SELECT SUM(
                       (julianday(end_ts) - julianday(start_ts)) * 86400
                   ) as total_seconds
                   FROM runs
                   WHERE session_id IS NULL
                   AND end_ts IS NOT NULL AND is_hub = 0"""
            )
        return row["total_seconds"] if row and row["total_seconds"] else 0.0

    def get_total_map_costs(
        self, season_id: Optional[int] = None, player_id: Optional[str] = None
    ) -> float:
        """
        Get total map costs across all runs.

        Args:
            season_id: Filter by season (uses context if None)
            player_id: Filter by player (uses context if None)

        Returns:
            Total map cost in FE
        """
        # Use provided values or fall back to context
        season_id = season_id if season_id is not None else self._current_season_id
        player_id = player_id if player_id is not None else self._current_player_id

        # Return 0 if no player context is set
        if self._current_player_id is None and player_id is None:
            return 0.0

        # Get all map cost deltas (Spv3Open events) for runs not yet in a session
        if season_id is not None:
            rows = self.db.fetchall(
                """SELECT config_base_id, SUM(delta) as total_delta
                   FROM item_deltas
                   WHERE run_id IN (SELECT id FROM runs WHERE session_id IS NULL)
                   AND proto_name = 'Spv3Open'
                   AND (season_id IS NULL OR season_id = ?)
                   AND (player_id IS NULL OR player_id = ?)
                   GROUP BY config_base_id""",
                (season_id, player_id or ''),
            )
        else:
            rows = self.db.fetchall(
                """SELECT config_base_id, SUM(delta) as total_delta
                   FROM item_deltas
                   WHERE run_id IN (SELECT id FROM runs WHERE session_id IS NULL)
                   AND proto_name = 'Spv3Open'
                   GROUP BY config_base_id"""
            )

        total_cost = 0.0

        for row in rows:
            config_id = row["config_base_id"]
            quantity = row["total_delta"]  # Negative for consumption
            price_fe = self.get_effective_price(config_id)
            if price_fe and price_fe > 0:
                # Use absolute value since quantity is negative
                # No trade tax - items are consumed, not sold
                total_cost += abs(quantity) * price_fe

        return total_cost

    # --- Sessions ---

    def create_session(
        self,
        name: str,
        total_play_seconds: float = 0.0,
        mapping_play_seconds: float = 0.0,
    ) -> dict:
        """
        Create a new farming session and associate unassigned runs.

        - Inserts a new row into sessions with current player context.
        - Links all runs that have session_id IS NULL (and match player context).
        - Calculates run_count and total_net_profit_fe from associated runs.
        - Does NOT delete runs/item_deltas (data preservation).

        Returns:
            Dict with the created session info.
        """
        player_id = self._current_player_id
        season_id = self._current_season_id
        created_at = datetime.now().isoformat()

        conn = self.db.connection
        conn.execute("BEGIN IMMEDIATE")
        try:
            # Insert session row
            cursor = conn.execute(
                """INSERT INTO sessions
                   (name, created_at, total_play_seconds, mapping_play_seconds,
                    run_count, total_net_profit_fe, player_id, season_id, status)
                   VALUES (?, ?, ?, ?, 0, 0, ?, ?, 'closed')""",
                (name, created_at, total_play_seconds, mapping_play_seconds,
                 player_id, season_id),
            )
            session_id = cursor.lastrowid

            # Link unassigned runs (session_id IS NULL) matching player context
            if season_id is not None:
                conn.execute(
                    """UPDATE runs SET session_id = ?
                       WHERE session_id IS NULL AND is_hub = 0
                       AND end_ts IS NOT NULL
                       AND (season_id IS NULL OR season_id = ?)
                       AND (player_id IS NULL OR player_id = ?)""",
                    (session_id, season_id, player_id or ''),
                )
            else:
                conn.execute(
                    """UPDATE runs SET session_id = ?
                       WHERE session_id IS NULL AND is_hub = 0
                       AND end_ts IS NOT NULL""",
                    (session_id,),
                )

            # Calculate run_count and total_net_profit_fe
            rows = conn.execute(
                "SELECT id FROM runs WHERE session_id = ? AND is_hub = 0",
                (session_id,),
            ).fetchall()

            run_count = len(rows)
            total_net_profit = 0.0

            for row in rows:
                rid = row[0]
                _, run_value = self.get_run_value(rid)
                _, run_cost, _ = self.get_run_cost(rid)
                total_net_profit += run_value - run_cost

            # Update session with calculated values
            conn.execute(
                """UPDATE sessions
                   SET run_count = ?, total_net_profit_fe = ?
                   WHERE id = ?""",
                (run_count, total_net_profit, session_id),
            )

            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

        return {
            "id": session_id,
            "name": name,
            "created_at": created_at,
            "total_play_seconds": total_play_seconds,
            "mapping_play_seconds": mapping_play_seconds,
            "run_count": run_count,
            "total_net_profit_fe": total_net_profit,
            "player_id": player_id,
            "season_id": season_id,
            "status": "closed",
        }

    def get_sessions(self) -> list[dict]:
        """
        Get all sessions for the current player context, ordered newest first.

        Returns:
            List of session dicts.
        """
        player_id = self._current_player_id
        season_id = self._current_season_id

        if season_id is not None:
            rows = self.db.fetchall(
                """SELECT * FROM sessions
                   WHERE (player_id IS NULL OR player_id = ?)
                   AND (season_id IS NULL OR season_id = ?)
                   ORDER BY created_at DESC""",
                (player_id or '', season_id),
            )
        else:
            rows = self.db.fetchall(
                "SELECT * FROM sessions ORDER BY created_at DESC"
            )

        result = []
        for row in rows:
            keys = row.keys()
            result.append({
                "id": row["id"],
                "name": row["name"],
                "created_at": row["created_at"],
                "total_play_seconds": row["total_play_seconds"] or 0.0,
                "mapping_play_seconds": row["mapping_play_seconds"] or 0.0,
                "run_count": row["run_count"] or 0,
                "total_net_profit_fe": row["total_net_profit_fe"] or 0.0,
                "status": row["status"] if "status" in keys else "closed",
            })
        return result

    def get_session_stats(self, session_id: int) -> dict:
        """
        Calculate detailed statistics for a session.

        Returns a dict with profitability, time, run metrics, deep analysis,
        and raw radar chart axis values.
        """
        # Get session row
        session_row = self.db.fetchone(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        )
        if not session_row:
            return {}

        session_name = session_row["name"]
        created_at = session_row["created_at"]
        total_play_seconds = session_row["total_play_seconds"] or 0.0
        mapping_play_seconds = session_row["mapping_play_seconds"] or 0.0

        # Get completed (non-hub) runs for this session
        run_rows = self.db.fetchall(
            """SELECT id, start_ts, end_ts, zone_signature FROM runs
               WHERE session_id = ? AND is_hub = 0 AND end_ts IS NOT NULL
               ORDER BY start_ts""",
            (session_id,),
        )

        run_count = len(run_rows)

        # Per-run profit calculation + season content (surgery) tracking
        run_profits: list[float] = []
        total_gross_value = 0.0
        total_entry_cost = 0.0
        surgery_run_count = 0
        surgery_profit = 0.0
        SURGERY_ZONE_KEY = "DiXiaZhenSuo"

        for rrow in run_rows:
            rid = rrow["id"]
            _, run_value = self.get_run_value(rid)
            _, run_cost, _ = self.get_run_cost(rid)
            net_profit = run_value - run_cost
            run_profits.append(net_profit)
            total_gross_value += run_value
            total_entry_cost += run_cost

            zone_sig = rrow["zone_signature"] or ""
            if SURGERY_ZONE_KEY in zone_sig:
                surgery_run_count += 1
                surgery_profit += net_profit

        total_net_profit = total_gross_value - total_entry_cost

        # Time-based metrics (safe division)
        mapping_minutes = mapping_play_seconds / 60.0 if mapping_play_seconds > 0 else 0.0
        mapping_hours = mapping_play_seconds / 3600.0 if mapping_play_seconds > 0 else 0.0
        total_minutes = total_play_seconds / 60.0 if total_play_seconds > 0 else 0.0
        total_hours = total_play_seconds / 3600.0 if total_play_seconds > 0 else 0.0

        profit_per_minute_mapping = (total_net_profit / mapping_minutes) if mapping_minutes > 0 else 0.0
        profit_per_hour_mapping = (total_net_profit / mapping_hours) if mapping_hours > 0 else 0.0
        profit_per_minute_total = (total_net_profit / total_minutes) if total_minutes > 0 else 0.0
        profit_per_hour_total = (total_net_profit / total_hours) if total_hours > 0 else 0.0

        # Run metrics
        runs_per_hour = (run_count / mapping_hours) if mapping_hours > 0 else 0.0

        # Average run duration from actual run timestamps
        run_durations: list[float] = []
        for rrow in run_rows:
            if rrow["start_ts"] and rrow["end_ts"]:
                start = datetime.fromisoformat(rrow["start_ts"])
                end = datetime.fromisoformat(rrow["end_ts"])
                run_durations.append((end - start).total_seconds())

        avg_run_seconds = (
            sum(run_durations) / len(run_durations) if run_durations else 0.0
        )

        avg_run_profit = (total_net_profit / run_count) if run_count > 0 else 0.0

        # Deep analysis metrics
        high_run_threshold_str = self.get_setting("high_run_threshold")
        high_run_threshold = float(high_run_threshold_str) if high_run_threshold_str else 100.0
        high_run_count = sum(1 for p in run_profits if p >= high_run_threshold)
        high_run_ratio = (high_run_count / run_count) if run_count > 0 else 0.0

        # Standard deviation (requires >= 2 values)
        if len(run_profits) >= 2:
            profit_stddev = statistics.stdev(run_profits)
        else:
            profit_stddev = 0.0

        # Coefficient of variation
        mean_profit = avg_run_profit
        profit_cv = (profit_stddev / abs(mean_profit)) if mean_profit != 0 else 0.0

        # Max profit
        max_run_profit = max(run_profits) if run_profits else 0.0

        # Median
        median_run_profit = statistics.median(run_profits) if run_profits else 0.0

        # Bottom 25% average
        if run_profits:
            sorted_profits = sorted(run_profits)
            bottom_count = max(1, len(sorted_profits) // 4)
            bottom_25 = sorted_profits[:bottom_count]
            bottom_25_avg = sum(bottom_25) / len(bottom_25)
        else:
            bottom_25_avg = 0.0

        # 상위 10% 평균 수익 (Top 10% mean)
        if run_profits:
            top_10_count = max(1, run_count // 10)
            sorted_desc = sorted(run_profits, reverse=True)
            top_10_avg = sum(sorted_desc[:top_10_count]) / top_10_count
        else:
            top_10_avg = 0.0

        # Radar chart raw values
        efficiency_ratio = (
            (mapping_play_seconds / total_play_seconds)
            if total_play_seconds > 0
            else 0.0
        )

        # Season content ratio (based on gross value to avoid >100% when net is low)
        surgery_income_ratio = (
            (surgery_profit / total_gross_value)
            if total_gross_value > 0
            else 0.0
        )

        # Cost ratio
        cost_ratio = (
            (total_entry_cost / total_gross_value)
            if total_gross_value > 0
            else 0.0
        )

        # Min run profit
        min_run_profit = min(run_profits) if run_profits else 0.0

        # Generate farming style tags
        tags = self._generate_tags(
            run_count=run_count,
            run_profits=run_profits,
            profit_cv=profit_cv,
            high_run_ratio=high_run_ratio,
            total_play_seconds=total_play_seconds,
            mapping_play_seconds=mapping_play_seconds,
            avg_run_seconds=avg_run_seconds,
            runs_per_hour=runs_per_hour,
            total_net_profit=total_net_profit,
            total_gross_value=total_gross_value,
            total_entry_cost=total_entry_cost,
            surgery_run_count=surgery_run_count,
            surgery_profit=surgery_profit,
            surgery_income_ratio=surgery_income_ratio,
            cost_ratio=cost_ratio,
            efficiency_ratio=efficiency_ratio,
            max_run_profit=max_run_profit,
            min_run_profit=min_run_profit,
        )

        return {
            "session_id": session_id,
            "name": session_name,
            "created_at": created_at,
            "run_count": run_count,
            "total_play_seconds": total_play_seconds,
            "mapping_play_seconds": mapping_play_seconds,
            # Profitability
            "total_gross_value_fe": total_gross_value,
            "total_entry_cost_fe": total_entry_cost,
            "total_net_profit_fe": total_net_profit,
            # Time-based
            "profit_per_minute_mapping": profit_per_minute_mapping,
            "profit_per_hour_mapping": profit_per_hour_mapping,
            "profit_per_minute_total": profit_per_minute_total,
            "profit_per_hour_total": profit_per_hour_total,
            # Run metrics
            "runs_per_hour": runs_per_hour,
            "avg_run_seconds": avg_run_seconds,
            "avg_run_profit_fe": avg_run_profit,
            # Deep analysis
            "high_run_count": high_run_count,
            "high_run_ratio": high_run_ratio,
            "profit_stddev": profit_stddev,
            "profit_cv": profit_cv,
            "max_run_profit_fe": max_run_profit,
            "median_run_profit_fe": median_run_profit,
            "bottom_25_avg_fe": bottom_25_avg,
            "top_10_avg_profit_fe": top_10_avg,
            "high_run_threshold": high_run_threshold,
            # Season content (surgery)
            "surgery_run_count": surgery_run_count,
            "surgery_profit_fe": surgery_profit,
            "surgery_income_ratio": surgery_income_ratio,
            # Cost analysis
            "cost_ratio": cost_ratio,
            # Farming style tags
            "tags": tags,
            # Radar chart axes (raw values, normalized during comparison)
            "radar_profitability": profit_per_hour_mapping,
            "radar_stability": 1 - profit_cv,  # raw; higher = more stable
            "radar_efficiency": efficiency_ratio,
            "radar_burst": high_run_ratio,
            "radar_speed": runs_per_hour,
            "radar_scale": total_net_profit,
        }

    def update_session_name(self, session_id: int, name: str) -> bool:
        """
        Update a session's name.

        Returns True if the row was updated, False otherwise.
        """
        cursor = self.db.execute(
            "UPDATE sessions SET name = ? WHERE id = ?",
            (name, session_id),
        )
        return cursor.rowcount > 0

    def delete_session(self, session_id: int) -> bool:
        """
        Delete a session and all its associated data.

        Deletes item_deltas for runs in the session, then runs, then the session.
        Uses a transaction for atomicity.

        Returns True if the session was deleted.
        """
        conn = self.db.connection
        conn.execute("BEGIN IMMEDIATE")
        try:
            # Delete item_deltas for runs belonging to this session
            conn.execute(
                """DELETE FROM item_deltas
                   WHERE run_id IN (SELECT id FROM runs WHERE session_id = ?)""",
                (session_id,),
            )
            # Delete runs belonging to this session
            conn.execute(
                "DELETE FROM runs WHERE session_id = ?",
                (session_id,),
            )
            # Delete the session itself
            cursor = conn.execute(
                "DELETE FROM sessions WHERE id = ?",
                (session_id,),
            )
            deleted = cursor.rowcount > 0
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

        # Force WAL checkpoint (non-critical if it fails due to concurrent access)
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception:
            pass
        return deleted

    def compare_sessions(self, session_ids: list[int]) -> dict:
        """
        Compare up to 3 sessions with normalized radar chart data and analysis.

        Args:
            session_ids: List of session IDs to compare (max 3).

        Returns:
            Dict with sessions stats, normalized radar, analysis, and recommendation.
        """
        session_ids = session_ids[:3]  # cap at 3

        sessions_stats: list[dict] = []
        for sid in session_ids:
            stats = self.get_session_stats(sid)
            if stats:
                sessions_stats.append(stats)

        if not sessions_stats:
            return {
                "sessions": [],
                "radar_normalized": [],
                "analysis": [],
                "recommendation": "",
            }

        # --- Radar normalization ---
        radar_axes = [
            "radar_profitability",
            "radar_efficiency",
            "radar_burst",
            "radar_speed",
            "radar_scale",
        ]

        radar_normalized: list[dict] = [{} for _ in sessions_stats]

        # Standard axes: higher = better, max = 100
        for axis in radar_axes:
            max_val = max(s.get(axis, 0) for s in sessions_stats)
            for i, s in enumerate(sessions_stats):
                if max_val > 0:
                    radar_normalized[i][axis.replace("radar_", "")] = (
                        s.get(axis, 0) / max_val
                    ) * 100
                else:
                    radar_normalized[i][axis.replace("radar_", "")] = 0

        # Stability: CV lower = better (inverse normalization)
        cvs = [s.get("profit_cv", 0) for s in sessions_stats]
        min_cv = min(cvs)
        max_cv = max(cvs)
        for i, s in enumerate(sessions_stats):
            cv = s.get("profit_cv", 0)
            if max_cv > min_cv:
                radar_normalized[i]["stability"] = 100 - (
                    (cv - min_cv) / (max_cv - min_cv)
                ) * 100
            else:
                # All sessions have same CV → all get 100
                radar_normalized[i]["stability"] = 100

        # --- Analysis comments ---
        analysis: list[dict] = []
        for s in sessions_stats:
            atype, summary = self._generate_analysis(s)
            analysis.append({
                "session_id": s["session_id"],
                "name": s["name"],
                "type": atype,
                "summary": summary,
            })

        # --- Recommendation ---
        recommendation = self._generate_recommendation(sessions_stats)

        return {
            "sessions": sessions_stats,
            "radar_normalized": radar_normalized,
            "analysis": analysis,
            "recommendation": recommendation,
        }

    @staticmethod
    def _generate_tags(**kwargs) -> list[dict]:
        """
        Generate farming style tags for a session based on various metrics.

        Returns a list of dicts: [{"id": "tag_id", "label": "태그명", "desc": "설명"}]
        """
        tags: list[dict] = []
        run_count = kwargs.get("run_count", 0)
        if run_count < 2:
            return tags

        run_profits = kwargs.get("run_profits", [])
        profit_cv = kwargs.get("profit_cv", 0)
        total_play_seconds = kwargs.get("total_play_seconds", 0)
        mapping_play_seconds = kwargs.get("mapping_play_seconds", 0)
        avg_run_seconds = kwargs.get("avg_run_seconds", 0)
        runs_per_hour = kwargs.get("runs_per_hour", 0)
        total_net_profit = kwargs.get("total_net_profit", 0)
        total_gross_value = kwargs.get("total_gross_value", 0)
        total_entry_cost = kwargs.get("total_entry_cost", 0)
        surgery_run_count = kwargs.get("surgery_run_count", 0)
        surgery_income_ratio = kwargs.get("surgery_income_ratio", 0)
        cost_ratio = kwargs.get("cost_ratio", 0)
        efficiency_ratio = kwargs.get("efficiency_ratio", 0)
        max_run_profit = kwargs.get("max_run_profit", 0)
        min_run_profit = kwargs.get("min_run_profit", 0)

        # 도파민중독자: 하이런과 로우런의 격차가 매우 큰 경우
        # IQR (사분위범위) 대비 범위가 크고 CV가 높은 경우
        if run_profits and profit_cv > 0.7:
            sorted_p = sorted(run_profits)
            q1_idx = len(sorted_p) // 4
            q3_idx = (3 * len(sorted_p)) // 4
            iqr = sorted_p[q3_idx] - sorted_p[q1_idx] if q3_idx > q1_idx else 0
            full_range = max_run_profit - min_run_profit
            if full_range > 0 and iqr > 0 and (full_range / iqr) > 3.0:
                tags.append({
                    "id": "dopamine_addict",
                    "label": "도파민중독자",
                    "desc": f"수익 변동 극심 (CV: {profit_cv:.1f}, 최대-최소: {full_range:.0f})",
                })

        # 안정성우선: 판당 소득차이가 작음
        if profit_cv < 0.35 and run_count >= 5:
            tags.append({
                "id": "stability_first",
                "label": "안정성우선",
                "desc": f"꾸준한 수익 (CV: {profit_cv:.2f})",
            })

        # 시즌컨텐츠중독자: 주요 소득이 시즌 컨텐츠에 몰림
        if surgery_run_count >= 3 and surgery_income_ratio > 0.4:
            tags.append({
                "id": "season_addict",
                "label": "시즌컨텐츠중독자",
                "desc": f"수술실 {surgery_run_count}회, 수익 비중 {surgery_income_ratio*100:.0f}%",
            })

        # 엉덩력GOAT: 총 플레이 시간 3시간 이상
        if total_play_seconds >= 10800:
            hours = total_play_seconds / 3600
            tags.append({
                "id": "endurance_goat",
                "label": "엉덩력GOAT",
                "desc": f"총 플레이 {hours:.1f}시간",
            })

        # 재빠른스핀: 평균 런 시간 50초 이내 + 시간당 40회 이상
        if avg_run_seconds > 0 and avg_run_seconds <= 50 and runs_per_hour >= 40:
            tags.append({
                "id": "fast_spin",
                "label": "재빠른스핀",
                "desc": f"평균 {avg_run_seconds:.0f}초/런, {runs_per_hour:.0f}회/시간",
            })

        # 여유를즐기는자: 맵핑/총 플레이 비율이 50% 미만
        if total_play_seconds > 0 and efficiency_ratio < 0.5:
            tags.append({
                "id": "leisurely",
                "label": "여유를즐기는자",
                "desc": f"맵핑 비율 {efficiency_ratio*100:.0f}% (나머지는 마을/거래소 등)",
            })

        # 입장료과다지출: 총 수익 대비 지출 비율이 높음
        if total_gross_value > 0 and cost_ratio > 0.3:
            tags.append({
                "id": "overspender",
                "label": "입장료과다지출",
                "desc": f"입장 비용이 총 수익의 {cost_ratio*100:.0f}%",
            })

        # HRHR (High Risk High Return): 지출도 크고 수익도 큰 경우
        if total_entry_cost > 500 and total_net_profit > 3000:
            tags.append({
                "id": "hrhr",
                "label": "HRHR",
                "desc": f"지출 {total_entry_cost:.0f} / 순수익 {total_net_profit:.0f} 결정",
            })

        # 파밍의신: 누적 수입 15000 결정 이상
        if total_net_profit >= 15000:
            tags.append({
                "id": "farming_god",
                "label": "파밍의신",
                "desc": f"누적 순수익 {total_net_profit:.0f} 결정",
            })

        return tags

    @staticmethod
    def _generate_analysis(stats: dict) -> tuple[str, str]:
        """Generate a farming style classification and summary for a session."""
        cv = stats.get("profit_cv", 0)
        hr = stats.get("high_run_ratio", 0)
        efficiency = stats.get("radar_efficiency", 0)
        runs_per_hour = stats.get("runs_per_hour", 0)

        if cv < 0.4 and hr < 0.1:
            return (
                "stable",
                "수익 편차가 낮아 꾸준한 수입을 기대할 수 있습니다. "
                "하이런 비율은 낮지만 안정적입니다.",
            )
        elif hr > 0.15 and cv > 0.5:
            return (
                "burst",
                "하이런 비율이 높아 대박 가능성이 크지만, "
                "수익 변동이 큽니다.",
            )
        elif efficiency > 0.7 and runs_per_hour > 30:
            return (
                "efficient",
                "빠른 런 속도와 높은 맵핑 효율로 "
                "시간 대비 성과가 좋습니다.",
            )
        else:
            return (
                "balanced",
                "전반적으로 균형 잡힌 파밍입니다.",
            )

    @staticmethod
    def _generate_recommendation(sessions_stats: list[dict]) -> str:
        """Generate a recommendation comparing sessions."""
        if not sessions_stats:
            return ""

        if len(sessions_stats) == 1:
            s = sessions_stats[0]
            atype, _ = Repository._generate_analysis(s)
            type_labels = {
                "stable": "안정형",
                "burst": "폭발형",
                "efficient": "효율형",
                "balanced": "균형형",
            }
            return (
                f"'{s['name']}'은(는) {type_labels.get(atype, '균형형')} "
                f"파밍 세션입니다."
            )

        best_profit = max(
            sessions_stats, key=lambda s: s.get("profit_per_hour_mapping", 0)
        )
        best_stable = min(
            sessions_stats, key=lambda s: s.get("profit_cv", float("inf"))
        )

        if best_profit["session_id"] == best_stable["session_id"]:
            return (
                f"'{best_profit['name']}'이(가) "
                f"수익성과 안정성 모두 우수합니다."
            )
        else:
            return (
                f"안정적 파밍을 원하면 '{best_stable['name']}', "
                f"높은 수익을 노리면 '{best_profit['name']}'"
            )
