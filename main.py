
import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape
from html.parser import HTMLParser
from datetime import datetime, timezone

FEEDS = {
    "Ratopati": "https://www.ratopati.com/feed",
    "Onlinekhabar": "https://www.onlinekhabar.com/feed"
}

OUTPUT_FILE = "news.json"
MAX_NEWS = 40
MAX_DESCRIPTION_CHARS = 3000


class ImageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "img":
            data = dict(attrs)
            url = (
                data.get("src")
                or data.get("data-src")
                or data.get("data-lazy-src")
            )
            if url and url.startswith("http"):
                self.images.append(url)


def clean_html(value):
    if not value:
        return ""

    value = unescape(str(value))

    value = re.sub(
        r"<script.*?</script>",
        " ",
        value,
        flags=re.I | re.S
    )

    value = re.sub(
        r"<style.*?</style>",
        " ",
        value,
        flags=re.I | re.S
    )

    value = re.sub(
        r"<[^>]+>",
        " ",
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


def get_text(element, names):
    for child in element.iter():
        tag = child.tag.split("}")[-1].lower()

        if tag in names and child.text:
            value = child.text.strip()

            if value:
                return value

    return ""


def get_full_description(item):
    """
    RSS मा उपलब्ध सबैभन्दा लामो description/content लिने।
    """

    candidates = []

    for child in item.iter():
        tag = child.tag.split("}")[-1].lower()

        if tag in (
            "encoded",
            "description",
            "summary",
            "content"
        ):
            if child.text:
                text = clean_html(child.text)

                if text and text not in candidates:
                    candidates.append(text)

    if not candidates:
        return ""

    # उपलब्ध विवरणमध्ये सबैभन्दा लामो विवरण प्रयोग गर्ने।
    return max(candidates, key=len)


def get_image(element, description):
    for child in element.iter():
        tag = child.tag.split("}")[-1].lower()

        if tag in ("content", "thumbnail"):
            url = child.attrib.get("url")

            if url and url.startswith("http"):
                return url

        if tag == "enclosure":
            url = child.attrib.get("url")
            media_type = child.attrib.get("type", "")

            if url and (
                media_type.startswith("image")
                or not media_type
            ):
                return url

    parser = ImageParser()

    try:
        parser.feed(description)
    except Exception:
        pass

    if parser.images:
        return parser.images[0]

    return ""


def limit_complete_sentences(text, max_chars=3000):
    """
    विवरण लामो राख्ने र सम्भव भएसम्म पूरा वाक्य मात्र राख्ने।
    """

    text = re.sub(r"\s+", " ", str(text or "")).strip()

    if len(text) <= max_chars:
        return text

    sentences = re.split(
        r"(?<=[।.!?])\s+",
        text
    )

    result = []
    total = 0

    for sentence in sentences:
        sentence = sentence.strip()

        if not sentence:
            continue

        extra = len(sentence) + (1 if result else 0)

        if result and total + extra > max_chars:
            break

        result.append(sentence)
        total += extra

    if result:
        return " ".join(result)

    return text[:max_chars].rsplit(" ", 1)[0]


def fetch_feed(source, feed_url):
    print("Fetching:", source)

    request = urllib.request.Request(
        feed_url,
        headers={
            "User-Agent": "Mozilla/5.0 NewsAutomation/1.0"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=30
    ) as response:
        xml_data = response.read()

    root = ET.fromstring(xml_data)
    articles = []

    for item in root.iter():
        tag = item.tag.split("}")[-1].lower()

        if tag not in ("item", "entry"):
            continue

        title = get_text(item, ["title"])

        raw_description = get_full_description(item)

        link = ""

        for child in item.iter():
            child_tag = child.tag.split("}")[-1].lower()

            if child_tag == "link":
                link = (
                    child.attrib.get("href")
                    or child.text
                    or ""
                )

                if link:
                    break

        if not title or not link:
            continue

        title = clean_html(title)

        summary = clean_html(raw_description)

        if not summary:
            summary = title

        summary = limit_complete_sentences(
            summary,
            MAX_DESCRIPTION_CHARS
        )

        image_url = get_image(
            item,
            raw_description
        )

        published = get_text(
            item,
            ["pubdate", "published", "updated"]
        )

        articles.append({
            "source": source,
            "title": title,
            "description": summary,
            "link": link.strip(),
            "image_url": image_url,
            "published": published,
            "collected_at": datetime.now(
                timezone.utc
            ).isoformat()
        })

    print(
        source,
        "articles found:",
        len(articles)
    )

    return articles


def main():
    all_articles = []
    failed_sources = []

    for source, feed_url in FEEDS.items():
        try:
            articles = fetch_feed(
                source,
                feed_url
            )

            all_articles.extend(articles)

        except Exception as error:
            print(
                "Feed error:",
                source,
                str(error)
            )

            failed_sources.append(source)

        time.sleep(2)

    if not all_articles:
        raise RuntimeError(
            "No news received. Existing news.json was not changed."
        )

    unique = {}

    for article in all_articles:
        link = (
            article["link"]
            .split("#")[0]
            .rstrip("/")
        )

        if link and link not in unique:
            unique[link] = article

    news = list(unique.values())[:MAX_NEWS]

    output = {
        "updated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "total_news": len(news),

        "failed_sources": failed_sources,

        "articles": news
    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2
        )

    print("--------------------------------")
    print("NEWS COLLECTION SUCCESSFUL")
    print("Total news:", len(news))
    print("Failed sources:", failed_sources)
    print("Saved to:", OUTPUT_FILE)
    print("--------------------------------")


if __name__ == "__main__":
    main()
