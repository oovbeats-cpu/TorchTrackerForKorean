# tlidb.com 사이트 구조 분석 보고서

**분석 날짜**: 2026-02-12
**분석 범위**: https://tlidb.com/ko/Inventory
**목적**: 아이템 데이터 크롤링을 위한 사이트 구조 파악

---

## 1. 페이지 전체 구조

### 1.1 메인 인벤토리 페이지 (`/ko/Inventory`)

페이지는 **두 개의 주요 섹션**으로 구성됩니다:

1. **장비 (Equipment)** - 왼쪽 섹션
2. **창고 (Storage)** - 오른쪽 섹션

### 1.2 시즌 선택 UI

페이지 상단에는 **13개의 시즌 아이콘**이 표시되어 있습니다:
- Vorax Season (블러드 러스트 시즌, 현재 시즌)
- Overrealm Season
- Outlaw Season
- Sandlord Season
- Arcana Season
- The Frozen Canvas Season
- Clockwork Ballet Season
- Whispering Mist Season
- Nightmare Season
- Aeterna Season
- Cube Season
- Blacksail Season
- Dark Surge Season

---

## 2. 아이템 카테고리 및 URL 패턴

### 2.1 장비 카테고리

| 카테고리 | URL 패턴 | 한국어 이름 |
|----------|----------|-------------|
| **투구** | `/ko/STR_Helmet`, `/ko/DEX_Helmet`, `/ko/INT_Helmet` | 힘 투구, 민첩 투구, 지혜 투구 |
| **흉갑** | `/ko/STR_Chest_Armor`, `/ko/DEX_Chest_Armor`, `/ko/INT_Chest_Armor` | 힘 흉갑, 민첩 흉갑, 지혜 흉갑 |
| **장갑** | `/ko/STR_Gloves`, `/ko/DEX_Gloves`, `/ko/INT_Gloves` | 힘 글러브, 민첩 장갑, 지혜 장갑 |
| **신발** | `/ko/STR_Boots`, `/ko/DEX_Boots`, `/ko/INT_Boots` | 힘 신발, 민첩 신발, 지혜 신발 |
| **한손 무기** | `/ko/Claw`, `/ko/Dagger`, `/ko/One-Handed_Sword`, etc. | 클로, 단검, 한손검 등 (10종) |
| **양손 무기** | `/ko/Two-Handed_Sword`, `/ko/Bow`, `/ko/Crossbow`, etc. | 양손 검, 활, 석궁 등 (9종) |
| **방패** | `/ko/STR_Shield`, `/ko/DEX_Shield`, `/ko/INT_Shield` | 힘 방패, 민첩 방패, 지혜 방패 |
| **장신구** | `/ko/Necklace`, `/ko/Ring`, `/ko/Belt`, `/ko/Spirit_Ring` | 목걸이, 반지, 벨트, 영혼 반지 |
| **히어로** | `/ko/Hero_Memories`, `/ko/Divinity_Slate` | 히어로 추억, 신격의 석판 |
| **특수** | `/ko/Destiny`, `/ko/Ethereal_Prism` | 운명, 제노 프리즘 |
| **블러드 러스트** | `/ko/Vorax_Limb%3A_Head`, `/ko/Vorax_Limb%3A_Chest`, etc. | 블러드 러스트 부위 (10종) |

**총 장비 카테고리**: 약 50개 이상

### 2.2 창고 (소모품/재료) 카테고리

| URL 패턴 | 한국어 이름 | 설명 |
|----------|-------------|------|
| `/ko/Universal_Items` | 공용 아이템 | 범용 소모품 (12개) |
| `/ko/Fluorescent_Memory` | 찬란한 기억 | 스킬 관련 |
| `/ko/Active_Skill` | 액티브 스킬 | |
| `/ko/Support_Skill` | 보조 스킬 | |
| `/ko/Compass` | 나침반 | 맵 아이템 |
| `/ko/Probe` | 탐침 | |
| `/ko/Season_Compass` | 시즌 나침반 | |
| `/ko/Ember` | 엠버 | 재료 |
| `/ko/Fossil` | 화석 | 재료 |
| `/ko/Fuel` | 연료 | 재료 |
| `/ko/Divinity_Emblems` | 신력 엠블럼 | 신격 관련 |
| `/ko/Mod` | 코어 | 옵션 코어 |
| `/ko/Normal_Organ` | 일반 장기 | 블러드 러스트 시즌 아이템 |

