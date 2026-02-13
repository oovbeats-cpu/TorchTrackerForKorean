"""
PriceHistory 시세 데이터를 Supabase price_history 테이블에 업로드하는 스크립트.

작업 절차:
1. PriceHistory/*.txt 파일 목록 가져오기 (YYYYMMDD.txt 형식)
2. 각 파일 파싱 (JSON.parse)
3. 날짜 추출 및 UTC 00:00:00 변환
4. 데이터 변환 (price > 0인 아이템만)
5. Supabase UPSERT (100개/배치)
6. 진행 상황 출력 및 검증

Usage:
    python scripts/upload_price_history.py

Note:
    이 스크립트는 service_role 키를 사용하여 RLS를 우회합니다.
    .env 파일에 TITRACK_SUPABASE_SERVICE_KEY를 설정하거나,
    실행 시 환경 변수로 제공하세요.
"""

import json
import os
import sys
import codecs
from datetime import datetime, timezone
from pathlib import Path

# Windows 콘솔 UTF-8 강제 설정 (한글 출력 지원)
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# Load dotenv
try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except ImportError:
    pass

# Supabase is required for this script
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("[ERROR] Supabase SDK not available. Install with: pip install supabase")
    sys.exit(1)


def parse_date_from_filename(filename: str) -> datetime:
    """
    파일명에서 날짜 추출 (YYYYMMDD.txt → YYYY-MM-DD 00:00:00 UTC).

    Args:
        filename: 파일명 (예: "20260121.txt")

    Returns:
        datetime 객체 (UTC 00:00:00)
    """
    # Remove .txt extension
    date_str = filename.replace('.txt', '')

    # Parse YYYYMMDD
    year = int(date_str[:4])
    month = int(date_str[4:6])
    day = int(date_str[6:8])

    return datetime(year, month, day, 0, 0, 0, tzinfo=timezone.utc)


