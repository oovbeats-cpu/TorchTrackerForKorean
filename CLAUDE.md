# CLAUDE.md - TITrack 프로젝트 운영 지침서 v3.0.0

> **Last Updated**: 2026-02-06
> **Version**: 1.0.2 (Korean Fork)

---

## 0. 작업 관리 규칙 (필수)

### 서브에이전트 위임 원칙 (MANDATORY)
- **모든 코드 작업은 반드시 서브에이전트에게 위임합니다** (Main Agent가 직접 코드를 수정하지 않음)
- Main Agent는 오케스트레이터/PM 역할만 수행합니다:
  1. 사용자 요청을 분석하고 작업을 분배
  2. 적절한 서브에이전트를 선택하여 Task 도구로 위임
  3. 서브에이전트 결과를 사용자에게 보고
- **작업 완료 후 반드시 사용자에게 보고합니다**:
  - 어떤 에이전트가 작업했는지
  - 무엇을 변경했는지
  - 결과가 어떤지

### 에이전트 선택 기준
| 작업 유형 | 에이전트 | scope |
|-----------|----------|-------|
| 프론트엔드 (HTML/CSS/JS) | Frontend Agent (`general-purpose`) | `web/static/` |
| 백엔드 (API/DB/수집기) | Backend Agent (`general-purpose`) | `api/`, `db/`, `collector/`, `sync/`, `config/` |
| 데이터/파서 (로그/모델) | Data Agent (`general-purpose`) | `parser/`, `core/`, `data/` |
| 테스트/품질 | QA Agent (`general-purpose`) | `tests/` |
| 빌드/릴리스 | Infra Agent (`Bash`) | `*.spec`, `setup/`, `pyproject.toml` |
| 코드 탐색/조사 | Explore Agent (`Explore`) | 전체 |
| 여러 영역에 걸친 작업 | 해당 에이전트들을 **병렬**로 실행 | - |

### Tasks.md (Single Source of Truth)
- **위치**: [`docs/Tasks.md`](docs/Tasks.md)
- **모든 에이전트는 작업 시작 전 반드시 Tasks.md를 읽어야 합니다**
- 작업 완료 후 결과를 Tasks.md에 기록합니다
- 형식: `[YYYY-MM-DD HH:MM] [에이전트명] 작업 내용`

### 에이전트별 역할
```
Main Agent       → 오케스트레이션(PM), 사용자 보고, CLAUDE.md/Tasks.md 관리
Frontend Agent   → src/titrack/web/static/ (HTML, CSS, JS)
Backend Agent    → src/titrack/api/, db/, collector/, sync/
Data Agent       → src/titrack/parser/, core/, data/
QA Agent         → tests/ 작성 및 실행
Infra Agent      → *.spec, setup/, pyproject.toml, 빌드 관련
```

### 세션 작업 흐름
1. Tasks.md에서 현재 상태와 미완료 작업 확인
2. 사용자 요청 분석 → 담당 에이전트 결정
3. 서브에이전트에게 Task 도구로 위임 (가능하면 병렬)
4. 결과를 사용자에게 보고 (에이전트명 + 변경 내용 + 결과)
5. Tasks.md에 작업 기록, 새 이슈는 Backlog에 추가

---

## 1. 프로젝트 개요

**TITrack**은 Torchlight Infinite 게임 로그를 파싱하여 전리품을 추적하는 Windows 데스크톱 앱입니다.
WealthyExile (Path of Exile) 스타일의 대시보드를 제공합니다.

**핵심 제약사항**:
- 완전 로컬 (클라우드 불필요)
- 포터블 EXE 배포 (Python/Node 설치 불필요)
- 프라이버시 중심 (모든 데이터 로컬 저장)
- 치팅/후킹/메모리 읽기 없음 - 로그 파일만 파싱

**한국어 포크 특성**:
- 전체 UI 한국어 번역
- 한국어 아이템 이름 (`items_ko.json`)
- 폴백: 한국어 → 영어 → `"알 수 없음 {id}"`
- 기본 설정: 거래세/맵비용 활성화

---

## 2. 기술 스택

