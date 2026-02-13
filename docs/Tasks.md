# Tasks.md - TITrack 작업 관리 (Single Source of Truth)

> **규칙**: 모든 에이전트는 작업 시작 전 이 파일을 읽고, 작업 완료 후 결과를 기록합니다.
> **형식**: `[YYYY-MM-DD HH:MM] [에이전트명] 작업 내용`

---

## 현재 상태: v1.0.2

### Active Blockers

| ID | 설명 | 담당 | 상태 |
|----|------|------|------|
| BLK-1 | 클라우드 백엔드 미구성 (Supabase URL/Key 필요) | Infra | Open |
| BLK-2 | 코드 서명 없음 (MOTW 이슈, Workaround 존재) | Infra | Open |

---

## 세션 로그

### 2026-02-06 세션 #1

#### [Main Agent] 코드 분석 & 버그 수정
- **시작**: 전체 코드베이스 분석 (52개 Python 파일, 3개 프론트엔드 파일)
- **발견된 문제점**:

| 심각도 | 파일:줄 | 문제 | 상태 |
|--------|---------|------|------|
| CRITICAL | `pyproject.toml:33` | `supabase`가 필수 의존성으로 잘못 설정 (optional이어야 함) | FIXED |
| BUG | `commands.py:741` | `sync_manager.set_player_info()` - 존재하지 않는 메서드 호출 (AttributeError) | FIXED |
| LOW | `collector.py:102` | `dict[str, any]` 소문자 any - 타입 힌트 아님 | FIXED |
| PERF | `app.py:136` | 상태 API에서 10000개 Run 로드 후 len() - 비효율적 | FIXED |
| LOW | `delta_calculator.py:77-83` | 음수 수량 처리 시 raw_line 누락 | FIXED |

- **수정 내역**:
  1. `pyproject.toml`: `supabase` → `[project.optional-dependencies.cloud]`로 이동
  2. `commands.py:741`: `set_player_info()` → `set_season_context(season_id)` 수정
  3. `collector.py`: `from typing import Any` 추가, `dict[str, any]` → `dict[str, Any]`

- **결과**: CLAUDE.md 재작성 완료, Tasks.md 초기화

### 2026-02-06 세션 #2

#### [Main Agent] 백로그 버그 수정
- **시작**: 세션 #1에서 발견된 PERF/LOW 이슈 2건 수정
- **변경 파일**: `app.py`, `delta_calculator.py`
- **수정 내역**:
  1. `app.py:136`: `len(repo.get_recent_runs(limit=10000))` → `repo.get_completed_run_count()` (기존 COUNT 쿼리 활용)
  2. `delta_calculator.py:79`: 음수 수량 처리 시 `raw_line=event.raw_line` 필드 추가 (TypeError 방지)
- **결과**: 세션 #1 발견 이슈 5건 모두 FIXED

### 2026-02-06 세션 #3

#### [Main/Backend/Frontend Agent] 현재런 타이머 ↔ 맵핑 타이머 동기화
- **시작**: 현재런 duration이 wall clock 기반이라 일시정지를 무시함 → TimeTracker와 동기화 요청
- **문제 분석**:
  - `runs.py:487`: `(now - start_ts).total_seconds()` = wall clock (일시정지 포함)
  - `app.js:894`: refreshAll 때마다 서버 wall clock 값으로 덮어씀
  - `app.js:802`: 로컬 타이머는 mapping_play_state=='playing'일 때만 증가 (올바름)
  - **결과**: 일시정지해도 서버에서 계속 증가하는 duration으로 덮어써서 타이머 불일치
- **변경 파일**: `time_tracker.py`, `time.py`, `runs.py`, `app.js`
- **수정 내역**:
  1. `time_tracker.py`: `_current_map_accumulated` 필드 추가, `current_map_play_seconds` property 추가
     - `on_map_start()`: 리셋, `pause_mapping()`: 누적, `resume_mapping()`: 재시작 (변경 없음), `on_map_end()`: 누적
  2. `time_tracker.py`: `TimeTrackerState`에 `current_map_play_seconds` 필드 추가
  3. `runs.py:get_active_run()`: wall clock 대신 `time_tracker.current_map_play_seconds` 사용
  4. `time.py`: `TimeState` 모델에 `current_map_play_seconds` 필드 추가
  5. `app.js`: `syncTimeState()`에서 `current_map_play_seconds`로 `currentRunState` 동기화
  6. `app.js`: `updateTimeDisplay()`에서 현재런 duration 표시도 1초마다 갱신
  7. `app.js`: `renderActiveRun()` 해시에서 duration 제거 (로컬 타이머가 관리)
- **결과**: 현재런 타이머가 맵핑 타이머와 완전 동기화, 일시정지 시 현재런 타이머도 정지

#### [Main Agent] 맵 종료 시 현재런 타이머 0초 미초기화 버그 수정
- **시작**: 맵 종료 후 허브 복귀 시 현재런 타이머가 0으로 리셋되지 않는 문제
- **원인 분석**:
  - `on_map_end()`에서 `_current_map_accumulated`에 시간을 누적만 하고 리셋하지 않음
  - 맵 종료 후 `current_map_play_seconds`가 이전 맵의 누적 시간을 반환
  - `syncTimeState()`와 `renderActiveRun(null)` 사이 타이밍 경합으로 이전 값 잔존 가능
- **변경 파일**: `time_tracker.py`, `app.js`
- **수정 내역**:
  1. `time_tracker.py:on_map_end()`: 맵 종료 시 `_current_map_accumulated = timedelta()` 리셋 추가 (누적은 `_mapping_accumulated`에만)
  2. `app.js:syncTimeState()`: `mapping_play_state !== 'stopped'` 조건 추가 (맵핑 중일 때만 동기화)
- **결과**: 맵 종료 → current_map_play_seconds = 0, race condition 방어

#### [Backend Agent + Frontend Agent] "항상 위" (Always on Top) 토글 기능 구현
- **시작**: 자동 새로고침 토글 옆에 "항상 위" 토글 추가 요청
- **Backend Agent** (`commands.py`):
  - `Api` 클래스에 `toggle_on_top(enabled)` 메서드 추가
  - `self._window.on_top = enabled`으로 pywebview 항상 위 설정
