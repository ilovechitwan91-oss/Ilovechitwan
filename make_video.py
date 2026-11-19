
import os
import re
import json
import base64
import wave
import subprocess
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg


# ==========================================
# I LOVE CHITWAN - DAILY LANDSCAPE NEWS VIDEO
# 10 NEWS | 1920x1080 | NEPALI VOICE
# ==========================================

API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

TEXT_MODEL = "gemini-3.8-flash"
TTS_MODEL = "gemini-3.8-flash-lite-tts"
VOICE_NAME = "Aoede"

NEWS_FILE = Path("news_reels.json")
OUTPUT_DIR = Path("news_videos")
HISTORY_FILE = Path("video_history.json")

NEPAL_TZ = ZoneInfo("Asia/Kathmandu")
WIDTH = 1920
HEIGHT = 1080

OUTPUT_DIR.mkdir(exist_ok=True)


def today():
    return datetime.now(NEPAL_TZ).strftime("%Y-%m-%d")


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def clean_text(value):
    value = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", value).strip()


def gemini_request(url, payload, timeout=120):
    response = requests.post(
        url,
        params={"key": API_KEY},
        json=payload,
        timeout=timeout
    )

    if not response.ok:
        raise RuntimeError(
            f"Gemini API Error {response.status_code}: "
            f"{response.text[:1000]}"
        )

    return response.json()


