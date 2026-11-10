#!/usr/bin/env python3
"""Independent structured evidence plane; public APIs, no forecast or coin guesses.

Raw market observations are NOT historical publications, and symbol matching is
NEVER a verified mapping to CMC IDs. Preserve data integrity in every capture.
"""
from __future__ import annotations
import datetime as dt
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
from collections import defaultdict, Counter
try:
    from evidence_extensions import EXTRA_SOURCES, EXTRA_PARSERS
    from evidence_intelligence import assign_identity, load_previous, compute_deltas, integrated_quality, stamp
except ModuleNotFoundError:
    from src.evidence_extensions import EXTRA_SOURCES, EXTRA_PARSERS
    from src.evidence_intelligence import assign_identity, load_previous, compute_deltas, integrated_quality, stamp
import urllib.error
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"docs"/"evidence_engine"
MARKET=ROOT/"docs"/"latest.json"
UTC=dt.timezone.utc
MAX_RESPONSE_BYTES=12_000_000
HEADERS={"User-Agent":"CMC100-Evidence-Engine/1.0 (+https://github.com/SnakU4/crypto-market-data)",
         "Accept":"application/json"}

SOURCES=(
    {"key":"defillama_chains","family":"ONCHAIN_AGGREGATE_PROXY",
     "url":"https://api.llama.fi/v2/chains","max_bytes":2_500_000},
    {"key":"defillama_stablecoins","family":"STABLECOIN_SUPPLY",
     "url":"https://stablecoins.llama.fi/stablecoinchains","max_bytes":2_500_000},
    {"key":"kraken_futures_tickers","family":"DERIVATIVES_MARKET",
     "url":"https://futures.kraken.com/derivatives/api/v3/tickers","max_bytes":5_000_000},
    {"key":"bybit_linear_tickers","family":"DERIVATIVES_MARKET","enabled":False,
     "disable_reason":"GITHUB_ACTIONS_HTTP_403_PREVIOUS_LIVE_RUN",
     "url":"https://api.bybit.com/v5/market/tickers?category=linear","max_bytes":5_000_000},
    {"key":"bybit_instruments","family":"DERIVATIVES_INSTRUMENTS","enabled":False,
     "disable_reason":"GITHUB_ACTIONS_HTTP_403_PREVIOUS_LIVE_RUN",
     "url":"https://api.bybit.com/v5/market/instruments-info?category=linear&limit=1000","max_bytes":5_000_000},
) + EXTRA_SOURCES


def iso(x):return x.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00","Z")
def number(value):
    try:
        v=float(value)
        return v if math.isfinite(v) else None
    except (TypeError,ValueError,OverflowError):
        return None

def get_json(url,max_bytes=MAX_RESPONSE_BYTES,opener=urllib.request.urlopen):
    request=urllib.request.Request(url,headers=HEADERS)
    with opener(request,timeout=16) as response:
        if "json" not in response.headers.get("Content-Type","").lower():
            raise ValueError("NON_JSON_RESPONSE")
        data=response.read(max_bytes+1)
        if len(data)>max_bytes:raise ValueError("RESPONSE_TOO_LARGE")
    return json.loads(data)

def observation(source,id_,title,metrics,observed,attrs=None):
    return {"observation_id":hashlib.sha256((source+":"+id_).encode()).hexdigest()[:24],
            "source":source,"source_item_id":id_,"title":title,
            "metrics":metrics,"attributes":attrs or {},
            "observed_utc":iso(observed),"published_utc":None,
            "time_semantics":"LIVE_SNAPSHOT_NOT_HISTORICAL_PUBLICATION",
            "coin_identity_status":"NOT_VERIFIED",
            "prediction_or_price_direction":"NOT_ASSESSED"}

def parse_chains(raw,now):
    if not isinstance(raw,list):raise ValueError("CHAINS_INVALID")
    rows=[]
    for v in raw:
        if not isinstance(v,dict) or not v.get("name"):continue
        tvl=number(v.get("tvl"))
        if tvl is None or tvl<0:continue
        name=str(v["name"])[:120]
        rows.append(observation("defillama_chains",name,"Chain TVL "+name,
                                {"tvl_usd":tvl},now,{"provider_chain_id":v.get("gecko_id")}))
    return rows

