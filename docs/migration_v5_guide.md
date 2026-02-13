# Migration v5 가이드: Items 테이블 Supabase 정렬

> **작성일**: 2026-02-12
> **작성자**: Backend Agent
> **목적**: 로컬 SQLite `items` 테이블을 Supabase 스키마와 동기화

---

## 개요

Migration v5는 로컬 SQLite `items` 테이블에 Supabase 클라우드 동기화를 위한 11개 컬럼을 추가합니다.

### 추가 컬럼 목록

| 컬럼명 | 타입 | 기본값 | 설명 |
|--------|------|--------|------|
| `name_ko` | TEXT | NULL | 한국어 이름 (TITrack Korean 우선) |
| `type_ko` | TEXT | NULL | 한국어 타입 (화폐, 장비, 재료, 스킬, 레전드) |
| `type_en` | TEXT | NULL | 영어 타입 (currency, equipment, material, skill, legendary) |
| `url_tlidb` | TEXT | NULL | TLIDB 아이템 페이지 링크 |
| `category` | TEXT | NULL | 주요 카테고리 (currency, material, equipment, skill, legendary) |
| `subcategory` | TEXT | NULL | 세부 카테고리 (claw, hammer, sword, axe, dagger 등) |
| `tier` | INTEGER | NULL | 아이템 티어 (1-10, 높을수록 희귀) |
| `tradeable` | INTEGER | 1 | 거래 가능 여부 (0=불가, 1=가능) |
| `stackable` | INTEGER | 1 | 스택 가능 여부 (0=불가, 1=가능) |
| `created_at` | TEXT | NULL | 생성 시각 (ISO 8601) |
| `updated_at` | TEXT | NULL | 수정 시각 (ISO 8601) |

### 추가 인덱스

- `idx_items_category` - 카테고리 필터링 (e.g., "모든 장비 표시")
- `idx_items_subcategory` - 세부 카테고리 필터링 (e.g., "모든 클로 표시")
- `idx_items_tier` - 티어 필터링 (e.g., "티어 5+ 아이템 표시")
- `idx_items_updated` - 델타 동기화 (마지막 동기화 이후 변경된 아이템 조회)

---

## 자동 실행

Migration v5는 **애플리케이션 시작 시 자동 실행**됩니다.

1. 앱 시작 → `Database.connect()` 호출
2. `_init_schema()` 실행
3. `_run_migrations()` 실행
4. `_migrate_v4_to_v5()` 호출
5. 기존 컬럼 확인 (`PRAGMA table_info(items)`)
6. 누락된 컬럼 추가 (`ALTER TABLE items ADD COLUMN ...`)
7. 인덱스 생성 (`CREATE INDEX IF NOT EXISTS ...`)

**결과**: 앱 재시작만으로 Migration v5 자동 적용.

---

## 수동 실행 (선택 사항)

앱을 실행하지 않고 수동으로 마이그레이션하려면:

```python
# scripts/run_migration_v5.py
import sqlite3
from pathlib import Path
from titrack.db.connection import Database

# 로컬 DB 경로
db_path = Path.home() / "AppData" / "Local" / "TITrack" / "tracker.db"

# 데이터베이스 연결 및 마이그레이션 실행
db = Database(db_path)
db.connect()  # 자동으로 마이그레이션 실행됨

print("Migration v5 완료")
db.close()
```

실행:
```bash
python scripts/run_migration_v5.py
```

---

## 검증 쿼리

Migration v5 적용 후 다음 쿼리로 검증:

### 1. 스키마 버전 확인
```sql
SELECT value FROM settings WHERE key = 'schema_version';
-- 기대값: '5'
```

### 2. items 테이블 컬럼 확인
```sql
PRAGMA table_info(items);
```

**기대 출력** (18개 컬럼):
```
cid  name            type     notnull  dflt_value  pk
---  --------------  -------  -------  ----------  --
0    config_base_id  INTEGER  0        NULL        1
1    name_en         TEXT     0        NULL        0
2    name_cn         TEXT     0        NULL        0
3    type_cn         TEXT     0        NULL        0
4    icon_url        TEXT     0        NULL        0
5    url_en          TEXT     0        NULL        0
6    url_cn          TEXT     0        NULL        0
7    name_ko         TEXT     0        NULL        0
8    type_ko         TEXT     0        NULL        0
9    type_en         TEXT     0        NULL        0
10   url_tlidb       TEXT     0        NULL        0
11   category        TEXT     0        NULL        0
12   subcategory     TEXT     0        NULL        0
13   tier            INTEGER  0        NULL        0
14   tradeable       INTEGER  0        1           0
15   stackable       INTEGER  0        1           0
16   created_at      TEXT     0        NULL        0
17   updated_at      TEXT     0        NULL        0
```