def load_price_file(file_path: Path) -> dict:
    """
    PriceHistory txt 파일 로드 (JSON 형식).

    Args:
        file_path: 파일 경로

    Returns:
        dict[config_base_id, item_data]
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load {file_path.name}: {e}")
        return {}


def convert_to_price_history_rows(
    data: dict,
    hour_bucket: datetime,
    season_id: int = 0
) -> list[dict]:
    """
    JSON 데이터를 price_history 테이블 행으로 변환.

    Args:
        data: items_ko.json 형식 데이터
        hour_bucket: 날짜 (UTC 00:00:00)
        season_id: 시즌 ID (기본값: 0)

    Returns:
        price_history 행 목록 (price > 0인 것만)
    """
    rows = []

    for config_base_id_str, item_data in data.items():
        config_base_id = int(config_base_id_str)
        price = item_data.get('price', 0)

        # Skip items with price = 0 (untradeable or no data)
        if price <= 0:
            continue

        rows.append({
            'config_base_id': config_base_id,
            'season_id': season_id,
            'hour_bucket': hour_bucket.isoformat(),
            'price_fe_median': price,
            'price_fe_p10': price,  # 단일 값이므로 동일
            'price_fe_p90': price,  # 단일 값이므로 동일
            'submission_count': 1,
            'unique_devices': 1,
        })

    return rows


def upload_price_history(client: Client, rows: list[dict], batch_size: int = 100) -> tuple[int, int]:
    """
    price_history 데이터를 Supabase에 UPSERT.

    Args:
        client: Supabase 클라이언트
        rows: 업로드할 행 목록
        batch_size: 배치 크기

    Returns:
        (성공 개수, 실패 개수)
    """
    success_count = 0
    error_count = 0

    # Process in batches
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(rows) + batch_size - 1) // batch_size

        try:
            # UPSERT into price_history table
            # ON CONFLICT (config_base_id, season_id, hour_bucket) DO UPDATE
            result = client.table('price_history').upsert(batch).execute()

            success_count += len(batch)
            print(f"[OK] Batch {batch_num}/{total_batches}: {len(batch)} rows uploaded")

        except Exception as e:
            error_count += len(batch)
            print(f"[ERROR] Batch {batch_num}/{total_batches} failed: {e}")

    return success_count, error_count


def verify_upload(client: Client, season_id: int = 0):
    """
    업로드 검증 쿼리 실행.

    Args:
        client: Supabase 클라이언트
        season_id: 시즌 ID
    """
    try:
        # Total rows
        result = (
            client.table('price_history')
            .select('*', count='exact')
            .eq('season_id', season_id)
            .execute()
        )
        total_rows = result.count

        # Date range
        result_min = (
            client.table('price_history')
            .select('hour_bucket')
            .eq('season_id', season_id)
            .order('hour_bucket', desc=False)
            .limit(1)
            .execute()
        )

        result_max = (
            client.table('price_history')
            .select('hour_bucket')
            .eq('season_id', season_id)
            .order('hour_bucket', desc=True)
            .limit(1)
            .execute()
        )

        min_date = result_min.data[0]['hour_bucket'] if result_min.data else 'N/A'
        max_date = result_max.data[0]['hour_bucket'] if result_max.data else 'N/A'

        print("\n=== Verification ===")
        print(f"Total rows: {total_rows}")
        print(f"Date range: {min_date} ~ {max_date}")

    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")


def main():
    print("=== PriceHistory Upload Script ===\n")

    # 1. Locate PriceHistory folder
    price_history_dir = project_root / "PriceHistory"
    if not price_history_dir.exists():
        print(f"[ERROR] PriceHistory folder not found: {price_history_dir}")
        return 1

    # 2. Find all .txt files
    txt_files = sorted(price_history_dir.glob("*.txt"))
    if not txt_files:
        print(f"[ERROR] No .txt files found in {price_history_dir}")
        return 1

    print(f"Found {len(txt_files)} price history files\n")

    # 3. Connect to Supabase with service_role key (bypasses RLS)
    # Try service_role key first (for admin operations like this)
    supabase_url = os.getenv("TITRACK_SUPABASE_URL")
    service_key = os.getenv("TITRACK_SUPABASE_SERVICE_KEY")

    # Fallback to public key if service_role not available
    if not service_key:
        print("[WARNING] TITRACK_SUPABASE_SERVICE_KEY not found in .env")
        service_key = os.getenv("TITRACK_SUPABASE_KEY")
        if service_key:
            print("[WARNING] Using TITRACK_SUPABASE_KEY (may fail due to RLS)")
        else:
            print("[ERROR] No Supabase key found in environment")
            return 1

    if not supabase_url:
        print("[ERROR] TITRACK_SUPABASE_URL not found in .env")
        return 1

    try:
        client = create_client(supabase_url, service_key)
        print("[OK] Connected to Supabase\n")
    except Exception as e:
        print(f"[ERROR] Failed to connect to Supabase: {e}")
        return 1

    # 4. Process each file
    all_rows = []
    skipped_files = 0

    for file_path in txt_files:
        filename = file_path.name

        try:
            # Parse date from filename
            hour_bucket = parse_date_from_filename(filename)

            # Load file
            data = load_price_file(file_path)
            if not data:
                skipped_files += 1
                continue

            # Convert to rows (price > 0 only)
            rows = convert_to_price_history_rows(data, hour_bucket)

            print(f"[{filename}] Total: {len(data)}, Price > 0: {len(rows)}, Date: {hour_bucket.date()}")

            all_rows.extend(rows)

        except Exception as e:
            print(f"[ERROR] Failed to process {filename}: {e}")
            skipped_files += 1

    print(f"\n=== Summary ===")
    print(f"Files processed: {len(txt_files) - skipped_files}/{len(txt_files)}")
    print(f"Total rows to upload: {len(all_rows)}")

    if not all_rows:
        print("[WARNING] No data to upload")
        return 0

    # 5. Upload to Supabase
    print("\n=== Uploading to Supabase ===")
    success, errors = upload_price_history(client, all_rows)

    print(f"\n=== Upload Complete ===")
    print(f"Success: {success} rows")
    print(f"Errors: {errors} rows")

    # 6. Verify
    if success > 0:
        verify_upload(client)

    return 0 if errors == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
