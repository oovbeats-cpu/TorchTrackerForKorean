# Supabase 동기화 문제 해결 가이드

> **작성일**: 2026-02-12
> **문제**: 아이템 동기화 0개, 가격 데이터 로드 필요

---

## 문제 요약

### 문제 1: 아이템 동기화 0개 ❌

**현상**:
- Supabase items: **2,480개** (최신)
- 로컬 DB items: **1,809개** (오래된 데이터)
- 동기화 결과: **0개 동기화됨**

**원인**:
- `items_last_sync` 설정이 Supabase `updated_at`보다 최신이거나
- `fetch_items_delta(since)` 로직이 잘못된 날짜로 필터링
- 결과: 델타 동기화가 아무것도 가져오지 않음

**해결책**: 강제 전체 동기화 (since=NULL)

---

### 문제 2: 가격 데이터 로드 필요 📊

**요청**:
- `ref/v/20260212.txt` (2,447개) → Supabase aggregated_prices
- 로컬 DB exchange 가격 (44개) → Supabase aggregated_prices

**우선순위**:
1. 로컬 DB exchange 가격 (실제 거래소 가격, 최우선)
2. 20260212.txt 가격 (폴백)

---

## 해결 단계

### Step 1: 진단 실행 (현재 상태 확인)

```bash
python scripts/diagnose_sync_issues.py
```

**출력 예시**:
```
================================================================================
[1] 로컬 DB 상태
================================================================================

  Items 테이블: 1809개
  샘플 (처음 3개):
    100300: Flame Elementium | icon: 있음
    100301: Netherrealm Currency | icon: 있음
    100302: Chrono Watch | icon: 있음

  items_last_sync: 2026-02-12T10:00:00Z  # ← 이 값이 문제!

  Exchange 가격: 44개

================================================================================
[2] Supabase 상태
================================================================================

  Items 테이블: 2480개
  가장 오래된 updated_at: 2026-02-11T00:00:00Z
  가장 최근 updated_at: 2026-02-11T12:00:00Z  # ← items_last_sync보다 과거!

  Aggregated Prices 테이블: 44개

================================================================================
[4] 아이템 동기화 0개 문제 진단
================================================================================

  로컬 items_last_sync: 2026-02-12T10:00:00Z
  Supabase fetch_items_delta(since=2026-02-12T10:00:00Z): 0개

  ❌ 문제 발견: items_last_sync 이후 업데이트된 아이템이 없음
     → items_last_sync가 Supabase updated_at보다 최신이거나
     → Supabase items의 updated_at이 과거 날짜일 수 있음

  해결책: items_last_sync를 NULL로 초기화하거나
           fetch_items_delta(since=NULL)로 전체 동기화
```

---

### Step 2: 아이템 강제 전체 동기화 ⚡

```bash
python scripts/force_full_item_sync.py
```

**작업 내역**:
1. Supabase에서 `fetch_items_delta(since=NULL)` 호출 → 2,480개 아이템 가져오기
2. 로컬 DB items 테이블에 UPSERT (100개/배치)
3. `items_last_sync` 설정을 현재 시각으로 업데이트
4. 검증: 총 개수, name_en/icon_url 채워진 비율

**출력 예시**:
```
================================================================================
TITrack - Supabase Items 강제 전체 동기화
================================================================================

✅ Supabase 연결: https://qhjulyngunwiculnharg.supabase.co
✅ 로컬 DB: C:\Users\...\TITrack\tracker.db

[1/4] Supabase items 가져오기 (전체)...
  ✅ 2480개 아이템 가져옴
  샘플: 100300 - Flame Elementium

[2/4] 로컬 DB에 동기화 중...
  진행: 100/2480 (4%)
  진행: 200/2480 (8%)
  ...
  진행: 2480/2480 (100%)
  ✅ 2480개 아이템 동기화 완료

[3/4] items_last_sync 업데이트 중...
  ✅ items_last_sync = 2026-02-12T18:30:00Z

[4/4] 검증 중...
  총 아이템: 2480개
  name_en 채워짐: 26개 (1%)
  icon_url 채워짐: 2432개 (98%)
  items_last_sync: 2026-02-12T18:30:00Z

================================================================================
[완료] 2480개 아이템 동기화 완료!
================================================================================
```

**예상 결과**:
- ✅ 로컬 DB items: 1,809개 → **2,480개**
- ✅ name_en: 26개 (1.0%) - 영어 이름은 크롤링 데이터에 일부만 존재
- ✅ icon_url: 2,432개 (98.1%) - 아이콘 URL 거의 완벽
- ✅ items_last_sync: 최신 시각으로 업데이트

---

### Step 3: 가격 데이터 통합 업로드 💰

```bash
python scripts/upload_all_prices_to_supabase.py
```

**작업 내역**:
1. 로컬 DB prices 테이블에서 `source='exchange'` 가격 로드
2. `ref/v/20260212.txt` 가격 로드
3. 병합 (로컬 exchange 우선, 중복 제외)
4. Supabase aggregated_prices 테이블에 UPSERT (100개/배치)
5. 검증: 총 행 수 확인

**출력 예시**:
```
================================================================================
TITrack - 모든 가격 데이터 → Supabase 업로드
================================================================================

[1/6] Supabase 연결 중...
  ✅ 연결 성공: https://qhjulyngunwiculnharg.supabase.co

[2/6] 로컬 DB 확인 중...
  ✅ 로컬 DB: C:\Users\...\TITrack\tracker.db

[3/6] 가격 데이터 로드 중...
  ✅ 로컬 DB: 44개 exchange 가격
  ✅ 20260212.txt: 2447개 가격

[4/6] 가격 데이터 병합 중...

  병합 결과:
    - Local exchange: 44개
    - 20260212.txt (신규): 2403개
    - 총합: 2447개

[5/6] Supabase 업로드 중 (2447개)...
  진행: 100/2447 (4%)
  진행: 200/2447 (8%)
  ...
  진행: 2447/2447 (100%)

  ✅ 업로드 완료!
     Total: 2447
     Uploaded: 2447
     Errors: 0

[6/6] 검증 중...
  ✅ Supabase aggregated_prices: 2447 rows

================================================================================
[완료] 모든 가격 데이터 업로드 완료!
================================================================================

우선순위:
  1. 로컬 DB exchange 가격 (실제 거래소 가격)
  2. 20260212.txt 가격 (폴백)
```