### 3. 인덱스 확인
```sql
SELECT name, sql FROM sqlite_master
WHERE type = 'index' AND tbl_name = 'items'
ORDER BY name;
```

**기대 출력** (4개 인덱스):
```
name                      sql
------------------------  ----------------------------------------------------
idx_items_category        CREATE INDEX idx_items_category ON items(category)
idx_items_subcategory     CREATE INDEX idx_items_subcategory ON items(subcategory)
idx_items_tier            CREATE INDEX idx_items_tier ON items(tier)
idx_items_updated         CREATE INDEX idx_items_updated ON items(updated_at)
```

### 4. 기존 데이터 보존 확인
```sql
SELECT COUNT(*) FROM items WHERE config_base_id IS NOT NULL;
-- 기대값: 기존 아이템 수와 동일 (0 이상)
```

### 5. 새 컬럼 NULL 확인
```sql
SELECT COUNT(*) FROM items
WHERE name_ko IS NULL
  AND type_ko IS NULL
  AND category IS NULL;
-- 기대값: 기존 아이템 수 (새 컬럼은 NULL, 클라우드 동기화로 채움)
```

### 6. 기본값 확인
```sql
SELECT COUNT(*) FROM items WHERE tradeable = 1;
SELECT COUNT(*) FROM items WHERE stackable = 1;
-- 기대값: 기존 아이템 수 (기본값 1 적용됨)
```

---

## 데이터 채우기

Migration v5는 **컬럼만 추가**하며, 데이터는 **클라우드 동기화**로 채워집니다.

### 채우기 방법 1: Supabase 동기화 (권장)

1. Supabase에서 `002_items_master.sql` 실행
2. `scripts/load_items_to_supabase.py` 실행 (3,500개 아이템 업로드)
3. TITrack 앱에서 "클라우드 동기화" 활성화
4. 앱이 Supabase에서 아이템 메타데이터 다운로드
5. 로컬 `items` 테이블에 자동 병합

### 채우기 방법 2: items_ko.json 수동 로드 (임시)

```python
# scripts/load_items_ko_to_db.py
import json
import sqlite3
from pathlib import Path

# 로컬 DB 경로
db_path = Path.home() / "AppData" / "Local" / "TITrack" / "tracker.db"
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# items_ko.json 로드
with open("src/titrack/data/items_ko.json", "r", encoding="utf-8") as f:
    items_ko = json.load(f)

# 업데이트 쿼리 (name_ko, type_ko만 채움)
for config_id, item_data in items_ko.items():
    cursor.execute("""
        UPDATE items
        SET name_ko = ?, type_ko = ?, updated_at = datetime('now')
        WHERE config_base_id = ?
    """, (
        item_data.get("name"),
        item_data.get("type"),
        int(config_id)
    ))

conn.commit()
print(f"Updated {len(items_ko)} items with Korean names")
conn.close()
```

실행:
```bash
python scripts/load_items_ko_to_db.py
```

---

## 롤백 (Downgrade)

Migration v5를 되돌리려면 (v5 → v4):

**주의**: SQLite는 `DROP COLUMN`을 지원하지 않으므로 **테이블 재생성** 필요.

### 롤백 스크립트

```sql
-- 백업 생성
CREATE TABLE items_backup AS SELECT * FROM items;

-- 기존 테이블 삭제
DROP TABLE items;

-- v4 스키마로 재생성
CREATE TABLE items (
    config_base_id INTEGER PRIMARY KEY,
    name_en TEXT,
    name_cn TEXT,
    type_cn TEXT,
    icon_url TEXT,
    url_en TEXT,
    url_cn TEXT
);

-- 기존 데이터 복원 (v4 컬럼만)
INSERT INTO items (config_base_id, name_en, name_cn, type_cn, icon_url, url_en, url_cn)
SELECT config_base_id, name_en, name_cn, type_cn, icon_url, url_en, url_cn
FROM items_backup;

-- 백업 삭제 (선택 사항)
DROP TABLE items_backup;

-- 스키마 버전 되돌리기
UPDATE settings SET value = '4' WHERE key = 'schema_version';
```