**총 창고 카테고리**: 약 50개 이상

---

## 3. 아이템 목록 페이지 구조

### 3.1 공용 아이템 예시 (`/ko/Universal_Items`)

```
Item /12  ← 총 아이템 개수 표시

[Reset] [Search Box]  ← 검색 기능

[아이템 카드 1]
  - 아이콘 이미지
  - 아이템명 (링크)
  - 설명 텍스트

[아이템 카드 2]
  ...
```

**특징**:
- 각 아이템은 개별 카드로 표시
- 아이템명을 클릭하면 상세 페이지로 이동
- 총 개수가 상단에 표시됨 (`Item /12` 형식)
- 검색 기능 제공 (하지만 영어 검색은 작동하지 않을 수 있음)

### 3.2 장비 카테고리 페이지 (`/ko/STR_Helmet`)

**구조가 완전히 다름!**

```
옵션 /144    Item /12    레전드 장비 /13

[레전드 장비 실석화 /13]  [힘 투구 기본 옵션 /20]
[힘 투구 접사 기본 /10]  [힘 투구 제작]
[힘 투구 아룩다운 꿈 옵션 /19]  [장비 강화 /10]  [잠고대 /6]

옵션 /144

[Search]

[옵션 테이블]
옵션 효과 | 출처 | 유형
-----------|------|------
최대 HP +(54~74) | 힘 투구 | 기본 옵션 구
아마 수치 +(760~960) | 힘 투구 | 기본 옵션 구
...
```

**특징**:
- **탭 구조**: 옵션, Item, 레전드 장비 등 여러 탭
- **옵션 테이블**: 모든 가능한 옵션(stats)과 수치 범위 표시
- **레전드 장비**: 유니크 아이템 목록
- 장비 카테고리는 **개별 아이템보다 옵션/스탯을 중심으로 구성**

---

## 4. 개별 아이템 상세 페이지

### 4.1 URL 패턴

```
https://tlidb.com/ko/{ITEM_SLUG}
```

예시:
- `https://tlidb.com/ko/Elixir_of_Oblivion` (망각의 비약)
- `https://tlidb.com/ko/Flame_Elementium` (최초의 불꽃 결정)

### 4.2 페이지 구조

```html
[시즌 아이콘들]

<h1>아이템명 (한국어)</h1>

[카드 1: SS11시즌]
  - 아이콘 이미지
  - 아이템명 (h5)
  - 타입 (예: "연료")
  - 설명 텍스트

[카드 2: SS10시즌]
  (동일 구조)

[카드 3: 드랍 출처]
  - 드랍 위치 링크들

[카드 4: Info]
  id: 100300  ← ConfigBaseId!
```

### 4.3 추출 가능한 데이터

| 필드 | 추출 방법 | 예시 |
|------|-----------|------|
| **ConfigBaseId** | Info 카드에서 `id: (\d+)` 정규식 | `100300` |
| **한국어 이름** | `<h1>` 태그 또는 카드 내 `<h5>` | `최초의 불꽃 결정` |
| **영어 이름** | URL slug 또는 페이지 title | `Flame_Elementium` |
| **타입** | 카드 내 작은 텍스트 | `연료` |
| **아이콘 URL** | `<img src="...">` | `https://cdn.tlidb.com/UI/Textures/...` |
| **설명** | 카드 내 본문 텍스트 | `고급 제작 재료...` |
| **드랍 출처** | 드랍 출처 카드 | 링크 목록 |

### 4.4 시즌별 차이점

- 대부분의 아이템은 **SS11시즌**과 **SS10시즌** 두 카드가 있음
- 시즌별로 설명이나 스탯이 다를 수 있음
- **ID는 시즌에 관계없이 동일**

---

## 5. 크롤링 전략 제안

