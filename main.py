
import json
import re
import os
import time
import urllib.request
import xml.etree.ElementTree as ET

from html import unescape
from html.parser import HTMLParser
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo
from urllib.parse import urljoin, urlparse


# ==========================================
# I LOVE CHITWAN NEWS AUTOMATION
# TODAY'S NEWS ONLY
# 1 CHITWAN + 4 NATIONAL / INTERNATIONAL / SPORTS
# SOURCES: NARAYANI ONLINE, ONLINEKHABAR, RATOPATI
# ==========================================

OUTPUT_FILE = "news.json"
STATE_FILE = "published_news.json"

MAX_NEWS = 5
REQUEST_TIMEOUT = 25
MAX_SOURCE_ARTICLES = 30

NEPAL_TZ = ZoneInfo("Asia/Kathmandu")


# ==========================================
# BACKUP IMAGE
# ==========================================

FALLBACK_IMAGE_URL = (
    "https://raw.githubusercontent.com/"
    "ilovechitwan91-oss/Ilovechitwan/main/"
    "file_00000000b28c8208bbcc5d31991825cf.png"
)


# ==========================================
# NEWS SOURCES
# ==========================================

NARAYANI_URL = "https://narayanionline.com/chitwan/"

ONLINEKHABAR_URL = "https://www.onlinekhabar.com/"
ONLINEKHABAR_RSS = "https://www.onlinekhabar.com/feed"

RATOPATI_URL = "https://www.ratopati.com/"
RATOPATI_SPORTS_URL = "https://www.ratopati.com/sports"
RATOPATI_WORLD_URL = "https://www.ratopati.com/international"


# ==========================================
# KEYWORDS
# ==========================================

CHITWAN_WORDS = [
    "चितवन", "भरतपुर", "नारायणगढ", "माडी",
    "रत्ननगर", "खैरहनी", "इच्छाकामना",
    "कालिका", "राप्ती नगरपालिका", "सौराहा",
    "मेघौली", "पटिहानी", "जुटपानी",
    "देवघाट", "मुग्लिन", "घोप्टेभीर",
    "chitwan", "bharatpur", "narayangadh",
    "madi", "ratnanagar", "khairahani",
    "ichchhakamana", "sauraha", "meghauli"
]

EXCLUDED_WORDS = [
    "health tips", "स्वास्थ्य टिप्स",
    "स्वास्थ्य सुझाव", "स्वस्थ जीवन",
    "राशिफल", "ज्योतिष", "विज्ञापन",
    "प्रायोजित", "प्रमोसन",
    "ग्यालरी", "मनोरञ्जन", "फिल्म",
    "चलचित्र", "गीत सार्वजनिक",
    "म्युजिक भिडियो", "फेसन",
    "रेसिपी", "खाना बनाउने",
    "lifestyle", "horoscope",
    "entertainment", "advertisement",
    "sponsored", "recipe", "fashion"
]

SPORT_WORDS = [
    "खेल", "खेलकुद", "क्रिकेट", "फुटबल",
    "भलिबल", "बास्केटबल", "टेनिस",
    "विश्वकप", "प्रिमियर लिग", "एनपीएल",
    "आईपीएल", "olympic", "cricket",
    "football", "sports", "tournament",
    "world cup", "league", "tennis",
    "basketball", "volleyball"
]

INTERNATIONAL_WORDS = [
    "अमेरिका", "भारत", "चीन", "पाकिस्तान",
    "बंगलादेश", "श्रीलंका", "जापान",
    "रुस", "युक्रेन", "इजरायल",
    "प्यालेस्टाइन", "इरान", "इराक",
    "संयुक्त राष्ट्र", "विश्व",
    "international", "world",
    "america", "india", "china",
    "pakistan", "bangladesh", "japan",
    "russia", "ukraine", "israel",
    "palestine", "iran", "united nations"
]


# ==========================================
# NEPAL DATE AND TIME
# ==========================================

def nepal_today():
    return datetime.now(NEPAL_TZ).date()


def make_timestamp():
    return datetime.now(timezone.utc).isoformat()


def parse_news_date(value):

    if not value:
        return None

    value = str(value).strip()

    if not value:
        return None

    # ISO date / datetime
    try:
        dt = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=NEPAL_TZ)

        return dt.astimezone(NEPAL_TZ).date()

    except Exception:
        pass

    # RSS date format
    try:
        dt = parsedate_to_datetime(value)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=NEPAL_TZ)

        return dt.astimezone(NEPAL_TZ).date()

    except Exception:
        pass

    # Other date formats
    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y"
    ]

    for fmt in formats:

        try:
            return datetime.strptime(
                value[:10], fmt
            ).date()

        except Exception:
            continue

    return None


