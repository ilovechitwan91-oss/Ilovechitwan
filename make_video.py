
import os
import re
import json
import base64
import wave
import math
import subprocess
import requests
import numpy as np
import imageio_ffmpeg

from pathlib import Path
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageOps


# ==========================================
# I LOVE CHITWAN DAILY NEWS VIDEO
# 5 NEWS | 1920x1080 | NEPALI MALE VOICE
# LIGHT BACKGROUND MUSIC
# ==========================================

API_KEY = os.getenv("GEMINI_API_KEY")

TTS_MODEL = os.getenv(
    "GEMINI_TTS_MODEL",
    "gemini-3.8-flash-lite-tts"
)

VOICE_NAME = "Cruz"

WIDTH = 1920
HEIGHT = 1080
FPS = 25

MAX_NEWS = 5
SAMPLE_RATE = 24000

OUTPUT_DIR = Path("news_videos")
TEMP_DIR = Path("video_temp")

OUTPUT_FILE = OUTPUT_DIR / "daily_news.mp4"

OUTPUT_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


# ==========================================
# FONT
# ==========================================

FONT_PATHS = [
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

def get_font(size, bold=False):

    for path in FONT_PATHS:

        if bold and "Bold" not in path:
            continue

        if os.path.exists(path):

            try:
                return ImageFont.truetype(path, size)

            except Exception:
                pass

    return ImageFont.load_default()


# ==========================================
# GEMINI TEXT TO SPEECH
# ==========================================

def gemini_tts(text, output_file):

    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY भेटिएन।")

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{TTS_MODEL}:generateContent"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "समाचारलाई स्पष्ट, स्वाभाविक, "
                            "विश्वसनीय र गम्भीर नेपाली पुरुष "
                            "समाचार वाचकको शैलीमा पढ्नुहोस्। "
                            "शब्दहरू नछुटाउनुहोस्। "
                            "गति मध्यम राख्नुहोस्।\n\n"
                            + text
                        )
                    }
                ]
            }
        ],
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

    last_error = None

    for attempt in range(1, 4):

        try:

            response = requests.post(
                url,
                params={"key": API_KEY},
                json=payload,
                timeout=300
            )

            if response.status_code == 429:

                raise RuntimeError(
                    "Gemini TTS quota समाप्त भयो।"
                )

            if response.status_code in (500, 502, 503, 504):

                last_error = response.text[:500]

                if attempt < 3:
                    import time
                    time.sleep(15 * attempt)
                    continue

            response.raise_for_status()

            result = response.json()

            parts = (
                result["candidates"][0]
                ["content"]["parts"]
            )

            audio_data = None

            for part in parts:

                inline = (
                    part.get("inlineData")
                    or part.get("inline_data")
                )

                if inline and inline.get("data"):
                    audio_data = inline["data"]
                    break

            if not audio_data:

                raise RuntimeError(
                    "Gemini ले Audio पठाएन: "
                    + str(result)[:500]
                )

            pcm = base64.b64decode(audio_data)

            # Gemini PCM audio लाई WAV मा रूपान्तरण

            with wave.open(str(output_file), "wb") as wav:

                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(SAMPLE_RATE)
                wav.writeframes(pcm)

            print("Voice तयार:", output_file)

            return

        except RuntimeError:
            raise

        except Exception as exc:

            last_error = str(exc)

            print(
                f"TTS retry {attempt}/3:",
                last_error[:300]
            )

            if attempt < 3:
                import time
                time.sleep(10 * attempt)

    raise RuntimeError(
        "Gemini TTS असफल भयो: " + str(last_error)
    )


# ==========================================
# NEWS FILE
# ==========================================

def load_news():

    candidates = [
        Path("news_reels.json"),
        Path("news.json")
    ]

    for file in candidates:

        if not file.exists():
            continue

        print("News file:", file)

        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            articles = data

        elif isinstance(data, dict):

            articles = (
                data.get("articles")
                or data.get("news")
                or data.get("items")
                or []
            )

        else:
            articles = []

        valid = []

        for item in articles:

            if not isinstance(item, dict):
                continue

            title = (
                item.get("title")
                or item.get("headline")
                or item.get("heading")
                or ""
            )

            description = (
                item.get("description")
                or item.get("content")
                or item.get("summary")
                or ""
            )

            if title.strip():

                valid.append({
                    "title": title.strip(),
                    "description": description.strip(),
                    "image_url": (
                        item.get("image_url")
                        or item.get("image")
                        or ""
                    )
                })

        if valid:
            return valid[:MAX_NEWS]

    raise RuntimeError(
        "news_reels.json वा news.json मा समाचार भेटिएन।"
    )


# ==========================================
# IMAGE DOWNLOAD
# ==========================================

