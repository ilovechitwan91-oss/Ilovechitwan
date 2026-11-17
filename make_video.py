
import os
import json
import re
import base64
import subprocess
import wave
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg


# ==========================================
# I LOVE CHITWAN - NEWS VIDEO GENERATOR
# Gemini TTS | Aoede Voice
# One video per run | Maximum 2 per Nepal day
# ==========================================

API_KEY = os.getenv("GEMINI_API_KEY", "")

# Updated Gemini models
TEXT_MODEL = "gemini-3.8-flash"
TTS_MODEL = "gemini-3.8-flash-lite-tts"
VOICE_NAME = "Aoede"

NEWS_FILE = Path("news.json")
PRESENTER_FILE = Path("presenter.png")
HISTORY_FILE = Path("video_history.json")
OUTPUT_DIR = Path("news_videos")

NEPAL_TZ = ZoneInfo("Asia/Kathmandu")
MAX_DAILY_VIDEOS = 2
MAX_VIDEO_SECONDS = 60

OUTPUT_DIR.mkdir(exist_ok=True)


def today():
    return datetime.now(NEPAL_TZ).strftime("%Y-%m-%d")


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def clean_text(value):
    value = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", value).strip()


def make_script(article):
    title = clean_text(article.get("title", ""))
    description = clean_text(article.get("description", ""))

    prompt = f"""
तपाईं नेपाली समाचार वाचक हुनुहुन्छ।

तलको एउटा समाचारलाई मात्र आधार बनाएर
प्राकृतिक नेपाली भाषामा समाचार वाचन स्क्रिप्ट लेख्नुहोस्।

शीर्षक: {title}
विवरण: {description[:5000]}

नियम:
- समाचारको तथ्य नबदल्नुहोस्।
- कुनै नयाँ तथ्य नथप्नुहोस्।
- सरल र शुद्ध नेपाली बोल्ने शैली अपनाउनुहोस्।
- सुरुमा मुख्य समाचार बताउनुहोस्।
- त्यसपछि आवश्यक विवरण दिनुहोस्।
- अन्त्यमा छोटो निष्कर्ष दिनुहोस्।
- ६० सेकेन्डभित्र पढ्न मिल्ने बनाउनुहोस्।
- Hashtag वा अतिरिक्त टिप्पणी नलेख्नुहोस्।
- एउटै समाचार मात्र प्रस्तुत गर्नुहोस्।
"""

    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{TEXT_MODEL}:generateContent"
    )

    response = requests.post(
        url,
        params={"key": API_KEY},
        json={
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        },
        timeout=90
    )

    if not response.ok:
        raise RuntimeError(
            f"Gemini Script API Error {response.status_code}: "
            f"{response.text[:1000]}"
        )

    data = response.json()

    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini ले समाचार स्क्रिप्ट दिएन।")

    parts = candidates[0].get("content", {}).get("parts", [])
    script = " ".join(
        p.get("text", "") for p in parts if p.get("text")
    ).strip()

    if not script:
        raise RuntimeError("समाचार स्क्रिप्ट खाली आयो।")

    return script


