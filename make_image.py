
import json
import os
import urllib.request
from pathlib import Path
from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont, ImageOps

WIDTH, HEIGHT = 1080, 1350

BG = (8, 17, 40)
RED = (224, 20, 48)
YELLOW = (255, 211, 0)
WHITE = (255, 255, 255)

NEWS_FILE = Path("news.json")
IMAGE_DIR = Path("news_images")
IMAGE_DIR.mkdir(exist_ok=True)

# Nepali font
NEPALI_REGULAR = [
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
]

NEPALI_BOLD = [
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
]

# English font
ENGLISH_REGULAR = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
]

ENGLISH_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
]


def load_font(paths, size):
    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(
                path,
                size,
                layout_engine=ImageFont.Layout.RAQM
            )

    return ImageFont.load_default()


def get_nepali_font(size, bold=False):
    return load_font(
        NEPALI_BOLD if bold else NEPALI_REGULAR,
        size
    )


def get_english_font(size, bold=False):
    return load_font(
        ENGLISH_BOLD if bold else ENGLISH_REGULAR,
        size
    )


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

        return (
            f"{nepali_number(today.year)} "
            f"{months[today.month - 1]} "
            f"{nepali_number(today.day)} गते"
        )

    except Exception as error:
        print("NEPALI DATE ERROR:", error)
        return "मिति उपलब्ध छैन"


def download_photo(url):
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
            data = response.read()

        return Image.open(
            BytesIO(data)
        ).convert("RGB")

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

    return ImageOps.fit(
        image,
        (WIDTH, 700),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.35)
    )


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

    if current:
        lines.append(current)

    return lines


def draw_centered(draw, text, y, font, fill):
    draw.text(
        (WIDTH // 2, y),
        text,
        font=font,
        fill=fill,
        anchor="mt"
    )


def draw_headline(draw, title):
    x = 58
    y = 735
    max_width = 964

    lines = []

    for size in range(82, 39, -2):
        font = get_nepali_font(size, True)

        lines = wrap_text(
            draw,
            title,
            font,
            max_width
        )

        line_height = int(size * 1.30)

        if (
            len(lines) <= 4
            and y + len(lines) * line_height <= 1080
        ):
            break

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


def draw_comment_label(draw):
    text = "पूरा समाचार कमेन्टमा"

    # Text अनुसार Highlight को आकार
    font_size = 30
    font = get_nepali_font(font_size, True)

    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font
    )

    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    padding_x = 18
    padding_y = 13

    box_width = text_width + padding_x * 2
    box_height = text_height + padding_y * 2

    x = 60
    y = 1120

    draw.rounded_rectangle(
        (
            x,
            y,
            x + box_width,
            y + box_height
        ),
        radius=10,
        fill=YELLOW
    )

    draw.text(
        (
            x + padding_x,
            y + padding_y - bbox[1]
        ),
        text,
        font=font,
        fill=BG
    )


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

    canvas = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        BG
    )

    # News photo
    photo = fit_photo(
        download_photo(image_url)
    )

    canvas.paste(photo, (0, 0))

    # Photo gradient
    gradient = Image.new(
        "RGBA",
        (WIDTH, 250),
        (0, 0, 0, 0)
    )

    pixels = gradient.load()

    for y in range(250):
        alpha = int(210 * (y / 249))

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

    # Top border
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
        font=get_nepali_font(36, True),
        fill=WHITE
    )

    # Nepali date
    date_text = get_nepali_date()
    date_font = get_nepali_font(27, True)

    date_bbox = draw.textbbox(
        (0, 0),
        date_text,
        font=date_font
    )

    date_width = date_bbox[2] - date_bbox[0]

    date_box_width = date_width + 40
    date_x = WIDTH - 40 - date_box_width

    draw.rounded_rectangle(
        (
            date_x,
            40,
            WIDTH - 40,
            102
        ),
        radius=14,
        fill=BG
    )

    draw.text(
        (
            date_x + 20,
            54 - date_bbox[1]
        ),
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

    # Underline
    underline_y = min(
        max(end_y + 8, 1085),
        1095
    )

    draw.rectangle(
        (60, underline_y, 265, underline_y + 8),
        fill=RED
    )

    # Automatically sized comment highlight
    draw_comment_label(draw)

    # Footer
    draw.rectangle(
        (0, 1210, WIDTH, HEIGHT),
        fill=RED
    )

    footer1 = "PLEASE LIKE, SHARE & FOLLOW US AT"
    footer2 = "fb.com/ilovechitwan"

    # English fonts separately
    footer_font1 = get_english_font(28, True)
    footer_font2 = get_english_font(48, True)

    draw_centered(
        draw,
        footer1,
        1230,
        footer_font1,
        WHITE
    )

    draw_centered(
        draw,
        footer2,
        1290,
        footer_font2,
        WHITE
    )

    # Save
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
