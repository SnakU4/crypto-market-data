#!/usr/bin/env python3
"""Direct publisher-feed discovery for coins lacking substantive individual articles.

Uses only the project website URLs supplied by an exact-matched provider coin
profile, with public HTTPS/DNS/robots checks and advertised RSS/Atom or standard
public feed URLs. Source-text candidate is attributed, NOT an established
price catalyst or independent official-issuer verification.
"""
from __future__ import annotations
import collections
import concurrent.futures
import datetime as dt
import hashlib
import json
import pathlib
import urllib.parse

UTC=dt.timezone.utc
HISTORY="docs/intelligence/coin_feed_probe_history.json"
# Multi-asset exchanges require the coin to be identifiable in BOTH fields.
# This prevents a generic exchange article from being attributed to every
# associated exchange token. Project-owned publisher websites are more focused.
MULTI_ASSET_PUBLISHERS={"binance.com","kucoin.com","bitfinex.com",
    "bitget.com","okx.com","okex.com","gate.io","coinbase.com","paxos.com"}
# The CMC100 #28298 gaming BEAM is not the older Beam Mimblewimble chain.
PROJECT_WEBSITE_QUARANTINE={(28298,"beam.mw")}

def stamp(t):
    return t.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00","Z")

def when(s):
    try:
        t=dt.datetime.fromisoformat(str(s).replace("Z","+00:00"))
        return t.astimezone(UTC) if t.tzinfo else None
    except (ValueError,TypeError,OverflowError):
        return None

