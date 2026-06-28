from pipeline.render_props import active_title, build_props

TOPIC = {"key": "claude", "accent": "#E17055", "pattern": "rings"}
SCRIPT = {"title": "Primary", "title_variants": ["Alt A", "Alt B"],
          "topic_title": "Claude updates", "accent": "#E17055",
          "lines": ["a", "b"], "points": [{"heading": "h", "detail": "d"}],
          "flow": ["x", "y"]}
CAPS = {"duration": 55.5, "words": [{"text": "a", "start": 0, "end": 1}]}


def test_active_title_disabled_returns_primary():
    assert active_title(SCRIPT, 12345, ab_testing=False) == ("Primary", 0)


def test_active_title_rotates_when_enabled():
    seen = {active_title(SCRIPT, d, True)[0] for d in range(6)}
    assert "Primary" in seen and ("Alt A" in seen or "Alt B" in seen)


def test_build_props_shape_and_theme():
    p = build_props(SCRIPT, CAPS, topic=TOPIC, hero_image="http://x/y.jpg")
    for key in ("title", "topicTitle", "accent", "accent2", "pattern",
                "heroImage", "audioSrc", "durationSeconds", "words",
                "lines", "points", "flow"):
        assert key in p
    assert p["pattern"] == "rings"
    assert p["heroImage"] == "http://x/y.jpg"
    assert p["accent2"].startswith("#") and p["accent2"] != p["accent"]
    assert p["durationSeconds"] == 55.5


def test_build_props_title_override():
    p = build_props(SCRIPT, CAPS, topic=TOPIC, title="Chosen")
    assert p["title"] == "Chosen"