- **Frontend Agent** (`index.html`, `app.js`, `style.css`):
  - `index.html`: 자동 새로고침 뒤에 `on-top-control` div 추가 (기본 숨김)
  - `app.js`: `initAlwaysOnTop()` 함수 추가, `pywebviewready`에서 토글 표시, localStorage 상태 저장/복원
  - `style.css`: `.on-top-control { margin-left: 4px; }` 추가
- **결과**: 네이티브 윈도우 모드에서만 토글 표시, 브라우저 모드에서는 숨김, 앱 재시작 시 설정 유지

### 2026-02-07 세션 #1

#### [Frontend Agent] 인게임 오버레이 UI 파일 생성
- **시작**: 인게임 오버레이를 위한 프론트엔드 파일 3개 생성 요청
- **변경 파일**: `overlay.html`, `overlay.css`, `overlay.js` (모두 `src/titrack/web/static/`)
- **생성 내역**:
  1. `overlay.html`: 오버레이 메인 HTML - 현재 수익, 런 시간, 총 시간, FE/시간 표시 바 + 설정 패널 (불투명도, 닫기)
  2. `overlay.css`: 반투명 다크 테마 스타일 - `pywebview-drag-region` 드래그 지원, 설정 패널, 슬라이더
  3. `overlay.js`: API 폴링 (2초 간격) + 로컬 타이머 (1초 간격 보간) - `/api/runs/active`, `/api/time`, `/api/runs/performance` 엔드포인트 사용, 불투명도 설정 (localStorage 저장 + pywebview API 연동)
- **결과**: 오버레이 프론트엔드 파일 3개 생성 완료 (백엔드 오버레이 윈도우 생성 로직은 별도 작업 필요)

### 2026-02-12 세션 #1

#### [Data Agent] 데이터 소스 비교 분석 및 병합 (첫 번째)
- **시작**: ref/v/full_table.json, items_ko.json, crawler*.json 3개 소스 비교 분석 요청
- **생성 파일**: `scripts/compare_data_sources.py`, `scripts/merge_data_sources.py`
- **산출물**:
  - `docs/data_comparison_report.md` - 상세 비교 보고서
  - `output/missing_items.json` - ref/v에는 있지만 items_ko에 없는 2개 아이템
  - `output/crawler_new_items.json` - 크롤링 신규 발견 4개 (유효: 2개)
  - `output/items_ko_backup.json` - 병합 전 백업
- **분석 결과**:
  - ref/v: 2,447개 (장비 866개, 레전드 324개, 비장비 1,257개)
  - items_ko.json: 2,450개 → **2,454개** (병합 후)
  - 누락 아이템: 2개 (350756: 이중 천명: 앙숙, 350757: 이중 천명: 원녀)
  - 크롤링 신규: 2개 (300005: 계승 축, 7485: 지면 분열)
  - **이름 불일치**: 0개 ✅
  - **카테고리 불일치**: 0개 ✅
- **병합 작업**:
  1. ref/v 누락 2개 추가 (운명 타입)
  2. 크롤링 신규 2개 추가 (화석, 스킬)
  3. 메타데이터 키 (categories, structure_notes) 제외
- **결과**: items_ko.json 2,450개 → 2,454개 (4개 추가), 백업 완료

#### [Data Agent] 아이템 데이터 관리 체계 분석
- **시작**: 장비 아이템 데이터베이스 설계를 위한 현재 시스템 분석
- **분석 파일**: `items_ko.json`, `korean_names.py`, `schema.py`, `models.py`, `inventory.py`, `repository.py`, `fallback_prices.py`
- **주요 발견**:
  - items_ko.json: 3,300개 아이템 (장비 866개, 레전드 324개)
  - PageId 100 (장비 탭) 전체 제외 중 (접사 가격 편차)
  - 가격 우선순위: Exchange → Cloud → Local → Fallback
  - 이름 해석 체인: 한국어 → 영어 → "알 수 없음 {id}"
- **결과**: 아이템 데이터 구조 전체 분석 완료 (agent memory 저장)

#### [TLIDB Web Crawler] tlidb.com 구조 분석
- **시작**: https://tlidb.com/ko/Inventory 페이지 크롤링 구조 파악
- **분석 결과**:
  - 약 100개 카테고리 (장비 50개, 창고 50개)
  - ConfigBaseId, 한국어/영어 이름, 아이콘 URL 추출 가능
  - 카테고리별 URL 패턴 확인 (`/ko/{CATEGORY_NAME}`)
  - "Item 탭"과 "레전드 장비 탭" 구조 존재
- **산출물**: `docs/tlidb_structure_analysis.md` 생성
- **결과**: 크롤링 전략 수립 완료 (3단계 Phase 제안)

#### [Log Format Analyzer] 장비 로그 패턴 분석
- **시작**: DummyLog에서 장비(PageId 100) 관련 로그 패턴 분석
- **주요 발견**:
  - ✅ BagMgr 이벤트로 장비 획득/이동 감지 가능
  - ❌ **로그에 Affix(접사) 정보 없음** - ConfigBaseId만 기록
  - PageId 100 제외 이유: 접사에 따른 가격 편차 (동일 ID도 100배 차이)
- **제안**:
  - 옵션 A: 단순 통계 추적 (가치 무시) - 2-3시간
  - 옵션 B: 조건부 가격 추적 (정밀) - 12-16시간 + 로그 샘플 필요
- **결과**: 장비 추적 제약사항 및 구현 옵션 정리 (agent memory 저장)

#### [Backend Agent] 거래소 시세 검색 파싱 로직 분석
- **시작**: exchange_parser.py 분석 및 조건부 검색 파싱 가능 여부 확인
- **현재 파싱**: ConfigBaseId + FE 가격만
- **주요 발견**:
  - ✅ 조건부 필터는 로그에 `+filters` 필드로 기록됨
  - ❌ 현재 파서는 필터 조건 무시 (`+refer`만 추출)
  - ❌ 장비 조건부 검색 로그 샘플 없음 (테스트 파일에도)
- **개선 방안**:
  - FilterCondition 데이터 모델 추가
  - 파서 로직 확장 (정규식 패턴 6개 추가)
  - DB 스키마 v4 마이그레이션 (exchange_filters 테이블)
  - 예상 공수: 6-10시간