def is_today_news(article):

    published = parse_news_date(
        article.get("published", "")
    )

    today = nepal_today()

    if published is None:

        print(
            "REJECTED - DATE NOT FOUND:",
            article.get("title", "")
        )

        return False

    if published != today:

        print(
            "REJECTED - OLD NEWS:",
            published,
            article.get("title", "")
        )

        return False

    print(
        "APPROVED TODAY:",
        published,
        article.get("title", "")
    )

    return True


# ==========================================
# TEXT HELPERS
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
        parsed.scheme + "://" +
        parsed.netloc.lower() +
        parsed.path
    ).rstrip("/")


def contains_word(text, words):

    text = (text or "").lower()

    return any(
        word.lower() in text
        for word in words
    )


def is_excluded(article):

    text = (
        article.get("title", "") + " " +
        article.get("description", "")
    ).lower()

    return contains_word(text, EXCLUDED_WORDS)


def is_chitwan_news(article):

    text = (
        article.get("title", "") + " " +
        article.get("description", "")
    )

    return contains_word(text, CHITWAN_WORDS)


def classify_national(article):

    text = (
        article.get("title", "") + " " +
        article.get("description", "")
    )

    if contains_word(text, SPORT_WORDS):
        return "sports"

    if contains_word(text, INTERNATIONAL_WORDS):
        return "international"

    return "national"


# ==========================================
# PUBLISHED HISTORY
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

                        link = normalize_link(key)

                        if link:
                            links.add(link)

                    if isinstance(value, str):

                        if key.lower() in (
                            "link", "url",
                            "article_url",
                            "news_url",
                            "original_url"
                        ):

                            link = normalize_link(value)

                            if link:
                                links.add(link)

                    collect(value)

            elif isinstance(obj, list):

                for item in obj:
                    collect(item)

        collect(data)

        print(
            "Published links loaded:",
            len(links)
        )

    except Exception as exc:

        print("History error:", exc)

    return links


# ==========================================
# HTML ARTICLE LINK PARSER
# ==========================================

class ArticleLinkParser(HTMLParser):

    def __init__(self):

        super().__init__()

        self.links = []
        self.active = False
        self.href = ""
        self.text = ""

    def handle_starttag(self, tag, attrs):

        if tag.lower() == "a" and not self.active:

            attrs = dict(attrs)

            self.href = (
                attrs.get("href")
                or attrs.get("data-href")
                or ""
            )

            if self.href:

                self.active = True
                self.text = ""

    def handle_data(self, data):

        if self.active:
            self.text += " " + data

    def handle_endtag(self, tag):

        if tag.lower() == "a" and self.active:

            title = clean_text(self.text)

            if title:

                self.links.append({
                    "href": self.href,
                    "title": title
                })

            self.active = False
            self.href = ""
            self.text = ""


# ==========================================
# ARTICLE PARAGRAPH PARSER
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
            "script", "style", "nav",
            "footer", "header", "aside",
            "noscript", "form"
        ):

            self.skip += 1

        elif tag == "p" and not self.skip:

            self.in_p = True
            self.current = ""

    def handle_data(self, data):

        if self.in_p and not self.skip:
            self.current += " " + data

    def handle_endtag(self, tag):

        tag = tag.lower()

        if tag in (
            "script", "style", "nav",
            "footer", "header", "aside",
            "noscript", "form"
        ):

            self.skip = max(0, self.skip - 1)

        elif tag == "p" and self.in_p:

            paragraph = clean_text(self.current)

            if len(paragraph) > 35:
                self.parts.append(paragraph)

            self.in_p = False
            self.current = ""


# ==========================================
# META DATA PARSER
# ==========================================

class ArticleMetaParser(HTMLParser):

    def __init__(self):

        super().__init__()

        self.image = ""
        self.dates = []

    def handle_starttag(self, tag, attrs):

        attrs = dict(attrs)

        if tag.lower() == "meta":

            prop = (
                attrs.get("property", "")
                or attrs.get("name", "")
                or attrs.get("itemprop", "")
            ).lower()

            content = attrs.get("content", "")

            if not content:
                return

            if prop in (
                "og:image",
                "twitter:image"
            ):

                if content.startswith("http"):
                    self.image = content

            if prop in (
                "article:published_time",
                "datepublished",
                "publishdate",
                "pubdate",
                "date",
                "article:modified_time"
            ):

                self.dates.append(content)

        if tag.lower() == "time":

            value = attrs.get("datetime", "")

            if value:
                self.dates.append(value)


