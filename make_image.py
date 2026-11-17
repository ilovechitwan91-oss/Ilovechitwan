
import json
import os
import re
import urllib.request
from pathlib import Path
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, ImageOps

# =====================================
# CANVAS SETTINGS
# =====================================

WIDTH, HEIGHT = 1080, 1350
PHOTO_HEIGHT = 760

BG = (10, 21, 48)
RED = (208, 20, 60)
YELLOW = (255, 212, 0)
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


# =====================================
# NEPALI DATE
# =====================================

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
            f"{nepali_num(today.day)} "
            f"{months[today.month - 1]} "
            f"{nepali_num(today.year)}"
        )

    except Exception as exc:
        print("DATE ERROR:", exc)
        return ""


# =====================================
# DOWNLOAD NEWS PHOTO
# =====================================

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


# =====================================
# TEXT UTILITIES
# =====================================

def text_width(draw, text, fnt):

    bbox = draw.textbbox(
        (0, 0),
        text,
        font=fnt
    )

    return bbox[2] - bbox[0]


def split_news_title(title):
    """
    Colon वा dash पछाडिको नामलाई
    subtitle बनाउने।
    """

    title = title.strip()

    parts = re.split(
        r"\s*[:：–—]\s*",
        title,
        maxsplit=1
    )

    if len(parts) == 2 and parts[1].strip():
        return parts[0].strip(), parts[1].strip()

    return title, ""


def split_headline(draw, title):

    words = title.split()

    if len(words) < 2:
        return title, ""

    # First line 54px, second line 88px
    for first_size in range(54, 39, -2):

        first_font = font(
            NEPALI_BOLD,
            first_size
        )

        for second_size in range(90, 57, -2):

            second_font = font(
                NEPALI_BOLD,
                second_size
            )

            best = None
            best_score = float("inf")

            for i in range(1, len(words)):

                first = " ".join(words[:i])
                second = " ".join(words[i:])

                w1 = text_width(draw, first, first_font)
                w2 = text_width(draw, second, second_font)

                if w1 <= 1000 and w2 <= 1000:

                    # Prefer balanced visual widths
                    score = abs(w1 - w2)

                    if score < best_score:
                        best_score = score
                        best = (
                            first,
                            second,
                            first_font,
                            second_font
                        )

            if best:
                return best

    # Fallback for unusually long headlines
    first = " ".join(words[:-1])
    second = words[-1]

    return (
        first,
        second,
        font(NEPALI_BOLD, 40),
        font(NEPALI_BOLD, 58)
    )


# =====================================
# DATE BADGE
# =====================================

def draw_date(draw):

    date = nepali_date()

    if not date:
        return

    date_font = font(
        NEPALI_BOLD,
        34
    )

    bx = 760
    by = 40
    bw = 285
    bh = 60

    draw.rounded_rectangle(
        (bx, by, bx + bw, by + bh),
        radius=8,
        fill=RED
    )

    draw.text(
        (
            bx + bw // 2,
            by + bh // 2
        ),
        date,
        font=date_font,
        fill=WHITE,
        anchor="mm"
    )


# =====================================
# HEADLINE SECTION
# =====================================