def get_news_image(index, image_url):

    image = None

    if image_url:

        try:

            response = requests.get(
                image_url,
                timeout=30,
                headers={
                    "User-Agent": "Mozilla/5.0"
                }
            )

            response.raise_for_status()

            image = Image.open(
                BytesIO(response.content)
            ).convert("RGB")

        except Exception as exc:

            print("Image download failed:", exc)

    # Local news_images fallback

    if image is None:

        folder = Path("news_images")

        if folder.exists():

            files = []

            for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp"):

                files.extend(folder.glob(ext))

            if files:

                path = files[(index - 1) % len(files)]

                try:
                    image = Image.open(path).convert("RGB")
                except Exception:
                    pass

    # Fallback background

    if image is None:

        image = Image.new(
            "RGB",
            (WIDTH, HEIGHT),
            (20, 30, 55)
        )

    return image


# ==========================================
# TEXT WRAPPING
# ==========================================

def wrap_text(draw, text, font, max_width):

    words = str(text).split()

    lines = []
    current = ""

    for word in words:

        test = current + " " + word if current else word

        box = draw.textbbox(
            (0, 0),
            test,
            font=font
        )

        if box[2] - box[0] <= max_width:

            current = test

        else:

            if current:
                lines.append(current)

            current = word

    if current:
        lines.append(current)

    return lines


# ==========================================
# CREATE NEWS SLIDE
# ==========================================

def create_slide(index, total, news):

    image = get_news_image(
        index,
        news["image_url"]
    )

    image = ImageOps.fit(
        image,
        (WIDTH, HEIGHT)
    )

    # Dark overlay

    overlay = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (0, 0, 0, 105)
    )

    image = Image.alpha_composite(
        image.convert("RGBA"),
        overlay
    )

    draw = ImageDraw.Draw(image)

    # Header

    draw.rectangle(
        (0, 0, WIDTH, 125),
        fill=(150, 0, 0, 240)
    )

    header_font = get_font(55, True)

    draw.text(
        (65, 25),
        "I LOVE CHITWAN",
        font=header_font,
        fill="white"
    )

    number_font = get_font(42, True)

    draw.text(
        (WIDTH - 250, 35),
        f"{index}/{total}",
        font=number_font,
        fill="white"
    )

    # Bottom information panel

    draw.rectangle(
        (0, 590, WIDTH, HEIGHT),
        fill=(5, 12, 30, 225)
    )

    title_font = get_font(65, True)
    description_font = get_font(39)

    title_lines = wrap_text(
        draw,
        news["title"],
        title_font,
        1750
    )[:3]

    y = 635

    for line in title_lines:

        draw.text(
            (75, y),
            line,
            font=title_font,
            fill=(255, 225, 80)
        )

        y += 88

    y += 15

    description_lines = wrap_text(
        draw,
        news["description"],
        description_font,
        1750
    )[:3]

    for line in description_lines:

        draw.text(
            (80, y),
            line,
            font=description_font,
            fill="white"
        )

        y += 60

    # Footer

    footer_font = get_font(29)

    draw.text(
        (75, 1030),
        "I LOVE CHITWAN | ताजा समाचार",
        font=footer_font,
        fill=(220, 220, 220)
    )

    path = TEMP_DIR / f"slide_{index}.jpg"

    image.convert("RGB").save(
        path,
        quality=92
    )

    return path


# ==========================================
# AUDIO DURATION
# ==========================================

def audio_duration(path):

    with wave.open(str(path), "rb") as wav:

        return (
            wav.getnframes()
            / wav.getframerate()
        )


# ==========================================
# CREATE LIGHT BACKGROUND MUSIC
# ==========================================

def create_background_music(duration, output_file):

    print("हल्का Background Music तयार हुँदैछ...")

    sample_count = int(
        duration * SAMPLE_RATE
    )

    t = np.arange(
        sample_count,
        dtype=np.float64
    ) / SAMPLE_RATE

    # Soft ambient chord progression

    chords = [
        [130.81, 164.81, 196.00],
        [110.00, 130.81, 164.81],
        [146.83, 174.61, 220.00],
        [130.81, 164.81, 196.00]
    ]

    music = np.zeros(
        sample_count,
        dtype=np.float64
    )

    segment_length = 12

    for i, frequencies in enumerate(chords):

        start = i * segment_length
        end = min(
            start + segment_length,
            duration
        )

        if start >= duration:
            break

        mask = (
            (t >= start)
            & (t < end)
        )

        local_t = t[mask] - start

        for freq in frequencies:

            music[mask] += (
                0.35
                * np.sin(2 * np.pi * freq * local_t)
            )

    # Gentle volume and fade

    music *= 0.025

    fade_in = min(
        SAMPLE_RATE * 2,
        sample_count
    )

    fade_out = min(
        SAMPLE_RATE * 3,
        sample_count
    )

    if fade_in:
        music[:fade_in] *= np.linspace(
            0, 1, fade_in
        )

    if fade_out:
        music[-fade_out:] *= np.linspace(
            1, 0, fade_out
        )

    music = np.clip(
        music,
        -1,
        1
    )

    pcm = (
        music * 32767
    ).astype(np.int16)

    with wave.open(str(output_file), "wb") as wav:

        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm.tobytes())


