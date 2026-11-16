import json
import os
import urllib.request
from pathlib import Path
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageOps

WIDTH, HEIGHT = 1080, 1350
BG = (8, 17, 40)
RED = (224, 20, 48)
YELLOW = (255, 211, 0)
WHITE = (255, 255, 255)

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
ENGLISH_REGULAR = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
ENGLISH_BOLD = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


def font(paths, size):
    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)
    return ImageFont.load_default()


def nepali_date():
    try:
        import nepali_datetime
        today = nepali_datetime.date.today()
        months = ["बैशाख", "जेठ", "असार", "साउन", "भदौ", "असोज", "कात्तिक", "मंसिर", "पुष", "माघ", "फागुन", "चैत"]
        digits = "०१२३४५६७८९"
        n = lambda x: "".join(digits[int(c)] if c.isdigit() else c for c in str(x))
        return f"{n(today.year)} {months[today.month-1]} {n(today.day)} गते"
    except Exception:
        return ""


def download_photo(url):
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25) as response:
            raw = response.read()
        image = Image.open(BytesIO(raw))
        image.load()
        return ImageOps.exif_transpose(image).convert("RGB")
    except Exception as exc:
        print("PHOTO DOWNLOAD ERROR:", exc)
        return None


def fit_photo(image):
    if image is None:
        image = Image.new("RGB", (WIDTH, 700), (20, 35, 65))
    return ImageOps.fit(image, (WIDTH, 700), method=Image.Resampling.LANCZOS, centering=(0.5, 0.38))


def wrap(draw, text, fnt, max_width):
    lines, current = [], ""
    for word in str(text).split():
        test = (current + " " + word).strip()
        box = draw.textbbox((0, 0), test, font=fnt)
        if box[2] - box[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def create_card(article, index):
    title = (article.get("title") or "").strip()
    if not title:
        return False

    canvas = Image.new("RGB", (WIDTH, HEIGHT), BG)
    canvas.paste(fit_photo(download_photo(article.get("image_url", ""))), (0, 0))
    draw = ImageDraw.Draw(canvas)

    # Dark translucent fade over the lower edge of the photograph.
    fade = Image.new("RGBA", (WIDTH, 250), (0, 0, 0, 0))
    px = fade.load()
    for y in range(250):
        alpha = int(205 * y / 249)
        for x in range(WIDTH):
            px[x, y] = (8, 17, 40, alpha)
    canvas.paste(fade, (0, 450), fade)
    draw = ImageDraw.Draw(canvas)

    draw.rectangle((0, 0, WIDTH, 15), fill=RED)
    draw.rounded_rectangle((40, 40, 265, 102), radius=14, fill=RED)
    draw.text((75, 48), "ताजा खबर", font=font(NEPALI_BOLD, 36), fill=WHITE)

    date = nepali_date()
    if date:
        df = font(NEPALI_BOLD, 27)
        bbox = draw.textbbox((0, 0), date, font=df)
        dw = bbox[2] - bbox[0]
        x = WIDTH - 40 - dw - 40
        draw.rounded_rectangle((x, 40, WIDTH-40, 102), radius=14, fill=BG)
        draw.text((x+20, 54-bbox[1]), date, font=df, fill=WHITE)

    draw.rectangle((0, 650, WIDTH, 1210), fill=BG)

    y = 735
    selected_font = font(NEPALI_BOLD, 52)
    lines = []
    for size in range(82, 39, -2):
        selected_font = font(NEPALI_BOLD, size)
        lines = wrap(draw, title, selected_font, 964)
        line_height = int(size * 1.28)
        if len(lines) <= 4 and y + len(lines) * line_height <= 1080:
            break

    line_height = int(selected_font.size * 1.28)
    for i, line in enumerate(lines[:4]):
        draw.text((58, y), line, font=selected_font, fill=YELLOW if i == 0 else WHITE,
                  stroke_width=1, stroke_fill=YELLOW if i == 0 else WHITE)
        y += line_height

    draw.rectangle((60, 1095, 265, 1103), fill=RED)
    label = "पूरा समाचार कमेन्टमा"
    lf = font(NEPALI_BOLD, 30)
    bbox = draw.textbbox((0, 0), label, font=lf)
    w, h = bbox[2]-bbox[0], bbox[3]-bbox[1]
    draw.rounded_rectangle((60, 1120, 60+w+36, 1120+h+26), radius=10, fill=YELLOW)
    draw.text((78, 1133-bbox[1]), label, font=lf, fill=BG)

    draw.rectangle((0, 1210, WIDTH, HEIGHT), fill=RED)
    draw.text((WIDTH//2, 1230), "PLEASE LIKE, SHARE & FOLLOW US AT",
              font=font(ENGLISH_BOLD, 28), fill=WHITE, anchor="mt")
    draw.text((WIDTH//2, 1290), "fb.com/ilovechitwan",
              font=font(ENGLISH_BOLD, 48), fill=WHITE, anchor="mt")

    output = IMAGE_DIR / f"news_{index:02d}.jpg"
    canvas.save(output, "JPEG", quality=98, optimize=True, progressive=True, subsampling=0)
    print("HD CARD SAVED:", output)
    return True


def main():
    if not NEWS_FILE.exists():
        raise FileNotFoundError("news.json not found")
    data = json.loads(NEWS_FILE.read_text(encoding="utf-8"))
    articles = data.get("articles", [])
    if not articles:
        print("No news available")
        return

    published = []
    if STATE_FILE.exists():
        try:
            published = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            published = []
    done = {x.get("link") for x in published if isinstance(x, dict)}

    # Remove stale image files so old cards cannot be mistaken for current ones.
    for old in IMAGE_DIR.glob("news_*.jpg"):
        old.unlink()

    made = 0
    for index, article in enumerate(articles, start=1):
        link = (article.get("link") or "").split("#")[0].rstrip("/")
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
