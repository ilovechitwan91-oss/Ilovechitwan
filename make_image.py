
import json
import os
import re
import urllib.request
from pathlib import Path
from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo

from PIL import (
    Image, ImageDraw, ImageFont,
    ImageOps, ImageFilter
)

WIDTH, HEIGHT = 1080, 1350

BG = (8, 17, 40)
RED = (224, 20, 48)
YELLOW = (255, 211, 0)
WHITE = (255, 255, 255)

NEWS_FILE = Path("news.json")
IMAGE_DIR = Path("news_images")

IMAGE_DIR.mkdir(exist_ok=True)

# Nepali fonts
FONT_REGULAR = [
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
]

FONT_BOLD = [
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
]


def get_font(size, bold=False):
    paths = FONT_BOLD if bold else FONT_REGULAR

    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(
                path, size,
                layout_engine=ImageFont.Layout.RAQM
            )

    return ImageFont.load_default()


def nepali_number(number):
    digits = "०१२३४५६७८९"
    return "".join(
        digits[int(x)] if x.isdigit() else x
        for x in str(number)
    )


def get_nepali_date():

    try:
        import nepali_datetime

        today = nepali_datetime.date.today()

        months = [
            "बैशाख", "जेठ", "असार", "साउन",
            "भदौ", "असोज", "कात्तिक", "मंसिर",
            "पुष", "माघ", "फागुन", "चैत"
        ]

        month = months[today.month - 1]

        return (
            f"{nepali_number(today.year)} "
            f"{month} "
            f"{nepali_number(today.day)} गते"
        )

    except Exception:

        return datetime.now(
            ZoneInfo("Asia/Kathmandu")
        ).strftime("%Y-%m-%d")


def download_photo(url):

    if not url:
        return None

    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        with urllib.request.urlopen(
            request, timeout=25
        ) as response:

            data = response.read()

        image = Image.open(
            BytesIO(data)
        ).convert("RGB")

        return image

    except Exception as error:

        print("PHOTO DOWNLOAD ERROR:", error)
        return None


def fit_photo(image):

    if image is None:
        image = Image.new(
            "RGB",
            (WIDTH, 700),
            (20, 35, 65)
        )

    image = ImageOps.fit(
        image,
        (WIDTH, 700),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.35)
    )

    return image


def wrap_text(draw, text, font, max_width):

    words = str(text).split()
    lines = []
    current = ""

    for word in words:

        test = (
            current + " " + word
        ).strip()

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

    if current:
        lines.append(current)

    return lines


def draw_headline(draw, title):

    x = 58
    y = 735
    max_width = 964

    # Fit headline into available space
    for size in range(82, 45, -2):

        font = get_font(size, True)

        lines = wrap_text(
            draw,
            title,
            font,
            max_width
        )

        line_height = int(size * 1.38)

        if (
            len(lines) <= 4
            and y + len(lines) * line_height <= 1085
        ):
            break

    # First line yellow, remaining lines white
    for index, line in enumerate(lines):

        color = YELLOW if index == 0 else WHITE

        draw.text(
            (x, y),
            line,
            font=font,
            fill=color,
            stroke_width=1,
            stroke_fill=color
        )

        y += line_height

    return y


def create_card(article, index):

    title = (
        article.get("title") or ""
    ).strip()

    image_url = (
        article.get("image_url") or ""
    ).strip()

    if not title:
        print("Skipping empty title:", index)
        return

    print("Creating news card:", title)

    # Create canvas
    canvas = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        BG
    )

    # Download and crop news photo
    photo = download_photo(image_url)
    photo = fit_photo(photo)

    canvas.paste(photo, (0, 0))

    # Dark gradient on lower part of photo
    gradient = Image.new(
        "RGBA",
        (WIDTH, 250),
        (0, 0, 0, 0)
    )

    pixels = gradient.load()

    for y in range(250):

        alpha = int(
            210 * (y / 249)
        )

        for x in range(WIDTH):
            pixels[x, y] = (
                8, 17, 40, alpha
            )

    canvas.paste(
        gradient,
        (0, 450),
        gradient
    )

    draw = ImageDraw.Draw(canvas)

    # Top red border
    draw.rectangle(
        (0, 0, WIDTH, 15),
        fill=RED
    )

    # Breaking news label
    draw.rounded_rectangle(
        (40, 40, 265, 102),
        radius=14,
        fill=RED
    )

    draw.text(
        (75, 48),
        "ताजा खबर",
        font=get_font(36, True),
        fill=WHITE
    )

    # Nepali date
    date_text = get_nepali_date()

    draw.rounded_rectangle(
        (695, 40, 1040, 102),
        radius=14,
        fill=BG
    )

    date_font = get_font(29, True)

    draw.text(
        (720, 54),
        date_text,
        font=date_font,
        fill=WHITE
    )

    # Lower news panel
    draw.rectangle(
        (0, 650, WIDTH, 1210),
        fill=BG
    )

    # Headline
    end_y = draw_headline(
        draw,
        title
    )

    # Red underline
    underline_y = min(
        max(end_y + 8, 1085),
        1095
    )

    draw.rectangle(
        (60, underline_y, 265, underline_y + 9),
        fill=RED
    )

    # Yellow comment label
    draw.rounded_rectangle(
        (60, 1120, 445, 1195),
        radius=9,
        fill=YELLOW
    )

    draw.text(
        (78, 1133),
        "पूरा समाचार कमेन्टमा",
        font=get_font(34, True),
        fill=BG
    )

    # Red footer
    draw.rectangle(
        (0, 1210, WIDTH, HEIGHT),
        fill=RED
    )

    footer1 = "Please like, share & follow us at"
    footer2 = "fb.com/ilovechitwan"

    draw.text(
        (WIDTH // 2, 1230),
        footer1,
        font=get_font(34, True),
        fill=WHITE,
        anchor="mt"
    )

    draw.text(
        (WIDTH // 2, 1290),
        footer2,
        font=get_font(52, True),
        fill=WHITE,
        anchor="mt"
    )

    # Save image
    output = IMAGE_DIR / f"news_{index:02d}.jpg"

    canvas.save(
        output,
        "JPEG",
        quality=95,
        optimize=True
    )

    print("CARD SAVED:", output)


def main():

    if not NEWS_FILE.exists():
        raise FileNotFoundError(
            "news.json not found!"
        )

    data = json.loads(
        NEWS_FILE.read_text(
            encoding="utf-8"
        )
    )

    articles = data.get("articles", [])

    if not articles:
        print("No news available.")
        return

    for index, article in enumerate(
        articles[:10],
        start=1
    ):

        try:
            create_card(article, index)

        except Exception as error:
            print(
                "CARD ERROR:",
                index,
                error
            )

    print("ALL NEWS CARDS COMPLETED!")


if __name__ == "__main__":
    main()