### 5.1 "Item" 탭과 "레전드 장비 탭"의 차이

**추가 조사 필요**:
- 장비 카테고리 페이지에서 "Item /12" 탭과 "레전드 장비 /13" 탭의 구조가 정확히 어떤지 확인 필요
- 현재 분석에서는 옵션 테이블만 확인됨

**예상**:
- **Item 탭**: 일반 베이스 아이템 목록 (12개)
- **레전드 장비 탭**: 유니크/레전드 아이템 목록 (13개)

### 5.2 크롤링 단계별 전략

#### Phase 1: 카테고리 목록 수집
1. `/ko/Inventory` 페이지 파싱
2. 모든 카테고리 링크 추출 (약 100개)
3. URL 패턴별로 분류 (장비 vs 창고)

#### Phase 2: 아이템 목록 수집
**창고 카테고리** (간단):
```python
for category_url in storage_categories:
    items = extract_item_cards(category_url)
    for item in items:
        item_slug = item['url'].split('/')[-1]
        item_details_urls.append(f"https://tlidb.com/ko/{item_slug}")
```

**장비 카테고리** (복잡):
1. 각 장비 카테고리 페이지 방문
2. "Item" 탭 클릭 (JavaScript 필요?)
3. 아이템 목록 추출
4. "레전드 장비" 탭 클릭
5. 레전드 아이템 목록 추출

#### Phase 3: 개별 아이템 상세 정보 수집
```python
for item_url in all_item_urls:
    item_data = extract_item_details(item_url)
    # ConfigBaseId, 한국어명, 영어명, 타입, 아이콘 등 추출
    items_dict[item_data['id']] = {
        'name': item_data['nameKo'],
        'type': item_data['type'],
        'icon': item_data['iconUrl']
    }
```

### 5.3 Rate Limiting 권장사항

```python
import time

RATE_LIMIT = 1.0  # 1초당 1 요청
MAX_RETRIES = 3
TIMEOUT = 10

def fetch_with_retry(url):
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, timeout=TIMEOUT)
            time.sleep(RATE_LIMIT)
            return response
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2 ** attempt)  # Exponential backoff
```

### 5.4 HTML 파싱 패턴

#### 아이템 목록 페이지:
```python
from bs4 import BeautifulSoup

soup = BeautifulSoup(html, 'html.parser')

# 아이템 카드 찾기
item_cards = soup.select('.card-body')

for card in item_cards:
    link = card.find('a')
    if link:
        item_name = link.text.strip()
        item_url = link['href']
        # ...
```

#### 아이템 상세 페이지:
```python
# ConfigBaseId 추출
info_card = soup.find(text=re.compile('Info')).parent.parent
id_match = re.search(r'id:\s*(\d+)', info_card.text)
config_base_id = id_match.group(1) if id_match else None

# 한국어 이름
name_ko = soup.find('h1').text.strip()

# 영어 이름
title_parts = soup.title.text.split(' - ')
name_en = title_parts[1] if len(title_parts) > 1 else None

# 아이콘 URL
icon_img = soup.select_one('.card img')
icon_url = icon_img['src'] if icon_img else None

# 타입 (첫 번째 카드에서)
first_card = soup.select('.card')[0]
# 타입은 h5 다음에 오는 작은 텍스트
```

---

## 6. 발견된 주요 아이템

### 6.1 Flame Elementium (화염 원소)

- **ConfigBaseId**: `100300`
- **한국어명**: `최초의 불꽃 결정`
- **영어명**: `Flame_Elementium`
- **타입**: `연료`
- **URL**: `https://tlidb.com/ko/Flame_Elementium`
- **아이콘**: `https://cdn.tlidb.com/UI/Textures/Common/Icon/Item/128/UI_Goods_FlameElementium_Icon_128.webp` (추정)
- **참고**: TITrack에서 기본 화폐로 사용됨

### 6.2 Elixir of Oblivion (망각의 비약)

