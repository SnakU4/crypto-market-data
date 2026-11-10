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
    {"key":"btc_recent_transactions","family":"DIRECT_WALLET_ACTIVITY_SAMPLE",
     "url":"https://mempool.space/api/mempool/recent","max_bytes":200_000},
    {"key":"ethereum_recent_transactions","family":"DIRECT_WALLET_ACTIVITY_SAMPLE",
     "url":"https://eth.blockscout.com/api/v2/transactions","max_bytes":1_500_000},
    {"key":"patternplus_unlocks","family":"TOKEN_UNLOCK_SCHEDULE_CANDIDATE",
     "url":"https://pattern.plus/api/v1/unlocks.json","max_bytes":5_000_000},
    {"key":"patternplus_calendar","family":"EXTERNAL_EVENT_CALENDAR",
     "url":"https://pattern.plus/api/v1/calendar.json","max_bytes":5_000_000},
    {"key":"defillama_dex_volume","family":"DEFI_PROTOCOL_ACTIVITY",
     "url":"https://api.llama.fi/overview/dexs?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true","max_bytes":5_000_000},
    {"key":"defillama_fees","family":"DEFI_PROTOCOL_ACTIVITY",
     "url":"https://api.llama.fi/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true","max_bytes":5_000_000},
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

def parse_btc_recent_transactions(raw,now):
    if not isinstance(raw,list):raise ValueError("BITCOIN_TX_INVALID")
    rows=[]
    for item in raw[:25]:
        if not isinstance(item,dict):continue
        ident=item.get("txid")
        if not isinstance(ident,str) or not re.fullmatch(r"[0-9a-fA-F]{64}",ident):continue
        m={}
        for key in ("fee","vsize","value"):
            value=num(item.get(key))
            if value is not None and value>=0:m[key]=value
        rows.append(row("btc_recent_transactions",ident.lower(),
                        "Bitcoin mempool transaction "+ident[:16],m,now,
                        {"chain":"bitcoin","level":"network_transaction",
                         "confirmation_status":"UNCONFIRMED_WHEN_LISTED",
                         "first_public_utc":"UNKNOWN",
                         "observed_from":"MEMPOOL_RECENT_SAMPLE_NOT_CMC100_WALLET_FLOW"}))
    return rows


def parse_ethereum_transactions(raw,now):
    data=raw.get("items") if isinstance(raw,dict) else None
    if not isinstance(data,list):raise ValueError("ETHEREUM_TX_INVALID")
    rows=[]
    for item in data[:40]:
        if not isinstance(item,dict):continue
        ident=item.get("hash")
        if not isinstance(ident,str) or not re.fullmatch(r"0x[0-9a-fA-F]{64}",ident):continue
        m={}
        value=num(item.get("value"))
        if value is not None and value>=0:m["value_wei"]=value
        fee=item.get("fee",{})
        if isinstance(fee,dict):
            value=num(fee.get("value"))
            if value is not None and value>=0:m["fee_wei"]=value
        rows.append(row("ethereum_recent_transactions",ident.lower(),
                        "Ethereum transaction "+ident[:18],m,now,
                        {"chain":"ethereum","level":"network_transaction",
                         "block_number":item.get("block"),
                         "block_timestamp_utc":item.get("timestamp"),
                         "transaction_status":item.get("status"),
                         "time_semantics_warning":"BLOCK_TIMESTAMP_NOT_FIRST_DISCOVERY",
                         "observed_from":"GENERAL_TRANSACTION_SAMPLE_NOT_CMC100_TOKEN_FLOW"}))
    return rows


def extract_calendar_list(raw):
    if isinstance(raw,list):return raw
    if isinstance(raw,dict):
        for field in ("unlocks","events","items","calendar","data","rows","schedule"):
            field_value=raw.get(field)
            if isinstance(field_value,list):return field_value
            if isinstance(field_value,dict):
                for nested in ("unlocks","events","items","rows"):
                    if isinstance(field_value.get(nested),list):return field_value[nested]
    raise ValueError("EVENT_CALENDAR_STRUCTURE_UNRECOGNIZED")


def schedule_date(raw_value):
    """Only source-stated calendar day; do not create fictional publication time."""
    import datetime as dt
    if isinstance(raw_value,(int,float)):
        try:return dt.datetime.fromtimestamp(float(raw_value)/(1000 if raw_value>1e11 else 1),dt.timezone.utc).date().isoformat()
        except (ValueError,OverflowError):return None
    if not isinstance(raw_value,str):return None
    value=raw_value.strip()
    try:return dt.date.fromisoformat(value[:10]).isoformat()
    except ValueError:return None


