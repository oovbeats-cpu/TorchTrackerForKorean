# TITrack Supabase 구축 체크리스트

> **빠른 참조용 체크리스트** - 상세 내용은 [`supabase_architecture.md`](supabase_architecture.md) 참고

---

## 📌 Phase 1: 아이템 마스터 데이터 (우선순위: 최상)

**예상 시간**: 10시간 (구현 8시간 + 테스트 2시간)

### 1. Supabase 프로젝트 설정 (30분)
- [ ] Supabase 계정 생성/로그인
- [ ] 프로젝트 생성: `TITrack-Korean`
- [ ] 리전 선택: `Northeast Asia (Seoul)`
- [ ] Database 비밀번호 설정
- [ ] URL/Key 복사 → 환경 변수 설정
- [ ] pg_cron extension 활성화

### 2. Supabase 마이그레이션 실행 (15분)
- [ ] `supabase/migrations/002_items_master.sql` 파일 확인
- [ ] Supabase Dashboard → SQL Editor → 파일 붙여넣기
- [ ] 실행 → 성공 확인
- [ ] 검증 쿼리 실행:
  ```sql
  SELECT * FROM schema_version ORDER BY version;
  SELECT * FROM items LIMIT 1;  -- 빈 테이블
  SELECT indexname FROM pg_indexes WHERE tablename = 'items';
  SELECT policyname FROM pg_policies WHERE tablename = 'items';
  ```

### 3. 데이터 로드 (30분)
- [ ] 환경 변수 설정:
  ```bash
  export TITRACK_SUPABASE_URL="https://xxx.supabase.co"
  export TITRACK_SUPABASE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  ```
- [ ] 스크립트 실행:
  ```bash
  python scripts/load_items_to_supabase.py
  ```
- [ ] 결과 확인:
  - 총 ~3,500 items 업로드
  - 에러 0건
- [ ] Supabase Dashboard에서 검증:
  ```sql
  SELECT COUNT(*) FROM items;  -- ~3500
  SELECT category, COUNT(*) FROM items GROUP BY category;
  SELECT * FROM items WHERE name_ko IS NULL;  -- 0 rows
  ```

### 4. 클라이언트 동기화 로직 (3시간)
- [ ] **`src/titrack/sync/client.py` 확장**:
  ```python
  async def fetch_all_items(self) -> list[dict]: ...
  async def fetch_items_delta(self, since: datetime) -> list[dict]: ...
  ```
- [ ] **`src/titrack/sync/manager.py` 확장**:
  ```python
  async def initialize_item_metadata(self): ...
  async def _download_items_loop(self): ...  # 백그라운드 스레드
  ```
- [ ] **`src/titrack/db/repository.py` 확장**:
  ```python
  def bulk_upsert_items(self, items: list[dict]) -> int: ...
  def get_item_by_id(self, config_base_id: int) -> Optional[dict]: ...
  ```

### 5. 로컬 DB 마이그레이션 v5 (2시간)
- [ ] **`src/titrack/db/schema.py` 수정**:
  - [ ] `SCHEMA_VERSION = 5`로 증가
  - [ ] `CREATE_ITEMS` DDL 확장 (9개 필드 추가):
    - `name_ko`, `type_ko`, `url_tlidb`, `category`, `subcategory`, `tier`, `tradeable`, `stackable`, `cloud_updated_at`
- [ ] **`src/titrack/db/connection.py` 수정**:
  - [ ] `migrate_v4_to_v5()` 함수 작성 (기존 데이터 보존)
  - [ ] 마이그레이션 로직 등록
- [ ] **테스트**:
  - [ ] 신규 DB 생성 → SCHEMA_VERSION=5 확인
  - [ ] 기존 v4 DB → v5 마이그레이션 성공 확인
  - [ ] 기존 `name_en`, `name_cn` 데이터 보존 확인

### 6. 한국어 이름 통합 (1시간)
- [ ] **`src/titrack/data/korean_names.py` 수정**:
  ```python
  def get_korean_name(config_id: int) -> Optional[str]:
      # 1. 로컬 SQLite items 테이블 조회 (캐시)
      # 2. Fallback: items_ko.json
      # 3. Fallback: None
  ```
- [ ] **`src/titrack/db/repository.py` 수정**:
  - [ ] `get_item_name()`: Supabase items → items_ko.json → name_en → fallback

### 7. 통합 테스트 (2시간)
- [ ] **`tests/test_item_sync.py` 작성**:
  ```python
  def test_full_sync(): ...  # 전체 동기화
  def test_delta_sync(): ...  # 델타 동기화
  def test_offline_fallback(): ...  # 오프라인 시 로컬 캐시 사용
  def test_name_resolution(): ...  # 이름 해석 체인
  ```
- [ ] **수동 테스트**:
  - [ ] 앱 시작 → items 다운로드 로그 확인
  - [ ] 네트워크 차단 → 로컬 캐시로 작동 확인
  - [ ] 7일 후 재시작 → 전체 동기화 트리거 확인

---

## 📌 Phase 2: 장비 베이스 타입 (우선순위: 높음)

**예상 시간**: 5시간 (구현 4시간 + 테스트 1시간)

### 1. Supabase 마이그레이션 (1시간)
- [ ] **`supabase/migrations/003_equipment_bases.sql` 작성**:
  ```sql
  CREATE TABLE equipment_bases (
      config_base_id INTEGER PRIMARY KEY REFERENCES items(config_base_id),
      equipment_type TEXT NOT NULL,
      slot TEXT NOT NULL,
      ...
  );
  ```
