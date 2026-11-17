import json
import os
import re
import sys
import time
from pathlib import Path
import requests

API_VERSION = "v27.0"
NEWS_FILE = Path("news.json")
IMAGE_DIR = Path("news_images")
STATE_FILE = Path("published_news.json")
MAX_HISTORY = 500

MAX_PHOTO_RETRIES = 3
MAX_COMMENT_RETRIES = 3
MAX_POSTS_PER_RUN = 5


def load_published():
    if not STATE_FILE.exists():
        return []

    try:
        value = json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        )
        return value if isinstance(value, list) else []
    except Exception:
        return []


def save_published(items):
    temp = STATE_FILE.with_suffix(".tmp")
    temp.write_text(
        json.dumps(
            items[-MAX_HISTORY:],
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )
    temp.replace(STATE_FILE)


def normalize_link(link):
    return (link or "").split("#")[0].rstrip("/")


def hashtags_for(title):
    text = (title or "").lower()

    rules = [
        (("चितवन", "भरतपुर", "रत्ननगर", "खैरहनी",
          "माडी", "राप्ती", "कालिका"),
         ["Chitwan", "ChitwanNews"]),

        (("नेपाल", "नेपाली", "काठमाडौं", "काठमाडौँ",
          "सरकार", "प्रधानमन्त्री"),
         ["Nepal", "NepalNews"]),

        (("भारत", "भारतीय", "दिल्ली"),
         ["India", "IndiaNews"]),

        (("खेल", "क्रिकेट", "फुटबल", "गोल", "खेलाडी"),
         ["Sports", "SportsNews"]),

        (("मौसम", "वर्षा", "बाढी", "पहिरो", "भूकम्प"),
         ["Weather", "DisasterUpdate"]),

        (("शिक्षा", "विद्यालय", "परीक्षा", "विश्वविद्यालय"),
         ["Education", "EducationNews"]),

        (("स्वास्थ्य", "अस्पताल", "चिकित्सक"),
         ["Health", "HealthNews"]),

        (("अर्थ", "बैंक", "व्यापार", "बजेट", "बजार"),
         ["Business", "Economy"]),

        (("दुर्घटना", "प्रहरी", "हत्या", "चोरी", "अपराध"),
         ["CrimeNews", "PublicSafety"]),

        (("निर्वाचन", "चुनाव", "राजनीति", "सांसद"),
         ["Politics", "PoliticalNews"]),
    ]

    tags = []

    for keys, values in rules:
        if any(k in text for k in keys):
            tags.extend(values)

    if not tags:
        tags = ["NewsUpdate", "LatestNews"]

    tags = list(dict.fromkeys(tags))[:4]

    return " ".join(
        "#" + re.sub(r"[^A-Za-z0-9]", "", x)
        for x in tags
    )


def api_error(response):
    try:
        result = response.json()
    except Exception:
        result = {"message": response.text[:1000]}

    error = result.get("error", {})
    return error.get("message") or str(result)


def publish_photo(page_id, token, image_path, caption):
    url = (
        f"https://graph.facebook.com/"
        f"{API_VERSION}/{page_id}/photos"
    )

    last_error = None

    for attempt in range(1, MAX_PHOTO_RETRIES + 1):
        try:
            print(
                f"PHOTO UPLOAD ATTEMPT "
                f"{attempt}/{MAX_PHOTO_RETRIES}"
            )

            with image_path.open("rb") as photo:
                response = requests.post(
                    url,
                    data={
                        "caption": caption,
                        "published": "true",
                        "access_token": token,
                    },
                    files={
                        "source": (
                            image_path.name,
                            photo,
                            "image/jpeg"
                        )
                    },
                    timeout=120,
                )

            result = response.json()

            if not response.ok or "error" in result:
                last_error = api_error(response)
                print("PHOTO API ERROR:", last_error)

                if attempt < MAX_PHOTO_RETRIES:
                    time.sleep(attempt * 5)
                    continue

                break

            post_id = (
                result.get("post_id")
                or result.get("id")
            )

            if not post_id:
                last_error = (
                    "Facebook did not return a post ID: "
                    + str(result)
                )

                if attempt < MAX_PHOTO_RETRIES:
                    time.sleep(attempt * 5)
                    continue

                break

            return post_id

        except Exception as exc:
            last_error = str(exc)
            print("PHOTO REQUEST ERROR:", last_error)

            if attempt < MAX_PHOTO_RETRIES:
                time.sleep(attempt * 5)

    raise RuntimeError(
        "Photo Publish Error after retries: "
        + str(last_error)
    )


def publish_first_comment(post_id, token, link):
    url = (
        f"https://graph.facebook.com/"
        f"{API_VERSION}/{post_id}/comments"
    )

    response = requests.post(
        url,
        data={
            "message": link,
            "access_token": token,
        },
        timeout=60,
    )

    try:
        result = response.json()
    except Exception:
        result = {}

    if not response.ok or "error" in result:
        raise RuntimeError(
            "First Comment Error: " + api_error(response)
        )

    return result.get("id")


def retry_pending_comments(token, published):
    for item in published:
        if item.get("comment_posted") is not False:
            continue

        post_id = item.get("post_id")
        link = normalize_link(item.get("link"))

        if not post_id or not link:
            continue

        for attempt in range(1, MAX_COMMENT_RETRIES + 1):
            try:
                print(
                    f"COMMENT RETRY "
                    f"{attempt}/{MAX_COMMENT_RETRIES}:",
                    item.get("title", "")
                )

                cid = publish_first_comment(
                    post_id, token, link
                )

                item["comment_posted"] = True
                item["comment_id"] = cid
                item.pop("comment_text", None)

                save_published(published)

                print("PENDING COMMENT POSTED:", cid)
                break

            except Exception as exc:
                print("COMMENT RETRY FAILED:", exc)

                if attempt < MAX_COMMENT_RETRIES:
                    time.sleep(attempt * 5)


def main():
    page_id = os.environ.get(
        "FB_PAGE_ID", ""
    ).strip()

    token = os.environ.get(
        "FB_PAGE_ACCESS_TOKEN", ""
    ).strip()

    if not page_id or not token:
        raise RuntimeError(
            "Facebook GitHub Secrets missing"
        )

    if not NEWS_FILE.exists():
        raise FileNotFoundError(
            "news.json not found"
        )

    data = json.loads(
        NEWS_FILE.read_text(encoding="utf-8")
    )

    articles = data.get("articles", [])

    if not articles:
        print("No news available")
        return

    published = load_published()

    # पहिले पोस्ट भएका समाचारका बाँकी कमेन्ट पूरा गर्ने।
    retry_pending_comments(token, published)

    published_links = {
        normalize_link(x.get("link"))
        for x in published
        if isinstance(x, dict)
    }

    success_count = 0
    failed_count = 0
    skipped_count = 0

    for index, article in enumerate(articles, start=1):

        if success_count >= MAX_POSTS_PER_RUN:
            break

        title = (
            article.get("title") or ""
        ).strip()

        link = normalize_link(
            article.get("link")
        )

        if not title or not link:
            print("SKIP: Missing title or link")
            skipped_count += 1
            continue

        if link in published_links:
            print("ALREADY POSTED:", title)
            skipped_count += 1
            continue

        image_path = (
            IMAGE_DIR / f"news_{index:02d}.jpg"
        )

        if not image_path.exists():
            print(
                "HD photo not available; skip:",
                image_path
            )
            skipped_count += 1
            continue

        caption = (
            f"{title}\n\n{hashtags_for(title)}"
        )

        print("\n================================")
        print(
            f"POSTING NEWS "
            f"{success_count + 1}/{MAX_POSTS_PER_RUN}"
        )
        print("TITLE:", title)
        print("IMAGE:", image_path)
        print("================================")

        try:
            post_id = publish_photo(
                page_id,
                token,
                image_path,
                caption[:9500]
            )

        except Exception as exc:
            print(
                "PHOTO FAILED; MOVING TO NEXT NEWS:",
                exc
            )
            failed_count += 1
            continue

        # पोस्ट सफल भएपछि तुरुन्तै इतिहासमा सुरक्षित गर्ने।
        record = {
            "link": link,
            "title": title,
            "post_id": post_id,
            "comment_posted": False,
        }

        published.append(record)
        published_links.add(link)
        save_published(published)

        success_count += 1

        print("PHOTO SUCCESS:", post_id)

        # प्रत्येक पोस्टमा समाचारको लिंक मात्र कमेन्ट गर्ने।
        try:
            comment_id = publish_first_comment(
                post_id, token, link
            )

            record["comment_posted"] = True
            record["comment_id"] = comment_id

            save_published(published)

            print("LINK COMMENT SUCCESS:", comment_id)

        except Exception as exc:
            print(
                "LINK COMMENT FAILED; WILL RETRY:",
                exc
            )

        print(
            f"NEWS POST COMPLETED "
            f"({success_count}/{MAX_POSTS_PER_RUN})"
        )

        # Facebook मा धेरै छिटो अनुरोध नहोस्।
        time.sleep(3)

    print("\n========== FINAL REPORT ==========")
    print("Successfully posted:", success_count)
    print("Failed:", failed_count)
    print("Skipped:", skipped_count)
    print("==================================")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("PUBLISH ERROR:", exc)
        sys.exit(1)
