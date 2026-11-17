
import json
import re
import time
import os
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from html import unescape
from html.parser import HTMLParser
from datetime import datetime, timezone

# =====================================
# I LOVE CHITWAN NEWS AUTOMATION
# 1 CHITWAN + 4 NATIONAL NEWS
# =====================================

CHITWAN_QUERY = (
    "चितवन OR भरतपुर OR माडी OR रत्ननगर OR "
    "खैरहनी OR राप्ती OR कालिका OR इच्छाकामना"
)

GOOGLE_CHITWAN = (
    "https://news.google.com/rss/search?q="
    + urllib.parse.quote(CHITWAN_QUERY)
    + "&hl=ne&gl=NP&ceid=NP:ne"
)

FEEDS = {
    "Chitwan Google News": {
        "url": GOOGLE_CHITWAN,
        "category": "chitwan"
    },
    "Ratopati": {
        "url": "https://www.ratopati.com/feed",
        "category": "national"
    },
    "Onlinekhabar": {
        "url": "https://www.onlinekhabar.com/feed",
        "category": "national"
    },
    "Nepal Google News": {
        "url": (
            "https://news.google.com/rss/search?q="
            + urllib.parse.quote("नेपाल राष्ट्रिय समाचार")
            + "&hl=ne&gl=NP&ceid=NP:ne"
        ),
        "category": "national"
    }
}

OUTPUT_FILE = "news.json"
MAX_NEWS = 5
REQUEST_TIMEOUT = 25

CHITWAN_WORDS = [
    "चितवन", "भरतपुर", "माडी", "रत्ननगर",
    "खैरहनी", "राप्ती नगरपालिका", "राप्ती",
    "कालिका नगरपालिका", "इच्छाकामना",
    "सौराहा", "मेघौली", "पटिहानी",
    "देवघाट", "जुटपानी", "पर्सा"
]


def clean_text(value):
    if not value:
        return ""
    value = unescape(str(value))
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def is_chitwan(title, description=""):
    text = (title + " " + description).lower()
    return any(word.lower() in text for word in CHITWAN_WORDS)


class ParagraphParser(HTMLParser):

    def __init__(self):
        super().__init__()
        self.parts = []
        self.current = ""
        self.in_p = False
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in (
            "script", "style", "nav", "footer",
            "header", "aside", "noscript"
        ):
            self.skip += 1
        elif tag.lower() == "p" and not self.skip:
            self.in_p = True
            self.current = ""

    def handle_data(self, data):
        if self.in_p and not self.skip:
            self.current += data

    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag in (
            "script", "style", "nav", "footer",
            "header", "aside", "noscript"
        ):
            self.skip = max(0, self.skip - 1)

        elif tag == "p" and self.in_p:
            p = clean_text(self.current)

            if len(p) > 35:
                self.parts.append(p)

            self.in_p = False
            self.current = ""


def read_article(url):
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept-Language": "ne-NP,ne;q=0.9,en;q=0.8"
            }
        )

        with urllib.request.urlopen(
            req, timeout=REQUEST_TIMEOUT
        ) as response:
            html = response.read().decode(
                "utf-8", errors="replace"
            )

        parser = ParagraphParser()
        parser.feed(html)

        return " ".join(parser.parts)[:5000]

    except Exception as exc:
        print("Article detail unavailable:", url, exc)
        return ""


def child_text(item, names):
    for child in item.iter():
        tag = child.tag.split("}")[-1].lower()

        if tag in names and child.text:
            value = clean_text(child.text)

            if value:
                return value

    return ""


def get_link(item, feed_url):
    for child in item.iter():
        if child.tag.split("}")[-1].lower() == "link":
            link = (
                child.attrib.get("href")
                or child.text
                or ""
            ).strip()

            if link:
                return urllib.parse.urljoin(
                    feed_url, link
                )

    return ""


def get_description(item):
    values = []

    for child in item.iter():
        tag = child.tag.split("}")[-1].lower()

        if tag in (
            "encoded", "description",
            "summary", "content"
        ) and child.text:

            value = clean_text(child.text)

            if value and value not in values:
                values.append(value)

    return max(values, key=len) if values else ""