| 기술 | 버전 | 용도 |
|------|------|------|
| Python | 3.11+ | 언어 |
| FastAPI | >=0.109.0 | REST API |
| Uvicorn | >=0.27.0 | ASGI 서버 |
| SQLite | (내장) | 데이터베이스 (WAL 모드) |
| pywebview | >=5.0.0 | 네이티브 윈도우 |
| Vanilla JS | - | 프론트엔드 (프레임워크 없음) |
| PyInstaller | >=6.0.0 | 패키징 |
| supabase | >=2.0.0 | 클라우드 동기화 (선택적: `pip install titrack[cloud]`) |

**플랫폼**: Windows 10/11

---

## 3. 프로젝트 구조

```
src/titrack/
├── __main__.py          # 엔트리포인트 (python -m titrack)
├── version.py           # 버전 관리 (__version__)
├── api/
│   ├── app.py           # FastAPI 앱 팩토리
│   ├── schemas.py       # Pydantic 응답 모델
│   └── routes/
│       ├── runs.py      # /api/runs/*
│       ├── inventory.py # /api/inventory
│       ├── items.py     # /api/items/*
│       ├── prices.py    # /api/prices/*
│       ├── stats.py     # /api/stats/*
│       ├── icons.py     # /api/icons/*
│       ├── settings.py  # /api/settings/*
│       ├── cloud.py     # /api/cloud/*
│       ├── time.py      # /api/time/*
│       └── update.py    # /api/update/*
├── cli/
│   └── commands.py      # CLI 명령어 (init, serve, tail 등)
├── collector/
│   └── collector.py     # 메인 수집 루프 (로그 감시 + 이벤트 처리)
├── config/
│   ├── logging.py       # 로깅 설정
│   ├── paths.py         # 경로 해석 (frozen/source 모드)
│   ├── preferences.py   # 사용자 설정 (JSON 파일)
│   └── settings.py      # 앱 설정 + 로그 파일 자동 탐지
├── core/
│   ├── models.py        # 도메인 모델 (Run, ItemDelta, SlotState 등)
│   ├── delta_calculator.py  # 슬롯 상태 기반 델타 계산
│   ├── run_segmenter.py     # 맵 런 경계 추적
│   └── time_tracker.py      # 플레이 시간 추적
├── data/
│   ├── fallback_prices.py   # 폴백 가격 데이터
│   ├── icon_urls.py         # 아이콘 URL 매핑
│   ├── inventory.py         # 인벤토리 탭 필터링 (EXCLUDED_PAGES)
│   ├── korean_names.py      # 한국어 아이템 이름 로더
│   └── zones.py             # 존 이름 번역 + 존 분류
├── db/
│   ├── connection.py    # SQLite 연결 관리 (WAL, 스레드 안전)
│   ├── repository.py    # CRUD 오퍼레이션 (모든 엔티티)
│   └── schema.py        # DDL 스키마 + 마이그레이션
├── parser/
│   ├── exchange_parser.py   # 거래소 가격 메시지 파서
│   ├── log_parser.py        # 로그 라인 → 타입 이벤트 변환
│   ├── log_tailer.py        # 로그 파일 증분 읽기
│   ├── patterns.py          # 정규식 패턴 (컴파일됨)
│   └── player_parser.py     # 플레이어 정보 파싱
├── sync/
│   ├── client.py        # Supabase 클라이언트 래퍼
│   ├── device.py        # 익명 디바이스 ID
│   └── manager.py       # 클라우드 동기화 오케스트레이터
├── updater/
│   ├── github_client.py # GitHub 릴리스 API
│   ├── installer.py     # 자동 업데이트 설치
│   └── manager.py       # 업데이트 관리자
└── web/
    └── static/
        ├── index.html   # 메인 대시보드 (한국어)
        ├── app.js       # 프론트엔드 로직
        └── style.css    # 스타일
```

---

## 4. 핵심 데이터 개념

| 개념 | 설명 |
|------|------|
| **FE** | Flame Elementium, 기본 통화 (ConfigBaseId = `100300`) |
| **ConfigBaseId** | 아이템 타입 식별자 (정수) |
| **Delta** | `현재 Num - 이전 Num` (슬롯별 변화량) |
| **SlotState** | `(PlayerID, PageId, SlotId)` → `(ConfigBaseId, Num)` |
| **Run** | 맵 진입 → 퇴장 구간 (is_hub=False인 것만 추적) |
| **EventContext** | PICK_ITEMS / MAP_OPEN / OTHER |

---

## 5. 빌드 & 개발 명령어