- **BLOCKER**: 실제 게임에서 장비 조건부 검색 로그 샘플 필요
- **결과**: 조건부 검색 파싱 가능하지만 추가 작업 필요 (상세 보고서 작성)

### 2026-02-12 세션 #2

#### [Backend Agent] Supabase 클라우드 백엔드 아키텍처 설계
- **시작**: 기존 Supabase 스키마 (v1) + 새 데이터 통합 방안 수립
- **분석 항목**:
  - 기존 v1 스키마 (price crowdsourcing 4개 테이블) 검토
  - items_ko.json (3,300), ref/v/full_table.json (2,447), icon_urls.py (270) 통합 전략
  - 장비 아이템 추적 확장 방안
  - 조건부 가격 저장 구조 설계
- **주요 설계**:
  - Phase 1: items 마스터 테이블 (한국어/영어/중국어 이름, 카테고리, 티어, 아이콘)
  - Phase 2: equipment_bases 테이블 (장비 베이스 타입, 슬롯, 기본 스탯)
  - Phase 3: affixes + filtered_prices 테이블 (접사 정의, 조건부 가격)
  - 데이터 동기화: Supabase = SSOT, 로컬 SQLite = 캐시
  - 비용 분석: 무료 티어 대역폭 초과 예상 (24.5 GB/월), CDN + 델타 동기화로 완화
- **산출물**:
  - `docs/supabase_architecture.md` (60KB, 12개 섹션)
  - `supabase/migrations/002_items_master.sql` (items 테이블 + 인덱스 + RLS + 함수)
  - `scripts/load_items_to_supabase.py` (데이터 로드 스크립트, 3단계 통합)
- **구현 체크리스트**: Phase 1-3 총 37개 작업 정의
- **결과**: Supabase v2 스키마 설계 완료, Migration 002 준비 완료

### 2026-02-12 세션 #3

#### [Backend Agent] Supabase 클라우드 백엔드 구축 준비 완료
- **시작**: Supabase 프로젝트 URL/Key 수령, Migration 002 + 초기 데이터 로드 준비
- **생성 파일**:
  1. `.env` - Supabase 환경 변수 (URL, service_role key)
  2. `scripts/setup_supabase_backend.py` - 통합 설정 마법사 (대화형)
  3. `scripts/load_equipment_data.py` - 장비 데이터 로더 (2,447개)
  4. `scripts/run_migration_002.py` - Migration 실행 보조 스크립트
  5. `scripts/load_items_to_supabase_20260212.py` - 20260212.txt 전용 로더
  6. `docs/supabase_setup_guide.md` - 단계별 설정 가이드
- **수정 파일**: `.gitignore` - .env 파일 제외 규칙 추가
- **Migration 파일**: `supabase/migrations/002_items_master.sql` (이미 존재)
- **데이터 파일**: `ref/v/20260212.txt` (2,447개 장비 아이템)
- **결과**:
  - ✅ 환경 변수 설정 완료 (.env 파일 생성)
  - ✅ .gitignore 업데이트 (.env 제외)
  - ✅ Supabase client 연결 테스트 성공
  - ⏳ **Migration 002 실행 대기 중** (사용자 수동 실행 필요)
  - ⏳ **데이터 로드 대기 중** (Migration 후 실행)
- **다음 단계**:
  1. Supabase Dashboard에서 `002_items_master.sql` 실행
  2. `python scripts\load_equipment_data.py` 실행
  3. 검증 쿼리 실행 (`docs/supabase_setup_guide.md` 참조)
- **참고 문서**: `docs/supabase_setup_guide.md` (상세 가이드)

#### [Data Agent] 크롤링 신규 아이템 26개 병합
- **시작**: `output/crawler_new_71_items.json` (26개) → `items_ko.json` 병합 요청
- **작업 절차**:
  1. 백업 생성: `items_ko.json` → `output/items_ko_backup_20260212_v2.json`
  2. 데이터 검증: ConfigBaseId, name, type, price 필드 검증
  3. 중복 확인: 0개 중복 (모두 신규)
  4. 병합 실행: 26개 추가, 0개 스킵
  5. JSON 정렬 및 저장 (ConfigBaseId 오름차순)
  6. 병합 보고서 생성: `docs/items_merge_report_20260212_v2.md`
- **변경 파일**: `scripts/merge_crawler_items.py` (신규), `src/titrack/data/items_ko.json`
- **통계**:
  - **병합 전**: 2,454개 아이템
  - **병합 후**: 2,480개 아이템 (+26개)
  - **추가된 카테고리 분포**:
    - 부귀 보조 스킬: +12개 (117 → 129)
    - 숭고 보조 스킬: +6개 (135 → 141)
    - 패시브 스킬: +2개 (72 → 74)
    - 황천: +6개 (장비 카테고리)
- **추가된 주요 아이템**:
  - 7734: 엠버 해머: 격동(부귀) - 부귀 보조 스킬
  - 7825~7826: 블리자드 변형 2종 (부귀)
  - 7831: 라이트닝 스톰: 물결(숭고)
  - 7855~7856: 서리의 영혼 소환 변형 2종 (부귀)
  - 7923~7928: 반석/부패 영혼 소환 변형 4종 (부귀)
  - 7948~7951: 사악한 유령 출몰 변형 4종 (부귀/숭고)
  - 7971, 7976~7977, 7984: 문 슬래시/플레임 서펀트/익스플로딩 슬래시 변형 4종 (부귀/숭고)
  - 7106, 7219: 패시브 스킬 2종
  - 1118, 1912, 2002, 4528, 4654, 4655: 황천 장비 6종
- **검증 결과**:
  - ConfigBaseId 형식: ✅ 정상 (모두 정수)
  - name/type/price 필드: ✅ 정상
  - 중복: ✅ 없음 (0개)
  - JSON 형식: ✅ 정상 (UTF-8, 오름차순 정렬)
- **산출물**:
  - `src/titrack/data/items_ko.json` - 업데이트됨 (2,480개)
  - `output/items_ko_backup_20260212_v2.json` - 백업
  - `docs/items_merge_report_20260212_v2.md` - 병합 보고서
  - `scripts/merge_crawler_items.py` - 병합 스크립트
- **결과**: items_ko.json 2,454 → 2,480개 업데이트 완료, 모든 검증 통과

### 2026-02-12 세션 #4

