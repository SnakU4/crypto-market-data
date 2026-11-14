#!/usr/bin/env python3
"""Free publisher-article discovery through exact-linked project website sitemaps.

Sitemap lastmod is never substituted for an article publication time.
Only news/blog articles with actually retrieved meaningful publisher text are
counted as undated source context. No paywall, robot, private IP or API bypass.
"""
from __future__ import annotations

import collections
import concurrent.futures
import datetime as dt
import hashlib
import json
import pathlib
import re
import urllib.parse
import xml.etree.ElementTree as ET

UTC=dt.timezone.utc
HISTORY="docs/intelligence/coin_project_sitemap_history.json"
ARTICLE_PATH=re.compile(r"/(blog|news|insights|announcements|updates|articles|posts|press|research)/",re.I)
BAD_PATH=re.compile(r"/(category|tag|author|page|search|feed|archive)/",re.I)
EXCLUDED_WEBSITES={(28298,"beam.mw")}
MAX_SITEMAP_BYTES=600_000

def stamp(t):
    return t.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00","Z")

def parsed(t):
    try:
        x=dt.datetime.fromisoformat(str(t).replace("Z","+00:00"))
        return x.astimezone(UTC) if x.tzinfo else None
    except (TypeError,ValueError,OverflowError):return None

def hostof(url):
    p=urllib.parse.urlsplit(str(url or ""))
    return (p.hostname or "").lower().removeprefix("www.") if p.scheme=="https" else ""

def same_host(a,b):
    return bool(hostof(a) and hostof(a)==hostof(b))

def parse_sitemap(payload,url,cutoff,mode="auto"):
    if not payload or len(payload)>MAX_SITEMAP_BYTES:return [],[],"OVERSIZED_OR_EMPTY"
    try:r=ET.fromstring(payload)
    except (ET.ParseError,ValueError,TypeError):return [],[],"INVALID_XML"
    typ=r.tag.split("}")[-1].casefold()
    pages=[];nested=[]
    if typ=="sitemapindex":
        for entry in r:
            loc=next((n.text for n in entry if n.tag.split("}")[-1]=="loc"),None)
            if (loc and same_host(url,loc) and
                re.search(r"blog|post|news|article|press|update|sitemap",loc,re.I)):
                nested.append(loc)
        nested.sort(key=lambda x:0 if re.search(r"post|blog|news",x,re.I) else 1)
    elif typ=="urlset":
        for entry in r:
            loc=next((n.text for n in entry if n.tag.split("}")[-1]=="loc"),None)
            lastmod=next((n.text for n in entry if n.tag.split("}")[-1]=="lastmod"),None)
            if not loc or not same_host(url,loc):continue
            path=urllib.parse.urlsplit(loc).path
            if not ARTICLE_PATH.search(path) or BAD_PATH.search(path):continue
            when=parsed(lastmod)
            # Prefer explicit lastmod in the last 90 days, while retaining
            # UNKNOWN publication status if a page is later extracted.
            if not when or not dt.timedelta(0)<=cutoff-when<=dt.timedelta(days=90):
                continue
            pages.append({"url":loc,"sitemap_lastmod_utc":stamp(when)})
        pages.sort(key=lambda x:x["sitemap_lastmod_utc"],reverse=True)
    else:return [],[],"UNEXPECTED_XML_ROOT"
    return pages[:18],nested[:4],typ.upper()

