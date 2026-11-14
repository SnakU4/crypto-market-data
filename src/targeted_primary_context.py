#!/usr/bin/env python3
"""Keyless targeted original-source coverage for CMC100 coins.

Curated CMC-ID mappings are verified separately from token-symbol search.
Only retrieved, substantive original texts count. Project background is never
reported as timely news, an event, price causality, or verified token economics.
"""
from __future__ import annotations
import concurrent.futures
import datetime as dt
import pathlib
import re
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = "docs/intelligence/primary_coin_context.json"
UTC = dt.timezone.utc

# Verify exact project/token association manually before adding a mapping.
# Prefer the token's issuer/project docs. Exchange announcements are explicitly
# secondary, not invented issuer documentation (notably the community memecoin).
# Format: CMC_ID: (EXACT_CMC_NAME, TOKEN_SYMBOL, [(URL, identity phrase, class),...])
REGISTRY = {
  3957: ("UNUS SED LEO","LEO", [
      ("https://support.bitfinex.com/hc/en-us/articles/360023342674-Unus-Sed-LEO-LEO","UNUS SED LEO","ISSUER_DOCUMENTATION")]),
  28321: ("Polygon (prev. MATIC)","POL", [
      ("https://support.polygon.technology/support/solutions/articles/82000906989-information-related-to-pol-contract-and-migration","POL","ISSUER_DOCUMENTATION")]),
  29270: ("Aero","AERO", [
      ("https://aerodrome.finance/docs","AERO","ISSUER_DOCUMENTATION")]),
  33251: ("World Liberty Financial","WLFI", [
      ("https://docs.worldlibertyfinancial.com/wlfi-token/tokenomics","WLFI","ISSUER_DOCUMENTATION"),
      ("https://worldlibertyfinancial.com/governance","WLFI","ISSUER_DOCUMENTATION")]),
  35697: ("Pi","PI", [
      ("https://minepi.com/white-paper/","Pi","ISSUER_DOCUMENTATION"),
      ("https://minepi.com/about/","Pi Network","ISSUER_DOCUMENTATION")]),
  36341: ("Aster","ASTER", [
      ("https://docs.asterdex.com/usdaster-token/tokenomics","ASTER","ISSUER_DOCUMENTATION")]),
  36507: ("Pump.fun","PUMP", [
      ("https://pump.fun/pump-token","PUMP","ISSUER_DOCUMENTATION")]),
  36645: ("Plasma","XPL", [
      ("https://www.plasma.org/company/blog/xpl-the-public-sale-and-its-role-in-the-plasma-ecosystem","XPL","ISSUER_DOCUMENTATION")]),
  37263: ("Canton","CC", [
      ("https://www.canton.network/faq","Canton Coin","ISSUER_DOCUMENTATION")]),
  38482: ("Falcon Finance","FF", [
      ("https://docs.falcon.finance/ff-token/","FF","ISSUER_DOCUMENTATION"),
      ("https://docs.falcon.finance/ff-token/ff-tokenomics/","FF","ISSUER_DOCUMENTATION")]),
  38590: ("币安人生","币安人生", [
      ("https://www.binance.com/de/support/announcement/detail/51881f9d018242ce80bed6ce015de2a7","币安人生","EXCHANGE_ANNOUNCEMENT_NOT_ISSUER")]),
  38828: ("Kite","KITE", [
      ("https://docs.gokite.ai/about/tokenomics","KITE","ISSUER_DOCUMENTATION")]),
  38849: ("Pieverse","PIEVERSE", [
      ("https://www.pieverse.io/whitepaper","PIEVERSE","ISSUER_DOCUMENTATION")]),
  38892: ("Stable","STABLE", [
      ("https://docs.stable.xyz/","STABLE","ISSUER_DOCUMENTATION"),
      ("https://support.bitfinex.com/hc/en-us/articles/53072258514073-Stable-STABLE","STABLE","EXCHANGE_ANNOUNCEMENT_NOT_ISSUER")]),
  39064: ("Midnight","NIGHT", [
      ("https://midnight.network/night","NIGHT","ISSUER_DOCUMENTATION")]),
  39125: ("Lighter","LIT", [
      ("https://docs.lighter.xyz/","LIT","ISSUER_DOCUMENTATION"),
      ("https://lighter.xyz/","Lighter","ISSUER_DOCUMENTATION")])
}

def utc(t):
    return t.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00","Z")

def parse(x):
    try:
        v=dt.datetime.fromisoformat(str(x).replace("Z","+00:00"))
        return v.astimezone(UTC) if v.tzinfo else None
    except (ValueError,TypeError,OverflowError):
        return None

def normal(x):
    return re.sub(r"[^\w]","",str(x or "").casefold(),flags=re.UNICODE)

