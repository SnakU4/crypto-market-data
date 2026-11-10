"""Additional public, structured evidence streams.

All data below are observation-time snapshots, not historical announcement times.
Providers and asset links remain explicit; network-level metrics are not token
transfers. Parsers are pure and tested without network access.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import math
import re

EXTRA_SOURCES = (
    {"key":"okx_swap_tickers","family":"DERIVATIVES_MARKET",
     "url":"https://www.okx.com/api/v5/market/tickers?instType=SWAP","max_bytes":6_000_000},
    {"key":"okx_swap_open_interest","family":"DERIVATIVES_OI",
     "url":"https://www.okx.com/api/v5/public/open-interest?instType=SWAP","max_bytes":6_000_000},
    {"key":"coingecko_supply","family":"TOKENOMICS_SUPPLY_PROXY",
     "url":"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page=1&sparkline=false","max_bytes":5_000_000},
    {"key":"btc_mempool","family":"DIRECT_ONCHAIN_NETWORK",
     "url":"https://mempool.space/api/mempool","max_bytes":150_000},
    {"key":"btc_fee_estimates","family":"DIRECT_ONCHAIN_NETWORK",
     "url":"https://mempool.space/api/v1/fees/recommended","max_bytes":150_000},
    {"key":"ethereum_blockscout_stats","family":"DIRECT_ONCHAIN_NETWORK",
     "url":"https://eth.blockscout.com/api/v2/stats","max_bytes":350_000},
    {"key":"geckoterminal_trending_pools","family":"DEX_ONCHAIN_MARKET",
     "url":"https://api.geckoterminal.com/api/v2/networks/trending_pools?page=1","max_bytes":2_000_000},
)

def num(x):
    try:
        if isinstance(x, str) and re.fullmatch(r"[-+]?\d{1,3}(,\d{3})+(?:\.\d+)?",x.strip()):
            x=x.replace(",","")
        value=float(x)
        return value if math.isfinite(value) else None
    except (TypeError,ValueError,OverflowError):
        return None

def row(source,key,title,metrics,now,attrs=None):
    return {
        "observation_id":hashlib.sha256((source+":"+key).encode("utf-8")).hexdigest()[:24],
        "source":source,"source_item_id":key,"title":title[:200],
        "metrics":metrics,"attributes":attrs or {},
        "observed_utc":now.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z"),
        "published_utc":None,"time_semantics":"LIVE_SNAPSHOT_NOT_HISTORICAL_PUBLICATION",
        "coin_identity_status":"NOT_VERIFIED","prediction_or_price_direction":"NOT_ASSESSED",
    }

def okx_rows(payload,now,source):
    if not isinstance(payload,dict) or str(payload.get("code"))!="0" or not isinstance(payload.get("data"),list):
        raise ValueError("OKX_RESPONSE_INVALID")
    out=[]
    for x in payload["data"]:
        if not isinstance(x,dict):continue
        inst=x.get("instId")
        if not isinstance(inst,str) or not re.fullmatch(r"[A-Z0-9-]{3,80}-SWAP",inst):
            continue
        fields=(("open_interest_contracts","oi"),("open_interest_base","oiCcy"),("open_interest_usd","oiUsd"),
                ("last_price","last"),("mark_price","markPx"),("volume_24h_contracts","vol24h"),
                ("volume_24h_quote","volCcy24h"))
        metrics={}
        for name,orig in fields:
            val=num(x.get(orig))
            if val is not None:metrics[name]=val
        if not metrics:continue
        ts=x.get("ts")
        try:timestamp=int(ts) if ts is not None else None
        except (ValueError,TypeError):timestamp=None
        if timestamp and (timestamp/1000>now.timestamp()+120 or timestamp/1000<now.timestamp()-86400):
            continue
        attrs={"exchange":"OKX","instrument_id":inst,"market_timestamp_ms":timestamp,
               "instrument_family":x.get("instType")}
        out.append(row(source,inst,"OKX swap "+inst,metrics,now,attrs))
    return out

def parse_okx_tickers(raw,now):return okx_rows(raw,now,"okx_swap_tickers")
def parse_okx_open_interest(raw,now):return okx_rows(raw,now,"okx_swap_open_interest")

def parse_coingecko_supply(raw,now):
    if not isinstance(raw,list):raise ValueError("COINGECKO_MARKET_INVALID")
    out=[]
    for x in raw[:250]:
        if not isinstance(x,dict):continue
        ident=x.get("id")
        name=x.get("name")
        symbol=x.get("symbol")
        if not isinstance(ident,str) or not re.fullmatch(r"[a-zA-Z0-9_-]{2,120}",ident):
            continue
        metrics={}
        for field in ("circulating_supply","total_supply","max_supply","market_cap","total_volume","current_price"):
            v=num(x.get(field))
            if v is not None and v>=0:metrics[field]=v
        if not metrics:continue
        out.append(row("coingecko_supply",ident,"Supply data "+str(name or ident),metrics,now,
                       {"coingecko_id":ident,"name":name,"symbol":symbol,
                        "source_last_updated":x.get("last_updated")}))
    return out

def parse_bitcoin_mempool(raw,now):
    if not isinstance(raw,dict):raise ValueError("MEMPOOL_INVALID")
    metrics={}
    for key in ("count","vsize","total_fee"):
        value=num(raw.get(key))
        if value is not None and value>=0:metrics[key]=value
    if "count" not in metrics:raise ValueError("MEMPOOL_MISSING_COUNT")
    return [row("btc_mempool","bitcoin-mainnet","Bitcoin mempool state",metrics,now,
                {"chain":"bitcoin","level":"network","token_event":False})]

def parse_bitcoin_fees(raw,now):
    if not isinstance(raw,dict):raise ValueError("FEES_INVALID")
    metrics={}
    for key in ("fastestFee","halfHourFee","hourFee","economyFee","minimumFee"):
        value=num(raw.get(key))
        if value is not None and value>=0:metrics[key+"_sat_vbyte"]=value
    if not metrics:raise ValueError("FEES_NO_VALUES")
    return [row("btc_fee_estimates","bitcoin-mainnet","Bitcoin recommended transaction fees",
                metrics,now,{"chain":"bitcoin","level":"network","token_event":False})]

def parse_ethereum_stats(raw,now):
    if not isinstance(raw,dict):raise ValueError("BLOCKSCOUT_INVALID")
    metrics={}
    for key in ("total_transactions","total_addresses","average_block_time","gas_used_today",
                "network_utilization_percentage","total_blocks"):
        value=num(raw.get(key))
        if value is not None and value>=0:metrics[key]=value
    if not metrics:raise ValueError("BLOCKSCOUT_NO_VALUES")
    return [row("ethereum_blockscout_stats","ethereum-mainnet","Ethereum network statistics",
                metrics,now,{"chain":"ethereum","level":"network","token_event":False})]

def parse_geckoterminal_pools(raw,now):
    if not isinstance(raw,dict) or not isinstance(raw.get("data"),list):
        raise ValueError("GECKOTERMINAL_INVALID")
    out=[]
    for entry in raw["data"][:40]:
        if not isinstance(entry,dict):continue
        key=str(entry.get("id") or "")
        if len(key)>160 or not re.fullmatch(r"[a-zA-Z0-9_:-]+",key):continue
        attrs=entry.get("attributes") or {}
        if not isinstance(attrs,dict):continue
        metrics={}
        for f in ("reserve_in_usd","base_token_price_usd","quote_token_price_usd",
                  "base_token_price_quote_token","fdv_usd","market_cap_usd"):
            v=num(attrs.get(f))
            if v is not None and v>=0:metrics[f]=v
        vol=attrs.get("volume_usd")
        if isinstance(vol,dict):
            v=num(vol.get("h24"))
            if v is not None:metrics["volume_usd_h24"]=v
        if not metrics:continue
        out.append(row("geckoterminal_trending_pools",key,"DEX trending pool "+str(attrs.get("name") or key),
                       metrics,now,{"pool_id":key,"pool_address":attrs.get("address"),
                                    "network_id":key.split("_")[0],"level":"dex_pool",
                                    "token_contract_not_verified":True}))
    return out

EXTRA_PARSERS={
    "okx_swap_tickers":parse_okx_tickers,
    "okx_swap_open_interest":parse_okx_open_interest,
    "coingecko_supply":parse_coingecko_supply,
    "btc_mempool":parse_bitcoin_mempool,
    "btc_fee_estimates":parse_bitcoin_fees,
    "ethereum_blockscout_stats":parse_ethereum_stats,
    "geckoterminal_trending_pools":parse_geckoterminal_pools,
}
