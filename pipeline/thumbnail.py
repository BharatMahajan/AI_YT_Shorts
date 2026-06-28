"""Generate a 1280x720 thumbnail (Pillow, free), themed by topic accent.

Supports A/B layout variants (variant=0 left-aligned, variant=1 centered).
Non-fatal: failures log a warning and return None instead of aborting the run.
"""
from __future__ import annotations
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from . import config
from .logging_setup import get_logger

log = get_logger(__name__)

FONTS = config.ROOT / "assets" / "fonts"
BOLD = str(FONTS / "Poppins-Bold.ttf")
REG = str(FONTS / "Poppins-Regular.ttf")
THUMB_FILE = config.BUILD / "thumb.png"
W, H = 1280, 720


def _font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size)
    except Exception as e:
        log.warning("Font '%s' unavailable (%s); using default.", path, e)
        return ImageFont.load_default()


def _hex(h: str):
    try:
        n = int(h.replace("#", ""), 16)
        return (n >> 16) & 255, (n >> 8) & 255, n & 255
    except (ValueError, AttributeError):
        return 0x6C, 0x5C, 0xE7


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:3]


def make(script: dict, variant: int = 0) -> str | None:
    try:
        return _make(script, variant)
    except Exception as e:  # pragma: no cover
        log.warning("Thumbnail generation failed (%s); continuing without it.", e)
        return None


def _make(script: dict, variant: int) -> str:
    centered = bool(variant % 2)
    r, g, b = _hex(script.get("accent", "#6C5CE7"))
    img = Image.new("RGB", (W, H), (11, 13, 23))

    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    if centered:
        gd.ellipse([340, -300, 940, 360], fill=(r, g, b, 110))
    else:
        gd.ellipse([820, -260, 1480, 400], fill=(r, g, b, 120))
        gd.ellipse([-260, 380, 360, 1000], fill=(r, g, b, 70))
    img = Image.alpha_composite(img.convert("RGBA"),
                                glow.filter(ImageFilter.GaussianBlur(120))).convert("RGB")
    d = ImageDraw.Draw(img, "RGBA")

    for x in range(0, W, 96):
        d.line([(x, 0), (x, H)], fill=(255, 255, 255, 10), width=1)
    for y in range(0, H, 96):
        d.line([(0, y), (W, y)], fill=(255, 255, 255, 10), width=1)

    chip = _font(BOLD, 34)
    label = str(script.get("topic_title", "AI Update")).upper()
    tw = d.textlength(label, font=chip)
    cx = (W - (tw + 90)) / 2 if centered else 70
    d.rounded_rectangle([cx, 70, cx + tw + 90, 140], radius=35,
                        fill=(255, 255, 255, 20), outline=(r, g, b, 255), width=3)
    d.ellipse([cx + 30, 96, cx + 50, 116], fill=(r, g, b, 255))
    d.text((cx + 65, 86), label, font=chip, fill=(255, 255, 255))

    title_font = _font(BOLD, 92)
    lines = _wrap(d, str(script.get("title", "")), title_font, W - 140)
    y = 230
    for ln in lines:
        lw = d.textlength(ln, font=title_font)
        x = (W - lw) / 2 if centered else 70
        d.text((x + 2, y + 4), ln, font=title_font, fill=(0, 0, 0, 160))
        d.text((x, y), ln, font=title_font, fill=(255, 255, 255))
        y += 104

    d.line([(70, 632), (1210, 632)], fill=(255, 255, 255, 30), width=2)
    d.arc([72, 648, 132, 708], start=0, end=300, fill=(r, g, b, 255), width=8)
    d.polygon([(96, 666), (96, 690), (118, 678)], fill=(255, 255, 255))
    d.text((150, 656), "THE AI MINUTE", font=_font(BOLD, 40), fill=(255, 255, 255))
    d.text((690, 662), "New AI Short · every day", font=_font(REG, 30), fill=(174, 180, 214))

    img.save(THUMB_FILE)
    log.info("Thumbnail written (variant=%d): %s", variant, THUMB_FILE)
    return str(THUMB_FILE)


if __name__ == "__main__":  # pragma: no cover
    import json
    s = json.loads(config.SCRIPT_FILE.read_text(encoding="utf-8"))
    print("thumbnail:", make(s))
