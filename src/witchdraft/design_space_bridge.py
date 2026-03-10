from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional


DEFAULT_BRIDGE_URL = os.getenv(
    "DESIGN_SPACE_BRIDGE_URL", "http://127.0.0.1:4020/api/character-palette"
)
DEFAULT_TIMEOUT_SECONDS = float(os.getenv("DESIGN_SPACE_BRIDGE_TIMEOUT", "6"))


@dataclass
class CharacterProfile:
    name: str
    description: str = ""
    traits: list[str] = field(default_factory=list)
    theme: str = ""


@dataclass
class PaletteResult:
    ok: bool
    source: str
    name: str
    colors: list[str]
    error: Optional[str] = None
    raw: Optional[dict] = None


def load_character_profile(
    db_path: Path,
    name: str,
    *,
    entity_type: Optional[str] = None,
) -> Optional[CharacterProfile]:
    """Load a character profile from the WitchDraft vault database."""
    if not db_path.exists():
        return None

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        if entity_type:
            cursor.execute(
                """
                SELECT id, name FROM entities
                WHERE lower(name) = lower(?) AND type = ?
                """,
                (name, entity_type),
            )
        else:
            cursor.execute(
                "SELECT id, name FROM entities WHERE lower(name) = lower(?)",
                (name,),
            )

        row = cursor.fetchone()
        if not row:
            return None

        entity_id, entity_name = row
        cursor.execute(
            "SELECT trait FROM traits WHERE entity_id = ? ORDER BY recorded_at DESC",
            (entity_id,),
        )
        traits = [record[0] for record in cursor.fetchall() if record and record[0]]
        return CharacterProfile(name=entity_name, traits=traits)
    finally:
        conn.close()


def request_design_space_palette(
    profile: CharacterProfile,
    *,
    api_url: Optional[str] = None,
    token: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    retries: int = 1,
) -> PaletteResult:
    """Request a palette from the Design Space bridge service with fallback."""
    url = api_url or DEFAULT_BRIDGE_URL
    token = token or os.getenv("DESIGN_SPACE_BRIDGE_TOKEN") or ""

    payload = {
        "character": {
            "name": profile.name,
            "description": profile.description,
            "traits": profile.traits,
            "theme": profile.theme,
        }
    }

    last_error: Optional[str] = None
    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    **({"X-Design-Space-Token": token} if token else {}),
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                data = json.loads(body)
                if data.get("ok") and data.get("palette"):
                    palette = data["palette"]
                    colors = [c for c in palette.get("colors", []) if isinstance(c, str)]
                    if colors:
                        return PaletteResult(
                            ok=True,
                            source=data.get("source", "design-space-ai"),
                            name=str(palette.get("name") or f"{profile.name} Palette"),
                            colors=colors,
                            raw=data,
                        )
                last_error = data.get("error") or "Invalid response from Design Space."
        except urllib.error.HTTPError as exc:
            last_error = f"Design Space error {exc.code}: {exc.reason}"
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = f"Design Space unavailable: {exc}"
        except json.JSONDecodeError:
            last_error = "Design Space returned invalid JSON."

        if attempt < retries:
            time.sleep(0.25)

    fallback = generate_fallback_palette(profile)
    fallback.error = last_error
    return fallback


def generate_fallback_palette(profile: CharacterProfile) -> PaletteResult:
    """Generate a simple deterministic palette when Design Space is unavailable."""
    combined = " ".join([profile.name, profile.description, *profile.traits, profile.theme]).strip()
    base_hue = _infer_hue(combined) if combined else 220

    colors = _unique_colors(
        [
            _hsl_to_hex(base_hue, 65, 45),  # primary
            _hsl_to_hex((base_hue + 28) % 360, 58, 55),  # secondary
            _hsl_to_hex((base_hue + 180) % 360, 70, 50),  # accent
            _hsl_to_hex((base_hue + 60) % 360, 55, 60),  # highlight
            _hsl_to_hex(base_hue, 18, 92),  # surface
            _hsl_to_hex(base_hue, 12, 18),  # text
        ]
    )

    return PaletteResult(
        ok=True,
        source="fallback",
        name=f"{profile.name} Fallback Palette",
        colors=colors,
    )


def _infer_hue(text: str) -> int:
    keywords = {
        "fire": 15,
        "flame": 10,
        "ember": 20,
        "sun": 45,
        "gold": 50,
        "forest": 120,
        "earth": 30,
        "wood": 35,
        "ocean": 200,
        "sea": 200,
        "sky": 210,
        "storm": 220,
        "night": 240,
        "shadow": 260,
        "mystic": 280,
        "violet": 285,
        "rose": 340,
        "blood": 355,
    }
    text_lower = text.lower()
    matches = [hue for key, hue in keywords.items() if key in text_lower]
    if matches:
        return int(sum(matches) / len(matches))

    digest = hashlib.sha256(text_lower.encode("utf-8")).digest()
    return int.from_bytes(digest[:2], "big") % 360


def _hsl_to_hex(hue: int, saturation: int, lightness: int) -> str:
    h = (hue % 360) / 360.0
    s = max(0, min(100, saturation)) / 100.0
    l = max(0, min(100, lightness)) / 100.0

    if s == 0:
        value = int(round(l * 255))
        return f"#{value:02x}{value:02x}{value:02x}"

    def hue_to_rgb(p: float, q: float, t: float) -> float:
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q

    r = hue_to_rgb(p, q, h + 1 / 3)
    g = hue_to_rgb(p, q, h)
    b = hue_to_rgb(p, q, h - 1 / 3)

    return f"#{int(round(r * 255)):02x}{int(round(g * 255)):02x}{int(round(b * 255)):02x}"


def _unique_colors(colors: Iterable[str]) -> list[str]:
    seen = set()
    ordered = []
    for color in colors:
        if color not in seen:
            ordered.append(color)
            seen.add(color)
    return ordered
