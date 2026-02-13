#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
크롤링된 26개 신규 아이템을 items_ko.json에 병합하는 스크립트
"""

import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import sys
import codecs

# Windows 콘솔 UTF-8 강제 설정 (한글 깨짐 방지)
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')



# 경로 설정
BASE_DIR = Path(__file__).parent.parent
ITEMS_KO_PATH = BASE_DIR / "src" / "titrack" / "data" / "items_ko.json"
CRAWLER_NEW_PATH = BASE_DIR / "output" / "crawler_new_71_items.json"
BACKUP_PATH = BASE_DIR / "output" / "items_ko_backup_20260212_v2.json"
REPORT_PATH = BASE_DIR / "docs" / "items_merge_report_20260212_v2.md"


def load_json(file_path):
    """JSON 파일 로드"""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, file_path, indent=2):
    """JSON 파일 저장 (정렬 및 들여쓰기)"""
    # ConfigBaseId 기준 오름차순 정렬
    sorted_data = {k: data[k] for k in sorted(data.keys(), key=int)}

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(sorted_data, f, ensure_ascii=False, indent=indent)


def validate_item(config_base_id, item_data):
    """아이템 데이터 검증"""
    errors = []

    # ConfigBaseId 검증 (정수 변환 가능 여부)
    try:
        int(config_base_id)
    except ValueError:
        errors.append(f"Invalid ConfigBaseId: {config_base_id}")

    # name 필드 검증
    if "name" not in item_data:
        errors.append(f"Missing 'name' field")
    elif not isinstance(item_data["name"], str) or not item_data["name"]:
        errors.append(f"Invalid 'name': {item_data.get('name')}")

    # type 필드 검증
    if "type" not in item_data:
        errors.append(f"Missing 'type' field")
    elif not isinstance(item_data["type"], str) or not item_data["type"]:
        errors.append(f"Invalid 'type': {item_data.get('type')}")

    # price 필드 검증
    if "price" not in item_data:
        errors.append(f"Missing 'price' field")
    elif not isinstance(item_data["price"], (int, float)):
        errors.append(f"Invalid 'price': {item_data.get('price')}")

    return errors


def get_type_stats(items_data):
    """카테고리별 통계 반환"""
    type_counts = defaultdict(int)
    for item in items_data.values():
        type_counts[item["type"]] += 1

    # 개수 기준 내림차순 정렬
    return dict(sorted(type_counts.items(), key=lambda x: x[1], reverse=True))


def main():
    print("=" * 80)
    print("아이템 데이터 병합 시작")
    print("=" * 80)

    # 1. 파일 로드
    print("\n[1/6] 데이터 로드 중...")
    items_ko = load_json(ITEMS_KO_PATH)
    crawler_new = load_json(CRAWLER_NEW_PATH)

    print(f"  - items_ko.json: {len(items_ko):,}개 아이템")
    print(f"  - crawler_new_71_items.json: {len(crawler_new):,}개 아이템")

    # 2. 백업 생성
    print("\n[2/6] 백업 생성 중...")
    save_json(items_ko, BACKUP_PATH)
    print(f"  [OK] 백업 저장: {BACKUP_PATH}")

    # 3. 데이터 검증
    print("\n[3/6] 데이터 검증 중...")
    validation_errors = {}
    duplicates = []

    for config_base_id, item_data in crawler_new.items():
        # 검증
        errors = validate_item(config_base_id, item_data)
        if errors:
            validation_errors[config_base_id] = errors

        # 중복 확인
        if config_base_id in items_ko:
            duplicates.append(config_base_id)

    if validation_errors:
        print(f"  [WARN] 검증 실패: {len(validation_errors)}개 아이템")
        for cid, errors in validation_errors.items():
            print(f"    - {cid}: {', '.join(errors)}")
    else:
        print("  [OK] 검증 통과: 모든 아이템 정상")

    if duplicates:
        print(f"  [WARN] 중복 발견: {len(duplicates)}개 ConfigBaseId")
        print(f"    {', '.join(duplicates)}")
    else:
        print("  [OK] 중복 없음")

    # 검증 실패 시 중단
    if validation_errors:
        print("\n[ERROR] 검증 오류로 인해 병합을 중단합니다.")
        return

    # 4. 병합 실행
    print("\n[4/6] 병합 실행 중...")
    added_items = []
    skipped_items = []

    for config_base_id, item_data in crawler_new.items():
        if config_base_id in items_ko:
            skipped_items.append(config_base_id)
        else:
            items_ko[config_base_id] = item_data
            added_items.append(config_base_id)

    print(f"  [OK] 추가된 아이템: {len(added_items)}개")
    print(f"  [SKIP] 스킵된 아이템 (중복): {len(skipped_items)}개")

    # 5. 저장
    print("\n[5/6] 병합 결과 저장 중...")
    save_json(items_ko, ITEMS_KO_PATH)
    print(f"  [OK] 업데이트된 items_ko.json 저장: {len(items_ko):,}개 아이템")

    # 6. 통계 및 보고서 생성
    print("\n[6/6] 병합 보고서 생성 중...")

    # 카테고리별 통계
    type_stats_before = get_type_stats(load_json(BACKUP_PATH))
    type_stats_after = get_type_stats(items_ko)

    # 추가된 아이템 상세
    added_details = []
    for cid in sorted(added_items, key=int):
        item = items_ko[cid]
        added_details.append({
            "config_base_id": cid,
            "name": item["name"],
            "type": item["type"],
            "price": item["price"]
        })

    # 보고서 작성
    report_lines = [
        "# 아이템 데이터 병합 보고서",
        "",
        f"**작업 일시**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**작업자**: Data Agent",
        "",
        "---",
        "",
        "## 1. 작업 요약",
        "",
        f"- **소스 파일**: `output/crawler_new_71_items.json` (26개 아이템)",
        f"- **대상 파일**: `src/titrack/data/items_ko.json`",
        f"- **백업 파일**: `output/items_ko_backup_20260212_v2.json`",
        "",
        "### 병합 전후 통계",
        "",
        f"- **병합 전**: {len(load_json(BACKUP_PATH)):,}개 아이템",
        f"- **병합 후**: {len(items_ko):,}개 아이템",
        f"- **추가됨**: {len(added_items)}개",
        f"- **스킵됨 (중복)**: {len(skipped_items)}개",
        "",
        "---",
        "",
        "## 2. 추가된 아이템 목록",
        "",
        "| ConfigBaseId | 이름 | 타입 | 가격 (FE) |",
        "|--------------|------|------|-----------|",
    ]

    for item in added_details:
        report_lines.append(
            f"| {item['config_base_id']} | {item['name']} | {item['type']} | {item['price']} |"
        )

    report_lines.extend([
        "",
        "---",
        "",
        "## 3. 카테고리별 분포 변화",
        "",
        "### 병합 전 (Top 20)",
        "",
        "| 카테고리 | 개수 |",
        "|----------|------|",
    ])

    for type_name, count in list(type_stats_before.items())[:20]:
        report_lines.append(f"| {type_name} | {count:,} |")

    report_lines.extend([
        "",
        "### 병합 후 (Top 20)",
        "",
        "| 카테고리 | 개수 | 변화 |",
        "|----------|------|------|",
    ])

    for type_name, count_after in list(type_stats_after.items())[:20]:
        count_before = type_stats_before.get(type_name, 0)
        delta = count_after - count_before
        delta_str = f"+{delta}" if delta > 0 else str(delta) if delta < 0 else "±0"
        report_lines.append(f"| {type_name} | {count_after:,} | {delta_str} |")

    report_lines.extend([
        "",
        "---",
        "",
        "## 4. 검증 결과",
        "",
        "### 데이터 검증",
        "",
        f"- **ConfigBaseId 형식**: [OK] 정상 (모두 정수로 변환 가능)",
        f"- **name 필드**: [OK] 정상 (모두 비어있지 않은 문자열)",
        f"- **type 필드**: [OK] 정상 (모두 비어있지 않은 문자열)",
        f"- **price 필드**: [OK] 정상 (모두 숫자 형식)",
        "",
        "### 중복 검사",
        "",
        f"- **중복된 ConfigBaseId**: {len(duplicates)}개",
    ])

    if duplicates:
        report_lines.append("")
        report_lines.append("중복된 아이템 (기존 데이터 유지):")
        for cid in duplicates:
            item = items_ko[cid]
            report_lines.append(f"  - {cid}: {item['name']} ({item['type']})")

    report_lines.extend([
        "",
        "---",
        "",
        "## 5. 파일 상태",
        "",
        f"- [OK] `src/titrack/data/items_ko.json` 업데이트 완료 ({len(items_ko):,}개)",
        f"- [OK] `output/items_ko_backup_20260212_v2.json` 백업 생성 완료",
        f"- [OK] `docs/items_merge_report_20260212_v2.md` 보고서 생성 완료",
        "",
        "---",
        "",
        f"*Generated by Data Agent - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        "",
    ])

    # 보고서 저장
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print(f"  [OK] 병합 보고서 저장: {REPORT_PATH}")

    # 최종 요약
    print("\n" + "=" * 80)
    print("병합 완료!")
    print("=" * 80)
    print(f"최종 통계:")
    print(f"  - 총 아이템: {len(items_ko):,}개")
    print(f"  - 추가됨: {len(added_items)}개")
    print(f"  - 스킵됨 (중복): {len(skipped_items)}개")
    print(f"\n상세 내용은 보고서를 확인하세요:")
    print(f"  {REPORT_PATH}")
    print("=" * 80)


if __name__ == "__main__":
    main()
