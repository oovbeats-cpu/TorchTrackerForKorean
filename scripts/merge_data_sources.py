"""
데이터 소스 병합 스크립트
- ref/v의 누락된 2개 아이템을 items_ko.json에 추가
- 크롤링 결과의 유효한 2개 아이템 추가 (categories, structure_notes 제외)
"""

import json
from pathlib import Path
from typing import Dict, Any

# 경로 설정
BASE_DIR = Path(__file__).parent.parent
ITEMS_KO_PATH = BASE_DIR / "src" / "titrack" / "data" / "items_ko.json"
MISSING_ITEMS_PATH = BASE_DIR / "output" / "missing_items.json"
CRAWLER_NEW_PATH = BASE_DIR / "output" / "crawler_new_items.json"
BACKUP_PATH = BASE_DIR / "output" / "items_ko_backup.json"


def load_json(path: Path) -> Dict:
    """JSON 파일 로드"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any, indent: int = 2):
    """JSON 파일 저장"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


def merge_items(items_ko: Dict, missing_items: Dict, crawler_items: Dict) -> Dict:
    """
    데이터 병합
    - items_ko: 기존 데이터 (우선순위 최고)
    - missing_items: ref/v에서 누락된 2개
    - crawler_items: 크롤링 결과 (유효한 것만)
    """
    merged = items_ko.copy()
    added_count = 0

    # 1. ref/v의 누락 아이템 추가
    for config_id, item in missing_items.items():
        if config_id not in merged:
            merged[config_id] = item
            added_count += 1
            print(f"   [ADD] {config_id}: {item['name']} ({item['type']})")

    # 2. 크롤링 결과 중 유효한 아이템만 추가 (categories, structure_notes 제외)
    invalid_ids = {"categories", "structure_notes"}

    for config_id, item in crawler_items.items():
        if config_id in invalid_ids:
            print(f"   [SKIP] {config_id}: 메타데이터 (아이템 아님)")
            continue

        if config_id not in merged:
            merged[config_id] = {
                "name": item["name"],
                "type": item["type"],
                "price": item["price"]
            }
            added_count += 1
            print(f"   [ADD] {config_id}: {item['name']} ({item['type']}) - 크롤링 신규")

    return merged, added_count


def main():
    """메인 병합 실행"""
    print("[DATA MERGE] 데이터 소스 병합 시작...")

    # 1. 데이터 로드
    print("\n[1/4] 데이터 로드 중...")
    items_ko = load_json(ITEMS_KO_PATH)
    missing_items = load_json(MISSING_ITEMS_PATH)
    crawler_items = load_json(CRAWLER_NEW_PATH)

    print(f"   - items_ko.json: {len(items_ko):,}개")
    print(f"   - missing_items.json: {len(missing_items):,}개")
    print(f"   - crawler_new_items.json: {len(crawler_items):,}개 (유효: 2개)")

    # 2. 백업 생성
    print("\n[2/4] 기존 items_ko.json 백업 중...")
    save_json(BACKUP_PATH, items_ko)
    print(f"   [OK] 백업 저장: {BACKUP_PATH}")

    # 3. 병합
    print("\n[3/4] 데이터 병합 중...")
    merged, added_count = merge_items(items_ko, missing_items, crawler_items)

    print(f"\n   총 추가된 아이템: {added_count}개")
    print(f"   병합 후 총 개수: {len(merged):,}개")

    # 4. 저장
    print("\n[4/4] items_ko.json 업데이트 중...")
    save_json(ITEMS_KO_PATH, merged)
    print(f"   [OK] 저장 완료: {ITEMS_KO_PATH}")

    print("\n[DONE] 병합 완료!")
    print(f"\n요약:")
    print(f"   - 이전: {len(items_ko):,}개")
    print(f"   - 이후: {len(merged):,}개")
    print(f"   - 추가: {added_count}개")
    print(f"\n백업: {BACKUP_PATH}")


if __name__ == "__main__":
    main()
