"""
Migration v5 롤백 스크립트 (v5 → v4)

경고: 이 스크립트는 items 테이블을 v4 스키마로 되돌립니다.
      v5에서 추가된 데이터 (name_ko, category, tier 등)는 영구 삭제됩니다.
      롤백 전 반드시 백업하세요!

Usage:
    python scripts/rollback_migration_v5.py [--confirm]

Options:
    --confirm  확인 없이 즉시 롤백 실행 (자동화용)
"""

import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
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


def backup_db(db_path: Path) -> Path:
    """DB 파일 전체 백업."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"{db_path.stem}_backup_v5_to_v4_{timestamp}{db_path.suffix}"

    print(f"DB 백업 생성 중: {backup_path}")
    shutil.copy2(db_path, backup_path)
    print(f"[OK] 백업 완료: {backup_path}")

    return backup_path


def rollback_v5_to_v4(conn: sqlite3.Connection) -> None:
    """Migration v5 → v4 롤백 실행."""
    cursor = conn.cursor()

    print("\n[1/6] items_backup 테이블 생성 중...")
    cursor.execute("DROP TABLE IF EXISTS items_backup")
    cursor.execute("CREATE TABLE items_backup AS SELECT * FROM items")
    backup_count = cursor.execute("SELECT COUNT(*) FROM items_backup").fetchone()[0]
    print(f"   [OK] {backup_count}개 아이템 백업 완료")

    print("\n[2/6] 기존 items 테이블 삭제 중...")
    cursor.execute("DROP TABLE items")
    print("   [OK] 삭제 완료")

    print("\n[3/6] v4 스키마로 items 테이블 재생성 중...")
    cursor.execute("""
        CREATE TABLE items (
            config_base_id INTEGER PRIMARY KEY,
            name_en TEXT,
            name_cn TEXT,
            type_cn TEXT,
            icon_url TEXT,
            url_en TEXT,
            url_cn TEXT
        )
    """)
    print("   [OK] 재생성 완료 (7개 컬럼)")

    print("\n[4/6] v4 컬럼 데이터 복원 중...")
    cursor.execute("""
        INSERT INTO items (config_base_id, name_en, name_cn, type_cn, icon_url, url_en, url_cn)
        SELECT config_base_id, name_en, name_cn, type_cn, icon_url, url_en, url_cn
        FROM items_backup
    """)
    restored_count = cursor.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    print(f"   [OK] {restored_count}개 아이템 복원 완료")

    print("\n[5/6] 스키마 버전 되돌리기...")
    cursor.execute("UPDATE settings SET value = '4' WHERE key = 'schema_version'")
    version = cursor.execute("SELECT value FROM settings WHERE key = 'schema_version'").fetchone()[0]
    print(f"   [OK] 스키마 버전: {version}")

    print("\n[6/6] items_backup 테이블 유지 (복구용)")
    print("   [WARNING]  items_backup 테이블은 삭제하지 않았습니다.")
    print("   [WARNING]  복구가 필요하면 이 테이블을 사용하세요.")
    print("   [WARNING]  확인 후 수동으로 삭제: DROP TABLE items_backup;")

    conn.commit()


def verify_rollback(conn: sqlite3.Connection) -> bool:
    """롤백 검증."""
    cursor = conn.cursor()

    print("\n" + "=" * 60)
    print("롤백 검증")
    print("=" * 60)

    # 스키마 버전 확인
    version = cursor.execute("SELECT value FROM settings WHERE key = 'schema_version'").fetchone()[0]
    if version == "4":
        print(f"[OK] 스키마 버전: {version}")
    else:
        print(f"[ERROR] 스키마 버전: {version} (기대값: 4)")
        return False

    # 컬럼 수 확인
    cursor.execute("PRAGMA table_info(items)")
    columns = cursor.fetchall()
    if len(columns) == 7:
        print(f"[OK] items 테이블 컬럼: {len(columns)}개 (기대값: 7)")
    else:
        print(f"[ERROR] items 테이블 컬럼: {len(columns)}개 (기대값: 7)")
        return False

    # 데이터 보존 확인
    item_count = cursor.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    backup_count = cursor.execute("SELECT COUNT(*) FROM items_backup").fetchone()[0]
    if item_count == backup_count:
        print(f"[OK] 데이터 보존: {item_count}개 (백업: {backup_count}개)")
    else:
        print(f"[ERROR] 데이터 손실: {item_count}개 (백업: {backup_count}개)")
        return False

    return True


def main() -> None:
    """메인 롤백 루틴."""
    print("=" * 60)
    print("Migration v5 롤백 스크립트 (v5 → v4)")
    print("=" * 60)

    # 인자 확인
    auto_confirm = "--confirm" in sys.argv

    # DB 경로 확인
    db_path = get_db_path()
    print(f"\nDB 경로: {db_path}")

    # 스키마 버전 확인
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    current_version = cursor.execute("SELECT value FROM settings WHERE key = 'schema_version'").fetchone()
    if not current_version or current_version[0] != "5":
        version = current_version[0] if current_version else "알 수 없음"
        print(f"\n[ERROR] 현재 스키마 버전: {version}")
        print("   롤백 불필요 또는 불가능 (v5가 아님)")
        conn.close()
        sys.exit(1)

    print(f"\n현재 스키마 버전: 5")

    # 경고 표시
    print("\n" + "!" * 60)
    print("[WARNING]  경고: 다음 데이터가 영구 삭제됩니다!")
    print("!" * 60)
    print("  - name_ko (한국어 이름)")
    print("  - type_ko, type_en (한국어/영어 타입)")
    print("  - url_tlidb (TLIDB 링크)")
    print("  - category, subcategory (카테고리)")
    print("  - tier (티어)")
    print("  - tradeable, stackable (거래/스택 가능 여부)")
    print("  - created_at, updated_at (타임스탬프)")
    print("!" * 60)

    # 확인
    if not auto_confirm:
        response = input("\n롤백을 진행하시겠습니까? (yes/no): ").strip().lower()
        if response not in ("yes", "y"):
            print("\n롤백 취소됨")
            conn.close()
            sys.exit(0)

    # DB 파일 전체 백업
    print("\n" + "=" * 60)
    print("DB 파일 백업")
    print("=" * 60)
    backup_path = backup_db(db_path)

    # 롤백 실행
    print("\n" + "=" * 60)
    print("롤백 실행")
    print("=" * 60)

    try:
        rollback_v5_to_v4(conn)

        # 검증
        if verify_rollback(conn):
            print("\n" + "=" * 60)
            print("[OK] 롤백 성공!")
            print("=" * 60)
            print(f"\n백업 파일: {backup_path}")
            print("items_backup 테이블: DB 내부에 유지됨")
            print("\n주의사항:")
            print("  1. 앱 재시작 시 v5 마이그레이션이 다시 실행될 수 있습니다.")
            print("  2. v4 상태 유지를 원하면 schema.py의 SCHEMA_VERSION을 4로 수정하세요.")
            print("  3. items_backup 테이블 삭제: DROP TABLE items_backup;")
        else:
            print("\n" + "=" * 60)
            print("[ERROR] 롤백 검증 실패")
            print("=" * 60)
            print(f"\n백업에서 복구하려면: {backup_path}")
            conn.close()
            sys.exit(1)

    except Exception as e:
        print(f"\n[ERROR] 롤백 실패: {e}")
        import traceback
        traceback.print_exc()
        print(f"\n백업에서 복구하려면: {backup_path}")
        conn.close()
        sys.exit(1)

    conn.close()


if __name__ == "__main__":
    main()