# ==========================================
# DOWNLOAD WEB PAGE
# ==========================================

def download_page(url):

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 13) "
                "AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36"
            ),
            "Accept-Language": "ne-NP,ne;q=0.9,en;q=0.8"
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
# IMAGE CHECK
# ==========================================

def valid_news_image(url):

    if not url or not url.startswith("http"):
        return False

    bad_words = [
        "logo", "favicon", "placeholder",
        "default", "avatar", "banner",
        "site-icon", "no-image"
    ]

    if contains_word(url, bad_words):
        return False

    return True


# ==========================================
# ARTICLE DATE EXTRACTION
# ==========================================

def extract_article_date(html, parser):

    # First check meta and time tags
    for candidate in parser.dates:

        if parse_news_date(candidate):
            return candidate

    # Check JSON-LD datePublished
    patterns = [
        r'"datePublished"\s*:\s*"([^"]+)"',
        r'"dateCreated"\s*:\s*"([^"]+)"',
        r'"published_time"\s*:\s*"([^"]+)"'
    ]

    for pattern in patterns:

        matches = re.findall(
            pattern, html, re.I
        )

        for candidate in matches:

            if parse_news_date(candidate):
                return candidate

    return ""


# ==========================================
# FULL ARTICLE DETAILS AND IMAGE
# ==========================================

def read_article(url):

    try:

        html = download_page(url)

        paragraph_parser = ParagraphParser()
        paragraph_parser.feed(html)

        meta_parser = ArticleMetaParser()
        meta_parser.feed(html)

        detail = " ".join(
            paragraph_parser.parts
        )[:5000]

        image = meta_parser.image

        if not valid_news_image(image):
            image = ""

        published = extract_article_date(
            html,
            meta_parser
        )

        return detail, image, published

    except Exception as exc:

        print(
            "Article detail error:",
            exc
        )

        return "", "", ""


# ==========================================
# WEBSITE ARTICLE COLLECTOR
# ==========================================

def fetch_website(
    source,
    page_url,
    allowed_domain,
    category,
    published_links,
    limit=30,
    chitwan_only=False
):

    print("Fetching:", source, page_url)

    try:

        html = download_page(page_url)

        parser = ArticleLinkParser()
        parser.feed(html)

        results = []
        seen = set()

        blocked = {
            "category", "categories", "tag",
            "author", "page", "search",
            "contact", "about", "privacy",
            "wp-content", "wp-admin",
            "login", "register", "feed",
            "comment", "sports", "international",
            "national", "video"
        }

        for item in parser.links:

            title = clean_text(item["title"])

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
                or domain.endswith("." + allowed_domain)
            ):
                continue

            path = parsed.path.strip("/")

            if not path:
                continue

            parts = [
                p.lower()
                for p in path.split("/")
                if p
            ]

            if any(
                part in blocked
                for part in parts
            ):
                continue

            link = normalize_link(link)

            if not link:
                continue

            if link in seen or link in published_links:
                continue

            article = {
                "source": source,
                "category": category,
                "title": title,
                "description": title,
                "link": link,
                "image_url": "",
                "published": "",
                "collected_at": make_timestamp()
            }

            if is_excluded(article):
                continue

            if chitwan_only and not is_chitwan_news(article):
                continue

            seen.add(link)
            results.append(article)

            if len(results) >= limit:
                break

        print(
            source,
            "articles:",
            len(results)
        )

        return results

    except Exception as exc:

        print(
            source,
            "error:",
            exc
        )

        return []


# ==========================================
# NARAYANI ONLINE - CHITWAN ONLY
# ==========================================

def fetch_narayani(published_links):

    articles = fetch_website(
        source="Narayani Online",
        page_url=NARAYANI_URL,
        allowed_domain="narayanionline.com",
        category="chitwan",
        published_links=published_links,
        limit=MAX_SOURCE_ARTICLES,
        chitwan_only=True
    )

    results = []

    for article in articles:

        if is_chitwan_news(article):
            results.append(article)

    print(
        "Narayani Chitwan news:",
        len(results)
    )

    return results


# ==========================================
# RSS HELPERS
# ==========================================

def child_text(item, names):

    for child in item.iter():

        tag = child.tag.split("}")[-1].lower()

        if tag in names and child.text:

            value = clean_text(child.text)

            if value:
                return value

    return ""


