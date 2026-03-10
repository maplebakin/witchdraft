from __future__ import annotations


PROJECT_TYPE_ONE_OFF = "one-off"
PROJECT_TYPE_BOOK = "book"


def split_scenes(
    text: str, project_type: str = PROJECT_TYPE_ONE_OFF
) -> list[tuple[str, str]]:
    scenes: list[tuple[str, str]] = []
    current_title = "Untitled Scene"
    current_lines: list[str] = []
    seen_heading = False

    for line in text.splitlines():
        if line.startswith("#"):
            if seen_heading or current_lines:
                scenes.append((current_title, "\n".join(current_lines)))

            if project_type == PROJECT_TYPE_BOOK:
                if line.startswith("# "):
                    current_title = line.lstrip("#").strip() or "Untitled Chapter"
                else:
                    current_title = line.lstrip("#").strip() or "Untitled Scene"
            else:
                current_title = line.lstrip("#").strip() or "Untitled Scene"

            current_lines = []
            seen_heading = True
        else:
            current_lines.append(line)

    if seen_heading or current_lines:
        scenes.append((current_title, "\n".join(current_lines)))
    elif text.strip():
        scenes.append(("Untitled Scene", text))

    return scenes

