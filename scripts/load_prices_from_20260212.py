#!/usr/bin/env python3
"""ref/v/20260212.txt 파일의 가격 데이터를 Supabase aggregated_prices 테이블에 로드

ref/v/20260212.txt:
{
  "100": { "name": "클로", "type": "장비", "price": 0 }
}

→ Supabase aggregated_prices:
{
  config_base_id: 100,
  season_id: 0,
  price_fe_median: 1.0,  # price=0인 경우 1.0 기본값
  price_fe_p10: 0.8,
  price_fe_p90: 1.2,
  submission_count: 1,
  unique_devices: 1
}

주의: price=0인 아이템은 기본 가격 1.0 FE로 설정됩니다.
"""

import os
import json
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


def load_20260212_file():
    """ref/v/20260212.txt 로드"""
    file_path = Path("ref") / "v" / "20260212.txt"

    if not file_path.exists():
        raise FileNotFoundError(f"파일 없음: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"  [OK] {len(data)}개 아이템 로드")
    return data


def prepare_price_data(items_data: dict, season_id: int = 0):
    """가격 데이터 준비 (price=0 → 기본값 1.0 FE)"""
    prices = []

    for config_id_str, item in items_data.items():
        config_id = int(config_id_str)
        price = item.get("price", 0)

        # price=0인 경우 기본값 1.0 FE (거래 불가능한 아이템)
        if price == 0:
            base_price = 1.0
        else:
            base_price = float(price)

        prices.append({
            "config_base_id": config_id,
            "season_id": season_id,
            "price_fe_median": base_price,
            "price_fe_p10": base_price * 0.8,
            "price_fe_p90": base_price * 1.2,
            "submission_count": 1,
            "unique_devices": 1
        })

    print(f"  [OK] {len(prices)}개 가격 데이터 준비 완료")
    return prices


def upload_prices_to_supabase(supabase, prices: list):
    """Supabase aggregated_prices 테이블에 배치 UPSERT"""
    batch_size = 100
    uploaded = 0
    errors = 0

    for i in range(0, len(prices), batch_size):
        batch = prices[i:i+batch_size]

        try:
            supabase.table("aggregated_prices").upsert(batch).execute()
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
    print("TITrack - 20260212.txt 가격 데이터 → Supabase 로드")
    print("=" * 80)

    # Supabase 연결
    print("\n[1/5] Supabase 연결 중...")
    supabase_url = os.getenv("TITRACK_SUPABASE_URL")
    supabase_key = os.getenv("TITRACK_SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        print("  [ERROR] Supabase credentials 없음")
        print("     .env 파일에 TITRACK_SUPABASE_URL, TITRACK_SUPABASE_KEY 설정 필요")
        exit(1)

    supabase = create_client(supabase_url, supabase_key)
    print(f"  [OK] 연결 성공: {supabase_url}")

    # 20260212.txt 로드
    print("\n[2/5] ref/v/20260212.txt 로드 중...")
    try:
        items_data = load_20260212_file()
    except Exception as e:
        print(f"  [ERROR] 파일 로드 실패: {e}")
        exit(1)

    # 가격 데이터 준비
    print("\n[3/5] 가격 데이터 준비 중...")
    prices = prepare_price_data(items_data, season_id=0)

    # Supabase 업로드
    print(f"\n[4/5] Supabase 업로드 중 ({len(prices)}개)...")
    try:
        stats = upload_prices_to_supabase(supabase, prices)
        print(f"\n  [OK] 업로드 완료!")
        print(f"     Total: {stats['total']}")
        print(f"     Uploaded: {stats['uploaded']}")
        print(f"     Errors: {stats['errors']}")
    except Exception as e:
        print(f"  [ERROR] 업로드 실패: {e}")
        exit(1)

    # 검증
    print("\n[5/5] 검증 중...")
    count = verify_upload(supabase)
    if count >= 0:
        print(f"  [OK] Supabase aggregated_prices: {count} rows")
    else:
        print("  [WARNING] 검증 실패 (위 에러 참조)")

    print("\n" + "=" * 80)
    print("[완료] 가격 데이터 로드 완료!")
    print("=" * 80)
    print("\n주의: price=0인 아이템은 기본값 1.0 FE로 설정되었습니다.")
    print("      실제 거래소 가격이 있는 경우 수동으로 업데이트 필요합니다.")
    print()


if __name__ == "__main__":
    main()