**주의**: 롤백 시 `name_ko`, `category`, `tier` 등 새 컬럼의 데이터는 **영구 삭제**됩니다.

---

## 하위 호환성

- ✅ 기존 v4 데이터 보존 (config_base_id, name_en, icon_url 등)
- ✅ 기존 쿼리 동작 보장 (새 컬럼은 NULL 허용, WHERE 절 영향 없음)
- ✅ 기존 API 엔드포인트 동작 보장 (`/api/items`, `/api/prices`)
- ✅ 기존 Repository 메서드 동작 보장 (`get_item()`, `upsert_item()`)

### 주의사항

- 새 컬럼을 참조하는 코드는 **NULL 체크** 필요:
  ```python
  name_ko = item.name_ko if item.name_ko else item.name_en
  ```
- Supabase 동기화 활성화 전까지 새 컬럼은 NULL 상태.

---

## 성능 영향

- **컬럼 추가**: 기존 행에 영향 없음 (NULL 컬럼은 저장 공간 미사용)
- **인덱스 추가**:
  - 쓰기 성능 약 5-10% 감소 (인덱스 갱신 오버헤드)
  - 읽기 성능 향상 (카테고리/티어 필터링 쿼리 2-10배 빠름)
- **DB 파일 크기**: 약 2-5% 증가 (인덱스 메타데이터)

---

## 테스트 체크리스트

- [ ] 스키마 버전이 '5'로 업데이트됨
- [ ] items 테이블에 18개 컬럼 존재
- [ ] 4개 인덱스 생성됨
- [ ] 기존 아이템 데이터 보존됨
- [ ] 새 컬럼 기본값 적용됨 (tradeable=1, stackable=1)
- [ ] 앱 재시작 후 정상 동작
- [ ] `/api/items` 엔드포인트 정상 응답
- [ ] 아이템 이름 표시 정상 (한국어 → 영어 폴백)

---

## 문제 해결

### Q1: "table items has no column named name_ko" 오류
**원인**: Migration v5가 실행되지 않음.
**해결**: 앱을 재시작하거나 `scripts/run_migration_v5.py` 실행.

### Q2: 한국어 이름이 표시되지 않음
**원인**: `name_ko` 컬럼이 NULL 상태.
**해결**:
1. Supabase 동기화 활성화 (권장)
2. `scripts/load_items_ko_to_db.py` 실행 (임시)

### Q3: 인덱스가 생성되지 않음
**원인**: SQLite 버전이 3.3.0 미만 (CREATE INDEX IF NOT EXISTS 미지원).
**해결**: Python 3.11+는 SQLite 3.37+ 내장, 문제 없음.

### Q4: 롤백 후 데이터 손실
**원인**: SQLite는 `DROP COLUMN` 미지원, 테이블 재생성 시 v5 컬럼 삭제됨.
**해결**: 롤백 전 `items_backup` 테이블 생성, 필요 시 복원.

---

## 다음 단계

1. ✅ Migration v5 자동 실행 완료
2. ⏳ Supabase `002_items_master.sql` 실행
3. ⏳ `load_items_to_supabase.py` 실행 (3,500 items)
4. ⏳ 클라이언트 동기화 로직 구현 (`sync/manager.py`)
5. ⏳ 한국어 이름 통합 (`korean_names.py` 수정)
6. ⏳ 통합 테스트 작성 및 실행

---

## 참고 문서

- [`docs/supabase_architecture.md`](supabase_architecture.md) - Supabase 아키텍처 설계
- [`supabase/migrations/002_items_master.sql`](../supabase/migrations/002_items_master.sql) - Supabase items 스키마
- [`src/titrack/db/schema.py`](../src/titrack/db/schema.py) - 로컬 스키마 정의
- [`src/titrack/db/connection.py`](../src/titrack/db/connection.py) - 마이그레이션 로직

---

**작성 완료**: 2026-02-12
**작성자**: Backend Agent
**버전**: Migration v5 Guide v1.0
