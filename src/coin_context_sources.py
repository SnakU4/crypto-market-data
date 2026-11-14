#!/usr/bin/env python3
"""Keyless public per-coin descriptive context; a baseline, NOT 24h catalysts.

Uses CoinPaprika descriptive profiles, CoinGecko public profiles as a strictly
identity-matched fallback, and persists an auditable cache in docs/intelligence.
Never invents descriptions or substitutes market price rows for actual context.
"""
from __future__ import annotations

import concurrent.futures
import datetime as dt
import html
import json
import math
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request

UTC = dt.timezone.utc
USER_AGENT = "CMC100-Coin-Context/1.0 (public research; github.com/SnakU4/crypto-market-data)"
PAPRIKA = "https://api.coinpaprika.com/v1"
GECKO = "https://api.coingecko.com/api/v3"
CACHE_PATH = "docs/intelligence/coin_profiles.json"
PROFILES_MAX_AGE_HOURS = 72
# Narrow, manually corroborated ticker/name aliases. Every mapping still requires
# the published provider ID, expected name, and exact ticker to match. These
# are not heuristic aliases and MUST NEVER be inferred for arbitrary tickers.
# Public corroboration: Bitfinex LEO issuer, minepi.com PI, midnight.network
# NIGHT supply and CoinPaprika night-midnight2 (not unrelated night-midnight),
# CoinPaprika's community meme listing for 币安人生.
VERIFIED_PROVIDER_ALIASES = {
    ("coingecko",3957): ("leo-token","LEO Token"),
    ("coingecko",35697): ("pi-network","Pi Network"),
    ("coinpaprika",35697): ("pi2-pi-network","Pi Network"),
    ("coinpaprika",39064): ("night-midnight2","Midnight"),
    ("coinpaprika",38590): ("bianrensheng-bianrensheng","币安人生 (BinanceLife)")
}


def stamp(t):
    return t.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parsed(value):
    try:
        v = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return v.astimezone(UTC) if v.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def canonical(value):
    """Compare full project identity strings, never ticker alone."""
    return re.sub(r"[^\w]", "", str(value or "").casefold(), flags=re.UNICODE)


def project_name(value):
    """Remove only explicit CoinMarketCap display annotations, not identity."""
    name=str(value or "")
    name=re.sub(r"\s*\[(?:New|Old)\]\s*$", "", name, flags=re.I)
    name=re.sub(r"\s*\((?:prev\.|previously|ex[-.]?)\s+[^)]*\)\s*$",
                "", name, flags=re.I)
    return canonical(name)


def clean(text, limit=450):
    v = html.unescape(re.sub(r"<[^>]*>", " ", str(text or "")))
    v = re.sub(r"\s+", " ", v).strip()
    v = re.sub(r"\s*Source:\s*CoinPaprika\.com\s*$", "", v, flags=re.I)
    return v[:limit].strip()


def fetch_json(url, opener=None):
    """Only documented public provider hosts; never follows user-supplied URLs."""
    host = urllib.parse.urlsplit(url).hostname
    if host not in ("api.coinpaprika.com", "api.coingecko.com"):
        raise ValueError("Source endpoint not allowlisted")
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT, "Accept": "application/json"})
    op = opener or urllib.request.urlopen
    with op(req, timeout=12) as response:
        raw = response.read(24_000_001)
        if len(raw) > 24_000_000:
            raise ValueError("Provider response exceeds 24 MB")
    return json.loads(raw)


def exact_match(assets, listing, provider=None):
    """Reject ambiguous listings; require both exact normalized asset name and ticker."""
    found = {}
    index = {}
    for item in listing:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        if item.get("is_active") is False:
            continue
        key = (project_name(item.get("name")), canonical(item.get("symbol")))
        index.setdefault(key, []).append(item)
    for asset in assets:
        key = (project_name(asset["name"]), canonical(asset["symbol"]))
        rows = index.get(key, [])
        # Multiple active assets with same name and ticker are NOT safely identifiable.
        pinned=VERIFIED_PROVIDER_ALIASES.get((provider,int(asset["cmc_id"])))
        if pinned:
            matches=[x for x in listing if isinstance(x,dict)
                and x.get("id")==pinned[0]
                and project_name(x.get("name"))==project_name(pinned[1])
                and canonical(x.get("symbol"))==canonical(asset["symbol"])
                and x.get("is_active") is not False]
            if len(matches)==1:
                found[str(asset["cmc_id"])]=pinned[0]
            # Fail closed if the pinned identity is missing, even if a
            # different ticker/name match could be selected automatically.
            continue
        if len(rows) == 1:
            found[str(asset["cmc_id"])] = rows[0]["id"]
    return found


