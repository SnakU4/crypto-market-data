"""Bounded public-source context enrichment and audit labels.

This module does not decide token relevance, price direction, or whether a
published claim is true. It stores short excerpts, not copyrighted full texts.
"""
from __future__ import annotations

import concurrent.futures as cf
import html
from html.parser import HTMLParser
import ipaddress
import socket
import threading
import time
import urllib.error
import urllib.robotparser
from collections import defaultdict
import re
import urllib.parse
import urllib.request
from collections import Counter

USER_AGENT = "CMC100-Evidence-Research/4.0 (+https://github.com/SnakU4/crypto-market-data)"
MAX_ARTICLE_BYTES = 350_000
MAX_ARTICLES = 320
MAX_RESOLUTIONS = 120
MAX_PER_HOST = 12
MIN_ADDITIONAL = 100

class ArticleText(HTMLParser):
    """Extract legitimate short context from <article>, <main> or metadata."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip=0;self.active=0;self.main_active=0
        self.parts=[];self.main_parts=[];self.meta=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag in ("script","style","nav","footer","header","aside","noscript"):
            self.skip+=1
        if tag=="article" and not self.skip:self.active+=1
        if tag=="main" and not self.skip:self.main_active+=1
        if tag=="meta":
            if attrs.get("property") in ("og:description","twitter:description") or attrs.get("name","").lower()=="description":
                self.meta.append(attrs.get("content",""))
        if tag in ("p","h2","h3","li") and not self.skip:
            if self.active:self.parts.append(" ")
            elif self.main_active:self.main_parts.append(" ")
    def handle_endtag(self,tag):
        if tag=="article" and self.active:self.active-=1
        if tag=="main" and self.main_active:self.main_active-=1
        if tag in ("script","style","nav","footer","header","aside","noscript"):
            self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if self.skip:return
        if self.active:self.parts.append(data)
        elif self.main_active:self.main_parts.append(data)

def normalized(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", str(text or "")))).strip()

def has_additional_information(title, excerpt):
    t = set(re.findall(r"[a-z0-9]+", normalized(title).casefold()))
    words = re.findall(r"[a-z0-9]+", normalized(excerpt).casefold())
    new = [w for w in words if len(w) > 3 and w not in t]
    return len(words) >= 24 and len(new) >= 9 and len(normalized(excerpt)) >= MIN_ADDITIONAL

def public_html_url(url):
    """Reject credentials, non-HTTPS, non-public IP literals and internal names."""
    try:
        p = urllib.parse.urlsplit(url)
        host = (p.hostname or "").rstrip(".").lower()
        if (p.scheme != "https" or not host or p.username or p.password
                or host in ("localhost", "metadata.google.internal")
                or host.endswith((".local", ".internal", ".localhost"))
                or not (p.port is None or p.port == 443)):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return bool(re.fullmatch(r"[a-z0-9.-]+", host)) and "." in host
    except (ValueError, TypeError):
        return False


def public_dns(url):
    """Fail closed when any resolved address is not globally routable."""
    if not public_html_url(url):
        return False
    host = urllib.parse.urlsplit(url).hostname
    try:
        addrs = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        return bool(addrs) and all(ipaddress.ip_address(a[4][0]).is_global for a in addrs)
    except (OSError, ValueError):
        return False


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not public_dns(newurl):
            raise urllib.error.HTTPError(newurl, 403, "Unsafe redirect", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def direct_news_target(url):
    """Only take explicit HTTPS publisher URLs, never guess Google article IDs."""
    if not public_html_url(url):
        return None
    parts = urllib.parse.urlsplit(url)
    if parts.hostname not in ("news.google.com", "news.google.co.uk"):
        return url
    query = urllib.parse.parse_qs(parts.query)
    for key in ("url", "u"):
        candidate = query.get(key, [None])[0]
        if candidate and public_html_url(candidate) and urllib.parse.urlsplit(candidate).hostname != parts.hostname:
            return candidate
    return None


class LinkHints(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.candidates = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "link" and "canonical" in a.get("rel", "").lower().split():
            self.candidates.append(a.get("href"))
        if tag == "meta" and a.get("property", "").lower() == "og:url":
            self.candidates.append(a.get("content"))


def resolve_google_news(url, opener=None):
    """Conservative resolution: HTTP redirects and explicit publisher canonical only.

    Does not call unofficial Google News decode services, use browser bypasses,
    or treat an arbitrary outbound link as the reported article.
    """
    direct = direct_news_target(url)
    if direct:
        return direct if public_dns(direct) else None
    if not public_dns(url):
        return None
    open_fn = opener or urllib.request.build_opener(SafeRedirect()).open
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
        with open_fn(req, timeout=6) as resp:
            final = resp.geturl()
            if public_dns(final) and urllib.parse.urlsplit(final).hostname not in ("news.google.com", "news.google.co.uk"):
                return final
            if "text/html" not in resp.headers.get("Content-Type", "").lower():
                return None
            raw = resp.read(100_001)
            if len(raw) > 100_000:
                return None
        parser = LinkHints()
        parser.feed(raw.decode("utf-8", errors="replace"))
        for hint in parser.candidates:
            candidate = urllib.parse.urljoin(url, hint or "")
            if public_dns(candidate) and urllib.parse.urlsplit(candidate).hostname not in ("news.google.com", "news.google.co.uk"):
                return candidate
    except (OSError, ValueError, UnicodeError, TimeoutError):
        return None
    return None


_robots_cache = {}
_robots_lock = threading.Lock()

def robots_permit(url, cache=None):
    """Bounded public robots.txt check; inaccessible policy fails closed."""
    if not public_dns(url):
        return False
    origin = urllib.parse.urlsplit(url)
    key = origin.scheme + "://" + origin.netloc
    with _robots_lock:
        rules = (cache if cache is not None else _robots_cache)
        if key in rules:
            rp = rules[key]
            return bool(rp and rp.can_fetch(USER_AGENT, url))
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(key + "/robots.txt")
    try:
        req = urllib.request.Request(key + "/robots.txt", headers={"User-Agent": USER_AGENT})
        with urllib.request.build_opener(SafeRedirect()).open(req, timeout=4) as response:
            raw = response.read(80_001)
            if len(raw) > 80_000:
                return False
        rp.parse(raw.decode("utf-8", errors="replace").splitlines())
        allowed = rp.can_fetch(USER_AGENT, url)
    except urllib.error.HTTPError as exc:
        # 404 means no exclusion policy; 401/403 and transient errors fail closed.
        allowed = (exc.code == 404)
        if allowed:
            rp.parse([])
    except (OSError, ValueError, TimeoutError):
        allowed = False
    with _robots_lock:
        rules = (cache if cache is not None else _robots_cache)
        if len(rules) < 500:
            rules[key] = rp if allowed else None
    return allowed

def extract_article(url, opener=None, robots_check=robots_permit):
    """Bounded HTML extraction; never intentionally bypass robots or paywalls."""
    if not public_dns(url) or urllib.parse.urlsplit(url).hostname in ("news.google.com", "news.google.co.uk"):
        return None
    if not robots_check(url):
        return None
    try:
        open_fn = opener or urllib.request.build_opener(SafeRedirect()).open
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
        with open_fn(req, timeout=7) as response:
            final_url = response.geturl()
            if not public_dns(final_url):
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
        main = normalized(" ".join(parser.main_parts))
        meta = normalized(" ".join(parser.meta))
        candidate = article if len(article) >= 200 else (main if len(main) >= 200 else meta)
        return candidate[:1600] if len(candidate) >= MIN_ADDITIONAL else None
    except (OSError, ValueError, UnicodeError, TimeoutError):
        return None

def enrich(events, max_articles=MAX_ARTICLES, fetcher=extract_article,
           max_resolutions=MAX_RESOLUTIONS, resolver=resolve_google_news):
    """Preserve raw leads, select diverse fresh leads for bounded enrichment."""
    for e in events:
        existing = normalized(e.get("excerpt", ""))
        substantive = has_additional_information(e.get("title"), existing)
        e["content_quality"] = "SUBSTANTIVE_EXCERPT" if substantive else "TITLE_EQUIVALENT_OR_SHORT"
        e["excerpt_adds_information"] = substantive
        e["article_fetch_status"] = "NOT_ATTEMPTED"
        e["resolution_status"] = "NOT_ATTEMPTED"
        e["resolved_article_url"] = None
    # Prefer newly observed, direct publisher and primary/community leads, but
    # reserve explicit budget for opaque Google News articles.
    ranked = sorted((e for e in events if not e["excerpt_adds_information"]
                     and public_html_url(e.get("url",""))),
                    key=lambda e: (
                        e.get("previously_seen", False),
                        not any(f in e.get("source_families",[]) for f in
                                ("PROJECT_PRIMARY","PUBLIC_COMMUNITY","TECH_SECURITY_RESEARCH")),
                        -(len(e.get("search_origins",[]))),
                        e.get("event_id","")))
    google = [e for e in ranked if urllib.parse.urlsplit(e["url"]).hostname in
              ("news.google.com","news.google.co.uk")]
    google_ids = {id(e) for e in google}
    direct = [e for e in ranked if id(e) not in google_ids]
    resolving = google[:max(0,max_resolutions)]
    def resolve_one(e):
        try: return resolver(e["url"])
        except (OSError, ValueError, TimeoutError): return None
    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        resolved = list(pool.map(resolve_one, resolving))
    for e, link in zip(resolving, resolved):
        e["resolution_status"] = "RESOLVED" if link and public_html_url(link) else "UNRESOLVED"
        if e["resolution_status"] == "RESOLVED":
            e["resolved_article_url"] = link
    resolved_google = [e for e in resolving if e["resolution_status"] == "RESOLVED"]
    # Cap requests per publisher domain and deduplicate direct article targets.
    selected=[]
    host_counts=Counter()
    seen_targets=set()
    preferred = direct[:max_articles] + resolved_google
    preferred.sort(key=lambda e: (
        e.get("previously_seen",False),
        not any(f in e.get("source_families",[]) for f in ("PROJECT_PRIMARY","PUBLIC_COMMUNITY")),
        e.get("event_id","")))
    for e in preferred:
        target=e["resolved_article_url"] or e["url"]
        host=urllib.parse.urlsplit(target).hostname
        if not public_html_url(target) or target in seen_targets or host_counts[host]>=MAX_PER_HOST:
            continue
        if len(selected)>=max_articles:
            break
        seen_targets.add(target)
        host_counts[host]+=1
        selected.append((e,target))
    def fetch_one(pair):
        try: return fetcher(pair[1])
        except (OSError, ValueError, TimeoutError): return None
    with cf.ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(fetch_one, selected))
    for (e,target),extracted in zip(selected,results):
        e["article_fetch_status"]="SUCCESS" if extracted else "NO_ACCESSIBLE_TEXT"
        if extracted and has_additional_information(e.get("title"),extracted):
            e["excerpt"]=normalized(extracted)[:1600]
            e["context_origin"]="PUBLIC_ARTICLE_EXTRACT"
            e["content_quality"]="SUBSTANTIVE_ARTICLE_EXTRACT"
            e["excerpt_adds_information"]=True
    counts=Counter(e["story_title_hash"] for e in events)
    for e in events:
        e["same_title_url_count"]=counts[e["story_title_hash"]]
        e["information_status"]=("REPEATED_HEADLINE" if counts[e["story_title_hash"]]>1
                                  else "SUBSTANTIVE" if e["excerpt_adds_information"] else "LOW_INFORMATION")
    return {
        "article_fetch_attempted":len(selected),
        "article_fetch_succeeded":sum(e["article_fetch_status"]=="SUCCESS" for e,_ in selected),
        "article_fetch_substantive":sum(e.get("context_origin")=="PUBLIC_ARTICLE_EXTRACT" for e,_ in selected),
        "google_news_resolution_attempted":len(resolving),
        "google_news_resolution_succeeded":len(resolved_google),
        "resolved_google_articles_fetched":sum(e["resolution_status"]=="RESOLVED" and e["article_fetch_status"]!="NOT_ATTEMPTED" for e in resolving),
        "substantive_excerpts":sum(e["excerpt_adds_information"] for e in events),
        "title_equivalent_or_short":sum(not e["excerpt_adds_information"] for e in events),
        "repeated_headline_urls":sum(e["same_title_url_count"]>1 for e in events),
        "unique_title_clusters":len(counts),
    }