def parse_stablecoins(raw,now):
    if not isinstance(raw,list):raise ValueError("STABLECOIN_CHAINS_INVALID")
    rows=[]
    for v in raw:
        if not isinstance(v,dict) or not v.get("name"):continue
        circ=v.get("totalCirculatingUSD",v.get("totalCirculating"))
        value=number(circ.get("peggedUSD")) if isinstance(circ,dict) else number(circ)
        if value is None or value<0:continue
        name=str(v["name"])[:120]
        rows.append(observation("defillama_stablecoinchains",name,
                                "Stablecoin circulation "+name,{"circulating_usd":value},now))
    return rows

def parse_kraken_tickers(raw,now):
    if not isinstance(raw,dict) or str(raw.get("result")).lower()!="success" or not isinstance(raw.get("tickers"),list):
        raise ValueError("KRAKEN_TICKERS_INVALID")
    rows=[]
    for entry in raw["tickers"]:
        if not isinstance(entry,dict) or entry.get("tag")!="perpetual":
            continue
        symbol=str(entry.get("symbol") or "")
        if not symbol or len(symbol)>40 or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_." for c in symbol):
            continue
        metrics={}
        for field in ("openInterest","fundingRate","fundingRatePrediction",
                      "markPrice","indexPrice","vol24h","volumeQuote","change24h"):
            value=number(entry.get(field))
            if value is not None:metrics[field]=value
        if not metrics:continue
        rows.append(observation("kraken_futures_tickers",symbol,
                                "Kraken perpetual derivatives "+symbol,metrics,now,
                                {"exchange":"Kraken Futures","exchange_symbol":symbol,
                                 "pair":entry.get("pair"),"tag":entry.get("tag"),
                                 "suspended":entry.get("suspended")}))
    return rows


def parse_bybit_tickers(raw,now):
    if not isinstance(raw,dict) or raw.get("retCode")!=0 or not isinstance(raw.get("result",{}).get("list"),list):
        raise ValueError("BYBIT_TICKERS_INVALID")
    rows=[]
    for v in raw["result"]["list"]:
        if not isinstance(v,dict):continue
        symbol=str(v.get("symbol") or "")
        if not symbol.isalnum() or len(symbol)>32:continue
        metrics={}
        for field in ("lastPrice","openInterestValue","openInterest","fundingRate",
                      "nextFundingTime","volume24h","turnover24h","price24hPcnt"):
            if field=="nextFundingTime":
                try:metrics[field]=int(v[field])
                except (ValueError,TypeError,KeyError):pass
            else:
                n=number(v.get(field))
                if n is not None:metrics[field]=n
        if not metrics:continue
        rows.append(observation("bybit_linear_tickers",symbol,
                                "Bybit linear derivatives "+symbol,metrics,now,
                                {"exchange":"Bybit","category":"linear",
                                 "exchange_symbol":symbol,"quoteCoin":v.get("quoteCoin")}))
    return rows

def parse_bybit_instruments(raw,now):
    if not isinstance(raw,dict) or raw.get("retCode")!=0 or not isinstance(raw.get("result",{}).get("list"),list):
        raise ValueError("BYBIT_INSTRUMENTS_INVALID")
    rows=[]
    for v in raw["result"]["list"]:
        if not isinstance(v,dict):continue
        symbol=str(v.get("symbol") or "")
        if not symbol.isalnum() or len(symbol)>32:continue
        rows.append(observation("bybit_instruments",symbol,"Bybit instrument "+symbol,{},now,
                                {"baseCoin":v.get("baseCoin"),"quoteCoin":v.get("quoteCoin"),
                                 "status":v.get("status"),"contractType":v.get("contractType"),
                                 "launchTime":v.get("launchTime")}))
    return rows

PARSERS={"kraken_futures_tickers":parse_kraken_tickers,
         "defillama_chains":parse_chains,
         "defillama_stablecoins":parse_stablecoins,
         "bybit_linear_tickers":parse_bybit_tickers,
         "bybit_instruments":parse_bybit_instruments, **EXTRA_PARSERS}

