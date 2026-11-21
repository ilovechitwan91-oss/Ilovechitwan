
import os
import re
import json
import base64
import wave
import subprocess
import time
import math
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg


# ==========================================
# I LOVE CHITWAN REELS
# 1080 x 1080 SQUARE NEWS VIDEO
# CRUZ MALE PROFESSIONAL VOICE
# PHOTO PAN + ZOOM + HEADLINE ANIMATION
# NEWS TRANSITION + COMPLETE SENTENCES
# ==========================================

API_KEY = os.getenv("GEMINI_API_KEY", "")

TEXT_MODEL = "gemini-3.8-flash"
TTS_MODEL = "gemini-3.8-flash-lite-tts"

# SAME VOICE FOR EVERY NEWS
VOICE_NAME = "Cruz"

NEWS_FILE = Path("news_reels.json")
OUTPUT_DIR = Path("news_videos")
HISTORY_FILE = Path("video_history.json")

NEPAL_TZ = ZoneInfo("Asia/Kathmandu")

WIDTH = 1080
HEIGHT = 1080
FPS = 25

MAX_RETRIES = 3
API_TIMEOUT = (20, 180)

OUTPUT_DIR.mkdir(exist_ok=True)


# ==========================================
# BASIC FUNCTIONS
# ==========================================

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


def run_ffmpeg(command):

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if result.returncode != 0:

        raise RuntimeError(
            "FFmpeg error: " + result.stderr[-2500:]
        )


def audio_duration(audio_file):

    with wave.open(str(audio_file), "rb") as wav:

        return wav.getnframes() / wav.getframerate()


# ==========================================
# GEMINI API
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

            if response.status_code == 429 or response.status_code >= 500:

                raise RuntimeError(
                    f"Gemini error {response.status_code}: "
                    f"{response.text[:500]}"
                )

            if not response.ok:

                raise RuntimeError(
                    f"Gemini API Error {response.status_code}: "
                    f"{response.text[:1000]}"
                )

            return response.json()

        except (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            RuntimeError
        ) as exc:

            last_error = exc

            print(
                f"Gemini retry {attempt}/{MAX_RETRIES}:",
                str(exc)[:300]
            )

            if attempt < MAX_RETRIES:

                time.sleep(5 * (2 ** (attempt - 1)))

    raise RuntimeError(str(last_error))


# ==========================================
# COMPLETE SENTENCE HANDLING
# ==========================================

def complete_script(text):

    text = clean_text(text)

    if not text:
        return ""

    # Remove unwanted quotation marks
    text = text.strip(" \"'“”")

    # Ensure the final sentence has punctuation.
    if not re.search(r"[।!?…]$", text):

        text += "।"

    return text


def fallback_script(article):

    title = clean_text(article.get("title", ""))

    description = clean_text(
        article.get("description", "")
    )

    if not title:
        title = "आजको मुख्य समाचार"

    # Keep complete sentences only.
    sentences = re.split(
        r"(?<=[।!?])\s+",
        description
    )

    valid = []

    for sentence in sentences:

        sentence = clean_text(sentence)

        if len(sentence) > 15:

            if re.search(r"[।!?]$", sentence):
                valid.append(sentence)

        if len(valid) >= 2:
            break

    if valid:

        return complete_script(
            title + "। " + " ".join(valid)
        )

    return complete_script(title)


# ==========================================
# MAKE NEWS SCRIPT
# ==========================================

def make_script(article):

    title = clean_text(article.get("title", ""))

    description = clean_text(
        article.get("description", "")
    )

    prompt = f"""
तपाईं नेपाली टेलिभिजनका अनुभवी समाचार वाचक हुनुहुन्छ।

तलको समाचारलाई प्राकृतिक नेपाली समाचार वाचनमा बदल्नुहोस्।

शीर्षक:
{title}

विवरण:
{description[:2500]}

नियम:

1. समाचारको शीर्षकबाट सुरु गर्नुहोस्।
2. मुख्य विवरण २ देखि ३ पूरा वाक्यमा प्रस्तुत गर्नुहोस्।
3. प्रत्येक वाक्य व्याकरणिक रूपमा पूरा हुनुपर्छ।
4. अन्तिम वाक्य पनि पूरा हुनुपर्छ।
5. बीचमा अधुरो वाक्य नराख्नुहोस्।
6. उपलब्ध तथ्य मात्र प्रयोग गर्नुहोस्।
7. अनुमान वा नयाँ तथ्य नथप्नुहोस्।
8. सरल, स्पष्ट र स्वाभाविक नेपाली बोल्नुहोस्।
9. हरेक समाचारलाई स्वतन्त्र रूपमा प्रस्तुत गर्नुहोस्।
10. ह्यासट्याग, Subtitle वा निर्देशन नलेख्नुहोस्।

समाचार वाचनको पाठ मात्र दिनुहोस्।
"""

    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{TEXT_MODEL}:generateContent"
    )

    try:

        data = gemini_request(
            url,
            {
                "contents": [{
                    "parts": [{"text": prompt}]
                }]
            }
        )

        parts = data.get(
            "candidates", [{}]
        )[0].get(
            "content", {}
        ).get("parts", [])

        script = " ".join(
            p.get("text", "")
            for p in parts
            if p.get("text")
        )

        script = complete_script(script)

        if script:

            print("Complete news script ready.")

            return script

        raise RuntimeError("Empty script")

    except Exception as exc:

        print("Script fallback:", str(exc)[:300])

        return fallback_script(article)


