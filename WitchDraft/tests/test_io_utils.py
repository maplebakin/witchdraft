import sys
import tempfile
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from witchdraft.core.io_utils import collect_index_entries, move_to_compost, slugify  # noqa: E402


class IoUtilsTests(unittest.TestCase):
    def test_slugify_uses_fallback(self) -> None:
        self.assertEqual(slugify("  ", fallback="default-name"), "default-name")

    def test_move_to_compost_moves_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "scene.md"
            source.write_text("hello", encoding="utf-8")
            destination = move_to_compost(source, root / ".compost")
            self.assertIsNotNone(destination)
            assert destination is not None
            self.assertFalse(source.exists())
            self.assertTrue(destination.exists())
            self.assertEqual(destination.read_text(encoding="utf-8"), "hello")

    def test_collect_index_entries_parses_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapters = root / "chapters"
            chapters.mkdir()
            chapter = chapters / "opening-scene.md"
            chapter.write_text(
                "\n".join(
                    [
                        "---",
                        "title: Opening",
                        "created: 2025-01-01T12:00:00",
                        "tags: [alpha, beta]",
                        "---",
                        "",
                        "# Body",
                    ]
                ),
                encoding="utf-8",
            )

            entries = collect_index_entries(chapters, root)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["title"], "Opening")
            self.assertEqual(entries[0]["tags"], ["alpha", "beta"])
            self.assertEqual(entries[0]["path"], "chapters/opening-scene.md")


if __name__ == "__main__":
    unittest.main()

