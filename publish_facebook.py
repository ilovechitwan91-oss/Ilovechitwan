
import json
import os
import sys
from pathlib import Path

import requests

API_VERSION = "v27.0"

NEWS_FILE = Path("news.json")
IMAGE_DIR = Path("news_images")
STATE_FILE = Path("published_news.json")

MAX_HISTORY = 500


def load_published():
    if not STATE_FILE.exists():
        return []

    try:
        data = json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        )
        return data if isinstance(data, list) else []

    except Exception:
        return []


def save_published(items):
    temp_file = STATE_FILE.with_suffix(".tmp")

    temp_file.write_text(
        json.dumps(
            items[-MAX_HISTORY:],
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    temp_file.replace(STATE_FILE)


def publish_photo(page_id, token, image_path, caption):

    url = (
        f"https://graph.facebook.com/"
        f"{API_VERSION}/{page_id}/photos"
    )

    with image_path.open("rb") as photo:

        response = requests.post(
            url,
            data={
                "caption": caption,
                "published": "true",
                "access_token": token
            },
            files={
                "source": (
                    image_path.name,
                    photo,
                    "image/jpeg"
                )
            },
            timeout=90
        )

    try:
        result = response.json()
    except ValueError:
        raise RuntimeError(
            "Facebook API returned an invalid response."
        )

    if not response.ok or "error" in result:

        error = result.get("error", {})

        raise RuntimeError(
            "Facebook Error: "
            + str(error.get("message", result))
        )

    return result.get("post_id") or result.get("id")


def main():

    page_id = os.environ.get(
        "FB_PAGE_ID", ""
    ).strip()

    token = os.environ.get(
        "FB_PAGE_ACCESS_TOKEN", ""
    ).strip()

    if not page_id or not token:
        raise RuntimeError(
            "Facebook GitHub Secrets missing!"
        )

    if not NEWS_FILE.exists():
        raise FileNotFoundError(
            "news.json not found!"
        )

    data = json.loads(
        NEWS_FILE.read_text(
            encoding="utf-8"
        )
    )

    articles = data.get("articles", [])

    if not articles:
        print("No news available.")
        return

    published = load_published()

    published_links = {
        item.get("link")
        for item in published
        if isinstance(item, dict)
    }

    # एउटै Workflow मा एउटा मात्र नयाँ समाचार
    for index, article in enumerate(
        articles[:10], start=1
    ):

        title = (
            article.get("title") or ""
        ).strip()

        description = (
            article.get("description") or ""
        ).strip()

        link = (
            article.get("link") or ""
        ).strip()

        source = (
            article.get("source") or "समाचार"
        ).strip()

        if not title or not link:
            continue

        if link in published_links:
            continue

        image_path = (
            IMAGE_DIR /
            f"news_{index:02d}.jpg"
        )

        if not image_path.exists():
            print(
                "Photo missing:",
                image_path
            )
            continue

        caption = (
            f"{title}\n\n"
            f"{description}\n\n"
            f"📰 स्रोत: {source}\n\n"
            f"थप जानकारी: {link}\n\n"
            f"❤️ Hamro Chitwan Ramro Chitwan\n"
            f"Facebook: www.fb.com/ilovechitwan"
        )

        print("Publishing:", title)

        post_id = publish_photo(
            page_id,
            token,
            image_path,
            caption[:9500]
        )

        published.append({
            "link": link,
            "title": title,
            "post_id": post_id
        })

        save_published(published)

        print("SUCCESS!")
        print("Facebook Post ID:", post_id)

        return

    print("No new unpublished news found.")


if __name__ == "__main__":

    try:
        main()

    except Exception as error:

        print("PUBLISH ERROR:", error)

        sys.exit(1)
