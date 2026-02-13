#!/usr/bin/env python3
"""로컬 DB exchange 가격 + 20260212.txt 가격을 Supabase에 한 번에 업로드

1. 로컬 DB prices 테이블 (source='exchange') → aggregated_prices
2. ref/v/20260212.txt → aggregated_prices (중복 제외)
"""

import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime
import sys
import codecs

# Windows 콘솔 UTF-8 강제 설정 (한글 깨짐 방지)
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')



try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from supabase import create_client
except ImportError:
    print("Error: supabase package not installed")
    print("Install: pip install supabase")
    exit(1)


def get_local_db_path() -> Path:
    """로컬 DB 경로 가져오기"""
    portable_db = Path("data") / "tracker.db"
    if portable_db.exists():
        return portable_db

    localappdata = os.getenv("LOCALAPPDATA")
    if not localappdata:
        raise RuntimeError("LOCALAPPDATA not set")

    default_db = Path(localappdata) / "TITrack" / "tracker.db"
    if not default_db.exists():
        raise FileNotFoundError(f"Local DB not found: {default_db}")

    return default_db


def load_exchange_prices_from_local_db(db_path: Path) -> dict:
    """로컬 DB에서 exchange 가격 로드 (config_base_id → price)"""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("""
        SELECT config_base_id, season_id, price_fe, updated_at
        FROM prices
        WHERE source = 'exchange'
          AND price_fe > 0
        ORDER BY config_base_id, season_id
    """)

    prices = {}
    for config_id, season_id, price_fe, updated_at in cursor.fetchall():
        if season_id is None:
            season_id = 0

        key = (config_id, season_id)
        prices[key] = {
            "config_base_id": config_id,
            "season_id": season_id,
            "price_fe_median": price_fe,
            "price_fe_p10": price_fe,
            "price_fe_p90": price_fe,
            "submission_count": 1,
            "unique_devices": 1,
            "source": "local_exchange",
            "updated_at": updated_at or datetime.utcnow().isoformat() + "Z"
        }

    conn.close()

    print(f"  [OK] 로컬 DB: {len(prices)}개 exchange 가격")
    return prices


def load_prices_from_20260212(file_path: Path, season_id: int = 0) -> dict:
    """ref/v/20260212.txt에서 가격 로드 (config_base_id → price)"""
    if not file_path.exists():
        print(f"  [WARNING] 파일 없음: {file_path} (스킵)")
        return {}

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    prices = {}
    for config_id_str, item in data.items():
        config_id = int(config_id_str)
        price = item.get("price", 0)

        # price=0 → 1.0 FE 기본값
        if price == 0:
            base_price = 1.0
        else:
            base_price = float(price)

        key = (config_id, season_id)
        prices[key] = {
            "config_base_id": config_id,
            "season_id": season_id,
            "price_fe_median": base_price,
            "price_fe_p10": base_price * 0.8,
            "price_fe_p90": base_price * 1.2,
            "submission_count": 1,
            "unique_devices": 1,
            "source": "20260212.txt"
        }

    print(f"  [OK] 20260212.txt: {len(prices)}개 가격")
    return prices


def merge_prices(local_prices: dict, file_prices: dict) -> list:
    """두 소스 병합 (local exchange 우선, 중복 제외)"""
    merged = {}

    # 1. local exchange 가격 (우선순위 높음)
    for key, price in local_prices.items():
        merged[key] = price

    # 2. 20260212.txt 가격 (local에 없는 것만 추가)
    added_from_file = 0
    for key, price in file_prices.items():
        if key not in merged:
            merged[key] = price
            added_from_file += 1

    print(f"\n  병합 결과:")
    print(f"    - Local exchange: {len(local_prices)}개")
    print(f"    - 20260212.txt (신규): {added_from_file}개")
    print(f"    - 총합: {len(merged)}개")

    return list(merged.values())