def capture(market,fetcher=get_json,now=None,sources=SOURCES):
    """Source-isolated collection; never allow one blocked API to hide another."""
    fixed_time=now is not None or fetcher is not get_json
    now=now or dt.datetime.now(UTC)
    assets=market.get("assets") or []
    if len(assets)!=100 or len({int(a["cmc_id"]) for a in assets})!=100 or market.get("index",{}).get("verified_constituents")!=100:
        raise ValueError("OFFICIAL_CMC100_UNIVERSE_REQUIRED")
    observed=[];audit=[]
    for spec in sources:
        if spec.get("enabled") is False:
            audit.append({"source":spec["key"],"family":spec["family"],
                          "status":"DISABLED_ACCESS_RESTRICTED","records":0,
                          "error":spec.get("disable_reason") or "NOT_ENABLED",
                          "url":spec["url"]})
            continue
        try:
            payload=fetcher(spec["url"],spec["max_bytes"])
            # The request completion time is the earliest defensible publicly
            # observed time. In deterministic offline tests use supplied NOW.
            response_at=now if fixed_time else dt.datetime.now(UTC)
            rows=PARSERS[spec["key"]](payload,response_at)
            observed.extend(rows)
            audit.append({"source":spec["key"],"family":spec["family"],
                          "status":"OK" if rows else "OK_NO_RECORDS",
                          "records":len(rows),"observed_utc":iso(response_at),
                          "error":None,"url":spec["url"]})
        except (OSError,ValueError,TypeError,KeyError,urllib.error.URLError) as ex:
            audit.append({"source":spec["key"],"family":spec["family"],"status":"ERROR",
                          "records":0,"error":type(ex).__name__+": "+str(ex)[:180],
                          "url":spec["url"]})
    complete_at=now if fixed_time else dt.datetime.now(UTC)
    count_by_family=Counter()
    source_to_family={x["key"]:x["family"] for x in sources}
    for item in observed:
        family=source_to_family.get(item["source"])
        if not family and item["source"]=="defillama_stablecoinchains":
            family="STABLECOIN_SUPPLY"
        if family:count_by_family[family]+=1
    identity=assign_identity(observed,market)
    metrics={"schema_version":"crypto-evidence-engine-v2",
             "capture_utc":iso(complete_at),"capture_started_utc":iso(now),
             "official_cmc100_count":100,
             "market_snapshot_utc":market.get("snapshot_completed_utc"),
             "configured_sources":len(sources),
             "attempted_sources":sum(x["status"]!="DISABLED_ACCESS_RESTRICTED" for x in audit),
             "successful_sources":sum(x["status"]=="OK" for x in audit),
             "records":len(observed),"records_by_family":dict(count_by_family),
             "source_audit":audit,
             "identity_mapping":identity,
             "verified_cmc_id_matches":identity["anchored_distinct_cmc_ids"],
             "verification_status":"EXCHANGE_SNAPSHOT_ANCHORED; FULL_TOKEN_CONTRACT_VERIFICATION_OPEN",
             "stage1_9_of_10_verified":False,
             "limitations":["NO_GUARANTEED_DIRECT_TOKEN_UNLOCK_FEED",
                            "NO_WALLET_TRANSACTION_INDEX_CMC100_COVERAGE",
                            "NO_UNVERIFIED_TICKER_AUTOMATIC_CMC_MATCH",
                            "POINT_IN_TIME_OBSERVED_WHEN_RECEIVED_NOT_INFERRED_PUBLICATION",
                            "NO_PREDICTIVE_ALPHA_CLAIM"]}
    return {"metrics":metrics,"observations":observed}

