#!/usr/bin/env python3
"""
TLIDB Map Items Crawler
크롤링 대상: 나침반, 탐침, 시즌 나침반 등 맵 관련 아이템
"""

import json
import time
import re
from typing import Dict, List, Optional
from pathlib import Path
import requests
from bs4 import BeautifulSoup

# Configuration
BASE_URL = "https://tlidb.com"
USER_AGENT = "TITrack/1.0.2 (+https://github.com/yourusername/TorchTrackerForKorean)"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}
TIMEOUT = (10, 30)  # connection, read timeout
RATE_LIMIT = 1.0  # seconds between requests

# Target categories
CATEGORIES = [
    {"path": "/ko/Compass", "type": "나침반"},
    {"path": "/ko/Probe", "type": "탐침"},
    {"path": "/ko/Season_Compass", "type": "시즌 나침반"},
]

# Output
OUTPUT_DIR = Path("output")
OUTPUT_FILE = OUTPUT_DIR / "crawler3_maps.json"


class TLIDBCrawler:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.items = {}
        self.errors = []
        self.last_request_time = 0

    def rate_limit(self):
        """Rate limiting: 1 request per second"""
        elapsed = time.time() - self.last_request_time
        if elapsed < RATE_LIMIT:
            time.sleep(RATE_LIMIT - elapsed)
        self.last_request_time = time.time()

    def get_page(self, url: str, max_retries: int = 3) -> Optional[BeautifulSoup]:
        """Fetch and parse HTML page with exponential backoff"""
        for attempt in range(max_retries):
            try:
                self.rate_limit()
                response = self.session.get(url, timeout=TIMEOUT)
                response.raise_for_status()
                response.encoding = 'utf-8'
                return BeautifulSoup(response.text, 'html.parser')
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:  # Rate limited
                    wait_time = (2 ** attempt) * RATE_LIMIT
                    print(f"[!] Rate limited, waiting {wait_time:.1f}s...")
                    time.sleep(wait_time)
                else:
                    print(f"[!] HTTP {e.response.status_code} for {url}")
                    self.errors.append(f"HTTP {e.response.status_code}: {url}")
                    return None
            except Exception as e:
                print(f"[!] Error fetching {url}: {e}")
                self.errors.append(f"Fetch error ({url}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep((2 ** attempt) * RATE_LIMIT)
                else:
                    return None
        return None

    def parse_category_page(self, category_path: str, item_type: str) -> List[Dict]:
        """Parse category listing page and extract item data directly"""
        full_url = f"{BASE_URL}{category_path}"
        soup = self.get_page(full_url)
        if not soup:
            return []

        items = []

        # TLIDB uses card grid with data-hover containing ItemBase ID
        cards = soup.find_all("div", class_="col")
        for card in cards:
            # Extract ConfigBaseId from data-hover attribute
            link = card.find("a", attrs={"data-hover": re.compile(r"ItemBase")})
            if not link:
                continue

            data_hover = link.get("data-hover", "")
            match = re.search(r"ItemBase%2F(\d+)", data_hover)
            if not match:
                continue

            config_id = match.group(1)

            # Extract Korean name from link text
            name_ko = link.get_text(strip=True)
            if not name_ko:
                name_ko = f"알 수 없음 {config_id}"

            # Extract icon URL
            icon_img = card.find("img", src=True)
            icon_url = None
            if icon_img:
                icon_url = icon_img["src"]
                if not icon_url.startswith("http"):
                    icon_url = f"{BASE_URL}{icon_url}"

            items.append({
                "config_base_id": config_id,
                "name": name_ko,
                "type": item_type,
                "price": 0,
                "icon_url": icon_url,
                "source_url": full_url,
            })

        print(f"[OK] Found {len(items)} items in {category_path}")
        return items

    def crawl_category(self, category_path: str, item_type: str):
        """Crawl all items in a category"""
        print(f"\n[+] Crawling category: {category_path} ({item_type})")
        items = self.parse_category_page(category_path, item_type)

        for idx, item_data in enumerate(items, 1):
            config_id = item_data["config_base_id"]
            name = item_data["name"]

            # Store in items_ko.json format
            self.items[config_id] = {
                "name": name,
                "type": item_type,
                "price": 0,
            }
            print(f"  [{idx}/{len(items)}] {config_id}: {name}")

    def run(self):
        """Main crawling workflow"""
        print("[*] Starting TLIDB Map Items Crawler")
        print(f"Target: {len(CATEGORIES)} categories")
        print(f"Rate limit: {RATE_LIMIT}s/request\n")

        # Ensure output directory
        OUTPUT_DIR.mkdir(exist_ok=True)

        # Crawl each category
        for category in CATEGORIES:
            try:
                self.crawl_category(category["path"], category["type"])
            except Exception as e:
                print(f"[!] Category failed: {category['path']} - {e}")
                self.errors.append(f"Category error ({category['path']}): {str(e)}")

        # Save results
        self.save_results()

        # Print summary
        print("\n" + "="*60)
        print(f"[OK] Crawling complete!")
        print(f"Items extracted: {len(self.items)}")
        print(f"Errors: {len(self.errors)}")
        print(f"Output: {OUTPUT_FILE}")

        if self.errors:
            print("\n[!] Errors encountered:")
            for error in self.errors[:10]:  # Show first 10
                print(f"  - {error}")
            if len(self.errors) > 10:
                print(f"  ... and {len(self.errors) - 10} more")

    def save_results(self):
        """Save results in items_ko.json format"""
        output_data = {
            "metadata": {
                "source": "tlidb.com",
                "categories": [cat["path"] for cat in CATEGORIES],
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "item_count": len(self.items),
                "error_count": len(self.errors),
            },
            "items": self.items,
            "errors": self.errors,
        }

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        # Also save items-only version (for merging into items_ko.json)
        items_only_file = OUTPUT_DIR / "crawler3_maps_items_only.json"
        with open(items_only_file, "w", encoding="utf-8") as f:
            json.dump(self.items, f, ensure_ascii=False, indent=2)

        print(f"[OK] Saved to {OUTPUT_FILE}")
        print(f"[OK] Items-only saved to {items_only_file}")


def main():
    crawler = TLIDBCrawler()
    crawler.run()


if __name__ == "__main__":
    main()
