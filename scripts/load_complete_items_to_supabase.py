#!/usr/bin/env python3
"""
TITrack - Load COMPLETE Items to Supabase

완전한 아이템 데이터 (한국어/영어/중국어 이름 + 아이콘) 로드

데이터 소스:
1. src/titrack/data/items_ko.json (2,480 items) - name_ko, type_ko, price
2. output/crawler*.json (387 items) - name_en, name_cn, icon_url
3. src/titrack/data/icon_urls.py (270 items) - icon_url (폴백)

우선순위:
- name_ko: items_ko.json
- name_en/name_cn: crawler > 없음
- icon_url: crawler > icon_urls.py

실행:
    python scripts/load_complete_items_to_supabase.py

환경 변수:
    TITRACK_SUPABASE_URL - Supabase 프로젝트 URL
    TITRACK_SUPABASE_KEY - Supabase service_role key
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


class CompleteItemLoader:
    """완전한 아이템 데이터 Supabase 로더"""

    def __init__(self, supabase_url: str, supabase_key: str) -> None:
        """
        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase service_role key (full access)
        """
        self.client: Client = create_client(supabase_url, supabase_key)
        self.items: dict[int, dict[str, Any]] = {}
        self.stats = {
            "items_ko_loaded": 0,
            "crawler_items_loaded": 0,
            "icon_urls_loaded": 0,
            "total_unique": 0,
            "with_en_name": 0,
            "with_cn_name": 0,
            "with_icon": 0,
            "uploaded": 0,
            "errors": 0,
        }

    def load_items_ko(self, path: Path) -> None:
        """items_ko.json 로드 (기본 데이터)"""
        print(f"[1/4] Loading items_ko.json from {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for config_id_str, item in data.items():
            config_id = int(config_id_str)
            self.items[config_id] = {
                "config_base_id": config_id,
                "name_ko": item.get("name"),
                "type_ko": item.get("type"),
                "tradeable": True,  # 기본값
                "stackable": True,  # 기본값
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
            self.stats["items_ko_loaded"] += 1

        print(f"      Loaded {self.stats['items_ko_loaded']} items")

    def load_crawler_data(self, output_dir: Path) -> None:
        """크롤러 데이터 파일들에서 영어/중국어 이름 + 아이콘 로드"""
        print(f"[2/4] Loading crawler data from {output_dir}")

        # name_en/icon_url이 있는 파일들만 로드
        crawler_files_with_en = [
            "crawler1_currency_fuel.json",  # items 키 사용
            "crawler2_materials_detailed.json",  # direct 키 사용
        ]

        all_crawler_items: dict[int, dict[str, Any]] = {}

        for filename in crawler_files_with_en:
            filepath = output_dir / filename
            if not filepath.exists():
                print(f"      Warning: {filename} not found, skipping")
                continue

            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # crawler1: {"items": {id: {name, name_en, icon_url, ...}}, ...}
            # crawler2: {id: {name, name_en, icon_url, ...}}
            if "items" in data and isinstance(data["items"], dict):
                items_data = data["items"]
            else:
                # 파일 전체가 아이템 딕셔너리인 경우
                items_data = {k: v for k, v in data.items() if k.isdigit()}

            for config_id_str, item_data in items_data.items():
                try:
                    config_id = int(config_id_str)
                    all_crawler_items[config_id] = item_data
                except (ValueError, TypeError):
                    continue

        print(f"      Found {len(all_crawler_items)} items with name_en/icon_url")

        # items에 병합
        for config_id, crawler_item in all_crawler_items.items():
            if config_id not in self.items:
                # items_ko.json에 없는 아이템은 새로 추가
                self.items[config_id] = {
                    "config_base_id": config_id,
                    "name_ko": crawler_item.get("name"),
                    "type_ko": crawler_item.get("type"),
                    "tradeable": True,
                    "stackable": True,
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat(),
                }

            # 영어/중국어 이름 + 아이콘 추가
            if "name_en" in crawler_item:
                self.items[config_id]["name_en"] = crawler_item["name_en"]
            if "name_cn" in crawler_item:
                self.items[config_id]["name_cn"] = crawler_item["name_cn"]
            if "icon_url" in crawler_item:
                self.items[config_id]["icon_url"] = crawler_item["icon_url"]
            if "url_tlidb" in crawler_item:
                self.items[config_id]["url_tlidb"] = crawler_item["url_tlidb"]

            self.stats["crawler_items_loaded"] += 1

        print(f"      Merged {self.stats['crawler_items_loaded']} items from crawler")

    def load_icon_urls_fallback(self, icon_urls_module_path: Path) -> None:
        """icon_urls.py에서 아이콘 URL 로드 (폴백)"""
        print(f"[3/4] Loading icon_urls.py fallback from {icon_urls_module_path}")

        # icon_urls.py 파일 경로 추가
        sys.path.insert(0, str(icon_urls_module_path.parent.parent))

        try:
            # icon_urls.py는 동적 로더이므로 먼저 로드 함수 호출
            from titrack.data import icon_urls as icon_urls_module
            icon_urls_module.load_icon_urls()
            ICON_URLS = icon_urls_module._icon_urls
        except ImportError as e:
            print(f"      Warning: Could not import icon_urls.py: {e}")
            return

        # 크롤러에서 이미 로드된 아이콘이 없는 경우에만 추가
        for config_id, icon_url in ICON_URLS.items():
            if config_id in self.items and "icon_url" not in self.items[config_id]:
                self.items[config_id]["icon_url"] = icon_url
                self.stats["icon_urls_loaded"] += 1

        print(f"      Loaded {self.stats['icon_urls_loaded']} fallback icon URLs")

    def enrich_items(self) -> None:
        """아이템 분류 및 추가 메타데이터 생성"""
        print("[4/4] Enriching items with category/tier metadata...")

        for config_id, item in self.items.items():
            # 카테고리 분류 (type_ko 기반)
            type_ko = item.get("type_ko", "")

            if type_ko == "화폐" or type_ko == "연료":
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
            elif type_ko in ["스킬", "부귀 보조 스킬", "숭고 보조 스킬", "패시브 스킬"]:
                item["category"] = "skill"
                item["tier"] = 1
            elif type_ko == "레전드":
                item["category"] = "legendary"
                item["tier"] = 10
            elif type_ko == "기타" or type_ko == "공용 아이템":
                item["category"] = "other"
                item["tier"] = 1
            else:
                item["category"] = "other"
                item["tier"] = 1

            # type_en 추론 (name_en이 있는 경우)
            if "name_en" in item and "type_en" not in item:
                item["type_en"] = self._translate_type_to_en(type_ko)

        print("      Enrichment complete")

    def _translate_type_to_en(self, type_ko: str) -> str:
        """한국어 타입을 영어로 번역"""
        type_map = {
            "화폐": "Currency",
            "연료": "Fuel",
            "재료": "Material",
            "장비": "Equipment",
            "스킬": "Skill",
            "부귀 보조 스킬": "Magnificent Support Skill",
            "숭고 보조 스킬": "Noble Support Skill",
            "패시브 스킬": "Passive Skill",
            "레전드": "Legendary",
            "기타": "Other",
            "공용 아이템": "Common Item",
        }
        return type_map.get(type_ko, "Other")

    def _infer_tier_from_name(self, name: str) -> int:
        """이름에서 티어 추론 (재료용)"""
        if "상급" in name or "고급" in name:
            return 5
        elif "중급" in name:
            return 3
        elif "하급" in name or "초급" in name:
            return 1
        return 2

    def _infer_tier_from_id(self, config_id: int) -> int:
        """ConfigBaseId에서 티어 추론 (장비용)"""
        if config_id >= 10000:
            return 10  # 레전드
        elif config_id >= 5000:
            return 8
        elif config_id >= 2000:
            return 6
        elif config_id >= 1000:
            return 4
        else:
            return 2

    def _infer_equipment_subcategory(self, config_id: int, name: str) -> Optional[str]:
        """장비 서브카테고리 추론"""
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

    def compute_stats(self) -> None:
        """최종 통계 계산"""
        self.stats["total_unique"] = len(self.items)

        for item in self.items.values():
            if item.get("name_en"):
                self.stats["with_en_name"] += 1
            if item.get("name_cn"):
                self.stats["with_cn_name"] += 1
            if item.get("icon_url"):
                self.stats["with_icon"] += 1

    def upload_to_supabase(self, batch_size: int = 100) -> None:
        """Supabase에 bulk upsert"""
        print(f"\n[UPLOAD] Uploading {len(self.items)} items to Supabase (batch size: {batch_size})...")

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
                print(f"         Batch {batch_num}/{total_batches}: Uploaded {len(batch)} items")

            except Exception as e:
                print(f"         Batch {batch_num}/{total_batches}: Error - {e}")
                self.stats["errors"] += 1

        print(f"\n[UPLOAD] Upload complete: {self.stats['uploaded']} items uploaded, {self.stats['errors']} errors")

    def print_stats(self) -> None:
        """통계 출력"""
        print("\n" + "="*70)
        print("FINAL STATISTICS:")
        print("="*70)
        print(f"  items_ko.json loaded:        {self.stats['items_ko_loaded']}")
        print(f"  Crawler data merged:         {self.stats['crawler_items_loaded']}")
        print(f"  icon_urls.py fallback:       {self.stats['icon_urls_loaded']}")
        print(f"  Total unique items:          {self.stats['total_unique']}")
        print("-"*70)
        print(f"  Items with name_en:          {self.stats['with_en_name']} ({self.stats['with_en_name']/self.stats['total_unique']*100:.1f}%)")
        print(f"  Items with name_cn:          {self.stats['with_cn_name']} ({self.stats['with_cn_name']/self.stats['total_unique']*100:.1f}%)")
        print(f"  Items with icon_url:         {self.stats['with_icon']} ({self.stats['with_icon']/self.stats['total_unique']*100:.1f}%)")
        print("-"*70)
        print(f"  Uploaded to Supabase:        {self.stats['uploaded']}")
        print(f"  Errors:                      {self.stats['errors']}")
        print("="*70)


def main() -> None:
    """메인 실행 함수"""
    # .env 파일에서 환경 변수 로드
    root_path = Path(__file__).parent.parent
    env_path = root_path / ".env"

    if env_path.exists():
        print(f"Loading environment from {env_path}")
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()

    # 환경 변수에서 Supabase 설정 읽기
    supabase_url = os.environ.get("TITRACK_SUPABASE_URL")
    supabase_key = os.environ.get("TITRACK_SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        print("Error: TITRACK_SUPABASE_URL and TITRACK_SUPABASE_KEY must be set")
        print("\nEither set environment variables or create a .env file with:")
        print("  TITRACK_SUPABASE_URL=https://xxx.supabase.co")
        print("  TITRACK_SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
        print("\nThen run: python scripts/load_complete_items_to_supabase.py")
        sys.exit(1)

    # 프로젝트 루트 경로
    root_path = Path(__file__).parent.parent

    # 파일 경로 설정
    items_ko_path = root_path / "src" / "titrack" / "data" / "items_ko.json"
    output_dir = root_path / "output"
    icon_urls_path = root_path / "src" / "titrack" / "data" / "icon_urls.py"

    # 파일 존재 확인
    if not items_ko_path.exists():
        print(f"Error: {items_ko_path} not found")
        sys.exit(1)
    if not output_dir.exists():
        print(f"Error: {output_dir} not found")
        sys.exit(1)

    print("="*70)
    print("TITrack - Complete Item Loader for Supabase")
    print("="*70)
    print(f"Supabase URL: {supabase_url}")
    print(f"Data sources:")
    print(f"  - items_ko.json: {items_ko_path}")
    print(f"  - crawler data:  {output_dir}")
    print(f"  - icon_urls.py:  {icon_urls_path}")
    print("="*70)

    # 로더 초기화
    loader = CompleteItemLoader(supabase_url, supabase_key)

    # 데이터 로드
    loader.load_items_ko(items_ko_path)
    loader.load_crawler_data(output_dir)

    if icon_urls_path.exists():
        loader.load_icon_urls_fallback(icon_urls_path)
    else:
        print(f"[3/4] Warning: {icon_urls_path} not found, skipping fallback")

    # 메타데이터 보강
    loader.enrich_items()

    # 통계 계산
    loader.compute_stats()

    # Supabase 업로드
    loader.upload_to_supabase(batch_size=100)

    # 최종 통계 출력
    loader.print_stats()


if __name__ == "__main__":
    main()
