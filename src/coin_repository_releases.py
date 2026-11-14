#!/usr/bin/env python3
"""Free, PIT-aware primary software-release evidence from coin-linked GitHub repositories.

Every repository URL originates in an exact CMC-ID/name/symbol provider profile.
A release is project SOFTWARE activity, not token economics, governance passage,
confirmed adoption, or evidence of a profitable trade. Ambiguous repositories
are excluded; empty release feeds never become fabricated news.
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
import urllib.request
import urllib.error

UTC=dt.timezone.utc
HISTORY="docs/intelligence/coin_repository_releases.json"
MAX_AGE_DAYS=120
# CMC #28298 BEAM is the gaming/Beam Network asset, while BeamMW/beam is
# the unrelated Mimblewimble Beam chain sharing its name and ticker.
REPOSITORY_QUARANTINE={
    (28298,"beammw/beam"):"OTHER_PROJECT_BEAM_MIMBLEWIMBLE_NOT_CMC28298_GAMING"
}

def stamp(value):
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00","Z")

def parse(value):
    try:
        z=dt.datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return z.astimezone(UTC) if z.tzinfo else None
    except (ValueError,TypeError,OverflowError):
        return None

def valid_repo(url):
    p=urllib.parse.urlsplit(str(url or ""))
    if p.scheme!="https" or (p.hostname or "").lower() not in ("github.com","www.github.com"):
        return None
    if p.username or p.password or p.query or p.fragment or p.port:
        return None
    parts=p.path.strip("/").split("/")
    if len(parts)!=2 or any(not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}",x) for x in parts):
        return None
    if parts[0].lower() in ("orgs","topics","settings","features","users","marketplace"):
        return None
    return "/".join(parts)

def release_event(asset,repo,row,cutoff,observed,information):
    try:
        from discovery_quality import has_additional_information
    except ImportError:
        from src.discovery_quality import has_additional_information
    title=str(row.get("headline") or "")[:230]
    excerpt=re.sub(r"\s+"," ",str(row.get("excerpt") or "")).strip()[:900]
    pub=parse(row.get("published_utc"))
    if pub and (pub>cutoff or pub<cutoff-dt.timedelta(days=MAX_AGE_DAYS)):
        return None
    if not has_additional_information(title,excerpt):
        return None
    url=str(row.get("url") or "")
    urlpath=urllib.parse.urlsplit(url)
    expected="/"+repo.lower()+"/"
    # Accept only releases authored within the linked repository; an Atom
    # entry may not redirect us to a third-party domain.
    if (urlpath.scheme!="https" or (urlpath.hostname or "").lower() not in ("github.com","www.github.com")
        or not urlpath.path.lower().startswith(expected)):
        return None
    cid=int(asset["cmc_id"])
    stable_id="R:"+hashlib.sha256((str(cid)+":"+url.split("?")[0]).encode()).hexdigest()[:20]
    return {
        "id":stable_id,"source_plane":"linked_project_repository",
        "source_id":"COIN_REPO_"+str(cid),
        "title":title,"url":url,"excerpt":excerpt,
        "published_utc":row.get("published_utc"),
        "first_observed_utc":observed,
        "scope":"ASSET_CANDIDATE",
        "candidate_cmc_ids":[cid],"themes":[],
        "priority":51,
        "context_origin":"EXACT_CMC_ID_PROVIDER_LINKED_GITHUB_RELEASE",
        "identity_status":"PROVIDER_LINKED_PROJECT_REPO_NOT_TOKEN_CAUSALITY",
        "claim_status":"PROJECT_SOFTWARE_RELEASE_NOT_VERIFIED_PRICE_CATALYST",
        "source_family":"PUBLISHED_SOFTWARE_RELEASE",
        "provenance_ids":[stable_id],
        "observed_source_repo":"https://github.com/"+repo,
        "time_classification":"PUBLISHER_DATE" if pub else "PUBLICATION_DATE_UNKNOWN",
        "source_identity_caveat":"Third-party profile links repository; do not assume all repo work changes the tradeable token."
    }

def api_releases(repo,opener=None):
    """Official keyless REST API, capped and without third-party scraping.
    Return no false data on 403/429 rate limits or inaccessible repositories.
    """
    owner,name=repo.split("/",1)
    url=("https://api.github.com/repos/"+urllib.parse.quote(owner,safe="")
         +"/"+urllib.parse.quote(name,safe="")+"/releases?per_page=7")
    req=urllib.request.Request(url,headers={
        "Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28",
        "User-Agent":"CMC100-Public-Project-Release-Research/1.0"})
    try:
        open_fn=opener or urllib.request.urlopen
        with open_fn(req,timeout=8) as response:
            final=urllib.parse.urlsplit(response.geturl())
            if (final.scheme!="https" or final.hostname!="api.github.com"
                or final.path!=urllib.parse.urlsplit(url).path):
                return [],"INVALID_REDIRECT"
            raw=response.read(700_001)
            if len(raw)>700_000:return [],"OVERSIZED"
        obj=json.loads(raw)
        if not isinstance(obj,list):return [],"INVALID_RESPONSE"
        return [x for x in obj if isinstance(x,dict) and not x.get("draft")][:7],"OK"
    except urllib.error.HTTPError as ex:
        return [],"HTTP_"+str(ex.code)
    except (OSError,ValueError,TypeError,TimeoutError):
        return [],"ACCESS_OR_JSON_ERROR"

def collect(root,assets,profiles,events,cutoff,network=False,
            max_repos=15,download=None):
    root=pathlib.Path(root)
    path=root/HISTORY
    try: prior=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,ValueError,TypeError): prior={}
    old_items=prior.get("events") or []
    previous=prior.get("probes") or {}
    if not isinstance(previous,dict):previous={}
    allowed={int(a["cmc_id"]):a for a in assets}
    cached=[]
    for e in old_items:
        if not isinstance(e,dict):continue
        cid=(e.get("candidate_cmc_ids") or [None])[0]
        if cid not in allowed:continue
        p=parse(e.get("first_observed_utc"))
        d=parse(e.get("published_utc"))
        if (p and p<=cutoff and (not d or d<=cutoff)
            and (not d or d>=cutoff-dt.timedelta(days=MAX_AGE_DAYS))):
            cached.append(e)
    try:from discovery_quality import has_additional_information
    except ImportError:from src.discovery_quality import has_additional_information
    rich={cid for e in events for cid in (e.get("candidate_cmc_ids") or [])
          if has_additional_information(e.get("title"),e.get("excerpt"))}
    rich.update(cid for e in cached for cid in (e.get("candidate_cmc_ids") or []))
    skip=[];choices=[]
    ids_selected=set()
    for asset in assets:
        cid=int(asset["cmc_id"])
        if cid in rich:continue
        profile=profiles.get(str(cid)) or {}
        if not profile.get("has_substantive_descriptive_context"):
            continue
        sources=(profile.get("primary_links_unverified") or {}).get("source_code") or []
        if not isinstance(sources,list):continue
        for url in sources:
            repo=valid_repo(url)
            if not repo:continue
            reason=REPOSITORY_QUARANTINE.get((cid,repo.casefold()))
            if reason:
                skip.append({"cmc_id":cid,"symbol":asset["symbol"],"repo":repo,"reason":reason})
                continue
            key=str(cid)+":"+repo.lower()
            t=parse((previous.get(key) or {}).get("checked_utc"))
            if t:
                status=str((previous.get(key) or {}).get("status") or "")
                # Old generic HTML endpoint explicitly blocked GitHub.
                # Do not cache that implementation error against the new API.
                cooldown=(0 if status=="UNSAFE_OR_NOT_PUBLIC" else
                          24 if status in ("HTTP_403","HTTP_429","ACCESS_OR_JSON_ERROR") else 12)
                if dt.timedelta(0)<=dt.datetime.now(UTC)-t<dt.timedelta(hours=cooldown):
                    break
            choices.append((asset,repo,key))
            ids_selected.add(cid)
            break
        if len(choices)>=max_repos:break
    def task(job):
        asset,repo,key=job
        try:
            if download is not None:
                # Offline test injection for Atom-compatible source examples.
                try:from research_collector import parse_feed
                except ImportError:from src.research_collector import parse_feed
                raw,status=download("https://github.com/"+repo+"/releases.atom")
                entries=parse_feed(raw,"DIRECT_LINKED_"+str(asset["cmc_id"]),
                    stamp(dt.datetime.now(UTC)),limit=30) if raw else []
            else:
                # Production uses the keyless public GitHub REST API. The
                # generic website/feed discoverer intentionally excludes
                # GitHub, so never call it for an authoritative releases feed.
                releases,status=api_releases(repo)
                entries=[{"headline":row.get("name") or row.get("tag_name"),
                          "excerpt":row.get("body") or "",
                          "url":row.get("html_url"),
                          "published_utc":row.get("published_at")}
                         for row in releases]
            found=[]
            for row in entries:
                event=release_event(asset,repo,row,cutoff,stamp(dt.datetime.now(UTC)),{})
                if event:found.append(event)
            return key,repo,found,status,len(entries)
        except (OSError,UnicodeError,TypeError,ValueError,TimeoutError) as exc:
            return key,repo,[],type(exc).__name__,0
    new=[];probe_log=[]
    if network:
        # A small initial probe prevents 12 simultaneous GitHub 403/429s
        # on runners sharing the unauthenticated 60-request/hour quota.
        first=choices[:2]
        rest=choices[2:]
        results=[task(x) for x in first]
        blocked=bool(first and all(x[3] in ("HTTP_403","HTTP_429") for x in results))
        if not blocked:
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
                results.extend(pool.map(task,rest))
        for key,repo,items,status,count in results:
            now=stamp(dt.datetime.now(UTC))
            previous[key]={"checked_utc":now,"repo":repo,
                           "status":str(status),"feed_entries":count,
                           "substantive_events":len(items)}
            probe_log.append({"repo":repo,"status":str(status),
                              "feed_entries":count,"substantive_events":len(items)})
            new.extend(items[:6])
        if blocked:probe_log.append({"status":"RATE_LIMIT_CIRCUIT_OPEN_AFTER_2_FAILURES",
                                    "not_attempted":len(rest)})
    combined={e["id"]:e for e in cached+new}
    combined_items=list(combined.values())
    recent={24:0,72:0,168:0}
    for h in recent:
        recent[h]=sum(bool(parse(e.get("published_utc")) and
                dt.timedelta(0)<=cutoff-parse(e["published_utc"])<=dt.timedelta(hours=h))
                for e in combined_items)
    audit={
        "repositories_probed":sum("repo" in x for x in probe_log),
        "api":"GITHUB_PUBLIC_REST_RELEASES_KEYLESS",
        "no_credential_or_paid_api":True,
        "coin_ids_targeted":len(ids_selected) if network else 0,
        "new_substantive_release_events":len(new),
        "newly_supported_coins":len({e["candidate_cmc_ids"][0] for e in new
                                   if e["candidate_cmc_ids"][0] not in rich}),
        "cached_substantive_release_events":len(cached),
        "substantive_release_events_recent_hours":recent,
        "source_identity_quarantine":skip,
        "probe_log":probe_log,
        "no_verified_token_catalysts_claimed":True,
        "provider_project_repo_association_is_not_token_event":True,
        "all_raw_titles_and_feeds_not_counted_without_substantive_text":True
    }
    now=dt.datetime.now(UTC)
    history_items={k:v for k,v in previous.items() if isinstance(v,dict) and
        parse(v.get("checked_utc")) and
        dt.timedelta(0)<=now-parse(v["checked_utc"])<=dt.timedelta(days=35)}
    return combined_items,{"schema_version":"cmc100-linked-release-events-v1",
        "events":combined_items[-300:],"probes":history_items,
        "provider_identity_quarantine":skip,
        "note":"Not a token-price event feed, only source-linked software release notes."},audit