# ==========================================
# CONCATENATE WAV FILES
# ==========================================

def combine_audio(files, output_file):

    with wave.open(
        str(output_file), "wb"
    ) as output:

        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)

        for file in files:

            with wave.open(str(file), "rb") as source:

                output.writeframes(
                    source.readframes(
                        source.getnframes()
                    )
                )

            # Short pause between news

            silence = np.zeros(
                int(SAMPLE_RATE * 0.4),
                dtype=np.int16
            )

            output.writeframes(
                silence.tobytes()
            )


# ==========================================
# CREATE VIDEO SEGMENTS
# ==========================================

def create_video_segment(
    image_file,
    duration,
    output_file
):

    command = [
        FFMPEG,
        "-y",
        "-loop", "1",
        "-framerate", str(FPS),
        "-i", str(image_file),
        "-t", str(duration),
        "-vf",
        (
            f"scale={WIDTH}:{HEIGHT}:"
            "force_original_aspect_ratio=decrease,"
            f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2,"
            "format=yuv420p"
        ),
        "-r", str(FPS),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "25",
        "-an",
        str(output_file)
    ]

    subprocess.run(
        command,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE
    )


# ==========================================
# CONCATENATE VIDEO SEGMENTS
# ==========================================

def combine_videos(files, output_file):

    list_file = TEMP_DIR / "videos.txt"

    with open(
        list_file,
        "w",
        encoding="utf-8"
    ) as f:

        for file in files:

            path = file.resolve()

            f.write(
                "file '" + str(path) + "'\n"
            )

    subprocess.run(
        [
            FFMPEG,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            str(output_file)
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE
    )


# ==========================================
# FINAL AUDIO MIX
# ==========================================

def add_audio(video, narration, music, output):

    command = [
        FFMPEG,
        "-y",
        "-i", str(video),
        "-i", str(narration),
        "-i", str(music),
        "-filter_complex",
        (
            "[1:a]volume=1.0[voice];"
            "[2:a]volume=0.18[bg];"
            "[voice][bg]amix=inputs=2:"
            "duration=first:dropout_transition=2,"
            "alimiter=limit=0.95[a]"
        ),
        "-map", "0:v",
        "-map", "[a]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        "-shortest",
        str(output)
    ]

    subprocess.run(
        command,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE
    )


# ==========================================
# MAIN
# ==========================================

def main():

    print("=" * 55)
    print("I LOVE CHITWAN VIDEO GENERATION STARTED")
    print("=" * 55)

    if not API_KEY:

        raise RuntimeError(
            "GEMINI_API_KEY GitHub Secrets मा राख्नुहोस्।"
        )

    news = load_news()

    if not news:

        raise RuntimeError(
            "समाचार उपलब्ध छैन।"
        )

    print("Total news:", len(news))

    narration_files = []
    video_files = []

    for index, item in enumerate(news, start=1):

        print("\nProcessing news:", index)

        title = item["title"]

        description = item["description"]

        narration_text = (
            f"समाचार नम्बर {index}। "
            f"{title}। "
            f"{description}"
        )

        # Generate voice

        audio_file = TEMP_DIR / f"voice_{index}.wav"

        gemini_tts(
            narration_text,
            audio_file
        )

        narration_files.append(audio_file)

        duration = audio_duration(audio_file)

        # Add a small display margin

        duration += 1.5

        # Create news image

        slide = create_slide(
            index,
            len(news),
            item
        )

        # Create silent video

        segment = TEMP_DIR / f"video_{index}.mp4"

        create_video_segment(
            slide,
            duration,
            segment
        )

        video_files.append(segment)

        print(
            f"News {index} completed | "
            f"Voice duration: {duration:.1f}s"
        )

    # Combine narration

    narration = TEMP_DIR / "all_voice.wav"

    combine_audio(
        narration_files,
        narration
    )

    total_duration = audio_duration(
        narration
    )

    # Generate light music

    music = TEMP_DIR / "background_music.wav"

    create_background_music(
        total_duration,
        music
    )

    # Combine videos

    silent_video = TEMP_DIR / "silent_video.mp4"

    combine_videos(
        video_files,
        silent_video
    )

    # Final video with voice and music

    add_audio(
        silent_video,
        narration,
        music,
        OUTPUT_FILE
    )

    if not OUTPUT_FILE.exists():

        raise RuntimeError(
            "Final video सिर्जना हुन सकेन।"
        )

    if OUTPUT_FILE.stat().st_size < 1000:

        raise RuntimeError(
            "Final video file खाली छ।"
        )

    print("\n" + "=" * 55)
    print("VIDEO SUCCESSFULLY CREATED!")
    print("Total News:", len(news))
    print("Output:", OUTPUT_FILE)
    print(
        "File Size:",
        round(
            OUTPUT_FILE.stat().st_size / (1024 * 1024),
            2
        ),
        "MB"
    )
    print("=" * 55)


if __name__ == "__main__":

    main()
