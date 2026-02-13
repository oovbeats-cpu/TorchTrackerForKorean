"""
tlidb.com Materials Category Crawler
재료 관련 카테고리 (Ember, Fossil, Mod) 아이템 데이터 크롤러
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
from typing import Dict, List, Optional
from pathlib import Path
import logging
import sys
import codecs

# Windows 콘솔 UTF-8 강제 설정 (한글 깨짐 방지)
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')



# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 설정
BASE_URL = "https://tlidb.com"
RATE_LIMIT = 1.0  # 초 단위
MAX_RETRIES = 3
TIMEOUT = 30

# 크롤링할 카테고리
CATEGORIES = {
    "Ember": "/ko/Ember",
    "Fossil": "/ko/Fossil",
    "Mod": "/ko/Mod"
}

class TLIDBCrawler:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'TITrack/1.0.2 (+https://github.com/yourusername/TorchTrackerForKorean)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
        })
        self.results = {}
        self.errors = []

    def fetch_with_retry(self, url: str) -> Optional[requests.Response]:
        """재시도 로직이 포함된 HTTP GET 요청"""
        for attempt in range(MAX_RETRIES):
            try:
                time.sleep(RATE_LIMIT)  # Rate limiting
                logger.info(f"Fetching: {url} (attempt {attempt + 1}/{MAX_RETRIES})")

                response = self.session.get(url, timeout=TIMEOUT)
                response.raise_for_status()
                return response

            except requests.exceptions.RequestException as e:
                wait_time = (2 ** attempt) * RATE_LIMIT  # Exponential backoff
                logger.warning(f"Request failed: {e}. Retrying in {wait_time}s...")

                if attempt < MAX_RETRIES - 1:
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed after {MAX_RETRIES} attempts: {url}")
                    self.errors.append({
                        'url': url,
                        'error': str(e),
                        'type': 'fetch_error'
                    })
                    return None
        return None

    def extract_config_base_id(self, url: str, soup: BeautifulSoup) -> Optional[str]:
        """URL 또는 HTML에서 ConfigBaseId 추출"""
        # URL 패턴: /ko/item/123456
        match = re.search(r'/ko/item/(\d+)', url)
        if match:
            return match.group(1)

        # HTML에서 "id: 숫자" 패턴 찾기 (Info 섹션)
        # BeautifulSoup으로 텍스트 검색
        text_content = soup.get_text()

        # 패턴: "id: 123456" 또는 "id:123456"
        patterns = [
            r'\bid:\s*(\d+)',
            r'ConfigBaseId["\s:]+(\d+)',
            r'baseId["\s:]+(\d+)',
            r'itemId["\s:]+(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                config_id = match.group(1)
                logger.debug(f"Found ConfigBaseId via pattern '{pattern}': {config_id}")
                return config_id

        return None

    def extract_item_name(self, soup: BeautifulSoup, url: str) -> Dict[str, str]:
        """한국어 및 영어 아이템 이름 추출"""
        names = {"ko": None, "en": None}

        # 1. 한국어 이름 추출 (h1 태그에서)
        h1_tags = soup.find_all('h1')
        for h1 in h1_tags:
            text = h1.get_text(strip=True)
            # 한글이 포함된 텍스트면 한국어 이름
            if text and re.search(r'[가-힣]', text):
                names["ko"] = text
                logger.debug(f"Found Korean name: {text}")
                break

        # 2. 영어 이름 추출 (URL에서)
        match = re.search(r'/ko/([^/]+)$', url)
        if match:
            en_name = match.group(1).replace('_', ' ')
            names["en"] = en_name
            logger.debug(f"Found English name from URL: {en_name}")

        # 3. meta 태그에서 한국어 이름 확인 (fallback)
        if not names["ko"]:
            meta_title = soup.find('meta', property='og:title')
            if meta_title:
                title = meta_title.get('content', '').strip()
                if title and re.search(r'[가-힣]', title):
                    names["ko"] = title

        return names

    def extract_item_type(self, soup: BeautifulSoup, category: str) -> str:
        """아이템 타입 추출"""
        # 카테고리 기반 기본 타입
        type_mapping = {
            "Ember": "엠버",
            "Fossil": "화석",
            "Mod": "코어"
        }

        default_type = type_mapping.get(category, "재료")

        # HTML에서 타입 정보 찾기
        type_selectors = [
            'span.item-type',
            'div.item-category',
            '.item-info .type'
        ]

        for selector in type_selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                if text:
                    logger.debug(f"Found type via '{selector}': {text}")
                    return text

        return default_type

    def extract_icon_url(self, soup: BeautifulSoup) -> Optional[str]:
        """아이템 아이콘 URL 추출"""
        # cdn.tlidb.com에서 아이콘 찾기
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src')
            if src and 'cdn.tlidb.com' in src and 'Icon' in src:
                # 상대 경로를 절대 경로로 변환
                if src.startswith('//'):
                    src = 'https:' + src
                elif src.startswith('/'):
                    src = 'https:' + src if src.startswith('//') else 'https://cdn.tlidb.com' + src

                logger.debug(f"Found icon URL: {src}")
                return src

        # Fallback: 일반 이미지 선택자
        img_selectors = [
            'img.item-icon',
            'div.item-image img',
            '.item-header img',
            'img[alt*="icon"]',
            'img'  # 마지막 fallback
        ]

        for selector in img_selectors:
            img = soup.select_one(selector)
            if img:
                src = img.get('src') or img.get('data-src')
                if src:
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        src = BASE_URL + src
                    logger.debug(f"Found icon via fallback '{selector}': {src}")
                    return src

        return None

    def crawl_item_detail(self, item_url: str, category: str) -> Optional[Dict]:
        """개별 아이템 상세 페이지 크롤링"""
        full_url = BASE_URL + item_url if item_url.startswith('/') else item_url

        response = self.fetch_with_retry(full_url)
        if not response:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        # ConfigBaseId 추출
        config_base_id = self.extract_config_base_id(full_url, soup)
        if not config_base_id:
            logger.warning(f"Could not extract ConfigBaseId from {full_url}")
            self.errors.append({
                'url': full_url,
                'error': 'Missing ConfigBaseId',
                'type': 'parse_error'
            })
            return None

        # 이름 추출
        names = self.extract_item_name(soup, full_url)
        if not names["ko"]:
            logger.warning(f"Could not extract Korean name from {full_url}")
            self.errors.append({
                'url': full_url,
                'config_base_id': config_base_id,
                'error': 'Missing Korean name',
                'type': 'parse_error'
            })

        # 타입 추출
        item_type = self.extract_item_type(soup, category)

        # 아이콘 URL 추출
        icon_url = self.extract_icon_url(soup)

        item_data = {
            "config_base_id": config_base_id,
            "name_ko": names["ko"] or f"Unknown_{config_base_id}",
            "name_en": names["en"],
            "type": item_type,
            "icon_url": icon_url,
            "source_url": full_url,
            "category": category
        }

        logger.info(f"[OK] Extracted: {config_base_id} - {item_data['name_ko']}")
        return item_data

    def crawl_category_list(self, category: str, url_path: str) -> List[str]:
        """카테고리 목록 페이지에서 아이템 URL 목록 추출"""
        full_url = BASE_URL + url_path

        response = self.fetch_with_retry(full_url)
        if not response:
            return []

        soup = BeautifulSoup(response.text, 'html.parser')

        # 아이템 링크 찾기
        item_links = []

        # 패턴: /ko/ItemName 형식의 링크 (Ember, Fossil, Mod 등)
        # 카테고리 페이지 자체 링크를 제외하고 아이템 링크만 추출
        exclude_paths = ['/ko/Ember', '/ko/Fossil', '/ko/Mod', '/ko/', '/en/', '/tw/', '/cn/', '/ja/', '/ru/']

        for link in soup.find_all('a', href=True):
            href = link.get('href', '')

            # /ko/로 시작하고, 제외 목록에 없으며, 언어 코드만 있는 것이 아닌 경우
            if href.startswith('/ko/') and href not in exclude_paths:
                # 언어 변경 링크 제외 (/ko/, /en/ 등)
                if not href.endswith('/ko/') and not href.endswith('/en/'):
                    # 중복 제거
                    if href not in item_links:
                        item_links.append(href)
                        logger.debug(f"Found item link: {href}")

        logger.info(f"Found {len(item_links)} items in category '{category}'")
        return item_links

    def crawl_all_categories(self) -> Dict[str, Dict]:
        """모든 카테고리 크롤링"""
        all_items = {}

        for category, url_path in CATEGORIES.items():
            logger.info(f"\n{'='*60}")
            logger.info(f"Starting category: {category} ({url_path})")
            logger.info(f"{'='*60}")

            # 1. 카테고리 목록 페이지에서 아이템 URL 추출
            item_urls = self.crawl_category_list(category, url_path)

            if not item_urls:
                logger.warning(f"No items found in category '{category}'")
                continue

            # 2. 각 아이템 상세 페이지 크롤링
            for idx, item_url in enumerate(item_urls, 1):
                logger.info(f"[{idx}/{len(item_urls)}] Crawling: {item_url}")

                item_data = self.crawl_item_detail(item_url, category)
                if item_data:
                    config_id = item_data["config_base_id"]
                    all_items[config_id] = {
                        "name": item_data["name_ko"],
                        "type": item_data["type"],
                        "price": 0,
                        "icon_url": item_data["icon_url"],
                        "name_en": item_data["name_en"],
                        "category": category
                    }

        logger.info(f"\n{'='*60}")
        logger.info(f"Crawling completed: {len(all_items)} items extracted")
        logger.info(f"Errors: {len(self.errors)}")
        logger.info(f"{'='*60}")

        return all_items

    def save_results(self, output_path: Path):
        """결과를 JSON 파일로 저장"""
        # TITrack items_ko.json 형식으로 변환
        titrack_format = {}
        icons_data = {}

        for config_id, data in self.results.items():
            titrack_format[config_id] = {
                "name": data["name"],
                "type": data["type"],
                "price": data["price"]
            }

            if data.get("icon_url"):
                icons_data[config_id] = data["icon_url"]

        # 메인 결과 저장
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(titrack_format, f, ensure_ascii=False, indent=2)

        logger.info(f"[OK] Saved main results to: {output_path}")

        # 아이콘 데이터 별도 저장
        icons_path = output_path.parent / "crawler2_materials_icons.json"
        with open(icons_path, 'w', encoding='utf-8') as f:
            json.dump(icons_data, f, ensure_ascii=False, indent=2)

        logger.info(f"[OK] Saved icon URLs to: {icons_path}")

        # 상세 로그 (디버깅용)
        detailed_path = output_path.parent / "crawler2_materials_detailed.json"
        with open(detailed_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)

        logger.info(f"[OK] Saved detailed data to: {detailed_path}")

        # 에러 로그
        if self.errors:
            errors_path = output_path.parent / "crawler2_materials_errors.json"
            with open(errors_path, 'w', encoding='utf-8') as f:
                json.dump(self.errors, f, ensure_ascii=False, indent=2)

            logger.warning(f"[WARNING] Saved {len(self.errors)} errors to: {errors_path}")

        # 요약 보고서
        summary = {
            "total_items": len(self.results),
            "total_errors": len(self.errors),
            "categories": {},
            "items_with_icons": sum(1 for d in self.results.values() if d.get("icon_url")),
            "items_with_english_names": sum(1 for d in self.results.values() if d.get("name_en"))
        }

        for config_id, data in self.results.items():
            category = data.get("category", "Unknown")
            summary["categories"][category] = summary["categories"].get(category, 0) + 1

        summary_path = output_path.parent / "crawler2_materials_summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        logger.info(f"[OK] Saved summary to: {summary_path}")

        return summary

    def run(self, output_path: Path):
        """크롤러 실행"""
        logger.info("Starting tlidb.com Materials Crawler")
        logger.info(f"Target categories: {', '.join(CATEGORIES.keys())}")
        logger.info(f"Rate limit: {RATE_LIMIT}s per request")
        logger.info(f"Max retries: {MAX_RETRIES}")
        logger.info(f"Output path: {output_path}")

        # 크롤링 시작
        self.results = self.crawl_all_categories()

        # 결과 저장
        summary = self.save_results(output_path)

        # 요약 출력
        print("\n" + "="*60)
        print("크롤링 완료 요약")
        print("="*60)
        print(f"총 아이템 수: {summary['total_items']}")
        print(f"에러 수: {summary['total_errors']}")
        print(f"아이콘 URL 수집: {summary['items_with_icons']}/{summary['total_items']}")
        print(f"영어 이름 수집: {summary['items_with_english_names']}/{summary['total_items']}")
        print("\n카테고리별 아이템 수:")
        for category, count in summary['categories'].items():
            print(f"  - {category}: {count}")
        print("="*60)


def main():
    """메인 함수"""
    # 출력 경로 설정
    project_root = Path(__file__).parent.parent
    output_path = project_root / "output" / "crawler2_materials.json"

    # 크롤러 실행
    crawler = TLIDBCrawler()
    crawler.run(output_path)


if __name__ == "__main__":
    main()
