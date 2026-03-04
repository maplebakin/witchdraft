"""
WitchDraft Enhanced Shadow Bible

Extracts rich semantic information from narrative text for:
- Character traits and personality descriptions
- Emotional/psychological themes
- Setting characteristics
- Color-suggestive language
- Evolution tracking over time

Designed for color palette generation and thematic analysis.
"""

from __future__ import annotations

import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from witchdraft.core.scene_utils import split_scenes
from witchdraft.db.schema import ensure_vault_schema
from witchdraft.palette_theme_db import (
    init_palette_theme_tables,
    upsert_theme,
    assign_theme_to_entity,
    record_theme_evolution,
    get_entity_themes,
)


# =============================================================================
# CONFIGURATION: Thematic and semantic extraction rules
# =============================================================================

# Core literary themes with associated keywords
THEME_KEYWORDS: dict[str, set[str]] = {
    "redemption": {
        "forgive", "forgiven", "redeem", "redeemed", "atone", "atonement",
        "repent", "repentance", "salvation", "saved", "reformed", "absolution",
        "mercy", "second chance", "making amends",
    },
    "loss": {
        "lost", "lose", "grief", "grieve", "mourning", "mourn", "death",
        "died", "gone", "absence", "missing", "farewell", "goodbye",
        "departed", "passed", "empty", "void", "bereaved",
    },
    "growth": {
        "grow", "grew", "grown", "learn", "learned", "mature", "matured",
        "develop", "evolved", "transform", "changed", "becoming", "progress",
        "journey", "awakening", "realization", "understood",
    },
    "love": {
        "love", "loved", "loving", "heart", "passion", "desire", "longing",
        "adore", "cherish", "devotion", "romance", "tender", "affection",
        "beloved", "sweetheart", "embrace", "kiss",
    },
    "betrayal": {
        "betray", "betrayed", "betrayal", "traitor", "treachery", "deceive",
        "deceived", "deception", "lies", "lied", "trust", "broken",
        "backstab", "unfaithful", "disloyal",
    },
    "power": {
        "power", "powerful", "strength", "strong", "control", "dominate",
        "command", "authority", "rule", "ruler", "throne", "crown",
        "conquer", "victory", "triumph", "mighty",
    },
    "fear": {
        "fear", "afraid", "terror", "terrified", "dread", "horror",
        "nightmare", "frightened", "scared", "panic", "anxiety", "worried",
        "trembling", "shaking", "haunted",
    },
    "hope": {
        "hope", "hopeful", "dream", "dreaming", "wish", "aspire", "believe",
        "faith", "optimism", "light", "dawn", "promise", "future",
        "possibility", "chance",
    },
    "isolation": {
        "alone", "lonely", "isolated", "solitude", "abandoned", "forsaken",
        "outcast", "exile", "separated", "apart", "distant", "withdrawn",
        "hermit", "recluse",
    },
    "vengeance": {
        "revenge", "vengeance", "avenge", "retribution", "payback",
        "retaliate", "grudge", "hatred", "bitter", "wrath", "fury",
        "punish", "justice",
    },
    "identity": {
        "identity", "self", "who am i", "purpose", "meaning", "destiny",
        "fate", "calling", "belonging", "roots", "heritage", "legacy",
        "mask", "true self",
    },
    "sacrifice": {
        "sacrifice", "sacrificed", "give up", "surrender", "selfless",
        "martyr", "cost", "price", "loss", "offering", "devotion",
    },
    "corruption": {
        "corrupt", "corrupted", "taint", "tainted", "darkness", "evil",
        "wicked", "sinister", "malice", "twisted", "decay", "rot",
        "poison", "vile",
    },
    "innocence": {
        "innocent", "innocence", "pure", "purity", "naive", "child",
        "youth", "untouched", "simple", "gentle", "tender", "sweet",
    },
    "mystery": {
        "mystery", "mysterious", "secret", "hidden", "unknown", "enigma",
        "puzzle", "riddle", "cryptic", "shadow", "whisper", "ancient",
    },
}

# Emotion categories with associated adjectives/descriptors
EMOTION_DESCRIPTORS: dict[str, set[str]] = {
    "joy": {
        "happy", "joyful", "elated", "ecstatic", "delighted", "cheerful",
        "merry", "gleeful", "blissful", "radiant", "beaming", "jubilant",
    },
    "sadness": {
        "sad", "sorrowful", "melancholy", "dejected", "despondent", "gloomy",
        "mournful", "somber", "forlorn", "heartbroken", "weeping", "tearful",
    },
    "anger": {
        "angry", "furious", "enraged", "wrathful", "irate", "livid",
        "seething", "incensed", "outraged", "hostile", "fierce",
    },
    "fear": {
        "afraid", "fearful", "terrified", "frightened", "anxious", "nervous",
        "panicked", "horrified", "petrified", "trembling", "uneasy",
    },
    "surprise": {
        "surprised", "shocked", "astonished", "amazed", "stunned",
        "startled", "bewildered", "astounded", "dumbfounded",
    },
    "disgust": {
        "disgusted", "repulsed", "revolted", "sickened", "nauseated",
        "appalled", "horrified", "loathing",
    },
    "trust": {
        "trusting", "faithful", "loyal", "devoted", "reliable", "steadfast",
        "confident", "secure", "assured",
    },
    "anticipation": {
        "eager", "excited", "expectant", "hopeful", "anxious", "restless",
        "impatient", "yearning", "longing",
    },
}

