
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


# =====================================
# FIND UPLOADED LOGO AND DEFAULT PHOTO
# =====================================

def find_asset(names):
    for name in names:
        if os.path.isfile(name):
            return name

    for name in names:
        matches = glob.glob(
            "**/" + name,
            recursive=True
        )
        matches = [
            p for p in matches
            if "news_images" not in p.replace("\\", "/")
        ]
        if matches:
            return matches[0]

    return None


LOGO_PATH = find_asset([
    "logo.jpg",
    "logo.jpeg",
    "logo.png",
    "Logo.jpg",
    "Logo.png",
    "rhino_logo.png",
    "rhino_logo.jpg"
])

DEFAULT_PHOTO_PATH = find_asset([
    "FB_IMG_1794663825968.jpg",
    "FB_IMG_1794663825968.jpeg",
    "default_photo.jpg",
    "default_photo.png",
    "fallback.jpg",
    "fallback.png"
])


# =====================================
# FONTS
# =====================================

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
    return any(
        "\u0900" <= c <= "\u097F"
        for c in str(text)
    )


def get_font(text, size, bold=False):
    if has_nepali(text):
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


# =====================================
# DATE
# =====================================

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


# =====================================
# TEXT WRAPPING
# =====================================

def wrap_text(draw, text, font, max_width):
    words = str(text).split()
    lines = []
    current = ""

    for word in words:
        test = (current + " " + word).strip()

        box = draw.textbbox(
            (0, 0),
            test,
            font=font
        )

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
    start_size, min_size, max_lines,
    color, bold=False
):
    text = str(text or "").strip()

    if not text:
        return y

    for size in range(start_size, min_size - 1, -1):

        font = get_font(text, size, bold)

        lines = wrap_text(
            draw, text, font, width
        )

        line_height = int(size * 1.40)

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

    # If text is too long, fit as many lines as possible
    size = min_size
    font = get_font(text, size, bold)

    lines = wrap_text(
        draw, text, font, width
    )

    line_height = int(size * 1.35)

    allowed = min(
        max_lines,
        max(1, height // line_height)
    )

    lines = lines[:allowed]

    if lines:
        last = lines[-1]

        while last and draw.textbbox(
            (0, 0),
            last + "...",
            font=font
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


# =====================================
# IMAGE LOADING
# =====================================

def load_local_image(path):
    if not path or not os.path.isfile(path):
        return None

    try:
        return Image.open(path).convert("RGB")
    except Exception as error:
        print("Local image error:", error)
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
            request,
            timeout=25
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
    if not LOGO_PATH:
        print("WARNING: Logo file not found")
        return

    try:
        logo = Image.open(LOGO_PATH).convert("RGBA")

        logo.thumbnail(
            size,
            Image.Resampling.LANCZOS
        )

        x, y = position

        # Transparent background support
        image.paste(
            logo,
            (
                x + (size[0] - logo.width) // 2,
                y + (size[1] - logo.height) // 2
            ),
            logo
        )

    except Exception as error:
        print("Logo error:", error)


def prepare_photo(photo, size):
    photo = ImageOps.fit(
        photo,
        size,
        method=Image.Resampling.LANCZOS
    )

    return photo


# =====================================
# SUMMARY
# =====================================

def complete_summary(text, max_chars=1200):
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

    if result:
        return " ".join(result)

    return text[:max_chars]


# =====================================
# CREATE NEWS CARD
# =====================================

def create_card(article, number):

    image = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        BG
    )

    draw = ImageDraw.Draw(image)

    # ---------------------------------
    # HEADER
    # ---------------------------------

    draw.rectangle(
        (0, 0, WIDTH, 140),
        fill=(2, 25, 56)
    )

    # Logo in header
    draw.rounded_rectangle(
        (25, 18, 132, 122),
        radius=15,
        fill=WHITE
    )

    add_logo(
        image,
        (29, 22),
        (99, 96)
    )

    draw = ImageDraw.Draw(image)

    draw.text(
        (155, 25),
        "ILOVECHITWAN",
        font=get_font("ILOVECHITWAN", 39, True),
        fill=WHITE
    )

    draw.text(
        (158, 79),
        "NEWS AND UPDATES",
        font=get_font("NEWS AND UPDATES", 22, True),
        fill=CYAN
    )

    # Date
    date_text = nepali_date()

    draw.rounded_rectangle(
        (745, 35, 1050, 105),
        radius=17,
        fill=WHITE
    )

    date_font = get_font(date_text, 25, True)

    draw.text(
        (770, 55),
        date_text,
        font=date_font,
        fill=BG
    )

    # ---------------------------------
    # NEWS PHOTO
    # ---------------------------------

    photo = download_image(
        article.get("image_url", "")
    )

    if photo is None:
        print("Using uploaded default photo")

        photo = load_local_image(
            DEFAULT_PHOTO_PATH
        )

    if photo is not None:

        photo = prepare_photo(
            photo,
            (1000, 410)
        )

        image.paste(
            photo,
            (40, 155)
        )

    else:
        print(
            "ERROR: Both news photo and default photo missing"
        )

        draw.rectangle(
            (40, 155, 1040, 565),
            fill=PANEL
        )

        message = "ILOVECHITWAN NEWS"

        draw.text(
            (280, 330),
            message,
            font=get_font(message, 43, True),
            fill=CYAN
        )

    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        (38, 153, 1042, 567),
        radius=12,
        outline=CYAN,
        width=3
    )

    # ---------------------------------
    # NEWS INFORMATION PANEL
    # ---------------------------------

    draw.rounded_rectangle(
        (30, 585, 1050, 1185),
        radius=20,
        fill=PANEL
    )

    # Breaking/news label
    draw.rounded_rectangle(
        (55, 605, 285, 650),
        radius=10,
        fill=RED
    )

    draw.text(
        (75, 612),
        "LATEST NEWS",
        font=get_font("LATEST NEWS", 22, True),
        fill=WHITE
    )

    # ---------------------------------
    # HEADLINE
    # ---------------------------------

    headline = (
        article.get("english_title")
        or article.get("title")
        or "LATEST NEWS UPDATE"
    )

    headline = str(headline).strip()

    y = fit_text(
        draw,
        headline,
        60, 675,
        950, 145,
        42, 29, 3,
        CYAN,
        True
    )

    # Separator
    separator_y = y + 8

    draw.line(
        (60, separator_y, 1020, separator_y),
        fill=(65, 100, 135),
        width=2
    )

    # ---------------------------------
    # DESCRIPTION
    # ---------------------------------

    description = (
        article.get("english_description")
        or article.get("description")
        or article.get("summary")
        or article.get("content")
        or "More details about this news will be updated soon."
    )

    description = complete_summary(
        description,
        1200
    )

    description_y = separator_y + 20

    available_height = max(
        50,
        1160 - description_y
    )

    fit_text(
        draw,
        description,
        60,
        description_y,
        950,
        available_height,
        27,
        18,
        17,
        WHITE,
        False
    )

    # ---------------------------------
    # FOOTER
    # ---------------------------------

    draw.rectangle(
        (0, 1200, WIDTH, HEIGHT),
        fill=RED
    )

    # Footer logo
    draw.rounded_rectangle(
        (28, 1215, 140, 1335),
        radius=12,
        fill=WHITE
    )

    add_logo(
        image,
        (32, 1219),
        (104, 112)
    )

    draw = ImageDraw.Draw(image)

    draw.text(
        (165, 1218),
        "ILOVECHITWAN",
        font=get_font("ILOVECHITWAN", 36, True),
        fill=WHITE
    )

    draw.text(
        (165, 1265),
        "NEWS AND UPDATES",
        font=get_font("NEWS AND UPDATES", 23, True),
        fill=WHITE
    )

    source = str(
        article.get("source") or "News"
    )

    draw.text(
        (165, 1305),
        "Source: " + source[:55],
        font=get_font(source, 19),
        fill=WHITE
    )

    # ---------------------------------
    # SAVE
    # ---------------------------------

    output = (
        f"news_images/news_{number:02d}.jpg"
    )

    image.save(
        output,
        "JPEG",
        quality=95,
        optimize=True
    )

    print("Created:", output)


# =====================================
# MAIN
# =====================================

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
        raise FileNotFoundError(
            "news.json missing"
        )

    print("Logo:", LOGO_PATH)
    print("Default photo:", DEFAULT_PHOTO_PATH)

    if not LOGO_PATH:
        print("WARNING: Upload logo.jpg to repository root")

    if not DEFAULT_PHOTO_PATH:
        print(
            "WARNING: Default photo not found. "
            "Upload FB_IMG_1794663825968.jpg"
        )

    with open(
        "news.json",
        "r",
        encoding="utf-8"
    ) as file:
        data = json.load(file)

    articles = data.get("articles", [])

    if not articles:
        raise ValueError(
            "No news articles found"
        )

    for number, article in enumerate(
        articles[:10],
        1
    ):
        create_card(
            article,
            number
        )

    print("ALL NEWS CARDS COMPLETED")


if __name__ == "__main__":
    main()
