
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
    "Onlinekhabar": "https://www.onlinekhabar.com/feed"
}

OUTPUT_FILE = "news.json"
MAX_NEWS = 40
MAX_DESCRIPTION_CHARS = 3000
REQUEST_TIMEOUT = 25

# प्रत्येक लाइनमा लगभग यति अक्षर राख्ने
LINE_LENGTH = 125
TOTAL_LINES = 4


def clean_text(value):
    if not value:
        return ""

    value = unescape(str(value))
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


class ArticleParser(HTMLParser):

    def __init__(self):
        super().__init__()

        self.paragraphs = []
        self.content_paragraphs = []
        self.current = ""
        self.in_paragraph = False
        self.skip = 0
        self.content_depth = 0
        self.script_text = []
        self.in_script = False

    def handle_starttag(self, tag, attrs):

        tag = tag.lower()
        data = dict(attrs)

        classes = data.get("class", "").lower()
        element_id = data.get("id", "").lower()

        if tag in (
            "script", "style", "nav", "footer",
            "header", "aside", "noscript"
        ):
            self.skip += 1

            if tag == "script":
                self.in_script = True

            return

        if self.skip:
            return

        if (
            tag in ("article", "main")
            or any(
                word in classes + " " + element_id
                for word in (
                    "article-content",
                    "entry-content",
                    "post-content",
                    "story-content",
                    "news-content",
                    "article-body",
                    "detail-content"
                )
            )
        ):
            self.content_depth += 1

        if tag == "p":
            self.in_paragraph = True
            self.current = ""

    def handle_data(self, data):

        if self.in_script:
            self.script_text.append(data)
            return

        if self.skip:
            return

        if self.in_paragraph:
            self.current += data

    def handle_endtag(self, tag):

        tag = tag.lower()

        if tag == "script" and self.in_script:
            self.in_script = False
            self.skip = max(0, self.skip - 1)
            return

        if tag in (
            "style", "nav", "footer",
            "header", "aside", "noscript"
        ):
            self.skip = max(0, self.skip - 1)
            return

        if self.skip:
            return

        if tag == "p" and self.in_paragraph:

            paragraph = clean_text(self.current)

            if len(paragraph) > 30:

                self.paragraphs.append(paragraph)

                if self.content_depth:
                    self.content_paragraphs.append(paragraph)

            self.current = ""
            self.in_paragraph = False

        if tag in ("article", "main"):
            self.content_depth = max(
                0, self.content_depth - 1
            )


def get_page_description(url):

    print("Reading full article:", url)

    try:

        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/120 Safari/537.36"
                ),
                "Accept-Language": "ne-NP,ne;q=0.9,en;q=0.8"
            }
        )

        with urllib.request.urlopen(
            request,
            timeout=REQUEST_TIMEOUT
        ) as response:

            html = response.read().decode(
                "utf-8", errors="replace"
            )

        parser = ArticleParser()
        parser.feed(html)

        candidates = []

        # Structured article data
        for script in parser.script_text:

            try:

                data = json.loads(script)

                def find_article_body(obj):

                    if isinstance(obj, dict):

                        body = obj.get("articleBody")

                        if isinstance(body, str):
                            candidates.append(
                                clean_text(body)
                            )

                        for value in obj.values():
                            find_article_body(value)

                    elif isinstance(obj, list):

                        for value in obj:
                            find_article_body(value)

                find_article_body(data)

            except Exception:
                pass

        # Full article paragraphs
        paragraphs = (
            parser.content_paragraphs
            if parser.content_paragraphs
            else parser.paragraphs
        )

        if paragraphs:
            candidates.append(" ".join(paragraphs))

        # Meta description
        for match in re.findall(
            r'<meta[^>]+(?:name|property)=["\']'
            r'(?:description|og:description)["\'][^>]+'
            r'content=["\'](.*?)["\']',
            html,
            flags=re.I | re.S
        ):
            candidates.append(clean_text(match))

        candidates = [
            text for text in candidates
            if len(text) > 80
        ]

        if candidates:
            return max(candidates, key=len)

    except Exception as error:

        print("Article reading error:", str(error))

    return ""


