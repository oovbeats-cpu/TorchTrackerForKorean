"""
tlidb.com 웹 크롤러 - 화폐/연료 카테고리

담당 카테고리:
1. /ko/Universal_Items (공용 아이템 12개)
2. /ko/Fuel (연료 2개)

출력: output/crawler1_currency_fuel.json
"""

import json
import re
import time
from typing import Dict, Optional, Any
from pathlib import Path
import requests
from bs4 import BeautifulSoup


# 설정
BASE_URL = "https://tlidb.com"
RATE_LIMIT_DELAY = 1.0  # 요청 간 1초 대기
MAX_RETRIES = 3
TIMEOUT = 30
USER_AGENT = "TITrack/1.0.2 (+https://github.com/yourusername/TorchTrackerForKorean)"

# 타겟 카테고리
CATEGORIES = [
    {"path": "/ko/Universal_Items", "name": "공용 아이템", "expected_count": 12},
    {"path": "/ko/Fuel", "name": "연료", "expected_count": 2},
]


class TLIDBCrawler:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.results = {}
        self.errors = []
        self.request_count = 0

    def fetch_with_retry(self, url: str, retry_count: int = 0) -> Optional[BeautifulSoup]:
        """HTTP 요청 (재시도 로직 포함)"""
        try:
            self.request_count += 1
            print(f"[{self.request_count}] Fetching: {url}")

            response = self.session.get(url, timeout=TIMEOUT)
            response.raise_for_status()

            # Rate limiting
            time.sleep(RATE_LIMIT_DELAY)

            return BeautifulSoup(response.text, 'html.parser')

        except requests.exceptions.RequestException as e:
            if retry_count < MAX_RETRIES - 1:
                wait_time = 2 ** retry_count  # Exponential backoff
                print(f"  [WARN] Error: {e}. Retrying in {wait_time}s... ({retry_count + 1}/{MAX_RETRIES})")
                time.sleep(wait_time)
                return self.fetch_with_retry(url, retry_count + 1)
            else:
                print(f"  [FAIL] Failed after {MAX_RETRIES} attempts: {e}")
                self.errors.append({"url": url, "error": str(e)})
                return None

    def extract_item_links(self, soup: BeautifulSoup) -> list[str]:
        """카테고리 페이지에서 아이템 링크 추출"""
        links = []

        # 네비게이션/카테고리 페이지 블랙리스트
        blacklist = [
            '/ko/', '/en/', '/tw/', '/cn/', '/ja/', '/ru/',  # 언어 메인
            '/ko/Hero', '/ko/Talent', '/ko/Inventory', '/ko/Legendary_Gear',
            '/ko/Active_Skill', '/ko/Support_Skill', '/ko/Passive_Skill',
            '/ko/Activation_Medium_Skill', '/ko/Noble_Support_Skill',
            '/ko/Magnificent_Support_Skill', '/ko/Craft', '/ko/Gear_Empowerment',
            '/ko/Dream_Talking', '/ko/Outfit', '/ko/Commodity', '/ko/Pactspirit',
            '/ko/Drop_Source', '/ko/Destiny', '/ko/Tip', '/ko/Hyperlink',
            '/ko/Corrosion', '/ko/Path_of_Progression', '/ko/Help', '/ko/Codex',
            '/ko/Netherrealm', '/ko/Confusion_Card_Library', '/ko/Void_Chart',
            '/ko/Compass', '/ko/Probe', '/ko/Path_of_the_Brave', '/ko/Boon',
            '/ko/Blending_Rituals', '/ko/TOWER_Sequence', '/ko/Graft',
            '/ko/Ethereal_Prism', '/ko/Universal_Items', '/ko/Fuel',
            '#', 'privacy', '#top'
        ]

        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text(strip=True)

            # 빈 텍스트 제외
            if not text:
                continue

            # HTTP 링크 제외 (외부 사이트)
            if href.startswith('http'):
                continue

            # 블랙리스트 체크
            if href in blacklist:
                continue

            # 시즌 링크 제외 (Season으로 끝나는 것들)
            if href.endswith('_Season'):
                continue

            # 아이템 링크는 상대 경로 (예: "Elixir_of_Oblivion")
            # 또는 /ko/로 시작하되 블랙리스트에 없는 것
            if not href.startswith('/'):
                # 상대 경로 → 절대 경로로 변환
                links.append(f"/ko/{href}")
            elif href.startswith('/ko/') and href not in blacklist:
                links.append(href)

        return list(set(links))  # 중복 제거

    def extract_config_base_id(self, soup: BeautifulSoup) -> Optional[int]:
        """ConfigBaseId 추출 (id: 패턴)"""
        # "id: 100300" 패턴 찾기
        text = soup.get_text()
        match = re.search(r'\bid:\s*(\d+)', text)
        if match:
            return int(match.group(1))

        # 대체 패턴: data-id, data-config-id 등
        for attr in ['data-id', 'data-config-id', 'data-item-id']:
            element = soup.find(attrs={attr: True})
            if element:
                try:
                    return int(element[attr])
                except ValueError:
                    continue

        return None

    def extract_item_data(self, soup: BeautifulSoup, url_path: str) -> Optional[Dict[str, Any]]:
        """아이템 상세 페이지에서 데이터 추출"""
        data = {}

        # 1. 한국어 이름 (h1 태그)
        h1 = soup.find('h1')
        if h1:
            data['name'] = h1.get_text(strip=True)

        # 2. 영어 이름 (URL slug)
        slug = url_path.split('/')[-1]
        data['name_en'] = slug

        # 3. ConfigBaseId
        config_id = self.extract_config_base_id(soup)
        if not config_id:
            print(f"  [WARN] ConfigBaseId not found for {slug}")
            return None
        data['config_base_id'] = config_id

        # 4. 아이콘 URL (size128 클래스 우선 검색)
        img = soup.find('img', class_=re.compile(r'size128|ui_item_base'))
        if not img:
            # 폴백: CDN 이미지 중 128 크기 찾기
            img = soup.find('img', src=re.compile(r'cdn\.tlidb\.com.*128'))
        if not img:
            # 최종 폴백: 첫 번째 CDN 이미지
            img = soup.find('img', src=re.compile(r'cdn\.tlidb\.com'))

        if img and img.get('src'):
            icon_url = img['src']
            if not icon_url.startswith('http'):
                icon_url = f"https:{icon_url}" if icon_url.startswith('//') else f"{BASE_URL}{icon_url}"
            data['icon_url'] = icon_url

        # 5. 타입 추측 (카테고리 기반)
        if 'Fuel' in url_path or 'Flame' in slug or 'Sand' in slug:
            data['type'] = '연료'
        elif 'Universal' in url_path or 'Elixir' in slug or 'Key' in slug:
            data['type'] = '공용 아이템'
        else:
            data['type'] = '기타'

        # 6. 가격 초기화 (Flame Elementium은 1, 나머지는 0)
        if config_id == 100300:
            data['price'] = 1
        else:
            data['price'] = 0

        return data

    def crawl_category(self, category: Dict[str, str]) -> int:
        """카테고리 크롤링"""
        print(f"\n{'=' * 60}")
        print(f"Category: {category['name']} ({category['path']})")
        print(f"{'=' * 60}")

        # 카테고리 페이지 가져오기
        soup = self.fetch_with_retry(f"{BASE_URL}{category['path']}")
        if not soup:
            return 0

        # 아이템 링크 추출
        item_links = self.extract_item_links(soup)
        print(f"  Found {len(item_links)} item links (expected: {category['expected_count']})")

        if len(item_links) == 0:
            print(f"  [WARN] No item links found. Page structure may have changed.")
            return 0

        # 각 아이템 페이지 크롤링
        success_count = 0
        for idx, link in enumerate(item_links, 1):
            print(f"\n  [{idx}/{len(item_links)}] Crawling item: {link}")

            item_soup = self.fetch_with_retry(f"{BASE_URL}{link}")
            if not item_soup:
                continue

            item_data = self.extract_item_data(item_soup, link)
            if item_data:
                config_id = item_data.pop('config_base_id')
                self.results[str(config_id)] = item_data
                print(f"    [OK] {item_data['name']} (ID: {config_id})")
                success_count += 1
            else:
                print(f"    [FAIL] Failed to extract data")

        return success_count

    def crawl_all(self) -> Dict[str, Any]:
        """모든 카테고리 크롤링"""
        print("=" * 60)
        print("tlidb.com Currency/Fuel Crawler")
        print("=" * 60)

        total_success = 0
        for category in CATEGORIES:
            count = self.crawl_category(category)
            total_success += count

        return {
            "items": self.results,
            "metadata": {
                "total_items": len(self.results),
                "total_requests": self.request_count,
                "categories_crawled": len(CATEGORIES),
                "errors": len(self.errors),
            },
            "errors": self.errors,
        }

    def save_results(self, output_path: Path):
        """결과를 JSON 파일로 저장"""
        # items_ko.json 형식으로 변환
        items_ko_format = {
            str(config_id): {
                "name": data["name"],
                "type": data["type"],
                "price": data["price"],
            }
            for config_id, data in self.results.items()
        }

        # 전체 데이터 (디버깅용)
        full_data = {
            "items": self.results,
            "items_ko_format": items_ko_format,
            "metadata": {
                "total_items": len(self.results),
                "total_requests": self.request_count,
                "categories_crawled": len(CATEGORIES),
                "errors_count": len(self.errors),
            },
            "errors": self.errors,
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(full_data, f, ensure_ascii=False, indent=2)

        print(f"\n{'=' * 60}")
        print(f"Results saved to: {output_path}")
        print(f"   Total items: {len(self.results)}")
        print(f"   Total requests: {self.request_count}")
        print(f"   Errors: {len(self.errors)}")
        print(f"{'=' * 60}")


def main():
    crawler = TLIDBCrawler()
    crawler.crawl_all()

    # 결과 저장
    output_path = Path(__file__).parent.parent / "output" / "crawler1_currency_fuel.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    crawler.save_results(output_path)

    # 요약 출력
    print("\nSummary:")
    print(f"  [OK] Successfully crawled: {len(crawler.results)} items")
    if crawler.errors:
        print(f"  [FAIL] Errors encountered: {len(crawler.errors)}")
        for error in crawler.errors[:5]:  # 최대 5개만 표시
            print(f"     - {error['url']}: {error['error']}")


if __name__ == "__main__":
    main()
