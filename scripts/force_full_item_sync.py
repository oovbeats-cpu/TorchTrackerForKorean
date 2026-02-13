#!/usr/bin/env python3
"""Supabase items 강제 전체 동기화

items_last_sync를 무시하고 Supabase items 테이블의 모든 아이템을 로컬 DB에 동기화합니다.
"""

import os
import sys
import sqlite3
import codecs
from pathlib import Path
from datetime import datetime

# Windows 콘솔 UTF-8 강제 설정 (한글 깨짐 방지)
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from supabase import create_client
except ImportError:
    print("Error: supabase package not installed")
    print("Install: pip install supabase")
    exit(1)


def get_local_db_path() -> Path:
    """로컬 DB 경로 가져오기"""
    portable_db = Path("data") / "tracker.db"
    if portable_db.exists():
        return portable_db

    localappdata = os.getenv("LOCALAPPDATA")
    if not localappdata:
        raise RuntimeError("LOCALAPPDATA not set")

    default_db = Path(localappdata) / "TITrack" / "tracker.db"
    if not default_db.exists():
        raise FileNotFoundError(f"Local DB not found: {default_db}")

    return default_db


def fetch_all_items_from_supabase(supabase):
    """Supabase에서 모든 아이템 가져오기 (since=NULL)"""
    print("\n[1/4] Supabase items 가져오기 (전체)...")

    try:
        # fetch_items_delta(p_since=NULL) → 모든 아이템
        result = supabase.rpc("fetch_items_delta", {"p_since": None}).execute()

        if not result.data:
            print("  [WARNING] Supabase에서 아이템을 가져오지 못했습니다")
            return []

        items = result.data
        print(f"  [OK] {len(items)}개 아이템 가져옴")

        # 샘플 출력
        if items:
            sample = items[0]
            print(f"  샘플: {sample.get('config_base_id')} - {sample.get('name_en')}")

        return items
    except Exception as e:
        print(f"  [ERROR] 에러: {e}")
        raise


def sync_items_to_local_db(db_path: Path, items: list):
    """로컬 DB items 테이블에 UPSERT"""
    print("\n[2/4] 로컬 DB에 동기화 중...")

    if not items:
        print("  [WARNING] 동기화할 아이템이 없습니다")
        return 0

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    batch_size = 100
    synced = 0

    for i in range(0, len(items), batch_size):
        batch = items[i:i+batch_size]

        for item in batch:
            config_base_id = item.get("config_base_id")
            name_en = item.get("name_en")
            name_cn = item.get("name_cn")
            type_cn = item.get("type_cn")
            icon_url = item.get("icon_url")

            # SQLite items 테이블에 UPSERT
            cursor.execute("""
                INSERT INTO items (config_base_id, name_en, name_cn, type_cn, icon_url)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(config_base_id) DO UPDATE SET
                    name_en = excluded.name_en,
                    name_cn = excluded.name_cn,
                    type_cn = excluded.type_cn,
                    icon_url = excluded.icon_url
            """, (config_base_id, name_en, name_cn, type_cn, icon_url))
            synced += 1

        conn.commit()
        print(f"  진행: {synced}/{len(items)} ({synced*100//len(items)}%)")

    conn.close()

    print(f"  [OK] {synced}개 아이템 동기화 완료")
    return synced


def update_items_last_sync(db_path: Path):
    """items_last_sync 설정 업데이트 (현재 시각)"""
    print("\n[3/4] items_last_sync 업데이트 중...")

    now = datetime.utcnow().isoformat() + "Z"

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO settings (key, value)
        VALUES ('items_last_sync', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (now,))

    conn.commit()
    conn.close()

    print(f"  [OK] items_last_sync = {now}")


def verify_sync(db_path: Path):
    """동기화 결과 검증"""
    print("\n[4/4] 검증 중...")

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # 총 개수
    cursor.execute("SELECT COUNT(*) FROM items")
    total_count = cursor.fetchone()[0]
    print(f"  총 아이템: {total_count}개")

    # name_en 채워진 개수
    cursor.execute("SELECT COUNT(*) FROM items WHERE name_en IS NOT NULL")
    name_en_count = cursor.fetchone()[0]
    print(f"  name_en 채워짐: {name_en_count}개 ({name_en_count*100//total_count if total_count > 0 else 0}%)")

    # icon_url 채워진 개수
    cursor.execute("SELECT COUNT(*) FROM items WHERE icon_url IS NOT NULL")
    icon_count = cursor.fetchone()[0]
    print(f"  icon_url 채워짐: {icon_count}개 ({icon_count*100//total_count if total_count > 0 else 0}%)")

    # items_last_sync
    cursor.execute("SELECT value FROM settings WHERE key = 'items_last_sync'")
    row = cursor.fetchone()
    if row:
        print(f"  items_last_sync: {row[0]}")
    else:
        print(f"  items_last_sync: NULL (설정 없음)")

    conn.close()


def main():
    print("=" * 80)
    print("TITrack - Supabase Items 강제 전체 동기화")
    print("=" * 80)

    # Supabase 연결
    supabase_url = os.getenv("TITRACK_SUPABASE_URL")
    supabase_key = os.getenv("TITRACK_SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        print("\n[ERROR] Supabase credentials 없음")
        print("   .env 파일에 TITRACK_SUPABASE_URL, TITRACK_SUPABASE_KEY 설정 필요")
        exit(1)

    supabase = create_client(supabase_url, supabase_key)
    print(f"\n[OK] Supabase 연결: {supabase_url}")

    # 로컬 DB 경로
    try:
        db_path = get_local_db_path()
        print(f"[OK] 로컬 DB: {db_path}")
    except Exception as e:
        print(f"\n[ERROR] 로컬 DB 없음: {e}")
        exit(1)

    # 동기화 실행
    try:
        items = fetch_all_items_from_supabase(supabase)

        if not items:
            print("\n[WARNING] 동기화할 아이템이 없습니다 (Supabase items 테이블이 비어있음)")
            exit(0)

        synced = sync_items_to_local_db(db_path, items)
        update_items_last_sync(db_path)
        verify_sync(db_path)

        print("\n" + "=" * 80)
        print(f"[완료] {synced}개 아이템 동기화 완료!")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERROR] 에러 발생: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
