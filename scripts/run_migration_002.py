#!/usr/bin/env python3
"""
TITrack - Auto Migration 002 + Data Load

이 스크립트는:
1. Migration 002 상태 확인
2. 필요 시 사용자에게 수동 실행 안내
3. items 테이블 확인 후 자동 데이터 로드
4. 검증 쿼리 실행

실행:
    python scripts/run_migration_002.py

환경 변수:
    TITRACK_SUPABASE_URL - Supabase 프로젝트 URL
    TITRACK_SUPABASE_KEY - Supabase service role key
"""

import os
import sys
from pathlib import Path
import sys
import codecs

# Windows 콘솔 UTF-8 강제 설정 (한글 깨짐 방지)
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')



# Supabase client (optional dependency)
try:
    from supabase import create_client, Client
    from dotenv import load_dotenv
    SUPABASE_AVAILABLE = True
except ImportError as e:
    print(f"[ERROR] 필요한 라이브러리가 설치되지 않았습니다: {e}")
    print("\n다음 명령어를 실행하세요:")
    print("  pip install titrack[cloud] python-dotenv")
    sys.exit(1)


def check_migration_status(client: Client) -> bool:
    """Migration 002가 적용되었는지 확인"""
    try:
        result = client.table("schema_version").select("*").eq("version", 2).execute()
        return len(result.data) > 0
    except Exception:
        return False


def check_items_table(client: Client) -> tuple[bool, int]:
    """items 테이블 존재 여부와 레코드 수 확인"""
    try:
        result = client.table("items").select("count", count="exact").execute()
        return True, result.count or 0
    except Exception:
        return False, 0


def prompt_manual_migration(supabase_url: str, migration_file: Path, auto_mode: bool = False) -> None:
    """수동 Migration 실행 안내"""
    project_id = supabase_url.split("//")[1].split(".")[0]

    print("\n" + "="*70)
    print("[!] Migration 002를 수동으로 실행해야 합니다")
    print("="*70)
    print("\nSupabase Python 클라이언트는 DDL을 직접 실행할 수 없습니다.")
    print("다음 단계를 따라 수동으로 실행하세요:\n")
    print(f"1. Supabase 대시보드 열기:")
    print(f"   https://app.supabase.com/project/{project_id}\n")
    print(f"2. 왼쪽 메뉴에서 'SQL Editor' 선택\n")
    print(f"3. 'New query' 버튼 클릭\n")
    print(f"4. 다음 파일 내용 복사/붙여넣기:")
    print(f"   {migration_file.absolute()}\n")
    print(f"5. 'Run' 버튼 클릭하여 실행\n")
    print(f"6. 완료 후 이 스크립트를 다시 실행하세요")
    print("="*70 + "\n")

    # 자동 모드이거나 대화형 환경이 아니면 항상 SQL 출력
    is_interactive = sys.stdin.isatty() and not auto_mode

    if not is_interactive:
        print("[AUTO] SQL 파일 내용을 자동으로 출력합니다:\n")
        print("="*70)
        try:
            sql_content = migration_file.read_text(encoding="utf-8")
            print(sql_content)
        except Exception as e:
            print(f"[ERROR] SQL 파일을 읽을 수 없습니다: {e}")
        print("="*70)
    else:
        # 대화형 환경에서만 물어봄
        try:
            response = input("[?] SQL 파일 내용을 여기에 출력할까요? (y/N): ").strip().lower()
            if response == 'y':
                print("\n" + "="*70)
                sql_content = migration_file.read_text(encoding="utf-8")
                print(sql_content)
                print("="*70)
        except (EOFError, KeyboardInterrupt):
            print("\n[!] 대화형 입력을 건너뜁니다")
            pass


def load_data() -> dict:
    """초기 데이터 로드 (load_equipment_data.py 호출)"""
    print("\n[*] 초기 데이터 로드 중...")

    # 프로젝트 루트를 sys.path에 추가
    root = Path(__file__).parent.parent
    sys.path.insert(0, str(root / "scripts"))

    try:
        from load_equipment_data import main as load_equipment
        result = load_equipment()
        return result
    except ImportError as e:
        print(f"[ERROR] load_equipment_data.py를 찾을 수 없습니다: {e}")
        return {"inserted": 0, "updated": 0, "skipped": 0}
    except Exception as e:
        print(f"[ERROR] 데이터 로드 실패: {e}")
        import traceback
        traceback.print_exc()
        return {"inserted": 0, "updated": 0, "skipped": 0}


