#!/usr/bin/env python3
"""
TITrack - Load Equipment Data to Supabase

이 스크립트는 ref/v/20260212.txt의 장비 아이템 2,447개를 Supabase에 업로드합니다.

실행 전 준비:
1. .env 파일에 TITRACK_SUPABASE_URL, TITRACK_SUPABASE_KEY 설정
2. Supabase Dashboard에서 002_items_master.sql Migration 실행

실행:
    python scripts/load_equipment_data.py
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

# .env 파일 자동 로드
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"[OK] Loaded .env from {env_path}")
    else:
        print(f"[!] .env file not found at {env_path}")
except ImportError:
    # python-dotenv 없으면 수동 로드
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        with open(env_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
        print(f"[OK] Manually loaded .env from {env_path}")
    else:
        print(f"[!] .env file not found at {env_path}")

# Supabase client
try:
    from supabase import create_client, Client
except ImportError:
    print("Error: supabase package not installed")
    print("Install with: pip install titrack[cloud]")
    sys.exit(1)


def load_env() -> tuple[str, str]:
    """환경 변수 로드"""
    url = os.environ.get("TITRACK_SUPABASE_URL")
    key = os.environ.get("TITRACK_SUPABASE_KEY")

    if not url or not key:
        print("Error: TITRACK_SUPABASE_URL and TITRACK_SUPABASE_KEY must be set")
        print("\nSet them in .env file or as environment variables:")
        print("  TITRACK_SUPABASE_URL=https://dxuxdnglefrxtqvfitho.supabase.co")
        print("  TITRACK_SUPABASE_KEY=sb_secret_...")
        sys.exit(1)

    return url, key


def infer_tier(config_id: int) -> int:
    """ConfigBaseId에서 티어 추론"""
    if config_id >= 10000:
        return 10
    elif config_id >= 5000:
        return 8
    elif config_id >= 2000:
        return 6
    elif config_id >= 1000:
        return 4
    else:
        return 2


def infer_subcategory(config_id: int) -> Optional[str]:
    """ConfigBaseId에서 장비 서브카테고리 추론"""
    if 100 <= config_id < 200:
        return "claw"
    elif 200 <= config_id < 400:
        return "hammer"
    elif 400 <= config_id < 500:
        return "sword"
    elif 500 <= config_id < 600:
        return "axe"
    elif 600 <= config_id < 800:
        return "dagger"
    elif 800 <= config_id < 1000:
        return "bow"
    elif 1000 <= config_id < 1200:
        return "staff"
    elif 1200 <= config_id < 1400:
        return "wand"
    elif 2000 <= config_id < 2500:
        return "helmet"
    elif 2500 <= config_id < 3000:
        return "armor"
    elif 3000 <= config_id < 3500:
        return "gloves"
    elif 3500 <= config_id < 4000:
        return "boots"
    elif 4000 <= config_id < 4500:
        return "belt"
    elif 5000 <= config_id < 5500:
        return "ring"
    elif 5500 <= config_id < 6000:
        return "amulet"
    elif 6000 <= config_id < 6500:
        return "quiver"
    return None


def main() -> None:
    """메인 실행"""
    print("="*70)
    print("  TITrack - Load Equipment Data to Supabase")
    print("="*70)
    print()

    # 환경 변수 로드
    supabase_url, supabase_key = load_env()
    print(f"[OK] Supabase URL: {supabase_url}")
    print(f"[OK] API Key: {supabase_key[:20]}...")
    print()

    # Supabase 클라이언트 생성
    try:
        client: Client = create_client(supabase_url, supabase_key)
        print("[OK] Supabase client created")
    except Exception as e:
        print(f"[X] Failed to create Supabase client: {e}")
        sys.exit(1)

    # items 테이블 확인
    print()
    print("Checking if items table exists...")
    try:
        result = client.table("items").select("config_base_id", count="exact").limit(1).execute()
        print(f"[OK] items table exists (current records: {result.count})")
    except Exception as e:
        print(f"[X] items table not found: {e}")
        print()
        print("Please run Migration 002 first:")
        print("  1. Go to Supabase Dashboard SQL Editor")
        print("  2. Copy and paste supabase/migrations/002_items_master.sql")
        print("  3. Click 'Run'")
        sys.exit(1)

    # 데이터 파일 읽기
    root_path = Path(__file__).parent.parent
    data_file = root_path / "ref" / "v" / "20260212.txt"

    print()
    print(f"Loading data from: {data_file}")

    if not data_file.exists():
        print(f"[X] Data file not found: {data_file}")
        sys.exit(1)

    with open(data_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"[OK] Loaded {len(data)} items from file")

    # 아이템 변환
    print()
    print("Converting items...")
    items = []
    for config_id_str, item in data.items():
        config_id = int(config_id_str)
        items.append({
            "config_base_id": config_id,
            "name_ko": item.get("name"),
            "type_ko": item.get("type"),
            "category": "equipment",
            "subcategory": infer_subcategory(config_id),
            "tier": infer_tier(config_id),
            "tradeable": True,
            "stackable": False,
        })

    print(f"[OK] Converted {len(items)} items")

    # 배치 업로드
    print()
    print("Uploading to Supabase...")
    batch_size = 100
    total_batches = (len(items) + batch_size - 1) // batch_size
    uploaded = 0
    errors = 0

    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        batch_num = i // batch_size + 1

        try:
            result = client.table("items").upsert(batch).execute()
            uploaded += len(batch)
            print(f"  Batch {batch_num}/{total_batches}: [OK] {len(batch)} items uploaded")
        except Exception as e:
            errors += 1
            print(f"  Batch {batch_num}/{total_batches}: [X] Error: {e}")

    # 결과 요약
    print()
    print("="*70)
    print("Upload Summary:")
    print(f"  Total items:       {len(items)}")
    print(f"  Uploaded:          {uploaded}")
    print(f"  Errors:            {errors}")
    print("="*70)

    # 검증
    if errors == 0:
        print()
        print("Verifying upload...")
        try:
            result = client.table("items").select("config_base_id", count="exact").execute()
            print(f"[OK] Total items in Supabase: {result.count}")

            sample = client.table("items").select("*").limit(5).execute()
            print(f"[OK] Sample items (first 5):")
            for item in sample.data:
                print(f"     - {item['config_base_id']}: {item.get('name_ko', 'N/A')} ({item.get('subcategory', 'N/A')})")
        except Exception as e:
            print(f"[X] Verification error: {e}")

    print()
    print("[OK] Done!")


if __name__ == "__main__":
    main()
