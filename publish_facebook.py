import json
import os
import re
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
        value = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except Exception:
        return []


def save_published(items):
    temp = STATE_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(items[-MAX_HISTORY:], ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(STATE_FILE)


def hashtags_for(title):
    text = (title or "").lower()
    rules = [
        (("चितवन", "भरतपुर", "रत्ननगर", "खैरहनी", "माडी", "राप्ती", "कालिका"), ["Chitwan", "ChitwanNews"]),
        (("नेपाल", "नेपाली", "काठमाडौं", "काठमाडौँ", "सरकार", "प्रधानमन्त्री"), ["Nepal", "NepalNews"]),
        (("भारत", "भारतीय", "दिल्ली"), ["India", "IndiaNews"]),
        (("खेल", "क्रिकेट", "फुटबल", "गोल", "खेलाडी"), ["Sports", "SportsNews"]),
        (("मौसम", "वर्षा", "बाढी", "पहिरो", "भूकम्प"), ["Weather", "DisasterUpdate"]),
        (("शिक्षा", "विद्यालय", "परीक्षा", "विश्वविद्यालय"), ["Education", "EducationNews"]),
        (("स्वास्थ्य", "अस्पताल", "चिकित्सक"), ["Health", "HealthNews"]),
        (("अर्थ", "बैंक", "व्यापार", "बजेट", "बजार"), ["Business", "Economy"]),
        (("दुर्घटना", "प्रहरी", "हत्या", "चोरी", "अपराध"), ["CrimeNews", "PublicSafety"]),
        (("निर्वाचन", "चुनाव", "राजनीति", "सांसद"), ["Politics", "PoliticalNews"]),
    ]
    tags = []
    for keys, values in rules:
        if any(k in text for k in keys):
            tags.extend(values)
    if not tags:
        tags = ["NewsUpdate", "LatestNews"]
    tags = list(dict.fromkeys(tags))[:4]
    return " ".join("#" + re.sub(r"[^A-Za-z0-9]", "", x) for x in tags)


def publish_photo(page_id, token, image_path, caption):
    url = f"https://graph.facebook.com/{API_VERSION}/{page_id}/photos"
    with image_path.open("rb") as photo:
        response = requests.post(
            url,
            data={"caption": caption, "published": "true", "access_token": token},
            files={"source": (image_path.name, photo, "image/jpeg")},
            timeout=120,
        )
    result = response.json()
    if not response.ok or "error" in result:
        raise RuntimeError("Photo Publish Error: " + str(result.get("error", {}).get("message", result)))
    post_id = result.get("post_id") or result.get("id")
    if not post_id:
        raise RuntimeError("Facebook did not return a post ID")
    return post_id


def publish_first_comment(post_id, token, message):
    url = f"https://graph.facebook.com/{API_VERSION}/{post_id}/comments"
    response = requests.post(url, data={"message": message, "access_token": token}, timeout=60)
    result = response.json()
    if not response.ok or "error" in result:
        raise RuntimeError("First Comment Error: " + str(result.get("error", {}).get("message", result)))
    return result.get("id")


def retry_pending_comments(token, published):
    for item in published:
        if item.get("comment_posted") is False:
            post_id = item.get("post_id")
            comment_text = item.get("comment_text", "")
            if not post_id or not comment_text:
                continue
            try:
                cid = publish_first_comment(post_id, token, comment_text)
                item["comment_posted"] = True
                item["comment_id"] = cid
                save_published(published)
                print("PENDING COMMENT POSTED:", item.get("title", ""))
            except Exception as exc:
                print("COMMENT RETRY FAILED:", exc)


def main():
    page_id = os.environ.get("FB_PAGE_ID", "").strip()
    token = os.environ.get("FB_PAGE_ACCESS_TOKEN", "").strip()
    if not page_id or not token:
        raise RuntimeError("Facebook GitHub Secrets missing")
    if not NEWS_FILE.exists():
        raise FileNotFoundError("news.json not found")

    data = json.loads(NEWS_FILE.read_text(encoding="utf-8"))
    articles = data.get("articles", [])
    if not articles:
        print("No news available")
        return

    published = load_published()
    retry_pending_comments(token, published)
    published_links = {
        (x.get("link") or "").split("#")[0].rstrip("/")
        for x in published if isinstance(x, dict)
    }

    for index, article in enumerate(articles, start=1):
        title = (article.get("title") or "").strip()
        description = (article.get("description") or "").strip()
        link = (article.get("link") or "").split("#")[0].rstrip("/")
        source = (article.get("source") or "समाचार").strip()
        if not title or not link or link in published_links:
            continue

        image_path = IMAGE_DIR / f"news_{index:02d}.jpg"
        if not image_path.exists():
            print("HD photo not available; skip:", image_path)
            continue

        # Main post: headline and topic-related English hashtags only.
        caption = f"{title}\n\n{hashtags_for(title)}"

        # First comment: story details and clickable source link.
        comment_text = (
            f"📰 पूरा समाचार\n\n{title}\n\n{description}\n\n"
            f"समाचार स्रोत: {source}\n\nपूरा समाचार पढ्नुहोस्: {link}\n\n"
            "❤️ Hamro Chitwan Ramro Chitwan"
        )

        print("Publishing:", title)
        post_id = publish_photo(page_id, token, image_path, caption[:9500])
        record = {
            "link": link,
            "title": title,
            "post_id": post_id,
            "comment_text": comment_text,
            "comment_posted": False,
        }
        published.append(record)
        save_published(published)
        published_links.add(link)
        print("PHOTO SUCCESS:", post_id)

        try:
            comment_id = publish_first_comment(post_id, token, comment_text)
            record["comment_posted"] = True
            record["comment_id"] = comment_id
            save_published(published)
            print("FIRST COMMENT SUCCESS:", comment_id)
        except Exception as exc:
            print("FIRST COMMENT FAILED; WILL RETRY:", exc)

        # One new article per workflow execution.
        print("ONE NEW NEWS POST COMPLETED")
        return

    print("No new unpublished news found in current feed.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("PUBLISH ERROR:", exc)
        sys.exit(1)