def valid_profile(asset, raw, provider, received):
    if not isinstance(raw, dict):
        return None
    strict=project_name(raw.get("name")) == project_name(asset["name"])
    alias=VERIFIED_PROVIDER_ALIASES.get((provider,int(asset["cmc_id"])))
    pinned_ok=bool(alias and str(raw.get("id"))==alias[0]
        and project_name(raw.get("name"))==project_name(alias[1]))
    if canonical(raw.get("symbol"))!=canonical(asset["symbol"]) or (alias and not pinned_ok) or not (strict or pinned_ok):
        return None
    if provider == "coinpaprika":
        description = clean(raw.get("description"))
        tags = [clean(t.get("name"), 70) for t in (raw.get("tags") or [])
                if isinstance(t, dict)]
        attrs = {k: raw.get(k) for k in ("type", "started_at", "proof_type",
            "hash_algorithm", "open_source", "development_status", "org_structure")
            if raw.get(k) is not None}
        team = [{"name": clean(member.get("name"), 70),
                 "role": clean(member.get("position"), 85)}
                 for member in (raw.get("team") or [])
                 if isinstance(member, dict) and member.get("name")][:8]
        src_id = str(raw["id"])
        src_url = "https://coinpaprika.com/coin/" + urllib.parse.quote(src_id, safe="") + "/"
        links = raw.get("links") or {}
        if not isinstance(links,dict):links={}
        url_types = ("website", "source_code", "explorer")
        citations = {k: [v for v in links.get(k, []) if isinstance(v, str) and v.startswith("https://")][:2]
                     for k in url_types if isinstance(links.get(k), list)}
        wp = raw.get("whitepaper") or {}
        if isinstance(wp, dict) and str(wp.get("link", "")).startswith("https://"):
            citations["whitepaper"] = [wp["link"]]
    else:
        lang = raw.get("description") or {}
        description = clean((lang.get("en") or lang.get("de") or "") if isinstance(lang, dict) else "", 450)
        tags = [clean(t, 70) for t in (raw.get("categories") or []) if isinstance(t, str)]
        attrs = {"genesis_date": raw.get("genesis_date"),
                 "asset_platform_id": raw.get("asset_platform_id"),
                 "block_time_in_minutes": raw.get("block_time_in_minutes")}
        attrs = {k: v for k, v in attrs.items() if v is not None}
        team = []
        src_id = str(raw["id"])
        src_url = "https://www.coingecko.com/en/coins/" + urllib.parse.quote(src_id, safe="")
        links = raw.get("links") or {}
        if not isinstance(links,dict):links={}
        citations = {}
        for key in ("homepage", "blockchain_site", "official_forum_url"):
            val = links.get(key) or []
            if isinstance(val, list):
                citations[key] = [v for v in val if isinstance(v, str) and v.startswith("https://")][:2]
        code = links.get("repos_url") or {}
        if isinstance(code, dict):
            citations["source_code"] = [v for v in (code.get("github") or []) if isinstance(v, str) and v.startswith("https://")][:2]

    tags = list(dict.fromkeys(x for x in tags if x))[:12]
    # Context requires an actual descriptive account AND at least one independent
    # identity-specific detail. Bare name, ticker, price, or tag list never suffices.
    meaningful = (len(description) >= 105 and len(description.split()) >= 16
                  and (len(tags) >= 1 or len(attrs) >= 2 or bool(citations)))
    return {"cmc_id": int(asset["cmc_id"]), "name": asset["name"], "symbol": asset["symbol"],
       "provider": provider, "provider_id": src_id, "source_url": src_url,
       "observed_utc": received, "description_excerpt": description,
       "categories": tags, "project_team_unverified": team,
       "technology_and_project_attributes": attrs,
       "primary_links_unverified": citations,
       "has_substantive_descriptive_context": bool(meaningful),
       "context_type": "EVERGREEN_PROJECT_BACKGROUND_NOT_DATED_CATALYST",
       "claim_status": "THIRD_PARTY_DESCRIPTION_NOT_INDEPENDENTLY_FACT_CHECKED",
       "provider_identity_validation": ("PINNED_PROVIDER_ID_NAME_AND_SYMBOL" if
            pinned_ok and not strict else "EXACT_NAME_AND_SYMBOL_MATCH")}