def get_rss_link(item, feed_url):

    for child in item.iter():

        if child.tag.split("}")[-1].lower() == "link":

            link = (
                child.attrib.get("href")
                or child.text
                or ""
            ).strip()

            if link:
                return urljoin(feed_url, link)

    return ""


def get_rss_description(item):

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

    return max(
        values,
        key=len
    ) if values else ""


def get_rss_image(item, raw_description):

    for child in item.iter():

        tag = child.tag.split("}")[-1].lower()

        if tag in (
            "content", "thumbnail", "enclosure"
        ):

            image = child.attrib.get("url", "")
            media_type = child.attrib.get("type", "")

            if (
                image.startswith("http")
                and (
                    tag != "enclosure"
                    or not media_type
                    or media_type.startswith("image")
                )
                and valid_news_image(image)
            ):

                return image

    match = re.search(
        r"""<img[^>]+src=["'](https?://[^"']+)""",
        raw_description or "",
        re.I
    )

    if match:
        return match.group(1)

    return ""


# ==========================================
# ONLINEKHABAR RSS
# ==========================================

def fetch_onlinekhabar(published_links):

    print("Fetching Onlinekhabar RSS")

    results = []

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

        seen = set()

        for item in root.iter():

            if item.tag.split("}")[-1].lower() not in (
                "item", "entry"
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

            if link in seen or link in published_links:
                continue

            description = get_rss_description(item)

            article = {
                "source": "Onlinekhabar",
                "category": "national",
                "title": title,
                "description": description or title,
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
                        "updated",
                        "date"
                    ]
                ),
                "collected_at": make_timestamp()
            }

            if is_excluded(article):
                continue

            article["category"] = classify_national(
                article
            )

            seen.add(link)
            results.append(article)

            if len(results) >= MAX_SOURCE_ARTICLES:
                break

        print(
            "Onlinekhabar RSS articles:",
            len(results)
        )

    except Exception as exc:

        print(
            "Onlinekhabar RSS error:",
            exc
        )

    # Homepage fallback
    if len(results) < 10:

        extra = fetch_website(
            source="Onlinekhabar",
            page_url=ONLINEKHABAR_URL,
            allowed_domain="onlinekhabar.com",
            category="national",
            published_links=published_links,
            limit=MAX_SOURCE_ARTICLES
        )

        existing = {
            a["link"] for a in results
        }

        for article in extra:

            if article["link"] not in existing:

                article["category"] = classify_national(
                    article
                )

                results.append(article)
                existing.add(article["link"])

    return results


# ==========================================
# RATOPATI
# NATIONAL / INTERNATIONAL / SPORTS
# ==========================================

def fetch_ratopati(published_links):

    results = []
    seen = set()

    pages = [
        (
            RATOPATI_URL,
            "national"
        ),
        (
            RATOPATI_SPORTS_URL,
            "sports"
        ),
        (
            RATOPATI_WORLD_URL,
            "international"
        )
    ]

    for page_url, page_category in pages:

        articles = fetch_website(
            source="Ratopati",
            page_url=page_url,
            allowed_domain="ratopati.com",
            category=page_category,
            published_links=published_links,
            limit=MAX_SOURCE_ARTICLES
        )

        for article in articles:

            if article["link"] in seen:
                continue

            if is_excluded(article):
                continue

            if page_category == "sports":

                article["category"] = "sports"

            elif page_category == "international":

                article["category"] = "international"

            else:

                article["category"] = classify_national(
                    article
                )

            seen.add(article["link"])
            results.append(article)

        time.sleep(1)

    print(
        "Ratopati total articles:",
        len(results)
    )

    return results


# ==========================================
# REMOVE DUPLICATES
# ==========================================

def remove_duplicates(articles):

    output = []
    seen = set()

    for article in articles:

        link = normalize_link(
            article.get("link", "")
        )

        if not link or link in seen:
            continue

        article["link"] = link

        seen.add(link)
        output.append(article)

    return output


# ==========================================
# SELECT 1 CHITWAN + 4 OTHER NEWS
# ==========================================

def select_news(all_articles):

    articles = remove_duplicates(
        all_articles
    )

    local_news = [
        a for a in articles
        if (
            a["source"] == "Narayani Online"
            and a["category"] == "chitwan"
            and is_chitwan_news(a)
        )
    ]

    online_news = [
        a for a in articles
        if a["source"] == "Onlinekhabar"
    ]

    rato_news = [
        a for a in articles
        if a["source"] == "Ratopati"
    ]

    selected = []

    # One Chitwan news first
    if local_news:
        selected.append(local_news[0])

    # Four national / international / sports
    # Alternate Onlinekhabar and Ratopati

    while len(selected) < MAX_NEWS:

        added = False

        for source_list in (
            online_news,
            rato_news
        ):

            if len(selected) >= MAX_NEWS:
                break

            for article in source_list:

                if article not in selected:

                    selected.append(article)
                    added = True
                    break

        if not added:
            break

    return selected[:MAX_NEWS]