def upload_prices_to_supabase(supabase, prices: list):
    """Supabase aggregated_prices 테이블에 배치 UPSERT"""
    batch_size = 100
    uploaded = 0
    errors = 0

    for i in range(0, len(prices), batch_size):
        batch = prices[i:i+batch_size]

        # source, updated_at 필드 제거 (Supabase 스키마에 없음)
        clean_batch = []
        for price in batch:
            clean_price = {k: v for k, v in price.items() if k not in ["source", "updated_at"]}
            clean_batch.append(clean_price)

        try:
            supabase.table("aggregated_prices").upsert(clean_batch).execute()
            uploaded += len(batch)
            print(f"  진행: {uploaded}/{len(prices)} ({uploaded*100//len(prices)}%)")
        except Exception as e:
            print(f"  [ERROR] 배치 업로드 실패: {e}")
            errors += len(batch)

    return {
        "total": len(prices),
        "uploaded": uploaded,
        "errors": errors
    }


def verify_upload(supabase):
    """Supabase aggregated_prices 테이블 검증"""
    try:
        result = supabase.table("aggregated_prices").select("*", count="exact").limit(0).execute()
        return result.count
    except Exception as e:
        print(f"  [ERROR] 검증 실패: {e}")
        return -1


def main():
    print("=" * 80)
    print("TITrack - 모든 가격 데이터 → Supabase 업로드")
    print("=" * 80)

    # Supabase 연결
    print("\n[1/6] Supabase 연결 중...")
    supabase_url = os.getenv("TITRACK_SUPABASE_URL")
    supabase_key = os.getenv("TITRACK_SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        print("  [ERROR] Supabase credentials 없음")
        print("     .env 파일에 TITRACK_SUPABASE_URL, TITRACK_SUPABASE_KEY 설정 필요")
        exit(1)

    supabase = create_client(supabase_url, supabase_key)
    print(f"  [OK] 연결 성공: {supabase_url}")

    # 로컬 DB 경로
    print("\n[2/6] 로컬 DB 확인 중...")
    try:
        db_path = get_local_db_path()
        print(f"  [OK] 로컬 DB: {db_path}")
    except Exception as e:
        print(f"  [WARNING] 로컬 DB 없음: {e} (스킵)")
        db_path = None

    # 가격 데이터 로드
    print("\n[3/6] 가격 데이터 로드 중...")

    local_prices = {}
    if db_path:
        try:
            local_prices = load_exchange_prices_from_local_db(db_path)
        except Exception as e:
            print(f"  [WARNING] 로컬 DB 가격 로드 실패: {e} (스킵)")

    file_prices = {}
    file_path = Path("ref") / "v" / "20260212.txt"
    try:
        file_prices = load_prices_from_20260212(file_path)
    except Exception as e:
        print(f"  [WARNING] 20260212.txt 로드 실패: {e} (스킵)")

    if not local_prices and not file_prices:
        print("\n  [ERROR] 로드할 가격 데이터가 없습니다")
        exit(1)

    # 병합
    print("\n[4/6] 가격 데이터 병합 중...")
    merged_prices = merge_prices(local_prices, file_prices)

    if not merged_prices:
        print("  [ERROR] 병합 실패 (데이터 없음)")
        exit(1)

    # Supabase 업로드
    print(f"\n[5/6] Supabase 업로드 중 ({len(merged_prices)}개)...")
    try:
        stats = upload_prices_to_supabase(supabase, merged_prices)
        print(f"\n  [OK] 업로드 완료!")
        print(f"     Total: {stats['total']}")
        print(f"     Uploaded: {stats['uploaded']}")
        print(f"     Errors: {stats['errors']}")
    except Exception as e:
        print(f"  [ERROR] 업로드 실패: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

    # 검증
    print("\n[6/6] 검증 중...")
    count = verify_upload(supabase)
    if count >= 0:
        print(f"  [OK] Supabase aggregated_prices: {count} rows")
    else:
        print("  [WARNING] 검증 실패 (위 에러 참조)")

    print("\n" + "=" * 80)
    print("[완료] 모든 가격 데이터 업로드 완료!")
    print("=" * 80)
    print("\n우선순위:")
    print("  1. 로컬 DB exchange 가격 (실제 거래소 가격)")
    print("  2. 20260212.txt 가격 (폴백)")
    print()


if __name__ == "__main__":
    main()
