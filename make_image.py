
import os
import json
import glob
import re
import urllib.request
from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont, ImageOps, features

WIDTH, HEIGHT = 1080, 1350

BG = (4, 17, 39)
PANEL = (8, 32, 65)
CYAN = (75, 220, 235)
WHITE = (255, 255, 255)
RED = (225, 12, 38)
MUTED = (190, 210, 225)

os.makedirs("news_images", exist_ok=True)

ASSET = "FB_IMG_1794663825968.jpg"

PAGE_NAME = "HAMRO CHITWAN RAMRO CHITWAN"
FACEBOOK = "www.fb.com/ilovechitwan"


def find_font(patterns):
    for pattern in patterns:
        matches = glob.glob(pattern, recursive=True)
        if matches:
            return matches[0]
    return None


NEPALI_FONT = find_font([
    "/usr/share/fonts/**/*NotoSansDevanagari-Bold.ttf",
    "/usr/share/fonts/**/*NotoSansDevanagari-Regular.ttf",
    "/usr/share/fonts/**/*Devanagari*Bold*.ttf",
    "/usr/share/fonts/**/*Devanagari*Regular*.ttf"
])

ENGLISH_FONT = find_font([
    "/usr/share/fonts/**/*DejaVuSans.ttf"
])

ENGLISH_BOLD = find_font([
    "/usr/share/fonts/**/*DejaVuSans-Bold.ttf"
])


def get_font(text, size, bold=False):
    if any("\u0900" <= c <= "\u097F" for c in str(text)):
        path = NEPALI_FONT
    else:
        path = ENGLISH_BOLD if bold else ENGLISH_FONT

    if not path:
        return ImageFont.load_default()

    return ImageFont.truetype(
        path,
        size,
        layout_engine=ImageFont.Layout.RAQM
    )


def nepali_date():
    try:
        import nepali_datetime

        today = datetime.now(
            ZoneInfo("Asia/Kathmandu")
        ).date()

        nd = nepali_datetime.date.from_datetime_date(today)

        months = [
            "बैशाख", "जेठ", "असार", "साउन",
            "भदौ", "असोज", "कार्तिक", "मंसिर",
            "पुष", "माघ", "फागुन", "चैत"
        ]

        return f"{nd.year} {months[nd.month - 1]} {nd.day}"

    except Exception:
        return datetime.now(
            ZoneInfo("Asia/Kathmandu")
        ).strftime("%Y-%m-%d")