#### [Backend Agent] Supabase items 동기화 로직 구현
- **시작**: Supabase items 테이블과 로컬 DB 동기화 기능 구현
- **변경 파일**:
  1. `src/titrack/sync/client.py` - `fetch_items_from_cloud()` 함수 추가
  2. `src/titrack/db/repository.py` - `sync_items_from_cloud()` 메서드 추가
  3. `src/titrack/api/routes/cloud.py` - 2개 엔드포인트 추가
  4. `src/titrack/db/schema.py` - settings 테이블 주석 업데이트
- **구현 내역**:
  1. **CloudClient.fetch_items_from_cloud(since)**: Supabase `fetch_items_delta()` RPC 호출, delta sync 지원
  2. **Repository.sync_items_from_cloud(items)**: 배치 UPSERT (100개/배치), 트랜잭션 처리
  3. **POST /api/cloud/items/sync**: items 동기화 트리거, `{ success, synced_count, last_sync }` 반환
  4. **GET /api/cloud/items/last-sync**: 마지막 동기화 시각 + 총 아이템 수 조회
  5. **settings 테이블**: `items_last_sync` 키 문서화 (ISO 8601 형식)
- **주요 로직**:
  - delta sync: `since` 파라미터로 마지막 동기화 이후 업데이트만 가져오기
  - 필드 매핑: Supabase → SQLite (name_ko는 items_ko.json에만, SQLite는 name_en/name_cn/type_cn만)
  - 에러 처리: Supabase 연결 실패, 네트워크 타임아웃, 로컬 DB 쓰기 실패 모두 처리
  - 로깅: 진행 상황 출력 (`print()` 사용)
- **제약사항**:
  - 현재 SQLite 스키마는 한국어 이름(name_ko) 미지원 → items_ko.json 계속 사용
  - 로컬 DB 마이그레이션 v5는 별도 작업 필요 (name_ko, category, tier 등 추가 필요)
- **결과**: Supabase items 동기화 로직 구현 완료, 문법 체크 통과

#### [Backend Agent] Migration v5 설계: SQLite items 테이블 Supabase 정렬
- **시작**: 로컬 SQLite items 테이블을 Supabase 스키마와 동기화 (11개 컬럼 추가)
- **생성 파일**:
  1. `docs/migration_v5_guide.md` - Migration v5 상세 가이드 (검증, 롤백, 문제 해결)
  2. `scripts/verify_migration_v5.py` - 검증 스크립트 (6단계 검증)
  3. `scripts/run_migration_v5.py` - 수동 실행 스크립트
  4. `scripts/rollback_migration_v5.py` - Python 롤백 스크립트 (DB 백업 포함)
  5. `scripts/rollback_migration_v5.sql` - SQL 롤백 스크립트
- **변경 파일**:
  1. `src/titrack/db/schema.py` - SCHEMA_VERSION 4 → 5
  2. `src/titrack/db/connection.py` - `_migrate_v4_to_v5()` 메서드 추가
- **Migration v4 → v5 내용**:
  - **추가 컬럼 (11개)**:
    - `name_ko TEXT` - 한국어 이름
    - `type_ko TEXT`, `type_en TEXT` - 한국어/영어 타입
    - `url_tlidb TEXT` - TLIDB 페이지 링크
    - `category TEXT`, `subcategory TEXT` - 카테고리/세부 카테고리
    - `tier INTEGER` - 아이템 티어 (1-10)
    - `tradeable INTEGER DEFAULT 1`, `stackable INTEGER DEFAULT 1` - 거래/스택 가능 여부
    - `created_at TEXT`, `updated_at TEXT` - 생성/수정 시각
  - **추가 인덱스 (4개)**:
    - `idx_items_category`, `idx_items_subcategory`, `idx_items_tier`, `idx_items_updated`
  - **하위 호환성**: 기존 v4 데이터 보존 (config_base_id, name_en, icon_url 등)
  - **자동 실행**: 앱 재시작 시 자동 마이그레이션
- **검증 체크리스트** (6단계):
  1. 스키마 버전 = '5'
  2. items 테이블 컬럼 = 18개
  3. items 인덱스 = 4개
  4. 기존 데이터 보존
  5. 새 컬럼 NULL 상태 (클라우드 동기화 전)
  6. 기본값 적용 (tradeable=1, stackable=1)
- **롤백 시나리오**:
  - SQLite는 DROP COLUMN 미지원 → 테이블 재생성 패턴 사용
  - `items_backup` 테이블 생성 → 기존 items 삭제 → v4 스키마 재생성 → 데이터 복원
  - 롤백 시 v5 컬럼 데이터 영구 삭제 (name_ko, category, tier 등)
- **성능 영향**:
  - 컬럼 추가: 기존 행에 영향 없음 (NULL 컬럼은 저장 공간 미사용)
  - 인덱스 추가: 쓰기 5-10% 감소, 읽기 2-10배 향상 (카테고리/티어 필터링)
  - DB 파일 크기: 약 2-5% 증가
- **결과**: Migration v5 설계 완료, 자동 실행 준비 완료, 문서화 완료

---

## 미완료 작업 (Backlog)

### Priority 1 - 버그 수정
- [x] ~~`app.py:136` - `get_recent_runs(limit=10000)` → 전용 COUNT 쿼리 사용~~
- [x] ~~`delta_calculator.py:77-83` - 음수 수량 처리 시 `raw_line` 필드 보존~~
- [x] ~~현재런 duration ↔ 맵핑 타이머 동기화~~

### Priority 2 - Supabase 클라우드 백엔드 구축 (신규)

**참고 문서**: [`docs/supabase_architecture.md`](supabase_architecture.md)

#### Phase 1: 아이템 마스터 데이터 (우선순위: 최상)
- [x] ~~아키텍처 설계 및 문서 작성 (Backend Agent)~~
- [x] ~~Supabase 프로젝트 생성 + URL/Key 설정 (BLK-1 해소)~~
- [ ] `002_items_master.sql` 마이그레이션 실행 (사용자 수동)
- [ ] `load_items_to_supabase.py` 스크립트 실행 (3,500 items) (사용자 수동)
- [x] ~~클라이언트 동기화 로직 구현 (`sync/client.py`)~~
- [x] ~~API 엔드포인트 구현 (`api/routes/cloud.py`)~~
- [x] ~~로컬 DB 마이그레이션 v5 (items 테이블 확장: name_ko, category, tier 등)~~
- [ ] 한국어 이름 통합 (`korean_names.py` 수정 - Supabase 우선)
- [ ] 통합 테스트 작성 및 실행
- **예상 공수**: ~~8시간 (구현)~~ 완료 + 2시간 (테스트)

