#!/usr/bin/env python3
"""
TITrack - Load Items to Supabase

데이터 소스:
1. src/titrack/data/items_ko.json (3,300 items)
2. ref/v/full_table.json (2,447 items)
3. src/titrack/data/icon_urls.py (270 icon URLs)

실행:
    python scripts/load_items_to_supabase.py

환경 변수:
    TITRACK_SUPABASE_URL - Supabase 프로젝트 URL
    TITRACK_SUPABASE_KEY - Supabase anon/service role key
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


class ItemLoader:
    """Supabase items 테이블 로더"""

    def __init__(self, supabase_url: str, supabase_key: str) -> None:
        """
        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase API key (anon or service_role)
        """
        self.client: Client = create_client(supabase_url, supabase_key)
        self.items: dict[int, dict[str, Any]] = {}
        self.stats = {
            "items_ko_loaded": 0,
            "full_table_loaded": 0,
            "icon_urls_loaded": 0,
            "total_unique": 0,
            "uploaded": 0,
            "errors": 0,
        }

    def load_items_ko(self, path: Path) -> None:
        """items_ko.json 로드"""
        print(f"Loading items_ko.json from {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for config_id_str, item in data.items():
            config_id = int(config_id_str)
            self.items[config_id] = {
                "config_base_id": config_id,
                "name_ko": item.get("name"),
                "type_ko": item.get("type"),
                "tradeable": True,  # 기본값 (거래 가능)
                "stackable": True,  # 기본값 (스택 가능)
            }
            self.stats["items_ko_loaded"] += 1

        print(f"  Loaded {self.stats['items_ko_loaded']} items from items_ko.json")

    def load_full_table(self, path: Path) -> None:
        """ref/v/full_table.json 로드 (UPSERT)"""
        print(f"Loading full_table.json from {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for config_id_str, item in data.items():
            config_id = int(config_id_str)
            if config_id in self.items:
                # 이미 존재하면 name_ko만 보존하고 나머지 업데이트
                self.items[config_id].update({
                    # name_ko는 덮어쓰지 않음 (items_ko.json 우선)
                    "type_ko": item.get("type", self.items[config_id].get("type_ko")),
                })
            else:
                # 새 아이템 추가
                self.items[config_id] = {
                    "config_base_id": config_id,
                    "name_ko": item.get("name"),
                    "type_ko": item.get("type"),
                    "tradeable": True,
                    "stackable": True,
                }
            self.stats["full_table_loaded"] += 1

        print(f"  Processed {self.stats['full_table_loaded']} items from full_table.json")

    def load_icon_urls(self, icon_urls_module_path: Path) -> None:
        """icon_urls.py에서 아이콘 URL 로드"""
        print(f"Loading icon_urls.py from {icon_urls_module_path}")

        # icon_urls.py 파일 경로 추가
        sys.path.insert(0, str(icon_urls_module_path.parent.parent))

        try:
            from titrack.data.icon_urls import ICON_URLS
        except ImportError as e:
            print(f"  Warning: Could not import icon_urls.py: {e}")
            return

        for config_id, icon_url in ICON_URLS.items():
            if config_id in self.items:
                self.items[config_id]["icon_url"] = icon_url
                self.stats["icon_urls_loaded"] += 1

        print(f"  Loaded {self.stats['icon_urls_loaded']} icon URLs")

    def enrich_items(self) -> None:
        """아이템 분류 및 추가 메타데이터 생성"""
        print("Enriching items with category/tier metadata...")

        for config_id, item in self.items.items():
            # 카테고리 분류 (type_ko 기반)
            type_ko = item.get("type_ko", "")
            if type_ko == "화폐":
                item["category"] = "currency"
                item["tier"] = 1
            elif type_ko == "재료":
                item["category"] = "material"
                item["tier"] = self._infer_tier_from_name(item.get("name_ko", ""))
            elif type_ko == "장비":
                item["category"] = "equipment"
                item["subcategory"] = self._infer_equipment_subcategory(
                    config_id, item.get("name_ko", "")
                )
                item["tier"] = self._infer_tier_from_id(config_id)
            elif type_ko == "스킬":
                item["category"] = "skill"
                item["tier"] = 1
            elif type_ko == "레전드":
                item["category"] = "legendary"
                item["tier"] = 10  # 레전드는 최고 티어
            else:
                item["category"] = "other"
                item["tier"] = 1

        print("  Enrichment complete")

    def _infer_tier_from_name(self, name: str) -> int:
        """이름에서 티어 추론 (재료 아이템용)"""
        # 간단한 휴리스틱: 특정 키워드로 티어 추론
        if "상급" in name or "고급" in name:
            return 5
        elif "중급" in name:
            return 3
        elif "하급" in name or "초급" in name:
            return 1
        return 2  # 기본값

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
        # ConfigBaseId 범위별 서브카테고리 (ref/v/full_table.json 분석 기반)
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

    def print_stats(self) -> None:
        """통계 출력"""
        self.stats["total_unique"] = len(self.items)
        print("\n" + "="*60)
        print("Statistics:")
        print(f"  items_ko.json loaded:    {self.stats['items_ko_loaded']}")
        print(f"  full_table.json loaded:  {self.stats['full_table_loaded']}")
        print(f"  icon_urls.py loaded:     {self.stats['icon_urls_loaded']}")
        print(f"  Total unique items:      {self.stats['total_unique']}")
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
        print("  export TITRACK_SUPABASE_URL=https://xxx.supabase.co")
        print("  export TITRACK_SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
        print("  python scripts/load_items_to_supabase.py")
        sys.exit(1)

    # 프로젝트 루트 경로 (scripts/ 기준)
    root_path = Path(__file__).parent.parent

    # 파일 경로 설정
    items_ko_path = root_path / "src" / "titrack" / "data" / "items_ko.json"
    full_table_path = root_path / "ref" / "v" / "full_table.json"
    icon_urls_path = root_path / "src" / "titrack" / "data" / "icon_urls.py"

    # 파일 존재 확인
    if not items_ko_path.exists():
        print(f"Error: {items_ko_path} not found")
        sys.exit(1)
    if not full_table_path.exists():
        print(f"Error: {full_table_path} not found")
        sys.exit(1)

    # 로더 초기화
    loader = ItemLoader(supabase_url, supabase_key)

    # 데이터 로드
    loader.load_items_ko(items_ko_path)
    loader.load_full_table(full_table_path)

    if icon_urls_path.exists():
        loader.load_icon_urls(icon_urls_path)
    else:
        print(f"Warning: {icon_urls_path} not found, skipping icon URLs")

    # 메타데이터 보강
    loader.enrich_items()

    # Supabase 업로드
    loader.upload_to_supabase(batch_size=100)

    # 통계 출력
    loader.print_stats()


if __name__ == "__main__":
    main()