def get_text(element, names):

    for child in element.iter():

        tag = child.tag.split("}")[-1].lower()

        if tag in names and child.text:

            value = child.text.strip()

            if value:
                return value

    return ""


def get_full_description(item):

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

                text = clean_text(child.text)

                if text and text not in candidates:
                    candidates.append(text)

    return max(candidates, key=len) if candidates else ""


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

    match = re.search(
        r'<img[^>]+src=["\'](https?://[^"\']+)',
        description or "",
        flags=re.I
    )

    return match.group(1) if match else ""


def limit_description(text):

    text = re.sub(r"\s+", " ", str(text or "")).strip()

    if len(text) <= MAX_DESCRIPTION_CHARS:
        return text

    shortened = text[:MAX_DESCRIPTION_CHARS]

    return shortened.rsplit(" ", 1)[0].strip()


def make_four_lines(text):

    """
    समाचारलाई चारवटा लामो लाइनमा विभाजन गर्छ।
    कुनै नयाँ वा काल्पनिक समाचार थप्दैन।
    """

    text = clean_text(text)

    if not text:
        return ""

    # अनावश्यक दोहोरिएका खाली ठाउँ हटाउने
    text = re.sub(r"\s+", " ", text).strip()

    # धेरै लामो विवरण भए उपयोगी भाग मात्र लिने
    text = limit_description(text)

    words = text.split()

    if not words:
        return ""

    lines = []
    current = ""

    for word in words:

        if not current:
            current = word
            continue

        # प्रत्येक लाइनलाई सन्तुलित राख्ने
        if len(current) + len(word) + 1 <= LINE_LENGTH:

            current += " " + word

        else:

            lines.append(current)
            current = word

            if len(lines) == TOTAL_LINES - 1:
                break

    if current and len(lines) < TOTAL_LINES:
        lines.append(current)

    # बाँकी शब्दलाई चौथो लाइनमा थप्ने
    used_words = sum(
        len(line.split()) for line in lines
    )

    remaining = words[used_words:]

    if remaining and lines:

        lines[-1] += " " + " ".join(remaining)

    # चार लाइन नपुगेमा उपलब्ध वाक्यलाई
    # खाली लाइन नराखी सन्तुलित गर्ने
    if len(lines) > TOTAL_LINES:
        lines = lines[:TOTAL_LINES]

    return "\n".join(lines)


def fetch_feed(source, feed_url):

    print("Fetching:", source)

    request = urllib.request.Request(
        feed_url,
        headers={
            "User-Agent": "Mozilla/5.0 NewsAutomation/2.0"
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

        title = clean_text(
            get_text(item, ["title"])
        )

        raw_description = get_full_description(item)

        link = ""

        for child in item.iter():

            child_tag = child.tag.split("}")[-1].lower()

            if child_tag == "link":

                link = (
                    child.attrib.get("href")
                    or child.text
                    or ""
                ).strip()

                if link:
                    break

        if not title or not link:
            continue

        link = urllib.parse.urljoin(feed_url, link)

        # RSS विवरण
        rss_description = clean_text(raw_description)

        # वेबसाइटबाट पूरा समाचार
        website_description = get_page_description(link)

        descriptions = [
            value for value in (
                website_description,
                rss_description
            )
            if value and len(value) > len(title) + 20
        ]

        if descriptions:

            description = max(
                descriptions,
                key=len
            )

        else:

            description = rss_description or title

        # चारवटा लामो लाइन बनाउने
        description = make_four_lines(description)

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

            "description": description,

            "link": link,

            "image_url": image_url,

            "published": published,

            "collected_at": datetime.now(
                timezone.utc
            ).isoformat()

        })

        print("News prepared:", title)

        time.sleep(0.5)

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
