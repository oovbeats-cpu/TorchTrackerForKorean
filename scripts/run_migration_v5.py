"""
Migration v5 수동 실행 스크립트

앱을 실행하지 않고 수동으로 Migration v5를 적용합니다.
(일반적으로는 앱 재시작 시 자동 실행됨)

Usage:
    python scripts/run_migration_v5.py
"""

import sys
from pathlib import Path
import sys
import codecs

# Windows 콘솔 UTF-8 강제 설정 (한글 깨짐 방지)
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')



# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from titrack.db.connection import Database


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
            print(f"[WARNING]  DB 파일을 찾을 수 없습니다: {db_path}")
            print("   앱을 한 번 실행하여 DB를 생성하거나, 경로를 확인하세요.")
            sys.exit(1)

    return db_path


def main() -> None:
    """메인 실행 루틴."""
    print("=" * 60)
    print("Migration v5 수동 실행 스크립트")
    print("=" * 60)

    # DB 경로 확인
    db_path = get_db_path()
    print(f"\nDB 경로: {db_path}")

    # DB 연결 (자동으로 마이그레이션 실행됨)
    print("\nDB 연결 중... (마이그레이션 자동 실행)")
    try:
        db = Database(db_path)
        db.connect()

        # 스키마 버전 확인
        result = db.fetchone("SELECT value FROM settings WHERE key = 'schema_version'")
        version = result[0] if result else "알 수 없음"

        print(f"\n[OK] Migration v5 완료")
        print(f"   현재 스키마 버전: {version}")

        # 컬럼 수 확인
        cursor = db.execute("PRAGMA table_info(items)")
        columns = cursor.fetchall()
        print(f"   items 테이블 컬럼: {len(columns)}개")

        # 인덱스 수 확인
        cursor = db.execute("""
            SELECT COUNT(*) FROM sqlite_master
            WHERE type = 'index' AND tbl_name = 'items'
              AND name NOT LIKE 'sqlite_autoindex%'
        """)
        index_count = cursor.fetchone()[0]
        print(f"   items 인덱스: {index_count}개")

        db.close()

        print("\n다음 단계:")
        print("  1. python scripts/verify_migration_v5.py 실행 (검증)")
        print("  2. Supabase 002_items_master.sql 마이그레이션 실행")
        print("  3. python scripts/load_items_to_supabase.py 실행")

    except Exception as e:
        print(f"\n[ERROR] Migration v5 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("=" * 60)


if __name__ == "__main__":
    main()
