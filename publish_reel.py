
import os
import requests
from pathlib import Path

API_VERSION = "v27.0"

PAGE_ID = os.getenv("FB_PAGE_ID")
PAGE_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN")

# सम्भावित भिडियो स्थानहरू
VIDEO_PATHS = [
    Path("news_videos/daily_news.mp4"),
    Path("daily_news.mp4"),
    Path("output/daily_news.mp4"),
]

TITLE = "आजका १० प्रमुख समाचार | Daily News"

DESCRIPTION = """आजका १० प्रमुख समाचार एउटै भिडियोमा।

नेपाल तथा विश्वका ताजा घटनाक्रम, तथ्य र जानकारीका लागि हाम्रो Page फलो गर्नुहोस्।

#News #NepalNews #DailyNews #BreakingNews #समाचार
"""

def find_video():
    for path in VIDEO_PATHS:
        print("Checking:", path)
        if path.is_file():
            print("भिडियो भेटियो:", path)
            return path

    raise FileNotFoundError(
        "भिडियो फाइल भेटिएन। जाँच गरिएका स्थानहरू: "
        + ", ".join(str(p) for p in VIDEO_PATHS)
    )


def main():
    if not PAGE_ID or not PAGE_TOKEN:
        raise RuntimeError(
            "FB_PAGE_ID वा FB_PAGE_ACCESS_TOKEN GitHub Secrets मा भेटिएन।"
        )

    video_file = find_video()

    file_size = video_file.stat().st_size

    if file_size < 1000:
        raise RuntimeError("भिडियो फाइल खाली वा धेरै सानो छ।")

    url = (
        f"https://graph-video.facebook.com/"
        f"{API_VERSION}/{PAGE_ID}/videos"
    )

    print("Facebook Page मा भिडियो अपलोड हुँदैछ...")
    print(f"Video size: {file_size / (1024 * 1024):.2f} MB")

    data = {
        "access_token": PAGE_TOKEN,
        "title": TITLE,
        "description": DESCRIPTION,
        "published": "true",
    }

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
            timeout=1800
        )

    try:
        result = response.json()
    except ValueError:
        raise RuntimeError(
            f"Facebook बाट बुझ्न नसकिने जवाफ आयो: {response.text[:500]}"
        )

    if response.status_code != 200 or "id" not in result:
        raise RuntimeError(
            "Facebook भिडियो पोस्ट असफल भयो: " + str(result)
        )

    print("भिडियो सफलतापूर्वक Facebook Page मा प्रकाशित भयो!")
    print("Facebook Video ID:", result["id"])


if __name__ == "__main__":
    main()