def valid_project(asset, record):
    return normal(asset.get("name"))==normal(record[0]) and normal(asset.get("symbol"))==normal(record[1])

def has_identity(text, expected):
    return bool(re.search(r"(?<!\w)"+re.escape(expected)+r"(?!\w)", str(text or ""), flags=re.I))

def substantive(title, raw, expected):
    try:
        from discovery_quality import has_additional_information
    except ImportError:
        from src.discovery_quality import has_additional_information
    v=re.sub(r"\s+"," ",str(raw or "")).strip()
    return (len(v)>=240 and len(v.split())>=36 and
            has_identity(v, expected) and has_additional_information(title,v) and
            not all(x in v.casefold() for x in ("loading","something went wrong","try again")))

def collect(root, assets, cutoff, network=False, fetcher=None, max_pages=28):
    """Persist only observed original excerpts; stale cached context is still
    background, never fresh news. Historical replay may not use a future fetch."""
    root=pathlib.Path(root)
    path=root/CACHE
    prior={}
    if path.exists():
        try:
            import json
            prior=(json.loads(path.read_text(encoding="utf-8")).get("profiles") or {})
        except (ValueError,OSError,TypeError):
            prior={}
    profiles={}
    for a in assets:
        cid=int(a["cmc_id"]); key=str(cid)
        rec=REGISTRY.get(cid); old=prior.get(key)
        if (rec and valid_project(a,rec) and isinstance(old,dict)
            and old.get("source_url") in [x[0] for x in rec[2]]
            and parse(old.get("first_observed_utc")) and parse(old["first_observed_utc"])<=cutoff):
            profiles[key]=old
    missing=[a for a in assets if int(a["cmc_id"]) in REGISTRY
             and valid_project(a,REGISTRY[int(a["cmc_id"])])
             and not profiles.get(str(a["cmc_id"]),{}).get("substantive")]
    selection=[]
    for a in missing:
        cid=int(a["cmc_id"]);rec=REGISTRY[cid]
        for url,phrase,kind in rec[2]:
            if len(selection)>=max_pages:break
            selection.append((a,url,phrase,kind))
    if fetcher is None:
        try:
            from discovery_quality import extract_article as fetcher
        except ImportError:
            from src.discovery_quality import extract_article as fetcher

    def one(task):
        a,url,phrase,kind=task
        try:
            text=fetcher(url)
            if substantive(a["name"],text,phrase):
                # Quotation is short and attached to an authoritative public URL.
                return a,{"cmc_id":a["cmc_id"],"name":a["name"],"symbol":a["symbol"],
                    "source_url":url,"source_kind":kind,
                    "identity_match":"CURATED_EXACT_CMC_ID_NAME_SYMBOL_AND_SOURCE_TERM",
                    "description_excerpt":re.sub(r"\s+"," ",text).strip()[:420],
                    "first_observed_utc":utc(dt.datetime.now(UTC)),
                    "substantive":True,
                    "context_type":"ORIGINAL_PROJECT_BACKGROUND_NOT_FRESH_NEWS",
                    "claim_status":"DOCUMENT_TEXT_EXTRACTED_NOT_INDEPENDENT_FACT_CHECK"},None
            return a,None,"NO_ACCESSIBLE_MATCHING_SUBSTANTIVE_TEXT"
        except (OSError,TypeError,ValueError,TimeoutError) as exc:
            return a,None,type(exc).__name__
    attempted=0
    errors=[]
    if network:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            for a,item,err in pool.map(one,selection):
                attempted+=1
                if item:
                    profiles.setdefault(str(a["cmc_id"]),item)
                else:
                    errors.append({"cmc_id":a["cmc_id"],"symbol":a["symbol"],"reason":err})
    accepted={int(cid) for cid,v in profiles.items()
        if v.get("substantive") and v.get("source_kind")=="ISSUER_DOCUMENTATION"}
    secondary={int(cid) for cid,v in profiles.items()
        if v.get("substantive") and v.get("source_kind")=="EXCHANGE_ANNOUNCEMENT_NOT_ISSUER"}
    gaps=[{"cmc_id":a["cmc_id"],"symbol":a["symbol"],"name":a["name"]}
          for a in assets if int(a["cmc_id"]) in REGISTRY
          and valid_project(a,REGISTRY[int(a["cmc_id"])])
          and int(a["cmc_id"]) not in accepted and int(a["cmc_id"]) not in secondary]
    audit={"mapped_projects":len(REGISTRY),"pages_attempted":attempted,
           "substantive_issuer_dossiers":len(accepted),
           "substantive_exchange_only_dossiers":len(secondary),
           "targeted_gaps":gaps,"failed_pages":errors[:35],
           "no_fresh_event_claim":True,"no_automatic_relevance_inference":True}
    return {"schema_version":"cmc100-exact-curated-original-project-v1",
        "profiles":profiles,"audit":audit},audit
