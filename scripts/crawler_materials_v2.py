"""
tlidb.com Materials Crawler v2
수동 아이템 목록 기반 크롤러
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
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("crawler.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 설정
BASE_URL = "https://tlidb.com"
RATE_LIMIT = 1.0
MAX_RETRIES = 3
TIMEOUT = 30

# 수동으로 정의한 아이템 목록 (WebFetch로 확인한 정보 기반)
ITEMS = {
    "Ember": [
        "Fine_Ember",
        "Precious_Ember",
        "Matchless_Ember",
        "Ultimate_Ember"
    ],
    "Fossil": [
        "Truth_Fossil",
        "Inheritance_Axis",
        "Sacred_Fossil"
    ],
    "Mod": [
        "Base_Mod",
        "Expansion_Mod_-_Warlock",
        "Expansion_Mod_-_Vanguard",
        "Expansion_Mod_-_Sniper",
        "Expansion_Mod_-_Tank"
    ]
}

class TLIDBCrawlerV2:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        })
        self.results = {}
        self.errors = []

    def fetch_with_retry(self, url: str) -> Optional[requests.Response]:
        """재시도 로직이 포함된 HTTP GET 요청"""
        for attempt in range(MAX_RETRIES):
            try:
                time.sleep(RATE_LIMIT)
                logger.info(f"Fetching: {url} (attempt {attempt + 1}/{MAX_RETRIES})")

                response = self.session.get(url, timeout=TIMEOUT)
                response.raise_for_status()
                return response

            except requests.exceptions.RequestException as e:
                wait_time = (2 ** attempt) * RATE_LIMIT
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

    def extract_config_base_id(self, soup: BeautifulSoup) -> Optional[str]:
        """HTML에서 ConfigBaseId 추출"""
        text_content = soup.get_text()

        # "id: 123456" 패턴
        patterns = [
            r'\bid:\s*(\d+)',
            r'ConfigBaseId["\s:]+(\d+)',
            r'baseId["\s:]+(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                config_id = match.group(1)
                logger.debug(f"Found ConfigBaseId: {config_id}")
                return config_id

        return None

    def extract_item_name(self, soup: BeautifulSoup, url: str) -> Dict[str, str]:
        """한국어 및 영어 아이템 이름 추출"""
        names = {"ko": None, "en": None}

        # 한국어 이름 (h1 태그)
        h1_tags = soup.find_all('h1')
        for h1 in h1_tags:
            text = h1.get_text(strip=True)
            if text and re.search(r'[가-힣]', text):
                names["ko"] = text
                logger.debug(f"Found Korean name: {text}")
                break

        # 영어 이름 (URL에서)
        match = re.search(r'/ko/([^/]+)$', url)
        if match:
            en_name = match.group(1).replace('_', ' ')
            names["en"] = en_name
            logger.debug(f"Found English name: {en_name}")

        return names

    def extract_icon_url(self, soup: BeautifulSoup) -> Optional[str]:
        """아이템 아이콘 URL 추출"""
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src')
            if src and 'cdn.tlidb.com' in src and 'Icon' in src:
                if src.startswith('//'):
                    src = 'https:' + src
                logger.debug(f"Found icon: {src}")
                return src
        return None

    def crawl_item(self, item_name: str, category: str) -> Optional[Dict]:
        """개별 아이템 크롤링"""
        url = f"{BASE_URL}/ko/{item_name}"

        response = self.fetch_with_retry(url)
        if not response:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        # ConfigBaseId 추출
        config_base_id = self.extract_config_base_id(soup)
        if not config_base_id:
            logger.warning(f"Could not extract ConfigBaseId from {url}")
            self.errors.append({
                'url': url,
                'item_name': item_name,
                'error': 'Missing ConfigBaseId',
                'type': 'parse_error'
            })
            return None

        # 이름 추출
        names = self.extract_item_name(soup, url)
        if not names["ko"]:
            logger.warning(f"Could not extract Korean name from {url}")

        # 타입 매핑
        type_mapping = {
            "Ember": "엠버",
            "Fossil": "화석",
            "Mod": "코어"
        }
        item_type = type_mapping.get(category, "재료")

        # 아이콘 URL
        icon_url = self.extract_icon_url(soup)

        item_data = {
            "config_base_id": config_base_id,
            "name_ko": names["ko"] or f"Unknown_{config_base_id}",
            "name_en": names["en"] or item_name.replace('_', ' '),
            "type": item_type,
            "icon_url": icon_url,
            "source_url": url,
            "category": category
        }

        logger.info(f"[OK] [{config_base_id}] {item_data['name_ko']} ({item_data['name_en']})")
        return item_data

    def crawl_all_items(self) -> Dict[str, Dict]:
        """모든 아이템 크롤링"""
        all_items = {}

        for category, item_list in ITEMS.items():
            if not item_list:
                logger.info(f"Skipping empty category: {category}")
                continue

            logger.info(f"\n{'='*60}")
            logger.info(f"Category: {category} ({len(item_list)} items)")
            logger.info(f"{'='*60}")

            for idx, item_name in enumerate(item_list, 1):
                logger.info(f"[{idx}/{len(item_list)}] {item_name}")

                item_data = self.crawl_item(item_name, category)
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
        logger.info(f"Total items extracted: {len(all_items)}")
        logger.info(f"Total errors: {len(self.errors)}")
        logger.info(f"{'='*60}")

        return all_items

    def save_results(self, output_path: Path):
        """결과 저장"""
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

        # 메인 결과
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(titrack_format, f, ensure_ascii=False, indent=2)
        logger.info(f"[OK] Saved: {output_path}")

        # 아이콘
        icons_path = output_path.parent / "crawler2_materials_icons.json"
        with open(icons_path, 'w', encoding='utf-8') as f:
            json.dump(icons_data, f, ensure_ascii=False, indent=2)
        logger.info(f"[OK] Saved: {icons_path}")

        # 상세 데이터
        detailed_path = output_path.parent / "crawler2_materials_detailed.json"
        with open(detailed_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        logger.info(f"[OK] Saved: {detailed_path}")

        # 에러 로그
        if self.errors:
            errors_path = output_path.parent / "crawler2_materials_errors.json"
            with open(errors_path, 'w', encoding='utf-8') as f:
                json.dump(self.errors, f, ensure_ascii=False, indent=2)
            logger.warning(f"[WARNING] Errors saved: {errors_path}")

        # 요약
        summary = {
            "total_items": len(self.results),
            "total_errors": len(self.errors),
            "items_with_icons": sum(1 for d in self.results.values() if d.get("icon_url")),
            "categories": {}
        }

        for config_id, data in self.results.items():
            category = data.get("category", "Unknown")
            summary["categories"][category] = summary["categories"].get(category, 0) + 1

        summary_path = output_path.parent / "crawler2_materials_summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        logger.info(f"[OK] Saved: {summary_path}")

        return summary

    def run(self, output_path: Path):
        """크롤러 실행"""
        logger.info("="*60)
        logger.info("TITrack Materials Crawler v2")
        logger.info("="*60)

        self.results = self.crawl_all_items()
        summary = self.save_results(output_path)

        print("\n" + "="*60)
        print("크롤링 완료")
        print("="*60)
        print(f"총 아이템: {summary['total_items']}")
        print(f"에러: {summary['total_errors']}")
        print(f"아이콘: {summary['items_with_icons']}/{summary['total_items']}")
        print("\n카테고리별:")
        for category, count in summary['categories'].items():
            print(f"  {category}: {count}")
        print("="*60)


def main():
    project_root = Path(__file__).parent.parent
    output_path = project_root / "output" / "crawler2_materials.json"

    crawler = TLIDBCrawlerV2()
    crawler.run(output_path)


if __name__ == "__main__":
    main()