def get_image(item, raw_description):
    for child in item.iter():
        tag = child.tag.split("}")[-1].lower()

        if tag in ("content", "thumbnail", "enclosure"):
            url = child.attrib.get("url", "")
            media_type = child.attrib.get("type", "")

            if url.startswith("http") and (
                tag != "enclosure"
                or not media_type
                or media_type.startswith("image")
            ):
                return url

    match = re.search(
        r"""<img[^>]+src=["'](https?://[^"']+)""",
        raw_description or "",
        re.I
    )

    return match.group(1) if match else ""


def fetch_feed(source, config):

    feed_url = config["url"]
    category = config["category"]

    print("Fetching:", source)

    req = urllib.request.Request(
        feed_url,
        headers={
            "User-Agent": "Mozilla/5.0 NewsAutomation/4.0"
        }
    )

    with urllib.request.urlopen(
        req, timeout=REQUEST_TIMEOUT
    ) as response:
        root = ET.fromstring(response.read())

    results = []

    for item in root.iter():

        if item.tag.split("}")[-1].lower() not in (
            "item", "entry"
        ):
            continue

        title = child_text(item, ["title"])
        link = get_link(item, feed_url)

        if not title or not link:
            continue

        raw = get_description(item)

        local = is_chitwan(title, raw)

        results.append({
            "source": source,
            "category": (
                "chitwan" if local else category
            ),
            "title": title,
            "description": raw or title,
            "link": link.split("#")[0].rstrip("/"),
            "image_url": get_image(item, raw),
            "published": child_text(
                item,
                ["pubdate", "published", "updated"]
            ),
            "collected_at": datetime.now(
                timezone.utc
            ).isoformat()
        })

        # Limit feed processing
        if len(results) >= 15:
            break

    print(source, "articles found:", len(results))

    return results


def main():

    all_articles = []
    failed = []

    # Collect all news feeds
    for source, config in FEEDS.items():

        try:
            articles = fetch_feed(source, config)
            all_articles.extend(articles)

        except Exception as exc:
            print("Feed error:", source, exc)
            failed.append(source)

        time.sleep(1)

    if not all_articles:
        raise RuntimeError(
            "No news received. Existing news.json was not changed."
        )

    # Remove duplicate links
    unique = {}

    for article in all_articles:

        key = article["link"].split("#")[0].rstrip("/")

        if key and key not in unique:
            unique[key] = article

    articles = list(unique.values())

    # Separate Chitwan and national news
    chitwan_news = [
        x for x in articles
        if x["category"] == "chitwan"
    ]

    national_news = [
        x for x in articles
        if x["category"] == "national"
    ]

    # Chitwan gets first priority
    selected = []

    if chitwan_news:
        selected.append(chitwan_news[0])

    # Add four national news
    for article in national_news:

        if len(selected) >= MAX_NEWS:
            break

        selected.append(article)

    # If Chitwan news unavailable, fill all five
    if len(selected) < MAX_NEWS:

        for article in articles:

            if len(selected) >= MAX_NEWS:
                break

            if article not in selected:
                selected.append(article)

    # Get full details only for selected news
    for article in selected:

        detail = read_article(article["link"])

        if len(detail) > len(article["description"]):
            article["description"] = detail

        article["description"] = (
            article["description"] or article["title"]
        )[:5000]

        print(
            "SELECTED:",
            article["category"],
            article["title"]
        )

        time.sleep(0.3)

    # Save output
    output = {
        "updated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "total_news": len(selected),
        "chitwan_news": sum(
            1 for x in selected
            if x["category"] == "chitwan"
        ),
        "national_news": sum(
            1 for x in selected
            if x["category"] == "national"
        ),
        "failed_sources": failed,
        "articles": selected
    }

    temp = OUTPUT_FILE + ".tmp"

    with open(temp, "w", encoding="utf-8") as f:
        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2
        )

    os.replace(temp, OUTPUT_FILE)

    print("--------------------------------")
    print("NEWS COLLECTION SUCCESSFUL")
    print("TOTAL NEWS:", len(selected))
    print("CHITWAN:", output["chitwan_news"])
    print("NATIONAL:", output["national_news"])
    print("--------------------------------")


if __name__ == "__main__":
    main()