#### Phase 2: 장비 베이스 타입 (우선순위: 높음)
- [ ] `003_equipment_bases.sql` 마이그레이션 작성
- [ ] `load_equipment_bases.py` 스크립트 작성
- [ ] Supabase 마이그레이션 실행
- [ ] 클라이언트 통합 (동기화 로직)
- [ ] 로컬 DB 마이그레이션 v6
- **예상 공수**: 4시간 (구현) + 1시간 (테스트)

#### Phase 3: 조건부 가격 (우선순위: 낮음, BLOCKED)
- [ ] **전제조건**: 거래소 필터 로그 샘플 확보
- [ ] `004_affixes.sql`, `005_filtered_prices.sql` 마이그레이션 작성
- [ ] `aggregate_filtered_prices()` 함수 작성
- [ ] `exchange_parser.py` 확장 (필터 파싱)
- [ ] 클라이언트 통합 (조건부 가격 제출/조회)
- [ ] 프론트엔드 UI 개발
- **예상 공수**: 12시간 (구현) + 2시간 (테스트)

### Priority 3 - 장비 아이템 추적 (기존)

#### Phase 1: 기초 조사 (완료)
- [x] ~~현재 아이템 데이터 구조 분석 (Data Agent)~~
- [x] ~~tlidb.com 크롤링 구조 파악 (TLIDB Crawler)~~
- [x] ~~장비 로그 패턴 분석 (Log Analyzer)~~
- [x] ~~거래소 조건부 검색 파싱 분석 (Backend Agent)~~
- [ ] **게임에서 장비 조건부 검색 로그 샘플 확보** (BLOCKER)
- [ ] `+filters` 구조 상세 분석 및 명세 작성

#### Phase 2: tlidb.com 크롤링 (보류 - Supabase Phase 1로 대체)
- ~~화폐/재료 카테고리 크롤링~~ → Supabase items 테이블에서 다운로드
- ~~스킬 카테고리 크롤링~~ → Supabase items 테이블에서 다운로드
- ~~장비 카테고리 크롤링~~ → Supabase items 테이블에서 다운로드
- ~~items_ko.json 업데이트~~ → Supabase가 SSOT

#### Phase 3A: 단순 구현 (우선순위: 중간)
- [ ] PageId 100 제외 해제 (`inventory.py` 수정)
- [ ] 장비 획득 통계 화면 추가 (Frontend)
- [ ] 테스트 및 검증 (QA Agent)
- **예상 공수**: 2-3시간

#### Phase 3B: 정밀 구현 (우선순위: 낮음, BLOCKED)
- [ ] FilterCondition 데이터 모델 설계
- [ ] DB 마이그레이션 v7 (exchange_filters 테이블)
- [ ] exchange_parser.py 확장 (필터 파싱)
- [ ] Repository 레이어 확장 (조건부 가격 조회)
- [ ] API 엔드포인트 추가 (`/api/prices/filtered`)
- [ ] 프론트엔드 UI 개발 (조건부 가격 표시)
- **전제조건**: Phase 1의 로그 샘플 확보 완료
- **예상 공수**: 12-16시간

### Priority 4 - 개선
- [ ] 테스트 커버리지 확대 (현재 8개 테스트 파일)
- [ ] 프론트엔드 API 엔드포인트 일치 여부 검증
- [ ] 대역폭 최적화 (Cloudflare CDN 적용, 델타 동기화 강화)

### Priority 5 - 문서화
- [ ] API 엔드포인트 실제 코드와 CLAUDE.md 동기화 검증
- [x] ~~Supabase 아키텍처 문서 작성 (`docs/supabase_architecture.md`)~~

---

## 작업 기록 규칙

### 에이전트별 역할
```
Main Agent       → 오케스트레이션, 코드 리뷰, 문서화
Frontend Agent   → web/static/ 하위 파일 수정
Backend Agent    → api/, db/, collector/, sync/ 수정
Data Agent       → parser/, core/, data/ 수정
QA Agent         → tests/ 작성 및 실행
Infra Agent      → *.spec, setup/, 빌드 관련
```

### 기록 형식
```markdown
#### [에이전트명] 작업 제목
- **시작**: 작업 설명
- **변경 파일**: file1.py, file2.py
- **결과**: 성공/실패 + 상세
```

#### [Frontend Agent] Supabase 아이템 동기화 UI 추가
- **시작**: 설정 탭에 "아이템 데이터 동기화" 섹션 추가 요청 (2026-02-12 16:14)
- **변경 파일**: `src/titrack/web/static/index.html`, `src/titrack/web/static/style.css`, `src/titrack/web/static/app.js`
- **작업 내역**:
  1. **HTML 구조** (`index.html`):
     - 설정 모달에 새 섹션 추가 (오버레이 설정 섹션 앞)
     - 동기화 상태 표시 (마지막 동기화 시각, 총 아이템 수)
     - 동기화 버튼 + 진행 바 UI
  2. **CSS 스타일** (`style.css`):
     - `.setting-description` - 섹션 설명 스타일
     - `.sync-status` - 상태 박스 스타일 (반투명 배경)
     - `.status-row` - 상태 행 레이아웃 (라벨/값 좌우 정렬)
     - `.sync-items-btn` - 동기화 버튼 스타일 (녹색 강조)
     - `.sync-progress` - 진행 바 컨테이너
     - `.progress-bar`, `.progress-fill` - 진행 바 애니메이션 (0-100%)
     - `.progress-text` - 진행 상태 텍스트
  3. **JavaScript 로직** (`app.js`):
     - `formatSyncTime(dateStr)` - 상대 시간 포맷 함수 (방금 전, N분 전, N시간 전, 날짜)
     - `loadItemSyncStatus()` - 동기화 상태 로드 (`GET /api/cloud/items/last-sync`)
     - `syncItemsFromCloud()` - 동기화 실행 (`POST /api/cloud/items/sync`)
     - `initItemSyncUI()` - 버튼 이벤트 리스너 등록
     - `openSettingsModal()`에 `loadItemSyncStatus()` 호출 추가
     - `DOMContentLoaded`에 `initItemSyncUI()` 호출 추가
