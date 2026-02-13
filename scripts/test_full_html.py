"""전체 HTML 저장 및 분석"""
import requests

url = "https://tlidb.com/ko/Flame_Elementium"
headers = {"User-Agent": "TITrack/1.0.2"}

response = requests.get(url, headers=headers, timeout=30)

# HTML 저장
with open("output/flame_elementium.html", 'w', encoding='utf-8') as f:
    f.write(response.text)

print(f"HTML saved to: output/flame_elementium.html")
print(f"Size: {len(response.text)} characters")

# chuhuoyuanzhiV3 검색
if 'chuhuoyuanzhiV3' in response.text:
    print("\n[OK] Found 'chuhuoyuanzhiV3' in HTML")

    # 해당 라인 찾기
    lines = response.text.split('\n')
    for idx, line in enumerate(lines):
        if 'chuhuoyuanzhiV3' in line:
            print(f"\nLine {idx}: {line.strip()[:200]}")
else:
    print("\n[WARN] 'chuhuoyuanzhiV3' NOT found in HTML")
    print("Searching for '100300' instead...")

    lines = response.text.split('\n')
    for idx, line in enumerate(lines):
        if '100300' in line:
            print(f"\nLine {idx}: {line.strip()[:200]}")
