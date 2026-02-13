#!/usr/bin/env python3
"""로컬 DB의 가격 데이터를 Supabase aggregated_prices 테이블로 업로드

로컬 SQLite DB의 prices 테이블 (exchange 출처)에서 가격 데이터를 가져와서
Supabase aggregated_prices 테이블에 UPSERT합니다.

Usage:
    python scripts/upload_local_prices_to_supabase.py
"""

import os
import sqlite3
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed, using environment variables only")

try:
    from supabase import create_client, Client
except ImportError:
    print("Error: supabase package not installed")
    print("Please install: pip install supabase")
    exit(1)


def get_local_db_path() -> Path:
    """로컬 DB 경로 가져오기"""
    # 포터블 모드 확인
    portable_db = Path("data") / "tracker.db"
    if portable_db.exists():
        return portable_db

    # 기본 모드
    localappdata = os.getenv("LOCALAPPDATA")
    if not localappdata:
        raise RuntimeError("LOCALAPPDATA environment variable not set")

    default_db = Path(localappdata) / "TITrack" / "tracker.db"
    if not default_db.exists():
        raise FileNotFoundError(f"Local database not found: {default_db}")

    return default_db


def load_local_prices(db_path: Path) -> list[tuple]:
    """로컬 DB에서 exchange 출처 가격 데이터 로드

    Returns:
        List of tuples: (config_base_id, season_id, price_fe, updated_at)
    """
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("""
        SELECT config_base_id, season_id, price_fe, updated_at
        FROM prices
        WHERE source = 'exchange'
          AND price_fe > 0
        ORDER BY config_base_id, season_id
    """)

    prices = cursor.fetchall()
    conn.close()

    return prices


def upload_to_supabase(supabase: Client, prices: list[tuple]) -> dict:
    """Supabase aggregated_prices 테이블에 업로드

    Args:
        supabase: Supabase client
        prices: List of (config_base_id, season_id, price_fe, updated_at)

    Returns:
        Dict with upload statistics: {total, uploaded, errors}
    """
    total = len(prices)
    uploaded = 0
    errors = 0
    batch_size = 50

    batch = []
    for config_id, season_id, price_fe, updated_at in prices:
        # NULL season_id → 0
        if season_id is None:
            season_id = 0

        # ISO 8601 timestamp (기본값: 현재 시각)
        if not updated_at:
            updated_at = datetime.utcnow().isoformat() + "Z"
        elif not updated_at.endswith("Z"):
            # SQLite datetime → ISO 8601
            try:
                dt = datetime.fromisoformat(updated_at.replace("Z", ""))
                updated_at = dt.isoformat() + "Z"
            except ValueError:
                updated_at = datetime.utcnow().isoformat() + "Z"

        batch.append({
            "config_base_id": config_id,
            "season_id": season_id,
            "price_fe_median": price_fe,
            "price_fe_p10": price_fe,
            "price_fe_p90": price_fe,
            "submission_count": 1,
            "unique_devices": 1,
            "updated_at": updated_at
        })

        # 배치 업로드
        if len(batch) >= batch_size:
            try:
                supabase.table("aggregated_prices").upsert(batch).execute()
                uploaded += len(batch)
                print(f"  Uploaded batch: {uploaded}/{total} ({uploaded*100//total}%)")
            except Exception as e:
                print(f"  Error uploading batch: {e}")
                errors += len(batch)
            batch = []

    # 남은 배치 업로드
    if batch:
        try:
            supabase.table("aggregated_prices").upsert(batch).execute()
            uploaded += len(batch)
            print(f"  Uploaded batch: {uploaded}/{total} (100%)")
        except Exception as e:
            print(f"  Error uploading final batch: {e}")
            errors += len(batch)

    return {
        "total": total,
        "uploaded": uploaded,
        "errors": errors
    }


def verify_upload(supabase: Client) -> int:
    """Supabase aggregated_prices 테이블 행 수 확인

    Returns:
        Row count in aggregated_prices table
    """
    try:
        result = supabase.table("aggregated_prices").select("*", count="exact").execute()
        return result.count
    except Exception as e:
        print(f"  Error verifying upload: {e}")
        return -1


def main():
    print("=" * 80)
    print("TITrack - 로컬 가격 데이터 -> Supabase 업로드")
    print("=" * 80)
    print()

    # 1. Supabase 연결
    print("[1/5] Supabase 연결 중...")
    supabase_url = os.getenv("TITRACK_SUPABASE_URL")
    supabase_key = os.getenv("TITRACK_SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        print("  [ERROR] Supabase credentials not found")
        print("     Please set TITRACK_SUPABASE_URL and TITRACK_SUPABASE_KEY")
        print("     in .env file or environment variables")
        exit(1)

    try:
        supabase = create_client(supabase_url, supabase_key)
        print(f"  [OK] Connected to Supabase: {supabase_url}")
    except Exception as e:
        print(f"  [ERROR] Error connecting to Supabase: {e}")
        exit(1)

    # 2. 로컬 DB 경로 확인
    print()
    print("[2/5] 로컬 DB 확인 중...")
    try:
        db_path = get_local_db_path()
        print(f"  [OK] Local DB found: {db_path}")
    except Exception as e:
        print(f"  [ERROR] {e}")
        exit(1)

    # 3. 로컬 가격 데이터 로드
    print()
    print("[3/5] 로컬 가격 데이터 로드 중...")
    try:
        prices = load_local_prices(db_path)
        print(f"  [OK] Loaded {len(prices)} exchange prices from local DB")

        if len(prices) == 0:
            print("  [WARNING] No exchange prices found in local DB")
            print("     Exiting...")
            exit(0)
    except Exception as e:
        print(f"  [ERROR] Error loading local prices: {e}")
        exit(1)

    # 4. Supabase 업로드
    print()
    print("[4/5] Supabase 업로드 중...")
    try:
        stats = upload_to_supabase(supabase, prices)
        print(f"  [OK] Upload complete!")
        print(f"     Total: {stats['total']}")
        print(f"     Uploaded: {stats['uploaded']}")
        print(f"     Errors: {stats['errors']}")
    except Exception as e:
        print(f"  [ERROR] Error uploading to Supabase: {e}")
        exit(1)

    # 5. 검증
    print()
    print("[5/5] 검증 중...")
    try:
        count = verify_upload(supabase)
        if count >= 0:
            print(f"  [OK] Verification: {count} rows in Supabase aggregated_prices")
        else:
            print("  [WARNING] Verification failed (see error above)")
    except Exception as e:
        print(f"  [ERROR] Error verifying upload: {e}")

    print()
    print("=" * 80)
    print("[DONE] 업로드 완료!")
    print("=" * 80)


if __name__ == "__main__":
    main()
