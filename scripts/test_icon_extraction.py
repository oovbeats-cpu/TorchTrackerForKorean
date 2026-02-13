"""아이콘 URL 추출 테스트"""
import requests
from bs4 import BeautifulSoup
import re

items_to_test = [
    "/ko/Flame_Elementium",
    "/ko/망각의_비약",
    "/ko/Energy_Core"
]

headers = {"User-Agent": "TITrack/1.0.2"}

for item_path in items_to_test:
    url = f"https://tlidb.com{item_path}"
    print(f"\n{'='*60}")
    print(f"Testing: {url}")
    print(f"{'='*60}")

    response = requests.get(url, headers=headers, timeout=30)
    soup = BeautifulSoup(response.text, 'html.parser')

    # 모든 이미지 찾기
    all_imgs = soup.find_all('img')
    print(f"Total images found: {len(all_imgs)}")

    # CDN 이미지만 필터링
    cdn_imgs = [img for img in all_imgs if img.get('src') and 'cdn.tlidb.com' in img.get('src')]
    print(f"CDN images found: {len(cdn_imgs)}")

    for idx, img in enumerate(cdn_imgs[:5], 1):
        src = img['src']
        if not src.startswith('http'):
            src = f"https:{src}" if src.startswith('//') else f"https://tlidb.com{src}"
        print(f"  {idx}. {src}")

        # 부모 요소 정보
        parent = img.parent
        print(f"     Parent: {parent.name if parent else 'None'}")

    # h1 태그 확인
    h1 = soup.find('h1')
    if h1:
        print(f"\nItem name (h1): {h1.get_text(strip=True)}")

    # ConfigBaseId 추출
    text = soup.get_text()
    match = re.search(r'\bid:\s*(\d+)', text)
    if match:
        print(f"ConfigBaseId: {match.group(1)}")