def draw_headline(draw, title):

    first, second, font1, font2 = split_headline(
        draw,
        title
    )

    # LINE 1 - WHITE
    draw.text(
        (WIDTH // 2, 850),
        first,
        font=font1,
        fill=WHITE,
        anchor="mm"
    )

    # LINE 2 - LARGE YELLOW
    if second:

        draw.text(
            (WIDTH // 2, 950),
            second,
            font=font2,
            fill=YELLOW,
            anchor="mm"
        )

    return 1 if second else 0


# =====================================
# RED DIVIDER
# =====================================

def draw_divider(draw):

    draw.rounded_rectangle(
        (480, 1011, 600, 1019),
        radius=5,
        fill=RED
    )


# =====================================
# SUBTITLE / PERSON NAME
# =====================================

def draw_subtitle(draw, subtitle):

    if not subtitle:
        return

    # Automatically reduce font if name is long
    for size in range(48, 29, -2):

        subtitle_font = font(
            NEPALI_BOLD,
            size
        )

        if text_width(draw, subtitle, subtitle_font) <= 950:
            break

    draw.text(
        (WIDTH // 2, 1070),
        subtitle,
        font=subtitle_font,
        fill=WHITE,
        anchor="mm"
    )


# =====================================
# COMMENT CTA BUTTON
# =====================================

def draw_cta(draw):

    label = "पूरा समाचार कमेन्टमा"

    label_font = font(
        NEPALI_BOLD,
        40
    )

    bx = 190
    by = 1125
    bw = 700
    bh = 76

    draw.rounded_rectangle(
        (bx, by, bx + bw, by + bh),
        radius=38,
        fill=RED
    )

    draw.text(
        (WIDTH // 2, by + bh // 2),
        label,
        font=label_font,
        fill=WHITE,
        anchor="mm"
    )


# =====================================
# SOCIAL MEDIA FOOTER
# =====================================

def draw_social_icons(draw):

    y = 1297

    # FACEBOOK GROUP
    fx = 76

    draw.ellipse(
        (fx, y, fx + 46, y + 46),
        fill=(24, 119, 242)
    )

    draw.text(
        (fx + 23, y + 23),
        "f",
        font=font(ENGLISH_BOLD, 35),
        fill=WHITE,
        anchor="mm"
    )

    draw.text(
        (fx + 56, y + 23),
        "ilovechitwan",
        font=font(ENGLISH_BOLD, 25),
        fill=WHITE,
        anchor="lm"
    )

    # YOUTUBE GROUP
    yx = 410

    draw.rounded_rectangle(
        (yx, y + 7, yx + 50, y + 39),
        radius=9,
        fill=(255, 0, 0)
    )

    draw.polygon(
        [
            (yx + 19, y + 13),
            (yx + 19, y + 33),
            (yx + 34, y + 23)
        ],
        fill=WHITE
    )

    draw.text(
        (yx + 59, y + 23),
        "hamraikhabar",
        font=font(ENGLISH_BOLD, 25),
        fill=WHITE,
        anchor="lm"
    )

    # INSTAGRAM GROUP
    ix = 750

    draw.rounded_rectangle(
        (ix, y, ix + 46, y + 46),
        radius=11,
        fill=(210, 55, 130)
    )

    draw.rounded_rectangle(
        (ix + 8, y + 8, ix + 38, y + 38),
        radius=8,
        outline=WHITE,
        width=3
    )

    draw.ellipse(
        (ix + 16, y + 16, ix + 30, y + 30),
        outline=WHITE,
        width=3
    )

    draw.ellipse(
        (ix + 30, y + 10, ix + 35, y + 15),
        fill=WHITE
    )

    draw.text(
        (ix + 55, y + 23),
        "khabar.short",
        font=font(ENGLISH_BOLD, 25),
        fill=WHITE,
        anchor="lm"
    )


# =====================================
# CREATE NEWS CARD
# =====================================

def create_card(article, index):

    title = (
        article.get("title") or ""
    ).strip()

    if not title:
        return False

    # Separate headline and subtitle
    headline, subtitle = split_news_title(title)

    canvas = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        BG
    )

    # PHOTO
    photo = download_photo(
        article.get("image_url", "")
    )

    photo = fit_photo(photo)

    canvas.paste(photo, (0, 0))

    draw = ImageDraw.Draw(canvas)

    # DATE BADGE
    draw_date(draw)

    # NAVY LOWER PANEL
    draw.rectangle(
        (0, PHOTO_HEIGHT, WIDTH, HEIGHT),
        fill=BG
    )

    # HEADLINE
    draw_headline(
        draw,
        headline
    )

    # DIVIDER
    draw_divider(draw)

    # SUBTITLE
    draw_subtitle(
        draw,
        subtitle
    )

    # COMMENT BUTTON
    draw_cta(draw)

    # SOCIAL FOOTER
    draw_social_icons(draw)

    # SAVE HD IMAGE
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


# =====================================
# MAIN AUTOMATION
# =====================================

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
