"""
데이터 소스 비교 분석 스크립트
- ref/v/full_table.json (참고 데이터)
- src/titrack/data/items_ko.json (현재 TITrack)
- output/crawler*.json (크롤링 결과)
"""

import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, Set, List, Any

# 경로 설정
BASE_DIR = Path(__file__).parent.parent
REF_PATH = BASE_DIR / "ref" / "v" / "full_table.json"
ITEMS_KO_PATH = BASE_DIR / "src" / "titrack" / "data" / "items_ko.json"
OUTPUT_DIR = BASE_DIR / "output"
DOCS_DIR = BASE_DIR / "docs"


def load_json(path: Path) -> Dict:
    """JSON 파일 로드"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any, indent: int = 2):
    """JSON 파일 저장"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


def analyze_ref_data(ref_data: Dict) -> Dict[str, Any]:
    """ref/v/full_table.json 분석"""
    result = {
        "total_count": len(ref_data),
        "config_ids": set(ref_data.keys()),
        "categories": defaultdict(int),
        "items": {}
    }

    for config_id, item in ref_data.items():
        category = item.get("type", "Unknown")
        result["categories"][category] += 1
        result["items"][config_id] = {
            "name": item.get("name", ""),
            "type": item.get("type", ""),
            "price": item.get("price", 0)
        }

    return result


def analyze_items_ko(items_ko: Dict) -> Dict[str, Any]:
    """items_ko.json 분석"""
    result = {
        "total_count": len(items_ko),
        "config_ids": set(items_ko.keys()),
        "categories": defaultdict(int),
        "items": {}
    }

    for config_id, item in items_ko.items():
        category = item.get("type", "Unknown")
        result["categories"][category] += 1
        result["items"][config_id] = {
            "name": item.get("name", ""),
            "type": item.get("type", ""),
            "price": item.get("price", 0)
        }

    return result


def analyze_crawler_data(output_dir: Path) -> Dict[str, Any]:
    """크롤링 결과 분석 (모든 crawler*.json 병합)"""
    result = {
        "total_count": 0,
        "config_ids": set(),
        "categories": defaultdict(int),
        "items": {},
        "files": []
    }

    crawler_files = list(output_dir.glob("crawler*.json"))

    for crawler_file in crawler_files:
        try:
            crawler_data = load_json(crawler_file)
            result["files"].append(crawler_file.name)

            # items_ko_format 키가 있으면 사용, 없으면 전체 데이터 사용
            if isinstance(crawler_data, dict):
                if "items_ko_format" in crawler_data:
                    items_data = crawler_data["items_ko_format"]
                elif "items" in crawler_data:
                    items_data = crawler_data["items"]
                else:
                    items_data = crawler_data
            else:
                continue  # 딕셔너리가 아니면 스킵

            for config_id, item in items_data.items():
                # item이 딕셔너리가 아니면 스킵 (숫자나 다른 타입일 수 있음)
                if not isinstance(item, dict):
                    continue

                if config_id not in result["items"]:  # 중복 방지
                    result["config_ids"].add(config_id)
                    category = item.get("type", "Unknown")
                    result["categories"][category] += 1
                    result["items"][config_id] = {
                        "name": item.get("name", ""),
                        "type": item.get("type", ""),
                        "price": item.get("price", 0),
                        "source_file": crawler_file.name
                    }
        except Exception as e:
            print(f"   [WARNING] {crawler_file.name} 파싱 실패: {e}")
            continue

    result["total_count"] = len(result["items"])
    return result


def compare_data_sources(ref_analysis: Dict, items_ko_analysis: Dict, crawler_analysis: Dict) -> Dict[str, Any]:
    """데이터 소스 간 비교"""
    ref_ids = ref_analysis["config_ids"]
    items_ko_ids = items_ko_analysis["config_ids"]
    crawler_ids = crawler_analysis["config_ids"]

    comparison = {
        "missing_in_items_ko": sorted(list(ref_ids - items_ko_ids)),  # ref에 있지만 items_ko에 없음
        "missing_in_ref": sorted(list(items_ko_ids - ref_ids)),  # items_ko에 있지만 ref에 없음
        "common_ids": sorted(list(ref_ids & items_ko_ids)),  # 양쪽 모두 존재
        "crawler_new_ids": sorted(list(crawler_ids - items_ko_ids)),  # 크롤링으로 새로 발견된 ID
        "name_mismatches": [],  # 같은 ID, 다른 이름
        "category_mismatches": []  # 같은 ID, 다른 카테고리
    }

    # 공통 ID에서 이름/카테고리 불일치 검사
    for config_id in comparison["common_ids"]:
        ref_item = ref_analysis["items"][config_id]
        ko_item = items_ko_analysis["items"][config_id]

        if ref_item["name"] != ko_item["name"]:
            comparison["name_mismatches"].append({
                "config_id": config_id,
                "ref_name": ref_item["name"],
                "ko_name": ko_item["name"]
            })

        if ref_item["type"] != ko_item["type"]:
            comparison["category_mismatches"].append({
                "config_id": config_id,
                "ref_type": ref_item["type"],
                "ko_type": ko_item["type"]
            })

    return comparison


