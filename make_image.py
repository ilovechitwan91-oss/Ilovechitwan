
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


def has_nepali(text):
    return any("\u0900" <= c <= "\u097F" for c in str(text))


def get_font(text, size, bold=False):
    path = NEPALI_FONT if has_nepali(text) else (
        ENGLISH_BOLD if bold else ENGLISH_FONT
    )

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

    except Exception as error:
        print("Date error:", error)
        return datetime.now(
            ZoneInfo("Asia/Kathmandu")
        ).strftime("%Y-%m-%d")


def wrap_text(draw, text, selected_font, max_width):
    words = str(text).split()
    lines = []
    current = ""

    for word in words:
        test = (current + " " + word).strip()

        width = draw.textbbox(
            (0, 0), test, font=selected_font
        )[2]

        if width <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines


def fit_text(
    draw, text, x, y, width, height,
    start_size, min_size, max_lines,
    color, bold=False
):
    text = str(text or "").strip()

    if not text:
        return y

    for size in range(start_size, min_size - 1, -1):
        selected_font = get_font(text, size, bold)

        lines = wrap_text(
            draw, text, selected_font, width
        )

        line_height = int(size * 1.42)

        if (
            len(lines) <= max_lines
            and len(lines) * line_height <= height
        ):
            for line in lines:
                draw.text(
                    (x, y),
                    line,
                    font=selected_font,
                    fill=color
                )
                y += line_height

            return y

    raise ValueError(
        "News text is too long for the card. "
        "Please shorten the summary at a complete sentence."
    )


def complete_summary(text, max_chars=950):
    text = str(text or "").strip()

    if len(text) <= max_chars:
        return text

    sentences = re.split(
        r"(?<=[।.!?])\s+",
        text
    )

    result = []
    total = 0

    for sentence in sentences:
        sentence = sentence.strip()

        if not sentence:
            continue

        extra = len(sentence) + (1 if result else 0)

        if result and total + extra > max_chars:
            break

        result.append(sentence)
        total += extra

    return " ".join(result) if result else text


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

    # HEADER
    draw.rectangle(
        (0, 0, WIDTH, 145),
        fill=(2, 24, 55)
    )

    draw.polygon(
        [(35, 40), (105, 40), (90, 120), (35, 120)],
        fill=RED
    )

    draw.line((112, 43, 92, 118), fill=RED, width=9)
    draw.line((132, 43, 112, 118), fill=RED, width=9)

    draw.rectangle(
        (145, 45, 555, 115),
        fill=(245, 242, 225)
    )

    draw.text(
        (160, 53),
        "NEWS UPDATE",
        font=get_font("NEWS UPDATE", 40, True),
        fill=(15, 25, 50)
    )

    # NEPALI DATE
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

    # NEWS PHOTO
    draw.rectangle(
        (30, 160, 1050, 620),
        fill=(15, 55, 85)
    )

    photo = download_image(
        article.get("image_url", "")
    )

    if photo:
        photo = ImageOps.fit(
            photo,
            (1000, 450),
            method=Image.Resampling.LANCZOS
        )

        image.paste(photo, (40, 165))

    else:
        message = "NEWS PHOTO UNAVAILABLE"

        draw.text(
            (320, 365),
            message,
            font=get_font(message, 35, True),
            fill=WHITE
        )

    draw.rectangle(
        (30, 160, 1050, 620),
        outline=(90, 170, 205),
        width=3
    )

    # RED SIDE LINE
    draw.ellipse(
        (50, 655, 94, 699),
        fill=RED
    )

    draw.rectangle(
        (63, 685, 81, 1155),
        fill=RED
    )

    # HEADLINE
    headline = (
        article.get("english_title")
        or article.get("title")
        or "LATEST NEWS UPDATE"
    )

    y = fit_text(
        draw,
        headline,
        108, 650,
        900, 145,
        43, 27, 3,
        CYAN,
        True
    )

    # DESCRIPTION
    description = (
        article.get("english_description")
        or article.get("description")
        or ""
    )

    description = complete_summary(description, 950)

    y += 12

    available_height = 1160 - y

    fit_text(
        draw,
        description,
        108, y,
        900, available_height,
        27, 16, 22,
        WHITE,
        False
    )

    # FOOTER
    draw.rectangle(
        (0, 1180, WIDTH, HEIGHT),
        fill=RED
    )

    if os.path.exists("logo.jpg"):
        try:
            logo = Image.open(
                "logo.jpg"
            ).convert("RGB")

            logo = ImageOps.fit(
                logo, (120, 120)
            )

            image.paste(logo, (35, 1200))

        except Exception as error:
            print("Logo error:", error)

    draw.text(
        (185, 1205),
        "ILOVECHITWAN",
        font=get_font("ILOVECHITWAN", 37, True),
        fill=WHITE
    )

    draw.text(
        (185, 1255),
        "NEWS AND UPDATES",
        font=get_font("NEWS AND UPDATES", 23, True),
        fill=WHITE
    )

    source = str(article.get("source", "News"))

    draw.text(
        (185, 1293),
        "Source: " + source,
        font=get_font(source, 21),
        fill=WHITE
    )

    output = f"news_images/news_{number:02d}.jpg"

    image.save(
        output,
        "JPEG",
        quality=95
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

    with open(
        "news.json",
        "r",
        encoding="utf-8"
    ) as file:
        data = json.load(file)

    articles = data.get("articles", [])

    if not articles:
        raise ValueError("No news articles found")

    for number, article in enumerate(articles[:10], 1):
        create_card(article, number)

    print("ALL NEWS CARDS COMPLETED")


if __name__ == "__main__":
    main()
