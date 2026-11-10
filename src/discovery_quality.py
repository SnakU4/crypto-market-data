"""Bounded public-source context enrichment and audit labels.

This module does not decide token relevance, price direction, or whether a
published claim is true. It stores short excerpts, not copyrighted full texts.
"""
from __future__ import annotations

import concurrent.futures as cf
import html
from html.parser import HTMLParser
import ipaddress
import re
import urllib.parse
import urllib.request
from collections import Counter

USER_AGENT = "CMC100-Evidence-Research/4.0 (+https://github.com/SnakU4/crypto-market-data)"
MAX_ARTICLE_BYTES = 350_000
MAX_ARTICLES = 80
MIN_ADDITIONAL = 100

class ArticleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.active = 0
        self.parts = []
        self.meta = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("script", "style", "nav", "footer", "header", "aside", "noscript"):
            self.skip += 1
        if tag == "article" and not self.skip:
            self.active += 1
        if tag == "meta":
            if attrs.get("property") in ("og:description", "twitter:description") or attrs.get("name", "").lower() == "description":
                self.meta.append(attrs.get("content", ""))
        if tag in ("p", "h2", "h3") and self.active and not self.skip:
            self.parts.append(" ")
    def handle_endtag(self, tag):
        if tag == "article" and self.active:
            self.active -= 1
        if tag in ("script", "style", "nav", "footer", "header", "aside", "noscript"):
            self.skip = max(0, self.skip - 1)
    def handle_data(self, data):
        if self.active and not self.skip:
            self.parts.append(data)

def normalized(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", str(text or "")))).strip()

def has_additional_information(title, excerpt):
    t = set(re.findall(r"[a-z0-9]+", normalized(title).casefold()))
    words = re.findall(r"[a-z0-9]+", normalized(excerpt).casefold())
    new = [w for w in words if len(w) > 3 and w not in t]
    return len(words) >= 24 and len(new) >= 9 and len(normalized(excerpt)) >= MIN_ADDITIONAL

def public_html_url(url):
    try:
        p = urllib.parse.urlsplit(url)
        host = (p.hostname or "").lower()
        if p.scheme != "https" or not host or host == "localhost" or host.endswith((".local", ".internal")):
            return False
        try:
            ip = ipaddress.ip_address(host)
            return ip.is_global
        except ValueError:
            return True
    except (ValueError, TypeError):
        return False

def extract_article(url, opener=urllib.request.urlopen):
    """Fetch only a bounded HTML response; refuse redirects to local/private URLs."""
    if not public_html_url(url) or "news.google.com" in urllib.parse.urlsplit(url).hostname:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
        with opener(req, timeout=7) as response:
            final_url = response.geturl()
            if not public_html_url(final_url):
                return None
            mime = response.headers.get("Content-Type", "").lower()
            if "text/html" not in mime:
                return None
            raw = response.read(MAX_ARTICLE_BYTES + 1)
            if len(raw) > MAX_ARTICLE_BYTES:
                return None
        parser = ArticleText()
        parser.feed(raw.decode("utf-8", errors="replace"))
        article = normalized(" ".join(parser.parts))
        meta = normalized(" ".join(parser.meta))
        candidate = article if len(article) >= 200 else meta
        return candidate[:1600] if len(candidate) >= MIN_ADDITIONAL else None
    except (OSError, ValueError, UnicodeError, TimeoutError):
        return None

def enrich(events, max_articles=MAX_ARTICLES, fetcher=extract_article):
    """Prioritise direct primary/community evidence; keep all unsuccessful leads."""
    for e in events:
        existing = normalized(e.get("excerpt", ""))
        e["content_quality"] = ("SUBSTANTIVE_EXCERPT" if has_additional_information(e.get("title"), existing)
                                else "TITLE_EQUIVALENT_OR_SHORT")
        e["excerpt_adds_information"] = e["content_quality"] == "SUBSTANTIVE_EXCERPT"
        e["article_fetch_status"] = "NOT_ATTEMPTED"
    candidates = [e for e in events if not e["excerpt_adds_information"] and
                  public_html_url(e.get("url", "")) and
                  "news.google.com" not in urllib.parse.urlsplit(e["url"]).hostname]
    candidates.sort(key=lambda e: (
        not any(f in e.get("source_families", []) for f in
                ("PROJECT_PRIMARY", "PUBLIC_COMMUNITY", "TECH_SECURITY_RESEARCH")),
        e.get("published_utc") or e.get("first_observed_utc") or "",
        e["event_id"]))
    # No uncontrolled 10k-page crawl; only up to MAX_ARTICLES short extracts.
    selected = candidates[:max_articles]
    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda e: fetcher(e["url"]), selected))
    for e, extracted in zip(selected, results):
        e["article_fetch_status"] = "SUCCESS" if extracted else "NO_ACCESSIBLE_TEXT"
        if extracted and has_additional_information(e.get("title"), extracted):
            e["excerpt"] = normalized(extracted)[:1600]
            e["context_origin"] = "PUBLIC_ARTICLE_EXTRACT"
            e["content_quality"] = "SUBSTANTIVE_ARTICLE_EXTRACT"
            e["excerpt_adds_information"] = True
    # Retain all leads and duplicated URLs' provenance. Label near-exact title
    # syndication; do not collapse different URLs or erase cross-sector evidence.
    counts = Counter(e["story_title_hash"] for e in events)
    for e in events:
        e["same_title_url_count"] = counts[e["story_title_hash"]]
        e["information_status"] = ("REPEATED_HEADLINE" if counts[e["story_title_hash"]] > 1
                                   else "SUBSTANTIVE" if e["excerpt_adds_information"] else "LOW_INFORMATION")
    return {
        "article_fetch_attempted": len(selected),
        "article_fetch_succeeded": sum(e["article_fetch_status"] == "SUCCESS" for e in selected),
        "article_fetch_substantive": sum(e["context_origin"] == "PUBLIC_ARTICLE_EXTRACT" for e in selected),
        "substantive_excerpts": sum(e["excerpt_adds_information"] for e in events),
        "title_equivalent_or_short": sum(not e["excerpt_adds_information"] for e in events),
        "repeated_headline_urls": sum(e["same_title_url_count"] > 1 for e in events),
        "unique_title_clusters": len(counts),
    }
