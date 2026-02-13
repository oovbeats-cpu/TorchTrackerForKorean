# Supabase 클라우드 백엔드 구축 가이드

> **작업 일자**: 2026-02-12
> **담당**: Backend Agent
> **목표**: Migration 002 실행 및 초기 데이터 로드 (2,447개 장비 아이템)

---

## 준비 사항

### 1. 환경 변수 설정

프로젝트 루트에 `.env` 파일이 생성되어 있습니다:

```
TITRACK_SUPABASE_URL=https://dxuxdnglefrxtqvfitho.supabase.co
TITRACK_SUPABASE_KEY=sb_secret_AOxzX8M00M7CYwpnvSM8lw_-JQhyMNk
```

**주의**:
- Service role key를 사용하고 있습니다 (초기 로드용 관리자 권한)
- `.env` 파일은 `.gitignore`에 등록되어 있으므로 커밋되지 않습니다
- 클라이언트 앱에서는 anon key를 사용해야 합니다:
  - `sb_publishable_336WoGt3TS-a3bYXoLlETA_2Y7CGI8t`

### 2. 필수 패키지 확인

```bash
python -c "import supabase; print(supabase.__version__)"
```

출력: `2.27.2` (설치 완료)

---

## Step 1: Migration 002 실행

### 1.1 Supabase Dashboard 접속

브라우저에서 다음 URL로 이동:

```
https://app.supabase.com/project/dxuxdnglefrxtqvfitho
```

### 1.2 SQL Editor 열기

1. 왼쪽 메뉴에서 **SQL Editor** 클릭
2. **+ New query** 버튼 클릭

### 1.3 Migration SQL 복사

다음 파일의 내용을 전체 복사:

```
C:\Users\f4u12\OneDrive\문서\Github\TorchTrackerForKorean\supabase\migrations\002_items_master.sql
```

**파일 내용 요약**:
- `schema_version` 테이블 생성 (마이그레이션 추적)
- `items` 테이블 생성 (16개 컬럼)
- 6개 인덱스 생성 (category, subcategory, tier, updated_at, tradeable, category+tier)
- RLS (Row Level Security) 정책 설정 (public read access)
- 3개 함수 생성:
  - `fetch_items_delta()` - 델타 동기화용
  - `update_item_timestamp()` - updated_at 자동 갱신 트리거
  - `get_item_stats()` - 통계 조회

### 1.4 SQL 실행

1. SQL Editor에 붙여넣기
2. **Run** 버튼 클릭
3. 성공 메시지 확인:
   - "Success. No rows returned"
   - 또는 "Query executed successfully"

### 1.5 검증

SQL Editor에서 다음 쿼리 실행:

```sql
-- 테이블 확인
SELECT COUNT(*) FROM items;  -- 결과: 0 (아직 데이터 없음)

-- 스키마 버전 확인
SELECT * FROM schema_version ORDER BY version;
-- 결과: version 1, 2 두 레코드 존재

-- 인덱스 확인
SELECT indexname FROM pg_indexes WHERE tablename = 'items';
-- 결과: 6개 인덱스

-- RLS 정책 확인
SELECT policyname FROM pg_policies WHERE tablename = 'items';
-- 결과: "Public read access for items"

-- 함수 확인
SELECT * FROM fetch_items_delta() LIMIT 5;
-- 결과: 0 rows (데이터 없음)
```

**✅ 모든 검증 통과 시 Step 2로 진행**

---

## Step 2: 초기 데이터 로드

### 2.1 환경 변수 설정 (Windows CMD)

```cmd
cd C:\Users\f4u12\OneDrive\문서\Github\TorchTrackerForKorean
set TITRACK_SUPABASE_URL=https://dxuxdnglefrxtqvfitho.supabase.co
set TITRACK_SUPABASE_KEY=sb_secret_AOxzX8M00M7CYwpnvSM8lw_-JQhyMNk
```

### 2.2 데이터 로드 스크립트 실행

```cmd
python scripts\load_equipment_data.py
```

**예상 출력**:

```
======================================================================
  TITrack - Load Equipment Data to Supabase
======================================================================

[OK] Supabase URL: https://dxuxdnglefrxtqvfitho.supabase.co
[OK] API Key: sb_secret_AOxzX8M00M...
[OK] Supabase client created

Checking if items table exists...
[OK] items table exists (current records: 0)

Loading data from: C:\Users\f4u12\OneDrive\문서\Github\TorchTrackerForKorean\ref\v\20260212.txt
[OK] Loaded 2447 items from file

Converting items...
[OK] Converted 2447 items

Uploading to Supabase...
  Batch 1/25: [OK] 100 items uploaded
  Batch 2/25: [OK] 100 items uploaded
  ...
  Batch 25/25: [OK] 47 items uploaded

======================================================================
Upload Summary:
  Total items:       2447
  Uploaded:          2447
  Errors:            0
======================================================================

Verifying upload...
[OK] Total items in Supabase: 2447
[OK] Sample items (first 5):
     - 100: 클로 (claw)
     - 101: 데몬샤크의 이빨 (claw)
     - 102: 곡괭이 클로 (claw)
     - 103: 검은 고양이 클로 (claw)
     - 104: 눈부신 클로 (claw)

[OK] Done!
```

