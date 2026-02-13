#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tlidb.com 스킬/신격 카테고리 크롤러 (Crawler #4)

크롤링 대상:
- /ko/Fluorescent_Memory (찬란한 기억)
- /ko/Active_Skill (액티브 스킬)
- /ko/Support_Skill (보조 스킬)
- /ko/Divinity_Emblems (신력 엠블럼)
"""

import json
import time
import re
import sys
from typing import Dict, List, Optional
from pathlib import Path
import sys
import codecs

# Windows 콘솔 UTF-8 강제 설정 (한글 깨짐 방지)
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')



# Windows 콘솔 UTF-8 출력 설정
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("[ERROR] 필수 라이브러리 설치 필요: pip install requests beautifulsoup4 lxml")
    exit(1)


# ====================
# 설정
# ====================
BASE_URL = "https://tlidb.com"
USER_AGENT = "TITrack/1.0.2 (+https://github.com/yourusername/TorchTrackerForKorean)"
RATE_LIMIT = 0.5  # 초당 2 요청 (더 빠르게)
OUTPUT_DIR = Path(__file__).parent.parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "crawler4_skills.json"
FETCH_DETAILS = False  # 상세 페이지 크롤링 생략 (카테고리 페이지에 모든 정보 있음)

# 크롤링 대상 카테고리
CATEGORIES = [
    {"path": "/ko/Fluorescent_Memory", "name": "찬란한 기억", "type": "기억"},
    {"path": "/ko/Active_Skill", "name": "액티브 스킬", "type": "스킬"},
    {"path": "/ko/Support_Skill", "name": "보조 스킬", "type": "스킬"},
    {"path": "/ko/Divinity_Emblems", "name": "신력 엠블럼", "type": "엠블럼"},
]

# 통계
stats = {
    "categories_crawled": 0,
    "items_found": 0,
    "items_extracted": 0,
    "errors": 0,
    "requests_made": 0,
}


# ====================
# HTTP 유틸리티
# ====================
def make_request(url: str, max_retries: int = 3) -> Optional[requests.Response]:
    """Rate limit 준수 HTTP 요청"""
    stats["requests_made"] += 1

    for attempt in range(max_retries):
        try:
            time.sleep(RATE_LIMIT)  # Rate limiting
            response = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=(10, 30),  # (connect, read)
            )
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            wait_time = (2 ** attempt) * RATE_LIMIT  # Exponential backoff
            print(f"[WARNING]  요청 실패 (시도 {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                print(f"   {wait_time:.1f}초 후 재시도...")
                time.sleep(wait_time)
            else:
                stats["errors"] += 1
                return None
    return None


# ====================
# 파싱 함수
# ====================
def extract_config_base_id(url_or_text: str) -> Optional[int]:
    """URL 또는 텍스트에서 ConfigBaseId 추출"""
    # 패턴: /item/123456 또는 data-id="123456" 등
    match = re.search(r'/item/(\d+)', url_or_text)
    if match:
        return int(match.group(1))

    match = re.search(r'data-id["\s]*=\s*["\s]*(\d+)', url_or_text)
    if match:
        return int(match.group(1))

    match = re.search(r'\b(\d{6,})\b', url_or_text)  # 6자리 이상 숫자
    if match:
        return int(match.group(1))

    return None


def parse_category_page(html: str, category_type: str) -> List[Dict]:
    """카테고리 페이지에서 아이템 목록 추출"""
    soup = BeautifulSoup(html, 'lxml')
    items = []

    # tlidb.com 특화 파싱: div.row.row-cols-* 구조
    # <div class="col"><div class="d-flex border-top rounded">
    #   <a data-hover="?s=ItemBase%2F6002" href="...">아이템명</a>

    # 패턴 1: tlidb.com의 그리드 레이아웃 (가장 우선)
    grid_items = soup.select('div.row div.col div.d-flex')
    for item_div in grid_items:
        link = item_div.find('a', attrs={'data-hover': True})
        if not link:
            continue

        # data-hover="?s=ItemBase%2F6002" 형식에서 ID 추출 (%2F는 URL 인코딩된 /)
        hover_attr = link.get('data-hover', '')
        config_id = None

        # ItemBase/ID 또는 ItemBase%2FID 형식 찾기
        match = re.search(r'ItemBase(?:%2F|/)(\d+)', hover_attr)
        if match:
            config_id = int(match.group(1))
        else:
            # href에서도 시도
            href = link.get('href', '')
            match = re.search(r'/item/(\d+)', href)
            if match:
                config_id = int(match.group(1))

        if not config_id:
            continue

        # 한국어 이름 추출
        name_ko = link.get_text(strip=True)

        if name_ko and config_id:
            items.append({
                "config_base_id": config_id,
                "name_ko": name_ko,
                "type": category_type,
                "url": f"{BASE_URL}/{link['href']}" if not link['href'].startswith('http') else link['href']
            })

    # 패턴 2: 테이블 형식 (폴백)
    if not items:
        rows = soup.select('table.item-table tr, table.items-table tr, table tbody tr')
        for row in rows:
            link = row.find('a', href=re.compile(r'/item/\d+'))
            if not link:
                continue

            config_id = extract_config_base_id(link['href'])
            if not config_id:
                continue

            name_ko = (
                link.get('title', '').strip() or
                link.get_text(strip=True) or
                link.get('data-name', '').strip()
            )

            if name_ko and config_id:
                items.append({
                    "config_base_id": config_id,
                    "name_ko": name_ko,
                    "type": category_type,
                    "url": f"{BASE_URL}{link['href']}"
                })

    # 패턴 3: 카드 형식 (폴백)
    if not items:
        cards = soup.select('div.item-card, div.skill-card, a.item-link')
        for card in cards:
            link = card if card.name == 'a' else card.find('a', href=re.compile(r'/item/\d+'))
            if not link:
                continue

            config_id = extract_config_base_id(link.get('href', ''))
            if not config_id:
                continue

            name_elem = card.select_one('.item-name, .skill-name, h3, h4')
            name_ko = name_elem.get_text(strip=True) if name_elem else link.get_text(strip=True)

            if name_ko and config_id:
                items.append({
                    "config_base_id": config_id,
                    "name_ko": name_ko,
                    "type": category_type,
                    "url": f"{BASE_URL}{link['href']}"
                })

    return items


def extract_item_details(html: str, item_data: Dict) -> Dict:
    """개별 아이템 페이지에서 상세 정보 추출"""
    soup = BeautifulSoup(html, 'lxml')

    # 한국어 이름 재확인 (상세 페이지가 더 정확할 수 있음)
    name_elem = soup.select_one('h1.item-name, h1, .page-title')
    if name_elem:
        name_text = name_elem.get_text(strip=True)
        if name_text and len(name_text) > len(item_data.get("name_ko", "")):
            item_data["name_ko"] = name_text

    # 아이콘 URL 추출
    icon_elem = soup.select_one('img.item-icon, img[src*="icon"], img[src*="skill"]')
    if icon_elem and icon_elem.get('src'):
        icon_url = icon_elem['src']
        if not icon_url.startswith('http'):
            icon_url = BASE_URL + icon_url
        item_data["icon"] = icon_url

    # 설명 추출 (선택 사항)
    desc_elem = soup.select_one('.item-description, .skill-description, .description')
    if desc_elem:
        item_data["description"] = desc_elem.get_text(strip=True)[:200]  # 최대 200자

    return item_data


# ====================
# 메인 크롤링 로직
# ====================
def crawl_category(category: Dict) -> List[Dict]:
    """카테고리 페이지 크롤링"""
    print(f"\n{'='*60}")
    print(f"[DIR] 카테고리: {category['name']} ({category['path']})")
    print(f"{'='*60}")

    url = BASE_URL + category['path']
    response = make_request(url)

    if not response:
        print(f"[ERROR] 카테고리 페이지 접근 실패: {url}")
        return []

    items = parse_category_page(response.text, category['type'])
    print(f"[OK] {len(items)}개 아이템 발견")

    stats["categories_crawled"] += 1
    stats["items_found"] += len(items)

    # 개별 아이템 상세 정보 크롤링 (선택적)
    extracted_items = []
    for i, item in enumerate(items, 1):
        print(f"   [{i}/{len(items)}] {item['name_ko']} (ID: {item['config_base_id']})")

        if FETCH_DETAILS:
            detail_response = make_request(item['url'])
            if detail_response:
                item = extract_item_details(detail_response.text, item)
                stats["items_extracted"] += 1
        else:
            stats["items_extracted"] += 1

        # URL 제거 (출력 파일에 불필요)
        item.pop("url", None)
        extracted_items.append(item)

    return extracted_items


def main():
    """메인 실행 함수"""
    print("=" * 80)
    print("[SEARCH] TITrack Crawler #4: 스킬/신격 카테고리")
    print("=" * 80)
    print(f"대상 사이트: {BASE_URL}")
    print(f"출력 파일: {OUTPUT_FILE}")
    print(f"Rate Limit: {RATE_LIMIT}초/요청")

    OUTPUT_DIR.mkdir(exist_ok=True)

    all_items = []

    # 각 카테고리 크롤링
    for category in CATEGORIES:
        items = crawl_category(category)
        all_items.extend(items)

    # TITrack items_ko.json 형식으로 변환
    items_dict = {}
    for item in all_items:
        config_id = str(item["config_base_id"])
        items_dict[config_id] = {
            "name": item["name_ko"],
            "type": item["type"],
            "price": 0  # 스킬/신격은 거래 불가
        }

        # 아이콘 URL이 있으면 추가 (선택 사항)
        if "icon" in item:
            items_dict[config_id]["icon"] = item["icon"]

    # JSON 저장
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(items_dict, f, ensure_ascii=False, indent=2)

    # 통계 출력
    print("\n" + "=" * 80)
    print("[STATS] 크롤링 완료 통계")
    print("=" * 80)
    print(f"[OK] 크롤링한 카테고리: {stats['categories_crawled']}/{len(CATEGORIES)}")
    print(f"[OK] 발견한 아이템: {stats['items_found']}개")
    print(f"[OK] 추출한 아이템: {stats['items_extracted']}개")
    print(f"[ERROR] 오류 발생: {stats['errors']}회")
    print(f"📡 총 요청 수: {stats['requests_made']}회")
    print(f"💾 출력 파일: {OUTPUT_FILE}")
    print(f"📦 최종 아이템 수: {len(items_dict)}개")

    if stats['errors'] > 0:
        print(f"\n[WARNING]  {stats['errors']}개 오류 발생 - 로그 확인 필요")

    print("\n[OK] 크롤링 완료!")


if __name__ == "__main__":
    main()
