# TITrack Supabase 클라우드 백엔드 아키텍처

> **버전**: 2.0.0
> **작성일**: 2026-02-12
> **상태**: 설계 단계

---

## 📋 목차

1. [현재 상황 분석](#1-현재-상황-분석)
2. [데이터 통합 전략](#2-데이터-통합-전략)
3. [새 스키마 설계](#3-새-스키마-설계)
4. [마이그레이션 계획](#4-마이그레이션-계획)
5. [데이터 동기화 전략](#5-데이터-동기화-전략)
6. [비용 및 성능 고려사항](#6-비용-및-성능-고려사항)
7. [구현 체크리스트](#7-구현-체크리스트)

---

## 1. 현재 상황 분석

### 1.1 기존 Supabase 스키마 (v1 - Price Crowdsourcing)

| 테이블 | 목적 | 보관 기간 |
|--------|------|-----------|
| `device_registry` | 익명 디바이스 추적 + Rate Limiting | 영구 |
| `price_submissions` | 사용자 가격 제출 (원시 데이터) | 7일 |
| `aggregated_prices` | 시즌별 중앙값 가격 (집계) | 영구 |
| `price_history` | 시간별 가격 스냅샷 (스파크라인용) | 영구 |

**핵심 기능**:
- ✅ 커뮤니티 기반 가격 크라우드소싱
- ✅ 3+ 디바이스 합의 기반 집계
- ✅ 시간당/5분당 자동 집계 (pg_cron)
- ✅ 디바이스당 시간당 100건 제출 제한
- ✅ RLS (Row Level Security) 적용

**제약사항**:
- ❌ 아이템 메타데이터 없음 (이름, 타입, 아이콘)
- ❌ 장비 아이템 추적 불가 (접사 정보 없음)
- ❌ 조건부 가격 저장 불가 (필터 저장 구조 없음)

### 1.2 로컬 데이터 소스

#### items_ko.json (로컬 아이템 메타데이터)
- **총 아이템**: 3,300개 (ConfigBaseId → 한국어 이름/타입/가격)
- **구조**: `{ "100": { "name": "클로", "type": "장비", "price": 0 } }`
- **문제점**:
  - 일부 아이템만 포함 (게임 내 전체 X)
  - 아이콘 URL 없음 (`icon_urls.py`에만 270개 존재)
  - 영어 이름 없음 (중국어는 SQLite `items` 테이블에만)

#### ref/v/full_table.json (TLIDB 크롤링 데이터)
- **총 아이템**: 2,447개 (주로 장비 베이스 타입)
- **구조**: items_ko.json과 동일
- **용도**: items_ko.json 업데이트 소스

#### SQLite items 테이블 (로컬 DB)
```sql
CREATE TABLE items (
    config_base_id INTEGER PRIMARY KEY,
    name_en TEXT,
    name_cn TEXT,
    type_cn TEXT,
    icon_url TEXT,
    url_en TEXT,
    url_cn TEXT
)
```
- **현재 활용**: 이름 폴백 체인 (한국어 → 영어 → "알 수 없음 {id}")
- **문제점**: 한국어 이름 없음 (items_ko.json에만)

---

## 2. 데이터 통합 전략

### 2.1 3단계 통합 전략

#### Phase 1: 아이템 마스터 데이터 (기초 인프라)
**목표**: 모든 아이템의 기본 정보를 Supabase에 중앙화

**데이터 소스 통합**:
```
items_ko.json (3,300)  ─┐
                        ├─→ Supabase items 테이블
ref/v/*.json (2,447)   ─┤     (3,500+ unique ConfigBaseIds)
                        │
icon_urls.py (270)     ─┘
```

**이점**:
- 클라이언트가 최신 아이템 이름/아이콘을 항상 다운로드 가능
- items_ko.json 수동 업데이트 불필요 (Supabase가 SSOT)
- 새 시즌 아이템 자동 배포 (클라이언트 재빌드 없이)

#### Phase 2: 장비 베이스 타입 (장비 추적 기반)
**목표**: 장비 카테고리와 기본 속성 저장

**데이터 구조**:
- 무기 타입 (Claw, Hammer, Sword, Axe, Dagger 등)
- 방어구 슬롯 (Helmet, Armor, Gloves, Boots, Belt)
- 액세서리 (Ring, Amulet, Quiver)

**제약사항**:
- ❌ 접사(Affix) 정보는 로그에 없음
- ✅ 단순 통계 추적 가능 (획득 횟수, 기본 가격)

#### Phase 3: 조건부 가격 (미래 확장)
**목표**: 필터 기반 장비 가격 저장 (예: "Fire Res +50 이상")

**전제조건**:
- 게임 로그에서 거래소 필터 정보 파싱 (현재 미구현)
- 실제 로그 샘플 필요 (Tasks.md Phase 1 BLOCKER)

**구현 시기**: Phase 1-2 완료 후 재평가

### 2.2 데이터 동기화 방향

```
┌─────────────────┐          ┌──────────────────┐
│  Supabase       │          │  TITrack Client  │
│  (클라우드 SSOT) │          │  (로컬 캐시)      │
└─────────────────┘          └──────────────────┘
        │                             │
        │  1. 아이템 메타데이터 다운로드  │
        │◄────────────────────────────│
        │                             │
        │  2. 가격 집계 다운로드 (5분)  │
        │◄────────────────────────────│
        │                             │
        │  3. 가격 제출 업로드 (60초)   │
        │─────────────────────────────►
        │                             │
        │  4. 아이템 히스토리 (1-6시간) │
        │◄────────────────────────────│
```

**핵심 원칙**:
- **Read-Heavy**: 대부분의 클라이언트는 다운로드만 사용 (upload_enabled=false)
- **SSOT**: Supabase가 아이템 메타의 진실의 원천 (items_ko.json은 로컬 폴백)
- **캐싱**: 모든 데이터를 로컬 SQLite에 캐싱 (오프라인 작동)

---

## 3. 새 스키마 설계

### 3.1 아이템 마스터 테이블 (v2 추가)

```sql
-- 아이템 메타데이터 중앙 저장소
CREATE TABLE items (
    config_base_id INTEGER PRIMARY KEY,
    name_ko TEXT,                  -- 한국어 이름
    name_en TEXT,                  -- 영어 이름
    name_cn TEXT,                  -- 중국어 이름
    type_ko TEXT,                  -- 한국어 타입 (화폐, 장비, 재료 등)
    type_en TEXT,                  -- 영어 타입
    icon_url TEXT,                 -- CDN 아이콘 URL
    url_tlidb TEXT,                -- TLIDB 아이템 페이지 링크
    category TEXT,                 -- 대분류 (currency, material, equipment, skill, legendary)
    subcategory TEXT,              -- 소분류 (claw, hammer, sword 등)
    tier INTEGER,                  -- 아이템 티어 (1-10)
    tradeable BOOLEAN DEFAULT TRUE,-- 거래 가능 여부
    stackable BOOLEAN DEFAULT TRUE,-- 스택 가능 여부
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스
CREATE INDEX idx_items_category ON items(category);
CREATE INDEX idx_items_subcategory ON items(subcategory);
CREATE INDEX idx_items_tier ON items(tier);
CREATE INDEX idx_items_updated ON items(updated_at);
```

**RLS 정책**:
```sql
-- 전체 읽기 허용 (퍼블릭 데이터)
CREATE POLICY "Public read access for items"
    ON items
    FOR SELECT
    TO anon, authenticated
    USING (true);
```

### 3.2 장비 베이스 타입 테이블 (Phase 2)

```sql
-- 장비 아이템의 기본 속성
CREATE TABLE equipment_bases (
    config_base_id INTEGER PRIMARY KEY REFERENCES items(config_base_id),
    equipment_type TEXT NOT NULL,  -- weapon, armor, accessory
    slot TEXT NOT NULL,             -- mainhand, offhand, helmet, body, gloves, boots, belt, ring, amulet, quiver
    min_level INTEGER,              -- 최소 착용 레벨
    base_damage_min INTEGER,        -- 기본 공격력 (무기)
    base_damage_max INTEGER,
    base_armor INTEGER,             -- 기본 방어력 (방어구)
    base_evasion INTEGER,           -- 기본 회피 (방어구)
    implicit_affix_id INTEGER,      -- 내재 접사 ID (미래 확장)
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스
CREATE INDEX idx_equipment_type ON equipment_bases(equipment_type);
CREATE INDEX idx_equipment_slot ON equipment_bases(slot);
```

**RLS 정책**:
```sql
CREATE POLICY "Public read access for equipment_bases"
    ON equipment_bases
    FOR SELECT
    TO anon, authenticated
    USING (true);
```

### 3.3 접사 정의 테이블 (Phase 3 - 미래 확장)

```sql
-- 접사(Affix) 정의 (prefix/suffix)
CREATE TABLE affixes (
    affix_id INTEGER PRIMARY KEY,
    name_ko TEXT NOT NULL,
    name_en TEXT,
    affix_type TEXT NOT NULL,      -- prefix, suffix, implicit
    stat_type TEXT NOT NULL,        -- fire_res, crit_chance, life, etc.
    min_value REAL,
    max_value REAL,
    tier INTEGER,                   -- 접사 티어 (T1-T5)
    item_level_req INTEGER,         -- 최소 아이템 레벨
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_affixes_stat ON affixes(stat_type);
CREATE INDEX idx_affixes_tier ON affixes(tier);

CREATE POLICY "Public read access for affixes"
    ON affixes FOR SELECT TO anon, authenticated USING (true);
```

### 3.4 조건부 가격 테이블 (Phase 3 - 미래 확장)

```sql
-- 필터 기반 장비 가격
CREATE TABLE filtered_prices (
    id BIGSERIAL PRIMARY KEY,
    config_base_id INTEGER NOT NULL REFERENCES items(config_base_id),
    season_id INTEGER NOT NULL,
    filters JSONB NOT NULL,         -- 예: {"fire_res": {"min": 50}, "life": {"min": 100}}
    price_fe_median REAL NOT NULL,
    price_fe_p10 REAL,
    price_fe_p90 REAL,
    submission_count INTEGER NOT NULL DEFAULT 0,
    unique_devices INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(config_base_id, season_id, filters)
);

-- 인덱스
CREATE INDEX idx_filtered_prices_lookup ON filtered_prices(config_base_id, season_id);
CREATE INDEX idx_filtered_prices_filters ON filtered_prices USING GIN (filters);
CREATE INDEX idx_filtered_prices_updated ON filtered_prices(updated_at);

CREATE POLICY "Public read access for filtered_prices"
    ON filtered_prices FOR SELECT TO anon, authenticated USING (true);
```

### 3.5 스키마 버전 관리

```sql
-- 스키마 버전 추적
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMPTZ DEFAULT NOW()
);

-- 초기 버전 기록
INSERT INTO schema_version (version, description) VALUES
    (1, 'Initial price crowdsourcing schema'),
    (2, 'Added items master table');
```

---

## 4. 마이그레이션 계획

### 4.1 Migration 002: Items Master

**파일**: `supabase/migrations/002_items_master.sql`

**실행 순서**:
1. `items` 테이블 생성
2. 인덱스 생성
3. RLS 정책 적용
4. 초기 데이터 로드 (items_ko.json + ref/v/full_table.json)

**데이터 로드 전략**:
```sql
-- Python 스크립트로 실행 (Supabase REST API 사용)
-- 1. items_ko.json 파싱 → 3,300 rows
-- 2. ref/v/full_table.json 파싱 → 2,447 rows (UPSERT)
-- 3. icon_urls.py → 270 rows (UPSERT)
-- 4. 중복 제거 → 최종 ~3,500 unique items
```

**롤백 계획**:
```sql
-- 테이블 삭제 (RLS도 자동 삭제)
DROP TABLE IF EXISTS items CASCADE;
DROP TABLE IF EXISTS schema_version CASCADE;
```

### 4.2 Migration 003: Equipment Bases (Phase 2)

**파일**: `supabase/migrations/003_equipment_bases.sql`

**실행 순서**:
1. `equipment_bases` 테이블 생성
2. `items` 테이블 FK 추가
3. 인덱스 생성
4. RLS 정책 적용

**데이터 소스**: ref/v/*.json (장비 타입 분류 후 삽입)

### 4.3 Migration 004: Affixes (Phase 3)

**파일**: `supabase/migrations/004_affixes.sql`

**전제조건**:
- 거래소 필터 로그 파싱 구현 완료
- 실제 로그 샘플 확보

**데이터 소스**: 게임 로그 `+filters` 필드 분석 + TLIDB 크롤링

### 4.4 Migration 005: Filtered Prices (Phase 3)

**파일**: `supabase/migrations/005_filtered_prices.sql`

**실행 순서**:
1. `filtered_prices` 테이블 생성
2. JSONB GIN 인덱스 생성
3. RLS 정책 적용
4. 집계 함수 생성 (aggregate_filtered_prices)

---

## 5. 데이터 동기화 전략

### 5.1 클라이언트 ↔ Supabase 동기화 흐름

#### 앱 시작 시 (초기화)
```python
# sync/manager.py의 initialize() 확장
async def initialize_item_metadata():
    """
    앱 시작 시 아이템 메타데이터 동기화
    - 로컬 캐시가 없거나 7일 이상 경과 시 전체 다운로드
    - 그 외에는 delta sync (updated_at > last_sync)
    """
    last_sync = repo.get_setting("item_metadata_last_sync")

    if not last_sync or (now - last_sync) > timedelta(days=7):
        # 전체 동기화
        items = await client.fetch_all_items()
        repo.bulk_upsert_items(items)
    else:
        # 델타 동기화
        items = await client.fetch_items_delta(since=last_sync)
        repo.bulk_upsert_items(items)

    repo.set_setting("item_metadata_last_sync", now)
```

#### 주기적 동기화 (백그라운드)
| 항목 | 주기 | 이유 |
|------|------|------|
| 아이템 메타 | 1일 1회 | 새 시즌/패치 대응 |
| 가격 집계 | 5분 | 실시간 시세 반영 (기존) |
| 가격 히스토리 | 1-6시간 | 스파크라인용 (기존) |

### 5.2 Supabase 함수 확장

#### 아이템 메타 조회 함수
```sql
-- 클라이언트가 호출: items 전체 또는 델타 조회
CREATE OR REPLACE FUNCTION fetch_items_delta(
    p_since TIMESTAMPTZ DEFAULT NULL
)
RETURNS SETOF items
LANGUAGE sql
STABLE
AS $$
    SELECT * FROM items
    WHERE p_since IS NULL OR updated_at > p_since
    ORDER BY config_base_id;
$$;

GRANT EXECUTE ON FUNCTION fetch_items_delta TO anon, authenticated;
```

### 5.3 로컬 DB 스키마 확장

**현재 SQLite items 테이블 → 확장 필요**:
```sql
-- schema.py 수정 필요
CREATE_ITEMS = """
CREATE TABLE IF NOT EXISTS items (
    config_base_id INTEGER PRIMARY KEY,
    name_ko TEXT,                  -- 추가
    name_en TEXT,
    name_cn TEXT,
    type_ko TEXT,                  -- 추가
    type_cn TEXT,
    icon_url TEXT,
    url_tlidb TEXT,                -- 추가
    category TEXT,                 -- 추가
    subcategory TEXT,              -- 추가
    tier INTEGER,                  -- 추가
    tradeable INTEGER DEFAULT 1,   -- 추가
    stackable INTEGER DEFAULT 1,   -- 추가
    cloud_updated_at TEXT,         -- 추가 (Supabase 갱신 시각)
    cached_at TEXT DEFAULT (datetime('now'))
)
"""
```

**마이그레이션 v5 필요**:
```python
# db/schema.py
SCHEMA_VERSION = 5  # 4 → 5로 증가

# 마이그레이션 로직 (connection.py)
def migrate_v4_to_v5(db):
    # 기존 items 테이블 백업
    db.execute("ALTER TABLE items RENAME TO items_v4_backup")

    # 새 스키마로 재생성
    db.execute(CREATE_ITEMS)

    # 데이터 마이그레이션
    db.execute("""
        INSERT INTO items (config_base_id, name_en, name_cn, type_cn, icon_url)
        SELECT config_base_id, name_en, name_cn, type_cn, icon_url
        FROM items_v4_backup
    """)

    # 백업 삭제
    db.execute("DROP TABLE items_v4_backup")
```

---

## 6. 비용 및 성능 고려사항

### 6.1 Supabase 무료 티어 제한

| 리소스 | 무료 티어 | TITrack 예상 사용량 | 초과 가능성 |
|--------|-----------|---------------------|------------|
| Database | 500 MB | items (10 MB) + prices (100 MB) = **110 MB** | ✅ 안전 |
| Bandwidth | 5 GB/월 | 1,000 유저 × 5 MB/월 = **5 GB** | ⚠️ 경계 |
| Realtime | 200 concurrent | N/A (polling 사용) | ✅ 안전 |
| Storage | 1 GB | N/A (이미지 없음) | ✅ 안전 |

**대역폭 최적화 전략**:
1. **델타 동기화**: 전체 다운로드 최소화 (7일 주기)
2. **압축**: gzip 응답 압축 활성화 (Supabase 기본 제공)
3. **CDN 캐싱**: 아이템 메타는 Cache-Control: max-age=86400 (1일)

### 6.2 인덱싱 전략

#### 핵심 쿼리 패턴 분석
```sql
-- Q1: 시즌별 가격 조회 (가장 빈번)
SELECT * FROM aggregated_prices WHERE season_id = ? AND config_base_id = ?;
-- 인덱스: (config_base_id, season_id) - 이미 PK

-- Q2: 델타 동기화 (아이템 메타)
SELECT * FROM items WHERE updated_at > ?;
-- 인덱스: idx_items_updated (이미 생성)

-- Q3: 카테고리별 조회
SELECT * FROM items WHERE category = ? ORDER BY tier, name_ko;
-- 인덱스: idx_items_category (이미 생성)

-- Q4: 가격 히스토리 조회
SELECT * FROM price_history WHERE config_base_id = ? AND season_id = ? AND hour_bucket > ?;
-- 인덱스: (config_base_id, season_id, hour_bucket) - 이미 PK
```

**결론**: 현재 인덱스 설계로 충분, 추가 인덱스 불필요

### 6.3 pg_cron 작업 (기존 유지 + 1개 추가)

```sql
-- 기존 작업 (유지)
SELECT cron.schedule('aggregate-prices', '*/5 * * * *', $$SELECT aggregate_prices()$$);
SELECT cron.schedule('snapshot-price-history', '0 * * * *', $$SELECT snapshot_price_history()$$);
SELECT cron.schedule('cleanup-old-submissions', '0 3 * * *', $$SELECT cleanup_old_submissions()$$);

-- 신규 작업 (Phase 3 - 조건부 가격 집계)
SELECT cron.schedule(
    'aggregate-filtered-prices',
    '*/15 * * * *',  -- 15분마다 (가격 집계보다 덜 빈번)
    $$SELECT aggregate_filtered_prices()$$
);
```

### 6.4 RLS 성능 최적화

**현재 정책**:
- `aggregated_prices`, `price_history`: `USING (true)` - 전체 읽기 허용
- `device_registry`, `price_submissions`: RPC 함수만 접근

**추가 정책**:
- `items`, `equipment_bases`, `affixes`: `USING (true)` - 퍼블릭 읽기
- `filtered_prices`: `USING (true)` - 퍼블릭 읽기

**성능 영향**:
- ✅ 단순 읽기 정책 → 인덱스만 사용, RLS 오버헤드 최소

---

## 7. 구현 체크리스트

### Phase 1: 아이템 마스터 데이터 (우선순위: 최상)

#### 7.1 Supabase 마이그레이션
- [ ] **002_items_master.sql 작성**
  - [ ] `items` 테이블 생성
  - [ ] 인덱스 6개 생성
  - [ ] RLS 정책 적용
  - [ ] `schema_version` 테이블 생성 + 초기 레코드
- [ ] **Supabase 프로젝트에 마이그레이션 실행**
  - [ ] SQL Editor에서 실행
  - [ ] 테이블 생성 확인 (`SELECT * FROM items LIMIT 1`)

#### 7.2 데이터 로드 스크립트
- [ ] **`scripts/load_items_to_supabase.py` 작성**
  - [ ] items_ko.json 파싱 (3,300 rows)
  - [ ] ref/v/full_table.json 파싱 (2,447 rows)
  - [ ] icon_urls.py 통합 (270 rows)
  - [ ] 중복 제거 (ConfigBaseId 기준)
  - [ ] Supabase REST API로 bulk insert (배치 100개)
  - [ ] 진행률 표시 + 에러 로깅
- [ ] **스크립트 실행 및 검증**
  - [ ] `python scripts/load_items_to_supabase.py`
  - [ ] Supabase 대시보드에서 row count 확인

#### 7.3 클라이언트 동기화 로직
- [ ] **`sync/client.py` 확장**
  - [ ] `fetch_all_items()` 메서드 추가
  - [ ] `fetch_items_delta(since)` 메서드 추가
  - [ ] 페이지네이션 처리 (1000 rows/request)
- [ ] **`sync/manager.py` 확장**
  - [ ] `initialize_item_metadata()` 메서드 추가
  - [ ] 7일 주기 전체 동기화 로직
  - [ ] 델타 동기화 로직 (updated_at 기반)
  - [ ] 백그라운드 스레드에 1일 주기 추가
- [ ] **`db/repository.py` 확장**
  - [ ] `bulk_upsert_items(items)` 메서드 추가
  - [ ] items 테이블 CRUD 메서드 추가

#### 7.4 로컬 DB 마이그레이션
- [ ] **`db/schema.py` 수정**
  - [ ] SCHEMA_VERSION 4 → 5로 증가
  - [ ] `CREATE_ITEMS` DDL 확장 (9개 필드 추가)
  - [ ] 마이그레이션 함수 `migrate_v4_to_v5()` 작성
- [ ] **`db/connection.py` 수정**
  - [ ] v4→v5 마이그레이션 로직 추가
  - [ ] 기존 데이터 보존 (name_en, name_cn 등)
- [ ] **테스트**
  - [ ] 신규 DB 생성 테스트
  - [ ] 기존 DB 마이그레이션 테스트

#### 7.5 한국어 이름 통합
- [ ] **`data/korean_names.py` 수정**
  - [ ] Supabase items 테이블 우선 조회
  - [ ] 폴백: items_ko.json
  - [ ] 캐시 레이어 추가 (메모리)
- [ ] **`repository.py` 수정**
  - [ ] `get_item_name()`: Supabase items → items_ko.json → name_en → fallback
  - [ ] `get_item()`: 로컬 SQLite items 테이블 조회

#### 7.6 테스트 및 검증
- [ ] **통합 테스트 작성**
  - [ ] `tests/test_item_sync.py`
  - [ ] 전체 동기화 시나리오
  - [ ] 델타 동기화 시나리오
  - [ ] 오프라인 폴백 시나리오
- [ ] **수동 테스트**
  - [ ] 앱 시작 → items 다운로드 확인
  - [ ] 네트워크 차단 → 로컬 캐시 사용 확인
  - [ ] 7일 후 재시작 → 전체 동기화 확인

---

### Phase 2: 장비 베이스 타입 (우선순위: 높음)

#### 7.7 Supabase 마이그레이션
- [ ] **003_equipment_bases.sql 작성**
  - [ ] `equipment_bases` 테이블 생성
  - [ ] FK 제약조건 (`items` 참조)
  - [ ] 인덱스 2개 생성
  - [ ] RLS 정책 적용
- [ ] **Supabase 프로젝트에 실행**

#### 7.8 데이터 로드
- [ ] **`scripts/load_equipment_bases.py` 작성**
  - [ ] ref/v/*.json에서 장비 타입 분류
  - [ ] equipment_type, slot 매핑 로직
  - [ ] Supabase REST API로 bulk insert
- [ ] **스크립트 실행 및 검증**

#### 7.9 클라이언트 통합
- [ ] **`sync/client.py`**
  - [ ] `fetch_equipment_bases()` 추가
- [ ] **`sync/manager.py`**
  - [ ] `initialize_equipment_metadata()` 추가
- [ ] **로컬 DB 스키마**
  - [ ] `equipment_bases` 테이블 추가 (SQLite)
  - [ ] 마이그레이션 v6

---

### Phase 3: 조건부 가격 (우선순위: 낮음, BLOCKED)

**전제조건**:
- ✅ Phase 1-2 완료
- ⚠️ 거래소 필터 로그 샘플 확보 (Tasks.md BLOCKER)
- ⚠️ exchange_parser.py 확장 완료

#### 7.10 Supabase 마이그레이션
- [ ] **004_affixes.sql 작성**
- [ ] **005_filtered_prices.sql 작성**
- [ ] **집계 함수 `aggregate_filtered_prices()` 작성**
- [ ] **pg_cron 작업 추가**

#### 7.11 파서 확장
- [ ] **`parser/exchange_parser.py` 수정**
  - [ ] `+filters` 필드 파싱 로직 추가
  - [ ] FilterCondition 데이터 모델 추가
- [ ] **테스트**
  - [ ] 실제 로그 샘플로 검증

#### 7.12 클라이언트 통합
- [ ] **조건부 가격 제출 로직**
- [ ] **조건부 가격 조회 API**
- [ ] **프론트엔드 UI 개발**

---

## 8. 비용 계산 (1,000 유저 기준)

### 8.1 스토리지 예측

| 테이블 | Row 수 | Row 크기 | 총 크기 |
|--------|--------|----------|---------|
| items | 3,500 | 500 bytes | 1.8 MB |
| equipment_bases | 1,000 | 200 bytes | 0.2 MB |
| aggregated_prices | 10,000 | 80 bytes | 0.8 MB |
| price_history | 500,000 | 60 bytes | 30 MB |
| price_submissions | 100,000 | 100 bytes | 10 MB (7일) |
| device_registry | 1,000 | 100 bytes | 0.1 MB |
| **합계** | - | - | **43 MB** |

**결론**: 무료 티어 500 MB의 9% 사용 → ✅ 안전

### 8.2 대역폭 예측 (월간)

| 작업 | 빈도 | 크기 | 유저당 | 총 대역폭 |
|------|------|------|---------|-----------|
| 아이템 메타 다운 | 1회/7일 | 2 MB | 8 MB/월 | 8 GB |
| 가격 집계 다운 | 5분 | 50 KB | 15 MB/월 | 15 GB |
| 가격 제출 업로드 | 60초 | 1 KB | 1.5 MB/월 | 1.5 GB |
| **합계** | - | - | 24.5 MB/월 | **24.5 GB** |

**대역폭 초과**: 무료 티어 5 GB → **4.9배 초과** ⚠️

### 8.3 비용 절감 전략

#### 전략 1: 델타 동기화 강화 (우선)
```
아이템 메타 다운: 2 MB → 100 KB (델타만)
→ 8 GB → 0.4 GB (20배 감소)
→ 총 17 GB (여전히 초과)
```

#### 전략 2: 가격 다운로드 주기 확대
```
5분 → 10분: 15 GB → 7.5 GB
→ 총 9 GB (여전히 초과)
```

#### 전략 3: 유료 플랜 전환 (Pro: $25/월)
- 대역폭: 250 GB/월
- Database: 8 GB
- 1,000 유저까지 충분

#### 전략 4: CDN 사용 (Cloudflare Workers)
- 아이템 메타를 Cloudflare에 캐싱
- Supabase 대역폭 부담 제거
- 비용: 무료 (10만 요청/일)

**권장**: 전략 1 + 전략 4 (무료 유지 가능)

---

## 9. 롤백 계획

### 9.1 Supabase 롤백

```sql
-- Phase 3 롤백
DROP TABLE IF EXISTS filtered_prices CASCADE;
DROP TABLE IF EXISTS affixes CASCADE;

-- Phase 2 롤백
DROP TABLE IF EXISTS equipment_bases CASCADE;

-- Phase 1 롤백
DROP TABLE IF EXISTS items CASCADE;
DROP TABLE IF EXISTS schema_version CASCADE;

-- Phase 0으로 복귀 (가격 크라우드소싱만)
-- price_submissions, aggregated_prices, price_history, device_registry 유지
```

### 9.2 클라이언트 롤백

```python
# db/schema.py
SCHEMA_VERSION = 4  # 5 → 4로 되돌림

# sync/manager.py
# initialize_item_metadata() 메서드 제거

# data/korean_names.py
# Supabase 조회 로직 제거, items_ko.json으로 복귀
```

---

## 10. 타임라인

| Phase | 작업 | 예상 시간 | 담당 |
|-------|------|-----------|------|
| 준비 | Supabase 프로젝트 생성 + URL/Key 설정 | 30분 | Infra |
| Phase 1 | 아이템 마스터 구현 | 8시간 | Backend + Data |
| Phase 1 | 테스트 및 검증 | 2시간 | QA |
| Phase 2 | 장비 베이스 구현 | 4시간 | Backend + Data |
| Phase 2 | 테스트 | 1시간 | QA |
| Phase 3 | 조건부 가격 (BLOCKED) | 12시간 | Backend + Data + Frontend |
| **합계** | - | **27.5시간** | - |

**최소 구현 (Phase 1-2)**: 15시간

---

## 11. 주의사항 및 리스크

### 11.1 기술적 리스크

| 리스크 | 영향 | 완화 방안 |
|--------|------|-----------|
| Supabase 무료 티어 대역폭 초과 | 높음 | CDN + 델타 동기화 |
| 로컬 DB 마이그레이션 실패 | 중간 | 백업 + 롤백 스크립트 |
| items_ko.json과 Supabase 불일치 | 낮음 | Supabase를 SSOT로 |
| 네트워크 오프라인 시 앱 작동 | 중간 | 로컬 캐시 폴백 |

### 11.2 운영 리스크

| 리스크 | 영향 | 완화 방안 |
|--------|------|-----------|
| Supabase 서비스 장애 | 높음 | 로컬 캐시 + 재시도 로직 |
| 악의적 데이터 제출 | 중간 | Rate limiting + 디바이스 플래깅 (기존) |
| 새 시즌 아이템 업데이트 지연 | 낮음 | 수동 크롤링 + 긴급 패치 |

---

## 12. 다음 단계

### 즉시 실행 가능
1. ✅ Supabase 프로젝트 생성 (BLK-1 해소)
2. ✅ `002_items_master.sql` 작성
3. ✅ `scripts/load_items_to_supabase.py` 작성

### 대기 중 (BLOCKED)
4. ⚠️ 거래소 필터 로그 샘플 확보 (Tasks.md Phase 1)
5. ⚠️ Phase 3 설계 재검토

### 문서화
6. ✅ 이 문서를 Tasks.md에 링크
7. ✅ CLAUDE.md 업데이트 (Supabase 아키텍처 추가)

---

## 부록 A: Supabase 프로젝트 설정 가이드

### A.1 프로젝트 생성
1. https://supabase.com 로그인
2. "New Project" 클릭
3. 프로젝트 이름: `TITrack-Korean`
4. 리전: `Northeast Asia (Seoul)` (한국 유저 대상)
5. Database 비밀번호 설정

### A.2 환경 변수 설정
```bash
# .env 파일 (로컬 개발)
TITRACK_SUPABASE_URL=https://qhjulyngunwiculnharg.supabase.co
TITRACK_SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# PyInstaller 빌드 시
# sync/client.py의 DEFAULT_SUPABASE_URL/KEY 하드코딩
```

### A.3 pg_cron 활성화
1. Supabase Dashboard → Database → Extensions
2. `pg_cron` 검색 → Enable
3. 마이그레이션 001에서 cron 작업 자동 등록됨

### A.4 RLS 검증
```sql
-- anon 역할로 테스트
SET ROLE anon;
SELECT * FROM items LIMIT 1;  -- 성공해야 함
INSERT INTO items VALUES (999, 'test', 'test');  -- 실패해야 함 (읽기 전용)
```

---

## 부록 B: 참고 자료

- [Supabase Documentation](https://supabase.com/docs)
- [PostgreSQL JSONB](https://www.postgresql.org/docs/current/datatype-json.html)
- [pg_cron GitHub](https://github.com/citusdata/pg_cron)
- [TITrack Tasks.md](../docs/Tasks.md)
- [TITrack Architecture](../TITrack_Architecture.md)

---

**문서 끝**
