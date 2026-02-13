"""HTML 구조 디버깅 스크립트"""
import requests
from bs4 import BeautifulSoup
import json

url = "https://tlidb.com/ko/Universal_Items"
headers = {"User-Agent": "TITrack/1.0.2"}

response = requests.get(url, headers=headers, timeout=30)
soup = BeautifulSoup(response.text, 'html.parser')

output = []

output.append("=" * 60)
output.append("All links on the page:")
output.append("=" * 60)

all_links = []
for idx, link in enumerate(soup.find_all('a', href=True)[:100], 1):
    href = link['href']
    text = link.get_text(strip=True)[:50]
    all_links.append({"index": idx, "text": text, "href": href})
    output.append(f"{idx}. [{text}] -> {href}")

output.append("\n" + "=" * 60)
output.append("Links starting with /ko/ but NOT navigation:")
output.append("=" * 60)

# 네비게이션 카테고리 제외
nav_pages = ["/ko/Hero", "/ko/Talent", "/ko/Inventory", "/ko/Legendary_Gear",
             "/ko/Active_Skill", "/ko/Support_Skill", "/ko/Passive_Skill",
             "/ko/Activation_Medium_Skill", "/ko/Craft", "/ko/Gear_Empowerment",
             "/ko/Dream_Talking", "/ko/Outfit", "/ko/Commodity"]

item_links = []
for link in soup.find_all('a', href=True):
    href = link['href']
    if href.startswith('/ko/') and href not in nav_pages and '#' not in href:
        # /ko/로 시작하되 네비게이션이 아닌 것들
        text = link.get_text(strip=True)
        if text:  # 빈 텍스트 제외
            item_links.append({"text": text, "href": href})

# 중복 제거
seen = set()
unique_items = []
for item in item_links:
    if item['href'] not in seen:
        seen.add(item['href'])
        unique_items.append(item)
        output.append(f"{len(unique_items)}. [{item['text']}] -> {item['href']}")

output.append("\n" + "=" * 60)
output.append(f"Total unique item links found: {len(unique_items)}")
output.append("=" * 60)

# 파일로 저장
output_file = "output/html_debug.txt"
with open(output_file, 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))

print(f"Debug output saved to: {output_file}")
print(f"Total unique item links: {len(unique_items)}")

# JSON으로도 저장
with open("output/html_debug.json", 'w', encoding='utf-8') as f:
    json.dump({"all_links": all_links, "item_links": unique_items}, f, ensure_ascii=False, indent=2)
