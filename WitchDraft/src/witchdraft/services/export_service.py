from __future__ import annotations

from pathlib import Path


class ExportService:
    def build_project_text(self, chapters: list[tuple[int, str, Path]]) -> str:
        text_chunks: list[str] = []
        for _, _, path in chapters:
            if not path.exists():
                continue
            text_chunks.append(f"{path.read_text(encoding='utf-8')}\n")
        return "\n".join(text_chunks)

    def export_markdown_text(self, text: str, output_path: Path) -> None:
        cleaned = "\n".join(line.rstrip() for line in text.splitlines())
        if cleaned and not cleaned.endswith("\n"):
            cleaned += "\n"
        output_path.write_text(cleaned, encoding="utf-8")

    def export_markdown_file(self, source_path: Path, output_path: Path) -> None:
        if not source_path.exists():
            raise FileNotFoundError(f"Source not found: {source_path}")
        self.export_markdown_text(source_path.read_text(encoding="utf-8"), output_path)

    def export_pdf_text(self, text: str, output_path: Path, font_path: str | None) -> None:
        try:
            from reportlab.lib.pagesizes import LETTER
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.pdfgen import canvas
        except Exception as exc:
            raise RuntimeError("PDF export requires reportlab.") from exc

        normalized_text = text.replace("\t", "    ")
        font_name = "Times-Roman"
        font_size = 12
        if font_path:
            font_name = "GrimoireFont"
            try:
                pdfmetrics.registerFont(TTFont(font_name, font_path))
            except Exception as exc:
                raise RuntimeError(f"Could not load font: {exc}") from exc

        page_width, page_height = LETTER
        margin = 54
        line_height = font_size + 4
        max_width = page_width - (margin * 2)

        def wrap_line(raw_line: str) -> list[str]:
            if not raw_line:
                return [""]
            words = raw_line.split(" ")
            lines: list[str] = []
            current = ""
            for word in words:
                candidate = f"{current} {word}".strip()
                if pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width:
                    current = candidate
                else:
                    if current:
                        lines.append(current)
                    current = word
            if current:
                lines.append(current)
            return lines

        pdf = canvas.Canvas(str(output_path), pagesize=LETTER)
        pdf.setFont(font_name, font_size)
        x = margin
        y = page_height - margin

        for raw_line in normalized_text.splitlines():
            for line in wrap_line(raw_line):
                if y < margin:
                    pdf.showPage()
                    pdf.setFont(font_name, font_size)
                    y = page_height - margin
                pdf.drawString(x, y, line)
                y -= line_height

        pdf.save()

    def export_pdf_file(self, source_path: Path, output_path: Path, font_path: str | None) -> None:
        if not source_path.exists():
            raise FileNotFoundError(f"Source not found: {source_path}")
        self.export_pdf_text(source_path.read_text(encoding="utf-8"), output_path, font_path)
