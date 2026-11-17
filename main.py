
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
from urllib.parse import urljoin, urlparse

# ==========================================
# I LOVE CHITWAN NEWS AUTOMATION
# 1 CHITWAN + 4 NATIONAL NEWS
# NO GOOGLE NEWS / NO RATOPATI
# ==========================================

OUTPUT_FILE = "news.json"
STATE_FILE = "published_news.json"

MAX_NEWS = 5
REQUEST_TIMEOUT = 25

# ------------------------------------------
# NEWS SOURCES
# ------------------------------------------

NARAYANI_URL = "https://narayanionline.com/chitwan/"
JANA_AASTHA_URL = "https://janaaastha.com/"
ONLINEKHABAR_URL = "https://www.onlinekhabar.com/"
EKANTIPUR_URL = "https://ekantipur.com/"
RONB_URL = "https://www.ronbpost.com/"

ONLINEKHABAR_RSS = "https://www.onlinekhabar.com/feed"

NATIONAL_SOURCE_ORDER = [
    "Jana Aastha",
    "Onlinekhabar",
    "eKantipur",
    "Routine of Nepal Banda"
]

CHITWAN_WORDS = [
    "चितवन",
    "भरतपुर",
    "माडी",
    "रत्ननगर",
    "खैरहनी",
    "इच्छाकामना",
    "कालिका नगरपालिका",
    "राप्ती नगरपालिका",
    "सौराहा",
    "मेघौली",
    "पटिहानी",
    "देवघाट",
    "जुटपानी",
    "chitwan",
    "bharatpur",
    "madi",
    "ratnanagar",
    "khairahani",
    "ichchhakamana"
]


# ==========================================
# TEXT AND LINK HELPERS
# ==========================================

def clean_text(value):

    if not value:
        return ""

    value = unescape(str(value))
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def normalize_link(link):

    if not link:
        return ""

    parsed = urlparse(link.strip())

    if parsed.scheme not in ("http", "https"):
        return ""

    return (
        parsed.scheme
        + "://"
        + parsed.netloc.lower()
        + parsed.path
    ).rstrip("/")


def is_chitwan(title, description=""):

    # स्थानीय समाचार छुट्याउन शीर्षकलाई प्राथमिकता
    text = (title or "").lower()

    return any(
        word.lower() in text
        for word in CHITWAN_WORDS
    )


def make_timestamp():

    return datetime.now(
        timezone.utc
    ).isoformat()


# ==========================================
# PUBLISHED NEWS HISTORY
# ==========================================

def load_published_links():

    links = set()

    if not os.path.exists(STATE_FILE):
        return links

    try:

        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        def collect(obj):

            if isinstance(obj, dict):

                for key, value in obj.items():

                    if (
                        isinstance(key, str)
                        and key.startswith("http")
                    ):

                        normalized = normalize_link(key)

                        if normalized:
                            links.add(normalized)

                    if isinstance(value, str):

                        lower_key = key.lower()

                        if lower_key in (
                            "link",
                            "url",
                            "article_url",
                            "news_url",
                            "original_url"
                        ):

                            normalized = normalize_link(value)

                            if normalized:
                                links.add(normalized)

                    collect(value)

            elif isinstance(obj, list):

                for item in obj:
                    collect(item)

        collect(data)

        print(
            "Published history loaded:",
            len(links)
        )

    except Exception as exc:

        print(
            "History read error:",
            exc
        )

    return links


# ==========================================
# HTML LINK PARSER
# ==========================================

class ArticleLinkParser(HTMLParser):

    def __init__(self):

        super().__init__()

        self.links = []
        self.current_href = None
        self.current_text = ""

    def handle_starttag(self, tag, attrs):

        if tag.lower() == "a":

            attrs = dict(attrs)

            href = (
                attrs.get("href")
                or attrs.get("data-href")
                or ""
            )

            if href:

                self.current_href = href
                self.current_text = ""

    def handle_data(self, data):

        if self.current_href:

            self.current_text += data

    def handle_endtag(self, tag):

        if (
            tag.lower() == "a"
            and self.current_href
        ):

            title = clean_text(
                self.current_text
            )

            self.links.append({
                "href": self.current_href,
                "title": title
            })

            self.current_href = None
            self.current_text = ""


# ==========================================
# ARTICLE DETAIL PARSER
# ==========================================

