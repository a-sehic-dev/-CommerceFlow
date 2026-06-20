"""Generate 5 LinkedIn carousel slides (1080x1350 portrait) + PDF for upload."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "static" / "linkedin-carousel"
DESKTOP_OUT = Path.home() / "Desktop" / "CommerceFlow-LinkedIn-Slides"

# LinkedIn document carousel — portrait 4:5 (best mobile fit, no crop)
W, H = 1080, 1350
M = 80  # safe margin

BASE = (7, 11, 23)
PANEL = (18, 25, 51)
ACCENT = (99, 102, 241)
ACCENT2 = (129, 140, 248)
WHITE = (255, 255, 255)
SLATE = (148, 163, 184)
SLATE_DIM = (100, 116, 139)


def _fonts() -> dict[str, ImageFont.FreeTypeFont | ImageFont.ImageFont]:
    bold = "C:/Windows/Fonts/segoeuib.ttf"
    regular = "C:/Windows/Fonts/segoeui.ttf"
    mono = "C:/Windows/Fonts/consola.ttf"
    if Path(bold).exists():
        return {
            "hero": ImageFont.truetype(bold, 72),
            "title": ImageFont.truetype(bold, 52),
            "heading": ImageFont.truetype(bold, 36),
            "sub": ImageFont.truetype(bold, 28),
            "body": ImageFont.truetype(regular, 30),
            "small": ImageFont.truetype(regular, 24),
            "label": ImageFont.truetype(bold, 20),
            "mono": ImageFont.truetype(mono, 34),
            "mono_lg": ImageFont.truetype(mono, 44),
            "step": ImageFont.truetype(mono, 56),
        }
    default = ImageFont.load_default()
    return {k: default for k in ("hero", "title", "heading", "sub", "body", "small", "label", "mono", "mono_lg", "step")}


FONTS = _fonts()


def tw(text: str, font: ImageFont.ImageFont) -> int:
    b = font.getbbox(text)
    return b[2] - b[0]


def wrap(text: str, font: ImageFont.ImageFont, max_w: int) -> list[str]:
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


def multiline(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, font, fill, max_w: int, gap: int = 14) -> int:
    for line in wrap(text, font, max_w):
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + gap
    return y


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BASE)
    draw = ImageDraw.Draw(img)
    # full-bleed top glow
    for r in range(500, 0, -6):
        t = 1 - r / 500
        draw.ellipse(
            (W // 2 - r, -80 - r // 3, W // 2 + r, 280 + r // 3),
            fill=(int(20 + 30 * t), int(18 + 20 * t), int(50 + 60 * t)),
        )
    return img, draw


def logo(draw: ImageDraw.ImageDraw, x: int, y: int, s: float = 1.0) -> None:
    bars = [(0, 0.55, 0.4), (1, 0.35, 0.65), (2, 0.15, 0.85)]
    for i, top, h in bars:
        w = int(16 * s)
        left = x + int(i * 24 * s)
        ty = y + int(top * 70 * s)
        ht = int(h * 70 * s)
        shade = [100, 165, 255][i]
        draw.rounded_rectangle((left, ty, left + w, ty + ht), radius=int(4 * s), fill=(shade, shade, 255))
    pts = [(x + 6, y + int(48 * s)), (x + int(30 * s), y + int(24 * s)), (x + int(48 * s), y + int(34 * s)), (x + int(70 * s), y + int(10 * s))]
    draw.line(pts, fill=WHITE, width=max(2, int(3 * s)))
    draw.ellipse((pts[-1][0] - 4, pts[-1][1] - 4, pts[-1][0] + 4, pts[-1][1] + 4), fill=WHITE)


def header(draw: ImageDraw.ImageDraw, n: int) -> None:
    logo(draw, M, M, 1.2)
    draw.text((M + 92, M + 4), "CommerceFlow", font=FONTS["heading"], fill=WHITE)
    draw.text((M + 92, M + 46), "B2B Operational Intelligence", font=FONTS["label"], fill=SLATE)
    draw.rounded_rectangle((W - M - 72, M, W - M, M + 40), radius=20, fill=PANEL)
    draw.text((W - M - 58, M + 10), f"{n}/5", font=FONTS["label"], fill=SLATE)


def card(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int) -> None:
    draw.rounded_rectangle((x, y, x + w, y + h), radius=24, fill=PANEL, outline=(99, 102, 241, 90))


def slide_01() -> Image.Image:
    img, draw = canvas()
    header(draw, 1)
    draw.text((M, 260), "eCOMMERCE INTELLIGENCE", font=FONTS["label"], fill=ACCENT2)
    y = multiline(draw, M, 310, "Turn messy exports into operational intelligence.", FONTS["hero"], WHITE, W - 2 * M, 10)
    multiline(
        draw, M, y + 20,
        "Import → Analyze → Export insights from Shopify, WooCommerce, or spreadsheets.",
        FONTS["body"], SLATE, W - 2 * M, 8,
    )
    card(draw, M, 620, W - 2 * M, 620)
    draw.text((M + 28, 652), "EXECUTIVE OVERVIEW · DEMO", font=FONTS["label"], fill=SLATE_DIM)
    kpis = [("Revenue", "$42.8M"), ("Margin", "46.3%"), ("Inventory", "69.4%"), ("Risk", "88.2")]
    cw = (W - 2 * M - 56 - 36) // 4
    for i, (lab, val) in enumerate(kpis):
        cx = M + 28 + i * (cw + 12)
        draw.rounded_rectangle((cx, 700, cx + cw, 820), radius=16, fill=(14, 16, 22))
        draw.text((cx + 16, 718), lab.upper(), font=FONTS["label"], fill=SLATE_DIM)
        draw.text((cx + 16, 748), val, font=FONTS["mono_lg"], fill=WHITE)
    bars = [96, 95, 98, 90, 100, 98, 96, 96, 94, 94, 95, 99]
    base_y = 1180
    bw = (W - 2 * M - 56 - 11 * 8) // 12
    for i, h in enumerate(bars):
        bh = int(h * 2.4)
        bx = M + 28 + i * (bw + 8)
        color = ACCENT if i == 4 else (60, 65, 160)
        draw.rounded_rectangle((bx, base_y - bh, bx + bw, base_y), radius=6, fill=color)
    draw.text((M + 28, 870), "12-month revenue trend", font=FONTS["small"], fill=SLATE)
    draw.text((M, H - M - 30), "Deterministic analytics · No black-box AI", font=FONTS["small"], fill=SLATE_DIM)
    return img


def slide_02() -> Image.Image:
    img, draw = canvas()
    header(draw, 2)
    draw.text((M, 260), "THE PROBLEM", font=FONTS["label"], fill=ACCENT2)
    multiline(draw, M, 310, "Your data is everywhere. Your insights aren't.", FONTS["title"], WHITE, W - 2 * M, 12)
    pains = [
        ("Spreadsheets everywhere", "Products, sales, and inventory live in disconnected exports."),
        ("Profit leaks go unnoticed", "Low margins, discounts, and pricing gaps compound quietly."),
        ("Inventory risk builds up", "Dead stock, overstock, and stockouts hide in plain sight."),
        ("No time for complex BI", "Teams need answers today — not a 6-week analytics project."),
    ]
    y = 500
    ch = 175
    for title, desc in pains:
        card(draw, M, y, W - 2 * M, ch)
        draw.rounded_rectangle((M + 24, y + 24, M + 56, y + 56), radius=8, fill=ACCENT)
        draw.text((M + 32, y + 28), "!", font=FONTS["sub"], fill=WHITE)
        draw.text((M + 72, y + 28), title, font=FONTS["sub"], fill=WHITE)
        multiline(draw, M + 72, y + 72, desc, FONTS["body"], SLATE, W - 2 * M - 100, 6)
        y += ch + 20
    return img


def slide_03() -> Image.Image:
    img, draw = canvas()
    header(draw, 3)
    draw.text((M, 260), "HOW IT WORKS", font=FONTS["label"], fill=ACCENT2)
    draw.text((M, 310), "Three steps. One operational picture.", font=FONTS["title"], fill=WHITE)
    steps = [
        ("01", "Upload business data", "CSV, XLSX, Shopify & WooCommerce exports."),
        ("02", "Run CommerceFlow analysis", "Inventory risk, profit leakage, product intelligence."),
        ("03", "Explore & export reports", "Dashboards, alerts, and executive Excel workbooks."),
    ]
    y = 480
    sh = 240
    for num, title, desc in steps:
        card(draw, M, y, W - 2 * M, sh)
        draw.text((M + 32, y + 36), num, font=FONTS["step"], fill=(70, 75, 200))
        draw.text((M + 130, y + 40), title, font=FONTS["heading"], fill=WHITE)
        multiline(draw, M + 130, y + 100, desc, FONTS["body"], SLATE, W - 2 * M - 160, 8)
        y += sh + 24
    return img


def slide_04() -> Image.Image:
    img, draw = canvas()
    header(draw, 4)
    draw.text((M, 260), "KEY CAPABILITIES", font=FONTS["label"], fill=ACCENT2)
    draw.text((M, 310), "Built for ops & finance teams.", font=FONTS["title"], fill=WHITE)
    features = [
        "Inventory Intelligence",
        "Profit Leakage Detection",
        "Executive Dashboards",
        "Alerts & Recommendations",
        "CSV/XLSX Import Engine",
        "Enterprise Excel Reporting",
    ]
    y = 460
    for f in features:
        card(draw, M, y, W - 2 * M, 100)
        draw.rounded_rectangle((M + 24, y + 30, M + 56, y + 62), radius=8, fill=(ACCENT[0] // 3, ACCENT[1] // 3, ACCENT[2] // 2))
        draw.text((M + 34, y + 34), "◆", font=FONTS["sub"], fill=ACCENT2)
        draw.text((M + 72, y + 32), f, font=FONTS["sub"], fill=WHITE)
        y += 116
    draw.text((M, H - M - 40), "Deterministic engines · Transparent scoring · No AI API required", font=FONTS["small"], fill=SLATE)
    return img


def slide_05() -> Image.Image:
    img, draw = canvas()
    header(draw, 5)
    card(draw, M, 260, W - 2 * M, 980)
    draw.text((M + 40, 320), "READY TO SEE IT?", font=FONTS["label"], fill=ACCENT2)
    multiline(
        draw, M + 40, 370,
        "Turn messy eCommerce exports into operational intelligence.",
        FONTS["title"], WHITE, W - 2 * M - 80, 14,
    )
    tags = ["CSV/XLSX", "Profit Leakage", "Inventory Intel", "Executive Excel", "100k+ records tested"]
    ty = 620
    tx = M + 40
    for tag in tags:
        pill_w = tw(tag, FONTS["small"]) + 40
        if tx + pill_w > W - M - 40:
            tx = M + 40
            ty += 58
        draw.rounded_rectangle((tx, ty, tx + pill_w, ty + 48), radius=24, fill=(14, 16, 22), outline=(99, 102, 241, 80))
        draw.text((tx + 20, ty + 12), tag, font=FONTS["small"], fill=SLATE)
        tx += pill_w + 14
    draw.rounded_rectangle((M + 40, 860, M + 380, 940), radius=32, fill=ACCENT)
    draw.text((M + 72, 884), "Run Analysis →", font=FONTS["sub"], fill=WHITE)
    draw.text((M + 40, 980), "Open demo · Import sample data · Export your first report", font=FONTS["body"], fill=SLATE)
    draw.text((M + 40, 1040), "Built by Sedin Šehić", font=FONTS["small"], fill=SLATE_DIM)
    draw.text((M + 40, 1080), "commerceflow.platform@gmail.com", font=FONTS["small"], fill=SLATE_DIM)
    logo(draw, W - M - 120, 900, 2.0)
    return img


def save_pdf(images: list[Image.Image], path: Path) -> None:
    rgb = [im.convert("RGB") for im in images]
    rgb[0].save(path, "PDF", resolution=150.0, save_all=True, append_images=rgb[1:])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    DESKTOP_OUT.mkdir(parents=True, exist_ok=True)

    builders = [
        ("slide-01-cover.png", slide_01),
        ("slide-02-problem.png", slide_02),
        ("slide-03-how-it-works.png", slide_03),
        ("slide-04-features.png", slide_04),
        ("slide-05-cta.png", slide_05),
    ]
    images: list[Image.Image] = []
    for name, fn in builders:
        img = fn()
        images.append(img)
        p1 = OUT / name
        p2 = DESKTOP_OUT / name
        img.save(p1, "PNG", optimize=True)
        img.save(p2, "PNG", optimize=True)
        print(f"Wrote {p1}")
        print(f"Wrote {p2}")

    pdf_out = OUT / "CommerceFlow-LinkedIn-Carousel.pdf"
    pdf_desktop = DESKTOP_OUT / "CommerceFlow-LinkedIn-Carousel.pdf"
    save_pdf(images, pdf_out)
    save_pdf(images, pdf_desktop)
    print(f"Wrote {pdf_out}")
    print(f"Wrote {pdf_desktop}")
    print(f"\nUpload this PDF on LinkedIn: {pdf_desktop}")


if __name__ == "__main__":
    main()