def generate_report(ref_analysis: Dict, items_ko_analysis: Dict, crawler_analysis: Dict, comparison: Dict) -> str:
    """마크다운 보고서 생성"""
    report = f"""# 데이터 소스 비교 분석 보고서

> 생성 시간: {Path(__file__).stat().st_mtime}

---

## 1. 데이터 소스 개요

### 소스 1: ref/v/full_table.json (참고 데이터)
- **총 개수**: {ref_analysis['total_count']:,}개
- **카테고리 분포**:
"""

    for category, count in sorted(ref_analysis["categories"].items(), key=lambda x: x[1], reverse=True):
        report += f"  - {category}: {count:,}개\n"

    report += f"""
### 소스 2: src/titrack/data/items_ko.json (현재 TITrack)
- **총 개수**: {items_ko_analysis['total_count']:,}개
- **카테고리 분포** (상위 10개):
"""

    top_categories = sorted(items_ko_analysis["categories"].items(), key=lambda x: x[1], reverse=True)[:10]
    for category, count in top_categories:
        report += f"  - {category}: {count:,}개\n"

    report += f"""
### 소스 3: output/crawler*.json (크롤링 결과)
- **총 개수**: {crawler_analysis['total_count']:,}개
- **파일 목록**: {', '.join(crawler_analysis['files'])}
- **카테고리 분포**:
"""

    for category, count in sorted(crawler_analysis["categories"].items(), key=lambda x: x[1], reverse=True):
        report += f"  - {category}: {count:,}개\n"

    report += f"""

---

## 2. ConfigBaseId 중복/누락 분석

### 2.1 ref/v에는 있지만 items_ko.json에 없는 ID
- **개수**: {len(comparison['missing_in_items_ko']):,}개
- **첫 10개 예시**: {', '.join(comparison['missing_in_items_ko'][:10])}

### 2.2 items_ko.json에는 있지만 ref/v에 없는 ID
- **개수**: {len(comparison['missing_in_ref']):,}개
- **첫 10개 예시**: {', '.join(comparison['missing_in_ref'][:10])}

### 2.3 양쪽 모두 존재하는 ID
- **개수**: {len(comparison['common_ids']):,}개

### 2.4 크롤링으로 새로 발견된 ID
- **개수**: {len(comparison['crawler_new_ids']):,}개
- **ID 목록**: {', '.join(comparison['crawler_new_ids'][:20])}{'...' if len(comparison['crawler_new_ids']) > 20 else ''}

---

## 3. 데이터 품질 검증

### 3.1 이름 불일치 (같은 ID, 다른 이름)
- **개수**: {len(comparison['name_mismatches']):,}개

"""

    if comparison['name_mismatches']:
        report += "| ConfigBaseId | ref/v 이름 | items_ko 이름 |\n"
        report += "|--------------|------------|---------------|\n"
        for mismatch in comparison['name_mismatches'][:20]:  # 첫 20개만
            report += f"| {mismatch['config_id']} | {mismatch['ref_name']} | {mismatch['ko_name']} |\n"

        if len(comparison['name_mismatches']) > 20:
            report += f"\n*(총 {len(comparison['name_mismatches'])}개 중 20개만 표시)*\n"
    else:
        report += "*이름 불일치 없음*\n"

    report += f"""
### 3.2 카테고리 불일치 (같은 ID, 다른 타입)
- **개수**: {len(comparison['category_mismatches']):,}개

"""

    if comparison['category_mismatches']:
        report += "| ConfigBaseId | ref/v 타입 | items_ko 타입 |\n"
        report += "|--------------|------------|---------------|\n"
        for mismatch in comparison['category_mismatches'][:20]:
            report += f"| {mismatch['config_id']} | {mismatch['ref_type']} | {mismatch['ko_type']} |\n"

        if len(comparison['category_mismatches']) > 20:
            report += f"\n*(총 {len(comparison['category_mismatches'])}개 중 20개만 표시)*\n"
    else:
        report += "*카테고리 불일치 없음*\n"

    report += """

---

## 4. 통합 전략 제안

### 4.1 현황 분석
"""

    missing_count = len(comparison['missing_in_items_ko'])
    extra_count = len(comparison['missing_in_ref'])

    report += f"""
- ref/v에 있는 장비 데이터: **{ref_analysis['total_count']:,}개**
- items_ko.json의 현재 장비 데이터: **{items_ko_analysis['categories'].get('장비', 0):,}개**
- **누락된 장비**: **{missing_count:,}개**
- items_ko.json에만 있는 아이템: **{extra_count:,}개** (비장비 아이템)

### 4.2 통합 권장사항

#### 옵션 A: ref/v 데이터를 items_ko.json에 병합 (권장)
1. **장점**:
   - ref/v의 {missing_count:,}개 장비 데이터 추가
   - 기존 items_ko.json의 비장비 데이터({extra_count:,}개) 유지
   - 총 **{ref_analysis['total_count'] + extra_count:,}개** 아이템 확보

2. **작업 방법**:
   ```python
   # missing_in_items_ko ID들을 ref/v에서 가져와 items_ko.json에 추가
   # 기존 items_ko.json 데이터는 우선순위 유지 (덮어쓰지 않음)
   ```

3. **병합 우선순위**:
   - 기존 items_ko.json 데이터 우선 (수동 번역/검증된 데이터)
   - ref/v 데이터는 누락된 ID만 추가
   - 크롤링 데이터는 검증 후 수동 추가

#### 옵션 B: 크롤링 결과 우선 통합
1. **장점**:
   - 최신 게임 데이터 반영
   - 새로 발견된 {len(comparison['crawler_new_ids']):,}개 아이템 추가

2. **단점**:
   - 크롤링 데이터 품질 검증 필요
   - 번역 일관성 확인 필요

### 4.3 최종 추천

**2단계 통합 전략**:
1. **1단계**: ref/v의 누락된 {missing_count:,}개 장비를 items_ko.json에 병합
2. **2단계**: 크롤링 결과({len(comparison['crawler_new_ids']):,}개)를 검증 후 수동 추가

**예상 최종 데이터 규모**: **{ref_analysis['total_count'] + extra_count + len(comparison['crawler_new_ids']):,}개**

---

## 5. 데이터 무결성 이슈

### 5.1 이름 불일치 처리
- **이슈**: {len(comparison['name_mismatches']):,}개 아이템에서 ref/v와 items_ko 간 이름 차이
- **원인**: 번역 차이, 오타, 게임 업데이트
- **조치**: 수동 검토 후 정확한 이름 선택

### 5.2 카테고리 불일치 처리
- **이슈**: {len(comparison['category_mismatches']):,}개 아이템에서 타입 분류 차이
- **원인**: 분류 기준 차이
- **조치**: items_ko.json의 분류 기준 우선 적용 (TITrack 내부 로직과 일관성)

---

*보고서 생성 완료*
"""

    return report


