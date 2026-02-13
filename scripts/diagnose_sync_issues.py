#!/usr/bin/env python3
"""Supabase 동기화 문제 진단 스크립트

문제 1: 아이템 동기화 0개
문제 2: 가격 데이터 로드 (20260212.txt)
"""

import os
import sys
import sqlite3
import json
from pathlib import Path
from datetime import datetime

# Windows 콘솔 UTF-8 강제 설정 (한글 깨짐 방지)
if sys.platform == 'win32':
    import codecs
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


def check_local_db(db_path: Path):
    """로컬 DB 상태 확인"""
    print("\n" + "=" * 80)
    print("[1] 로컬 DB 상태")
    print("=" * 80)

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # items 테이블
    cursor.execute("SELECT COUNT(*) FROM items")
    items_count = cursor.fetchone()[0]
    print(f"\n  Items 테이블: {items_count}개")

    # items 샘플
    cursor.execute("SELECT config_base_id, name_en, icon_url FROM items LIMIT 3")
    samples = cursor.fetchall()
    print(f"  샘플 (처음 3개):")
    for config_id, name, icon in samples:
        print(f"    {config_id}: {name} | icon: {'있음' if icon else 'NULL'}")

    # items_last_sync 설정
    cursor.execute("SELECT value FROM settings WHERE key = 'items_last_sync'")
    row = cursor.fetchone()
    if row:
        print(f"\n  items_last_sync: {row[0]}")
    else:
        print(f"\n  items_last_sync: 설정 없음 (NULL)")

    # prices 테이블 (exchange)
    cursor.execute("SELECT COUNT(*) FROM prices WHERE source = 'exchange'")
    prices_count = cursor.fetchone()[0]
    print(f"\n  Exchange 가격: {prices_count}개")

    conn.close()


def check_supabase_state(supabase):
    """Supabase 상태 확인"""
    print("\n" + "=" * 80)
    print("[2] Supabase 상태")
    print("=" * 80)

    # items 테이블
    result = supabase.table("items").select("*", count="exact").limit(0).execute()
    items_count = result.count
    print(f"\n  Items 테이블: {items_count}개")

    # items updated_at 범위
    result = supabase.table("items").select("updated_at").order("updated_at").limit(1).execute()
    if result.data:
        oldest = result.data[0]["updated_at"]
        print(f"  가장 오래된 updated_at: {oldest}")

    result = supabase.table("items").select("updated_at").order("updated_at", desc=True).limit(1).execute()
    if result.data:
        newest = result.data[0]["updated_at"]
        print(f"  가장 최근 updated_at: {newest}")

    # aggregated_prices 테이블
    try:
        result = supabase.table("aggregated_prices").select("*", count="exact").limit(0).execute()
        prices_count = result.count
        print(f"\n  Aggregated Prices 테이블: {prices_count}개")
    except Exception as e:
        print(f"\n  Aggregated Prices 테이블: 에러 - {e}")


def check_20260212_file():
    """20260212.txt 파일 확인"""
    print("\n" + "=" * 80)
    print("[3] ref/v/20260212.txt 파일")
    print("=" * 80)

    file_path = Path("ref") / "v" / "20260212.txt"
    if not file_path.exists():
        print(f"\n  [ERROR] 파일 없음: {file_path}")
        return None

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"\n  [OK] 파일 존재: {len(data)}개 아이템")

    # 샘플
    sample_keys = list(data.keys())[:3]
    print(f"  샘플 (처음 3개):")
    for key in sample_keys:
        item = data[key]
        print(f"    {key}: {item['name']} ({item['type']}) - {item['price']} FE")

    return data


def diagnose_sync_issue(supabase, db_path: Path):
    """동기화 0개 문제 진단"""
    print("\n" + "=" * 80)
    print("[4] 아이템 동기화 0개 문제 진단")
    print("=" * 80)

    # 1. items_last_sync 읽기
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = 'items_last_sync'")
    row = cursor.fetchone()
    conn.close()

    if row:
        items_last_sync = row[0]
        print(f"\n  로컬 items_last_sync: {items_last_sync}")

        # 2. Supabase에서 since 이후 아이템 개수 확인
        try:
            result = supabase.rpc("fetch_items_delta", {"p_since": items_last_sync}).execute()
            delta_count = len(result.data) if result.data else 0
            print(f"  Supabase fetch_items_delta(since={items_last_sync}): {delta_count}개")

            if delta_count == 0:
                print(f"\n  [ERROR] 문제 발견: items_last_sync 이후 업데이트된 아이템이 없음")
                print(f"     → items_last_sync가 Supabase updated_at보다 최신이거나")
                print(f"     → Supabase items의 updated_at이 과거 날짜일 수 있음")
                print(f"\n  해결책: items_last_sync를 NULL로 초기화하거나")
                print(f"           fetch_items_delta(since=NULL)로 전체 동기화")
        except Exception as e:
            print(f"\n  [WARNING] fetch_items_delta() 호출 실패: {e}")
            print(f"     → RPC 함수가 존재하지 않거나 권한 문제일 수 있음")
    else:
        print(f"\n  [OK] items_last_sync가 NULL → 전체 동기화 예정")


def main():
    print("=" * 80)
    print("TITrack - Supabase 동기화 문제 진단")
    print("=" * 80)

    # Supabase 연결
    supabase_url = os.getenv("TITRACK_SUPABASE_URL")
    supabase_key = os.getenv("TITRACK_SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        print("\n[ERROR] Supabase credentials 없음")
        print("   .env 파일에 TITRACK_SUPABASE_URL, TITRACK_SUPABASE_KEY 설정 필요")
        exit(1)

    supabase = create_client(supabase_url, supabase_key)
    print(f"\n[OK] Supabase 연결 성공: {supabase_url}")

    # 로컬 DB 경로
    try:
        db_path = get_local_db_path()
        print(f"[OK] 로컬 DB 경로: {db_path}")
    except Exception as e:
        print(f"\n[ERROR] 로컬 DB 없음: {e}")
        exit(1)

    # 진단 실행
    check_local_db(db_path)
    check_supabase_state(supabase)
    check_20260212_file()
    diagnose_sync_issue(supabase, db_path)

    print("\n" + "=" * 80)
    print("[완료] 진단 완료")
    print("=" * 80)
    print("\n다음 단계:")
    print("  1. scripts/force_full_item_sync.py 실행 (아이템 전체 동기화)")
    print("  2. scripts/load_prices_from_20260212.py 실행 (가격 데이터 로드)")
    print()


if __name__ == "__main__":
    main()