def collect(root,assets,profiles,events,cutoff,network=False,max_coins=12,
            get=None):
    root=pathlib.Path(root)
    path=root/HISTORY
    try: past=json.loads(path.read_text(encoding="utf8")).get("domains",{})
    except (ValueError,OSError,TypeError):past={}
    if not isinstance(past,dict):past={}
    try:
        from primary_source_discovery import retrieve,inspect_feed_links
        from research_collector import parse_feed
        from discovery_quality import has_additional_information
        from coin_news_resolution import title_relevant
    except ImportError:
        from src.primary_source_discovery import retrieve,inspect_feed_links
        from src.research_collector import parse_feed
        from src.discovery_quality import has_additional_information
        from src.coin_news_resolution import title_relevant
    already_rich={int(cid) for e in events
        if has_additional_information(e.get("title"),e.get("excerpt"))
        for cid in (e.get("candidate_cmc_ids") or [])}
    selected=[];seen_domains=set();skipped=collections.Counter()
    quarantine=[]
    for asset in assets:
        cid=int(asset["cmc_id"])
        if cid in already_rich:continue
        item=profiles.get(str(cid)) or {}
        links=item.get("primary_links_unverified") or {}
        websites=links.get("website") or links.get("homepage") or []
        if not isinstance(websites,list):continue
        for url in websites[:2]:
            if not isinstance(url,str) or not url.startswith("https://"):continue
            u=urllib.parse.urlsplit(url)
            host=(u.hostname or "").lower().removeprefix("www.")
            if not host or host in seen_domains:continue
            if (cid,host) in PROJECT_WEBSITE_QUARANTINE:
                quarantine.append({"cmc_id":cid,"domain":host,
                    "reason":"UNRELATED_BEAM_MIMBLEWIMBLE_PROJECT"})
                continue
            past_item=past.get(host) or {}
            age=when(past_item.get("attempted_utc"))
            if age and dt.timedelta(0)<=dt.datetime.now(UTC)-age<=dt.timedelta(hours=72):
                skipped["recent_probe"]+=1;continue
            selected.append((asset,url,host))
            seen_domains.add(host)
            break
        if len(selected)>=max_coins:break
    def probe(item):
        asset,site,domain=item
        statuses=[];news=[]
        def download(url):
            if get:return get(url)
            return retrieve(url)
        try:
            html,status=download(site)
            statuses.append("home:"+str(status))
            feed_urls=[]
            if html:
                feed_urls=inspect_feed_links(html.decode("utf8","replace"),site)
            # Standard public feed addresses are candidates, never assumed
            # valid without an explicit parsed RSS/Atom response.
            base=urllib.parse.urlsplit(site)
            rooturl=base.scheme+"://"+base.netloc+"/"
            feed_urls=list(dict.fromkeys(feed_urls+[urllib.parse.urljoin(rooturl,"feed/")]))[:3]
            for feedurl in feed_urls:
                blob,fs=download(feedurl)
                statuses.append("feed:"+str(fs))
                if not blob:continue
                rows=parse_feed(blob,"COIN_PROJECT_FEED_"+str(asset["cmc_id"]),
                    stamp(dt.datetime.now(UTC)),limit=30)
                if not rows:continue
                for row in rows:
                    pub=when(row.get("published_utc"))
                    if pub and pub>cutoff:continue
                    title=row.get("headline") or ""
                    excerpt=row.get("excerpt") or ""
                    # Title + publisher summary MUST positively identify
                    # this coin. Website association is a candidate, not proof.
                    # Project-specific websites may publish generic release
                    # titles; their substantive publisher text still has to
                    # identify the linked project. Exchanges must identify
                    # the asset in BOTH title and body because they discuss
                    # thousands of other assets on one site.
                    if not title_relevant(excerpt,asset):continue
                    if domain in MULTI_ASSET_PUBLISHERS and not title_relevant(title,asset):
                        continue
                    if not has_additional_information(title,excerpt):continue
                    fullurl=str(row.get("url") or "")
                    if not fullurl.startswith("https://"):continue
                    evid="PF:"+hashlib.sha256((str(asset["cmc_id"])+fullurl).encode()).hexdigest()[:18]
                    news.append({"id":evid,"source_plane":"direct_project_feed",
                        "source_id":"COIN_PROJECT_SITE_"+str(asset["cmc_id"]),
                        "source_family":"PROJECT_SITE_PUBLICATION_CANDIDATE",
                        "title":title[:230],"url":fullurl,"excerpt":excerpt[:650],
                        "context_origin":"PUBLIC_PROJECT_WEBSITE_RSS_OR_ATOM",
                        "published_utc":row.get("published_utc"),
                        "first_observed_utc":stamp(dt.datetime.now(UTC)),
                        "scope":"ASSET_CANDIDATE",
                        "candidate_cmc_ids":[int(asset["cmc_id"])],
                        "themes":[],"priority":45,
                        "claim_status":"PUBLISHER_TEXT_NOT_FACT_VERIFIED",
                        "identity_status":"PROJECT_SITE_ASSOCIATION_NOT_INDEPENDENTLY_CONFIRMED",
                        "provenance_ids":[evid]})
                if news:break
            return domain,news,{"coin":asset["symbol"],"url":site,
                "feed_statuses":statuses,"substantive_items":len(news)}
        except (OSError,UnicodeError,ValueError,TypeError,TimeoutError) as exc:
            return domain,[],{"coin":asset["symbol"],"url":site,
                "feed_statuses":statuses,
                "substantive_items":0,"error":type(exc).__name__}
    out=[];source_audit=[]
    if network:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            for domain,rows,audit in pool.map(probe,selected):
                out+=rows[:4]
                source_audit.append(audit)
                past[domain]={"attempted_utc":stamp(dt.datetime.now(UTC)),
                    "substantive_items":audit["substantive_items"]}
    # Auditable but bounded source candidates; never show false 100% coverage.
    audit={"project_domains_attempted":len(selected) if network else 0,
        "coins_with_new_source_excerpts":len({x["candidate_cmc_ids"][0] for x in out}),
        "new_substantive_source_excerpts":len(out),"skipped":dict(skipped),
        "by_project":source_audit,"not_independent_primary_claims":True,
        "publisher_website_identity_quarantine":quarantine,
        "publisher_identity_rule":"PROJECT_SITE_BODY_MATCH; EXCHANGES_REQUIRE_TITLE_AND_BODY",
        "only_public_advertised_or_standard_feed_candidates":True}
    past={k:v for k,v in past.items() if isinstance(v,dict) and
          when(v.get("attempted_utc")) and dt.timedelta(0)<=dt.datetime.now(UTC)-when(v["attempted_utc"])<=dt.timedelta(days=35)}
    return out,{"domains":past,"cooldown_hours":72},audit