```bash
# 개발 서버
python -m titrack serve                # 네이티브 윈도우
python -m titrack serve --no-window    # 브라우저 모드 (디버깅)

# 테스트
pytest tests/                          # 전체 테스트
pytest tests/ -v                       # 상세 출력

# 린팅
black .
ruff check .

# PyInstaller 빌드
python -m PyInstaller ti_tracker.spec --noconfirm

# Setup.exe 빌드 (C# 포터블 추출기)
dotnet publish setup/TITrackSetup.csproj -c Release -r win-x64 --self-contained false -p:PublishSingleFile=true -o setup/publish
```

---

## 6. 릴리스 프로세스

1. **버전 업데이트** (두 파일 동기화 필수):
   - `pyproject.toml` → `version = "x.x.x"`
   - `src/titrack/version.py` → `__version__ = "x.x.x"`

2. **빌드**: `python -m PyInstaller ti_tracker.spec --noconfirm`

3. **ZIP 생성**: `Compress-Archive -Path dist\TITrack -DestinationPath dist\TITrack-x.x.x-windows.zip -Force`

4. **Setup.exe**: `dotnet publish setup/TITrackSetup.csproj -c Release -r win-x64 --self-contained false -p:PublishSingleFile=true -o setup/publish`

5. **커밋 & 태그**: `git add -A && git commit -m "Release vx.x.x" && git tag vx.x.x && git push origin master && git push origin vx.x.x`

6. **GitHub 릴리스**: `gh release create vx.x.x setup/publish/TITrack-Setup.exe dist/TITrack-x.x.x-windows.zip --title "vx.x.x" --notes "..."`

---

## 7. 데이터베이스 스키마

**버전**: 3 (Cloud Sync 지원)

| 테이블 | PK | 설명 |
|--------|-----|------|
| `settings` | key | 키/값 설정 |
| `runs` | id (AUTO) | 맵 런 인스턴스 |
| `item_deltas` | id (AUTO) | 아이템 변화량 (run_id FK) |
| `slot_state` | (player_id, page_id, slot_id) | 현재 인벤토리 |
| `items` | config_base_id | 아이템 메타데이터 |
| `prices` | (config_base_id, season_id) | 가격 정보 |
| `log_position` | id=1 | 로그 읽기 위치 |
| `cloud_sync_queue` | id (AUTO) | 업로드 대기열 |
| `cloud_price_cache` | (config_base_id, season_id) | 클라우드 가격 캐시 |
| `cloud_price_history` | (config_base_id, season_id, hour_bucket) | 가격 히스토리 |

---

## 8. API 엔드포인트

### Runs
- `GET /api/runs` - 최근 런 목록
- `GET /api/runs/active` - 현재 활성 런 + 실시간 드롭
- `GET /api/runs/stats` - 통계 요약
- `GET /api/runs/report` - 누적 전리품 통계
- `GET /api/runs/report/csv` - CSV 내보내기
- `GET /api/runs/{run_id}` - 런 상세
- `POST /api/runs/reset` - 데이터 초기화

### Items / Prices
- `GET /api/items`, `GET /api/items/{id}`, `PATCH /api/items/{id}`
- `GET /api/prices`, `GET /api/prices/{id}`, `PUT /api/prices/{id}`
- `GET /api/prices/export`, `POST /api/prices/migrate-legacy`

### Stats / Player / Other
- `GET /api/stats/history`, `GET /api/stats/zones`
- `GET /api/icons/{id}` - CDN 프록시
- `GET /api/player` - 현재 캐릭터
- `GET /api/inventory` - 인벤토리
- `GET /api/status` - 서버 상태
- `GET /api/cloud/status`, `POST /api/cloud/toggle`, `POST /api/cloud/sync`
- `GET /api/cloud/prices`, `GET /api/cloud/prices/{id}/history`
- `GET /api/time/*`, `POST /api/time/*` - 시간 추적
- `GET /api/update/*` - 자동 업데이트

---

## 9. 로그 파싱 패턴

### 로그 파일 위치 (자동 탐지)
- Steam: `<SteamLibrary>/steamapps/common/Torchlight Infinite/UE_Game/Torchlight/Saved/Logs/UE_game.log`
- 독립 클라이언트: `<InstallDir>/Game/UE_game/Torchlight/Saved/Logs/UE_game.log`