def collect(root,assets,profiles,events,cutoff,network=False,
            max_domains=12,download=None,extractor=None):
    root=pathlib.Path(root)
    hist=root/HISTORY
    try:past=json.loads(hist.read_text(encoding="utf-8")).get("domains",{})
    except (OSError,ValueError,TypeError):past={}
    if not isinstance(past,dict):past={}
    try:from discovery_quality import extract_article,has_additional_information
    except ImportError:from src.discovery_quality import extract_article,has_additional_information
    try:from coin_news_resolution import title_relevant
    except ImportError:from src.coin_news_resolution import title_relevant
    try:from primary_source_discovery import retrieve
    except ImportError:from src.primary_source_discovery import retrieve
    download=download or retrieve
    extractor=extractor or extract_article
    rich={cid for e in events for cid in (e.get("candidate_cmc_ids") or [])
          if has_additional_information(e.get("title"),e.get("excerpt"))}
    selected=[];skips=collections.Counter();seen=set();quarantined=[]
    for asset in assets:
        cid=int(asset["cmc_id"])
        if cid in rich:continue
        profile=profiles.get(str(cid)) or {}
        links=(profile.get("primary_links_unverified") or {})
        urls=links.get("website") or links.get("homepage") or []
        if not isinstance(urls,list):continue
        for home in urls[:2]:
            host=hostof(home)
            if not host or host in seen:continue
            if (cid,host) in EXCLUDED_WEBSITES:
                quarantined.append({"cmc_id":cid,"host":host,"reason":"UNRELATED_BEAM_CHAIN"})
                continue
            item=past.get(host) or {}
            previous=parsed(item.get("observed_utc"))
            if previous and dt.timedelta(0)<=dt.datetime.now(UTC)-previous<=dt.timedelta(hours=72):
                skips["cooldown"]+=1;continue
            seen.add(host);selected.append((asset,"https://"+urllib.parse.urlsplit(home).netloc+"/sitemap.xml",host))
            break
        if len(selected)>=max_domains:break
    def run(item):
        asset,url,host=item
        stats={"symbol":asset["symbol"],"host":host,"sitemaps":0,
               "pages_attempted":0,"substantive":0,"status":[]}
        found=[];pages=[]
        try:
            raw,status=download(url);stats["status"].append("root:"+str(status))
            if raw:
                pages,nested,state=parse_sitemap(raw,url,cutoff)
                stats["status"].append("parse:"+state)
                for feedurl in nested[:2]:
                    blob,substatus=download(feedurl)
                    stats["status"].append("nested:"+str(substatus))
                    if blob:
                        more,_,_=parse_sitemap(blob,feedurl,cutoff)
                        pages.extend(more)
                stats["sitemaps"]=1+len(nested[:2])
            uniq={}
            for page in pages:uniq.setdefault(page["url"],page)
            pages=sorted(uniq.values(),
                key=lambda x:x["sitemap_lastmod_utc"],reverse=True)[:4]
            for page in pages:
                stats["pages_attempted"]+=1
                body=extractor(page["url"])
                body=re.sub(r"\s+"," ",str(body or "")).strip()[:900]
                if not body or len(body)<160:continue
                # The source website is project-linked, but the article text
                # must independently identify that project/coin.
                if not title_relevant(body,asset):continue
                slug=urllib.parse.unquote(urllib.parse.urlsplit(page["url"]).path).split("/")[-1]
                title=re.sub(r"[-_]"," ",slug)[:180]
                if not has_additional_information(title,body):continue
                key="SM:"+hashlib.sha256((str(asset["cmc_id"])+page["url"]).encode()).hexdigest()[:20]
                found.append({"id":key,"source_plane":"direct_project_sitemap",
                    "source_id":"COIN_SITE_SITEMAP_"+str(asset["cmc_id"]),
                    "title":title,"url":page["url"],"excerpt":body[:650],
                    "sitemap_lastmod_utc":page["sitemap_lastmod_utc"],
                    "published_utc":None,
                    "first_observed_utc":stamp(dt.datetime.now(UTC)),
                    "context_origin":"PROJECT_WEBSITE_SITEMAP_EXTRACTED_ARTICLE",
                    "scope":"ASSET_CANDIDATE",
                    "candidate_cmc_ids":[int(asset["cmc_id"])],
                    "themes":[],"priority":44,
                    "claim_status":"PUBLIC_PROJECT_ARTICLE_NO_VERIFIED_PRICE_IMPACT",
                    "identity_status":"THIRD_PARTY_PROFILE_PROJECT_WEBSITE_ASSOCIATION",
                    "source_family":"PROJECT_SITE_ARTICLE_UNDATED",
                    "source_date_caveat":"SITEMAP_LASTMOD_IS_NOT_ARTICLE_PUBLICATION_TIME",
                    "provenance_ids":[key]})
                stats["substantive"]+=1
                if len(found)>=2:break
        except (OSError,TypeError,ValueError,TimeoutError) as exc:
            stats["status"].append(type(exc).__name__)
        return host,found,stats
    out=[];audit=[]
    if network:
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            for domain,items,status in pool.map(run,selected):
                audit.append(status);out.extend(items)
                past[domain]={"observed_utc":stamp(dt.datetime.now(UTC)),
                    "substantive":len(items),"status":status["status"]}
    now=dt.datetime.now(UTC)
    past={k:v for k,v in past.items() if isinstance(v,dict) and
          parsed(v.get("observed_utc")) and
          dt.timedelta(0)<=now-parsed(v["observed_utc"])<=dt.timedelta(days=30)}
    summary={"project_sitemaps_probed":len(audit),
             "new_substantive_undated_site_articles":len(out),
             "coins_with_new_substantive_site_articles":len({i["candidate_cmc_ids"][0] for i in out}),
             "sites":audit,"quarantine":quarantined,"skips":dict(skips),
             "sitemap_lastmod_is_not_article_publication_time":True,
             "never_claims_confirmed_token_catalyst":True}
    return out,{"domains":past,"cooldown_hours":72},summary
