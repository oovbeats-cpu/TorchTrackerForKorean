"""
Test script to debug HTML structure
"""

import requests
from bs4 import BeautifulSoup

url = "https://tlidb.com/ko/Ember"

response = requests.get(url, headers={
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

soup = BeautifulSoup(response.text, 'html.parser')

# 모든 링크 출력
print("=== All Links ===")
for link in soup.find_all('a', href=True):
    href = link.get('href')
    text = link.get_text(strip=True)
    print(f"{href} -> {text}")

print("\n=== Links starting with /ko/ ===")
for link in soup.find_all('a', href=True):
    href = link.get('href')
    if href.startswith('/ko/'):
        text = link.get_text(strip=True)
        print(f"{href} -> {text}")

# HTML 파일 저장
with open("C:\\Users\\f4u12\\OneDrive\\문서\\Github\\TorchTrackerForKorean\\output\\ember_page.html", 'w', encoding='utf-8') as f:
    f.write(response.text)

print(f"\nHTML saved to output/ember_page.html")
print(f"Total links: {len(soup.find_all('a', href=True))}")