def parse_patternplus_unlocks(raw,now):
    items=extract_calendar_list(raw)
    out=[]
    for entry in items[:3000]:
        if not isinstance(entry,dict):continue
        day=next((schedule_date(entry.get(key)) for key in
                  ("date","unlock_date","unlockDate","unlockAt","unlock_at","timestamp","day")
                  if schedule_date(entry.get(key))),None)
        if not day:continue
        project=entry.get("coin") or entry.get("project") or entry.get("token") or entry.get("asset") or entry.get("slug")
        if isinstance(project,dict):project=project.get("slug") or project.get("name") or project.get("symbol")
        project=str(project or entry.get("symbol") or "").strip()
        if not project:continue
        allocation=entry.get("categories") or entry.get("types") or entry.get("allocation") or ""
        if isinstance(allocation,(dict,list)):
            allocation=repr(allocation)[:100]
        identifier=project+"|"+day+"|"+str(entry.get("type") or entry.get("kind") or "unlock")+"|"+str(allocation)[:100]
        if len(identifier)>300:continue
        fields={}
        for name in ("tokens","amount","unlockTokens","unlockAmount","tokens_unlocked",
                     "percent_of_circulating","pctCirculating","unlockPercentOfCirculating",
                     "unlockUsd","value_usd","pct_circulating","pct_total"):
            n=num(entry.get(name))
            if n is not None:fields["reported_"+name]=n
        out.append(row("patternplus_unlocks",identifier,"Published unlock schedule candidate "+project+" "+day,
                       fields,now,{"project_label":project,"scheduled_date_utc":day,
                                   "source_project_name":str(entry.get("name") or "")[:120],
                                   "source_symbol":str(entry.get("symbol") or "")[:40],
                                   "source_basis":str(entry.get("basis") or "")[:100],
                                   "source_file_reference":str(entry.get("file") or "")[:240],
                                   "source_categories":str(entry.get("categories") or "")[:180],
                                   "source_types":str(entry.get("types") or "")[:180],
                                   "schedule_source":"https://pattern.plus/api/v1/unlocks.json",
                                   "provider_attribution":"Data: PatternPlus (pattern.plus); CC BY 4.0",
                                   "verification":"AGGREGATED_THIRD_PARTY_UNCORROBORATED",
                                   "source_row_keys":sorted(str(x) for x in entry.keys())[:40],
                                   "time_semantics_warning":"SCHEDULED_DAY_NOT_PUBLICATION_TIMESTAMP"}))
    return out


def parse_patternplus_calendar(raw,now):
    items=extract_calendar_list(raw)
    out=[]
    for item in items[:2000]:
        if not isinstance(item,dict):continue
        date=next((schedule_date(item.get(key)) for key in
                   ("date","event_date","eventDate","scheduledAt","timestamp","day")
                   if schedule_date(item.get(key))),None)
        if not date:continue
        title=str(item.get("title") or item.get("name") or item.get("event") or "").strip()
        if not title:continue
        category=str(item.get("category") or item.get("type") or "UNCLASSIFIED")[:80]
        key=category+"|"+date+"|"+title[:160]
        out.append(row("patternplus_calendar",key,"Scheduled event "+title,{},now,
                       {"scheduled_date_utc":date,"category":category,
                        "provider_attribution":"Data: PatternPlus (pattern.plus); CC BY 4.0",
                        "verification":"AGGREGATED_THIRD_PARTY_UNCORROBORATED",
                        "time_semantics_warning":"SCHEDULED_DAY_NOT_ACTUAL_OCCURRENCE"}))
    return out


def protocol_activity_rows(raw,now,source):
    if not isinstance(raw,dict) or not isinstance(raw.get("protocols"),list):
        raise ValueError("DEFILLAMA_ACTIVITY_SCHEMA_INVALID")
    candidates=[]
    for protocol in raw["protocols"]:
        if not isinstance(protocol,dict):continue
        key=str(protocol.get("defillamaId") or protocol.get("module") or protocol.get("id") or protocol.get("name") or "")
        if not key or len(key)>180:continue
        metrics={}
        for orig in ("total24h","total48hto24h","total7d","total30d","change_1d",
                     "change_7d","change_1m"):
            val=num(protocol.get(orig))
            if val is not None:metrics[orig]=val
        if "total24h" not in metrics:continue
        candidates.append((metrics["total24h"],key,protocol,metrics))
    candidates.sort(reverse=True,key=lambda x:x[0])
    result=[]
    for _,key,protocol,metrics in candidates[:200]:
        result.append(row(source,key,
               ("DeFi DEX volume " if source=="defillama_dex_volume" else "DeFi fees ")+str(protocol.get("name") or key),
               metrics,now,{"name":str(protocol.get("name") or "")[:120],
                            "defillama_protocol_id":str(protocol.get("defillamaId") or ""),
                            "gecko_id":str(protocol.get("gecko_id") or ""),
                            "category":str(protocol.get("category") or ""),
                            "chains":(protocol.get("chains") or [])[:10],
                            "methodology_warning":"PROVIDER_AGGREGATE_NOT_DIRECT_CONTRACT_EVENT"}))
    return result


def parse_defillama_dex_volume(raw,now):return protocol_activity_rows(raw,now,"defillama_dex_volume")
def parse_defillama_fees(raw,now):return protocol_activity_rows(raw,now,"defillama_fees")


EXTRA_PARSERS={
    "okx_swap_tickers":parse_okx_tickers,
    "okx_swap_open_interest":parse_okx_open_interest,
    "coingecko_supply":parse_coingecko_supply,
    "btc_mempool":parse_bitcoin_mempool,
    "btc_fee_estimates":parse_bitcoin_fees,
    "ethereum_blockscout_stats":parse_ethereum_stats,
    "geckoterminal_trending_pools":parse_geckoterminal_pools,
    "btc_recent_transactions":parse_btc_recent_transactions,
    "ethereum_recent_transactions":parse_ethereum_transactions,
    "patternplus_unlocks":parse_patternplus_unlocks,
    "patternplus_calendar":parse_patternplus_calendar,
    "defillama_dex_volume":parse_defillama_dex_volume,
    "defillama_fees":parse_defillama_fees,
}
