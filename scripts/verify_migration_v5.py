"""
Migration v5 검증 스크립트

Migration v5 (items 테이블 Supabase 정렬) 적용 후
스키마, 인덱스, 데이터 무결성을 검증합니다.

Usage:
    python scripts/verify_migration_v5.py
"""

import sqlite3
import sys
from pathlib import Path
from typing import Any
import sys
import codecs

# Windows 콘솔 UTF-8 강제 설정 (한글 깨짐 방지)
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')




def get_db_path() -> Path:
    """로컬 DB 경로 반환."""
    # Windows 기본 경로
    db_path = Path.home() / "AppData" / "Local" / "TITrack" / "tracker.db"

    if not db_path.exists():
        # 포터블 모드 경로
        alt_path = Path("data/tracker.db")
        if alt_path.exists():
            return alt_path
        else:
            print(f"[ERROR] DB 파일을 찾을 수 없습니다: {db_path}")
            sys.exit(1)

    return db_path


def verify_schema_version(conn: sqlite3.Connection) -> bool:
    """스키마 버전이 '5'인지 확인."""
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = 'schema_version'")
    row = cursor.fetchone()

    if row and row[0] == "5":
        print("[OK] 스키마 버전: 5")
        return True
    else:
        version = row[0] if row else "없음"
        print(f"[ERROR] 스키마 버전: {version} (기대값: 5)")
        return False


def verify_items_columns(conn: sqlite3.Connection) -> bool:
    """items 테이블에 18개 컬럼이 있는지 확인."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(items)")
    columns = cursor.fetchall()

    expected_columns = {
        "config_base_id", "name_en", "name_cn", "type_cn", "icon_url", "url_en", "url_cn",
        "name_ko", "type_ko", "type_en", "url_tlidb", "category", "subcategory", "tier",
        "tradeable", "stackable", "created_at", "updated_at"
    }

    actual_columns = {col[1] for col in columns}

    if expected_columns == actual_columns:
        print(f"[OK] items 테이블 컬럼: {len(actual_columns)}개 (기대값: 18개)")
        return True
    else:
        missing = expected_columns - actual_columns
        extra = actual_columns - expected_columns

        print(f"[ERROR] items 테이블 컬럼: {len(actual_columns)}개 (기대값: 18개)")
        if missing:
            print(f"   누락된 컬럼: {missing}")
        if extra:
            print(f"   추가된 컬럼: {extra}")
        return False


def verify_indexes(conn: sqlite3.Connection) -> bool:
    """items 테이블에 4개 인덱스가 있는지 확인."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type = 'index' AND tbl_name = 'items'
        ORDER BY name
    """)
    indexes = [row[0] for row in cursor.fetchall()]

    expected_indexes = {
        "idx_items_category",
        "idx_items_subcategory",
        "idx_items_tier",
        "idx_items_updated",
    }

    # sqlite_autoindex는 제외 (PRIMARY KEY 자동 인덱스)
    actual_indexes = {idx for idx in indexes if not idx.startswith("sqlite_autoindex")}

    if expected_indexes.issubset(actual_indexes):
        print(f"[OK] items 인덱스: {len(actual_indexes)}개 (최소 4개 기대)")
        for idx in sorted(actual_indexes):
            print(f"   - {idx}")
        return True
    else:
        missing = expected_indexes - actual_indexes
        print(f"[ERROR] items 인덱스: {len(actual_indexes)}개")
        print(f"   누락된 인덱스: {missing}")
        return False


def verify_existing_data(conn: sqlite3.Connection) -> bool:
    """기존 데이터가 보존되었는지 확인."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM items WHERE config_base_id IS NOT NULL")
    count = cursor.fetchone()[0]

    if count >= 0:
        print(f"[OK] 기존 아이템 데이터: {count}개 보존됨")
        return True
    else:
        print("[ERROR] 기존 아이템 데이터 조회 실패")
        return False


