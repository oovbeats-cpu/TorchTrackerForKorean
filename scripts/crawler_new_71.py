#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TLIDB Web Crawler - New 71 Items
크롤링 대상: Magnificent Support, Noble Support, Passive Skill, Netherrealm, Support Skill, Destiny
"""

import json
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# Windows 콘솔 UTF-8 인코딩 설정
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")


class TLIDBNewItemsCrawler:
    """TLIDB 신규 아이템 크롤러"""

    BASE_URL = "https://tlidb.com"
    RATE_LIMIT = 1.0  # seconds between requests
    TIMEOUT = (10, 30)  # connection, read timeout

    # 크롤링 대상 카테고리
    TARGET_CATEGORIES = [
        {
            "path": "/ko/Magnificent_Support_Skill",
            "type": "부귀 보조 스킬",
            "expected": 36,
        },
        {
            "path": "/ko/Noble_Support_Skill",
            "type": "숭고 보조 스킬",
            "expected": 18,
        },
        {
            "path": "/ko/Passive_Skill",
            "type": "패시브 스킬",
            "expected": 6,
        },
        {
            "path": "/ko/Netherrealm",
            "type": "황천",
            "expected": 6,
        },
        {
            "path": "/ko/Support_Skill",
            "type": "보조 스킬",
            "expected": 3,
        },
        {
            "path": "/ko/Destiny",
            "type": "운명",
            "expected": 2,
        },
    ]

    def __init__(self, existing_items_path: Path):
        """
        Args:
            existing_items_path: 기존 items_ko.json 경로
        """
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "TITrack/1.0.2 (+https://github.com/yourusername/TorchTrackerForKorean)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
            }
        )
        self.last_request = 0

        # 기존 아이템 로드
        self.existing_ids = set()
        if existing_items_path.exists():
            with open(existing_items_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.existing_ids = set(data.keys())
        print(f"[OK] 기존 아이템 {len(self.existing_ids)}개 로드됨")

    def rate_limit(self):
        """1 request/second throttling"""
        elapsed = time.time() - self.last_request
        if elapsed < self.RATE_LIMIT:
            time.sleep(self.RATE_LIMIT - elapsed)
        self.last_request = time.time()

    def get_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch page with exponential backoff"""
        self.rate_limit()

        for attempt in range(3):  # max 3 retries
            try:
                response = self.session.get(url, timeout=self.TIMEOUT)
                response.raise_for_status()
                response.encoding = "utf-8"
                return BeautifulSoup(response.text, "html.parser")
            except requests.HTTPError as e:
                if e.response.status_code == 429:  # Rate limited
                    wait = (2**attempt) * self.RATE_LIMIT
                    print(f"[WARNING] Rate limited, waiting {wait:.1f}s...")
                    time.sleep(wait)
                else:
                    print(f"[ERROR] HTTP Error {e.response.status_code}: {url}")
                    return None
            except Exception as e:
                print(f"[ERROR] Error fetching {url}: {e}")
                if attempt < 2:
                    time.sleep((2**attempt) * self.RATE_LIMIT)
                else:
                    return None

    def parse_category_page(
        self, path: str, item_type: str
    ) -> tuple[List[Dict], List[Dict]]:
        """
        카테고리 페이지에서 아이템 추출

        Returns:
            (new_items, all_items): 신규 아이템과 전체 아이템
        """
        url = f"{self.BASE_URL}{path}"
        print(f"\n▶ Crawling {url}")

        soup = self.get_page(url)
        if not soup:
            return [], []

        # 카드 그리드 레이아웃 파싱
        cards = soup.find_all("div", class_="col")
        print(f"  Found {len(cards)} cards")

        all_items = []
        new_items = []

        for card in cards:
            # data-hover 속성에서 ConfigBaseId 추출
            link = card.find("a", attrs={"data-hover": True})
            if not link:
                continue

            data_hover = link.get("data-hover", "")
            match = re.search(r"ItemBase%2F(\d+)", data_hover)
            if not match:
                continue

            config_id = match.group(1)

            # 한국어 이름 추출
            name_ko = link.get_text(strip=True)
            if not name_ko:
                continue

            # 아이콘 URL 추출 (optional)
            img = card.find("img")
            icon_url = img.get("src", "") if img else ""

            item = {
                "config_id": config_id,
                "name_ko": name_ko,
                "type": item_type,
                "icon_url": icon_url,
                "category_path": path,
            }

            all_items.append(item)

            # 신규 아이템 필터링
            if config_id not in self.existing_ids:
                new_items.append(item)

        print(f"  Total: {len(all_items)}, New: {len(new_items)}")
        return new_items, all_items

    def crawl_all_categories(self) -> Dict:
        """모든 카테고리 크롤링"""
        results = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "source": "tlidb.com",
                "crawler_version": "1.0.0",
                "total_categories": len(self.TARGET_CATEGORIES),
            },
            "categories": [],
            "new_items": {},
            "all_items": {},
            "summary": {
                "total_new": 0,
                "total_all": 0,
                "expected_total": sum(c["expected"] for c in self.TARGET_CATEGORIES),
            },
        }

        for category in self.TARGET_CATEGORIES:
            path = category["path"]
            item_type = category["type"]
            expected = category["expected"]

            print(f"\n{'=' * 60}")
            print(f"Category: {item_type} ({path})")
            print(f"Expected: {expected} new items")

            new_items, all_items = self.parse_category_page(path, item_type)

            category_result = {
                "path": path,
                "type": item_type,
                "expected": expected,
                "found_new": len(new_items),
                "found_all": len(all_items),
                "match": len(new_items) == expected,
            }
            results["categories"].append(category_result)

            # 신규 아이템 저장 (TITrack 형식)
            for item in new_items:
                results["new_items"][item["config_id"]] = {
                    "name": item["name_ko"],
                    "type": item["type"],
                    "price": 0,
                }

            # 전체 아이템 저장 (상세 정보 포함)
            for item in all_items:
                results["all_items"][item["config_id"]] = item

            results["summary"]["total_new"] += len(new_items)
            results["summary"]["total_all"] += len(all_items)

        return results

    def save_results(self, results: Dict, output_dir: Path):
        """결과 저장"""
        output_dir.mkdir(parents=True, exist_ok=True)

        # 1. TITrack 형식 (items_ko.json 병합용)
        titrack_file = output_dir / "crawler_new_71_items.json"
        with open(titrack_file, "w", encoding="utf-8") as f:
            json.dump(results["new_items"], f, ensure_ascii=False, indent=2)
        print(f"\n[OK] TITrack format: {titrack_file}")

        # 2. 상세 정보 포함
        detailed_file = output_dir / "crawler_new_71_detailed.json"
        with open(detailed_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"[OK] Detailed format: {detailed_file}")

        # 3. 요약 보고서
        summary_file = output_dir / "crawler_new_71_summary.txt"
        with open(summary_file, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write("TLIDB 신규 아이템 크롤링 요약\n")
            f.write("=" * 60 + "\n\n")

            metadata = results["metadata"]
            f.write(f"크롤링 시간: {metadata['timestamp']}\n")
            f.write(f"소스: {metadata['source']}\n")
            f.write(f"크롤러 버전: {metadata['crawler_version']}\n\n")

            summary = results["summary"]
            f.write(f"예상 신규 아이템: {summary['expected_total']}개\n")
            f.write(f"실제 신규 아이템: {summary['total_new']}개\n")
            f.write(f"전체 크롤링: {summary['total_all']}개\n\n")

            f.write("=" * 60 + "\n")
            f.write("카테고리별 상세\n")
            f.write("=" * 60 + "\n\n")

            for cat in results["categories"]:
                f.write(f"[{cat['type']}] {cat['path']}\n")
                f.write(f"  예상: {cat['expected']}개\n")
                f.write(f"  실제 신규: {cat['found_new']}개\n")
                f.write(f"  전체: {cat['found_all']}개\n")
                f.write(f"  일치: {'[OK]' if cat['match'] else '[ERROR]'}\n\n")

            # 신규 아이템 목록
            if results["new_items"]:
                f.write("=" * 60 + "\n")
                f.write("신규 아이템 목록\n")
                f.write("=" * 60 + "\n\n")
                for config_id, item in sorted(results["new_items"].items()):
                    f.write(f"{config_id}: {item['name']} ({item['type']})\n")

        print(f"[OK] Summary report: {summary_file}")


def main():
    """메인 실행"""
    print("=" * 60)
    print("TLIDB 신규 71개 아이템 크롤러")
    print("=" * 60)

    # 경로 설정
    project_root = Path(__file__).parent.parent
    items_ko_path = project_root / "src" / "titrack" / "data" / "items_ko.json"
    output_dir = project_root / "output"

    if not items_ko_path.exists():
        print(f"[ERROR] items_ko.json not found: {items_ko_path}")
        return

    # 크롤러 실행
    crawler = TLIDBNewItemsCrawler(items_ko_path)
    results = crawler.crawl_all_categories()

    # 결과 저장
    crawler.save_results(results, output_dir)

    # 최종 요약
    print("\n" + "=" * 60)
    print("크롤링 완료!")
    print("=" * 60)
    print(f"예상: {results['summary']['expected_total']}개")
    print(f"실제 신규: {results['summary']['total_new']}개")
    print(f"전체 크롤링: {results['summary']['total_all']}개")

    if results["summary"]["total_new"] == 0:
        print("\n[WARNING] 신규 아이템이 없습니다. items_ko.json이 이미 최신 상태입니다.")
    else:
        print(
            f"\n[OK] {results['summary']['total_new']}개 신규 아이템을 items_ko.json에 병합할 수 있습니다."
        )


if __name__ == "__main__":
    main()