def extra_context(kind, raw, observed, cutoff):
    """Bounded structured provider data; event date is NOT its publication date."""
    if not isinstance(raw, list):
        return [] if kind == "events" else {}
    if kind == "events":
        out = []
        for r in raw:
            if not isinstance(r, dict):
                continue
            title = clean(r.get("name") or r.get("title"), 150)
            description = clean(r.get("description"), 310)
            date = str(r.get("date") or r.get("start_date") or r.get("date_from") or "")
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
                date += "T00:00:00Z"
            url = r.get("link") or r.get("url")
            if not title or not date or not parsed(date):
                continue
            when = parsed(date)
            # An announced event may be in the future; retain that distinction.
            if not (cutoff - dt.timedelta(days=45) <= when <= cutoff + dt.timedelta(days=120)):
                continue
            out.append({"title": title, "description_excerpt": description,
                "event_date_utc": stamp(when),
                "source_url": url if isinstance(url, str) and url.startswith("https://") else None,
                "first_observed_utc": observed,
                "relation_status": "THIRD_PARTY_COIN_EVENT_DATE_NOT_PUBLICATION_DATE",
                "has_substantive_event_details": len(description) >= 110 and len(description.split()) >= 16})
        out.sort(key=lambda x:x["event_date_utc"])
        return out[:8]
    results = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        exchange = r.get("exchange") or {}
        exchange_name = exchange.get("name") if isinstance(exchange, dict) else str(exchange)
        pair = str(r.get("pair") or "")
        quotes = r.get("quotes") or {}
        usd = quotes.get("USD") or {} if isinstance(quotes, dict) else {}
        volume = usd.get("volume_24h") if isinstance(usd, dict) else None
        if isinstance(volume, (int, float)) and math.isfinite(volume) and volume >= 0:
            results.append({"exchange": clean(exchange_name, 75),
                "pair": clean(pair, 55), "volume_24h_usd": round(volume, 2)})
    results.sort(key=lambda x:-x["volume_24h_usd"])
    return {"reported_pair_count_with_usd_volume": len(results),
        "top_markets_by_reported_24h_volume": results[:6],
        "total_reported_volume_across_pairs_usd_NOT_UNIQUE_TRADING_VOLUME":
            round(sum(x["volume_24h_usd"] for x in results), 2),
        "observed_utc": observed,
        "relation_status": "THIRD_PARTY_MARKET_AGGREGATE_NOT_EXECUTION_LIQUIDITY",
        "disclaimer": "Reported 24h volumes across pairs may double-count activity."}