### 핵심 파싱 패턴 (`patterns.py`)
```
BAG_MODIFY_PATTERN  → BagMgr@:Modfy BagItem (아이템 변경)
BAG_INIT_PATTERN    → BagMgr@:InitBagData (인벤토리 스냅샷)
ITEM_CHANGE_PATTERN → ItemChange@ ProtoName=... start/end (컨텍스트)
LEVEL_EVENT_PATTERN → SceneLevelMgr@ OpenMainWorld (존 전환)
LEVEL_ID_PATTERN    → LevelMgr@ LevelUid, LevelType, LevelId (존 분류)
CUR_RUN_VIEW_PATTERN → CurRunView = (UI 뷰 변경 / 자동 일시정지)
```

### 파싱 규칙
- PickItems 블록 내 BagMgr 이벤트 = 아이템 획득
- InitBagData = 인벤토리 동기화 (델타 없음, 슬롯 상태만 갱신)
- Spv3Open = 맵 비용 (나침반/비콘 소모)
- PageId 100 (장비 탭) = 추적 제외

---

## 10. 한국어 로컬라이제이션

### 번역 파일
| 파일 | 용도 |
|------|------|
| `src/titrack/data/items_ko.json` | ConfigBaseId → 한국어 이름 |
| `src/titrack/data/korean_names.py` | 번역 로더 |

### items_ko.json 형식
```json
{
  "100300": { "name": "화염 원소", "type": "화폐", "price": 0 }
}
```

### 이름 해석 체인 (`repository.py:444`)
1. `get_korean_name(config_base_id)` → 한국어
2. `get_item().name_en` → 영어
3. `f"알 수 없음 {config_base_id}"` → 폴백

---

## 11. 주요 기능 상세

### 거래세 (Trade Tax)
- 12.5% (1 FE / 8 FE), 비-FE 아이템에만 적용
- `get_trade_tax_multiplier()` → 0.875 또는 1.0

### 맵 비용 (Map Costs)
- `Spv3Open` 이벤트로 감지, 다음 런에 연결
- 런 순가치 = 총 전리품 - 맵 비용

### 가격 우선순위 (`get_effective_price()`)
1. Exchange 가격 (최신일 경우)
2. Cloud 가격 (커뮤니티 중앙값)
3. 로컬 가격
4. 폴백 가격 (`fallback_prices.py`)

### 시간 추적 (TimeTracker)
- 총 플레이 시간 (수동 시작/정지)
- 맵핑 시간 (자동, 맵 진입/퇴장)
- UI 뷰 기반 자동 일시정지 (인벤토리, 거래소 등)
- 수술(Surgery) 통계 추적

### 멀티 캐릭터 지원
- Effective Player ID: `player_id` 또는 `{season_id}_{name}`
- 인벤토리/런/가격이 캐릭터별 격리
- 라이브 로그에서 캐릭터 전환 자동 감지

---

## 12. 알려진 제한사항 / Blockers

| ID | 설명 | Workaround |
|----|------|-----------|
| BLK-1 | Supabase 백엔드 미구성 | 로컬 전용 모드 사용 |
| BLK-2 | 코드 서명 없음 (MOTW) | TITrack-Setup.exe 또는 Unblock-File |
| LIMIT-1 | Timemark 레벨 미추적 | 같은 존은 통합 표시 |

---

## 13. 저장 경로

| 모드 | DB 경로 | 로그 경로 |
|------|---------|-----------|
| 기본 | `%LOCALAPPDATA%\TITrack\tracker.db` | `%LOCALAPPDATA%\TITracker\titrack.log` |
| 포터블 | `.\data\tracker.db` | `.\data\titrack.log` |

---

## 14. 참고 문서

| 파일 | 용도 |
|------|------|
| [`docs/Tasks.md`](docs/Tasks.md) | 작업 관리 (작업 전 필수 확인) |
| [`TI_Local_Loot_Tracker_PRD.md`](TI_Local_Loot_Tracker_PRD.md) | 요구사항 문서 |
| [`TITrack_Architecture.md`](TITrack_Architecture.md) | 시스템 아키텍처 |
| [`.claude/agents/backend-agent.md`](.claude/agents/backend-agent.md) | 백엔드 에이전트 설정 |

---

Output Rules:

Always respond in Korean.

Translate all technical explanations into Korean, but keep variable names/code in English.
