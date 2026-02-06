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

---

## 미완료 작업 (Backlog)

### Priority 1 - 버그 수정
- [x] ~~`app.py:136` - `get_recent_runs(limit=10000)` → 전용 COUNT 쿼리 사용~~
- [x] ~~`delta_calculator.py:77-83` - 음수 수량 처리 시 `raw_line` 필드 보존~~
- [x] ~~현재런 duration ↔ 맵핑 타이머 동기화~~

### Priority 2 - 개선
- [ ] 테스트 커버리지 확대 (현재 8개 테스트 파일)
- [ ] 프론트엔드 API 엔드포인트 일치 여부 검증

### Priority 3 - 문서화
- [ ] API 엔드포인트 실제 코드와 CLAUDE.md 동기화 검증

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
