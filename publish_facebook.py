
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

    result = response.json()

    if not response.ok or "error" in result:
        error = result.get("error", {})
        raise RuntimeError(
            "Photo Publish Error: "
            + str(error.get("message", result))
        )

    post_id = result.get("post_id") or result.get("id")

    if not post_id:
        raise RuntimeError(
            "Facebook did not return a post ID."
        )

    return post_id


def publish_first_comment(page_id, token, post_id, message):

    url = (
        f"https://graph.facebook.com/"
        f"{API_VERSION}/{post_id}/comments"
    )

    response = requests.post(
        url,
        data={
            "message": message,
            "access_token": token
        },
        timeout=60
    )

    result = response.json()

    if not response.ok or "error" in result:
        error = result.get("error", {})
        raise RuntimeError(
            "First Comment Error: "
            + str(error.get("message", result))
        )

    return result.get("id")


def retry_pending_comments(page_id, token, published):

    for item in published:

        if item.get("comment_posted") is False:

            post_id = item.get("post_id")
            comment_text = item.get("comment_text", "")

            if not post_id or not comment_text:
                raise RuntimeError(
                    "Pending comment information missing."
                )

            print(
                "Retrying first comment:",
                item.get("title", "")
            )

            comment_id = publish_first_comment(
                page_id,
                token,
                post_id,
                comment_text
            )

            item["comment_posted"] = True
            item["comment_id"] = comment_id

            save_published(published)

            print("FIRST COMMENT SUCCESS!")


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
        NEWS_FILE.read_text(encoding="utf-8")
    )

    articles = data.get("articles", [])

    if not articles:
        print("No news available.")
        return

    published = load_published()

    # पहिले बाँकी रहेका Comment पोस्ट गर्ने
    retry_pending_comments(
        page_id,
        token,
        published
    )

    published_links = {
        item.get("link")
        for item in published
        if isinstance(item, dict)
    }

    # एउटा Workflow मा एउटा मात्र नयाँ समाचार
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
            print("Photo missing:", image_path)
            continue

        # फोटो पोस्टमा छोटो शीर्षक मात्र
        caption = (
            f"📰 {title}\n\n"
            f"❤️ Hamro Chitwan Ramro Chitwan\n"
            f"Facebook: www.fb.com/ilovechitwan"
        )

        # पहिलो Comment मा पूरा समाचार
        comment_text = (
            f"📰 पूरा समाचार\n\n"
            f"{title}\n\n"
            f"{description}\n\n"
            f"समाचार स्रोत: {source}\n\n"
            f"थप जानकारी: {link}\n\n"
            f"❤️ Hamro Chitwan Ramro Chitwan"
        )

        print("Publishing photo:", title)

        post_id = publish_photo(
            page_id,
            token,
            image_path,
            caption[:9500]
        )

        print("PHOTO SUCCESS!")
        print("Facebook Post ID:", post_id)

        # फोटो सफल भएपछि तुरुन्तै सुरक्षित गर्ने
        record = {
            "link": link,
            "title": title,
            "post_id": post_id,
            "comment_text": comment_text,
            "comment_posted": False
        }

        published.append(record)
        save_published(published)

        # पहिलो Comment पोस्ट गर्ने
        comment_id = publish_first_comment(
            page_id,
            token,
            post_id,
            comment_text
        )

        record["comment_posted"] = True
        record["comment_id"] = comment_id

        save_published(published)

        print("FIRST COMMENT SUCCESS!")
        print("Comment ID:", comment_id)
        print("ALL DONE!")

        return

    print("No new unpublished news found.")


if __name__ == "__main__":

    try:
        main()

    except Exception as error:

        print("PUBLISH ERROR:", error)
        sys.exit(1)
