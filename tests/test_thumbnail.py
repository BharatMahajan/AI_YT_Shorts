from pipeline import thumbnail

SCRIPT = {"title": "A bold AI update lands today", "topic_title": "Claude updates",
          "accent": "#E17055"}


def test_make_variant_0_returns_path():
    assert thumbnail.make(SCRIPT, variant=0)


def test_make_variant_1_returns_path():
    assert thumbnail.make(SCRIPT, variant=1)