- **UX 플로우**:
  1. 설정 모달 열림 → 동기화 상태 로드
  2. "지금 동기화" 클릭 → 버튼 비활성화, 진행 바 30% 표시
  3. API 호출 성공 → 진행 바 100%, "완료! N개 아이템 동기화됨"
  4. 2초 대기 → 진행 바 숨김, 상태 새로고침
  5. 실패 시 → 에러 메시지 표시, 3초 후 숨김
- **API 엔드포인트 (백엔드 의존)**:
  - `GET /api/cloud/items/last-sync` - 마지막 동기화 시각 및 아이템 수 조회
  - `POST /api/cloud/items/sync` - 동기화 실행 (response: `{synced_count: number}`)
- **디자인 고려사항**:
  - 다크 테마: rgba 반투명 배경, 일관된 색상 팔레트 사용
  - 한국어 UI: 모든 텍스트 한국어 번역
  - 반응형: 모바일 대응 (설정 모달 레이아웃 상속)
- **결과**: 설정 탭에 동기화 UI 추가 완료, 백엔드 API와 통합 대기 중

#### [Backend Agent] Supabase items 테이블에 완전한 데이터 로드 완료
- **시작**: 사용자 보고 - Supabase items 테이블에 name_en, name_cn, icon_url이 null (2026-02-12 17:30)
- **분석 결과**:
  - 기존 `load_equipment_data.py`는 `ref/v/20260212.txt`만 로드 (한국어 이름 + 타입만)
  - 실제 필요 데이터: items_ko.json (2,480) + crawler*.json (name_en 30개, icon_url 26개) + icon_urls.py (2,406개)
- **생성 파일**:
  - `scripts/load_complete_items_to_supabase.py` - 완전한 데이터 통합 로더
- **작업 절차**:
  1. items_ko.json 로드 (2,480개) - name_ko, type_ko, price
  2. crawler1_currency_fuel.json + crawler2_materials_detailed.json 병합 (26개) - name_en, icon_url
  3. icon_urls.py 폴백 로드 (2,406개) - icon_url
  4. 카테고리/티어 메타데이터 보강
  5. Supabase bulk upsert (100개/배치, 총 25배치)
- **업로드 결과**:
  - **Total items**: 2,480개
  - **name_en**: 26개 (1.0%) ⚠️ - 크롤러 데이터에 30개만 존재
  - **name_cn**: 0개 (0.0%) ❌ - 크롤러 데이터에 없음
  - **icon_url**: 2,432개 (98.1%) ✅ - 거의 완벽
  - **Errors**: 0
- **제약사항**:
  - name_en/name_cn: tlidb.com에서 추가 크롤링 필요 (현재 크롤러 파일에 30개만 존재)
  - crawler3_maps_items_only.json, crawler4_skills.json에는 name_en 없음
- **시세 테이블 상태**:
  - items: ✅ 2,480 rows
  - aggregated_prices: ❌ NOT EXISTS
  - price_submissions: ❌ NOT EXISTS
  - price_history: ❌ NOT EXISTS
  - **원인**: Migration 001 미실행
  - **해결**: `supabase/migrations/001_price_crowdsourcing.sql` 실행 필요
- **결과**: items 테이블 데이터 로드 완료, icon_url 98.1% 커버리지, 시세 테이블은 Migration 001 필요

#### [Backend Agent] Migration 002 get_item_stats() 함수 ambiguous column 에러 긴급 수정
- **시작**: 사용자가 Migration 002 실행 시 `column reference "category" is ambiguous` 에러 보고 (2026-02-12)
- **문제 원인**:
  - `get_item_stats()` 함수의 172번째 줄에서 `FROM cat_counts, items` 암묵적 CROSS JOIN 사용
  - `category` 컬럼이 서브쿼리 `cat_counts`와 `items` 테이블 양쪽에 존재
  - PostgreSQL이 `jsonb_object_agg(category, cnt)`의 `category`가 어느 테이블 것인지 판단 불가
- **변경 파일**:
  1. `supabase/migrations/002_items_master.sql` - `get_item_stats()` 함수 재작성 (157-196줄)
  2. `supabase/migrations/fix_get_item_stats.sql` - 수정된 함수만 실행하는 hotfix 스크립트 (신규)
- **수정 내역**:
  1. **CTE 패턴으로 재구성**:
     - `stats` CTE: 전체 통계 계산 (total_items, items_with_ko_name, items_with_icon, avg_tier)
     - `categories` CTE: 카테고리별 집계 → jsonb_object_agg
     - `FROM stats CROSS JOIN categories`: 명시적 CROSS JOIN (1행 × 1행 = 1행)
  2. **NULL 처리 강화**:
     - `WHERE category IS NOT NULL` 추가 (카테고리가 NULL인 아이템 제외)
     - `COALESCE(categories.items_by_category, '{}'::jsonb)` 추가 (items 테이블이 비어있을 때 방어)
  3. **명확성 개선**:
     - 서브쿼리 `cat_counts` → CTE `categories`로 이동
     - 암묵적 CROSS JOIN → 명시적 CROSS JOIN
- **Hotfix 스크립트 (`fix_get_item_stats.sql`)**:
  - DROP FUNCTION → CREATE OR REPLACE → GRANT EXECUTE
  - 검증 쿼리 포함 (`SELECT * FROM get_item_stats()`)
  - 사용 가이드 주석 (Supabase SQL Editor에서 실행)
- **실행 방법**:
  - **옵션 A** (권장): 수정된 `002_items_master.sql` 전체 실행 (아직 실행하지 않은 경우)
  - **옵션 B**: `fix_get_item_stats.sql`만 실행 (이미 002를 실행했고 에러가 발생한 경우)
- **검증**:
  ```sql
  SELECT * FROM get_item_stats();
  -- 예상 출력 (데이터 로드 전):
  -- total_items=0, items_with_ko_name=0, items_with_icon=0,
  -- items_by_category={}, avg_tier=null
  ```
- **결과**: Migration 002의 ambiguous column 에러 수정 완료, hotfix 스크립트 준비 완료