**예상 결과**:
- ✅ Supabase aggregated_prices: 44개 → **2,447개**
- ✅ 로컬 exchange 가격 44개 우선 적용
- ✅ 20260212.txt 가격 2,403개 추가 (중복 제외)

---

## 검증 쿼리 (Supabase SQL Editor)

동기화 완료 후 Supabase SQL Editor에서 다음 쿼리를 실행하여 검증하세요:

```sql
-- 1. items 테이블 총 개수
SELECT COUNT(*) AS total_items FROM items;
-- 예상: 2480

-- 2. icon_url 채워진 비율
SELECT
  COUNT(*) AS total,
  COUNT(icon_url) AS with_icon,
  ROUND(COUNT(icon_url) * 100.0 / COUNT(*), 2) AS icon_coverage_pct
FROM items;
-- 예상: 98.1%

-- 3. aggregated_prices 테이블 총 개수
SELECT COUNT(*) AS total_prices FROM aggregated_prices;
-- 예상: 2447

-- 4. 가격 통계
SELECT
  MIN(price_fe_median) AS min_price,
  MAX(price_fe_median) AS max_price,
  AVG(price_fe_median) AS avg_price,
  COUNT(DISTINCT config_base_id) AS unique_items
FROM aggregated_prices;

-- 5. 아이템 통계 (RPC 함수)
SELECT * FROM get_item_stats();
-- 예상: total_items=2480, items_with_icon=2432
```

---

## 문제 해결 (Troubleshooting)

### 에러 1: `supabase package not installed`

**원인**: supabase SDK 미설치

**해결**:
```bash
pip install supabase
```

---

### 에러 2: `Supabase credentials not found`

**원인**: `.env` 파일에 Supabase URL/Key 없음

**해결**:
1. 프로젝트 루트에 `.env` 파일 생성
2. 다음 내용 추가:
   ```env
   TITRACK_SUPABASE_URL=https://qhjulyngunwiculnharg.supabase.co
   TITRACK_SUPABASE_KEY=sb_publishable_YgqYSMUarrM_IKvcNpJlBw_KwTpp7ho
   ```

---

### 에러 3: `schema "cron" does not exist`

**원인**: Migration 001의 pg_cron 호출 (이미 수정됨)

**해결**: 최신 Migration 001 파일 사용 (pg_cron 주석 처리됨)

---

### 에러 4: `column reference "category" is ambiguous`

**원인**: Migration 002의 `get_item_stats()` 함수 (이미 수정됨)

**해결**: 최신 Migration 002 파일 사용 또는 `supabase/migrations/fix_get_item_stats.sql` 실행

---

## 스크립트 파일 목록

| 스크립트 | 용도 |
|----------|------|
| `scripts/diagnose_sync_issues.py` | 동기화 문제 진단 (현재 상태 확인) |
| `scripts/force_full_item_sync.py` | 아이템 강제 전체 동기화 (since=NULL) |
| `scripts/load_prices_from_20260212.py` | 20260212.txt → Supabase (가격만) |
| `scripts/upload_all_prices_to_supabase.py` | 로컬 exchange + 20260212.txt 통합 업로드 (권장) |
| `scripts/upload_local_prices_to_supabase.py` | 로컬 exchange → Supabase (가격만) |

---

## 완료 체크리스트

- [ ] Step 1: `diagnose_sync_issues.py` 실행 → 문제 확인
- [ ] Step 2: `force_full_item_sync.py` 실행 → 2,480개 아이템 동기화
- [ ] Step 3: `upload_all_prices_to_supabase.py` 실행 → 2,447개 가격 업로드
- [ ] 검증: Supabase SQL Editor에서 검증 쿼리 실행
- [ ] 로컬 앱 재시작 후 아이템 이름/아이콘 정상 표시 확인
- [ ] 가격 데이터 정상 로드 확인 (거래소 가격 > 클라우드 가격 > 로컬 가격)

---

## 추가 작업 필요 사항

### 1. name_en/name_cn 보완 (선택)

현재 name_en은 1%, name_cn은 0% 커버리지입니다.

**해결 방안**:
- tlidb.com 크롤링 (모든 카테고리 순회)
- 또는 Supabase items 테이블 수동 수정

**스크립트 예시**:
```bash
# TODO: tlidb.com 크롤러 작성
python scripts/crawl_tlidb_all_items.py
python scripts/load_crawled_items_to_supabase.py
```

---

### 2. 가격 데이터 주기적 업데이트 (선택)

로컬 DB exchange 가격이 업데이트될 때마다 Supabase에 자동 동기화

**구현 방안**:
- `sync/manager.py`에 `sync_exchange_prices()` 메서드 추가
- 거래소 가격 파싱 시 자동 업로드

---

## 참고 문서

- [`docs/supabase_architecture.md`](supabase_architecture.md) - Supabase 아키텍처 설계
- [`docs/supabase_setup_guide.md`](supabase_setup_guide.md) - Supabase 초기 설정 가이드
- [`docs/Tasks.md`](Tasks.md) - 작업 관리 (세션 #5 참조)

---

**작성**: Backend Agent (TITrack Project)
**날짜**: 2026-02-12