def save(result,out=OUT):
    """Hash-verified PIT deltas against previous run; preserve complete archive."""
    out.mkdir(parents=True,exist_ok=True)
    meta_base=result["metrics"]
    capture_at=stamp(meta_base["capture_utc"])
    prior,prior_audit=load_previous(ROOT,out,capture_at)
    deltas=compute_deltas(result["observations"],prior,capture_at)
    stamp_str=meta_base["capture_utc"].replace(":","").replace("-","")
    folder=out/"archive"/stamp_str[:8]
    folder.mkdir(parents=True,exist_ok=True)
    archive=folder/(stamp_str+"_observations.jsonl.gz")
    if archive.exists():raise FileExistsError("IMMUTABLE_SNAPSHOT_ALREADY_EXISTS")
    with archive.open("wb") as target:
        with gzip.GzipFile(filename="",mode="wb",fileobj=target,mtime=0,compresslevel=6) as gz:
            for row in result["observations"]:
                gz.write((json.dumps(row,ensure_ascii=False,separators=(",",":"))+"\n").encode())
    meta={**meta_base,
          "archive_path":str(archive.relative_to(ROOT)) if archive.is_relative_to(ROOT) else str(archive),
          "archive_sha256":hashlib.sha256(archive.read_bytes()).hexdigest(),
          "prior_archive_audit":prior_audit,
          "deltas":{k:v for k,v in deltas.items() if k!="triage_candidates"}}
    discovery_path=ROOT/"docs"/"expanded_discovery"/"status.json"
    try:
        discovery=json.loads(discovery_path.read_text(encoding="utf8")) if discovery_path.exists() else None
    except (OSError,ValueError):discovery=None
    combined=integrated_quality(meta,discovery,capture_at)
    meta["integrated_quality_report"]=combined
    meta["stage1_9_of_10_verified"]=combined["certified_9_out_of_10"]
    def write_json(path,value):
        path.write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n",encoding="utf8")
    write_json(out/"integrated_quality_report.json",combined)
    write_json(out/"identity_audit.json",meta["identity_mapping"])
    write_json(out/"delta_candidates.json",{
        "schema_version":"evidence-delta-candidates-v1",
        "capture_utc":meta["capture_utc"],
        "prior_archive_audit":prior_audit,
        **deltas})
    history_path=out/"daily_metrics.json"
    try: history=json.loads(history_path.read_text()) if history_path.exists() else {"runs":[]}
    except (OSError,ValueError):history={"runs":[]}
    runs=[x for x in history.get("runs",[]) if x.get("capture_utc")!=meta["capture_utc"]]
    runs.append({"capture_utc":meta["capture_utc"],"records":meta["records"],
                 "successful_sources":meta["successful_sources"],
                 "anchored_cmc_ids":meta["verified_cmc_id_matches"],
                 "novel_first_seen_items":deltas["first_seen_observations"],
                 "changed_metric_candidates":deltas.get("triage_count",0),
                 "quality_score":combined["diagnostic_score_out_of_10"],
                 "nine_of_ten_certified":combined["certified_9_out_of_10"]})
    write_json(history_path,{"schema_version":"evidence-engine-daily-v1",
            "runs":sorted(runs,key=lambda x:x["capture_utc"])[-120:]})
    write_json(out/"status.json",meta)
    # Stratify quick-read preview, so derivatives never disappear behind TVL.
    groups=defaultdict(list)
    for rec in result["observations"]:groups[rec["source"]].append(rec)
    preview=[]
    keys=sorted(groups)
    while keys and len(preview)<500:
        remaining=[]
        for key in keys:
            if groups[key]:
                preview.append(groups[key].pop(0))
                if groups[key]:remaining.append(key)
                if len(preview)>=500:break
        keys=remaining
    write_json(out/"latest.json",{
        "capture_utc":meta["capture_utc"],"source_audit":meta["source_audit"],
        "preview_note":"STRATIFIED_FIRST_500_NOT_COMPLETE_ARCHIVE",
        "observations":preview})
    return meta

def main():
    market=json.loads(MARKET.read_text())
    result=capture(market)
    status=save(result)
    print(json.dumps({"capture_utc":status["capture_utc"],
                      "sources_ok":status["successful_sources"],
                      "records":status["records"],"audit":status["source_audit"],
                      "archive":status["archive_path"]},indent=2))
if __name__=="__main__":main()
