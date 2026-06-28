from pipeline import thumbnail

SCRIPT = {"title": "A bold AI update lands today", "topic_title": "Claude updates",
          "accent": "#E17055"}


def test_make_variant_0_returns_path():
    assert thumbnail.make(SCRIPT, variant=0)


def test_make_variant_1_returns_path():
    assert thumbnail.make(SCRIPT, variant=1)


def test_font_and_hex_fallbacks(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(thumbnail.ImageFont, "truetype", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no font")))
    monkeypatch.setattr(thumbnail.ImageFont, "load_default", lambda: sentinel)
    assert thumbnail._font("x.ttf", 12) is sentinel
    assert thumbnail._hex(None) == (0x6C, 0x5C, 0xE7)