# ==========================================
# GENERATE SAME CRUZ MALE VOICE
# ==========================================

def generate_voice(text, output_file):

    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{TTS_MODEL}:generateContent"
    )

    data = gemini_request(
        url,
        {
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
    )

    audio_part = None

    for part in data.get(
        "candidates", [{}]
    )[0].get(
        "content", {}
    ).get("parts", []):

        if "inlineData" in part:

            audio_part = part["inlineData"]

            break

    if not audio_part:

        raise RuntimeError(
            "Cruz voice audio प्राप्त भएन।"
        )

    raw_audio = base64.b64decode(
        audio_part["data"]
    )

    with wave.open(str(output_file), "wb") as wav:

        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)

        wav.writeframes(raw_audio)

    if not output_file.exists() or output_file.stat().st_size < 100:

        raise RuntimeError("Invalid voice audio")

    print(
        "Voice ready:",
        VOICE_NAME,
        round(audio_duration(output_file), 2),
        "seconds"
    )


# ==========================================
# FONT
# ==========================================

def get_font(size, bold=False):

    candidates = [

        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf"
        if bold else
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",

        "/usr/share/fonts/truetype/noto/NotoSansDevanagariUI-Bold.ttf"
        if bold else
        "/usr/share/fonts/truetype/noto/NotoSansDevanagariUI-Regular.ttf",

        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]

    for path in candidates:

        if os.path.exists(path):

            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


# ==========================================
# DOWNLOAD NEWS PHOTO
# ==========================================

def download_image(url):

    if not url:
        return None

    try:

        response = requests.get(
            url,
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        response.raise_for_status()

        return Image.open(
            BytesIO(response.content)
        ).convert("RGB")

    except Exception as exc:

        print("Photo error:", exc)

        return None


# ==========================================
# CROP PHOTO TO SQUARE
# ==========================================

def square_photo(photo):

    if photo is None:

        photo = Image.new(
            "RGB",
            (WIDTH, HEIGHT),
            "#18243a"
        )

    w, h = photo.size

    ratio = max(
        WIDTH / w,
        HEIGHT / h
    )

    new_size = (
        int(w * ratio),
        int(h * ratio)
    )

    photo = photo.resize(
        new_size,
        Image.Resampling.LANCZOS
    )

    left = (photo.width - WIDTH) // 2
    top = (photo.height - HEIGHT) // 2

    photo = photo.crop((
        left,
        top,
        left + WIDTH,
        top + HEIGHT
    ))

    return photo


# ==========================================
# HEADLINE WRAPPING
# ==========================================

def fit_text(draw, text, font, max_width):

    words = clean_text(text).split()

    lines = []
    current = ""

    for word in words:

        test = (current + " " + word).strip()

        bbox = draw.textbbox(
            (0, 0),
            test,
            font=font
        )

        if bbox[2] <= max_width:

            current = test

        else:

            if current:
                lines.append(current)

            current = word

    if current:
        lines.append(current)

    return lines


# ==========================================
# CREATE PHOTO + HEADLINE LAYER
# ==========================================

def create_news_layers(article, number):

    photo = download_image(
        article.get("image_url", "")
    )

    photo = square_photo(photo)

    base_file = OUTPUT_DIR / f"base_{number:02d}.jpg"

    overlay_file = OUTPUT_DIR / f"headline_{number:02d}.png"

    photo.save(
        base_file,
        quality=95
    )

    # Transparent text layer
    overlay = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (0, 0, 0, 0)
    )

    draw = ImageDraw.Draw(overlay)

    # Bottom headline area
    panel_height = 245

    panel_top = HEIGHT - panel_height

    draw.rectangle(
        (0, panel_top, WIDTH, HEIGHT),
        fill=(255, 255, 255, 250)
    )

    # Red borders
    draw.rectangle(
        (0, panel_top, WIDTH, panel_top + 9),
        fill=(225, 0, 0, 255)
    )

    draw.rectangle(
        (0, HEIGHT - 8, WIDTH, HEIGHT),
        fill=(225, 0, 0, 255)
    )

    title = clean_text(
        article.get("title", "")
    )

    number_text = f"{number}."

    number_font = get_font(58, True)

    title_font = get_font(57, True)

    draw.text(
        (35, panel_top + 62),
        number_text,
        font=number_font,
        fill="#e00000"
    )

    number_width = draw.textbbox(
        (0, 0),
        number_text,
        font=number_font
    )[2]

    lines = fit_text(
        draw,
        title,
        title_font,
        WIDTH - number_width - 100
    )

    # Two lines maximum. Reduce font if needed.
    if len(lines) > 2:

        title_font = get_font(44, True)

        lines = fit_text(
            draw,
            title,
            title_font,
            WIDTH - number_width - 100
        )

    if len(lines) > 2:

        # Keep the complete headline.
        title_font = get_font(36, True)

        lines = fit_text(
            draw,
            title,
            title_font,
            WIDTH - number_width - 100
        )

    y = panel_top + 58

    for line in lines[:2]:

        draw.text(
            (number_width + 65, y),
            line,
            font=title_font,
            fill="#d80000"
        )

        y += 72

    overlay.save(overlay_file)

    return base_file, overlay_file


