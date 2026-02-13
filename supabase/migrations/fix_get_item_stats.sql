-- ============================================================================
-- TITrack Cloud Sync v2 - Fix get_item_stats() Function
-- Hotfix: Resolve "column reference 'category' is ambiguous" error
-- ============================================================================
-- Author: Backend Agent
-- Date: 2026-02-12
-- Issue: Migration 002의 get_item_stats() 함수에서 CROSS JOIN 사용 시 ambiguous column 에러
-- Fix: CTE 패턴으로 재작성, category IS NOT NULL 필터 추가
-- ============================================================================

-- Drop existing function
DROP FUNCTION IF EXISTS get_item_stats CASCADE;

-- Recreate with fixed logic
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

-- Restore permissions
GRANT EXECUTE ON FUNCTION get_item_stats TO anon;
GRANT EXECUTE ON FUNCTION get_item_stats TO authenticated;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Test the function (should return stats, no error)
-- SELECT * FROM get_item_stats();

-- Expected output (before data load):
-- total_items | items_with_ko_name | items_with_icon | items_by_category | avg_tier
-- ------------+--------------------+-----------------+-------------------+----------
--           0 |                  0 |               0 | {}                | null

-- ============================================================================
-- USAGE NOTES
-- ============================================================================
-- 이 파일은 Migration 002를 실행한 후 에러가 발생했을 때만 실행하세요.
-- Migration 002를 아직 실행하지 않았다면, 수정된 002_items_master.sql을 실행하세요.
--
-- Supabase SQL Editor에서 실행:
-- 1. Supabase Dashboard → SQL Editor → New Query
-- 2. 이 파일 내용을 붙여넣기
-- 3. Run 클릭
-- 4. SELECT * FROM get_item_stats(); 로 검증
-- ============================================================================
