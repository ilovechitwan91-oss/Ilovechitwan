
import json
import os
import urllib.request
from pathlib import Path
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, ImageOps

WIDTH, HEIGHT = 1080, 1350
PHOTO_HEIGHT = 760

BG = (8, 19, 43)
RED = (224, 15, 55)
YELLOW = (255, 211, 0)
WHITE = (255, 255, 255)

NEWS_FILE = Path("news.json")
STATE_FILE = Path("published_news.json")
IMAGE_DIR = Path("news_images")
IMAGE_DIR.mkdir(exist_ok=True)

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
        print("DATE ERROR:", exc)
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
        print("PHOTO ERROR:", exc)
        return None


def fit_photo(image):
    if image is None:
        image = Image.new(
            "RGB",
            (WIDTH, PHOTO_HEIGHT),
            (50, 50, 50)
        )

    return ImageOps.fit(
        image,
        (WIDTH, PHOTO_HEIGHT),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.38)
    )


def text_width(draw, text, fnt):
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0]


def split_headline(draw, title):
    words = title.split()

    if len(words) < 2:
        return title, ""

    for size in range(70, 35, -2):
        fnt = font(NEPALI_BOLD, size)

        best = None
        best_difference = float("inf")

        for i in range(1, len(words)):
            first = " ".join(words[:i])
            second = " ".join(words[i:])

            w1 = text_width(draw, first, fnt)
            w2 = text_width(draw, second, fnt)

            if w1 <= 970 and w2 <= 970:
                difference = abs(w1 - w2)

                if difference < best_difference:
                    best_difference = difference
                    best = (first, second, size)

        if best:
            return best

    return " ".join(words[:-1]), words[-1], 36


def draw_social_icons(draw):
    y = 1280

    # FACEBOOK ICON
    fx = 95
    draw.ellipse(
        (fx, y, fx + 42, y + 42),
        fill=(24, 119, 242)
    )
    draw.text(
        (fx + 21, y + 21),
        "f",
        font=font(ENGLISH_BOLD, 32),
        fill=WHITE,
        anchor="mm"
    )

    draw.text(
        (145, y + 8),
        "ilovechitwan",
        font=font(ENGLISH_BOLD, 22),
        fill=WHITE
    )

    # YOUTUBE ICON
    yx = 435
    draw.rounded_rectangle(
        (yx, y + 5, yx + 49, y + 37),
        radius=9,
        fill=(255, 0, 0)
    )

    draw.polygon(
        [
            (yx + 20, y + 12),
            (yx + 20, y + 30),
            (yx + 34, y + 21)
        ],
        fill=WHITE
    )

    draw.text(
        (yx + 58, y + 8),
        "hamraikhabar",
        font=font(ENGLISH_BOLD, 21),
        fill=WHITE
    )

    # INSTAGRAM ICON
    ix = 790

    draw.rounded_rectangle(
        (ix, y + 2, ix + 42, y + 42),
        radius=11,
        fill=(210, 55, 130)
    )

    draw.rounded_rectangle(
        (ix + 8, y + 10, ix + 34, y + 34),
        radius=7,
        outline=WHITE,
        width=3
    )

    draw.ellipse(
        (ix + 15, y + 17, ix + 27, y + 29),
        outline=WHITE,
        width=3
    )

    draw.ellipse(
        (ix + 27, y + 12, ix + 31, y + 16),
        fill=WHITE
    )

    draw.text(
        (ix + 49, y + 8),
        "khabar.short",
        font=font(ENGLISH_BOLD, 21),
        fill=WHITE
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

    # --------------------------------
    # NEWS PHOTO - NATURAL COLORS
    # --------------------------------

    photo = download_photo(
        article.get("image_url", "")
    )

    photo = fit_photo(photo)

    # No blue overlay, no gradient, no logo
    canvas.paste(photo, (0, 0))

    draw = ImageDraw.Draw(canvas)

    # --------------------------------
    # NEPALI DATE
    # --------------------------------

    date = nepali_date()

    if date:
        date_font = font(NEPALI_BOLD, 29)

        bbox = draw.textbbox(
            (0, 0),
            date,
            font=date_font
        )

        dw = bbox[2] - bbox[0]

        x = WIDTH - dw - 85

        draw.rounded_rectangle(
            (x - 20, 40, WIDTH - 35, 105),
            radius=14,
            fill=RED
        )

        draw.text(
            (x, 55 - bbox[1]),
            date,
            font=date_font,
            fill=WHITE
        )

    # --------------------------------
    # NEWS TEXT BACKGROUND
    # --------------------------------

    # Direct transition: photo ends, navy panel begins
    draw.rectangle(
        (0, PHOTO_HEIGHT, WIDTH, HEIGHT),
        fill=BG
    )

    # --------------------------------
    # HEADLINE: TWO DIFFERENT COLORS
    # --------------------------------

    first, second, size = split_headline(
        draw,
        title
    )

    headline_font = font(
        NEPALI_BOLD,
        size
    )

    line_height = int(size * 1.45)

    # First line - WHITE
    bbox1 = draw.textbbox(
        (0, 0),
        first,
        font=headline_font
    )

    w1 = bbox1[2] - bbox1[0]

    draw.text(
        (
            (WIDTH - w1) // 2,
            805 - bbox1[1]
        ),
        first,
        font=headline_font,
        fill=WHITE
    )

    # Second line - YELLOW
    if second:
        bbox2 = draw.textbbox(
            (0, 0),
            second,
            font=headline_font
        )

        w2 = bbox2[2] - bbox2[0]

        draw.text(
            (
                (WIDTH - w2) // 2,
                805 + line_height - bbox2[1]
            ),
            second,
            font=headline_font,
            fill=YELLOW
        )

    # --------------------------------
    # RED UNDERLINE
    # --------------------------------

    draw.rounded_rectangle(
        (480, 1050, 600, 1060),
        radius=5,
        fill=RED
    )

    # --------------------------------
    # FULL NEWS BUTTON
    # --------------------------------

    label = "पूरा समाचार कमेन्टमा"

    label_font = font(
        NEPALI_BOLD,
        34
    )

    bx = 190
    by = 1090
    bw = 700
    bh = 76

    draw.rounded_rectangle(
        (bx, by, bx + bw, by + bh),
        radius=40,
        fill=RED
    )

    bbox = draw.textbbox(
        (0, 0),
        label,
        font=label_font
    )

    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    draw.text(
        (
            (WIDTH - tw) // 2,
            by + (bh - th) // 2 - bbox[1]
        ),
        label,
        font=label_font,
        fill=WHITE
    )

    # --------------------------------
    # SOCIAL MEDIA - ONE HORIZONTAL ROW
    # --------------------------------

    draw_social_icons(draw)

    # --------------------------------
    # SAVE HD CARD
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
        raise FileNotFoundError("news.json not found")

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
            print("CARD ERROR:", index, exc)

    print("NEW HD CARDS CREATED:", made)


if __name__ == "__main__":
    main()