class ParagraphParser(HTMLParser):

    def __init__(self):

        super().__init__()

        self.parts = []
        self.current = ""
        self.in_p = False
        self.skip = 0

    def handle_starttag(self, tag, attrs):

        tag = tag.lower()

        if tag in (
            "script",
            "style",
            "nav",
            "footer",
            "header",
            "aside",
            "noscript"
        ):

            self.skip += 1

        elif tag == "p" and not self.skip:

            self.in_p = True
            self.current = ""

    def handle_data(self, data):

        if self.in_p and not self.skip:

            self.current += data

    def handle_endtag(self, tag):

        tag = tag.lower()

        if tag in (
            "script",
            "style",
            "nav",
            "footer",
            "header",
            "aside",
            "noscript"
        ):

            self.skip = max(
                0,
                self.skip - 1
            )

        elif tag == "p" and self.in_p:

            paragraph = clean_text(
                self.current
            )

            if len(paragraph) > 35:

                self.parts.append(
                    paragraph
                )

            self.in_p = False
            self.current = ""


class MetaImageParser(HTMLParser):

    def __init__(self):

        super().__init__()

        self.image = ""

    def handle_starttag(self, tag, attrs):

        if tag.lower() != "meta":
            return

        attrs = dict(attrs)

        prop = (
            attrs.get("property", "")
            or attrs.get("name", "")
        ).lower()

        if prop in (
            "og:image",
            "twitter:image"
        ):

            image = attrs.get("content", "")

            if image.startswith("http"):

                self.image = image


# ==========================================
# DOWNLOAD WEBSITE
# ==========================================

def download_page(url):

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120 Safari/537.36"
            ),
            "Accept-Language": (
                "ne-NP,ne;q=0.9,en;q=0.8"
            )
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=REQUEST_TIMEOUT
    ) as response:

        return response.read().decode(
            "utf-8",
            errors="replace"
        )


# ==========================================
# WEBSITE ARTICLE COLLECTOR
# ==========================================

def fetch_website(
    source,
    page_url,
    allowed_domain,
    category,
    published_links,
    limit=20
):

    print("Fetching:", source)

    try:

        html = download_page(page_url)

        parser = ArticleLinkParser()
        parser.feed(html)

        results = []
        seen = set()

        blocked = {
            "category",
            "categories",
            "tag",
            "author",
            "page",
            "search",
            "contact",
            "about",
            "privacy",
            "wp-content",
            "wp-admin",
            "login",
            "register",
            "feed",
            "comment"
        }

        for item in parser.links:

            title = item["title"]

            if len(title) < 15:
                continue

            link = urljoin(
                page_url,
                item["href"]
            )

            parsed = urlparse(link)

            domain = parsed.netloc.lower()

            if not (
                domain == allowed_domain
                or domain == "www." + allowed_domain
            ):
                continue

            path = parsed.path.strip("/")

            if not path:
                continue

            parts = [
                part.lower()
                for part in path.split("/")
                if part
            ]

            if any(
                part in blocked
                for part in parts
            ):
                continue

            link = normalize_link(link)

            if not link:
                continue

            if link in seen:
                continue

            if link in published_links:
                continue

            seen.add(link)

            results.append({

                "source": source,

                "category": category,

                "title": title,

                "description": title,

                "link": link,

                "image_url": "",

                "published": "",

                "collected_at": make_timestamp()

            })

            if len(results) >= limit:
                break

        print(
            source,
            "articles found:",
            len(results)
        )

        return results

    except Exception as exc:

        print(
            source,
            "website error:",
            exc
        )

        return []


# ==========================================
# NARAYANI ONLINE - CHITWAN
# ==========================================

def fetch_narayani(published_links):

    return fetch_website(

        source="Narayani Online",

        page_url=NARAYANI_URL,

        allowed_domain="narayanionline.com",

        category="chitwan",

        published_links=published_links,

        limit=20
    )


# ==========================================
# JANA AASTHA - NATIONAL
# ==========================================

def fetch_janaastha(published_links):

    return fetch_website(

        source="Jana Aastha",

        page_url=JANA_AASTHA_URL,

        allowed_domain="janaaastha.com",

        category="national",

        published_links=published_links,

        limit=20
    )


# ==========================================
# EKANTIPUR - NATIONAL
# ==========================================

def fetch_ekantipur(published_links):

    return fetch_website(

        source="eKantipur",

        page_url=EKANTIPUR_URL,

        allowed_domain="ekantipur.com",

        category="national",

        published_links=published_links,

        limit=20
    )


# ==========================================
# ROUTINE OF NEPAL BANDA - NATIONAL
# Official RONB website
# ==========================================

def fetch_ronb(published_links):

    return fetch_website(

        source="Routine of Nepal Banda",

        page_url=RONB_URL,

        allowed_domain="ronbpost.com",

        category="national",

        published_links=published_links,

        limit=20
    )


# ==========================================
# ONLINEKHABAR RSS
# ==========================================

