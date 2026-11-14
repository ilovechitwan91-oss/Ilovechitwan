
import os
import json
import urllib.request
from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont, ImageOps

WIDTH = 1080
HEIGHT = 1350

BG = (3, 18, 43)
CYAN = (75, 220, 235)
WHITE = (255, 255, 255)
RED = (225, 12, 38)
DARK = (0, 10, 25)

os.makedirs("news_images", exist_ok=True)


def font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
        if bold else
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]

    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


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
        print("Image download failed:", error)
        return None


def add_logo(image, draw):
    if not os.path.exists("logo.jpg"):
        print("logo.jpg not found")
        return

    try:
        logo = Image.open("logo.jpg").convert("RGB")
        logo.thumbnail((135, 135), Image.Resampling.LANCZOS)

        x = 35
        y = 1198

        image.paste(logo, (x, y))

    except Exception as error:
        print("Logo error:", error)


def create_card(article, number):
    image = Image.new(
        "RGB", (WIDTH, HEIGHT), BG
    )

    draw = ImageDraw.Draw(image)

    # TOP HEADER
    draw.rectangle(
        (0, 0, WIDTH, 145),
        fill=(2, 24, 55)
    )

    draw.polygon(
        [(35, 40), (105, 40), (90, 120), (35, 120)],
        fill=RED
    )

    draw.line(
        (112, 43, 92, 118),
        fill=RED,
        width=9
    )

    draw.line(
        (132, 43, 112, 118),
        fill=RED,
        width=9
    )

    draw.rectangle(
        (145, 48, 470, 112),
        fill=(245, 242, 225)
    )

    draw.text(
        (158, 53),
        "NEWS UPDATE",
        font=font(42, True),
        fill=(15, 25, 50)
    )

    # NEPALI DATE
    date_text = nepali_date()

    draw.rounded_rectangle(
        (735, 45, 1045, 115),
        radius=18,
        fill=WHITE
    )

    date_font = font(29, True)

    draw.text(
        (750, 62),
        date_text,
        font=date_font,
        fill=(0, 0, 0)
    )

    # MAIN NEWS PHOTO
    draw.rectangle(
        (30, 160, 1050, 715),
        fill=(15, 55, 85)
    )

    photo = download_image(
        article.get("image_url", "")
    )

    if photo:
        # Preserve the complete original photo.
        photo.thumbnail(
            (1000, 545),
            Image.Resampling.LANCZOS
        )

        px = (WIDTH - photo.width) // 2
        py = 165 + (540 - photo.height) // 2

        image.paste(photo, (px, py))

    else:
        draw.text(
            (320, 400),
            "NEWS UPDATE",
            font=font(55, True),
            fill=WHITE
        )

    draw.rectangle(
        (30, 160, 1050, 715),
        outline=(90, 170, 205),
        width=3
    )

    # RED SIDE LINE
    draw.ellipse(
        (50, 755, 94, 799),
        fill=RED
    )

    draw.rectangle(
        (63, 785, 81, 1165),
        fill=RED
    )

    # ENGLISH HEADLINE
    headline = (
        article.get("english_title")
        or article.get("title")
        or "LATEST NEWS UPDATE"
    )

    headline_font = font(43, True)

    headline_lines = wrap_text(
        draw, headline, headline_font, 920
    )[:3]

    y = 760

    for line in headline_lines:
        draw.text(
            (108, y),
            line,
            font=headline_font,
            fill=CYAN,
            stroke_width=1
        )
        y += 58

    # ENGLISH DESCRIPTION
    description = (
        article.get("english_description")
        or article.get("description")
        or ""
    )

    description_font = font(27)

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

    # FOOTER
    draw.rectangle(
        (0, 1180, WIDTH, HEIGHT),
        fill=RED
    )

    add_logo(image, draw)

    draw.text(
        (195, 1205),
        "ILOVECHITWAN",
        font=font(37, True),
        fill=WHITE
    )

    draw.text(
        (195, 1255),
        "NEWS AND UPDATES",
        font=font(23, True),
        fill=WHITE
    )

    source = article.get("source", "News")

    draw.text(
        (195, 1293),
        "Source: " + str(source),
        font=font(21),
        fill=WHITE
    )

    output = f"news_images/news_{number:02d}.jpg"

    image.save(
        output,
        "JPEG",
        quality=95,
        optimize=True
    )

    print("Created:", output)


def main():
    if not os.path.exists("news.json"):
        raise FileNotFoundError("news.json missing")

    with open(
        "news.json", "r", encoding="utf-8"
    ) as file:
        data = json.load(file)

    articles = data.get("articles", [])

    if not articles:
        raise ValueError("No news articles found")

    for number, article in enumerate(
        articles[:10], 1
    ):
        try:
            create_card(article, number)
        except Exception as error:
            print("Card error:", error)

    print("ALL NEWS CARDS COMPLETED")


if __name__ == "__main__":
    main()