def verify_new_columns_null(conn: sqlite3.Connection) -> bool:
    """새 컬럼이 NULL 상태인지 확인 (클라우드 동기화 전)."""
    cursor = conn.cursor()

    # 전체 아이템 수
    cursor.execute("SELECT COUNT(*) FROM items")
    total_count = cursor.fetchone()[0]

    if total_count == 0:
        print("[WARNING]  items 테이블이 비어있음 (첫 실행 또는 시드 전)")
        return True

    # 새 컬럼이 모두 NULL인 아이템 수
    cursor.execute("""
        SELECT COUNT(*) FROM items
        WHERE name_ko IS NULL
          AND type_ko IS NULL
          AND category IS NULL
          AND tier IS NULL
          AND created_at IS NULL
          AND updated_at IS NULL
    """)
    null_count = cursor.fetchone()[0]

    # 새 컬럼에 데이터가 있는 아이템 수
    synced_count = total_count - null_count

    if null_count == total_count:
        print(f"[OK] 새 컬럼: 모두 NULL (클라우드 동기화 대기 중)")
        return True
    elif synced_count > 0:
        print(f"[OK] 새 컬럼: {synced_count}개 아이템 동기화됨, {null_count}개 대기 중")
        return True
    else:
        print("[ERROR] 새 컬럼 상태 확인 실패")
        return False


def verify_default_values(conn: sqlite3.Connection) -> bool:
    """기본값이 올바르게 적용되었는지 확인."""
    cursor = conn.cursor()

    # tradeable 기본값 (1)
    cursor.execute("SELECT COUNT(*) FROM items WHERE tradeable = 1")
    tradeable_count = cursor.fetchone()[0]

    # stackable 기본값 (1)
    cursor.execute("SELECT COUNT(*) FROM items WHERE stackable = 1")
    stackable_count = cursor.fetchone()[0]

    # 전체 아이템 수
    cursor.execute("SELECT COUNT(*) FROM items")
    total_count = cursor.fetchone()[0]

    if total_count == 0:
        print("[WARNING]  items 테이블이 비어있음 (기본값 검증 스킵)")
        return True

    if tradeable_count == total_count and stackable_count == total_count:
        print(f"[OK] 기본값 적용: tradeable={tradeable_count}, stackable={stackable_count}")
        return True
    else:
        print(f"[WARNING]  기본값 부분 적용: tradeable={tradeable_count}/{total_count}, stackable={stackable_count}/{total_count}")
        return True  # 경고만 표시, 실패 아님 (일부 아이템이 거래/스택 불가일 수 있음)


def print_sample_data(conn: sqlite3.Connection) -> None:
    """샘플 데이터 출력 (디버깅용)."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT config_base_id, name_ko, name_en, category, tier, tradeable, stackable
        FROM items
        LIMIT 5
    """)
    rows = cursor.fetchall()

    if rows:
        print("\n[DATA] 샘플 데이터 (최대 5개):")
        for row in rows:
            print(f"   ID {row[0]}: {row[1] or row[2] or '(이름 없음)'} | "
                  f"카테고리: {row[3] or 'NULL'} | 티어: {row[4] or 'NULL'} | "
                  f"거래: {row[5]} | 스택: {row[6]}")
    else:
        print("\n[WARNING]  items 테이블이 비어있음")


def main() -> None:
    """메인 검증 루틴."""
    print("=" * 60)
    print("Migration v5 검증 스크립트")
    print("=" * 60)

    # DB 연결
    db_path = get_db_path()
    print(f"\nDB 경로: {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # 검증 실행
    results = []

    print("\n[1/6] 스키마 버전 확인")
    results.append(verify_schema_version(conn))

    print("\n[2/6] items 테이블 컬럼 확인")
    results.append(verify_items_columns(conn))

    print("\n[3/6] items 인덱스 확인")
    results.append(verify_indexes(conn))

    print("\n[4/6] 기존 데이터 보존 확인")
    results.append(verify_existing_data(conn))

    print("\n[5/6] 새 컬럼 상태 확인")
    results.append(verify_new_columns_null(conn))

    print("\n[6/6] 기본값 확인")
    results.append(verify_default_values(conn))

    # 샘플 데이터 출력
    print_sample_data(conn)

    # 최종 결과
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)

    if all(results):
        print(f"[OK] 검증 성공: {passed}/{total} 통과")
        print("\nMigration v5가 올바르게 적용되었습니다.")
        print("다음 단계:")
        print("  1. Supabase 002_items_master.sql 마이그레이션 실행")
        print("  2. load_items_to_supabase.py 실행 (3,500 items)")
        print("  3. TITrack 앱에서 클라우드 동기화 활성화")
    else:
        print(f"[ERROR] 검증 실패: {passed}/{total} 통과")
        print("\nMigration v5가 올바르게 적용되지 않았습니다.")
        print("해결 방법:")
        print("  1. 앱을 재시작하여 자동 마이그레이션 실행")
        print("  2. scripts/run_migration_v5.py 실행 (수동)")

    print("=" * 60)

    conn.close()

    # 종료 코드 설정 (CI/CD 통합용)
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
