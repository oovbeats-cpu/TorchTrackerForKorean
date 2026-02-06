#!/usr/bin/env python3
"""Convert game data files into TITrack-compatible items_ko.json and items_icons.json.

Usage:
    python convert_dataset.py 20260207.txt
    python convert_dataset.py 20260207.txt --seed-file tlidb_items_seed_en.json
    python convert_dataset.py 20260207.txt --output-dir output/ --install

Standalone CLI tool - stdlib only, no external dependencies.
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_input_data(path: str) -> dict:
    """Load the input txt/json file with defensive parsing."""
    content = Path(path).read_text(encoding="utf-8")
    content = content.strip()
    if not content.startswith("{"):
        content = "{" + content
    if not content.endswith("}"):
        content = content + "}"
    # Remove trailing commas before } or ]
    content = re.sub(r",(\s*[}\]])", r"\1", content)
    return json.loads(content)


def load_seed_icons(path: str) -> dict[str, str]:
    """Load tlidb_items_seed_en.json, return {id_str: img_url} mapping."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    icons: dict[str, str] = {}
    for item in data.get("items", []):
        item_id = str(item.get("id", ""))
        img = item.get("img", "")
        if item_id and img:
            icons[item_id] = img
    return icons


def load_extra_icons(path: str) -> dict[str, str]:
    """Load extra icons from a flat {id: url} JSON file (e.g. scraped data)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {str(k): v for k, v in data.items() if v}


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

def generate_items_ko(data: dict) -> str:
    """Generate items_ko.json content string.

    Keeps only name/type/price per item.  Sorted by int(key).
    Tab-indented, one item per line - matches existing file format exactly.
    """
    sorted_keys = sorted(data.keys(), key=lambda k: int(k))
    lines: list[str] = ["{"]
    for i, key in enumerate(sorted_keys):
        entry = data[key]
        name = entry.get("name", "")
        item_type = entry.get("type", "")
        price = entry.get("price", 0)
        if price is None:
            price = 0
        # Build compact JSON matching existing format: { "name": ..., "type": ..., "price": ... }
        name_j = json.dumps(name, ensure_ascii=False)
        type_j = json.dumps(item_type, ensure_ascii=False)
        price_j = json.dumps(price)
        inner = f'{{ "name": {name_j}, "type": {type_j}, "price": {price_j} }}'
        comma = "," if i < len(sorted_keys) - 1 else ""
        lines.append(f'\t"{key}": {inner}{comma}')
    lines.append("}")
    return "\n".join(lines) + "\n"


def generate_items_icons(data: dict, icons: dict[str, str]) -> tuple[str, list[str], list[str]]:
    """Generate items_icons.json content.

    Returns (json_string, matched_ids, missing_ids).
    """
    matched: list[dict] = []
    matched_ids: list[str] = []
    missing_ids: list[str] = []

    for key in sorted(data.keys(), key=lambda k: int(k)):
        if key in icons:
            matched.append({"id": key, "img": icons[key]})
            matched_ids.append(key)
        else:
            missing_ids.append(key)

    output = {"items": matched}
    content = json.dumps(output, indent=2, ensure_ascii=False)
    return content + "\n", matched_ids, missing_ids


def generate_report(
    input_data: dict,
    matched_ids: list[str],
    missing_ids: list[str],
) -> str:
    """Generate a human-readable conversion report."""
    total = len(input_data)
    priced = [(k, v) for k, v in input_data.items() if (v.get("price") or 0) > 0]
    match_count = len(matched_ids)
    match_rate = (match_count / total * 100) if total else 0

    lines = [
        "=" * 60,
        "  TITrack Dataset Conversion Report",
        "=" * 60,
        "",
        f"Total items in input:    {total}",
        f"Items with price > 0:    {len(priced)}",
        f"Icon matches found:      {match_count}",
        f"Icon match rate:         {match_rate:.1f}%",
        "",
    ]

    # Top 10 by price
    top10 = sorted(priced, key=lambda x: x[1].get("price", 0), reverse=True)[:10]
    if top10:
        lines.append("--- Top 10 items by price ---")
        for k, v in top10:
            name = v.get("name", k)
            price = v.get("price", 0)
            lines.append(f"  [{k}] {name}: {price:,.4f} FE")
        lines.append("")

    # Missing icons (first 20)
    if missing_ids:
        shown = missing_ids[:20]
        lines.append(f"--- Items with no icon match (showing {len(shown)}/{len(missing_ids)}) ---")
        for mid in shown:
            name = input_data[mid].get("name", mid)
            lines.append(f"  [{mid}] {name}")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Seed file auto-discovery
# ---------------------------------------------------------------------------

SEED_FILENAME = "tlidb_items_seed_en.json"
EXTRA_ICONS_FILENAME = "scraped_icons_all.json"


def find_file(filename: str) -> str | None:
    """Auto-find a file in common project locations."""
    script_dir = Path(__file__).resolve().parent          # tools/
    project_root = script_dir.parent                       # project root
    candidates = [
        script_dir / filename,
        project_root / filename,
        project_root / "output" / filename,
        Path.cwd() / filename,
        Path.cwd() / "output" / filename,
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return None


def find_seed_file() -> str | None:
    return find_file(SEED_FILENAME)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert game data files into TITrack-compatible format.",
    )
    parser.add_argument("input_file", help="Path to input JSON/txt file (e.g. 20260207.txt)")
    parser.add_argument(
        "--seed-file",
        default=None,
        help=f"Path to {SEED_FILENAME} (default: auto-find in tools/ or project root)",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Output directory (default: output/)",
    )
    parser.add_argument(
        "--extra-icons",
        default=None,
        help=f"Path to extra icons JSON (flat {{id: url}}) (default: auto-find {EXTRA_ICONS_FILENAME})",
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Copy outputs to src/titrack/data/",
    )
    args = parser.parse_args()

    # --- Load input ---
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}")
        sys.exit(1)

    print(f"Loading input: {input_path}")
    input_data = load_input_data(str(input_path))
    print(f"  -> {len(input_data)} items loaded")

    # --- Load seed icons ---
    seed_path = args.seed_file or find_seed_file()
    icons: dict[str, str] = {}
    if seed_path and Path(seed_path).exists():
        print(f"Loading seed icons: {seed_path}")
        icons = load_seed_icons(seed_path)
        print(f"  -> {len(icons)} icons loaded")
    else:
        print(f"Warning: seed file ({SEED_FILENAME}) not found")

    # --- Load extra scraped icons ---
    extra_path = args.extra_icons or find_file(EXTRA_ICONS_FILENAME)
    if extra_path and Path(extra_path).exists():
        print(f"Loading extra icons: {extra_path}")
        extra = load_extra_icons(extra_path)
        new_count = sum(1 for k in extra if k not in icons)
        icons.update(extra)
        print(f"  -> {len(extra)} extra icons ({new_count} new)")
    print(f"  => {len(icons)} total icons available")

    # --- Generate outputs ---
    items_ko_content = generate_items_ko(input_data)
    icons_content, matched_ids, missing_ids = generate_items_icons(input_data, icons)
    report_content = generate_report(input_data, matched_ids, missing_ids)

    # --- Write to output dir ---
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    items_ko_path = out_dir / "items_ko.json"
    icons_path = out_dir / "items_icons.json"
    report_path = out_dir / "conversion_report.txt"

    items_ko_path.write_text(items_ko_content, encoding="utf-8")
    icons_path.write_text(icons_content, encoding="utf-8")
    report_path.write_text(report_content, encoding="utf-8")

    print(f"\nOutput written to {out_dir.resolve()}/")
    print(f"  items_ko.json       ({len(input_data)} items)")
    print(f"  items_icons.json    ({len(matched_ids)} icons)")
    print(f"  conversion_report.txt")

    # --- Install ---
    if args.install:
        project_root = Path(__file__).resolve().parent.parent
        data_dir = project_root / "src" / "titrack" / "data"
        if not data_dir.exists():
            print(f"\nError: data directory not found: {data_dir}")
            sys.exit(1)

        shutil.copy2(items_ko_path, data_dir / "items_ko.json")
        shutil.copy2(icons_path, data_dir / "items_icons.json")
        print(f"\nInstalled to {data_dir}/")
        print(f"  items_ko.json")
        print(f"  items_icons.json")

    # --- Print report ---
    print()
    print(report_content)


if __name__ == "__main__":
    main()
