#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from witchdraft.core.io_utils import collect_index_entries


def build_index(chapters_dir: Path, output_path: Path) -> None:
    entries = collect_index_entries(chapters_dir, Path.cwd())

    output_path.write_text(
        json.dumps(entries, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a flat index.json from chapters/ frontmatter."
    )
    parser.add_argument(
        "--chapters",
        default="chapters",
        help="Path to chapters directory (default: chapters).",
    )
    parser.add_argument(
        "--output",
        default="index.json",
        help="Output index path (default: index.json).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or [])
    chapters_dir = Path(args.chapters)

    if not chapters_dir.exists():
        raise SystemExit(f"Chapters directory not found: {chapters_dir}")

    output_path = Path(args.output)
    build_index(chapters_dir, output_path)
    return 0


if __name__ == "__main__":
    print("WitchDraft CLI index build has been disabled. Use the GUI Actions menu.")
    raise SystemExit(1)