# ==========================================
# NEWS TRANSITION GRAPHIC
# ==========================================

def create_transition_image(output_file):

    image = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        "#101b30"
    )

    draw = ImageDraw.Draw(image)

    draw.rectangle(
        (0, 0, WIDTH, 20),
        fill="#ed1010"
    )

    draw.rectangle(
        (0, HEIGHT - 20, WIDTH, HEIGHT),
        fill="#ed1010"
    )

    title_font = get_font(86, True)
    small_font = get_font(43, True)

    title = "अर्को समाचार"

    bbox = draw.textbbox(
        (0, 0),
        title,
        font=title_font
    )

    x = (WIDTH - bbox[2]) // 2

    draw.text(
        (x, 420),
        title,
        font=title_font,
        fill="white"
    )

    small = "I LOVE CHITWAN"

    bbox = draw.textbbox(
        (0, 0),
        small,
        font=small_font
    )

    x = (WIDTH - bbox[2]) // 2

    draw.text(
        (x, 570),
        small,
        font=small_font,
        fill="#ff3333"
    )

    image.save(output_file)


# ==========================================
# CREATE ANIMATED VIDEO SEGMENT
# ==========================================

def make_segment(
    image_file,
    overlay_file,
    audio_file,
    output_file
):

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    duration = audio_duration(audio_file)

    # Leave no fixed-length voice cut.
    duration += 0.15

    frames = math.ceil(duration * FPS)

    filter_complex = (
        "[0:v]"
        "zoompan="
        "z='min(1+on*0.00018,1.055)':"
        "x='(iw-iw/zoom)*0.5+"
        "(iw-iw/zoom)*0.35*sin(on/100)':"
        "y='(ih-ih/zoom)*0.5':"
        f"d=1:s={WIDTH}x{HEIGHT}:fps={FPS},"
        "setsar=1"
        "[bg];"

        "[bg][2:v]"
        "overlay="
        "x=0:"
        "y='if(lt(t,0.35),H-(H-h)*t/0.35,H-h)':"
        "format=auto,"
        "fade=t=in:st=0:d=0.20,"
        "format=yuv420p"
        "[v]"
    )

    command = [

        ffmpeg,
        "-y",

        "-loop", "1",
        "-framerate", str(FPS),
        "-i", str(image_file),

        "-i", str(audio_file),

        "-loop", "1",
        "-framerate", str(FPS),
        "-i", str(overlay_file),

        "-filter_complex",
        filter_complex,

        "-map", "[v]",
        "-map", "1:a",

        "-frames:v", str(frames),

        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "22",

        "-c:a", "aac",
        "-b:a", "160k",

        "-r", str(FPS),
        "-pix_fmt", "yuv420p",

        "-shortest",

        "-movflags", "+faststart",

        str(output_file)
    ]

    run_ffmpeg(command)

    if not output_file.exists() or output_file.stat().st_size == 0:

        raise RuntimeError("Video segment failed")


# ==========================================
# CREATE NEWS TRANSITION SEGMENT
# SAME CRUZ VOICE
# ==========================================

