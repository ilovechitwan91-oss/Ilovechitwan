
import os
import re
import json
import base64
import time
import wave
import textwrap
import subprocess
import requests

from pathlib import Path
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, ImageEnhance


# ==========================================
# I LOVE CHITWAN DAILY NEWS VIDEO
# 10 NEWS | LANDSCAPE 1920x1080
# NEPALI VOICE | FACEBOOK VIDEO
# ==========================================

API_KEY = os.getenv("GEMINI_API_KEY")

TEXT_MODEL = "gemini-3.8-flash"
TTS_MODEL = "gemini-3.8-flash-lite-tts"
VOICE_NAME = "Cruz"

API_TIMEOUT = 180
MAX_RETRIES = 3

WIDTH = 1920
HEIGHT = 1080
FPS = 25

NEWS_FILE = Path("news_reels.json")
OUTPUT_DIR = Path("news_videos")
OUTPUT_FILE = OUTPUT_DIR / "daily_news.mp4"

MAX_NEWS = 10

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================
# FONT
# ==========================================

FONT_PATHS = [
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansDevanagari-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def get_font(size):
    for path in FONT_PATHS:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


# ==========================================
# GEMINI REQUEST
# ==========================================

def gemini_request(url, payload):

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):

        try:
            response = requests.post(
                url,
                params={"key": API_KEY},
                json=payload,
                timeout=API_TIMEOUT
            )

            if response.status_code == 429:
                raise RuntimeError(
                    "Gemini daily quota exceeded. "
                    "Cruz voice quota सकियो।"
                )

            if response.status_code >= 500:
                raise RuntimeError(
                    f"Gemini server error: {response.status_code}"
                )

            if not response.ok:
                raise RuntimeError(
                    f"Gemini API Error {response.status_code}: "
                    f"{response.text[:1000]}"
                )

            return response.json()

        except requests.exceptions.Timeout as exc:
            last_error = exc

        except requests.exceptions.ConnectionError as exc:
            last_error = exc

        except RuntimeError:
            raise

        print(
            f"Gemini retry {attempt}/{MAX_RETRIES}:",
            str(last_error)[:300]
        )

        if attempt < MAX_RETRIES:
            time.sleep(5 * (2 ** (attempt - 1)))

    raise RuntimeError(str(last_error))


# ==========================================
# NEWS SCRIPT
# ==========================================

def make_narration(article):

    title = str(article.get("title", "")).strip()
    description = str(article.get("description", "")).strip()

    prompt = f"""
तपाईं नेपाली समाचार वाचक हुनुहुन्छ।

तलको समाचारलाई स्वाभाविक, स्पष्ट र शुद्ध नेपाली भाषामा
करिब २० देखि ३० सेकेन्डमा पढ्न मिल्ने गरी तयार गर्नुहोस्।

समाचारको तथ्य परिवर्तन नगर्नुहोस्।
आफैंले नयाँ तथ्य नथप्नुहोस्।
अंग्रेजी शब्द अनावश्यक प्रयोग नगर्नुहोस्।

शीर्षक:
{title}

विवरण:
{description}

केवल समाचार वाचनको स्क्रिप्ट दिनुहोस्।
"""

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{TEXT_MODEL}:generateContent"
    )

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }

    result = gemini_request(url, payload)

    try:
        return result["candidates"][0]["content"]["parts"][0]["text"].strip()

    except (KeyError, IndexError, TypeError):
        raise RuntimeError("Gemini बाट समाचार स्क्रिप्ट प्राप्त भएन।")


# ==========================================
# GEMINI TEXT TO SPEECH
# ==========================================