# Color-suggestive words (map to color families for palette hints)
COLOR_SUGGESTIVE: dict[str, list[str]] = {
    "red": [
        "blood", "bloody", "crimson", "scarlet", "ruby", "flame", "fire",
        "burning", "fiery", "rose", "cherry", "wine", "rage", "passion",
    ],
    "blue": [
        "ice", "icy", "cold", "frozen", "frost", "ocean", "sea", "sky",
        "azure", "sapphire", "melancholy", "sad", "tears", "water",
    ],
    "green": [
        "forest", "nature", "grass", "leaf", "leaves", "emerald", "jade",
        "moss", "verdant", "growth", "spring", "envy", "poison",
    ],
    "yellow": [
        "gold", "golden", "sun", "sunny", "bright", "light", "radiant",
        "honey", "amber", "warm", "cheerful", "coward",
    ],
    "purple": [
        "royal", "regal", "noble", "mystic", "mystical", "magic", "magical",
        "violet", "lavender", "twilight", "dusk", "mystery",
    ],
    "orange": [
        "autumn", "fall", "harvest", "sunset", "copper", "rust", "amber",
        "warmth", "spice",
    ],
    "black": [
        "dark", "darkness", "shadow", "shadows", "night", "midnight",
        "obsidian", "ebony", "void", "death", "evil", "sinister",
    ],
    "white": [
        "pure", "purity", "snow", "ice", "light", "bright", "silver",
        "pale", "ghost", "spirit", "innocent", "clean", "blank",
    ],
    "gray": [
        "ash", "ashes", "smoke", "fog", "mist", "cloudy", "overcast",
        "neutral", "ambiguous", "uncertain", "old", "aged",
    ],
    "brown": [
        "earth", "earthen", "soil", "wood", "wooden", "tree", "bark",
        "coffee", "chocolate", "rustic", "humble", "grounded",
    ],
}

# Setting atmosphere descriptors
SETTING_ATMOSPHERES: dict[str, set[str]] = {
    "ominous": {
        "dark", "shadowy", "looming", "threatening", "foreboding",
        "sinister", "eerie", "creepy", "haunted", "gloomy", "oppressive",
    },
    "serene": {
        "peaceful", "calm", "tranquil", "quiet", "still", "gentle",
        "soft", "soothing", "idyllic", "pastoral",
    },
    "chaotic": {
        "chaotic", "turbulent", "violent", "stormy", "wild", "frantic",
        "frenzied", "hectic", "disordered", "tumultuous",
    },
    "magical": {
        "magical", "enchanted", "mystical", "otherworldly", "ethereal",
        "supernatural", "arcane", "wondrous", "fantastical",
    },
    "decaying": {
        "decaying", "crumbling", "ruined", "abandoned", "desolate",
        "decrepit", "dilapidated", "withered", "rotting",
    },
    "vibrant": {
        "vibrant", "alive", "bustling", "lively", "colorful", "bright",
        "energetic", "flourishing", "thriving",
    },
    "cold": {
        "cold", "frigid", "frozen", "icy", "chilly", "bitter", "harsh",
        "bleak", "wintry",
    },
    "warm": {
        "warm", "cozy", "inviting", "comfortable", "welcoming", "sunny",
        "bright", "golden", "summery",
    },
}

