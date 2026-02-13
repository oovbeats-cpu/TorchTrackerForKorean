#!/usr/bin/env python3
"""
TITrack - Load Items to Supabase (20260212 Equipment Data)

데이터 소스:
1. ref/v/20260212.txt (2,447개 장비 아이템)

실행:
    python scripts/load_items_to_supabase_20260212.py

환경 변수:
    TITRACK_SUPABASE_URL - Supabase 프로젝트 URL
    TITRACK_SUPABASE_KEY - Supabase service role key (초기 로드용)
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional
from datetime import datetime

# Supabase client (optional dependency)
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    print("Error: supabase package not installed")
    print("Install with: pip install titrack[cloud]")
    sys.exit(1)


class ItemLoader20260212:
    """Supabase items 테이블 로더 (20260212 장비 데이터 전용)"""

    def __init__(self, supabase_url: str, supabase_key: str) -> None:
        """
        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase API key (service_role for initial load)
        """
        self.client: Client = create_client(supabase_url, supabase_key)
        self.items: dict[int, dict[str, Any]] = {}
        self.stats = {
            "loaded": 0,
            "uploaded": 0,
            "errors": 0,
        }

    def load_equipment_data(self, path: Path) -> None:
        """20260212.txt 로드 (장비 아이템만)"""
        print(f"Loading equipment data from {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for config_id_str, item in data.items():
            config_id = int(config_id_str)
            name_ko = item.get("name")
            type_ko = item.get("type")

            # 기본 아이템 데이터
            self.items[config_id] = {
                "config_base_id": config_id,
                "name_ko": name_ko,
                "type_ko": type_ko,
                "category": "equipment",  # 모두 장비
                "subcategory": self._infer_equipment_subcategory(config_id, name_ko),
                "tier": self._infer_tier_from_id(config_id),
                "tradeable": True,  # 기본값 (거래 가능)
                "stackable": False,  # 장비는 스택 불가
            }
            self.stats["loaded"] += 1

        print(f"  Loaded {self.stats['loaded']} equipment items")

    def _infer_tier_from_id(self, config_id: int) -> int:
        """ConfigBaseId에서 티어 추론 (장비용)"""
        # ConfigBaseId 범위별 티어 (경험적 매핑)
        if config_id >= 10000:
            return 10  # 레전드 장비
        elif config_id >= 5000:
            return 8
        elif config_id >= 2000:
            return 6
        elif config_id >= 1000:
            return 4
        else:
            return 2  # 일반 장비

    def _infer_equipment_subcategory(self, config_id: int, name: str) -> Optional[str]:
        """장비 서브카테고리 추론"""
        # ConfigBaseId 범위별 서브카테고리
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
        # 방어구 (추정)
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
        # 액세서리 (추정)
        elif 5000 <= config_id < 5500:
            return "ring"
        elif 5500 <= config_id < 6000:
            return "amulet"
        elif 6000 <= config_id < 6500:
            return "quiver"
        return None

    def upload_to_supabase(self, batch_size: int = 100) -> None:
        """Supabase에 bulk upsert"""
        print(f"Uploading {len(self.items)} items to Supabase (batch size: {batch_size})...")

        items_list = list(self.items.values())
        total_batches = (len(items_list) + batch_size - 1) // batch_size

        for i in range(0, len(items_list), batch_size):
            batch = items_list[i:i + batch_size]
            batch_num = i // batch_size + 1

            try:
                # Supabase upsert (conflict on primary key)
                result = self.client.table("items").upsert(batch).execute()

                # 성공 시 카운트 증가
                self.stats["uploaded"] += len(batch)
                print(f"  Batch {batch_num}/{total_batches}: Uploaded {len(batch)} items")

            except Exception as e:
                print(f"  Batch {batch_num}/{total_batches}: Error - {e}")
                self.stats["errors"] += 1

        print(f"Upload complete: {self.stats['uploaded']} items uploaded, {self.stats['errors']} errors")

    def verify_upload(self) -> None:
        """업로드 검증"""
        print("\nVerifying upload...")

        try:
            # 총 레코드 수 확인
            result = self.client.table("items").select("config_base_id", count="exact").execute()
            total_count = result.count
            print(f"  Total items in Supabase: {total_count}")

            # 샘플 데이터 조회 (최초 5개)
            sample = self.client.table("items").select("*").limit(5).execute()
            print(f"  Sample items (first 5):")
            for item in sample.data:
                print(f"    - {item['config_base_id']}: {item.get('name_ko', 'N/A')} ({item.get('subcategory', 'N/A')})")

            # 카테고리별 통계
            categories = self.client.table("items").select("category", count="exact").execute()
            print(f"  Equipment items: {categories.count}")

        except Exception as e:
            print(f"  Verification error: {e}")

    def print_stats(self) -> None:
        """통계 출력"""
        print("\n" + "="*60)
        print("Statistics:")
        print(f"  Loaded from file:        {self.stats['loaded']}")
        print(f"  Uploaded to Supabase:    {self.stats['uploaded']}")
        print(f"  Errors:                  {self.stats['errors']}")
        print("="*60)


def main() -> None:
    """메인 실행 함수"""
    # 환경 변수에서 Supabase 설정 읽기
    supabase_url = os.environ.get("TITRACK_SUPABASE_URL")
    supabase_key = os.environ.get("TITRACK_SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        print("Error: TITRACK_SUPABASE_URL and TITRACK_SUPABASE_KEY must be set")
        print("\nExample:")
        print("  set TITRACK_SUPABASE_URL=https://xxx.supabase.co")
        print("  set TITRACK_SUPABASE_KEY=sb_secret_...")
        print("  python scripts\\load_items_to_supabase_20260212.py")
        sys.exit(1)

    # 프로젝트 루트 경로 (scripts/ 기준)
    root_path = Path(__file__).parent.parent

    # 파일 경로 설정
    equipment_data_path = root_path / "ref" / "v" / "20260212.txt"

    # 파일 존재 확인
    if not equipment_data_path.exists():
        print(f"Error: {equipment_data_path} not found")
        sys.exit(1)

    print("="*60)
    print("TITrack - Load Equipment Items to Supabase")
    print("="*60)
    print(f"Supabase URL: {supabase_url}")
    print(f"Data file: {equipment_data_path}")
    print()

    # 로더 초기화
    loader = ItemLoader20260212(supabase_url, supabase_key)

    # 데이터 로드
    loader.load_equipment_data(equipment_data_path)

    # Supabase 업로드
    loader.upload_to_supabase(batch_size=100)

    # 통계 출력
    loader.print_stats()

    # 검증
    loader.verify_upload()


if __name__ == "__main__":
    main()