def wrap_text(draw, text, font, max_width):
    words = str(text).split()
    lines = []
    current = ""

    for word in words:
        test = (current + " " + word).strip()
        box = draw.textbbox((0, 0), test, font=font)

        if box[2] - box[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
                current = word
            else:
                lines.append(word)
                current = ""

    if current:
        lines.append(current)

    return lines


def fit_text(
    draw, text, x, y, width, height,
    start_size, min_size, max_lines, color, bold=False
):
    text = str(text or "").strip()

    if not text:
        return y

    # Try largest possible font first
    for size in range(start_size, min_size - 1, -1):

        font = get_font(text, size, bold)
        lines = wrap_text(draw, text, font, width)

        line_height = int(size * 1.45)

        if (
            len(lines) <= max_lines
            and len(lines) * line_height <= height
        ):
            for line in lines:
                draw.text(
                    (x, y),
                    line,
                    font=font,
                    fill=color
                )
                y += line_height

            return y

    # Minimum font size fallback
    size = min_size
    font = get_font(text, size, bold)

    lines = wrap_text(draw, text, font, width)
    line_height = int(size * 1.35)

    allowed = max(
        1,
        min(max_lines, height // line_height)
    )

    lines = lines[:allowed]

    if lines:
        last = lines[-1]

        while last and draw.textbbox(
            (0, 0), last + "...", font=font
        )[2] > width:
            last = last[:-1]

        lines[-1] = last.rstrip() + "..."

    for line in lines:
        draw.text(
            (x, y),
            line,
            font=font,
            fill=color
        )
        y += line_height

    return y


def get_news_description(article):
    fields = [
        "english_description",
        "description",
        "summary",
        "content",
        "full_text",
        "news_content"
    ]

    parts = []
    seen = set()

    for field in fields:
        value = str(article.get(field) or "").strip()

        if not value:
            continue

        value = re.sub(r"\s+", " ", value)

        key = value.lower()

        if key not in seen:
            parts.append(value)
            seen.add(key)

    if not parts:
        return "More details about this news will be updated soon."

    return "\n\n".join(parts)


def load_local_photo():
    if not os.path.isfile(ASSET):
        print("ERROR: Default photo missing:", ASSET)
        return None

    try:
        return Image.open(ASSET).convert("RGB")

    except Exception as error:
        print("Asset error:", error)
        return None


def download_image(url):
    if not url:
        return None

    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        with urllib.request.urlopen(
            request, timeout=25
        ) as response:

            data = response.read(12 * 1024 * 1024 + 1)

        if len(data) > 12 * 1024 * 1024:
            return None

        return Image.open(
            BytesIO(data)
        ).convert("RGB")

    except Exception as error:
        print("News photo error:", error)
        return None


def add_logo(image, position, size):
    logo = load_local_photo()

    if logo is None:
        print("Logo could not be loaded")
        return

    logo = ImageOps.fit(
        logo,
        size,
        method=Image.Resampling.LANCZOS
    )

    mask = Image.new("L", size, 0)
    mask_draw = ImageDraw.Draw(mask)

    mask_draw.rounded_rectangle(
        (0, 0, size[0] - 1, size[1] - 1),
        radius=15,
        fill=255
    )

    image.paste(logo, position, mask)


def create_card(article, number):

    image = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        BG
    )

    draw = ImageDraw.Draw(image)

    # =================================
    # HEADER
    # =================================

    draw.rectangle(
        (0, 0, WIDTH, 145),
        fill=(2, 25, 56)
    )

    draw.rounded_rectangle(
        (22, 17, 135, 128),
        radius=16,
        fill=WHITE
    )

    add_logo(
        image,
        (27, 22),
        (103, 101)
    )

    draw = ImageDraw.Draw(image)

    draw.text(
        (153, 20),
        "HAMRO CHITWAN",
        font=get_font("HAMRO CHITWAN", 38, True),
        fill=WHITE
    )

    draw.text(
        (155, 70),
        "RAMRO CHITWAN",
        font=get_font("RAMRO CHITWAN", 32, True),
        fill=CYAN
    )

    date_text = nepali_date()

    draw.rounded_rectangle(
        (755, 43, 1050, 105),
        radius=15,
        fill=WHITE
    )

    draw.text(
        (770, 59),
        date_text,
        font=get_font(date_text, 24, True),
        fill=BG
    )

    # =================================
    # NEWS PHOTO
    # =================================

    photo = download_image(
        article.get("image_url", "")
    )

    if photo is None:
        print("Using uploaded FB_IMG photo as default")
        photo = load_local_photo()

    if photo is not None:

        photo = ImageOps.fit(
            photo,
            (1000, 405),
            method=Image.Resampling.LANCZOS
        )

        image.paste(photo, (40, 155))

    else:
        draw.rectangle(
            (40, 155, 1040, 560),
            fill=PANEL
        )

    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        (38, 153, 1042, 562),
        radius=12,
        outline=CYAN,
        width=3
    )

    # =================================
    # NEWS PANEL
    # =================================

    draw.rounded_rectangle(
        (28, 580, 1052, 1185),
        radius=20,
        fill=PANEL
    )

    # News label

    draw.rounded_rectangle(
        (52, 597, 280, 643),
        radius=10,
        fill=RED
    )

    draw.text(
        (72, 607),
        "LATEST NEWS",
        font=get_font("LATEST NEWS", 22, True),
        fill=WHITE
    )

    # =================================
    # HEADLINE
    # =================================

    headline = (
        article.get("english_title")
        or article.get("title")
        or "LATEST NEWS UPDATE"
    )

    y = fit_text(
        draw,
        headline,
        58, 665,
        960, 140,
        50, 32, 3,
        CYAN,
        True
    )

    # Separator

    separator_y = y + 8

    draw.line(
        (58, separator_y, 1020, separator_y),
        fill=(75, 115, 155),
        width=2
    )

    # =================================
    # NEWS DESCRIPTION
    # =================================

    description = get_news_description(article)

    description_y = separator_y + 17

    available_height = 1160 - description_y

    fit_text(
        draw,
        description,
        58,
        description_y,
        960,
        available_height,
        34,
        24,
        25,
        WHITE,
        False
    )

    # =================================
    # FOOTER
    # =================================

    draw.rectangle(
        (0, 1200, WIDTH, HEIGHT),
        fill=RED
    )

    draw.rounded_rectangle(
        (25, 1213, 145, 1338),
        radius=15,
        fill=WHITE
    )

    add_logo(
        image,
        (30, 1218),
        (110, 115)
    )

    draw = ImageDraw.Draw(image)

    draw.text(
        (165, 1215),
        "HAMRO CHITWAN RAMRO CHITWAN",
        font=get_font(PAGE_NAME, 27, True),
        fill=WHITE
    )

    draw.text(
        (165, 1260),
        FACEBOOK,
        font=get_font(FACEBOOK, 25, True),
        fill=WHITE
    )

    draw.text(
        (165, 1305),
        "FOLLOW FOR LATEST NEWS & UPDATES",
        font=get_font(
            "FOLLOW FOR LATEST NEWS & UPDATES",
            19,
            True
        ),
        fill=WHITE
    )

    # =================================
    # SAVE
    # =================================

    output = f"news_images/news_{number:02d}.jpg"

    image.save(
        output,
        "JPEG",
        quality=95,
        optimize=True
    )

    print("Created:", output)


def main():

    if not NEPALI_FONT:
        raise RuntimeError(
            "Noto Sans Devanagari font not found"
        )

    if not features.check_feature("raqm"):
        raise RuntimeError(
            "Pillow RAQM support missing"
        )

    if not os.path.exists("news.json"):
        raise FileNotFoundError("news.json missing")

    if not os.path.exists(ASSET):
        raise FileNotFoundError(
            "Upload FB_IMG_1794663825968.jpg to repository root"
        )

    with open(
        "news.json",
        "r",
        encoding="utf-8"
    ) as file:
        data = json.load(file)

    articles = data.get("articles", [])

    if not articles:
        raise ValueError("No news articles found")

    print("Using Logo and Default Photo:", ASSET)

    for number, article in enumerate(
        articles[:10], 1
    ):
        create_card(article, number)

    print("ALL 10 NEWS CARDS COMPLETED")


if __name__ == "__main__":
    main()
