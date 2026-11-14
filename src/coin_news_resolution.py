#!/usr/bin/env python3
"""Bounded, robots-aware resolution of Google News candidate links for uncovered coins.

Directly attributes the ORIGINAL publisher URL where a legitimate HTTP redirect or
canonical link can be established. Never decodes opaque Google IDs via unofficial
services, bypasses access controls, or equates a headline with an article.
"""
from __future__ import annotations
import collections
import concurrent.futures
import datetime as dt
import json
import pathlib
import re
import urllib.parse

UTC=dt.timezone.utc
HISTORY="docs/intelligence/google_news_resolution_history.json"

def timestamp(t):
    return t.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00","Z")

def parse(value):
    try:
        d=dt.datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return d.astimezone(UTC) if d.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None

def title_relevant(title,asset):
    """Reject accidental symbolic collisions and most irrelevant aggregator leads."""
    name=str(asset.get("name") or "")
    symbol=str(asset.get("symbol") or "")
    text=str(title or "")
    if len(name)>=5 and re.search(r"(?<!\w)"+re.escape(name)+r"(?!\w)",text,flags=re.I):
        return True
    # Short/ambiguous tickers like PI, LEO, M, CC are not reliable by themselves.
    if len(symbol)>=3 and symbol.upper()==symbol:
        return bool(re.search(r"(?<![A-Za-z0-9])"+re.escape(symbol)+r"(?![A-Za-z0-9])",text))
    return False

def substantive_article(title,text,asset):
    try:from discovery_quality import has_additional_information
    except ImportError:from src.discovery_quality import has_additional_information
    body=re.sub(r"\s+"," ",str(text or "")).strip()
    # Name or ticker must appear in substantive source text, not only title.
    return (len(body)>=180 and has_additional_information(title,body)
        and title_relevant(body,asset) and not
        all(word in body.casefold() for word in ("sorry","something went wrong","loading")))

def collect(root,assets,events,existing=(),cutoff=None,network=False,
            resolver=None,fetcher=None,max_resolutions=32):
    root=pathlib.Path(root);cutoff=cutoff or dt.datetime.now(UTC)
    hist_path=root/HISTORY
    try: history=json.loads(hist_path.read_text(encoding="utf8")).get("attempts",{})
    except (OSError,ValueError,TypeError):history={}
    if not isinstance(history,dict):history={}
    existing_ids={item.get("evidence_id") for item in existing if isinstance(item,dict)}
    try:from discovery_quality import has_additional_information
    except ImportError:from src.discovery_quality import has_additional_information
    rich={cid for e in events for cid in (e.get("candidate_cmc_ids") or [])
          if has_additional_information(e.get("title"),e.get("excerpt")) or
             e.get("id") in existing_ids}
    assets_by_id={int(a["cmc_id"]):a for a in assets}
    candidates=collections.defaultdict(list)
    for e in events:
        url=str(e.get("url") or "")
        if urllib.parse.urlsplit(url).hostname not in ("news.google.com","news.google.co.uk"):
            continue
        for cid in e.get("candidate_cmc_ids") or []:
            if cid in rich or cid not in assets_by_id:continue
            if title_relevant(e.get("title"),assets_by_id[cid]):
                candidates[cid].append(e)
    # Distinct uncovered assets first. Prioritize newer, more-specific headlines.
    for cid in candidates:
        candidates[cid].sort(key=lambda e:(e.get("published_utc") or "",e.get("priority") or 0),reverse=True)
    chosen=[];selected_urls=set();chosen_ids=set()
    for depth in (0,1,2):
        for cid in sorted(candidates):
            if len(chosen)>=max_resolutions:break
            for e in candidates[cid][depth:]:
                url=e["url"]
                if url in selected_urls:continue
                prior=parse((history.get(url) or {}).get("attempted_utc")) if isinstance(history.get(url),dict) else None
                if prior and dt.timedelta(0)<=cutoff-prior<=dt.timedelta(days=7):
                    continue
                chosen.append((cid,e));selected_urls.add(url);chosen_ids.add(cid);break
        if len(chosen)>=max_resolutions:break
    if resolver is None:
        try:from discovery_quality import resolve_google_news as resolver
        except ImportError:from src.discovery_quality import resolve_google_news as resolver
    if fetcher is None:
        try:from discovery_quality import extract_article as fetcher
        except ImportError:from src.discovery_quality import extract_article as fetcher
    def one(task):
        cid,e=task
        try:
            resolved=resolver(e["url"])
            if not resolved or urllib.parse.urlsplit(resolved).hostname in ("news.google.com","news.google.co.uk"):
                return cid,e,None,"NO_CONFIRMED_DIRECT_PUBLISHER"
            body=fetcher(resolved)
            if not substantive_article(e.get("title"),body,assets_by_id[cid]):
                return cid,e,None,"PUBLISHER_TEXT_MISSING_OR_ASSET_NOT_CONFIRMED"
            return cid,e,{"evidence_id":e["id"],"url":resolved,
                "lead_url":e["url"],"scope":"ASSET_CANDIDATE",
                "source_excerpt":re.sub(r"\s+"," ",body).strip()[:650],
                "content_origin":"GOOGLE_NEWS_RESOLVED_DIRECT_PUBLISHER_TEXT",
                "verification":"ORIGINAL_PUBLISHER_TEXT_NOT_FACT_VERIFIED",
                "fetched_utc":timestamp(dt.datetime.now(UTC))}, "SUBSTANTIVE"
        except (ValueError,TypeError,OSError,TimeoutError):
            return cid,e,None,"ACCESS_DENIED_OR_RESOLUTION_ERROR"
    successes=[];statuses=collections.Counter()
    if network:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            for cid,e,result,status in pool.map(one,chosen):
                statuses[status]+=1
                history[e["url"]]={"attempted_utc":timestamp(dt.datetime.now(UTC)),
                    "status":status,"candidate_cmc_id":cid}
                if result:successes.append(result)
    audit={"attempted":len(chosen) if network else 0,
       "selected_uncovered_coins":len(chosen_ids) if network else 0,
       "resolved_substantive_articles":len(successes),
       "newly_covered_coins":len({cid for cid,e in chosen if any(
           item["evidence_id"]==e["id"] for item in successes)}),
       "statuses":dict(statuses),"no_unofficial_decode":True,
       "no_primary_claims_verified":True,"historical_network_disabled":not network}
    # Keep a week-long retry window and 35 days of audit history.
    history={k:v for k,v in history.items() if isinstance(v,dict) and
             parse(v.get("attempted_utc")) and
             dt.timedelta(0)<=dt.datetime.now(UTC)-parse(v["attempted_utc"])<=dt.timedelta(days=35)}
    return successes,{"attempts":history,"policy":"DIRECT_PUBLISHER_ONLY_AFTER_SAFE_RESOLUTION"},audit