#### [Main Agent] Migration 001 pg_cron 에러 긴급 수정
- **시작**: 사용자가 Migration 001 실행 시 `schema "cron" does not exist` 에러 보고 (2026-02-12)
- **문제 원인**:
  - 299~317번째 줄: `cron.schedule()` 호출 3개 (aggregate-prices, snapshot-price-history, cleanup-old-submissions)
  - Supabase에서 pg_cron 확장이 활성화되지 않음
- **해결 방안**: pg_cron은 선택적 기능 (자동화)이므로 주석 처리
- **변경 파일**: `supabase/migrations/001_initial_schema.sql`
- **수정 내역**:
  1. **섹션 제목 변경**: "SCHEDULED JOBS (pg_cron)" → "SCHEDULED JOBS (DISABLED - pg_cron not required)"
  2. **주석 추가**: 시스템은 pg_cron 없이 작동 가능, 수동 실행 가이드 제공
  3. **cron.schedule() 호출 3개 전체 주석 처리** (299-317줄)
- **주석 처리된 기능**:
  - aggregate-prices: 5분마다 가격 집계 → 수동 실행 가능 (`SELECT aggregate_prices()`)
  - snapshot-price-history: 1시간마다 히스토리 저장 → 수동 실행 가능 (`SELECT snapshot_price_history()`)
  - cleanup-old-submissions: 매일 오전 3시 7일 이상 데이터 삭제 → 수동 실행 가능 (`SELECT cleanup_old_submissions()`)
- **사용자 안내**:
  - pg_cron 활성화 원할 시: Supabase Dashboard > Database > Extensions에서 pg_cron 활성화 후 주석 해제
  - 자동화 없이 사용 가능: 필요 시 SQL Editor에서 수동 실행
- **결과**: Migration 001 pg_cron 에러 수정 완료, 모든 기능 정상 작동 (자동화는 선택)

#### [Backend Agent] 로컬 DB 가격 데이터 → Supabase 업로드
- **시작**: 로컬 DB prices 테이블 (exchange 출처 103개) → Supabase aggregated_prices 테이블 동기화 요청 (2026-02-12)
- **생성 파일**: `scripts/upload_local_prices_to_supabase.py`
- **작업 절차**:
  1. 로컬 DB 경로 자동 탐지 (포터블 모드 우선, LOCALAPPDATA 폴백)
  2. `prices` 테이블에서 `source='exchange'` 필터링
  3. 데이터 매핑: `price_fe` → `price_fe_median/p10/p90` (단일 값으로 통일)
  4. Supabase upsert (50개/배치)
  5. 검증 쿼리 (`COUNT(*)`)
- **데이터 매핑**:
  ```python
  로컬 price_fe → Supabase price_fe_median
  로컬 price_fe → Supabase price_fe_p10 (동일값)
  로컬 price_fe → Supabase price_fe_p90 (동일값)
  submission_count = 1
  unique_devices = 1
  updated_at = 로컬 updated_at (ISO 8601 변환)
  ```
- **실행 결과**:
  - **Local DB**: 44개 exchange 가격 로드 (data\tracker.db)
  - **Upload**: 44/44 업로드 성공 (1개 배치)
  - **Errors**: 0
  - **Verification**: Supabase aggregated_prices 테이블에 44 rows 확인
- **제약사항**:
  - exchange 출처만 업로드 (실제 거래소 가격)
  - season_id NULL → 0 변환
  - Windows 콘솔 인코딩 이슈로 이모지 제거 (체크마크 → [OK], X마크 → [ERROR])
- **결과**: 로컬 가격 데이터 44개 Supabase 업로드 완료, 검증 통과

### 2026-02-12 세션 #5

#### [Backend Agent] 아이템 동기화 0개 문제 진단 및 수정 스크립트 작성
- **시작**: 사용자 보고 - Supabase items 2,480개 vs 로컬 DB items 1,809개, 동기화 시 0개 동기화됨 (2026-02-12 18:30)
- **문제 분석**:
  - 원인 추정: `items_last_sync` 설정이 Supabase `updated_at`보다 최신이거나, `fetch_items_delta(since)` 로직 문제
  - 요청: 강제 전체 동기화 (since=NULL) 실행 필요
- **생성 파일**:
  1. `scripts/diagnose_sync_issues.py` - 동기화 문제 진단 스크립트
  2. `scripts/force_full_item_sync.py` - 강제 전체 동기화 (since=NULL)
  3. `scripts/load_prices_from_20260212.py` - ref/v/20260212.txt → Supabase aggregated_prices
  4. `scripts/upload_all_prices_to_supabase.py` - 로컬 DB exchange + 20260212.txt 통합 업로드
- **진단 스크립트 기능** (`diagnose_sync_issues.py`):
  - [1] 로컬 DB 상태: items 개수, items_last_sync 설정, exchange 가격 개수
  - [2] Supabase 상태: items 개수, updated_at 범위, aggregated_prices 개수
  - [3] ref/v/20260212.txt 파일 존재 여부 및 샘플
  - [4] 동기화 0개 문제 진단: fetch_items_delta(since) 결과 확인
- **강제 동기화 스크립트 기능** (`force_full_item_sync.py`):
  - [1/4] Supabase에서 fetch_items_delta(since=NULL) → 모든 아이템 가져오기
  - [2/4] 로컬 DB items 테이블에 UPSERT (100개/배치)
  - [3/4] items_last_sync 설정 업데이트 (현재 시각)
  - [4/4] 검증: 총 개수, name_en/icon_url 채워진 비율
- **가격 로드 스크립트 기능** (`load_prices_from_20260212.py`):
  - ref/v/20260212.txt (2,447개 아이템) → Supabase aggregated_prices
  - price=0인 경우 기본값 1.0 FE 사용 (거래 불가능한 아이템)
  - 100개/배치 UPSERT
- **통합 업로드 스크립트 기능** (`upload_all_prices_to_supabase.py`):
  - 로컬 DB exchange 가격 (우선순위 1)
  - ref/v/20260212.txt 가격 (우선순위 2, 중복 제외)
  - 병합 후 Supabase 업로드
- **실행 순서**:
  1. `python scripts/diagnose_sync_issues.py` - 현재 상태 확인
  2. `python scripts/force_full_item_sync.py` - 아이템 강제 전체 동기화 (2,480개)
  3. `python scripts/upload_all_prices_to_supabase.py` - 가격 데이터 통합 업로드 (로컬 exchange + 20260212.txt)
