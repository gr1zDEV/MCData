#!/usr/bin/env python3
"""Generate markdown master and categorized item lists from the JSON master list."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def load_items(master_json_path: Path) -> list[str]:
    payload = json.loads(master_json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or any(not isinstance(item, str) for item in payload):
        raise ValueError(f"Expected {master_json_path} to contain a JSON array of strings")

    normalized = sorted(set(payload))
    return normalized


def bucket_name(item_id: str) -> str:
    suffix = item_id.split(":", 1)[-1]
    first = suffix[:1].lower()
    if first.isalpha():
        return first
    if first.isdigit():
        return "0-9"
    return "misc"


def render_markdown(title: str, items: list[str]) -> str:
    lines = [f"# {title}", "", f"Total items: **{len(items)}**", ""]
    lines.extend(f"- `{item}`" for item in items)
    lines.append("")
    return "\n".join(lines)


def write_master_markdown(master_md_path: Path, items: list[str]) -> None:
    master_md_path.parent.mkdir(parents=True, exist_ok=True)
    master_md_path.write_text(render_markdown("Master Item List", items), encoding="utf-8")


def write_category_files(categories_dir: Path, items: list[str]) -> None:
    categories_dir.mkdir(parents=True, exist_ok=True)

    grouped: dict[str, list[str]] = defaultdict(list)
    for item in items:
        grouped[bucket_name(item)].append(item)

    expected_files: set[str] = set()
    for category, category_items in sorted(grouped.items()):
        expected_files.add(f"{category}.md")
        category_title = f"Category: {category}"
        (categories_dir / f"{category}.md").write_text(
            render_markdown(category_title, category_items),
            encoding="utf-8",
        )

    index_lines = ["# Item Categories", "", "This index is generated from `data/items.json`.", ""]
    for category, category_items in sorted(grouped.items()):
        index_lines.append(f"- [{category}](./{category}.md) — {len(category_items)} items")
    index_lines.append("")

    expected_files.add("README.md")
    (categories_dir / "README.md").write_text("\n".join(index_lines), encoding="utf-8")

    for file_path in categories_dir.glob("*.md"):
        if file_path.name not in expected_files:
            file_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--master-json", default="data/items.json")
    parser.add_argument("--master-md", default="data/items.md")
    parser.add_argument("--categories-dir", default="data/categories")
    args = parser.parse_args()

    master_json_path = Path(args.master_json)
    master_md_path = Path(args.master_md)
    categories_dir = Path(args.categories_dir)

    items = load_items(master_json_path)
    write_master_markdown(master_md_path, items)
    write_category_files(categories_dir, items)

    print(
        f"Synced markdown lists from {master_json_path} -> {master_md_path} and {categories_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