def main() -> None:
    """메인 실행 함수"""
    # --auto 플래그 확인
    auto_mode = "--auto" in sys.argv or os.getenv("AUTO_MODE") == "1"

    print("="*70)
    print("TITrack - Auto Migration 002 + Data Load")
    if auto_mode:
        print("[AUTO MODE]")
    print("="*70)

    # .env 파일 로드
    load_dotenv()

    # 환경 변수에서 Supabase 설정 읽기
    supabase_url = os.environ.get("TITRACK_SUPABASE_URL")
    supabase_key = os.environ.get("TITRACK_SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        print("\n[ERROR] 환경 변수가 설정되지 않았습니다")
        print("\n.env 파일을 확인하세요:")
        print("  TITRACK_SUPABASE_URL=https://xxx.supabase.co")
        print("  TITRACK_SUPABASE_KEY=sb_secret_...")
        sys.exit(1)

    print(f"\n[OK] Supabase URL: {supabase_url}")
    print(f"[OK] API Key: {supabase_key[:20]}...")

    # Supabase 클라이언트 생성
    print("\n[*] Supabase 연결 중...")
    client = create_client(supabase_url, supabase_key)

    # 프로젝트 루트 경로
    root_path = Path(__file__).parent.parent
    migration_file = root_path / "supabase" / "migrations" / "002_items_master.sql"

    if not migration_file.exists():
        print(f"\n[ERROR] Migration 파일을 찾을 수 없습니다: {migration_file}")
        sys.exit(1)

    # 1. Migration 상태 확인
    print("\n[1/5] Migration 002 상태 확인 중...")
    migration_applied = check_migration_status(client)

    if migration_applied:
        print("[OK] Migration 002가 이미 적용되었습니다")
    else:
        print("[!] Migration 002가 아직 적용되지 않았습니다")

    # 2. items 테이블 확인
    print("\n[2/5] items 테이블 확인 중...")
    items_exists, items_count = check_items_table(client)

    if items_exists:
        print(f"[OK] items 테이블 존재 (레코드 수: {items_count}개)")
    else:
        print("[!] items 테이블이 없습니다")

    # 3. Migration 필요 여부 판단
    if not items_exists:
        prompt_manual_migration(supabase_url, migration_file, auto_mode=auto_mode)
        print("\n[PAUSE] Migration 실행 후 이 스크립트를 다시 실행하세요")
        sys.exit(0)

    # 4. 데이터 로드
    print("\n[3/5] 데이터 로드 확인 중...")
    if items_count == 0:
        print("[OK] items 테이블이 비어 있습니다. 데이터 로드를 시작합니다")
        result = load_data()

        print(f"\n[DONE] 데이터 로드 완료:")
        print(f"   - 삽입: {result['inserted']}개")
        print(f"   - 업데이트: {result['updated']}개")
        print(f"   - 건너뜀: {result['skipped']}개")
    else:
        print(f"[OK] items 테이블에 이미 {items_count}개 레코드가 있습니다")

        # 대화형 환경에서만 물어봄
        if sys.stdin.isatty():
            try:
                response = input("\n데이터를 다시 로드할까요? (y/N): ").strip().lower()

                if response == 'y':
                    result = load_data()

                    print(f"\n[DONE] 데이터 로드 완료:")
                    print(f"   - 삽입: {result['inserted']}개")
                    print(f"   - 업데이트: {result['updated']}개")
                    print(f"   - 건너뜀: {result['skipped']}개")
            except (EOFError, KeyboardInterrupt):
                print("\n[!] 대화형 입력을 건너뜁니다")
                pass
        else:
            print("[AUTO] 데이터가 이미 있으므로 재로드를 건너뜁니다")

    # 5. 검증
    print("\n[4/5] 최종 검증 중...")
    _, final_count = check_items_table(client)
    print(f"[OK] items 테이블: {final_count}개 레코드")

    # schema_version 확인
    if check_migration_status(client):
        result = client.table("schema_version").select("*").eq("version", 2).execute()
        if result.data:
            applied_at = result.data[0].get("applied_at", "unknown")
            print(f"[OK] Migration 002 적용됨 ({applied_at})")

    print("\n" + "="*70)
    print("[SUCCESS] 모든 설정 완료!")
    print("="*70)


if __name__ == "__main__":
    main()
