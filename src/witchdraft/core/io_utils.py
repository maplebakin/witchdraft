from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path


def parse_frontmatter(lines: list[str]) -> dict[str, object]:
    if not lines or lines[0].strip() != "---":
        return {}

    data: dict[str, object] = {}
    current_list_key: str | None = None

    for raw in lines[1:]:
        stripped = raw.strip()
        if stripped in ("---", "..."):
            break
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("- "):
            if current_list_key:
                data.setdefault(current_list_key, [])
                if isinstance(data[current_list_key], list):
                    data[current_list_key].append(stripped[2:].strip().strip("'\""))
            continue

        if ":" not in raw:
            continue

        key, value = raw.split(":", 1)
        key = key.strip()
        value = value.strip()

        if value == "":
            data[key] = []
            current_list_key = key
            continue

        current_list_key = None

        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            if inner:
                items = [
                    item.strip().strip("'\"")
                    for item in inner.split(",")
                    if item.strip()
                ]
            else:
                items = []
            data[key] = items
        else:
            data[key] = value.strip("'\"")

    return data


def friendly_title(stem: str) -> str:
    return stem.replace("-", " ").replace("_", " ").title()


def slugify(text: str, fallback: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or fallback


def created_from_mtime(path: Path) -> str:
    ts = datetime.fromtimestamp(path.stat().st_mtime)
    return ts.isoformat(timespec="seconds")


def iter_entry_paths(chapters_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for path in chapters_dir.rglob("*.md"):
        if any(part.startswith(".") for part in path.parts):
            continue
        paths.append(path)
    return paths


def parse_created(value: object | None) -> datetime:
    if not value:
        return datetime.min
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return datetime.min


def parse_sequence(value: object | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except ValueError:
        return None


def move_to_compost(path: Path, compost_dir: Path) -> Path | None:
    if not path.exists():
        return None

    compost_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    destination = compost_dir / f"{timestamp}__{path.name}"
    counter = 1
    while destination.exists():
        destination = compost_dir / f"{timestamp}_{counter}__{path.name}"
        counter += 1
    path.replace(destination)
    return destination


def collect_index_entries(chapters_dir: Path, root: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []

    for path in iter_entry_paths(chapters_dir):
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        fm = parse_frontmatter(lines)

        entry_id = str(fm.get("id") or path.stem)
        title = str(fm.get("title") or friendly_title(path.stem))
        created = str(fm.get("created") or created_from_mtime(path))
        mood = str(fm.get("mood") or "")
        archetype = str(fm.get("archetype") or "")
        theme = str(fm.get("theme") or "")
        palette = str(fm.get("palette") or "")
        book = str(fm.get("book") or "")
        sequence = parse_sequence(fm.get("sequence"))
        tags = fm.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]

        try:
            rel_path = path.relative_to(root)
        except ValueError:
            rel_path = path

        entries.append(
            {
                "id": entry_id,
                "title": title,
                "created": created,
                "mood": mood,
                "archetype": archetype,
                "theme": theme,
                "palette": palette,
                "book": book,
                "sequence": sequence,
                "tags": tags,
                "path": str(rel_path),
            }
        )

    entries.sort(key=lambda e: parse_created(e.get("created")), reverse=True)
    return entries