def generate_voice(text, output_file):
    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{TTS_MODEL}:generateContent"
    )

    response = requests.post(
        url,
        params={"key": API_KEY},
        json={
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
        },
        timeout=120
    )

    if not response.ok:
        raise RuntimeError(
            f"Gemini TTS API Error {response.status_code}: "
            f"{response.text[:1000]}"
        )

    data = response.json()

    audio_part = None
    candidates = data.get("candidates", [])

    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        for part in parts:
            if "inlineData" in part:
                audio_part = part["inlineData"]
                break

    if not audio_part:
        raise RuntimeError("Gemini ले Audio पठाएन।")

    raw_audio = base64.b64decode(audio_part["data"])

    # Gemini TTS PCM audio to WAV
    sample_rate = 24000
    channels = 1
    bits = 16

    with wave.open(str(output_file), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(bits // 8)
        wav.setframerate(sample_rate)
        wav.writeframes(raw_audio)


def get_font(size):
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansDevanagariUI-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]

    for font_path in candidates:
        if os.path.exists(font_path):
            return ImageFont.truetype(font_path, size)

    return ImageFont.load_default()


def download_image(url):
    try:
        r = requests.get(
            url,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        r.raise_for_status()
        return Image.open(BytesIO(r.content)).convert("RGB")
    except Exception as exc:
        print("News image error:", exc)
        return None


def create_video_image(article, script, output_file):
    width, height = 720, 1280

    canvas = Image.new("RGB", (width, height), "#071a35")
    draw = ImageDraw.Draw(canvas)

    title_font = get_font(35)
    small_font = get_font(23)

    # Header
    draw.rectangle((0, 0, width, 95), fill="#b51225")
    draw.text(
        (30, 22),
        "I LOVE CHITWAN  |  BREAKING NEWS",
        font=small_font,
        fill="white"
    )

    # Presenter
    presenter = Image.open(PRESENTER_FILE).convert("RGB")
    presenter.thumbnail((660, 500))

    px = (width - presenter.width) // 2
    canvas.paste(presenter, (px, 110))

    # News image
    news_image = download_image(article.get("image_url", ""))

    if news_image:
        news_image.thumbnail((660, 300))
        nx = (width - news_image.width) // 2
        canvas.paste(news_image, (nx, 625))
    else:
        draw.rectangle((30, 625, 690, 925), fill="#17365d")
        draw.text(
            (55, 740),
            "I LOVE CHITWAN NEWS",
            font=title_font,
            fill="white"
        )

    # Headline
    draw.rectangle((0, 950, width, 1280), fill="#071a35")

    title = clean_text(article.get("title", ""))
    words = title.split()
    lines = []
    line = ""

    for word in words:
        test = (line + " " + word).strip()
        if draw.textbbox((0, 0), test, font=title_font)[2] > 660:
            if line:
                lines.append(line)
            line = word
        else:
            line = test

    if line:
        lines.append(line)

    y = 970
    for line in lines[:3]:
        draw.text((30, y), line, font=title_font, fill="#ffd166")
        y += 48

    draw.text(
        (30, 1140),
        "समाचार प्रस्तुति | I LOVE CHITWAN",
        font=small_font,
        fill="white"
    )

    canvas.save(output_file, quality=95)


def build_mp4(image_file, audio_file, output_file):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    command = [
        ffmpeg,
        "-y",
        "-loop", "1",
        "-i", str(image_file),
        "-i", str(audio_file),
        "-vf", "scale=720:1280,format=yuv420p",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        "-t", str(MAX_VIDEO_SECONDS),
        "-movflags", "+faststart",
        str(output_file)
    ]

    subprocess.run(command, check=True)


def main():
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY Secret भेटिएन।")

    if not PRESENTER_FILE.exists():
        raise RuntimeError("presenter.png फाइल भेटिएन।")

    news_data = load_json(NEWS_FILE, {})
    articles = news_data.get("articles", [])

    if not articles:
        raise RuntimeError("news.json मा समाचार भेटिएन।")

    history = load_json(HISTORY_FILE, {})
    done = set(history.get("published_links", []))

    daily_count = sum(
        1 for item in history.get("videos", [])
        if item.get("date") == today()
    )

    if daily_count >= MAX_DAILY_VIDEOS:
        print("आजको २ वटा Reel बनिसक्यो।")
        return

    created = False
    errors = []

    for article in articles:
        link = article.get("link", "")

        if not link or link in done:
            continue

        title = clean_text(article.get("title", ""))

        if not title:
            continue

        print("Creating video:", title)

        video_number = len(history.get("videos", [])) + 1

        safe_name = re.sub(
            r"[^a-zA-Z0-9_-]",
            "_",
            str(video_number)
        )

        image_file = OUTPUT_DIR / f"news_{safe_name}.jpg"
        audio_file = OUTPUT_DIR / f"news_{safe_name}.wav"
        video_file = OUTPUT_DIR / f"news_{safe_name}.mp4"

        try:
            script = make_script(article)

            generate_voice(
                script,
                audio_file
            )

            create_video_image(
                article,
                script,
                image_file
            )

            build_mp4(
                image_file,
                audio_file,
                video_file
            )

            if not video_file.exists() or video_file.stat().st_size == 0:
                raise RuntimeError("MP4 भिडियो फाइल बनेन।")

            done.add(link)

            history.setdefault("videos", []).append({
                "date": today(),
                "title": title,
                "link": link,
                "file": str(video_file)
            })

            history["published_links"] = list(done)

            save_json(HISTORY_FILE, history)

            print("VIDEO CREATED:", video_file)
            created = True

            # प्रत्येक Workflow मा एउटा मात्र Reel
            break

        except Exception as exc:
            print("VIDEO FAILED:", exc)
            errors.append(str(exc))

    if not created:
        if errors:
            raise RuntimeError(
                "कुनै पनि समाचारको भिडियो बन्न सकेन। "
                + " | ".join(errors[:3])
            )

        print("नयाँ प्रकाशित गर्न बाँकी समाचार भेटिएन।")
        return

    print("Video generation successful.")


if __name__ == "__main__":
    main()
