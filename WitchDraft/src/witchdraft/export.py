from __future__ import annotations

import argparse
from pathlib import Path

from witchdraft.services.export_service import ExportService

DEFAULT_SOURCE = Path("current_draft.md")
_EXPORT_SERVICE = ExportService()


def export_markdown(source_path: Path, output_path: Path) -> None:
    _EXPORT_SERVICE.export_markdown_file(source_path, output_path)


def export_pdf(source_path: Path, output_path: Path, font_path: str | None) -> None:
    _EXPORT_SERVICE.export_pdf_file(source_path, output_path, font_path)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export WitchDraft manuscript.")
    parser.add_argument(
        "--format",
        choices=["markdown", "pdf"],
        default="markdown",
        help="Output format.",
    )
    parser.add_argument("--output", required=True, help="Output file path.")
    parser.add_argument(
        "--font",
        help="Optional path to a .ttf font for PDF export.",
    )
    parser.add_argument(
        "--source",
        default=str(DEFAULT_SOURCE),
        help="Source manuscript path.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source_path = Path(args.source)
    output_path = Path(args.output)

    if args.format == "markdown":
        export_markdown(source_path, output_path)
        return 0

    export_pdf(source_path, output_path, args.font)
    return 0


if __name__ == "__main__":
    print("WitchDraft CLI export has been disabled. Use the GUI Actions menu.")
    raise SystemExit(1)
