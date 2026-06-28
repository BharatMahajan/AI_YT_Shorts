import pytest
from pipeline import generate_script as gs
from pipeline.errors import ScriptGenerationError

TOPIC = {"key": "claude", "title": "Claude updates", "accent": "#E17055",
         "focus": "newest Claude features"}


def test_extract_json_plain():
    assert gs._extract_json('{"title":"x","lines":["a"]}')["title"] == "x"


def test_extract_json_fenced():
    assert gs._extract_json('```json\n{"title":"x","lines":["a"]}\n```')["lines"] == ["a"]


def test_extract_json_with_prose():
    assert gs._extract_json('Sure!\n{"title":"x","lines":["a"]}\nThanks')["title"] == "x"


def test_extract_json_empty_raises():
    with pytest.raises(ScriptGenerationError):
        gs._extract_json("   ")


def test_validate_requires_title_and_lines():
    with pytest.raises(ScriptGenerationError):
        gs._validate({"lines": ["a"]})
    with pytest.raises(ScriptGenerationError):
        gs._validate({"title": "x", "lines": []})
    gs._validate({"title": "x", "lines": ["a"]})


def test_normalize_fills_derived_fields():
    data = gs._normalize({"title": "T", "lines": ["one", "  ", "two"]}, TOPIC, "hook")
    assert data["narration"] == "one two"
    assert data["topic"] == "claude" and data["accent"] == "#E17055"
    assert len(data["points"]) >= 1 and isinstance(data["tags"], list)


def test_normalize_title_variants_dedupes_primary():
    data = gs._normalize(
        {"title": "Primary", "lines": ["a"],
         "title_variants": ["Primary", "Alt A", "Alt B", "Alt C"]}, TOPIC, "hook")
    assert "Primary" not in data["title_variants"]
    assert len(data["title_variants"]) <= 2


def test_normalize_caps_points_and_flow():
    data = gs._normalize(
        {"title": "T", "lines": ["a"],
         "points": [{"heading": f"h{i}", "detail": "d"} for i in range(8)],
         "flow": [f"s{i}" for i in range(8)]}, TOPIC, "hook")
    assert len(data["points"]) <= 4 and len(data["flow"]) <= 4