- [ ] SQL Editor에서 실행
- [ ] 검증: `SELECT * FROM equipment_bases LIMIT 1;`

### 2. 데이터 로드 (1시간)
- [ ] **`scripts/load_equipment_bases.py` 작성**:
  - [ ] ref/v/full_table.json 파싱
  - [ ] ConfigBaseId 범위별 장비 타입 분류
  - [ ] Supabase bulk insert
- [ ] 스크립트 실행 → ~1,000 rows 업로드

### 3. 클라이언트 통합 (2시간)
- [ ] `sync/client.py`: `fetch_equipment_bases()` 추가
- [ ] `sync/manager.py`: `initialize_equipment_metadata()` 추가
- [ ] 로컬 DB 스키마 v6: `equipment_bases` 테이블 추가

### 4. 테스트 (1시간)
- [ ] 통합 테스트 작성
- [ ] 수동 테스트: 장비 메타 다운로드 확인

---

## 📌 Phase 3: 조건부 가격 (우선순위: 낮음, BLOCKED)

**전제조건**: 거래소 필터 로그 샘플 확보 필요

**예상 시간**: 14시간 (구현 12시간 + 테스트 2시간)

### 1. Supabase 마이그레이션 (2시간)
- [ ] `004_affixes.sql` 작성
- [ ] `005_filtered_prices.sql` 작성
- [ ] `aggregate_filtered_prices()` 함수 작성
- [ ] pg_cron 작업 추가 (15분 주기)

### 2. 파서 확장 (4시간)
- [ ] `parser/exchange_parser.py`: `+filters` 필드 파싱 추가
- [ ] `core/models.py`: FilterCondition 모델 추가
- [ ] 테스트 작성 (실제 로그 샘플 사용)

### 3. 클라이언트 통합 (4시간)
- [ ] 조건부 가격 제출 로직
- [ ] 조건부 가격 조회 API
- [ ] 로컬 DB 스키마 v7: `filtered_prices` 테이블

### 4. 프론트엔드 UI (2시간)
- [ ] 조건부 가격 표시 UI
- [ ] 필터 입력 폼

### 5. 테스트 (2시간)
- [ ] E2E 테스트: 거래소 검색 → 로그 파싱 → 가격 제출 → 집계 → 다운로드

---

## 🚀 즉시 실행 가능 항목

### 1. Supabase 프로젝트 생성 (지금 바로)
- [ ] https://supabase.com 로그인
- [ ] "New Project" 클릭
- [ ] 프로젝트 이름: `TITrack-Korean`
- [ ] 리전: `Northeast Asia (Seoul)`
- [ ] Database 비밀번호 설정 (안전한 곳에 저장!)

### 2. 환경 변수 설정 (프로젝트 생성 직후)
```bash
# Windows (PowerShell)
$env:TITRACK_SUPABASE_URL = "https://xxx.supabase.co"
$env:TITRACK_SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# Linux/Mac (Bash)
export TITRACK_SUPABASE_URL="https://xxx.supabase.co"
export TITRACK_SUPABASE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 3. supabase 패키지 설치 (개발 환경)
```bash
pip install titrack[cloud]
# 또는
pip install supabase
```

### 4. pg_cron 활성화 (Supabase Dashboard)
- [ ] Database → Extensions → `pg_cron` 검색 → Enable

---

## ⚠️ 블로커 해결 항목

| 블로커 | 설명 | 해결 방법 |
|--------|------|-----------|
| **BLK-1** | Supabase URL/Key 미설정 | Phase 1 Step 1에서 해결 |
| **BLOCKER** | 거래소 필터 로그 샘플 없음 | 게임 플레이 + 장비 조건부 검색 → 로그 확보 |

---

## 📊 진행률 추적

### Phase 1: 아이템 마스터 데이터
- [ ] Supabase 설정 (4/6 완료: 문서/마이그레이션/스크립트/아키텍처)
- [ ] 클라이언트 통합 (0/3 완료: client.py, manager.py, repository.py)
- [ ] 로컬 DB 마이그레이션 (0/1 완료)
- [ ] 테스트 (0/1 완료)
- **전체 진행률**: 4/11 = **36%**

### Phase 2: 장비 베이스 타입
- [ ] Supabase 마이그레이션 (0/1 완료)
- [ ] 데이터 로드 (0/1 완료)
- [ ] 클라이언트 통합 (0/1 완료)
- [ ] 테스트 (0/1 완료)
- **전체 진행률**: 0/4 = **0%**

### Phase 3: 조건부 가격
- **상태**: BLOCKED (로그 샘플 필요)
- **전체 진행률**: 0% (미착수)

---

## 📝 다음 단계 (우선순위 순)

1. ✅ **지금 바로**: Supabase 프로젝트 생성 → BLK-1 해소
2. ✅ **5분 후**: 002_items_master.sql 실행
3. ✅ **10분 후**: load_items_to_supabase.py 실행
4. 🔄 **1시간 후**: 클라이언트 동기화 로직 구현 시작
5. 🔄 **3시간 후**: 로컬 DB 마이그레이션 v5 구현
6. 🔄 **5시간 후**: 통합 테스트 작성 및 실행
7. 🔄 **8시간 후**: Phase 1 완료 → Phase 2 시작

---

**문서 끝** - 상세 내용은 [`supabase_architecture.md`](supabase_architecture.md) 참고
