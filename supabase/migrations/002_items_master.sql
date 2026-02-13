-- ============================================================================
-- TITrack Cloud Sync v2 - Items Master Schema
-- Migration 002: Add items master table for centralized item metadata
-- ============================================================================
-- Author: Backend Agent
-- Date: 2026-02-12
-- Dependencies: 001_initial_schema.sql
-- Rollback: See section at bottom
-- ============================================================================

-- ============================================================================
-- SCHEMA VERSION TRACKING
-- ============================================================================

-- Schema version table (tracks migration history)
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Record initial version (retroactive)
INSERT INTO schema_version (version, description, applied_at)
VALUES (1, 'Initial price crowdsourcing schema', '2026-02-01 00:00:00+00')
ON CONFLICT (version) DO NOTHING;

-- Record current migration
INSERT INTO schema_version (version, description)
VALUES (2, 'Added items master table for centralized item metadata');

-- ============================================================================
-- ITEMS MASTER TABLE
-- ============================================================================

-- Items master table - centralized item metadata (SSOT)
CREATE TABLE IF NOT EXISTS items (
    -- Primary key
    config_base_id INTEGER PRIMARY KEY,

    -- Names (multilingual)
    name_ko TEXT,                  -- Korean name (primary for TITrack Korean)
    name_en TEXT,                  -- English name (fallback)
    name_cn TEXT,                  -- Chinese name (original game data)

    -- Types (multilingual)
    type_ko TEXT,                  -- Korean type (화폐, 장비, 재료, 스킬, 레전드)
    type_en TEXT,                  -- English type (currency, equipment, material, skill, legendary)

    -- Media
    icon_url TEXT,                 -- CDN icon URL (used by frontend)
    url_tlidb TEXT,                -- TLIDB item page link (reference)

    -- Classification
    category TEXT,                 -- Major category: currency, material, equipment, skill, legendary
    subcategory TEXT,              -- Minor category: claw, hammer, sword, axe, dagger, etc.
    tier INTEGER,                  -- Item tier (1-10, higher = rarer)

    -- Properties
    tradeable BOOLEAN DEFAULT TRUE,    -- Can be traded on auction house
    stackable BOOLEAN DEFAULT TRUE,    -- Can stack in inventory

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Index for category filtering (e.g., "show all equipment")
CREATE INDEX IF NOT EXISTS idx_items_category
    ON items(category);

-- Index for subcategory filtering (e.g., "show all claws")
CREATE INDEX IF NOT EXISTS idx_items_subcategory
    ON items(subcategory);

-- Index for tier filtering (e.g., "show tier 5+ items")
CREATE INDEX IF NOT EXISTS idx_items_tier
    ON items(tier);

-- Index for delta sync (clients fetch items updated after last sync)
CREATE INDEX IF NOT EXISTS idx_items_updated
    ON items(updated_at);

-- Index for tradeable items (auction house queries)
CREATE INDEX IF NOT EXISTS idx_items_tradeable
    ON items(tradeable) WHERE tradeable = TRUE;

-- Composite index for common query pattern (category + tier)
CREATE INDEX IF NOT EXISTS idx_items_category_tier
    ON items(category, tier);

-- ============================================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================================

-- Enable RLS on items table
ALTER TABLE items ENABLE ROW LEVEL SECURITY;

-- Policy: Public read access (items are public metadata)
CREATE POLICY "Public read access for items"
    ON items
    FOR SELECT
    TO anon, authenticated
    USING (true);

-- Note: No INSERT/UPDATE/DELETE policies = only admins can modify
-- (admin = service_role key, not exposed to clients)

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Function: Fetch items with optional delta sync
-- Used by clients to download item metadata
CREATE OR REPLACE FUNCTION fetch_items_delta(
    p_since TIMESTAMPTZ DEFAULT NULL
)
RETURNS SETOF items
LANGUAGE sql
STABLE
SECURITY DEFINER
AS $$
    SELECT * FROM items
    WHERE p_since IS NULL OR updated_at > p_since
    ORDER BY config_base_id;
$$;

-- Grant execute to anonymous users (clients don't need authentication for metadata)
GRANT EXECUTE ON FUNCTION fetch_items_delta TO anon;
GRANT EXECUTE ON FUNCTION fetch_items_delta TO authenticated;

-- Function: Update item's updated_at timestamp (for delta sync)
CREATE OR REPLACE FUNCTION update_item_timestamp()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

-- Trigger: Auto-update updated_at on item modification
CREATE TRIGGER items_updated_at_trigger
    BEFORE UPDATE ON items
    FOR EACH ROW
    EXECUTE FUNCTION update_item_timestamp();

-- ============================================================================
-- STATISTICS
-- ============================================================================

-- Function: Get item statistics (for monitoring)
CREATE OR REPLACE FUNCTION get_item_stats()
RETURNS TABLE (
    total_items BIGINT,
    items_with_ko_name BIGINT,
    items_with_icon BIGINT,
    items_by_category JSONB,
    avg_tier NUMERIC
)
LANGUAGE sql
STABLE
AS $$
    WITH stats AS (
        SELECT
            COUNT(*) AS total_items,
            COUNT(name_ko) AS items_with_ko_name,
            COUNT(icon_url) AS items_with_icon,
            AVG(tier) AS avg_tier
        FROM items
    ),
    categories AS (
        SELECT jsonb_object_agg(category, cnt) AS items_by_category
        FROM (
            SELECT category, COUNT(*) AS cnt
            FROM items
            WHERE category IS NOT NULL
            GROUP BY category
        ) cat_counts
    )
    SELECT
        stats.total_items,
        stats.items_with_ko_name,
        stats.items_with_icon,
        COALESCE(categories.items_by_category, '{}'::jsonb) AS items_by_category,
        stats.avg_tier
    FROM stats
    CROSS JOIN categories;
$$;

GRANT EXECUTE ON FUNCTION get_item_stats TO anon;
GRANT EXECUTE ON FUNCTION get_item_stats TO authenticated;

-- ============================================================================
-- VERIFICATION QUERIES (run these after migration)
-- ============================================================================

-- Check table creation
-- SELECT COUNT(*) FROM items;  -- Should be 0 initially

-- Check indexes
-- SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'items';

-- Check RLS policies
-- SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual
-- FROM pg_policies WHERE tablename = 'items';

-- Test fetch function (no data yet, should return empty)
-- SELECT * FROM fetch_items_delta();

-- Check schema version
-- SELECT * FROM schema_version ORDER BY version;

-- ============================================================================
-- DATA LOADING NOTES
-- ============================================================================

-- After running this migration, load initial data using:
-- python scripts/load_items_to_supabase.py
--
-- Data sources:
-- 1. src/titrack/data/items_ko.json (3,300 items)
-- 2. ref/v/full_table.json (2,447 items)
-- 3. src/titrack/data/icon_urls.py (270 icon mappings)
--
-- Expected result: ~3,500 unique items

-- ============================================================================
-- ROLLBACK SCRIPT (if migration needs to be reverted)
-- ============================================================================

-- To rollback this migration, run:
-- DROP TRIGGER IF EXISTS items_updated_at_trigger ON items;
-- DROP FUNCTION IF EXISTS update_item_timestamp CASCADE;
-- DROP FUNCTION IF EXISTS get_item_stats CASCADE;
-- DROP FUNCTION IF EXISTS fetch_items_delta CASCADE;
-- DROP TABLE IF EXISTS items CASCADE;
-- DELETE FROM schema_version WHERE version = 2;

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================