def make_news_transition(index):

    image_file = OUTPUT_DIR / "transition.jpg"

    audio_file = OUTPUT_DIR / f"transition_{index:02d}.wav"

    video_file = OUTPUT_DIR / f"transition_{index:02d}.mp4"

    create_transition_image(image_file)

    # Same male Cruz voice for every transition.
    generate_voice(
        "अब अर्को समाचारतर्फ लागौँ।",
        audio_file
    )

    make_segment(
        image_file,
        image_file,
        audio_file,
        video_file
    )

    return video_file


# ==========================================
# JOIN VIDEOS
# ==========================================

def join_segments(segment_files, output_file):

    if not segment_files:

        raise RuntimeError("No videos to join")

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    list_file = OUTPUT_DIR / "segments.txt"

    with open(
        list_file,
        "w",
        encoding="utf-8"
    ) as f:

        for item in segment_files:

            path = str(item.resolve()).replace(
                "'", "'\\''"
            )

            f.write(
                f"file '{path}'\n"
            )

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

    run_ffmpeg(command)


# ==========================================
# MAIN AUTOMATION
# ==========================================

def main():

    if not API_KEY:

        raise RuntimeError(
            "GEMINI_API_KEY भेटिएन।"
        )

    news_data = load_json(
        NEWS_FILE,
        {}
    )

    articles = news_data.get(
        "articles",
        []
    )

    if not articles:

        raise RuntimeError(
            "news_reels.json मा समाचार भेटिएन।"
        )

    articles = articles[:10]

    history = load_json(
        HISTORY_FILE,
        {}
    )

    if (
        history.get("date") == today()
        and history.get("video_created")
    ):

        raise RuntimeError(
            "आजको भिडियो पहिले नै बनेको छ।"
        )

    successful = []

    failed = []

    # ======================================
    # STEP 1: GENERATE COMPLETE NEWS
    # ======================================

    for index, article in enumerate(
        articles,
        start=1
    ):

        print("")
        print("==============================")
        print(f"NEWS {index}/{len(articles)}")
        print("==============================")

        try:

            script = make_script(article)

            print("SCRIPT:", script)

            audio_file = OUTPUT_DIR / f"story_{index:02d}.wav"

            generate_voice(
                script,
                audio_file
            )

            base_file, overlay_file = create_news_layers(
                article,
                index
            )

            video_file = OUTPUT_DIR / f"story_{index:02d}.mp4"

            make_segment(
                base_file,
                overlay_file,
                audio_file,
                video_file
            )

            successful.append(video_file)

            print(
                f"NEWS {index} COMPLETE!"
            )

        except Exception as exc:

            failed.append(index)

            print(
                f"NEWS {index} FAILED:",
                str(exc)[:500]
            )

            continue

    # ======================================
    # STEP 2: INSERT NEWS TRANSITIONS
    # ======================================

    if not successful:

        raise RuntimeError(
            "कुनै पनि समाचारको भिडियो बनेन।"
        )

    final_segments = []

    for index, video_file in enumerate(
        successful,
        start=1
    ):

        final_segments.append(video_file)

        if index < len(successful):

            print(
                "Creating news transition..."
            )

            transition = make_news_transition(index)

            final_segments.append(transition)

    # ======================================
    # STEP 3: FINAL VIDEO
    # ======================================

    output_file = OUTPUT_DIR / "daily_news.mp4"

    join_segments(
        final_segments,
        output_file
    )

    if not output_file.exists() or output_file.stat().st_size == 0:

        raise RuntimeError(
            "Final video creation failed"
        )

    # ======================================
    # STEP 4: SAVE HISTORY
    # ======================================

    history = {

        "date": today(),

        "video_created": True,

        "file": str(output_file),

        "news_count": len(successful),

        "failed_news": failed,

        "resolution": "1080x1080",

        "fps": FPS,

        "voice": VOICE_NAME,

        "voice_style": "Professional Deep Male",

        "subtitle": False,

        "photo_animation": True,

        "headline_animation": True,

        "news_transition": True,

        "complete_sentence": True
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

    print("")
    print("================================")
    print("I LOVE CHITWAN REELS READY!")
    print("================================")

    print("Successful:", len(successful))

    print("Failed:", len(failed))

    print("Resolution: 1080 x 1080")

    print("Voice:", VOICE_NAME)

    print("Photo Motion: ON")

    print("Headline Animation: ON")

    print("News Transition: ON")

    print("Output:", output_file)

    print("================================")


if __name__ == "__main__":

    main()