# Character archetype patterns
CHARACTER_ARCHETYPES: dict[str, set[str]] = {
    "hero": {
        "brave", "courageous", "noble", "heroic", "valiant", "fearless",
        "selfless", "righteous", "honorable", "just",
    },
    "villain": {
        "evil", "wicked", "cruel", "malicious", "sinister", "dark",
        "ruthless", "merciless", "heartless", "villainous",
    },
    "mentor": {
        "wise", "ancient", "knowing", "sage", "experienced", "patient",
        "guiding", "teaching", "elder",
    },
    "trickster": {
        "cunning", "clever", "sly", "mischievous", "playful", "deceitful",
        "witty", "tricky", "scheming",
    },
    "innocent": {
        "innocent", "naive", "pure", "young", "inexperienced", "trusting",
        "gentle", "kind", "sweet",
    },
    "rebel": {
        "rebellious", "defiant", "independent", "free", "wild",
        "unconventional", "radical", "outcast",
    },
    "guardian": {
        "protective", "watchful", "loyal", "steadfast", "strong",
        "defensive", "sheltering", "devoted",
    },
    "seeker": {
        "curious", "searching", "questioning", "restless", "wandering",
        "seeking", "exploring", "discovering",
    },
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class ExtractedTrait:
    """A trait extracted from text with context."""
    trait: str
    category: str  # "personality", "emotion", "physical", "archetype"
    source_text: str  # The sentence/clause it was extracted from
    confidence: float = 1.0


@dataclass
class ExtractedTheme:
    """A theme detected in text."""
    theme: str
    keywords_found: list[str]
    intensity: int  # 1-5 based on frequency/prominence
    source_sentences: list[str]


@dataclass
class ColorSuggestion:
    """A color family suggested by the text."""
    color_family: str
    trigger_words: list[str]
    weight: float  # How strongly this color is suggested


@dataclass
class SettingAnalysis:
    """Analysis of a setting/location."""
    atmospheres: list[str]
    color_suggestions: list[ColorSuggestion]
    descriptors: list[str]


@dataclass
class EntityAnalysis:
    """Complete semantic analysis of an entity."""
    entity_id: int
    entity_name: str
    entity_type: str
    traits: list[ExtractedTrait] = field(default_factory=list)
    themes: list[ExtractedTheme] = field(default_factory=list)
    color_suggestions: list[ColorSuggestion] = field(default_factory=list)
    archetypes: list[str] = field(default_factory=list)
    emotions: dict[str, int] = field(default_factory=dict)  # emotion -> count


@dataclass
class SceneAnalysis:
    """Complete semantic analysis of a scene."""
    scene_id: int
    title: str
    entities: dict[int, EntityAnalysis] = field(default_factory=dict)
    setting: Optional[SettingAnalysis] = None
    dominant_themes: list[str] = field(default_factory=list)
    mood: str = "neutral"


# =============================================================================
# EXTRACTION FUNCTIONS
# =============================================================================


def _timestamp() -> str:
    """Generate ISO 8601 timestamp."""
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def extract_traits_from_dependency(ent, doc) -> list[ExtractedTrait]:
    """
    Extract traits using dependency parsing for richer context.

    Looks at:
    - Adjectives modifying the entity (amod)
    - Predicate adjectives (she was BRAVE)
    - Appositive phrases (John, the brave warrior)
    - Relative clauses (who was fierce)
    """
    traits: list[ExtractedTrait] = []
    seen: set[str] = set()

    # Get the head token of the entity span
    head = ent.root

    # 1. Direct adjectival modifiers (amod)
    for token in head.children:
        if token.dep_ == "amod" and token.pos_ == "ADJ":
            lemma = token.lemma_.lower()
            if lemma not in seen:
                seen.add(lemma)
                traits.append(ExtractedTrait(
                    trait=lemma,
                    category=_categorize_adjective(lemma),
                    source_text=ent.sent.text.strip()[:200],
                ))

    # 2. Look for predicate adjectives: "Entity is/was/seemed ADJ"
    # Check if entity is subject of a copular verb
    if head.dep_ in ("nsubj", "nsubjpass"):
        verb = head.head
        if verb.lemma_ in ("be", "seem", "become", "feel", "appear", "look"):
            for child in verb.children:
                if child.dep_ == "acomp" and child.pos_ == "ADJ":
                    lemma = child.lemma_.lower()
                    if lemma not in seen:
                        seen.add(lemma)
                        traits.append(ExtractedTrait(
                            trait=lemma,
                            category=_categorize_adjective(lemma),
                            source_text=ent.sent.text.strip()[:200],
                            confidence=0.9,
                        ))

    # 3. Adjacent adjectives (fallback, lower confidence)
    for index in (ent.start - 1, ent.start - 2, ent.end, ent.end + 1):
        if 0 <= index < len(doc):
            token = doc[index]
            if token.pos_ == "ADJ":
                lemma = token.lemma_.lower()
                if lemma not in seen:
                    seen.add(lemma)
                    traits.append(ExtractedTrait(
                        trait=lemma,
                        category=_categorize_adjective(lemma),
                        source_text=ent.sent.text.strip()[:200],
                        confidence=0.7,
                    ))

    # 4. Check for archetype-matching traits in the sentence
    sentence_lower = ent.sent.text.lower()
    for archetype, keywords in CHARACTER_ARCHETYPES.items():
        matches = [kw for kw in keywords if kw in sentence_lower]
        if matches:
            for match in matches:
                if match not in seen:
                    seen.add(match)
                    traits.append(ExtractedTrait(
                        trait=match,
                        category="archetype",
                        source_text=ent.sent.text.strip()[:200],
                        confidence=0.8,
                    ))

    return traits


def _categorize_adjective(adj: str) -> str:
    """Categorize an adjective into personality, emotion, physical, or general."""
    adj_lower = adj.lower()

    # Check emotion categories
    for emotion, descriptors in EMOTION_DESCRIPTORS.items():
        if adj_lower in descriptors:
            return "emotion"

    # Check archetype categories
    for archetype, keywords in CHARACTER_ARCHETYPES.items():
        if adj_lower in keywords:
            return "archetype"

    # Physical descriptors
    physical = {
        "tall", "short", "thin", "fat", "pale", "dark", "young", "old",
        "beautiful", "handsome", "ugly", "scarred", "muscular", "frail",
        "large", "small", "slender", "stocky", "gaunt", "weathered",
    }
    if adj_lower in physical:
        return "physical"

    return "personality"


def detect_themes_in_text(text: str) -> list[ExtractedTheme]:
    """
    Detect literary themes in a block of text.

    Returns themes sorted by intensity (most prominent first).
    """
    text_lower = text.lower()
    sentences = re.split(r'[.!?]+', text)

    theme_data: dict[str, dict] = {}

    for theme, keywords in THEME_KEYWORDS.items():
        found_keywords: list[str] = []
        source_sentences: list[str] = []

        for keyword in keywords:
            # Use word boundaries for more accurate matching
            pattern = rf'\b{re.escape(keyword)}\b'
            if re.search(pattern, text_lower):
                found_keywords.append(keyword)
                # Find sentences containing this keyword
                for sent in sentences:
                    if keyword in sent.lower() and sent.strip():
                        source_sentences.append(sent.strip()[:150])

        if found_keywords:
            # Calculate intensity based on keyword count and diversity
            keyword_count = len(found_keywords)
            intensity = min(5, max(1, keyword_count))

            theme_data[theme] = {
                "keywords": found_keywords,
                "intensity": intensity,
                "sentences": source_sentences[:3],  # Limit examples
            }

    # Convert to ExtractedTheme objects
    themes = [
        ExtractedTheme(
            theme=theme,
            keywords_found=data["keywords"],
            intensity=data["intensity"],
            source_sentences=data["sentences"],
        )
        for theme, data in theme_data.items()
    ]

    # Sort by intensity
    themes.sort(key=lambda t: t.intensity, reverse=True)
    return themes


def extract_color_suggestions(text: str) -> list[ColorSuggestion]:
    """
    Extract color suggestions from text based on evocative language.
    """
    text_lower = text.lower()
    suggestions: list[ColorSuggestion] = []

    for color, triggers in COLOR_SUGGESTIVE.items():
        found_triggers: list[str] = []

        for trigger in triggers:
            pattern = rf'\b{re.escape(trigger)}\b'
            matches = re.findall(pattern, text_lower)
            if matches:
                found_triggers.extend([trigger] * len(matches))

        if found_triggers:
            # Weight based on frequency
            weight = min(1.0, len(found_triggers) * 0.2)
            suggestions.append(ColorSuggestion(
                color_family=color,
                trigger_words=list(set(found_triggers)),
                weight=weight,
            ))

    # Sort by weight
    suggestions.sort(key=lambda s: s.weight, reverse=True)
    return suggestions


def analyze_setting(text: str) -> SettingAnalysis:
    """
    Analyze setting/atmosphere from descriptive text.
    """
    text_lower = text.lower()

    # Detect atmospheres
    atmospheres: list[str] = []
    for atmosphere, descriptors in SETTING_ATMOSPHERES.items():
        matches = sum(1 for d in descriptors if d in text_lower)
        if matches >= 2:  # Require at least 2 matching descriptors
            atmospheres.append(atmosphere)

    # Extract general descriptors (adjectives near setting words)
    setting_markers = {"room", "house", "castle", "forest", "city", "village",
                       "street", "garden", "palace", "tower", "cave", "mountain"}
    descriptors: list[str] = []

    words = text_lower.split()
    for i, word in enumerate(words):
        if word in setting_markers:
            # Look at adjacent words
            for j in range(max(0, i-3), min(len(words), i+3)):
                if words[j] not in setting_markers:
                    # Basic adjective check (ends in common suffixes)
                    w = words[j]
                    if (w.endswith(('y', 'ed', 'ing', 'ous', 'ive', 'ful', 'less'))
                            and len(w) > 3):
                        descriptors.append(w)

    return SettingAnalysis(
        atmospheres=atmospheres,
        color_suggestions=extract_color_suggestions(text),
        descriptors=list(set(descriptors))[:10],
    )


def extract_emotions_for_entity(ent, doc) -> dict[str, int]:
    """
    Extract emotions associated with an entity in context.
    """
    emotions: dict[str, int] = defaultdict(int)

    # Get the sentence containing the entity
    sent_text = ent.sent.text.lower()

    for emotion, descriptors in EMOTION_DESCRIPTORS.items():
        for descriptor in descriptors:
            if descriptor in sent_text:
                emotions[emotion] += 1

    return dict(emotions)


def detect_archetypes(traits: list[ExtractedTrait]) -> list[str]:
    """
    Detect character archetypes from extracted traits.
    """
    archetype_scores: dict[str, int] = defaultdict(int)

    for trait in traits:
        trait_lower = trait.trait.lower()
        for archetype, keywords in CHARACTER_ARCHETYPES.items():
            if trait_lower in keywords:
                archetype_scores[archetype] += 1

    # Return archetypes with at least 2 matching traits
    return [arch for arch, score in archetype_scores.items() if score >= 2]


def _merge_theme_lists(
    existing: list[ExtractedTheme],
    incoming: list[ExtractedTheme],
) -> list[ExtractedTheme]:
    """Merge theme lists by theme name, preserving strongest intensity."""
    merged: dict[str, ExtractedTheme] = {item.theme: item for item in existing}
    for item in incoming:
        current = merged.get(item.theme)
        if current is None:
            merged[item.theme] = item
            continue
        current.intensity = max(current.intensity, item.intensity)
        current.keywords_found = sorted(set(current.keywords_found + item.keywords_found))
        seen_sentences = list(dict.fromkeys(current.source_sentences + item.source_sentences))
        current.source_sentences = seen_sentences[:5]
    return sorted(merged.values(), key=lambda t: t.intensity, reverse=True)


def _merge_color_suggestions(
    existing: list[ColorSuggestion],
    incoming: list[ColorSuggestion],
) -> list[ColorSuggestion]:
    merged: dict[str, ColorSuggestion] = {item.color_family: item for item in existing}
    for item in incoming:
        current = merged.get(item.color_family)
        if current is None:
            merged[item.color_family] = item
            continue
        current.weight = max(current.weight, item.weight)
        current.trigger_words = sorted(set(current.trigger_words + item.trigger_words))
    return sorted(merged.values(), key=lambda s: s.weight, reverse=True)


# =============================================================================
# DATABASE INTEGRATION
# =============================================================================


def store_entity_analysis(
    conn: sqlite3.Connection,
    entity_id: int,
    analysis: EntityAnalysis,
    scene_id: Optional[int],
    timestamp: str,
) -> None:
    """
    Store the enhanced analysis in the database.
    """
    # Store traits (using existing + enhanced trait tables)
    seen_traits: set[str] = set()
    for trait in analysis.traits:
        trait_key = trait.trait.strip().casefold()
        if not trait_key or trait_key in seen_traits:
            continue
        seen_traits.add(trait_key)
        conn.execute(
            """
            INSERT INTO traits (entity_id, trait, recorded_at)
            VALUES (?, ?, ?)
            """,
            (entity_id, trait.trait, timestamp),
        )
        store_enhanced_trait(conn, entity_id, trait, scene_id, timestamp)

    # Persist derived archetypes so constellation can display them.
    seen_archetypes = {
        trait.trait.strip().casefold()
        for trait in analysis.traits
        if trait.category == "archetype"
    }
    for archetype in analysis.archetypes:
        key = archetype.strip().casefold()
        if not key or key in seen_archetypes:
            continue
        store_enhanced_trait(
            conn,
            entity_id,
            ExtractedTrait(
                trait=archetype,
                category="archetype",
                source_text="derived archetype",
                confidence=0.7,
            ),
            scene_id,
            timestamp,
        )

    # Store themes
    for theme_data in analysis.themes:
        # Upsert the theme
        theme_id = upsert_theme(conn, theme_data.theme)

        # Get current intensity for this entity-theme pair
        current_themes = get_entity_themes(conn, entity_id)
        current_intensity = 0
        for et, t in current_themes:
            if t.id == theme_id:
                current_intensity = et.intensity
                break

        # Assign theme to entity
        new_intensity = theme_data.intensity
        assign_theme_to_entity(
            conn, entity_id, theme_id,
            intensity=new_intensity,
            notes=f"Keywords: {', '.join(theme_data.keywords_found[:5])}"
        )

        # Record evolution if intensity changed significantly
        if current_intensity > 0 and abs(new_intensity - current_intensity) >= 2:
            record_theme_evolution(
                conn, entity_id, theme_id,
                intensity_before=current_intensity,
                intensity_after=new_intensity,
                context="Shadow Bible scan detected thematic shift",
                scene_id=scene_id,
            )

    # Store color hints used by palette generation fallback.
    for suggestion in analysis.color_suggestions:
        store_color_hint(conn, entity_id, suggestion, scene_id, timestamp)


def store_scene_themes(
    conn: sqlite3.Connection,
    scene_id: int,
    themes: list[ExtractedTheme],
    timestamp: str,
) -> None:
    """
    Store scene-level themes and link them to the scene.
    """
    for theme_data in themes:
        theme_id = upsert_theme(
            conn,
            theme_data.theme,
            description=f"Detected keywords: {', '.join(theme_data.keywords_found[:5])}"
        )
        conn.execute(
            """
            INSERT INTO scene_themes (scene_id, theme_id, intensity, recorded_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(scene_id, theme_id) DO UPDATE SET
                intensity = excluded.intensity,
                recorded_at = excluded.recorded_at
            """,
            (scene_id, theme_id, theme_data.intensity, timestamp),
        )


def store_scene_emotion(
    conn: sqlite3.Connection,
    scene_id: int,
    emotion: str,
    intensity: int,
    timestamp: str,
) -> None:
    """Store an aggregated scene emotion score."""
    conn.execute(
        """
        INSERT INTO scene_emotions (scene_id, emotion, intensity, recorded_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(scene_id, emotion) DO UPDATE SET
            intensity = excluded.intensity,
            recorded_at = excluded.recorded_at
        """,
        (scene_id, emotion, intensity, timestamp),
    )


# =============================================================================
# ENHANCED TRAIT EXTRACTION TABLE
# =============================================================================


def init_enhanced_traits_table(conn: sqlite3.Connection) -> None:
    """
    Create enhanced traits table with richer metadata.

    This supplements the existing traits table with additional context.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS enhanced_traits (
            id INTEGER PRIMARY KEY,
            entity_id INTEGER NOT NULL,
            trait TEXT NOT NULL,
            category TEXT NOT NULL,
            source_text TEXT,
            confidence REAL DEFAULT 1.0,
            scene_id INTEGER,
            recorded_at TEXT NOT NULL,
            FOREIGN KEY(entity_id) REFERENCES entities(id) ON DELETE CASCADE,
            FOREIGN KEY(scene_id) REFERENCES scenes(id) ON DELETE SET NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS entity_color_hints (
            id INTEGER PRIMARY KEY,
            entity_id INTEGER NOT NULL,
            color_family TEXT NOT NULL,
            trigger_words TEXT NOT NULL,
            weight REAL NOT NULL,
            scene_id INTEGER,
            recorded_at TEXT NOT NULL,
            FOREIGN KEY(entity_id) REFERENCES entities(id) ON DELETE CASCADE,
            FOREIGN KEY(scene_id) REFERENCES scenes(id) ON DELETE SET NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS scene_atmospheres (
            id INTEGER PRIMARY KEY,
            scene_id INTEGER NOT NULL,
            atmosphere TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            FOREIGN KEY(scene_id) REFERENCES scenes(id) ON DELETE CASCADE,
            UNIQUE(scene_id, atmosphere)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scene_themes (
            scene_id INTEGER NOT NULL,
            theme_id INTEGER NOT NULL,
            intensity INTEGER NOT NULL,
            recorded_at TEXT NOT NULL,
            PRIMARY KEY (scene_id, theme_id),
            FOREIGN KEY(scene_id) REFERENCES scenes(id) ON DELETE CASCADE,
            FOREIGN KEY(theme_id) REFERENCES themes(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scene_emotions (
            scene_id INTEGER NOT NULL,
            emotion TEXT NOT NULL,
            intensity INTEGER NOT NULL,
            recorded_at TEXT NOT NULL,
            PRIMARY KEY (scene_id, emotion),
            FOREIGN KEY(scene_id) REFERENCES scenes(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_enhanced_traits_entity
        ON enhanced_traits(entity_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_entity_color_hints_entity
        ON entity_color_hints(entity_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_scene_themes_scene
        ON scene_themes(scene_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_scene_emotions_scene
        ON scene_emotions(scene_id)
    """)


