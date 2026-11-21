
import os
import sys
import time
import requests

from pathlib import Path

# ==========================================
# I LOVE CHITWAN
# FACEBOOK VIDEO AUTO PUBLISHER
# ==========================================

API_VERSION = "v27.0"

PAGE_ID = os.getenv("FB_PAGE_ID")
PAGE_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN")

VIDEO_FILE = Path("news_videos/daily_news.mp4")

TITLE = "आजका ५ प्रमुख समाचार | I LOVE CHITWAN"

DESCRIPTION = """आजका ५ प्रमुख समाचार एउटै भिडियोमा।

नेपाल तथा विश्वका ताजा घटनाक्रम, तथ्य र जानकारीका लागि हाम्रो Page फलो गर्नुहोस्।

समाचार हेर्नुहोस्, जानकारी प्राप्त गर्नुहोस् र अरूसँग पनि शेयर गर्नुहोस्।

#ILoveChitwan #ChitwanNews #NepalNews #DailyNews #BreakingNews #समाचार
"""

TIMEOUT = 1800


# ==========================================
# CHECK ENVIRONMENT
# ==========================================

def check_settings():

    if not PAGE_ID:

        raise RuntimeError(
            "FB_PAGE_ID GitHub Secrets मा भेटिएन।"
        )

    if not PAGE_TOKEN:

        raise RuntimeError(
            "FB_PAGE_ACCESS_TOKEN GitHub Secrets मा भेटिएन।"
        )

    print("Facebook Page configuration OK.")


# ==========================================
# FIND VIDEO
# ==========================================

def find_video():

    possible_paths = [
        Path("news_videos/daily_news.mp4"),
        Path("daily_news.mp4"),
        Path("output/daily_news.mp4"),
    ]

    print("\nभिडियो खोजिँदैछ...")

    for path in possible_paths:

        print("Checking:", path)

        if path.is_file():

            print("भिडियो भेटियो:", path)

            return path

    raise FileNotFoundError(
        "भिडियो फाइल भेटिएन। "
        "पहिले make_video.py सफल भएको जाँच गर्नुहोस्।"
    )


# ==========================================
# VALIDATE VIDEO
# ==========================================

def validate_video(video_file):

    if not video_file.exists():

        raise FileNotFoundError(
            "भिडियो फाइल उपलब्ध छैन।"
        )

    size = video_file.stat().st_size

    if size < 1000:

        raise RuntimeError(
            "भिडियो फाइल खाली वा धेरै सानो छ।"
        )

    print(
        f"Video Size: {size / (1024 * 1024):.2f} MB"
    )

    with open(video_file, "rb") as f:

        header = f.read(12)

    if len(header) < 8 or header[4:8] != b"ftyp":

        raise RuntimeError(
            "यो मान्य MP4 भिडियो फाइल जस्तो देखिएन।"
        )

    print("MP4 file validation successful.")


# ==========================================
# FACEBOOK VIDEO PUBLISH
# ==========================================

def publish_video(video_file):

    url = (
        f"https://graph-video.facebook.com/"
        f"{API_VERSION}/{PAGE_ID}/videos"
    )

    data = {

        "access_token": PAGE_TOKEN,

        "title": TITLE,

        "description": DESCRIPTION,

        "published": "true",

    }

    print("\nFacebook Page मा भिडियो अपलोड सुरु हुँदैछ...")

    print("Page ID:", PAGE_ID)

    print("Video:", video_file)

    with open(video_file, "rb") as video:

        response = requests.post(

            url,

            data=data,

            files={
                "source": (
                    "daily_news.mp4",
                    video,
                    "video/mp4"
                )
            },

            timeout=TIMEOUT

        )

    try:

        result = response.json()

    except ValueError:

        raise RuntimeError(
            "Facebook बाट JSON जवाफ आएन: "
            + response.text[:1000]
        )

    if response.status_code != 200:

        raise RuntimeError(
            "Facebook Upload Error: "
            + str(result)
        )

    if "id" not in result:

        raise RuntimeError(
            "Facebook ले Video ID दिएन: "
            + str(result)
        )

    video_id = result["id"]

    print("\n====================================")
    print("VIDEO SUCCESSFULLY PUBLISHED!")
    print("Facebook Video ID:", video_id)
    print("====================================")

    return video_id


# ==========================================
# VERIFY FACEBOOK VIDEO
# ==========================================

def verify_video(video_id):

    url = (
        f"https://graph.facebook.com/"
        f"{API_VERSION}/{video_id}"
    )

    params = {

        "fields": "id,status",

        "access_token": PAGE_TOKEN

    }

    try:

        response = requests.get(

            url,

            params=params,

            timeout=60

        )

        result = response.json()

        print("\nFacebook Video Status:")

        print(result)

        if response.status_code != 200:

            print(
                "Status जाँच हुन सकेन। "
                "Upload सफल भएको ID सुरक्षित राख्नुहोस्।"
            )

    except Exception as exc:

        print("Verification warning:", exc)


# ==========================================
# MAIN
# ==========================================

def main():

    print("=" * 50)

    print("I LOVE CHITWAN FACEBOOK VIDEO PUBLISHER")

    print("=" * 50)

    check_settings()

    video_file = find_video()

    validate_video(video_file)

    video_id = publish_video(video_file)

    verify_video(video_id)

    print("\nकाम सफलतापूर्वक सम्पन्न भयो।")


# ==========================================
# START
# ==========================================

if __name__ == "__main__":

    try:

        main()

    except Exception as error:

        print("\nPUBLISH FAILED!")

        print("Error:", str(error))

        sys.exit(1)
