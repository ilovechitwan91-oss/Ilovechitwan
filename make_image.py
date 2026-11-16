
import json
import os
import urllib.request
from pathlib import Path
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, ImageOps

WIDTH, HEIGHT = 1080, 1350

BG = (8, 19, 45)
RED = (222, 15, 55)
YELLOW = (255, 211, 0)
WHITE = (255, 255, 255)

PHOTO_HEIGHT = 760

NEWS_FILE = Path("news.json")
STATE_FILE = Path("published_news.json")
IMAGE_DIR = Path("news_images")
IMAGE_DIR.mkdir(exist_ok=True)

NEPALI_REGULAR = [
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

NEPALI_BOLD = [
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

ENGLISH_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
]


def font(paths, size):
    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(
                path,
                size,
                layout_engine=ImageFont.Layout.RAQM
            )
    return ImageFont.load_default()


def nepali_date():
    try:
        import nepali_datetime

        today = nepali_datetime.date.today()

        months = [
            "बैशाख", "जेठ", "असार", "साउन",
            "भदौ", "असोज", "कात्तिक", "मंसिर",
            "पुष", "माघ", "फागुन", "चैत"
        ]

        digits = "०१२३४५६७८९"

        def nepali_num(value):
            return "".join(
                digits[int(c)] if c.isdigit() else c
                for c in str(value)
            )

        return (
            f"{nepali_num(today.year)} "
            f"{months[today.month - 1]} "
            f"{nepali_num(today.day)}"
        )

    except Exception as exc:
        print("NEPALI DATE ERROR:", exc)
        return ""


def download_photo(url):
    if not url:
        return None

    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        with urllib.request.urlopen(request, timeout=25) as response:
            raw = response.read()

        image = Image.open(BytesIO(raw))
        image.load()

        return ImageOps.exif_transpose(image).convert("RGB")

    except Exception as exc:
        print("PHOTO DOWNLOAD ERROR:", exc)
        return None


def fit_photo(image):
    if image is None:
        image = Image.new(
            "RGB",
            (WIDTH, PHOTO_HEIGHT),
            (25, 38, 65)
        )

    return ImageOps.fit(
        image,
        (WIDTH, PHOTO_HEIGHT),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.38)
    )


def wrap(draw, text, fnt, max_width):
    lines = []
    current = ""

    for word in str(text).split():
        test = (current + " " + word).strip()

        bbox = draw.textbbox(
            (0, 0),
            test,
            font=fnt
        )

        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines


def draw_center_text(draw, text, y, fnt, fill):
    draw.text(
        (WIDTH // 2, y),
        text,
        font=fnt,
        fill=fill,
        anchor="mt"
    )


def create_card(article, index):

    title = (article.get("title") or "").strip()

    if not title:
        return False

    canvas = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        BG
    )

    draw = ImageDraw.Draw(canvas)

    # --------------------------------
    # 1. HD NEWS PHOTO
    # --------------------------------

    photo = download_photo(
        article.get("image_url", "")
    )

    photo = fit_photo(photo)

    canvas.paste(photo, (0, 0))

    # Subtle dark fade at bottom of photo
    fade = Image.new(
        "RGBA",
        (WIDTH, 180),
        (0, 0, 0, 0)
    )

    pixels = fade.load()

    for y in range(180):
        alpha = int(150 * y / 179)

        for x in range(WIDTH):
            pixels[x, y] = (
                0, 0, 0, alpha
            )

    canvas.paste(
        fade,
        (0, PHOTO_HEIGHT - 180),
        fade
    )

    draw = ImageDraw.Draw(canvas)

    # --------------------------------
    # 2. DATE BADGE
    # --------------------------------

    date = nepali_date()

    if date:
        date_font = font(NEPALI_BOLD, 31)

        bbox = draw.textbbox(
            (0, 0),
            date,
            font=date_font
        )

        date_width = bbox[2] - bbox[0]

        badge_width = date_width + 48

        x = WIDTH - badge_width - 35

        draw.rounded_rectangle(
            (x, 40, WIDTH - 35, 105),
            radius=14,
            fill=RED
        )

        draw.text(
            (x + 24, 55 - bbox[1]),
            date,
            font=date_font,
            fill=WHITE
        )

    # --------------------------------
    # 3. NAVY BLUE NEWS PANEL
    # --------------------------------

    draw.rectangle(
        (0, PHOTO_HEIGHT, WIDTH, HEIGHT),
        fill=BG
    )

    # Small branding heading
    draw_center_text(
        draw,
        "I LOVE CHITWAN",
        785,
        font(ENGLISH_BOLD, 28),
        WHITE
    )

    # --------------------------------
    # 4. MAIN NEWS HEADLINE
    # --------------------------------

    selected_font = font(NEPALI_BOLD, 64)

    lines = []

    for size in range(76, 43, -2):

        selected_font = font(
            NEPALI_BOLD,
            size
        )

        lines = wrap(
            draw,
            title,
            selected_font,
            960
        )

        line_height = int(size * 1.25)

        if (
            len(lines) <= 4
            and 845 + len(lines) * line_height <= 1100
        ):
            break

    # Keep long headlines within four lines
    if len(lines) > 4:
        lines = lines[:4]

        last = lines[-1]

        while last:
            test = last + "..."

            bbox = draw.textbbox(
                (0, 0),
                test,
                font=selected_font
            )

            if bbox[2] - bbox[0] <= 960:
                break

            last = last[:-1]

        lines[-1] = last.rstrip() + "..."

    line_height = int(selected_font.size * 1.25)

    y = 845

    for line in lines:

        bbox = draw.textbbox(
            (0, 0),
            line,
            font=selected_font
        )

        text_width = bbox[2] - bbox[0]

        x = (WIDTH - text_width) // 2

        draw.text(
            (x, y - bbox[1]),
            line,
            font=selected_font,
            fill=YELLOW,
            stroke_width=1,
            stroke_fill=YELLOW
        )

        y += line_height

    # --------------------------------
    # 5. RED UNDERLINE
    # --------------------------------

    underline_y = min(y + 5, 1110)

    draw.rounded_rectangle(
        (
            WIDTH // 2 - 62,
            underline_y,
            WIDTH // 2 + 62,
            underline_y + 9
        ),
        radius=5,
        fill=RED
    )

    # --------------------------------
    # 6. READ FULL NEWS BUTTON
    # --------------------------------

    label = "पूरा समाचार कमेन्टमा"

    label_font = font(
        NEPALI_BOLD,
        35
    )

    button_width = 700
    button_height = 76

    button_x = (WIDTH - button_width) // 2
    button_y = 1150

    draw.rounded_rectangle(
        (
            button_x,
            button_y,
            button_x + button_width,
            button_y + button_height
        ),
        radius=40,
        fill=RED
    )

    bbox = draw.textbbox(
        (0, 0),
        label,
        font=label_font
    )

    label_width = bbox[2] - bbox[0]
    label_height = bbox[3] - bbox[1]

    draw.text(
        (
            (WIDTH - label_width) // 2,
            button_y + (button_height - label_height) // 2 - bbox[1]
        ),
        label,
        font=label_font,
        fill=WHITE
    )

    # --------------------------------
    # 7. TEXT-ONLY FACEBOOK BRANDING
    # --------------------------------

    footer_y = 1280

    # Facebook blue circle with text f
    draw.ellipse(
        (170, footer_y, 215, footer_y + 45),
        fill=(24, 119, 242)
    )

    draw.text(
        (192, footer_y + 21),
        "f",
        font=font(ENGLISH_BOLD, 34),
        fill=WHITE,
        anchor="mm"
    )

    draw.text(
        (230, footer_y + 7),
        "ilovechitwan",
        font=font(ENGLISH_BOLD, 31),
        fill=WHITE
    )

    # --------------------------------
    # 8. SAVE HD IMAGE
    # --------------------------------

    output = IMAGE_DIR / f"news_{index:02d}.jpg"

    canvas.save(
        output,
        "JPEG",
        quality=98,
        optimize=True,
        progressive=True,
        subsampling=0
    )

    print("HD NEWS CARD SAVED:", output)

    return True


def main():

    if not NEWS_FILE.exists():
        raise FileNotFoundError(
            "news.json not found"
        )

    data = json.loads(
        NEWS_FILE.read_text(encoding="utf-8")
    )

    articles = data.get("articles", [])

    if not articles:
        print("No news available")
        return

    published = []

    if STATE_FILE.exists():
        try:
            published = json.loads(
                STATE_FILE.read_text(encoding="utf-8")
            )
        except Exception:
            published = []

    done = {
        x.get("link")
        for x in published
        if isinstance(x, dict)
    }

    # Remove old generated images
    for old in IMAGE_DIR.glob("news_*.jpg"):
        old.unlink()

    made = 0

    for index, article in enumerate(articles, start=1):

        link = (
            article.get("link") or ""
        ).split("#")[0].rstrip("/")

        if not link or link in done:
            continue

        try:
            if create_card(article, index):
                made += 1

        except Exception as exc:
            print(
                "CARD ERROR:",
                index,
                exc
            )

    print("NEW HD CARDS CREATED:", made)


if __name__ == "__main__":
    main()
