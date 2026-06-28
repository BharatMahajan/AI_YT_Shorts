from types import SimpleNamespace
from pipeline import fetch_news


def test_image_from_media_thumbnail():
    e = SimpleNamespace(media_thumbnail=[{"url": "http://x/a.jpg"}])
    assert fetch_news._entry_image(e) == "http://x/a.jpg"


def test_image_from_summary_img_tag():
    e = SimpleNamespace(summary='<p><img src="http://x/b.png"/>hi</p>')
    assert fetch_news._entry_image(e) == "http://x/b.png"


def test_image_absent_returns_empty():
    e = SimpleNamespace(summary="no image here")
    assert fetch_news._entry_image(e) == ""


def test_top_image_picks_first_available():
    items = [{"image": ""}, {"image": "http://x/c.jpg"}, {"image": "http://x/d.jpg"}]
    assert fetch_news.top_image(items) == "http://x/c.jpg"