---

## Step 3: 최종 검증

Supabase Dashboard에서 다음 쿼리로 최종 검증:

```sql
-- 1. 총 레코드 수
SELECT COUNT(*) FROM items;
-- 결과: 2447

-- 2. 카테고리별 분포
SELECT category, COUNT(*) as count
FROM items
GROUP BY category;
-- 결과: equipment | 2447

-- 3. 서브카테고리별 분포 (상위 10개)
SELECT subcategory, COUNT(*) as count
FROM items
WHERE subcategory IS NOT NULL
GROUP BY subcategory
ORDER BY count DESC
LIMIT 10;

-- 4. 티어별 분포
SELECT tier, COUNT(*) as count
FROM items
GROUP BY tier
ORDER BY tier;

-- 5. 샘플 데이터 (무작위 5개)
SELECT config_base_id, name_ko, subcategory, tier
FROM items
ORDER BY RANDOM()
LIMIT 5;

-- 6. fetch_items_delta 함수 테스트
SELECT config_base_id, name_ko, category, updated_at
FROM fetch_items_delta()
LIMIT 10;

-- 7. 통계 함수 테스트
SELECT * FROM get_item_stats();
```

---

## 트러블슈팅

### 문제 1: Migration 실행 시 "relation already exists" 오류

**원인**: 이미 Migration이 실행됨

**해결**:
```sql
-- 테이블 존재 확인
SELECT COUNT(*) FROM items;
-- 결과가 나오면 이미 Migration 완료, Step 2로 진행
```

### 문제 2: 데이터 로드 시 "items table not found" 오류

**원인**: Migration 미실행 또는 실패

**해결**:
1. Supabase Dashboard SQL Editor에서 다음 실행:
   ```sql
   SELECT * FROM schema_version;
   ```
2. version 2가 없으면 Step 1부터 다시 실행

### 문제 3: 업로드 중 "permission denied" 오류

**원인**: Service role key 대신 anon key 사용

**해결**:
1. `.env` 파일에서 `TITRACK_SUPABASE_KEY` 확인
2. `sb_secret_`으로 시작하는지 확인 (service role key)
3. `sb_publishable_`로 시작하면 잘못된 키

### 문제 4: 환경 변수 미인식

**원인**: `.env` 파일 미로드 또는 경로 문제

**해결**:
```cmd
# CMD에서 직접 환경 변수 설정
set TITRACK_SUPABASE_URL=https://dxuxdnglefrxtqvfitho.supabase.co
set TITRACK_SUPABASE_KEY=sb_secret_AOxzX8M00M7CYwpnvSM8lw_-JQhyMNk

# 확인
echo %TITRACK_SUPABASE_URL%
```

---

## 롤백 (Migration 취소)

문제 발생 시 다음 SQL로 롤백 가능:

```sql
-- Step 1: Trigger 삭제
DROP TRIGGER IF EXISTS items_updated_at_trigger ON items;

-- Step 2: 함수 삭제
DROP FUNCTION IF EXISTS update_item_timestamp CASCADE;
DROP FUNCTION IF EXISTS get_item_stats CASCADE;
DROP FUNCTION IF EXISTS fetch_items_delta CASCADE;

-- Step 3: 테이블 삭제
DROP TABLE IF EXISTS items CASCADE;

-- Step 4: 스키마 버전 기록 삭제
DELETE FROM schema_version WHERE version = 2;
```

**주의**: 데이터도 모두 삭제되므로 신중히 사용

---

## 다음 단계

Migration 002 및 초기 데이터 로드 완료 후:

1. **클라이언트 동기화 로직 구현**
   - `src/titrack/sync/client.py` 수정
   - `src/titrack/sync/manager.py` 수정
   - `fetch_items_delta()` 함수 활용

2. **로컬 DB 마이그레이션 v5**
   - `src/titrack/db/schema.py` 수정
   - items 테이블 확장 (name_en, icon_url, category, subcategory, tier 추가)

3. **한국어 이름 통합**
   - `src/titrack/data/korean_names.py` 수정
   - Supabase에서 name_ko 가져오기

4. **통합 테스트**
   - 클라이언트 동기화 테스트
   - 델타 동기화 테스트
   - 가격 조회 우선순위 테스트

---

## 참고 문서

- **Supabase 아키텍처**: `docs/supabase_architecture.md`
- **Migration 파일**: `supabase/migrations/002_items_master.sql`
- **데이터 파일**: `ref/v/20260212.txt` (2,447개 장비 아이템)
- **Tasks.md**: `docs/Tasks.md` (작업 로그)

---

**작성자**: Backend Agent
**검토**: 필요 시 Main Agent에게 요청
**마지막 업데이트**: 2026-02-12
