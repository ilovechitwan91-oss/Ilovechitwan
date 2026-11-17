
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


# --------------------------------
# AUTOMATIC HEADLINE WRAPPING
# --------------------------------

def wrap_headline(draw, title, max_width, fnt):
    words = title.split()
    lines = []
    current = ""

    for word in words:
        test = word if not current else current + " " + word

        if text_width(draw, test, fnt) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines


def prepare_headline(draw, title):
    for size in range(112, 53, -2):

        fnt = font(NEPALI_BOLD, size)

        lines = wrap_headline(
            draw,
            title,
            990,
            fnt
        )

        if len(lines) <= 3 and all(
            text_width(draw, line, fnt) <= 990
            for line in lines
        ):
            return lines, fnt, size

    fnt = font(NEPALI_BOLD, 54)

    return (
        wrap_headline(draw, title, 990, fnt),
        fnt,
        54
    )


# --------------------------------
# SOCIAL MEDIA FOOTER
# --------------------------------

def draw_social_icons(draw):

    y = 1280

    # FACEBOOK
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

    # YOUTUBE
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

    # INSTAGRAM
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


# --------------------------------
# CREATE NEWS CARD
# --------------------------------

def create_card(article, index):

    title = (article.get("title") or "").strip()

    if not title:
        return False

    canvas = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        BG
    )

    # NEWS PHOTO
    photo = download_photo(
        article.get("image_url", "")
    )

    photo = fit_photo(photo)

    canvas.paste(photo, (0, 0))

    draw = ImageDraw.Draw(canvas)

    # --------------------------------
    # NEPALI DATE - DOUBLE SIZE
    # --------------------------------

    date = nepali_date()

    if date:

        date_font = font(NEPALI_BOLD, 58)

        bbox = draw.textbbox(
            (0, 0),
            date,
            font=date_font
        )

        dw = bbox[2] - bbox[0]
        dh = bbox[3] - bbox[1]

        padding_x = 25
        padding_y = 17

        x = WIDTH - dw - padding_x * 2 - 35
        y = 30

        draw.rounded_rectangle(
            (
                x,
                y,
                x + dw + padding_x * 2,
                y + dh + padding_y * 2
            ),
            radius=17,
            fill=RED
        )

        draw.text(
            (
                x + padding_x,
                y + padding_y - bbox[1]
            ),
            date,
            font=date_font,
            fill=WHITE
        )

    # --------------------------------
    # NEWS TEXT BACKGROUND
    # --------------------------------

    draw.rectangle(
        (0, PHOTO_HEIGHT, WIDTH, HEIGHT),
        fill=BG
    )

    # --------------------------------
    # HEADLINE - LARGE TEXT
    # WITH AUTOMATIC HIGHLIGHTER
    # --------------------------------

    lines, headline_font, size = prepare_headline(
        draw,
        title
    )

    line_height = int(size * 1.28)

    total_height = len(lines) * line_height

    start_y = 785 + max(
        0,
        (265 - total_height) // 2
    )

    for i, line in enumerate(lines):

        bbox = draw.textbbox(
            (0, 0),
            line,
            font=headline_font
        )

        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        # HIGHLIGHTER FITS TEXT SIZE
        padding_x = 19
        padding_y = 10

        highlight_width = tw + padding_x * 2
        highlight_height = th + padding_y * 2

        hx = (WIDTH - highlight_width) // 2
        hy = start_y + i * line_height

        draw.rounded_rectangle(
            (
                hx,
                hy,
                hx + highlight_width,
                hy + highlight_height
            ),
            radius=13,
            fill=RED
        )

        # ALTERNATE WHITE AND YELLOW TEXT
        text_color = WHITE if i % 2 == 0 else YELLOW

        draw.text(
            (
                hx + padding_x - bbox[0],
                hy + padding_y - bbox[1]
            ),
            line,
            font=headline_font,
            fill=text_color
        )

    # --------------------------------
    # RED UNDERLINE
    # --------------------------------

    draw.rounded_rectangle(
        (475, 1065, 605, 1077),
        radius=6,
        fill=RED
    )

    # --------------------------------
    # FULL NEWS COMMENT BUTTON
    # DOUBLE SIZE
    # --------------------------------

    label = "पूरा समाचार कमेन्टमा"

    label_font = font(
        NEPALI_BOLD,
        60
    )

    bx = 85
    by = 1100
    bw = 910
    bh = 105

    draw.rounded_rectangle(
        (bx, by, bx + bw, by + bh),
        radius=48,
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
    # SOCIAL MEDIA FOOTER
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


# --------------------------------
# MAIN
# --------------------------------

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