def create_voice(text, output_file):

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{TTS_MODEL}:generateContent"
    )

    payload = {
        "contents": [{
            "parts": [{
                "text": text
            }]
        }],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {
                        "voiceName": VOICE_NAME
                    }
                }
            }
        }
    }

    result = gemini_request(url, payload)

    audio_data = None

    for candidate in result.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")

            if inline and inline.get("data"):
                audio_data = base64.b64decode(inline["data"])
                break

        if audio_data:
            break

    if not audio_data:
        raise RuntimeError("Gemini TTS बाट आवाज प्राप्त भएन।")

    # Gemini TTS PCM: 24kHz, 16-bit, mono

    with wave.open(str(output_file), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(audio_data)

    print("Voice saved:", output_file)


# ==========================================
# DOWNLOAD NEWS IMAGE
# ==========================================

def download_image(url, output_file):

    try:
        response = requests.get(
            url,
            timeout=45,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        response.raise_for_status()

        image = Image.open(BytesIO(response.content)).convert("RGB")

        image.save(output_file, quality=90)

        return True

    except Exception as exc:
        print("Image download failed:", str(exc))

        return False


# ==========================================
# CREATE NEWS CARD
# ==========================================

def create_news_card(article, number, output_file):

    image_url = str(article.get("image_url", "")).strip()

    image_path = OUTPUT_DIR / f"news_{number}.jpg"

    if image_url:
        download_image(image_url, image_path)

    if image_path.exists():
        try:
            background = Image.open(image_path).convert("RGB")
        except Exception:
            background = Image.new(
                "RGB", (WIDTH, HEIGHT), (25, 30, 45)
            )
    else:
        background = Image.new(
            "RGB", (WIDTH, HEIGHT), (25, 30, 45)
        )

    background = background.resize(
        (WIDTH, HEIGHT),
        Image.Resampling.LANCZOS
    )

    background = ImageEnhance.Brightness(background).enhance(0.48)

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 100))
    background = background.convert("RGBA")
    background.alpha_composite(overlay)

    draw = ImageDraw.Draw(background)

    # Header
    draw.rectangle(
        (0, 0, WIDTH, 125),
        fill=(150, 0, 0, 240)
    )

    header_font = get_font(65)

    draw.text(
        (75, 22),
        "I LOVE CHITWAN",
        font=header_font,
        fill="white"
    )

    # News number
    number_font = get_font(48)

    draw.rounded_rectangle(
        (WIDTH - 390, 165, WIDTH - 70, 245),
        radius=20,
        fill=(190, 0, 0, 240)
    )

    draw.text(
        (WIDTH - 355, 180),
        f"मुख्य समाचार {number}/10",
        font=number_font,
        fill="white"
    )

    # Title
    title = str(article.get("title", "मुख्य समाचार")).strip()

    title_font = get_font(72)

    words = title.split()
    lines = []
    current = ""

    for word in words:
        test = (current + " " + word).strip()

        if draw.textbbox((0, 0), test, font=title_font)[2] < WIDTH - 180:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    y = 330

    for line in lines[:4]:
        draw.text(
            (85, y),
            line,
            font=title_font,
            fill="white",
            stroke_width=2,
            stroke_fill="black"
        )
        y += 105

    # Description
    description = str(article.get("description", "")).strip()

    desc_font = get_font(39)

    desc_lines = textwrap.wrap(
        description,
        width=75
    )[:5]

    y += 45

    for line in desc_lines:
        draw.text(
            (90, y),
            line,
            font=desc_font,
            fill=(245, 245, 245)
        )
        y += 62

    # Footer
    draw.rectangle(
        (0, HEIGHT - 105, WIDTH, HEIGHT),
        fill=(145, 0, 0, 235)
    )

    footer_font = get_font(42)

    draw.text(
        (75, HEIGHT - 82),
        "ताजा समाचारका लागि I LOVE CHITWAN फलो गर्नुहोस्",
        font=footer_font,
        fill="white"
    )

    background.convert("RGB").save(
        output_file,
        quality=95
    )

    print("News card created:", output_file)


# ==========================================
# CREATE VIDEO SEGMENT
# ==========================================

def create_segment(image_file, audio_file, output_file):

    probe = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_file)
        ],
        capture_output=True,
        text=True,
        check=True
    )

    duration = float(probe.stdout.strip())

    command = [
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-framerate", str(FPS),
        "-i", str(image_file),
        "-i", str(audio_file),
        "-t", str(duration),
        "-vf",
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={WIDTH}:{HEIGHT},format=yuv420p",
        "-r", str(FPS),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        str(output_file)
    ]

    subprocess.run(
        command,
        check=True
    )


# ==========================================
# JOIN ALL VIDEOS
# ==========================================

def join_segments(segment_files):

    list_file = OUTPUT_DIR / "video_list.txt"

    with open(list_file, "w", encoding="utf-8") as file:
        for segment in segment_files:
            file.write(
                f"file '{segment.resolve().as_posix()}'\n"
            )

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            str(OUTPUT_FILE)
        ],
        check=True
    )


# ==========================================
# MAIN
# ==========================================

def main():

    if not API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY GitHub Secrets मा भेटिएन।"
        )

    if not NEWS_FILE.exists():
        raise FileNotFoundError(
            f"समाचार फाइल भेटिएन: {NEWS_FILE}"
        )

    if not subprocess.run(
        ["ffmpeg", "-version"],
        capture_output=True
    ).returncode == 0:
        raise RuntimeError("FFmpeg उपलब्ध छैन।")

    with open(NEWS_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    articles = data.get("articles", [])

    if len(articles) < MAX_NEWS:
        raise RuntimeError(
            f"१० समाचार आवश्यक छ। अहिले {len(articles)} मात्र भेटिए।"
        )

    articles = articles[:MAX_NEWS]

    segments = []

    print("I LOVE CHITWAN VIDEO GENERATION STARTED")
    print("Total news:", len(articles))

    # पुरानो output हटाउने
    if OUTPUT_FILE.exists():
        OUTPUT_FILE.unlink()

    for number, article in enumerate(articles, start=1):

        print(f"\nProcessing news {number}/10")

        title = str(article.get("title", "")).strip()
        description = str(article.get("description", "")).strip()

        if not title:
            raise RuntimeError(
                f"समाचार {number} को शीर्षक खाली छ।"
            )

        narration = make_narration(article)

        image_file = OUTPUT_DIR / f"card_{number}.jpg"
        audio_file = OUTPUT_DIR / f"voice_{number}.wav"
        segment_file = OUTPUT_DIR / f"segment_{number}.mp4"

        create_news_card(
            article,
            number,
            image_file
        )

        create_voice(
            narration,
            audio_file
        )

        create_segment(
            image_file,
            audio_file,
            segment_file
        )

        segments.append(segment_file)

        print(f"News {number}/10 completed")

    print("\nJoining all 10 news segments...")

    join_segments(segments)

    if not OUTPUT_FILE.exists():
        raise RuntimeError("अन्तिम भिडियो निर्माण हुन सकेन।")

    if OUTPUT_FILE.stat().st_size < 100000:
        raise RuntimeError("अन्तिम भिडियोको आकार असामान्य रूपमा सानो छ।")

    print("\n================================")
    print("VIDEO CREATED SUCCESSFULLY!")
    print("File:", OUTPUT_FILE)
    print(
        "Size:",
        round(OUTPUT_FILE.stat().st_size / (1024 * 1024), 2),
        "MB"
    )
    print("================================")


if __name__ == "__main__":
    main()