def store_enhanced_trait(
    conn: sqlite3.Connection,
    entity_id: int,
    trait: ExtractedTrait,
    scene_id: Optional[int],
    timestamp: str,
) -> None:
    """Store an enhanced trait with full metadata."""
    conn.execute(
        """
        INSERT INTO enhanced_traits
            (entity_id, trait, category, source_text, confidence, scene_id, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (entity_id, trait.trait, trait.category, trait.source_text,
         trait.confidence, scene_id, timestamp),
    )


def store_color_hint(
    conn: sqlite3.Connection,
    entity_id: int,
    suggestion: ColorSuggestion,
    scene_id: Optional[int],
    timestamp: str,
) -> None:
    """Store a color hint for an entity."""
    conn.execute(
        """
        INSERT INTO entity_color_hints
            (entity_id, color_family, trigger_words, weight, scene_id, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (entity_id, suggestion.color_family, ",".join(suggestion.trigger_words),
         suggestion.weight, scene_id, timestamp),
    )


def store_scene_atmosphere(
    conn: sqlite3.Connection,
    scene_id: int,
    atmosphere: str,
    timestamp: str,
) -> None:
    """Store a scene atmosphere."""
    conn.execute(
        """
        INSERT OR IGNORE INTO scene_atmospheres (scene_id, atmosphere, recorded_at)
        VALUES (?, ?, ?)
        """,
        (scene_id, atmosphere, timestamp),
    )


# =============================================================================
# MAIN ENHANCED SCAN FUNCTION
# =============================================================================


def run_enhanced_spacy_scan(text: str, db_path: Path) -> None:
    """
    Enhanced Shadow Bible scan with rich semantic extraction.

    This function:
    1. Extracts named entities (PERSON, GPE, ORG, FAC)
    2. Performs dependency-based trait extraction
    3. Detects literary themes
    4. Extracts color-suggestive language
    5. Analyzes setting atmospheres
    6. Tracks evolution over time
    """
    if not text.strip():
        return

    # Lazy load spaCy
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")
    except Exception as exc:
        raise RuntimeError("spaCy unavailable (install spacy + en_core_web_sm).") from exc

    timestamp = _timestamp()

    conn = sqlite3.connect(db_path, timeout=5)
    try:
        # Initialize all tables
        ensure_vault_schema(conn)
        init_enhanced_traits_table(conn)
        init_palette_theme_tables(conn)
        conn.commit()

        # Split into scenes
        scenes = _split_scenes(text)
        scene_analyses: list[SceneAnalysis] = []

        # Clear previous scan data (scene-specific tables)
        conn.execute("DELETE FROM scene_entities")
        conn.execute("DELETE FROM scenes")
        conn.execute("DELETE FROM enhanced_traits")
        conn.execute("DELETE FROM entity_color_hints")
        conn.execute("DELETE FROM scene_atmospheres")
        conn.execute("DELETE FROM scene_themes")
        conn.execute("DELETE FROM scene_emotions")

        # Process each scene
        for position, (title, body) in enumerate(scenes, start=1):
            # Insert scene
            cursor = conn.execute(
                """
                INSERT INTO scenes (title, position, updated_at)
                VALUES (?, ?, ?)
                """,
                (title, position, timestamp),
            )
            scene_id = int(cursor.lastrowid)
            scene_analysis = SceneAnalysis(scene_id=scene_id, title=title)

            if not body.strip():
                scene_analyses.append(scene_analysis)
                continue

            # Process with spaCy
            doc = nlp(body)

            # Track entity counts for this scene
            entity_counts: dict[int, int] = {}
            scene_emotions: dict[str, int] = defaultdict(int)

            # Process named entities
            for ent in doc.ents:
                if ent.label_ not in {"PERSON", "GPE", "ORG", "FAC"}:
                    continue

                name = ent.text.strip()
                if not name or len(name) < 2:
                    continue

                # Upsert entity
                entity_id = _upsert_entity(conn, name, ent.label_, timestamp)
                entity_counts[entity_id] = entity_counts.get(entity_id, 0) + 1

                # Enhanced trait extraction for PERSON entities
                if ent.label_ == "PERSON":
                    traits = extract_traits_from_dependency(ent, doc)
                    emotions = extract_emotions_for_entity(ent, doc)
                    for emotion, count in emotions.items():
                        scene_emotions[emotion] += count

                    themes = detect_themes_in_text(ent.sent.text)

                    ent_sent_text = ent.sent.text
                    color_suggestions = extract_color_suggestions(ent_sent_text)[:3]

                    existing = scene_analysis.entities.get(entity_id)
                    if existing:
                        trait_map = {item.trait.casefold(): item for item in existing.traits}
                        for trait in traits:
                            trait_map.setdefault(trait.trait.casefold(), trait)
                        existing.traits = list(trait_map.values())

                        existing.themes = _merge_theme_lists(existing.themes, themes)
                        existing.color_suggestions = _merge_color_suggestions(
                            existing.color_suggestions,
                            color_suggestions,
                        )
                        for emotion, count in emotions.items():
                            existing.emotions[emotion] = existing.emotions.get(emotion, 0) + count
                    else:
                        scene_analysis.entities[entity_id] = EntityAnalysis(
                            entity_id=entity_id,
                            entity_name=name,
                            entity_type=ent.label_,
                            traits=traits,
                            themes=themes,
                            color_suggestions=color_suggestions,
                            emotions=dict(emotions),
                        )

                # For settings (GPE, FAC), analyze atmosphere
                elif ent.label_ in {"GPE", "FAC"}:
                    setting_analysis = analyze_setting(ent.sent.text)
                    for suggestion in setting_analysis.color_suggestions[:2]:
                        store_color_hint(conn, entity_id, suggestion, scene_id, timestamp)

            # Store scene-entity relationships
            for entity_id, count in entity_counts.items():
                conn.execute(
                    """
                    INSERT INTO scene_entities (scene_id, entity_id, count)
                    VALUES (?, ?, ?)
                    """,
                    (scene_id, entity_id, count),
                )

            # Persist per-entity analysis (themes/archetypes/traits/colors).
            for entity_id, analysis in scene_analysis.entities.items():
                analysis.archetypes = detect_archetypes(analysis.traits)
                store_entity_analysis(conn, entity_id, analysis, scene_id, timestamp)

            # Scene-level analysis
            scene_themes = detect_themes_in_text(body)
            scene_analysis.dominant_themes = [theme.theme for theme in scene_themes[:3]]
            store_scene_themes(conn, scene_id, scene_themes, timestamp)

            scene_setting = analyze_setting(body)
            scene_analysis.setting = scene_setting
            for atmosphere in scene_setting.atmospheres:
                store_scene_atmosphere(conn, scene_id, atmosphere, timestamp)

            if scene_emotions:
                top_emotion, _ = max(scene_emotions.items(), key=lambda item: item[1])
                scene_analysis.mood = top_emotion
                for emotion, intensity in scene_emotions.items():
                    store_scene_emotion(conn, scene_id, emotion, intensity, timestamp)

            scene_analyses.append(scene_analysis)

        # Commit all changes
        conn.commit()

    finally:
        conn.close()


def _split_scenes(text: str) -> list[tuple[str, str]]:
    """Split text into scenes by markdown headings."""
    return split_scenes(text)


def _upsert_entity(
    conn: sqlite3.Connection, name: str, entity_type: str, timestamp: str
) -> int:
    """Insert or update an entity."""
    existing = conn.execute(
        """
        SELECT id FROM entities
        WHERE lower(name) = lower(?) AND type = ?
        LIMIT 1
        """,
        (name, entity_type),
    ).fetchone()
    if existing:
        entity_id = int(existing[0])
        conn.execute(
            "UPDATE entities SET last_seen = ? WHERE id = ?",
            (timestamp, entity_id),
        )
        return entity_id

    conn.execute(
        """
        INSERT INTO entities (name, type, last_seen)
        VALUES (?, ?, ?)
        ON CONFLICT(name, type) DO UPDATE SET last_seen=excluded.last_seen
        """,
        (name, entity_type, timestamp),
    )
    row = conn.execute(
        """
        SELECT id FROM entities
        WHERE lower(name) = lower(?) AND type = ?
        LIMIT 1
        """,
        (name, entity_type),
    ).fetchone()
    return int(row[0])


# =============================================================================
# QUERY HELPERS
# =============================================================================


def get_entity_color_profile_enhanced(conn: sqlite3.Connection, entity_id: int) -> dict:
    """
    Get enhanced color profile for an entity including all extracted data.
    """
    # Basic entity info
    entity_row = conn.execute(
        "SELECT id, name, type FROM entities WHERE id = ?",
        (entity_id,),
    ).fetchone()

    if not entity_row:
        return {}

    # Enhanced traits
    traits = conn.execute(
        """
        SELECT trait, category, source_text, confidence
        FROM enhanced_traits
        WHERE entity_id = ?
        ORDER BY confidence DESC
        """,
        (entity_id,),
    ).fetchall()

    # Color hints aggregated
    color_hints = conn.execute(
        """
        SELECT color_family, SUM(weight) as total_weight,
               GROUP_CONCAT(DISTINCT trigger_words) as triggers
        FROM entity_color_hints
        WHERE entity_id = ?
        GROUP BY color_family
        ORDER BY total_weight DESC
        """,
        (entity_id,),
    ).fetchall()

    # Themes
    themes = conn.execute(
        """
        SELECT t.name, et.intensity, et.notes
        FROM entity_themes et
        JOIN themes t ON et.theme_id = t.id
        WHERE et.entity_id = ?
        ORDER BY et.intensity DESC
        """,
        (entity_id,),
    ).fetchall()

    # Detect archetypes from traits
    trait_objects = [
        ExtractedTrait(trait=r[0], category=r[1], source_text=r[2] or "", confidence=r[3])
        for r in traits
    ]
    archetypes = detect_archetypes(trait_objects)

    return {
        "entity": {
            "id": entity_row[0],
            "name": entity_row[1],
            "type": entity_row[2],
        },
        "traits": [
            {"trait": r[0], "category": r[1], "confidence": r[3]}
            for r in traits
        ],
        "color_hints": [
            {"color": r[0], "weight": r[1], "triggers": r[2].split(",") if r[2] else []}
            for r in color_hints
        ],
        "themes": [
            {"theme": r[0], "intensity": r[1], "notes": r[2]}
            for r in themes
        ],
        "archetypes": archetypes,
    }


def get_scene_analysis(conn: sqlite3.Connection, scene_id: int) -> dict:
    """
    Get complete analysis for a scene.
    """
    # Scene info
    scene_row = conn.execute(
        "SELECT id, title, position FROM scenes WHERE id = ?",
        (scene_id,),
    ).fetchone()

    if not scene_row:
        return {}

    # Atmospheres
    atmospheres = conn.execute(
        "SELECT atmosphere FROM scene_atmospheres WHERE scene_id = ?",
        (scene_id,),
    ).fetchall()

    # Entities in scene
    entities = conn.execute(
        """
        SELECT e.id, e.name, e.type, se.count
        FROM scene_entities se
        JOIN entities e ON se.entity_id = e.id
        WHERE se.scene_id = ?
        ORDER BY se.count DESC
        """,
        (scene_id,),
    ).fetchall()

    return {
        "scene": {
            "id": scene_row[0],
            "title": scene_row[1],
            "position": scene_row[2],
        },
        "atmospheres": [r[0] for r in atmospheres],
        "entities": [
            {"id": r[0], "name": r[1], "type": r[2], "mentions": r[3]}
            for r in entities
        ],
    }
