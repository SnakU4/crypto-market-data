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
    {"key":"bybit_linear_tickers","family":"DERIVATIVES_MARKET",
     "url":"https://api.bybit.com/v5/market/tickers?category=linear","max_bytes":5_000_000},
    {"key":"bybit_instruments","family":"DERIVATIVES_INSTRUMENTS",
     "url":"https://api.bybit.com/v5/market/instruments-info?category=linear&limit=1000","max_bytes":5_000_000},
)


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
        circ=v.get("totalCirculating")
        value=number(circ.get("peggedUSD")) if isinstance(circ,dict) else number(circ)
        if value is None or value<0:continue
        name=str(v["name"])[:120]
        rows.append(observation("defillama_stablecoinchains",name,
                                "Stablecoin circulation "+name,{"circulating_usd":value},now))
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

PARSERS={"defillama_chains":parse_chains,
         "defillama_stablecoins":parse_stablecoins,
         "bybit_linear_tickers":parse_bybit_tickers,
         "bybit_instruments":parse_bybit_instruments}

def capture(market,fetcher=get_json,now=None,sources=SOURCES):
    now=now or dt.datetime.now(UTC)
    assets=market.get("assets") or []
    if len(assets)!=100 or len({int(a["cmc_id"]) for a in assets})!=100 or market.get("index",{}).get("verified_constituents")!=100:
        raise ValueError("OFFICIAL_CMC100_UNIVERSE_REQUIRED")
    observed=[];audit=[]
    for spec in sources:
        try:
            payload=fetcher(spec["url"],spec["max_bytes"])
            rows=PARSERS[spec["key"]](payload,now)
            observed.extend(rows)
            audit.append({"source":spec["key"],"family":spec["family"],"status":"OK",
                          "records":len(rows),"error":None,"url":spec["url"]})
        except (OSError,ValueError,TypeError,KeyError,urllib.error.URLError) as ex:
            audit.append({"source":spec["key"],"family":spec["family"],"status":"ERROR",
                          "records":0,"error":type(ex).__name__+": "+str(ex)[:180],
                          "url":spec["url"]})
    # instrument catalog is metadata, not an extra signal: record duplication
    # across sources is intentional, but no name/ticker-to-CMC matching.
    count_by_family={}
    for row in observed:
        a=next((x for x in sources if x["key"]==row["source"]),None)
        if a:count_by_family[a["family"]]=count_by_family.get(a["family"],0)+1
        elif row["source"]=="defillama_stablecoinchains":
            count_by_family["STABLECOIN_SUPPLY"]=count_by_family.get("STABLECOIN_SUPPLY",0)+1
    metrics={"schema_version":"crypto-evidence-engine-v1",
             "capture_utc":iso(now),"official_cmc100_count":100,
             "configured_sources":len(sources),"successful_sources":sum(x["status"]=="OK" for x in audit),
             "records":len(observed),"records_by_family":count_by_family,
             "source_audit":audit,
             "verified_cmc_id_matches":0,
             "verification_status":"UNCORROBORATED_LIVE_MARKET_OBSERVATIONS",
             "stage1_9_of_10_verified":False,
             "limitations":["NOT_CMC100_COIN_MATCHED","NO_HISTORICAL_PUBLICATION_TIME_FOR_SNAPSHOTS",
                            "NO_DIRECT_TOKEN_UNLOCKS","NO_WALLET_TRANSFERS_OR_CONTRACT_EVENT_INDEX",
                            "MARKET_DATA_MAY_NOT_BE_ACCESSIBLE_FROM_GITHUB_RUNNER"]}
    return {"metrics":metrics,"observations":observed}

def save(result,out=OUT):
    out.mkdir(parents=True,exist_ok=True)
    stamp=result["metrics"]["capture_utc"].replace(":","").replace("-","")
    folder=out/"archive"/stamp[:8]
    folder.mkdir(parents=True,exist_ok=True)
    archive=folder/(stamp+"_observations.jsonl.gz")
    if archive.exists():raise FileExistsError("IMMUTABLE_SNAPSHOT_ALREADY_EXISTS")
    with archive.open("wb") as target:
        with gzip.GzipFile(filename="",mode="wb",fileobj=target,mtime=0,compresslevel=6) as gz:
            for row in result["observations"]:
                gz.write((json.dumps(row,ensure_ascii=False,separators=(",",":"))+"\n").encode())
    meta={**result["metrics"],"archive_path":str(archive.relative_to(ROOT)) if archive.is_relative_to(ROOT) else str(archive),
          "archive_sha256":hashlib.sha256(archive.read_bytes()).hexdigest()}
    (out/"status.json").write_text(json.dumps(meta,indent=2,sort_keys=True)+"\n")
    # Small accessible preview, full immutable archive never silently capped.
    (out/"latest.json").write_text(json.dumps({
        "capture_utc":meta["capture_utc"],"source_audit":meta["source_audit"],
        "observations":result["observations"][:500]},ensure_ascii=False,separators=(",",":"))+"\n")
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
