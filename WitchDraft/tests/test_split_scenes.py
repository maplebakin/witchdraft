import unittest
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from witchdraft.core.scene_utils import (  # noqa: E402
    PROJECT_TYPE_BOOK,
    PROJECT_TYPE_ONE_OFF,
    split_scenes,
)


class SplitScenesTests(unittest.TestCase):
    def test_one_off_uses_any_heading_as_scene(self) -> None:
        text = "# Scene A\nLine 1\n# Scene B\nLine 2"
        scenes = split_scenes(text, project_type=PROJECT_TYPE_ONE_OFF)
        self.assertEqual([title for title, _ in scenes], ["Scene A", "Scene B"])

    def test_book_uses_h1_for_chapters_and_h2_for_scenes(self) -> None:
        text = "# \nChapter text\n## \nScene text"
        scenes = split_scenes(text, project_type=PROJECT_TYPE_BOOK)
        self.assertEqual(
            [title for title, _ in scenes], ["Untitled Chapter", "Untitled Scene"]
        )

    def test_default_project_type_is_one_off(self) -> None:
        text = "# \nBody"
        scenes = split_scenes(text)
        self.assertEqual([title for title, _ in scenes], ["Untitled Scene"])


if __name__ == "__main__":
    unittest.main()
