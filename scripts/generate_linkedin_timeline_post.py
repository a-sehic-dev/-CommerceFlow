"""Single LinkedIn timeline image for CommerceFlow."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
LOGO_PATH = ROOT / "static" / "linkedin-company-logo.png"
OUT_DIR = ROOT / "static" / "linkedin-carousel"
DESKTOP = Path.home() / "Desktop" / "CommerceFlow-LinkedIn-Slides"

W, H = 1080, 1350
M = 72

BASE = (7, 11, 23)
PANEL = (18, 25, 51)
ACCENT = (99, 102, 241)
ACCENT2 = (129, 140, 248)
WHITE = (255, 255, 255)
SLATE = (148, 163, 184)
SLATE_DIM = (100, 116, 139)

WEB = "commerceflow-1.onrender.com"
EMAIL = "commerceflow.platform@gmail.com"
FOUNDER = "Sedin Šehić"


def fonts() -> dict:
    bold = "C:/Windows/Fonts/segoeuib.ttf"
    regular = "C:/Windows/Fonts/segoeui.ttf"
    if Path(bold).exists():
        return {
            "brand": ImageFont.truetype(bold, 64),
            "hero": ImageFont.truetype(bold, 52),
            "heading": ImageFont.truetype(bold, 34),
            "body": ImageFont.truetype(regular, 28),
            "small": ImageFont.truetype(regular, 24),
            "label": ImageFont.truetype(bold, 20),
            "contact": ImageFont.truetype(bold, 26),
        }
    d = ImageFont.load_default()
    return {k: d for k in ("brand", "hero", "heading", "body", "small", "label", "contact")}


F = fonts()


def tw(text: str, font) -> int:
    b = font.getbbox(text)
    return b[2] - b[0]


def wrap(text: str, font, max_w: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if tw(trial, font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def multiline(draw, x, y, text, font, fill, max_w, gap=12) -> int:
    for line in wrap(text, font, max_w):
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + gap
    return y


def build() -> Image.Image:
    img = Image.new("RGB", (W, H), BASE)
    draw = ImageDraw.Draw(img)

    for r in range(560, 0, -6):
        t = 1 - r / 560
        draw.ellipse(
            (W // 2 - r, -100 - r // 3, W // 2 + r, 320 + r // 3),
            fill=(int(18 + 35 * t), int(16 + 25 * t), int(48 + 70 * t)),
        )

    # Logo
    logo_size = 140
    if LOGO_PATH.exists():
        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
        img.paste(logo, (M, M), logo)
        name_x = M + logo_size + 28
    else:
        name_x = M

    draw.text((name_x, M + 18), "CommerceFlow", font=F["brand"], fill=WHITE)
    draw.text((name_x, M + 88), "eCommerce Operations Intelligence", font=F["label"], fill=SLATE)

    draw.text((M, 268), "WHAT WE DO", font=F["label"], fill=ACCENT2)
    y = multiline(
        draw, M, 312,
        "Turn Shopify, WooCommerce & spreadsheet exports into executive dashboards, profit leakage alerts, and inventory intelligence.",
        F["hero"], WHITE, W - 2 * M, 8,
    )

    y += 28
    cap_h = 340
    draw.rounded_rectangle((M, y, W - M, y + cap_h), radius=28, fill=PANEL, outline=(99, 102, 241, 90))
    inner_y = y + 28
    draw.text((M + 32, inner_y), "CORE CAPABILITIES", font=F["label"], fill=SLATE_DIM)
    inner_y += 40
    bullets = [
        "Profit leakage — margins, discounts, pricing gaps",
        "Inventory risk — low stock, overstock, dead inventory",
        "Product intelligence — health scores & trends",
        "Executive Excel — KPIs, charts, audit-ready exports",
    ]
    for b in bullets:
        draw.rounded_rectangle((M + 32, inner_y + 8, M + 48, inner_y + 24), radius=4, fill=ACCENT)
        inner_y = multiline(draw, M + 64, inner_y, b, F["body"], SLATE, W - 2 * M - 96, 6) + 10

    footer_y = y + cap_h + 28
    footer_h = H - M - footer_y
    draw.rounded_rectangle((M, footer_y, W - M, H - M), radius=28, fill=(14, 18, 38), outline=(99, 102, 241, 70))

    draw.text((M + 36, footer_y + 32), "FOUNDED BY", font=F["label"], fill=SLATE_DIM)
    draw.text((M + 36, footer_y + 62), FOUNDER, font=F["heading"], fill=WHITE)

    draw.line((M + 36, footer_y + 118, W - M - 36, footer_y + 118), fill=(80, 90, 120))

    draw.text((M + 36, footer_y + 140), "WEB", font=F["label"], fill=SLATE_DIM)
    draw.text((M + 36, footer_y + 168), WEB, font=F["contact"], fill=ACCENT2)

    draw.text((M + 36, footer_y + 224), "EMAIL", font=F["label"], fill=SLATE_DIM)
    draw.text((M + 36, footer_y + 252), EMAIL, font=F["contact"], fill=ACCENT2)

    tag_y = footer_y + footer_h - 72
    draw.text((M + 36, tag_y), "Import  →  Analyze  →  Export", font=F["small"], fill=SLATE)
    draw.text((M + 36, tag_y + 34), "Deterministic analytics · No black-box AI", font=F["small"], fill=SLATE_DIM)

    return img


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DESKTOP.mkdir(parents=True, exist_ok=True)
    img = build()
    for dest in (
        OUT_DIR / "commerceflow-linkedin-timeline.png",
        DESKTOP / "commerceflow-linkedin-timeline.png",
    ):
        img.save(dest, "PNG", optimize=True)
        print(f"Wrote {dest}")


if __name__ == "__main__":
    main()