def collect_profiles(root, assets, cutoff, network=False, opener=None, max_gecko=15, max_extra_per_type=100):
    root = pathlib.Path(root)
    path = root / CACHE_PATH
    past = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    prior = past.get("profiles") or {}
    if not isinstance(prior, dict):
        prior = {}
    cutoff = cutoff.astimezone(UTC)
    profiles = {}
    for asset in assets:
        key = str(asset["cmc_id"])
        item = prior.get(key)
        if (isinstance(item, dict) and int(item.get("cmc_id", -1)) == int(asset["cmc_id"])
                and project_name(item.get("name")) == project_name(asset["name"])
                and canonical(item.get("symbol")) == canonical(asset["symbol"])
                and (parsed(item.get("observed_utc")) or cutoff + dt.timedelta(days=1)) <= cutoff):
            profiles[key] = item
    audit = {"configured_sources": ["coinpaprika_keyless_coin_profiles", "coinpaprika_coin_events", "coinpaprika_coin_markets", "coingecko_public_coin_profiles"],
             "calls": 0, "success": 0, "errors": [], "source_status": {},
             "strict_name_and_symbol_matching": True, "historical_network_disabled": not network}
    if network:
        received = stamp(dt.datetime.now(UTC))
        try:
            pap_list = fetch_json(PAPRIKA + "/coins", opener)
            pap_ids = exact_match(assets, pap_list, provider="coinpaprika")
            audit["source_status"]["coinpaprika_coin_list"] = "OK"
            audit["calls"] += 1
        except (ValueError, KeyError, TypeError, OSError, urllib.error.URLError) as exc:
            pap_ids = {}
            audit["errors"].append("coinpaprika_list:" + type(exc).__name__)
            audit["source_status"]["coinpaprika_coin_list"] = "FAILED"
        work = []
        for asset in assets:
            key = str(asset["cmc_id"])
            previous = profiles.get(key, {})
            first = parsed(previous.get("observed_utc"))
            age = (cutoff - first).total_seconds() / 3600 if first else 99999
            if key in pap_ids and (age > PROFILES_MAX_AGE_HOURS or not previous.get("has_substantive_descriptive_context")):
                work.append((asset, PAPRIKA + "/coins/" + urllib.parse.quote(pap_ids[key], safe="")))
        def pap_call(pair):
            asset, url = pair
            try:
                raw = fetch_json(url, opener)
                return asset, valid_profile(asset, raw, "coinpaprika", received), None
            except (ValueError, TypeError, KeyError, OSError, urllib.error.URLError) as exc:
                return asset, None, type(exc).__name__
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            for asset, item, err in pool.map(pap_call, work):
                audit["calls"] += 1
                if item:
                    audit["success"] += 1
                    key = str(asset["cmc_id"])
                    if item["has_substantive_descriptive_context"] or not profiles.get(key, {}).get("has_substantive_descriptive_context"):
                        profiles[key] = item
                else:
                    audit["errors"].append("coinpaprika:" + asset["symbol"] + ":" + (err or "IDENTITY_MISMATCH"))
        # Free project-specific dated events and market/venue distribution.
        # Cache these independently for 24h so keyless monthly quotas remain bounded.
        # This does not imply every coin has events, or that a listed event is a catalyst.
        extra_work = []
        for kind in ("events", "markets"):
            chosen = 0
            for asset in assets:
                key = str(asset["cmc_id"])
                if key not in pap_ids or key not in profiles or chosen >= max_extra_per_type:
                    continue
                field = kind + "_observed_utc"
                last = parsed(profiles[key].get(field))
                if last and (cutoff - last).total_seconds() < 24 * 3600:
                    continue
                extra_work.append((asset, kind, PAPRIKA + "/coins/" +
                    urllib.parse.quote(pap_ids[key], safe="") + "/" + kind))
                chosen += 1
        def extra_call(task):
            asset, kind, url = task
            try:
                data = fetch_json(url, opener)
                return asset, kind, extra_context(kind, data, stamp(dt.datetime.now(UTC)), cutoff), None
            except urllib.error.HTTPError as exc:
                return asset, kind, None, "HTTP_" + str(exc.code)
            except (ValueError, TypeError, KeyError, OSError, urllib.error.URLError) as exc:
                return asset, kind, None, type(exc).__name__
        audit["extra_calls"] = 0
        audit["extra_ok"] = {"events":0, "markets":0}
        audit["extra_endpoint_state"] = {}
        def store_extra(asset,kind,data,err):
            audit["calls"] += 1
            audit["extra_calls"] += 1
            if data is not None:
                audit["success"] += 1
                audit["extra_ok"][kind] += 1
                profile = profiles[str(asset["cmc_id"])]
                profile["coin_" + kind] = data
                profile[kind + "_observed_utc"] = stamp(dt.datetime.now(UTC))
            else:
                audit["errors"].append("coinpaprika_" + kind + ":" +
                    asset["symbol"] + ":" + (err or "UNKNOWN_ERROR"))
        by_kind = {kind: [task for task in extra_work if task[1]==kind]
                   for kind in ("events","markets")}
        for kind, batch in by_kind.items():
            if not batch:continue
            # Probe three different assets before broad fan-out. 402/403/404
            # failures on all three indicate that this endpoint is currently
            # unavailable for the keyless GitHub runner, not 100 missing events.
            probes=batch[:3]
            probe_results=[extra_call(task) for task in probes]
            for asset,k,data,err in probe_results:
                store_extra(asset,k,data,err)
            inaccessible = all(data is None and err in
                ("HTTP_402","HTTP_403","HTTP_404","HTTP_429") for _,_,data,err in probe_results)
            if inaccessible:
                audit["extra_endpoint_state"][kind] = "DISABLED_AFTER_THREE_HTTP_FAILURES"
                continue
            audit["extra_endpoint_state"][kind] = "PROBES_ACCEPTED_CONTINUE"
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
                for asset,k,data,err in pool.map(extra_call, batch[3:]):
                    store_extra(asset,k,data,err)
        missing = [a for a in assets if not profiles.get(str(a["cmc_id"]), {}).get("has_substantive_descriptive_context")]
        if missing and max_gecko > 0:
            try:
                glist = fetch_json(GECKO + "/coins/list", opener)
                gids = exact_match(missing, glist, provider="coingecko")
                audit["calls"] += 1
                audit["source_status"]["coingecko_coin_list"] = "OK"
            except (ValueError, KeyError, TypeError, OSError, urllib.error.URLError) as exc:
                gids = {}
                audit["errors"].append("coingecko_list:" + type(exc).__name__)
                audit["source_status"]["coingecko_coin_list"] = "FAILED"
            # Cap unauthenticated CoinGecko calls to respect the public 5-15/min limit.
            for asset in missing:
                key = str(asset["cmc_id"])
                if max_gecko <= 0:
                    break
                if key not in gids:
                    continue
                max_gecko -= 1
                params = "?localization=false&tickers=false&market_data=false&community_data=false&developer_data=false"
                url = GECKO + "/coins/" + urllib.parse.quote(gids[key], safe="") + params
                try:
                    raw = fetch_json(url, opener)
                    item = valid_profile(asset, raw, "coingecko", stamp(dt.datetime.now(UTC)))
                    audit["calls"] += 1
                    if item:
                        audit["success"] += 1
                        if item["has_substantive_descriptive_context"] or not profiles.get(key, {}).get("has_substantive_descriptive_context"):
                            profiles[key] = item
                    else:
                        audit["errors"].append("coingecko:" + asset["symbol"] + ":IDENTITY_MISMATCH")
                except (ValueError, TypeError, KeyError, OSError, urllib.error.URLError) as exc:
                    audit["calls"] += 1
                    audit["errors"].append("coingecko:" + asset["symbol"] + ":" + type(exc).__name__)
                time.sleep(7.1)
    substantive = [a for a in assets if profiles.get(str(a["cmc_id"]), {}).get("has_substantive_descriptive_context")]
    gap = [{"cmc_id": a["cmc_id"], "symbol": a["symbol"], "name": a["name"],
            "reason": "NO_SOURCE_BACKED_SUBSTANTIVE_DESCRIPTION"}
           for a in assets if not profiles.get(str(a["cmc_id"]), {}).get("has_substantive_descriptive_context")]
    audit.update({"assets": len(assets), "profile_present": len(profiles),
        "coins_with_dated_third_party_events":sum(bool(p.get("coin_events")) for p in profiles.values()),
        "coins_with_substantive_dated_event_details":sum(
            any(e.get("has_substantive_event_details") for e in p.get("coin_events", []))
            for p in profiles.values()),
        "coins_with_cross_exchange_market_observations":sum(bool(
            (p.get("coin_markets") or {}).get("reported_pair_count_with_usd_volume"))
            for p in profiles.values()),
        "substantive_project_profiles": len(substantive), "profile_gaps": gap,
        "all_100_substantive_background": len(gap) == 0,
        "recent_24h_catalyst_coverage_NOT_INFERRED": True,
        "disclaimer": "Third-party descriptive context is not independently verified, current news, or token-price causality."})
    return {"schema_version": "cmc100-third-party-coin-profiles-v1",
        "source_licensing": "CoinPaprika free/keyless for personal use; cite Powered by CoinPaprika. Check redistribution and commercial licensing.",
        "profiles": profiles, "audit": audit}, audit