- **ConfigBaseId**: `5011`
- **한국어명**: `망각의 비약`
- **영어명**: `Elixir_of_Oblivion`
- **타입**: 공용 아이템
- **URL**: `https://tlidb.com/ko/Elixir_of_Oblivion`
- **아이콘**: `https://cdn.tlidb.com/UI/Textures/Common/Icon/Item/128/UI_Goods_Return1_Icon_128.webp`

---

## 7. 다음 단계 권장사항

### 7.1 추가 조사가 필요한 부분

1. **장비 카테고리의 "Item" 탭 구조**
   - JavaScript로 동적으로 로드되는지 확인
   - 탭 클릭 없이 직접 URL로 접근 가능한지 확인
   - 예: `https://tlidb.com/ko/STR_Helmet?tab=items` 같은 패턴 존재 여부

2. **레전드 장비 탭 구조**
   - 유니크 아이템 목록이 어떻게 표시되는지
   - 개별 유니크 아이템의 상세 페이지 구조

3. **가격 정보**
   - tlidb.com에 거래소 가격 정보가 있는지 확인
   - 있다면 어떤 API나 페이지에서 제공되는지

### 7.2 크롤링 우선순위

**높음**:
- 창고 카테고리 (공용 아이템, 나침반, 재료 등) - 구조가 단순함
- Flame Elementium 및 주요 화폐 아이템

**중간**:
- 장비 베이스 아이템 (탭 구조 파악 필요)

**낮음**:
- 레전드 장비 (게임플레이에 중요하지만 TITrack에서 가격 추적 대상이 아닐 수 있음)
- 스킬 아이템 (추적 대상이 아님)

### 7.3 데이터 품질 검증

크롤링 후 반드시 확인:
1. **ConfigBaseId 중복 확인**: 같은 ID가 여러 아이템에 할당되었는지
2. **한영 매칭**: 한국어명과 영어명이 올바르게 매칭되었는지
3. **TITrack 데이터와 비교**: 기존 `items_ko.json`과 ConfigBaseId 일치 여부
4. **누락 확인**: TITrack에 있는데 tlidb에 없는 아이템

---

## 8. 위험 요소 및 대응

| 위험 요소 | 대응 방안 |
|-----------|-----------|
| Rate limit (429 에러) | 1초당 1 요청, exponential backoff |
| 동적 콘텐츠 (JavaScript) | Playwright/Selenium 사용 |
| HTML 구조 변경 | 버전별로 파서 저장, 에러 로깅 |
| 인코딩 문제 (한글) | UTF-8 명시, `ensure_ascii=False` |
| CDN 아이콘 링크 만료 | 주기적 재크롤링 또는 로컬 캐싱 |
| 시즌별 데이터 차이 | 현재 시즌(SS11) 데이터만 추출 |

---

## 9. 최종 출력 형식

TITrack의 `items_ko.json` 호환 형식:

```json
{
  "100300": {
    "name": "최초의 불꽃 결정",
    "type": "연료",
    "price": 1
  },
  "5011": {
    "name": "망각의 비약",
    "type": "공용 아이템",
    "price": 0
  }
}
```

**참고**:
- `price` 필드는 tlidb에서 직접 제공되지 않을 수 있음 (기본값 0 설정)
- 추후 거래소 API나 클라우드 가격으로 업데이트

---

## 10. 요약

### 크롤링 가능 여부: ✅ **가능**

### 난이도:
- **창고 아이템**: ⭐ 쉬움
- **장비 아이템**: ⭐⭐ 중간 (탭 구조 파악 필요)
- **레전드 아이템**: ⭐⭐⭐ 어려움 (추가 조사 필요)

### 예상 작업 시간:
- 구조 분석 완료: ✅ (이 문서)
- 크롤러 개발: 4-8 시간
- 데이터 검증 및 정제: 2-4 시간
- **총**: 6-12 시간

### 다음 작업:
1. 장비 카테고리 "Item" 탭 구조 조사
2. 크롤러 프로토타입 개발 (창고 카테고리 대상)
3. ConfigBaseId 추출 및 검증
4. TITrack `items_ko.json` 업데이트

---

**작성자**: Claude (TITrack Web Crawler Agent)
**버전**: 1.0
**상태**: 초기 분석 완료 - 추가 조사 필요
