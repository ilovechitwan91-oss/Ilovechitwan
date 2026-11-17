
import os
import sys
import json
from pathlib import Path
import requests

API_VERSION = "v27.0"
PAGE_ID = os.getenv("FB_PAGE_ID", "").strip()
ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "").strip()

VIDEO_DIR = Path("news_videos")
GRAPH_URL = f"https://graph.facebook.com/{API_VERSION}"


def check_response(response, step):
    try:
        data = response.json()
    except Exception:
        raise RuntimeError(
            f"{step} असफल भयो: {response.status_code} "
            f"{response.text[:500]}"
        )

    if not response.ok or "error" in data:
        raise RuntimeError(
            f"{step} असफल भयो: {json.dumps(data, ensure_ascii=False)}"
        )

    return data


def find_video():
    if not VIDEO_DIR.exists():
        raise RuntimeError("news_videos फोल्डर भेटिएन।")

    videos = list(VIDEO_DIR.glob("*.mp4"))

    if not videos:
        raise RuntimeError("प्रकाशित गर्ने MP4 भिडियो भेटिएन।")

    return max(videos, key=lambda p: p.stat().st_mtime)


def publish_reel(video_path):
    file_size = video_path.stat().st_size

    if file_size <= 0:
        raise RuntimeError("भिडियो फाइल खाली छ।")

    print(f"भिडियो: {video_path}")
    print(f"फाइल साइज: {file_size} bytes")

    # चरण १: Reel upload सुरु गर्ने
    start_response = requests.post(
        f"{GRAPH_URL}/{PAGE_ID}/video_reels",
        data={
            "upload_phase": "start",
            "access_token": ACCESS_TOKEN,
        },
        timeout=60,
    )

    start_data = check_response(start_response, "Upload सुरु")

    video_id = start_data.get("video_id")
    upload_url = start_data.get("upload_url")

    if not video_id or not upload_url:
        raise RuntimeError("Meta बाट video_id वा upload_url आएन।")

    if not upload_url.startswith("https://rupload.facebook.com/"):
        raise RuntimeError("Meta ले दिएको upload URL सुरक्षित छैन।")

    print("Upload session तयार भयो।")

    # चरण २: भिडियो Meta मा पठाउने
    with open(video_path, "rb") as video_file:
        upload_response = requests.post(
            upload_url,
            headers={
                "Authorization": f"OAuth {ACCESS_TOKEN}",
                "offset": "0",
                "file_size": str(file_size),
                "Content-Type": "application/octet-stream",
            },
            data=video_file,
            timeout=600,
        )

    upload_data = check_response(upload_response, "भिडियो Upload")

    if upload_data.get("success") is not True:
        raise RuntimeError(f"भिडियो Upload सफल भएन: {upload_data}")

    print("भिडियो Meta मा Upload भयो।")

    # चरण ३: Reel प्रकाशित गर्ने
    finish_response = requests.post(
        f"{GRAPH_URL}/{PAGE_ID}/video_reels",
        data={
            "upload_phase": "finish",
            "video_id": video_id,
            "video_state": "PUBLISHED",
            "title": "आजको मुख्य समाचार",
            "description": (
                "आजको मुख्य समाचार। "
                "थप समाचारका लागि I Love Chitwan सँग जोडिनुहोस्।"
            ),
            "access_token": ACCESS_TOKEN,
        },
        timeout=120,
    )

    finish_data = check_response(finish_response, "Reel प्रकाशित")

    if finish_data.get("success") is not True:
        raise RuntimeError(f"Reel प्रकाशित भएको पुष्टि भएन: {finish_data}")

    print("SUCCESS: Facebook Page Reel प्रकाशित भयो।")
    print("Video ID:", video_id)
    print("Post ID:", finish_data.get("post_id", "उपलब्ध छैन"))


def main():
    if not PAGE_ID or not ACCESS_TOKEN:
        raise RuntimeError("FB_PAGE_ID वा FB_PAGE_ACCESS_TOKEN भेटिएन।")

    video_path = find_video()
    publish_reel(video_path)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("ERROR:", error)
        sys.exit(1)
