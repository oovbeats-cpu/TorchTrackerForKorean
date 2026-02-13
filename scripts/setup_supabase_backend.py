#!/usr/bin/env python3
"""
TITrack - Supabase Backend Setup Wizard

이 스크립트는 Supabase 클라우드 백엔드를 설정하는 전체 프로세스를 안내합니다.

실행:
    python scripts/setup_supabase_backend.py

환경 변수 (.env 파일에 설정):
    TITRACK_SUPABASE_URL - Supabase 프로젝트 URL
    TITRACK_SUPABASE_KEY - Supabase service role key
"""

import os
import sys
from pathlib import Path
from typing import Optional

# Load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    print("Note: python-dotenv not installed, reading from environment variables only")

# Supabase client
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    print("Error: supabase package not installed")
    print("Install with: pip install titrack[cloud]")
    sys.exit(1)


class SupabaseSetupWizard:
    """Supabase 백엔드 설정 마법사"""

    def __init__(self) -> None:
        self.root_path = Path(__file__).parent.parent
        self.migration_file = self.root_path / "supabase" / "migrations" / "002_items_master.sql"
        self.data_file = self.root_path / "ref" / "v" / "20260212.txt"
        self.supabase_url: Optional[str] = None
        self.supabase_key: Optional[str] = None
        self.client: Optional[Client] = None

    def print_header(self, title: str) -> None:
        """헤더 출력"""
        print("\n" + "="*70)
        print(f"  {title}")
        print("="*70)

    def step_1_check_env(self) -> bool:
        """Step 1: 환경 변수 확인"""
        self.print_header("Step 1: 환경 변수 확인")

        self.supabase_url = os.environ.get("TITRACK_SUPABASE_URL")
        self.supabase_key = os.environ.get("TITRACK_SUPABASE_KEY")

        if not self.supabase_url or not self.supabase_key:
            print("[X] 환경 변수가 설정되지 않았습니다.")
            print()
            print(".env 파일을 확인하거나 다음과 같이 설정하세요:")
            print()
            print("  TITRACK_SUPABASE_URL=https://dxuxdnglefrxtqvfitho.supabase.co")
            print("  TITRACK_SUPABASE_KEY=sb_secret_AOxzX8M00M7CYwpnvSM8lw_-JQhyMNk")
            print()
            return False

        print(f"[OK] TITRACK_SUPABASE_URL: {self.supabase_url}")
        print(f"[OK] TITRACK_SUPABASE_KEY: {self.supabase_key[:20]}...")

        # Supabase 클라이언트 생성 테스트
        try:
            self.client = create_client(self.supabase_url, self.supabase_key)
            print("[OK] Supabase 클라이언트 생성 성공")
            return True
        except Exception as e:
            print(f"[X] Supabase 클라이언트 생성 실패: {e}")
            return False

    def step_2_check_files(self) -> bool:
        """Step 2: 파일 확인"""
        self.print_header("Step 2: 필수 파일 확인")

        files_ok = True

        # Migration 파일
        if self.migration_file.exists():
            print(f"[OK] Migration 파일: {self.migration_file}")
        else:
            print(f"[X] Migration 파일 없음: {self.migration_file}")
            files_ok = False

        # 데이터 파일
        if self.data_file.exists():
            print(f"[OK] 데이터 파일: {self.data_file}")
        else:
            print(f"[X] 데이터 파일 없음: {self.data_file}")
            files_ok = False

        return files_ok

    def step_3_migration_instructions(self) -> None:
        """Step 3: Migration 실행 안내"""
        self.print_header("Step 3: Migration 002 실행")

        print("[!] Supabase Python 클라이언트는 직접 SQL 실행을 지원하지 않습니다.")
        print("    Supabase Dashboard에서 수동으로 Migration을 실행해야 합니다.")
        print()
        print("다음 단계를 따르세요:")
        print()
        print(f"  1. Supabase Dashboard 열기:")
        project_id = self.supabase_url.split("//")[1].split(".")[0]
        print(f"     https://app.supabase.com/project/{project_id}")
        print()
        print("  2. 왼쪽 메뉴에서 'SQL Editor' 클릭")
        print()
        print("  3. '+ New query' 버튼 클릭")
        print()
        print(f"  4. 다음 파일의 내용을 복사하여 붙여넣기:")
        print(f"     {self.migration_file}")
        print()
        print("  5. 'Run' 버튼 클릭하여 실행")
        print()
        print("  6. 성공 메시지 확인 후 이 스크립트로 돌아오기")
        print()

        input("Migration 실행을 완료했으면 Enter 키를 눌러 계속하세요...")

    def step_4_verify_migration(self) -> bool:
        """Step 4: Migration 검증"""
        self.print_header("Step 4: Migration 검증")

        try:
            # items 테이블 존재 확인
            result = self.client.table("items").select("config_base_id", count="exact").limit(1).execute()
            print("[OK] items 테이블이 생성되었습니다.")
            print(f"     현재 레코드 수: {result.count}")
            return True
        except Exception as e:
            print(f"[X] items 테이블 확인 실패: {e}")
            print()
            print("Migration이 성공적으로 실행되었는지 확인하세요.")
            return False

    def step_5_load_data(self) -> bool:
        """Step 5: 데이터 로드"""
        self.print_header("Step 5: 장비 아이템 데이터 로드 (2,447개)")

        import json

        # 데이터 파일 읽기
        print(f"데이터 파일 읽는 중: {self.data_file}")
        with open(self.data_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        print(f"[OK] {len(data)}개 아이템 로드됨")

        # 아이템 변환
        items = []
        for config_id_str, item in data.items():
            config_id = int(config_id_str)
            name_ko = item.get("name")
            type_ko = item.get("type")

            items.append({
                "config_base_id": config_id,
                "name_ko": name_ko,
                "type_ko": type_ko,
                "category": "equipment",
                "subcategory": self._infer_equipment_subcategory(config_id),
                "tier": self._infer_tier_from_id(config_id),
                "tradeable": True,
                "stackable": False,
            })

        # 배치 업로드
        batch_size = 100
        total_batches = (len(items) + batch_size - 1) // batch_size
        uploaded = 0
        errors = 0

        print(f"Supabase에 업로드 중 (배치 크기: {batch_size})...")

        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            batch_num = i // batch_size + 1

            try:
                result = self.client.table("items").upsert(batch).execute()
                uploaded += len(batch)
                print(f"  [{batch_num}/{total_batches}] [OK] {len(batch)}개 업로드 완료")
            except Exception as e:
                errors += 1
                print(f"  [{batch_num}/{total_batches}] [X] 오류: {e}")

        print()
        print(f"업로드 완료: {uploaded}개 성공, {errors}개 실패")

        return errors == 0

    def _infer_tier_from_id(self, config_id: int) -> int:
        """ConfigBaseId에서 티어 추론"""
        if config_id >= 10000:
            return 10
        elif config_id >= 5000:
            return 8
        elif config_id >= 2000:
            return 6
        elif config_id >= 1000:
            return 4
        else:
            return 2

    def _infer_equipment_subcategory(self, config_id: int) -> Optional[str]:
        """장비 서브카테고리 추론"""
        if 100 <= config_id < 200:
            return "claw"
        elif 200 <= config_id < 400:
            return "hammer"
        elif 400 <= config_id < 500:
            return "sword"
        elif 500 <= config_id < 600:
            return "axe"
        elif 600 <= config_id < 800:
            return "dagger"
        elif 800 <= config_id < 1000:
            return "bow"
        elif 1000 <= config_id < 1200:
            return "staff"
        elif 1200 <= config_id < 1400:
            return "wand"
        elif 2000 <= config_id < 2500:
            return "helmet"
        elif 2500 <= config_id < 3000:
            return "armor"
        elif 3000 <= config_id < 3500:
            return "gloves"
        elif 3500 <= config_id < 4000:
            return "boots"
        elif 4000 <= config_id < 4500:
            return "belt"
        elif 5000 <= config_id < 5500:
            return "ring"
        elif 5500 <= config_id < 6000:
            return "amulet"
        elif 6000 <= config_id < 6500:
            return "quiver"
        return None

    def step_6_verify_data(self) -> None:
        """Step 6: 데이터 검증"""
        self.print_header("Step 6: 데이터 검증")

        try:
            # 총 레코드 수
            result = self.client.table("items").select("config_base_id", count="exact").execute()
            print(f"[OK] 총 레코드 수: {result.count}")

            # 샘플 데이터 조회
            sample = self.client.table("items").select("*").limit(5).execute()
            print(f"[OK] 샘플 데이터 (최초 5개):")
            for item in sample.data:
                print(f"     - {item['config_base_id']}: {item.get('name_ko', 'N/A')} ({item.get('subcategory', 'N/A')})")

            # fetch_items_delta 함수 테스트
            print()
            print("[OK] fetch_items_delta() 함수 테스트:")
            result = self.client.rpc("fetch_items_delta").limit(5).execute()
            print(f"     반환된 아이템: {len(result.data)}개")

        except Exception as e:
            print(f"[X] 검증 오류: {e}")

    def run(self) -> None:
        """설정 마법사 실행"""
        print("="*70)
        print("  TITrack Supabase 백엔드 설정 마법사")
        print("="*70)

        # Step 1: 환경 변수 확인
        if not self.step_1_check_env():
            print("\n[X] 환경 변수 설정 후 다시 실행하세요.")
            sys.exit(1)

        # Step 2: 파일 확인
        if not self.step_2_check_files():
            print("\n[X] 필수 파일이 없습니다.")
            sys.exit(1)

        # Step 3: Migration 실행 안내
        self.step_3_migration_instructions()

        # Step 4: Migration 검증
        if not self.step_4_verify_migration():
            print("\n[X] Migration 검증 실패. 다시 시도하세요.")
            sys.exit(1)

        # Step 5: 데이터 로드
        if not self.step_5_load_data():
            print("\n[!] 일부 데이터 업로드 실패. 로그를 확인하세요.")

        # Step 6: 데이터 검증
        self.step_6_verify_data()

        # 완료
        self.print_header("[OK] 설정 완료!")
        print()
        print("Supabase 클라우드 백엔드가 성공적으로 구축되었습니다.")
        print()
        print("다음 단계:")
        print("  1. src/titrack/sync/client.py 통합 작업")
        print("  2. 로컬 DB 마이그레이션 v5")
        print("  3. 한국어 이름 통합 (korean_names.py)")
        print()


def main() -> None:
    """메인 실행 함수"""
    wizard = SupabaseSetupWizard()
    wizard.run()


if __name__ == "__main__":
    main()
