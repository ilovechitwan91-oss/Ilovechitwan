
import os
import json
import glob
from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo

import urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageOps, features

WIDTH = 1080
HEIGHT = 1350

BG = (3, 18, 43)
CYAN = (75, 220, 235)
WHITE = (255, 255, 255)
RED = (225, 12, 38)

os.makedirs("news_images", exist_ok=True)


def find_font(patterns):
    for pattern in patterns:
        matches = glob.glob(pattern, recursive=True)
        if matches:
            return matches[0]
    return None


NEPALI_FONT = find_font([
    "/usr/share/fonts/**/*Devanagari*Bold*.ttf",
    "/usr/share/fonts/**/*Devanagari*Regular*.ttf"
])

ENGLISH_FONT = find_font([
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
])

ENGLISH_BOLD = find_font([
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
])


def font(size, bold=False, nepali=False):
    path = None

    if nepali and NEPALI_FONT:
        path = NEPALI_FONT
    elif bold:
        path = ENGLISH_BOLD
    else:
        path = ENGLISH_FONT

    if not path:
        return ImageFont.load_default()

    if features.check_feature("raqm"):
        return ImageFont.truetype(
            path, size,
            layout_engine=ImageFont.Layout.RAQM
        )

    return ImageFont.truetype(path, size)


def has_nepali(text):
    return any(
        "\u0900" <= char <= "\u097F"
        for char in str(text)
    )


def get_font(text, size, bold=False):
    return font(
        size,
        bold=bold,
        nepali=has_nepali(text)
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

    except Exception as error:
        print("Nepali date error:", error)
        return datetime.now(
            ZoneInfo("Asia/Kathmandu")
        ).strftime("%Y-%m-%d")


def wrap_text(draw, text, selected_font, max_width):
    words = str(text).split()
    lines = []
    current = ""

    for word in words:
        test = (current + " " + word).strip()

        if draw.textbbox(
            (0, 0), test, font=selected_font
        )[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines


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
        print("Photo error:", error)
        return None


def create_card(article, number):
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)

    # Header
    draw.rectangle((0, 0, WIDTH, 145), fill=(2, 24, 55))
    draw.polygon(
        [(35, 40), (105, 40), (90, 120), (35, 120)],
        fill=RED
    )

    draw.line((112, 43, 92, 118), fill=RED, width=9)
    draw.line((132, 43, 112, 118), fill=RED, width=9)

    draw.rectangle((145, 48, 470, 112), fill=(245, 242, 225))
    draw.text(
        (158, 53),
        "NEWS UPDATE",
        font=font(42, True),
        fill=(15, 25, 50)
    )

    # Nepali date
    date_text = nepali_date()

    draw.rounded_rectangle(
        (735, 45, 1045, 115),
        radius=18,
        fill=WHITE
    )

    draw.text(
        (750, 62),
        date_text,
        font=get_font(date_text, 27, True),
        fill=(0, 0, 0)
    )

    # Main photo
    draw.rectangle(
        (30, 160, 1050, 715),
        fill=(15, 55, 85)
    )

    photo = download_image(article.get("image_url", ""))

    if photo:
        photo = ImageOps.contain(
            photo,
            (1000, 545),
            method=Image.Resampling.LANCZOS
        )

        px = (WIDTH - photo.width) // 2
        py = 165 + (540 - photo.height) // 2
        image.paste(photo, (px, py))

    else:
        draw.text(
            (320, 400),
            "NEWS PHOTO UNAVAILABLE",
            font=font(35, True),
            fill=WHITE
        )

    draw.rectangle(
        (30, 160, 1050, 715),
        outline=(90, 170, 205),
        width=3
    )

    # Red side line
    draw.ellipse((50, 755, 94, 799), fill=RED)
    draw.rectangle((63, 785, 81, 1165), fill=RED)

    # Headline
    headline = (
        article.get("english_title")
        or article.get("title")
        or "LATEST NEWS UPDATE"
    )

    headline_font = get_font(headline, 43, True)

    headline_lines = wrap_text(
        draw, headline, headline_font, 920
    )[:3]

    y = 760

    for line in headline_lines:
        draw.text(
            (108, y),
            line,
            font=headline_font,
            fill=CYAN
        )
        y += 58

    # Description
    description = (
        article.get("english_description")
        or article.get("description")
        or ""
    )

    description_font = get_font(description, 27)

    description_lines = wrap_text(
        draw, description, description_font, 900
    )[:5]

    y += 20

    for line in description_lines:
        if y > 1145:
            break

        draw.text(
            (108, y),
            line,
            font=description_font,
            fill=WHITE
        )
        y += 40

    # Footer
    draw.rectangle((0, 1180, WIDTH, HEIGHT), fill=RED)

    if os.path.exists("logo.jpg"):
        try:
            logo = Image.open("logo.jpg").convert("RGB")
            logo = ImageOps.fit(logo, (120, 120))
            image.paste(logo, (35, 1200))
        except Exception as error:
            print("Logo error:", error)

    draw.text(
        (185, 1205),
        "ILOVECHITWAN",
        font=font(37, True),
        fill=WHITE
    )

    draw.text(
        (185, 1255),
        "NEWS AND UPDATES",
        font=font(23, True),
        fill=WHITE
    )

    source = str(article.get("source", "News"))

    draw.text(
        (185, 1293),
        "Source: " + source,
        font=font(21),
        fill=WHITE
    )

    output = f"news_images/news_{number:02d}.jpg"

    image.save(output, "JPEG", quality=95)

    print("Created:", output)


def main():
    if not NEPALI_FONT:
        raise RuntimeError(
            "Noto Sans Devanagari font not found"
        )

    if not features.check_feature("raqm"):
        raise RuntimeError(
            "Pillow RAQM support missing. Nepali shaping unavailable."
        )

    if not os.path.exists("news.json"):
        raise FileNotFoundError("news.json missing")

    with open("news.json", "r", encoding="utf-8") as file:
        data = json.load(file)

    articles = data.get("articles", [])

    if not articles:
        raise ValueError("No news articles found")

    for number, article in enumerate(articles[:10], 1):
        create_card(article, number)

    print("ALL NEWS CARDS COMPLETED")


if __name__ == "__main__":
    main()
