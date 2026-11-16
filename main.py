import json
import re
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from html import unescape
from html.parser import HTMLParser
from datetime import datetime, timezone

FEEDS = {
    "Ratopati": "https://www.ratopati.com/feed",
    "Onlinekhabar": "https://www.onlinekhabar.com/feed",
}
OUTPUT_FILE = "news.json"
MAX_NEWS = 40
REQUEST_TIMEOUT = 25


def clean_text(value):
    if not value:
        return ""
    value = unescape(str(value))
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


class ParagraphParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.current = ""
        self.in_p = False
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in ("script", "style", "nav", "footer", "header", "aside", "noscript"):
            self.skip += 1
        elif tag.lower() == "p" and not self.skip:
            self.in_p = True
            self.current = ""

    def handle_data(self, data):
        if self.in_p and not self.skip:
            self.current += data

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ("script", "style", "nav", "footer", "header", "aside", "noscript"):
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
            headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "ne-NP,ne;q=0.9,en;q=0.8"}
        )
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            html = response.read().decode("utf-8", errors="replace")
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
            link = (child.attrib.get("href") or child.text or "").strip()
            if link:
                return urllib.parse.urljoin(feed_url, link)
    return ""


def get_description(item):
    values = []
    for child in item.iter():
        tag = child.tag.split("}")[-1].lower()
        if tag in ("encoded", "description", "summary", "content") and child.text:
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
            if url.startswith("http") and (tag != "enclosure" or not media_type or media_type.startswith("image")):
                return url
    match = re.search(r"""<img[^>]+src=[\"'](https?://[^\"']+)""", raw_description or "", re.I)
    return match.group(1) if match else ""


def fetch_feed(source, feed_url):
    print("Fetching:", source)
    req = urllib.request.Request(feed_url, headers={"User-Agent": "Mozilla/5.0 NewsAutomation/3.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        root = ET.fromstring(response.read())

    results = []
    for item in root.iter():
        if item.tag.split("}")[-1].lower() not in ("item", "entry"):
            continue
        title = child_text(item, ["title"])
        link = get_link(item, feed_url)
        if not title or not link:
            continue

        raw = get_description(item)
        detail = read_article(link)
        description = detail if len(detail) > len(raw) else raw
        description = description or title
        results.append({
            "source": source,
            "title": title,
            "description": description[:5000],
            "link": link.split("#")[0].rstrip("/"),
            "image_url": get_image(item, raw),
            "published": child_text(item, ["pubdate", "published", "updated"]),
            "collected_at": datetime.now(timezone.utc).isoformat(),
        })
        print("News prepared:", title)
        time.sleep(0.3)
    print(source, "articles found:", len(results))
    return results


def main():
    all_articles = []
    failed = []
    for source, url in FEEDS.items():
        try:
            all_articles.extend(fetch_feed(source, url))
        except Exception as exc:
            print("Feed error:", source, exc)
            failed.append(source)
        time.sleep(1)

    if not all_articles:
        raise RuntimeError("No news received. Existing news.json was not changed.")

    unique = {}
    for article in all_articles:
        key = article["link"].split("#")[0].rstrip("/")
        if key and key not in unique:
            unique[key] = article

    news = list(unique.values())[:MAX_NEWS]
    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_news": len(news),
        "failed_sources": failed,
        "articles": news,
    }
    temp = OUTPUT_FILE + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    import os
    os.replace(temp, OUTPUT_FILE)
    print("NEWS COLLECTION SUCCESSFUL:", len(news), "articles")


if __name__ == "__main__":
    main()
