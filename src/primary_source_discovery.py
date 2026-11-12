#!/usr/bin/env python3
"""Discover and sample publicly advertised RSS/Atom feeds from new publishers.

Source candidates are learned from prior GitHub research, not a closed taxonomy.
All network activity is bounded, HTTPS/DNS/robots checked, no bypass/paywalls,
no paid APIs and no unsupported claim of verified token relevance.
"""
from __future__ import annotations
import collections, datetime as dt, hashlib, html.parser, json, pathlib, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
try:
    from discovery_quality import public_dns, robots_permit, SafeRedirect, has_additional_information
except ImportError:
    from src.discovery_quality import public_dns, robots_permit, SafeRedirect, has_additional_information

UTC=dt.timezone.utc
UA="CMC100-Free-Source-Discovery/1.0 https://github.com/SnakU4/crypto-market-data"
MAX_BYTES=500_000
SOURCE_EXCLUDE={"google.com","github.com","arxiv.org","news.google.com"}

class Feeds(html.parser.HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag!="link":return
        a=dict(attrs);rel=a.get("rel","").lower();typ=a.get("type","").lower()
        if "alternate" in rel and ("rss" in typ or "atom" in typ) and a.get("href"):
            self.links.append(a["href"])

def inspect_feed_links(html,url):
    p=Feeds();p.feed(html)
    return list(dict.fromkeys(x for x in
        (urllib.parse.urljoin(url,part) for part in p.links)
        if urllib.parse.urlsplit(x).scheme=="https"))[:3]

def is_valid_source_url(url):
    if not public_dns(url):return False
    u=urllib.parse.urlsplit(url)
    host=(u.hostname or "").lower()
    return host not in SOURCE_EXCLUDE and not host.endswith(".google.com")

def retrieve(url, opener=None):
    if not is_valid_source_url(url):return None,"UNSAFE_OR_NOT_PUBLIC"
    if not robots_permit(url):return None,"ROBOTS_DISALLOW"
    req=urllib.request.Request(url,headers={"User-Agent":UA,
        "Accept":"application/rss+xml,application/atom+xml,application/xml,text/html;q=0.8"})
    try:
        op=opener or urllib.request.build_opener(SafeRedirect()).open
        with op(req,timeout=7) as resp:
            final_url=resp.geturl()
            if not is_valid_source_url(final_url):return None,"REDIRECT_BLOCKED"
            data=resp.read(MAX_BYTES+1)
            if len(data)>MAX_BYTES:
                # Modern homepages can be multi-megabyte HTML. Feed <link>
                # declarations are normally in the head. Parse only a bounded
                # first chunk, and label it as PARTIAL; never treat as article.
                typ=getattr(resp,"headers",{}).get("Content-Type","").lower()
                if url.endswith("/") and ("html" in typ or not typ):
                    return data[:MAX_BYTES],"TRUNCATED_PUBLIC_HOMEPAGE"
                return None,"OVERSIZED"
            return data,"OK"
    except (OSError,ValueError,TimeoutError) as err:
        return None,type(err).__name__

def parsed_feed(payload,source,observed_utc,limit=20):
    try:
        from research_collector import parse_feed
    except ImportError:
        from src.research_collector import parse_feed
    rows=parse_feed(payload,source,observed_utc,limit=limit)
    # Do not count an RSS search title as a substantiated article.
    return [{"id":"D:"+hashlib.sha256((x["url"]+str(source)).encode()).hexdigest()[:18],
       "source_plane":"new_primary_source","source_id":source,
       "title":x["headline"],"url":x["url"],"excerpt":x.get("excerpt") or "",
       "published_utc":x.get("published_utc"),
       "first_observed_utc":observed_utc,
       "candidate_cmc_ids":[],"themes":[],
       "scope":"GLOBAL_UNRESOLVED",
       "claim_status":"PUBLISHER_SOURCE_UNVERIFIED_COIN_RELEVANCE",
       "identity_status":"NO_COIN_LINK_ASSERTED",
       "source_family":"DISCOVERED_ORIGINAL_PUBLISHER",
       "priority":35,"context_origin":x.get("context_origin"),
       "provenance_ids":["D:"+hashlib.sha256(x["url"].encode()).hexdigest()[:18]]}
       for x in rows]

def discover(proposals,cutoff,max_sites=10,opener=None,known_feed_urls=(),skip_domains=()):
    audit=[];items=[]
    known=set(str(x).rstrip("/") for x in known_feed_urls)
    skip=set(str(x).lower() for x in skip_domains)
    candidates=(proposals.get("candidate_publishers") or [])[:90]
    for record in candidates:
        if len(audit)>=max_sites:break
        host=str(record.get("domain") or "").lower()
        if not host or host in SOURCE_EXCLUDE or host.endswith(".google.com") or host in skip:continue
        # Same source selection for the result and the resulting source audit;
        # do not auto-install domain/feed into a trusted collector.
        homepage="https://"+host+"/"
        payload,status=retrieve(homepage,opener)
        out={"domain":host,"home_status":status,"feed_status":"NOT_DISCOVERED",
             "article_count":0,"substantive":0}
        if payload:
            urls=inspect_feed_links(payload.decode("utf-8","replace"),homepage)
            out["advertised_feeds"]=urls
            for u in urls[:3]:
                if u.rstrip("/") in known:
                    out["feed_status"]="ALREADY_COLLECTED"
                    out["duplicate_feed_url"]=u
                    continue
                raw,fs=retrieve(u,opener)
                out["feed_status"]=fs
                if raw:
                    rows=parsed_feed(raw,"DYNAMIC_"+host,
                                     dt.datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00","Z"),limit=20)
                    out["article_count"]+=len(rows)
                    out["substantive"]+=sum(has_additional_information(
                        x["title"],x["excerpt"]) for x in rows)
                    items+=rows
                    if rows:break
        audit.append(out)
    return items,{"domains_attempted":len(audit),
                  "advertised_existing_feed_count":sum(x.get("feed_status")=="ALREADY_COLLECTED" for x in audit),
                  "domains_found_content":
                  sum(x["article_count"]>0 for x in audit),"new_feed_items":len(items),
                  "substantive_feed_items":sum(has_additional_information(
                      x["title"],x["excerpt"]) for x in items),
                  "sources":audit,"not_verified_facts":True}