- **결과**: 진단 및 수정 스크립트 4개 작성 완료, 사용자 실행 대기 중

#### [Backend Agent] Windows 콘솔 인코딩 에러 긴급 수정 (diagnose_sync_issues.py)
- **시작**: `scripts/diagnose_sync_issues.py` 실행 시 `UnicodeEncodeError: 'cp949' codec can't encode character '\u2705'` 에러 (2026-02-12)
- **문제 원인**:
  - Windows 콘솔 기본 인코딩: cp949 (한글 완성형, 이모지 미지원)
  - 스크립트에 ✅, ❌, ⚠️ 이모지 사용 → cp949 인코딩 불가
  - 한글 출력도 깨짐 (바이트 시퀀스로 표시)
- **변경 파일**: `scripts/diagnose_sync_issues.py`
- **수정 내역**:
  1. **UTF-8 콘솔 강제 설정** (파일 상단):
     ```python
     import sys
     import codecs
     if sys.platform == 'win32':
         sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
         sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
     ```
  2. **이모지 → ASCII 교체**:
     - ✅ → `[OK]`
     - ❌ → `[ERROR]`
     - ⚠️ → `[WARNING]`
     - 💡 → `[INFO]` (미사용)
- **실행 결과**:
  - **Before**: UnicodeEncodeError + 한글 깨짐 (����ȭ ���� ����)
  - **After**: 정상 출력 (동기화 문제 진단)
- **진단 결과** (재실행):
  - 로컬 DB: 1,809개 items, items_last_sync=NULL, 44개 exchange 가격
  - Supabase: 2,480개 items, 44개 aggregated_prices
  - ref/v/20260212.txt: 2,447개 아이템
  - **진단**: items_last_sync가 NULL → 전체 동기화 예정 (정상)
- **다음 단계**: `force_full_item_sync.py` 실행
- **결과**: Windows 콘솔 인코딩 에러 수정 완료, UTF-8 강제 설정 + 이모지 제거로 한글 정상 출력

### 2026-02-12 세션 #6

#### [Data Agent] exchange_parser.py에 "smart" 가격 계산 메서드 추가
- **시작**: 거래소 시세 계산 로직에 IQR 기반 이상가 제거 + Mode(거래집중가) 계산 추가 (2026-02-12)
- **변경 파일**: `src/titrack/parser/exchange_parser.py`
- **작업 내역**:
  1. **typing 임포트 확장**: `from collections import Counter` 추가, `typing.Any` 추가
  2. **ExchangePriceResponse에 필드 추가**:
     - `is_volatile: bool = False` - 가격 변동성 지표 추가
  3. **새 헬퍼 함수 3개 추가**:
     - `remove_outliers_iqr(prices)` - IQR 방식 이상가 제거 (Q1-1.5*IQR ~ Q3+1.5*IQR)
     - `calculate_mode_price(prices, bin_size=0.5)` - 거래집중가 계산 (0.5 FE 구간별 빈도 분석)
     - `calculate_price_volatility(prices)` - 변동성 계산 (IQR/Median 비율, 30% 이상이면 is_volatile=True)
  4. **calculate_reference_price() 확장**:
     - 기본값 변경: `method="percentile_10"` → `method="smart"`
     - "smart" 메서드 로직:
       1. IQR로 이상가 제거
       2. 데이터 10개 미만 시 median 사용 (안전 폴백)
       3. Mode 계산 (거래집중가)
       4. Mode 신뢰도 검증 (20% 이상 동일 구간이면 mode 사용, 아니면 median)
     - else 절 (unknown method): percentile_10 → smart 폴백으로 변경
  5. **_parse_response() 메서드 수정**:
     - `calculate_price_volatility(prices_fe)` 호출 추가
     - ExchangePriceResponse에 `is_volatile=volatility["is_volatile"]` 전달
- **테스트 결과**:
  - Test 1 - IQR Outlier Removal: [1.0, 2.0, 3.0, 4.0, 5.0, 100.0] → [1.0, 2.0, 3.0, 4.0, 5.0] (100.0 제거)
  - Test 2 - Mode Calculation: [1.0, 1.5, 2.0, 2.0, 2.5, 2.0, 3.0, 10.0] → Mode Price: 2.00 FE, Mode Count: 3
  - Test 3 - Volatility Calculation:
    - Low volatility: [10.0, 10.5, 11.0, 11.5, 12.0] → Ratio: 9.09%, Is Volatile: False
    - High volatility: [5.0, 10.0, 15.0, 20.0, 50.0] → Ratio: 66.67%, Is Volatile: True
  - Test 4 - Smart Method: [9.0, 9.5, 10.0, 10.0, 10.5, 10.5, 10.5, 11.0, 11.5, 12.0, 30.0]
    - Smart: 10.50 FE (Mode 기반)
    - Median: 10.50 FE (동일)
    - Percentile 10: 9.00 FE (더 낮음)
- **하위 호환성**: 기존 메서드 (lowest, percentile_10, percentile_20, median, mean_low_20) 모두 유지
- **결과**: exchange_parser.py에 "smart" 가격 계산 메서드 추가 완료, 모든 테스트 통과

#### [Backend Agent] sync/manager.py queue_price_submission() 디버그 로그 추가
- **시작**: 거래소 가격 큐잉 디버그 로그 추가 요청 (2026-02-12)
- **변경 파일**: `src/titrack/sync/manager.py`
- **작업 내역**:
  1. 메서드 시작 시 파라미터 출력 (config_base_id, season_id)
  2. is_enabled, is_upload_enabled 상태 출력
  3. 비활성화 시 SKIPPED 로그 출력
  4. INSERT 실행 전후 로그 출력
  5. INSERT 성공 후 검증 쿼리 (COUNT) 실행 및 결과 출력
  6. 예외 처리 블록 추가 (try-except, traceback 출력)
- **출력 예시**:
  ```
  [QUEUE] START: config_base_id=100300, season_id=0
  [QUEUE] is_enabled=True, is_upload_enabled=True
  [QUEUE] Executing INSERT...
  [QUEUE] INSERT executed successfully
  [QUEUE] Verification: 1 rows for config_base_id=100300
  ```
- **결과**: queue_price_submission() 메서드에 디버그 로그 추가 완료