def make_script(article):
    title = clean_text(article.get("title", ""))
    description = clean_text(
        article.get("description", "")
    )

    prompt = f"""
तपाईं नेपाली टेलिभिजनका अनुभवी समाचार वाचक हुनुहुन्छ।

तलको समाचारका आधारमा छोटो नेपाली समाचार वाचन तयार गर्नुहोस्।

शीर्षक: {title}
विवरण: {description[:2500]}

नियम:
- उपलब्ध समाचारका तथ्य मात्र प्रयोग गर्नुहोस्।
- नयाँ तथ्य वा अनुमान नथप्नुहोस्।
- सरल र स्वाभाविक नेपाली बोल्नुहोस्।
- शीर्षकबाट सुरु गर्नुहोस्।
- त्यसपछि मुख्य विवरण २ देखि ३ वाक्यमा दिनुहोस्।
- २० देखि ३० सेकेन्डभित्र पढ्न मिल्ने बनाउनुहोस्।
- ह्यासट्याग वा निर्देशन नलेख्नुहोस्।
"""

    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{TEXT_MODEL}:generateContent"
    )

    data = gemini_request(
        url,
        {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
    )

    parts = data.get("candidates", [{}])[0].get(
        "content", {}
    ).get("parts", [])

    script = " ".join(
        p.get("text", "")
        for p in parts
        if p.get("text")
    ).strip()

    if not script:
        raise RuntimeError("समाचार स्क्रिप्ट बनेन।")

    return script


def generate_voice(text, output_file):
    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{TTS_MODEL}:generateContent"
    )

    data = gemini_request(
        url,
        {
            "contents": [{
                "parts": [{"text": text}]
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
    )

    audio_part = None

    for part in data.get("candidates", [{}])[0].get(
        "content", {}
    ).get("parts", []):
        if "inlineData" in part:
            audio_part = part["inlineData"]
            break

    if not audio_part:
        raise RuntimeError("Gemini ले आवाज पठाएन।")

    raw_audio = base64.b64decode(audio_part["data"])

    with wave.open(str(output_file), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(raw_audio)


def get_font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf"
        if bold else
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",

        "/usr/share/fonts/truetype/noto/NotoSansDevanagariUI-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]

    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


def download_image(url):
    if not url:
        return None

    try:
        response = requests.get(
            url,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        response.raise_for_status()

        image = Image.open(
            BytesIO(response.content)
        ).convert("RGB")

        return image

    except Exception as exc:
        print("Photo download failed:", exc)
        return None


def fit_text(draw, text, font, max_width):
    words = clean_text(text).split()
    lines = []
    current = ""

    for word in words:
        test = (current + " " + word).strip()

        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines


def create_news_image(article, number, output_file):
    canvas = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        "#07182e"
    )

    draw = ImageDraw.Draw(canvas)

    # Header
    draw.rectangle(
        (0, 0, WIDTH, 125),
        fill="#b51225"
    )

    header_font = get_font(48, True)

    draw.text(
        (65, 28),
        "I LOVE CHITWAN  |  DAILY NEWS",
        font=header_font,
        fill="white"
    )

    # News photo
    photo = download_image(
        article.get("image_url", "")
    )

    if photo:
        photo.thumbnail((850, 790))

        px = 65 + (850 - photo.width) // 2
        py = 165 + (790 - photo.height) // 2

        canvas.paste(photo, (px, py))
    else:
        draw.rectangle(
            (65, 165, 915, 955),
            fill="#183454"
        )

        draw.text(
            (180, 520),
            "NEWS PHOTO UNAVAILABLE",
            font=get_font(35),
            fill="white"
        )

    # Right side text
    x = 990
    y = 180

    label_font = get_font(36, True)
    title_font = get_font(58, True)
    summary_font = get_font(35)

    draw.text(
        (x, y),
        f"मुख्य समाचार  {number}/10",
        font=label_font,
        fill="#ffca55"
    )

    y += 95

    title = clean_text(article.get("title", ""))

    for line in fit_text(
        draw,
        title,
        title_font,
        850
    )[:5]:

        draw.text(
            (x, y),
            line,
            font=title_font,
            fill="white"
        )
        y += 78

    y += 35

    description = clean_text(
        article.get("description", "")
    )

    # Summary: 2-3 short lines
    summary = description[:320]

    for line in fit_text(
        draw,
        summary,
        summary_font,
        850
    )[:5]:

        draw.text(
            (x, y),
            line,
            font=summary_font,
            fill="#d9e5f2"
        )
        y += 53

    # Footer
    draw.rectangle(
        (0, 1000, WIDTH, HEIGHT),
        fill="#b51225"
    )

    draw.text(
        (65, 1018),
        "I LOVE CHITWAN  |  समाचार अपडेट",
        font=get_font(30, True),
        fill="white"
    )

    canvas.save(output_file, quality=95)


def make_segment(image_file, audio_file, output_file):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    command = [
        ffmpeg,
        "-y",
        "-loop", "1",
        "-i", str(image_file),
        "-i", str(audio_file),
        "-vf", "scale=1920:1080,format=yuv420p",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "stillimage",
        "-r", "25",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_file)
    ]

    subprocess.run(command, check=True)


def join_segments(segment_files, output_file):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    list_file = OUTPUT_DIR / "segments.txt"

    with open(list_file, "w", encoding="utf-8") as f:
        for item in segment_files:
            path = str(item.resolve()).replace("'", "'\\''")
            f.write(f"file '{path}'\n")

    command = [
        ffmpeg,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        "-movflags", "+faststart",
        str(output_file)
    ]

    subprocess.run(command, check=True)


def main():
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY भेटिएन।")

    news_data = load_json(NEWS_FILE, {})
    articles = news_data.get("articles", [])

    if len(articles) < 10:
        raise RuntimeError(
            f"१० समाचार आवश्यक छन्। अहिले {len(articles)} मात्र भेटिए। "
            "भिडियो बनाइएन।"
        )

    articles = articles[:10]

    history = load_json(HISTORY_FILE, {})
    if history.get("date") == today() and history.get("video_created"):
        raise RuntimeError(
            "आजको दैनिक भिडियो पहिले नै बनेको छ।"
        )

    segment_files = []

    for index, article in enumerate(articles, start=1):
        print(f"समाचार {index}/10 तयार हुँदैछ...")

        image_file = OUTPUT_DIR / f"story_{index:02d}.jpg"
        audio_file = OUTPUT_DIR / f"story_{index:02d}.wav"
        segment_file = OUTPUT_DIR / f"story_{index:02d}.mp4"

        script = make_script(article)
        generate_voice(script, audio_file)

        create_news_image(
            article,
            index,
            image_file
        )

        make_segment(
            image_file,
            audio_file,
            segment_file
        )

        segment_files.append(segment_file)

    output_file = OUTPUT_DIR / "daily_news.mp4"

    join_segments(
        segment_files,
        output_file
    )

    if not output_file.exists() or output_file.stat().st_size == 0:
        raise RuntimeError("अन्तिम भिडियो बनेन।")

    history = {
        "date": today(),
        "video_created": True,
        "file": str(output_file),
        "news_count": 10,
        "resolution": "1920x1080"
    }

    with open(
        HISTORY_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            history,
            f,
            ensure_ascii=False,
            indent=2
        )

    print("================================")
    print("१० समाचारको Landscape भिडियो तयार!")
    print("Resolution: 1920 x 1080")
    print("Output:", output_file)
    print("================================")


if __name__ == "__main__":
    main()