# ==========================================
# MAIN
# ==========================================

def main():

    print("====================================")
    print("I LOVE CHITWAN NEWS AUTOMATION")
    print("TODAY'S NEWS ONLY")
    print("====================================")

    print(
        "NEPAL TODAY:",
        nepal_today()
    )

    published_links = load_published_links()

    all_articles = []
    failed = []

    # 1. NARAYANI ONLINE
    narayani = fetch_narayani(
        published_links
    )

    if narayani:
        all_articles.extend(narayani)
    else:
        failed.append(
            "Narayani Online - Chitwan"
        )

    time.sleep(1)

    # 2. ONLINEKHABAR
    online = fetch_onlinekhabar(
        published_links
    )

    if online:
        all_articles.extend(online)
    else:
        failed.append(
            "Onlinekhabar"
        )

    time.sleep(1)

    # 3. RATOPATI
    ratopati = fetch_ratopati(
        published_links
    )

    if ratopati:
        all_articles.extend(ratopati)
    else:
        failed.append(
            "Ratopati"
        )

    print("------------------------------------")
    print(
        "TOTAL COLLECTED:",
        len(all_articles)
    )

    if not all_articles:

        raise RuntimeError(
            "No news received. "
            "Old news.json was not changed."
        )

    # ======================================
    # VERIFY EVERY ARTICLE'S PUBLICATION DATE
    # ======================================

    today_articles = []

    print("------------------------------------")
    print("VERIFYING PUBLICATION DATES")
    print("------------------------------------")

    for article in all_articles:

        detail, image_url, page_date = read_article(
            article["link"]
        )

        # Prefer actual article page date.
        # RSS date is fallback.

        published = (
            page_date
            or article.get("published", "")
        )

        article["published"] = published

        # Strict today's news check
        if not is_today_news(article):
            continue

        if detail and len(detail) > len(
            article.get("description", "")
        ):

            article["description"] = detail

        # Real article photo first
        if image_url:
            article["image_url"] = image_url

        # Backup photo if no real photo
        if not valid_news_image(
            article.get("image_url", "")
        ):

            article["image_url"] = FALLBACK_IMAGE_URL

        article["fallback_image"] = (
            FALLBACK_IMAGE_URL
        )

        article["description"] = (
            article.get("description")
            or article["title"]
        )[:5000]

        today_articles.append(article)

        print(
            "TODAY VERIFIED:",
            article["source"],
            article["title"]
        )

        time.sleep(0.5)

    print("------------------------------------")
    print(
        "TODAY VERIFIED ARTICLES:",
        len(today_articles)
    )

    # ======================================
    # SELECT NEWS
    # ======================================

    selected = select_news(
        today_articles
    )

    if not selected:

        raise RuntimeError(
            "No verified news published today. "
            "Old news.json was not changed."
        )

    print(
        "FINAL SELECTED NEWS:",
        len(selected)
    )

    # Final date safety check
    for article in selected:

        if not is_today_news(article):

            raise RuntimeError(
                "Date verification failed. "
                "News file was not updated."
            )

    # ======================================
    # CREATE OUTPUT JSON
    # ======================================

    output = {

        "updated_at": make_timestamp(),

        "nepal_date": str(
            nepal_today()
        ),

        "total_news": len(selected),

        "chitwan_news": sum(
            1 for a in selected
            if a["category"] == "chitwan"
        ),

        "national_news": sum(
            1 for a in selected
            if a["category"] in (
                "national",
                "international",
                "sports"
            )
        ),

        "failed_sources": failed,

        "articles": selected
    }

    # ======================================
    # SAFE JSON SAVE
    # ======================================

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

    print("------------------------------------")
    print("NEWS COLLECTION SUCCESSFUL")
    print("------------------------------------")

    print(
        "NEPAL DATE:",
        output["nepal_date"]
    )

    print(
        "TOTAL:",
        output["total_news"]
    )

    print(
        "CHITWAN:",
        output["chitwan_news"]
    )

    print(
        "NATIONAL / INTERNATIONAL / SPORTS:",
        output["national_news"]
    )

    print(
        "FAILED SOURCES:",
        failed
    )

    print("------------------------------------")


if __name__ == "__main__":

    main()