def child_text(item, names):

    for child in item.iter():

        tag = child.tag.split("}")[-1].lower()

        if tag in names and child.text:

            value = clean_text(
                child.text
            )

            if value:
                return value

    return ""


def get_rss_link(item, feed_url):

    for child in item.iter():

        if (
            child.tag.split("}")[-1].lower()
            == "link"
        ):

            link = (
                child.attrib.get("href")
                or child.text
                or ""
            ).strip()

            if link:

                return urljoin(
                    feed_url,
                    link
                )

    return ""


def get_rss_description(item):

    values = []

    for child in item.iter():

        tag = child.tag.split("}")[-1].lower()

        if tag in (
            "encoded",
            "description",
            "summary",
            "content"
        ) and child.text:

            value = clean_text(
                child.text
            )

            if value and value not in values:

                values.append(value)

    return (
        max(values, key=len)
        if values
        else ""
    )


def get_rss_image(item, raw_description):

    for child in item.iter():

        tag = child.tag.split("}")[-1].lower()

        if tag in (
            "content",
            "thumbnail",
            "enclosure"
        ):

            image_url = child.attrib.get(
                "url",
                ""
            )

            media_type = child.attrib.get(
                "type",
                ""
            )

            if (
                image_url.startswith("http")
                and (
                    tag != "enclosure"
                    or not media_type
                    or media_type.startswith("image")
                )
            ):

                return image_url

    match = re.search(
        r"""<img[^>]+src=["'](https?://[^"']+)""",
        raw_description or "",
        re.I
    )

    return (
        match.group(1)
        if match
        else ""
    )


def fetch_onlinekhabar(published_links):

    print("Fetching Onlinekhabar RSS...")

    try:

        request = urllib.request.Request(
            ONLINEKHABAR_RSS,
            headers={
                "User-Agent": "Mozilla/5.0 NewsAutomation"
            }
        )

        with urllib.request.urlopen(
            request,
            timeout=REQUEST_TIMEOUT
        ) as response:

            root = ET.fromstring(
                response.read()
            )

        results = []
        seen = set()

        for item in root.iter():

            if item.tag.split("}")[-1].lower() not in (
                "item",
                "entry"
            ):
                continue

            title = child_text(
                item,
                ["title"]
            )

            link = get_rss_link(
                item,
                ONLINEKHABAR_RSS
            )

            if not title or not link:
                continue

            link = normalize_link(link)

            if not link:
                continue

            if (
                link in seen
                or link in published_links
            ):
                continue

            seen.add(link)

            description = get_rss_description(
                item
            )

            results.append({

                "source": "Onlinekhabar",

                "category": "national",

                "title": title,

                "description": (
                    description or title
                ),

                "link": link,

                "image_url": get_rss_image(
                    item,
                    description
                ),

                "published": child_text(
                    item,
                    [
                        "pubdate",
                        "published",
                        "updated"
                    ]
                ),

                "collected_at": make_timestamp()

            })

            if len(results) >= 20:
                break

        print(
            "Onlinekhabar articles found:",
            len(results)
        )

        # RSS खाली भए वेबसाइटबाट प्रयास
        if not results:

            print(
                "Onlinekhabar RSS empty; trying website..."
            )

            results = fetch_website(

                source="Onlinekhabar",

                page_url=ONLINEKHABAR_URL,

                allowed_domain="onlinekhabar.com",

                category="national",

                published_links=published_links,

                limit=20
            )

        return results

    except Exception as exc:

        print(
            "Onlinekhabar RSS error:",
            exc
        )

        print(
            "Trying Onlinekhabar website..."
        )

        return fetch_website(

            source="Onlinekhabar",

            page_url=ONLINEKHABAR_URL,

            allowed_domain="onlinekhabar.com",

            category="national",

            published_links=published_links,

            limit=20
        )


# ==========================================
# FULL ARTICLE DETAILS AND IMAGE
# ==========================================

def read_article(url):

    try:

        html = download_page(url)

        paragraph_parser = ParagraphParser()
        paragraph_parser.feed(html)

        image_parser = MetaImageParser()
        image_parser.feed(html)

        detail = " ".join(
            paragraph_parser.parts
        )[:5000]

        return (
            detail,
            image_parser.image
        )

    except Exception as exc:

        print(
            "Article detail unavailable:",
            url,
            exc
        )

        return "", ""


# ==========================================
# REMOVE DUPLICATES
# ==========================================

def remove_duplicates(articles):

    unique = {}
    output = []

    for article in articles:

        link = normalize_link(
            article.get("link", "")
        )

        if not link:
            continue

        if link in unique:
            continue

        article["link"] = link

        unique[link] = True

        output.append(article)

    return output