def main():
    """메인 분석 실행"""
    print("[DATA COMPARISON] 데이터 소스 비교 분석 시작...")

    # 1. 데이터 로드
    print("\n[1/6] 데이터 로드 중...")
    ref_data = load_json(REF_PATH)
    items_ko = load_json(ITEMS_KO_PATH)

    # 2. 각 소스 분석
    print("[2/6] 각 데이터 소스 분석 중...")
    ref_analysis = analyze_ref_data(ref_data)
    items_ko_analysis = analyze_items_ko(items_ko)
    crawler_analysis = analyze_crawler_data(OUTPUT_DIR)

    print(f"   - ref/v: {ref_analysis['total_count']:,}개")
    print(f"   - items_ko: {items_ko_analysis['total_count']:,}개")
    print(f"   - crawler: {crawler_analysis['total_count']:,}개")

    # 3. 비교 분석
    print("[3/6] 데이터 소스 간 비교 중...")
    comparison = compare_data_sources(ref_analysis, items_ko_analysis, crawler_analysis)

    print(f"   - ref/v에는 있지만 items_ko에 없음: {len(comparison['missing_in_items_ko']):,}개")
    print(f"   - items_ko에는 있지만 ref/v에 없음: {len(comparison['missing_in_ref']):,}개")
    print(f"   - 크롤링으로 새로 발견: {len(comparison['crawler_new_ids']):,}개")
    print(f"   - 이름 불일치: {len(comparison['name_mismatches']):,}개")
    print(f"   - 카테고리 불일치: {len(comparison['category_mismatches']):,}개")

    # 4. 보고서 생성
    print("[4/6] 보고서 생성 중...")
    report = generate_report(ref_analysis, items_ko_analysis, crawler_analysis, comparison)

    report_path = DOCS_DIR / "data_comparison_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"   [OK] 보고서 저장: {report_path}")

    # 5. 누락 아이템 목록 생성
    print("[5/6] 누락 아이템 목록 생성 중...")
    missing_items = {}

    for config_id in comparison["missing_in_items_ko"]:
        missing_items[config_id] = ref_analysis["items"][config_id]

    missing_path = OUTPUT_DIR / "missing_items.json"
    save_json(missing_path, missing_items)

    print(f"   [OK] 누락 아이템 저장: {missing_path} ({len(missing_items):,}개)")

    # 6. 크롤링 신규 아이템 목록 생성
    if comparison["crawler_new_ids"]:
        print("[6/6] 크롤링 신규 아이템 목록 생성 중...")
        crawler_new_items = {}

        for config_id in comparison["crawler_new_ids"]:
            crawler_new_items[config_id] = crawler_analysis["items"][config_id]

        crawler_new_path = OUTPUT_DIR / "crawler_new_items.json"
        save_json(crawler_new_path, crawler_new_items)

        print(f"   [OK] 크롤링 신규 아이템 저장: {crawler_new_path} ({len(crawler_new_items):,}개)")

    print("\n[DONE] 분석 완료!")
    print(f"\n출력 파일:")
    print(f"   - {report_path}")
    print(f"   - {missing_path}")
    if comparison["crawler_new_ids"]:
        print(f"   - {crawler_new_path}")


if __name__ == "__main__":
    main()
