
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

ASSET = "FB_IMG_1794663825968.jpg"

PAGE_NAME = "HAMRO CHITWAN RAMRO CHITWAN"
FACEBOOK = "www.fb.com/ilovechitwan"

OUTPUT_DIR = "news_images"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def find_font(patterns):
    for pattern in patterns:
        matches = glob.glob(pattern, recursive=True)
        if matches:
            return matches[0]
    return None


NEPALI_REGULAR = find_font([
    "/usr/share/fonts/**/*NotoSansDevanagari-Regular.ttf",
    "/usr/share/fonts/**/*NotoSerifDevanagari-Regular.ttf",
    "/usr/share/fonts/**/*Devanagari*Regular*.ttf"
])

NEPALI_BOLD = find_font([
    "/usr/share/fonts/**/*NotoSansDevanagari-Bold.ttf",
    "/usr/share/fonts/**/*NotoSerifDevanagari-Bold.ttf",
    "/usr/share/fonts/**/*Devanagari*Bold*.ttf"
])

ENGLISH_FONT = find_font([
    "/usr/share/fonts/**/*DejaVuSans.ttf"
])

ENGLISH_BOLD = find_font([
    "/usr/share/fonts/**/*DejaVuSans-Bold.ttf"
])


def get_font(text, size, bold=False):

    is_nepali = any(
        "\u0900" <= c <= "\u097F"
        for c in str(text)
    )

    if is_nepali:
        path = (
            NEPALI_BOLD or NEPALI_REGULAR
            if bold else
            NEPALI_REGULAR or NEPALI_BOLD
        )
    else:
        path = (
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

        nd = nepali_datetime.date.from_datetime_date(
            today
        )

        months = [
            "बैशाख", "जेठ", "असार", "साउन",
            "भदौ", "असोज", "कार्तिक", "मंसिर",
            "पुष", "माघ", "फागुन", "चैत"
        ]

        return (
            f"{nd.year} "
            f"{months[nd.month - 1]} "
            f"{nd.day}"
        )

    except Exception:

        return datetime.now(
            ZoneInfo("Asia/Kathmandu")
        ).strftime("%Y-%m-%d")


def clean_text(text):

    text = str(text or "")

    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def text_width(draw, text, font):

    box = draw.textbbox(
        (0, 0),
        text,
        font=font
    )

    return box[2] - box[0]


def wrap_text(draw, text, font, max_width):

    words = str(text).split()

    lines = []
    current = ""

    for word in words:

        test = (
            current + " " + word
        ).strip()

        if text_width(
            draw,
            test,
            font
        ) <= max_width:

            current = test

        else:

            if current:
                lines.append(current)

            current = word

    if current:
        lines.append(current)

    return lines


def draw_fitted_text(
    draw,
    text,
    x,
    y,
    max_width,
    max_height,
    start_size,
    min_size,
    max_lines,
    color,
    bold=False,
    line_gap=1.3
):

    text = clean_text(text)

    if not text:
        return y

    for size in range(
        start_size,
        min_size - 1,
        -1
    ):

        font = get_font(
            text,
            size,
            bold
        )

        lines = wrap_text(
            draw,
            text,
            font,
            max_width
        )

        line_height = int(
            size * line_gap
        )

        if (
            len(lines) <= max_lines
            and len(lines) * line_height <= max_height
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

    # Minimum size fallback
    font = get_font(
        text,
        min_size,
        bold
    )

    lines = wrap_text(
        draw,
        text,
        font,
        max_width
    )

    line_height = int(
        min_size * line_gap
    )

    allowed = max(
        1,
        min(
            max_lines,
            max_height // line_height
        )
    )

    lines = lines[:allowed]

    for line in lines:

        draw.text(
            (x, y),
            line,
            font=font,
            fill=color
        )

        y += line_height

    return y


def get_news_title(article):

    return (
        article.get("title")
        or article.get("english_title")
        or "ताजा समाचार"
    )


def get_news_description(article):

    fields = [
        "description",
        "full_text",
        "news_content",
        "summary",
        "content",
        "english_description"
    ]

    for field in fields:

        value = str(
            article.get(field) or ""
        ).strip()

        if value:

            # JSON को चार लाइन जोडेर एउटै
            # paragraph बनाउने
            value = value.replace("\n", " ")
            value = value.replace("\r", " ")

            return clean_text(value)

    return "यस समाचारसम्बन्धी थप विवरण प्राप्त भएपछि अपडेट गरिनेछ।"


def load_local_photo():

    if not os.path.isfile(ASSET):
        return None

    try:

        return Image.open(
            ASSET
        ).convert("RGB")

    except Exception as error:

        print("Logo error:", error)
        return None


def download_image(url):

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
            request,
            timeout=25
        ) as response:

            data = response.read(
                12 * 1024 * 1024 + 1
            )

        if len(data) > 12 * 1024 * 1024:
            return None

        return Image.open(
            BytesIO(data)
        ).convert("RGB")

    except Exception as error:

        print("Photo download error:", error)
        return None


def add_logo(image, position, size):

    logo = load_local_photo()

    if logo is None:
        return

    logo = ImageOps.fit(
        logo,
        size,
        method=Image.Resampling.LANCZOS
    )

    mask = Image.new(
        "L",
        size,
        0
    )

    mask_draw = ImageDraw.Draw(mask)

    mask_draw.rounded_rectangle(
        (0, 0, size[0] - 1, size[1] - 1),
        radius=12,
        fill=255
    )

    image.paste(
        logo,
        position,
        mask
    )


def create_card(article, number):

    image = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        BG
    )

    draw = ImageDraw.Draw(image)

    # =================================
    # TOP DATE AND NEWS UPDATE
    # =================================

    draw.rectangle(
        (0, 0, WIDTH, 140),
        fill=(2, 25, 56)
    )

    # NEWS UPDATE label

    draw.rounded_rectangle(
        (35, 35, 385, 91),
        radius=8,
        fill=RED
    )

    draw.text(
        (52, 43),
        "NEWS UPDATE",
        font=get_font(
            "NEWS UPDATE",
            30,
            True
        ),
        fill=WHITE
    )

    # Date box

    date_text = nepali_date()

    draw.rounded_rectangle(
        (755, 38, 1045, 93),
        radius=10,
        fill=WHITE
    )

    date_font = get_font(
        date_text,
        27,
        True
    )

    date_w = text_width(
        draw,
        date_text,
        date_font
    )

    draw.text(
        (900 - date_w // 2, 49),
        date_text,
        font=date_font,
        fill=BG
    )

    # =================================
    # NEWS PHOTO
    # =================================

    photo = download_image(
        article.get("image_url", "")
    )

    photo_x = 31
    photo_y = 160
    photo_w = 1018
    photo_h = 637

    if photo is not None:

        photo = ImageOps.fit(
            photo,
            (photo_w, photo_h),
            method=Image.Resampling.LANCZOS
        )

        image.paste(
            photo,
            (photo_x, photo_y)
        )

    else:

        draw.rectangle(
            (
                photo_x,
                photo_y,
                photo_x + photo_w,
                photo_y + photo_h
            ),
            fill=PANEL
        )

        placeholder = "समाचारको फोटो उपलब्ध छैन"

        font = get_font(
            placeholder,
            34,
            True
        )

        box = draw.textbbox(
            (0, 0),
            placeholder,
            font=font
        )

        tw = box[2] - box[0]
        th = box[3] - box[1]

        draw.text(
            (
                (WIDTH - tw) // 2,
                photo_y + (photo_h - th) // 2
            ),
            placeholder,
            font=font,
            fill=WHITE
        )

    draw = ImageDraw.Draw(image)

    # Photo border

    draw.rectangle(
        (
            photo_x,
            photo_y,
            photo_x + photo_w,
            photo_y + photo_h
        ),
        outline=(75, 115, 155),
        width=2
    )

    # =================================
    # HEADLINE
    # =================================

    headline = get_news_title(article)

    # Red vertical line

    draw.rounded_rectangle(
        (35, 835, 44, 1050),
        radius=4,
        fill=RED
    )

    draw.ellipse(
        (29, 825, 50, 846),
        fill=RED
    )

    y = draw_fitted_text(
        draw,
        headline,
        66,
        830,
        970,
        135,
        56,
        43,
        2,
        CYAN,
        True,
        1.10
    )

    # =================================
    # DESCRIPTION
    # =================================

    description = get_news_description(
        article
    )

    description_y = max(
        970,
        y + 8
    )

    draw_fitted_text(
        draw,
        description,
        66,
        description_y,
        970,
        260 - (description_y - 970),
        36,
        28,
        4,
        WHITE,
        False,
        1.25
    )

    # =================================
    # FOOTER
    # =================================

    draw.rectangle(
        (0, 1290, WIDTH, HEIGHT),
        fill=RED
    )

    # Footer logo

    draw.rounded_rectangle(
        (22, 1295, 80, 1345),
        radius=7,
        fill=WHITE
    )

    add_logo(
        image,
        (26, 1299),
        (50, 42)
    )

    draw = ImageDraw.Draw(image)

    # Footer page name

    page_font = get_font(
        PAGE_NAME,
        22,
        True
    )

    draw.text(
        (95, 1295),
        PAGE_NAME,
        font=page_font,
        fill=WHITE
    )

    # Facebook link

    draw.text(
        (95, 1322),
        FACEBOOK,
        font=get_font(
            FACEBOOK,
            19,
            True
        ),
        fill=WHITE
    )

    # =================================
    # SAVE IMAGE
    # =================================

    output = os.path.join(
        OUTPUT_DIR,
        f"news_{number:02d}.jpg"
    )

    image.save(
        output,
        "JPEG",
        quality=95,
        optimize=True
    )

    print("Created:", output)


def main():

    if not NEPALI_REGULAR and not NEPALI_BOLD:

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

    if not os.path.exists(ASSET):

        raise FileNotFoundError(
            "FB_IMG_1794663825968.jpg missing"
        )

    with open(
        "news.json",
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(file)

    articles = data.get(
        "articles",
        []
    )

    if not articles:

        raise ValueError(
            "No news articles found"
        )

    print("Total news:", len(articles))

    for number, article in enumerate(
        articles[:10],
        1
    ):

        try:

            create_card(
                article,
                number
            )

        except Exception as error:

            print(
                "Card error:",
                number,
                str(error)
            )

            raise

    print("--------------------------------")
    print("ALL NEWS CARDS COMPLETED")
    print("Total cards:", min(10, len(articles)))
    print("Size: 1080 x 1350")
    print("Output:", OUTPUT_DIR)
    print("--------------------------------")


if __name__ == "__main__":
    main()