# ==========================================
# SELECT 1 LOCAL + 4 NATIONAL
# ==========================================

def select_news(all_articles):

    articles = remove_duplicates(
        all_articles
    )

    local_news = [
        item for item in articles
        if (
            item["category"] == "chitwan"
            and item["source"] == "Narayani Online"
        )
    ]

    other_local = [
        item for item in articles
        if (
            item["category"] == "chitwan"
            and item["source"] != "Narayani Online"
        )
    ]

    national_news = [
        item for item in articles
        if item["category"] == "national"
    ]

    selected = []

    # First priority: Narayani local news
    if local_news:

        selected.append(
            local_news[0]
        )

    # If Narayani has no new local story,
    # use another verified Chitwan story
    elif other_local:

        selected.append(
            other_local[0]
        )

    # Prefer one story from each national source
    for source in NATIONAL_SOURCE_ORDER:

        if len(selected) >= MAX_NEWS:
            break

        for article in national_news:

            if article["source"] == source:

                if article not in selected:

                    selected.append(article)
                    break

    # Fill remaining spaces with other new stories
    if len(selected) < MAX_NEWS:

        for article in national_news:

            if len(selected) >= MAX_NEWS:
                break

            if article not in selected:

                selected.append(article)

    # Final fallback: any other new article
    if len(selected) < MAX_NEWS:

        for article in articles:

            if len(selected) >= MAX_NEWS:
                break

            if article not in selected:

                selected.append(article)

    return selected[:MAX_NEWS]


# ==========================================
# MAIN NEWS COLLECTION
# ==========================================

def main():

    print("================================")
    print("I LOVE CHITWAN NEWS AUTOMATION")
    print("================================")

    published_links = load_published_links()

    all_articles = []
    failed = []

    # 1. Narayani Online local news
    narayani = fetch_narayani(
        published_links
    )

    if narayani:
        all_articles.extend(narayani)
    else:
        failed.append("Narayani Online")

    time.sleep(1)

    # 2. Jana Aastha national news
    janaastha = fetch_janaastha(
        published_links
    )

    if janaastha:
        all_articles.extend(janaastha)
    else:
        failed.append("Jana Aastha")

    time.sleep(1)

    # 3. Onlinekhabar national news
    onlinekhabar = fetch_onlinekhabar(
        published_links
    )

    if onlinekhabar:
        all_articles.extend(onlinekhabar)
    else:
        failed.append("Onlinekhabar")

    time.sleep(1)

    # 4. eKantipur national news
    ekantipur = fetch_ekantipur(
        published_links
    )

    if ekantipur:
        all_articles.extend(ekantipur)
    else:
        failed.append("eKantipur")

    time.sleep(1)

    # 5. Routine of Nepal Banda
    ronb = fetch_ronb(
        published_links
    )

    if ronb:
        all_articles.extend(ronb)
    else:
        failed.append("Routine of Nepal Banda")

    # Do not overwrite old news.json if every source failed
    if not all_articles:

        raise RuntimeError(
            "No news received. Existing news.json was not changed."
        )

    # Select news
    selected = select_news(
        all_articles
    )

    if not selected:

        raise RuntimeError(
            "No new articles available."
        )

    # Download details and images
    for article in selected:

        detail, image_url = read_article(
            article["link"]
        )

        if len(detail) > len(
            article.get("description", "")
        ):

            article["description"] = detail

        if image_url:

            article["image_url"] = image_url

        article["description"] = (
            article.get("description")
            or article["title"]
        )[:5000]

        print(
            "SELECTED:",
            article["category"],
            "|",
            article["source"],
            "|",
            article["title"]
        )

        time.sleep(0.5)

    # Prepare output
    output = {

        "updated_at": make_timestamp(),

        "total_news": len(selected),

        "chitwan_news": sum(
            1 for item in selected
            if item["category"] == "chitwan"
        ),

        "national_news": sum(
            1 for item in selected
            if item["category"] == "national"
        ),

        "failed_sources": failed,

        "articles": selected

    }

    # Safe JSON save
    temp_file = OUTPUT_FILE + ".tmp"

    with open(
        temp_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2
        )

    os.replace(
        temp_file,
        OUTPUT_FILE
    )

    print("--------------------------------")
    print("NEWS COLLECTION SUCCESSFUL")
    print("TOTAL NEWS:", output["total_news"])
    print("CHITWAN:", output["chitwan_news"])
    print("NATIONAL:", output["national_news"])
    print("FAILED SOURCES:", failed)
    print("--------------------------------")


if __name__ == "__main__":
    main()
