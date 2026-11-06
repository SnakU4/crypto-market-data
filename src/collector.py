#!/usr/bin/env python3
"""Free CMC100 + public market-data collector. Standard library only.

Never claims completeness on API failure, never replaces official index with a top-N list,
never invents missing market data, never calls a paid API or an LLM.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import csv
import datetime as dt
import hashlib
import html
import io
import json
import math
import os
import pathlib
import random
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

UTC=dt.timezone.utc
CMC_BASE="https://pro-api.coinmarketcap.com/public-api"
FAPI_BASE="https://fapi.binance.com"
BYBIT_BASE="https://api.bybit.com"
OKX_BASE="https://www.okx.com"
COINGECKO_GLOBAL="https://api.coingecko.com/api/v3/global"
DEFILLAMA_CHAINS="https://api.llama.fi/v2/chains"
USER_AGENT="CMC100-Forward-Forecast-Research/0.4 (public endpoints; contact via GitHub repository)"
ROOT=pathlib.Path(__file__).resolve().parents[1]
DOCS=ROOT/"docs"


def iso_now():
    return dt.datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00","Z")


def timestamp_to_iso(t):
    if not isinstance(t,(int,float)) or not math.isfinite(t): return None
    return dt.datetime.fromtimestamp(t/1000 if t>1e11 else t, UTC).isoformat(timespec="milliseconds").replace("+00:00","Z")


def utc_parse(s):
    if not s or not isinstance(s,str): return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(UTC)
    except Exception: return None


def safe_float(value):
    if value is None or isinstance(value,bool): return None
    try:
        x=float(value)
        return x if math.isfinite(x) else None
    except (TypeError,ValueError,OverflowError): return None


def round_safe(value, n=7):
    x=safe_float(value)
    return round(x,n) if x is not None else None


def num_pct_delta(end,start):
    a,b=safe_float(end),safe_float(start)
    return round_safe(100*(a/b-1),6) if a is not None and b not in (None,0) else None


def require_cmc_api_success(payload, label):
    """CMC keyless JSON may return error_code 0 (integer) or '0' (string)."""
    if not isinstance(payload, dict):
        raise ValueError(f"{label}: API response is not a JSON object")
    status = payload.get("status") or {}
    if not isinstance(status, dict):
        raise ValueError(f"{label}: API status is not a JSON object")
    code = status.get("error_code", 0)
    if code not in (0, "0", None):
        message = status.get("error_message") or status.get("notice") or "no error detail provided"
        raise ValueError(f"{label}: error_code={code!r}; error_message={str(message)[:350]}")


def normalize_index(payload):
    """Only official CMC100 constituent response. Full 100 unique IDs required."""
    require_cmc_api_success(payload, "CMC100")
    root=payload.get("data")
    if not isinstance(root,dict) or not isinstance(root.get("constituents"),list):
        raise ValueError("CMC100 response lacks data.constituents[]")
    rows=[]
    for obj in root["constituents"]:
        if not isinstance(obj,dict): continue
        ident=obj.get("id"); name=obj.get("name"); sym=obj.get("symbol")
        if not isinstance(ident,int) or ident<=0 or not isinstance(name,str) or not name.strip() or not isinstance(sym,str) or not sym.strip():
            raise ValueError("CMC100 constituent has an invalid ID/name/symbol")
        rows.append({"cmc_id":ident,"symbol":sym.strip(),"name":name.strip(),"weight":round_safe(obj.get("weight"),10)})
    ids=[c["cmc_id"] for c in rows]
    if len(rows)!=100 or len(set(ids))!=100:
        raise ValueError(f"CMC100 full-universe gate rejected: {len(rows)} entries, {len(set(ids))} unique CMC IDs")
    updated=root.get("last_update")
    return sorted(rows,key=lambda r:r["cmc_id"]),updated


def normalize_quotes(payload):
    """Official CMC v3 quotes/latest: data[] with quote[]; keyed by unique CMC ID."""
    require_cmc_api_success(payload, "CMC quotes")
    data=payload.get("data")
    if isinstance(data,dict): data=list(data.values())
    if not isinstance(data,list): raise ValueError("CMC quotes/latest data expected list")
    output={}
    for item in data:
        if not isinstance(item,dict): continue
        ident=item.get("id")
        try: ident=int(ident)
        except (ValueError,TypeError): continue
        quotes=item.get("quote")
        if isinstance(quotes,dict):
            usd=quotes.get("USD") or next((x for x in quotes.values() if isinstance(x,dict) and x.get("symbol")=="USD"),None)
        else:
            usd=next((x for x in quotes or [] if isinstance(x,dict) and x.get("symbol")=="USD"),None)
        usd=usd or {}
        output[ident]={
            "price_usd":round_safe(usd.get("price")),
            "ret_1h_pct":round_safe(usd.get("percent_change_1h")),
            "ret_24h_pct":round_safe(usd.get("percent_change_24h")),
            "ret_7d_pct":round_safe(usd.get("percent_change_7d")),
            "volume_24h_usd":round_safe(usd.get("volume_24h"),2),
            "volume_change_24h_pct":round_safe(usd.get("volume_change_24h")),
            "quote_last_updated_utc":usd.get("last_updated") or item.get("last_updated"),
            "market_cap_usd":round_safe(usd.get("market_cap"),2),
        }
    return output


def normalize_exchange_info(payload):
    """Only TRADING USD-margined perpetuals; exact symbol mapping only."""
    syms={}
    if not isinstance(payload,dict): return syms
    for item in payload.get("symbols",[]):
        if not isinstance(item,dict): continue
        if item.get("contractType")!="PERPETUAL" or item.get("status")!="TRADING": continue
        if item.get("quoteAsset") not in ("USDT","USDC"): continue
        base=item.get("baseAsset"); sym=item.get("symbol")
        if not base or not sym: continue
        syms.setdefault(base.upper(),[]).append(item)
    return syms


def map_perp(coin, by_base):
    symbol=coin["symbol"].upper()
    exact=by_base.get(symbol,[])
    exact.sort(key=lambda x:0 if x.get("quoteAsset")=="USDT" else 1)
    if exact:
        item=exact[0]
        return {"symbol":item["symbol"],"base_asset":item["baseAsset"],"quote_asset":item["quoteAsset"],"mapping":"EXACT_BASE_ASSET","exchange":"BINANCE","contract_type":"PERPETUAL","trading_status":"TRADING"}
    # 1000PEPEUSDT is not an exact base-asset match to PEPE. Make visible but DO NOT treat as verified mapping.
    prefix=by_base.get("1000"+symbol,[])
    return {"symbol":None,"mapping":"NOT_MATCHED_OR_REQUIRES_MANUAL_REVIEW","review_candidates":[x.get("symbol") for x in prefix[:3]],"trading_status":"UNKNOWN"}


def compute_kline_features(klines, captured_at):
    """Closed bars only: no lookahead from a partially formed final bar."""
    end=utc_parse(captured_at)
    if end is None: return {}
    cleaned=[]
    for x in klines if isinstance(klines,list) else []:
        try:
            close_ms=int(x[6]); price=safe_float(x[4]); qvol=safe_float(x[7]); taker_q=safe_float(x[10]);
            if price is None or price<=0 or qvol is None or qvol<0: continue
            if dt.datetime.fromtimestamp(close_ms/1000,UTC)>end:continue
            cleaned.append((close_ms,price,qvol,taker_q))
        except (IndexError,TypeError,ValueError,OverflowError):continue
    cleaned.sort(key=lambda z:z[0])
    if not cleaned:return {}
    close=cleaned[-1][1]
    by_time={x[0]:x for x in cleaned}
    end_ms=cleaned[-1][0]
    def ret(h):
        past=by_time.get(end_ms-h*3_600_000)
        return num_pct_delta(close,past[1]) if past else None
    last24=[by_time.get(end_ms-i*3_600_000) for i in range(23,-1,-1)]
    if any(x is None for x in last24):last24=[]
    prev24=[by_time.get(end_ms-i*3_600_000) for i in range(47,23,-1)]
    if any(x is None for x in prev24):prev24=[]
    v24=sum(x[2] for x in last24) if len(last24)==24 else None
    vol_ratio=round_safe(v24/sum(x[2] for x in prev24),4) if v24 is not None and prev24 and sum(x[2] for x in prev24)>0 else None
    taker=sum(x[3] for x in last24) if last24 and all(x[3] is not None for x in last24) else None
    imbalance=round_safe(2*taker/v24-1,6) if taker is not None and v24 else None
    returns=[math.log(last24[i][1]/last24[i-1][1]) for i in range(1,len(last24))]
    rv=round_safe(statistics.stdev(returns)*math.sqrt(24)*100,5) if len(returns)>=12 else None
    return {"kline_last_close_utc":timestamp_to_iso(cleaned[-1][0]),"perp_ret_1h_pct":ret(1),"perp_ret_6h_pct":ret(6),"perp_ret_24h_pct":ret(24),"perp_ret_7d_pct":ret(168),"perp_closed_24h_quote_volume":round_safe(v24,2),"perp_volume_ratio_24h_vs_prior24h":vol_ratio,"perp_taker_imbalance_24h":imbalance,"perp_realized_volatility_24h_pct":rv,"bars_available":len(cleaned)}


def compute_oi_features(history, captured_at):
    end=utc_parse(captured_at)
    good=[]
    for x in history if isinstance(history,list) else []:
        if not isinstance(x,dict):continue
        t=x.get("timestamp");val=safe_float(x.get("sumOpenInterestValue"))
        if not isinstance(t,(int,float)) or val is None or val<0:continue
        observed=dt.datetime.fromtimestamp(t/1000,UTC)
        if observed<=end:good.append((observed,val))
    good.sort(key=lambda z:z[0]);
    if not good:return {}
    result={"oi_usd":round_safe(good[-1][1],2),"oi_observed_utc":good[-1][0].isoformat().replace("+00:00","Z"),"oi_change_24h_pct":None}
    historical=[(t,v) for t,v in good if t<=good[-1][0]-dt.timedelta(hours=23,minutes=30)]
    if historical and (good[-1][0]-historical[-1][0])<=dt.timedelta(hours=24,minutes=30):result["oi_change_24h_pct"]=num_pct_delta(good[-1][1],historical[-1][1])
    return result


class Client:
    def __init__(self): self.calls=[]
    def fetch(self,url,params=None,required=False):
        args=urllib.parse.urlencode(params or {})
        full=url+("?"+args if args else "")
        err=None
        for i in range(3):
            t=iso_now()
            try:
                req=urllib.request.Request(full,headers={"User-Agent":USER_AGENT,"Accept":"application/json"})
                with urllib.request.urlopen(req,timeout=18) as response:
                    # defensive memory bound: no huge payloads from out-of-scope endpoints
                    data=response.read(15_000_001)
                    if len(data)>15_000_000:raise ValueError("response over 15 MB")
                parsed=json.loads(data)
                cmc_status=parsed.get("status") if isinstance(parsed,dict) else None
                cmc_code=cmc_status.get("error_code") if isinstance(cmc_status,dict) else None
                call_log={"url":full,"request_started_utc":t,"received_at_utc":iso_now(),"status":"OK"}
                if cmc_code is not None:
                    call_log["api_error_code"]=cmc_code
                    if cmc_code not in (0,"0"):
                        call_log["status"]="API_ERROR"
                        call_log["api_error_message"]=str(cmc_status.get("error_message") or "")[:250]
                self.calls.append(call_log)
                return parsed
            except urllib.error.HTTPError as exc:
                err=f"HTTP {exc.code}"
                if exc.code not in (429,500,502,503,504):break
            except Exception as exc:
                err=f"{type(exc).__name__}: {str(exc)[:120]}"
            if i<2:time.sleep(1.5*(i+1))
        self.calls.append({"url":full,"received_at_utc":iso_now(),"status":"ERROR","error":err})
        if required:raise RuntimeError(f"Required source failed: {full}: {err}")
        return None


def api_success(payload, provider):
    """Reject provider-level errors even when the HTTP request returned 200."""
    if not isinstance(payload,dict): return False
    if provider=="BYBIT":return payload.get("retCode") in (0,"0") and isinstance(payload.get("result"),dict)
    if provider=="OKX":return payload.get("code") in (0,"0") and isinstance(payload.get("data"),list)
    return False


def bybit_instruments(client):
    """Public USDT linear perpetual contracts; cursor pagination is mandatory."""
    out={};cursor=None;seen=set()
    for _ in range(8):
        args={"category":"linear","limit":1000}
        if cursor:args["cursor"]=cursor
        raw=client.fetch(f"{BYBIT_BASE}/v5/market/instruments-info",args)
        if not api_success(raw,"BYBIT"):
            return {} if not out else out
        result=raw["result"]
        for v in result.get("list",[]):
            if not isinstance(v,dict):continue
            if v.get("contractType")!="LinearPerpetual" or v.get("status")!="Trading":continue
            if v.get("settleCoin")!="USDT" or v.get("quoteCoin")!="USDT":continue
            base=v.get("baseCoin");sym=v.get("symbol")
            if isinstance(base,str) and isinstance(sym,str) and sym==base+"USDT":out[base.upper()]=v
        nxt=result.get("nextPageCursor") or ""
        if not nxt or nxt in seen:break
        seen.add(nxt);cursor=nxt
    return out


def bybit_kline_features(raw,captured_at):
    """Convert closed 1-hour Bybit candles to Binance-compatible canonical format.

    Bybit returns reverse chronological records whose first timestamp is BAR START.
    Exclude unclosed bars. No taker-buy volume in this endpoint: keep it missing.
    """
    if not api_success(raw,"BYBIT"):return {}
    candles=[]
    for row in raw.get("result",{}).get("list",[]):
        try:
            st=int(row[0]); o,h,l,close=row[1:5]
            turnover=row[6]; ending=st+3600000-1
            candles.append([st,o,h,l,close,row[5],ending,turnover,None,None,None,None])
        except (ValueError,TypeError,IndexError):continue
    return compute_kline_features(candles,captured_at)


def bybit_oi_change(raw,asof):
    """Open interest history is in provider-specific units; only use ratio.

    Absolute USD value must come from the current Bybit ticker openInterestValue.
    """
    if not api_success(raw,"BYBIT"):return None
    end=utc_parse(asof)
    if end is None:return None
    points=[]
    for row in raw.get("result",{}).get("list",[]):
        try:
            t=dt.datetime.fromtimestamp(int(row["timestamp"])/1000,UTC)
            v=safe_float(row["openInterest"])
            if v is not None and v>0 and t<=end:points.append((t,v))
        except (TypeError,ValueError,KeyError,OverflowError):pass
    points.sort(key=lambda x:x[0])
    if not points:return None
    target=points[-1][0]-dt.timedelta(hours=24)
    before=[(t,v) for t,v in points if t<=target+dt.timedelta(minutes=30) and t>=target-dt.timedelta(minutes=30)]
    return num_pct_delta(points[-1][1], before[-1][1]) if before else None


def okx_instruments(client):
    raw=client.fetch(f"{OKX_BASE}/api/v5/public/instruments",{"instType":"SWAP"})
    if not api_success(raw,"OKX"):return {}
    out={}
    for x in raw["data"]:
        if not isinstance(x,dict):continue
        inst=x.get("instId");settle=x.get("settleCcy");state=x.get("state")
        if state!="live" or settle!="USDT" or not isinstance(inst,str):continue
        if not inst.endswith("-USDT-SWAP"):continue
        base=inst[:-len("-USDT-SWAP")]
        if base and base.upper()==base:out[base]=x
    return out


def okx_kline_features(raw,captured_at):
    """OKX 'confirm'=1 is complete, all other bars are excluded."""
    if not api_success(raw,"OKX"):return {}
    candles=[]
    for row in raw.get("data",[]):
        try:
            if row[8]!="1":continue
            st=int(row[0]);ending=st+3600000-1
            candles.append([st,row[1],row[2],row[3],row[4],row[5],ending,row[7],None,None,None,None])
        except (ValueError,TypeError,IndexError):continue
    return compute_kline_features(candles,captured_at)


def provider_fallback(client,assets,max_workers,limit_perps,problems):
    """Independent market-data exchanges; never represent proxy as Binance.

    Returns (provider name, count mapped) and alters assets in place. The output
    retains both exchange provenance and missing measurements explicitly.
    """
    bybit=bybit_instruments(client)
    if bybit:
        provider="BYBIT"
        raw=client.fetch(f"{BYBIT_BASE}/v5/market/tickers",{"category":"linear"})
        if not api_success(raw,"BYBIT"):
            problems.append("BYBIT_TICKERS_UNAVAILABLE")
            raw={}
        snapshot_time=timestamp_to_iso(raw.get("time")) if raw else None
        tickers={r.get("symbol"):r for r in raw.get("result",{}).get("list",[]) if isinstance(r,dict)}
        eligible=[]
        for c in assets:
            match=bybit.get(c["symbol"].upper())
            if not match:continue
            c["perpetual"]={"exchange":provider,"symbol":match["symbol"],"base_asset":match["baseCoin"],"quote_asset":"USDT","mapping":"EXACT_BASE_ASSET_BYBIT","trading_status":"Trading","contract_type":"LinearPerpetual","execution_reference":"RESEARCH_PROXY_NOT_BINANCE"}
            v=tickers.get(match["symbol"],{})
            market={"source_exchange":"BYBIT","source_type":"EXCHANGE_MARKET_DATA_PROXY","ticker_observed_utc":snapshot_time,"oi_notional_unit":"USDT_APPROX_USD"}
            if v:
                market["oi_usd"]=round_safe(v.get("openInterestValue"),2)
                if market["oi_usd"] is not None:market["oi_observed_utc"]=snapshot_time
                market["estimated_next_funding_rate_fraction"]=round_safe(v.get("fundingRate"),10)
                if market["estimated_next_funding_rate_fraction"] is not None:market["funding_quote_time_utc"]=snapshot_time
            c["perp_market"]=market
            eligible.append((c,match["symbol"]))
        if len(eligible)>limit_perps:
            problems.append(f"BYBIT_ENRICHMENT_CAPPED_{limit_perps}_OF_{len(eligible)}")
            eligible=eligible[:limit_perps]
        def work(arg):
            coin,sym=arg
            bars=client.fetch(f"{BYBIT_BASE}/v5/market/kline",{"category":"linear","symbol":sym,"interval":"60","limit":200})
            out=bybit_kline_features(bars,iso_now())
            history=client.fetch(f"{BYBIT_BASE}/v5/market/open-interest",{"category":"linear","symbol":sym,"intervalTime":"1h","limit":28})
            ch=bybit_oi_change(history,iso_now())
            if ch is not None:out["oi_change_24h_pct"]=ch
            return coin,out
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            for coin,out in pool.map(work,eligible):
                coin["perp_market"].update(out)
        return provider,len(eligible)

    problems.append("BINANCE_BLOCKED_AND_BYBIT_NOT_AVAILABLE_TRYING_OKX")
    okx=okx_instruments(client)
    if not okx:return "NONE",0
    provider="OKX"
    raw=client.fetch(f"{OKX_BASE}/api/v5/public/open-interest",{"instType":"SWAP"})
    oi={r.get("instId"):r for r in raw.get("data",[]) if isinstance(r,dict)} if api_success(raw,"OKX") else {}
    eligible=[]
    for c in assets:
        sym=c["symbol"].upper();match=okx.get(sym)
        if not match:continue
        inst=match["instId"]
        c["perpetual"]={"exchange":provider,"symbol":inst,"base_asset":sym,"quote_asset":"USDT","mapping":"EXACT_BASE_ASSET_OKX","trading_status":"live","contract_type":"SWAP","execution_reference":"RESEARCH_PROXY_NOT_BINANCE"}
        x=oi.get(inst,{})
        c["perp_market"]={"source_exchange":provider,"source_type":"EXCHANGE_MARKET_DATA_PROXY","oi_notional_unit":"USD","oi_usd":round_safe(x.get("oiUsd"),2),"oi_observed_utc":timestamp_to_iso(safe_float(x.get("ts"))) if x.get("oiUsd") is not None else None}
        eligible.append((c,inst))
    if len(eligible)>limit_perps:
        problems.append(f"OKX_ENRICHMENT_CAPPED_{limit_perps}_OF_{len(eligible)}")
        eligible=eligible[:limit_perps]
    def work(arg):
        coin,inst=arg
        bars=client.fetch(f"{OKX_BASE}/api/v5/market/history-candles",{"instId":inst,"bar":"1H","limit":200})
        out=okx_kline_features(bars,iso_now())
        funding=client.fetch(f"{OKX_BASE}/api/v5/public/funding-rate",{"instId":inst})
        if api_success(funding,"OKX") and funding["data"]:
            v=funding["data"][0];f=round_safe(v.get("fundingRate"),10)
            if f is not None:
                out["estimated_next_funding_rate_fraction"]=f
                out["funding_quote_time_utc"]=timestamp_to_iso(safe_float(v.get("ts")))
        return coin,out
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        for coin,out in pool.map(work,eligible):
            coin["perp_market"].update(out)
    return provider,len(eligible)


def collect(client,strict=True,max_workers=5,limit_perps=120):
    start=iso_now()
    problems=[]
    cmc_index=client.fetch(f"{CMC_BASE}/v3/index/cmc100-latest",required=strict)
    constituents=[];rebalance=None
    try:
        constituents,rebalance=normalize_index(cmc_index)
        index_at=utc_parse(rebalance)
        start_at=utc_parse(start)
        if index_at is None or index_at>start_at+dt.timedelta(minutes=5) or (start_at-index_at)>dt.timedelta(days=35):
            raise ValueError(f"CMC100 index last_update not safely current: {rebalance}")
        # The index is rebalanced monthly. Reject a previous-month snapshot as current after day 2.
        if start_at.day>=3 and (index_at.year,index_at.month)!=(start_at.year,start_at.month):
            raise ValueError(f"CMC100 index last_update belongs to another month: {rebalance}")
    except Exception as exc:
        problems.append(f"OFFICIAL_CMC100_UNIVERSE_UNVERIFIED: {exc}")
        if strict:raise
    cmc_quotes={}
    if constituents:
        # Chunked quote requests to avoid URL length issues and to preserve ID mapping.
        for i in range(0,len(constituents),40):
            ids=",".join(str(c["cmc_id"]) for c in constituents[i:i+40])
            obj=client.fetch(f"{CMC_BASE}/v3/cryptocurrency/quotes/latest",{"id":ids,"convert":"USD","skip_invalid":"true"})
            if obj:
                try:cmc_quotes.update(normalize_quotes(obj))
                except Exception as exc:problems.append(f"QUOTES_PARSE_ERROR: {exc}")
    exchange=client.fetch(f"{FAPI_BASE}/fapi/v1/exchangeInfo")
    by_base=normalize_exchange_info(exchange)
    premium=client.fetch(f"{FAPI_BASE}/fapi/v1/premiumIndex")
    premium_by_sym={v.get("symbol"):v for v in premium if isinstance(v,dict)} if isinstance(premium,list) else {}
    macro=client.fetch(COINGECKO_GLOBAL)
    chains=client.fetch(DEFILLAMA_CHAINS)
    chain_stats=[]
    if isinstance(chains,list):
        # This is a chain-level context source, not direct evidence of token price support.
        for x in chains:
            if isinstance(x,dict) and isinstance(x.get("name"),str):
                chain_stats.append({"name":x["name"],"tvl_usd":round_safe(x.get("tvl"),2)})
        chain_stats=sorted(chain_stats,key=lambda x:x["tvl_usd"] or 0,reverse=True)[:25]
    assets=[]
    for coin in constituents:
        mapping=map_perp(coin,by_base)
        c={"cmc_id":coin["cmc_id"],"symbol":coin["symbol"],"name":coin["name"],"cmc100_weight":coin["weight"],"cmc_quote":cmc_quotes.get(coin["cmc_id"]),"perpetual":mapping,"perp_market":None}
        if mapping.get("symbol") in premium_by_sym:
            rate=premium_by_sym[mapping["symbol"]]
            c["perp_market"]={"estimated_next_funding_rate_fraction":round_safe(rate.get("lastFundingRate"),10),"funding_quote_time_utc":timestamp_to_iso(rate.get("time"))}
        assets.append(c)
    eligible=[(c,c["perpetual"]["symbol"]) for c in assets if c["perpetual"].get("symbol")]
    if len(eligible)>limit_perps:
        problems.append(f"PERP_ENRICHMENT_CAPPED_AT_{limit_perps}_OF_{len(eligible)}")
        eligible=eligible[:limit_perps]
    def enrich(pair):
        coin,sym=pair
        # 200 hourly candles: >=7d while excluding the currently open bar.
        bars=client.fetch(f"{FAPI_BASE}/fapi/v1/klines",{"symbol":sym,"interval":"1h","limit":200})
        oi=client.fetch(f"{FAPI_BASE}/futures/data/openInterestHist",{"symbol":sym,"period":"1h","limit":28})
        out={}
        if bars:out.update(compute_kline_features(bars,iso_now()))
        if oi:out.update(compute_oi_features(oi,iso_now()))
        return coin,out
    if eligible:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures=[pool.submit(enrich,pair) for pair in eligible]
            for f in concurrent.futures.as_completed(futures):
                coin,extra=f.result()
                if extra:
                    coin["perp_market"]={**(coin["perp_market"] or {}),**extra}
    # Binance HTTP 451 can be jurisdictional. Use *independent* exchanges as
    # publicly documented research proxies, never as fabricated Binance market data.
    proxy_provider="NONE"
    if constituents and not by_base:
        try:proxy_provider,_=provider_fallback(client,assets,max_workers,limit_perps,problems)
        except Exception as exc:
            problems.append(f"ALTERNATIVE_DERIVATIVES_DATA_FAILED: {type(exc).__name__}: {str(exc)[:160]}")
    end=iso_now()
    cmc_full=len(constituents)==100
    quote_count=sum(bool(a["cmc_quote"] and a["cmc_quote"].get("price_usd") is not None) for a in assets)
    mapped=sum(bool(a["perpetual"].get("symbol")) for a in assets)
    binance_mapped=sum(bool(a["perpetual"].get("symbol") and a["perpetual"].get("exchange")=="BINANCE") for a in assets)
    bybit_mapped=sum(bool(a["perpetual"].get("symbol") and a["perpetual"].get("exchange")=="BYBIT") for a in assets)
    okx_mapped=sum(bool(a["perpetual"].get("symbol") and a["perpetual"].get("exchange")=="OKX") for a in assets)
    candle_count=sum(bool(a["perp_market"] and a["perp_market"].get("bars_available")) for a in assets)
    oi_count=sum(bool(a["perp_market"] and a["perp_market"].get("oi_usd") is not None) for a in assets)
    end_at=utc_parse(end)
    def is_recent(field, minutes):
        return sum(bool(a["perp_market"] and (t:=utc_parse(a["perp_market"].get(field))) and dt.timedelta(seconds=-2)<=(end_at-t)<=dt.timedelta(minutes=minutes)) for a in assets)
    fresh_closed_bars=is_recent("kline_last_close_utc", 125)
    fresh_oi=is_recent("oi_observed_utc", 125)
    fresh_funding=is_recent("funding_quote_time_utc", 125)
    fresh_quotes=sum(bool(a["cmc_quote"] and (t:=utc_parse(a["cmc_quote"].get("quote_last_updated_utc"))) and dt.timedelta(0)<=(end_at-t)<=dt.timedelta(minutes=90)) for a in assets)
    oi_require=math.ceil(mapped*.85)
    bars_require=math.ceil(mapped*.90)
    if not cmc_full:quality="FAILED_NO_OFFICIAL_UNIVERSE"
    elif quote_count<95 or fresh_quotes<95:quality="DATA_PARTIAL"
    elif binance_mapped<60 or mapped<60 or candle_count<bars_require or oi_count<oi_require or fresh_closed_bars<bars_require or fresh_oi<oi_require:quality="DATA_PARTIAL"
    else:quality="DATA_PASS"
    return {"schema_version":"v0.4","snapshot_started_utc":start,"snapshot_completed_utc":end,"status":quality,"index":{"source":"official_coinmarketcap_cmc100_keyless_api","source_url":f"{CMC_BASE}/v3/index/cmc100-latest","last_update":rebalance,"verified_constituents":len(constituents)},"coverage":{"official_cmc100_verified":len(constituents),"cmc_usd_quote_count":quote_count,"cmc_usd_quotes_fresh_90min":fresh_quotes,"binance_usd_m_exact_contract_mapping":binance_mapped,"binance_hourly_klines":sum(bool(a["perpetual"].get("exchange")=="BINANCE" and a["perp_market"] and a["perp_market"].get("bars_available")) for a in assets),"binance_closed_bars_fresh_125min":fresh_closed_bars if binance_mapped else 0,"binance_open_interest_history":sum(bool(a["perpetual"].get("exchange")=="BINANCE" and a["perp_market"] and a["perp_market"].get("oi_usd") is not None) for a in assets),"binance_oi_fresh_125min":fresh_oi if binance_mapped else 0,"binance_estimated_funding_fresh_125min":fresh_funding if binance_mapped else 0,"alternative_provider":proxy_provider,"bybit_linear_exact_contract_mapping":bybit_mapped,"okx_swap_exact_contract_mapping":okx_mapped,"alternative_hourly_klines":candle_count if not binance_mapped else 0,"alternative_oi_current_usd":oi_count if not binance_mapped else 0,"alternative_oi_change_24h":sum(bool(a["perp_market"] and a["perp_market"].get("oi_change_24h_pct") is not None and a["perpetual"].get("exchange")!="BINANCE") for a in assets),"alternative_funding_quote":fresh_funding if not binance_mapped else 0,"alternative_closed_bars_fresh_125min":fresh_closed_bars if not binance_mapped else 0},"market_context":{"coingecko_global":macro.get("data") if isinstance(macro,dict) else None,"defillama_top_chains_by_tvl":chain_stats},"assets":assets,"source_access_log":client.calls,"problems":problems,"research_boundary":"Only measured public sources. No forecast scores, news conclusions, or executions. No claims of full crypto information coverage."}


def html_page(snapshot, compact):
    return """<!doctype html><html lang='en'><head><meta charset='utf-8'><title>V6 CMC100 public market snapshot</title><style>body{font-family:system-ui,Arial,sans-serif;max-width:1120px;margin:36px auto;padding:0 18px;line-height:1.5;color:#1f2937}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f4f6;padding:16px;border-radius:8px;font:13px ui-monospace,monospace}h1{font-size:24px}p{max-width:900px}a{color:#174ea6}</style></head><body><h1>V6 CMC100 Public Market Snapshot</h1><p><strong>Live API data not guaranteed</strong>: the timestamp below is the snapshot capture time, NOT the forecast freeze. Each source observation may be older. Do not infer missing metrics, and read completeness first.</p><p><a href='latest.json'>Full snapshot JSON</a> · <a href='latest.csv'>Flat market features CSV</a> · <a href='forecast_context.md'>Forecast context Markdown</a> · <a href='status.json'>Collection status</a></p><h2>Compact verified CMC100 panel</h2><pre>"""+html.escape(compact)+"""</pre></body></html>"""


def output_artifacts(snapshot, docs=DOCS):
    docs.mkdir(parents=True,exist_ok=True)
    status={"status":snapshot["status"],"snapshot_completed_utc":snapshot["snapshot_completed_utc"],"coverage":snapshot["coverage"],"problems":snapshot["problems"],"source_errors":[x for x in snapshot["source_access_log"] if x["status"]!="OK"]}
    (docs/"status.json").write_text(json.dumps(status,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    if snapshot["index"]["verified_constituents"]!=100:return status
    # Snapshot immutable per file path; id hash includes data bytes. Avoid rewriting an earlier file.
    payload=json.dumps(snapshot,indent=2,ensure_ascii=False,sort_keys=True)+"\n"
    digest=hashlib.sha256(payload.encode()).hexdigest()[:12]
    stamp=snapshot["snapshot_completed_utc"].replace(":","").replace("-","")
    archive=docs/"archive"/stamp[:8]
    archive.mkdir(parents=True,exist_ok=True)
    archived=archive/f"{stamp}_{digest}.json"
    if not archived.exists():archived.write_text(payload,encoding="utf8")
    (docs/"latest.json").write_text(payload,encoding="utf8")
    fields=["cmc_id","symbol","name","quote_updated_utc","price_usd","ret_1h_pct","ret_24h_pct","ret_7d_pct","volume_24h_usd","volume_change_24h_pct","perp_symbol","perp_exchange","perp_mapping","perp_last_closed_bar_utc","perp_ret_6h_pct","perp_ret_24h_pct","perp_vol_24h_usd","perp_rv_24h_pct","perp_taker_imbalance_24h","oi_usd","oi_change_24h_pct","estimated_next_funding_rate_fraction","funding_quote_time_utc"]
    rows=[]
    for c in snapshot["assets"]:
        q=c["cmc_quote"] or {};m=c["perp_market"] or {};z=c["perpetual"]
        rows.append({"cmc_id":c["cmc_id"],"symbol":c["symbol"],"name":c["name"],"quote_updated_utc":q.get("quote_last_updated_utc"),"price_usd":q.get("price_usd"),"ret_1h_pct":q.get("ret_1h_pct"),"ret_24h_pct":q.get("ret_24h_pct"),"ret_7d_pct":q.get("ret_7d_pct"),"volume_24h_usd":q.get("volume_24h_usd"),"volume_change_24h_pct":q.get("volume_change_24h_pct"),"perp_symbol":z.get("symbol"),"perp_exchange":z.get("exchange"),"perp_mapping":z.get("mapping"),"perp_last_closed_bar_utc":m.get("kline_last_close_utc"),"perp_ret_6h_pct":m.get("perp_ret_6h_pct"),"perp_ret_24h_pct":m.get("perp_ret_24h_pct"),"perp_vol_24h_usd":m.get("perp_closed_24h_quote_volume"),"perp_rv_24h_pct":m.get("perp_realized_volatility_24h_pct"),"perp_taker_imbalance_24h":m.get("perp_taker_imbalance_24h"),"oi_usd":m.get("oi_usd"),"oi_change_24h_pct":m.get("oi_change_24h_pct"),"estimated_next_funding_rate_fraction":m.get("estimated_next_funding_rate_fraction"),"funding_quote_time_utc":m.get("funding_quote_time_utc")})
    sio=io.StringIO();writer=csv.DictWriter(sio,fieldnames=fields,lineterminator="\n");writer.writeheader();writer.writerows(rows)
    flat=sio.getvalue();(docs/"latest.csv").write_text(flat,encoding="utf8")
    compact_cols=["cmc_id","symbol","name","price_usd","ret_1h_pct","ret_24h_pct","ret_7d_pct","volume_24h_usd","perp_symbol","perp_exchange","perp_ret_6h_pct","oi_usd","oi_change_24h_pct","estimated_next_funding_rate_fraction"]
    s2=io.StringIO();w=csv.DictWriter(s2,fieldnames=compact_cols,extrasaction="ignore",lineterminator="\n");w.writeheader();w.writerows(rows)
    compact=s2.getvalue();
    context=(f"# V6 CMC100 verified quantitative snapshot\n\nSnapshot collected: {snapshot['snapshot_completed_utc']} (NOT forecast freeze)\nIndex last_update: {snapshot['index']['last_update']}\nSnapshot status: {snapshot['status']}\nDerivative market data may be from BYBIT/OKX and is NOT Binance execution or settlement data. Read perp_exchange column.\nCoverage: {json.dumps(snapshot['coverage'])}\n\nOnly actual measured values appear. Empty fields mean unavailable. Quoted 24h changes are trailing observations, NOT next-24h outcomes. Funding estimate is NOT settled funding. Check per-row observation timestamps in latest.json before using data.\n\n```csv\n{compact}```\n\nResearch must expand beyond this mechanical data panel autonomously, use Web Search and document separately cited incremental evidence. Do not treat market snapshots as predictions.\n")
    (docs/"forecast_context.md").write_text(context,encoding="utf8")
    (docs/"index.html").write_text(html_page(snapshot,compact),encoding="utf8")
    (docs/".nojekyll").touch()
    return status


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--relaxed",action="store_true",help="Record failures rather than fail on index API errors; no fake universe")
    ap.add_argument("--max-workers",type=int,default=5)
    ap.add_argument("--limit-perps",type=int,default=120)
    args=ap.parse_args(argv)
    if args.max_workers<1 or args.max_workers>12:ap.error("workers must be 1..12")
    client=Client()
    try:
        snap=collect(client,strict=not args.relaxed,max_workers=args.max_workers,limit_perps=args.limit_perps)
    except Exception as exc:
        status={"status":"FAILED_NO_OFFICIAL_UNIVERSE","snapshot_completed_utc":iso_now(),"coverage":{"official_cmc100_verified":0},"error":str(exc),"source_access_log":client.calls}
        DOCS.mkdir(parents=True,exist_ok=True)
        (DOCS/"status.json").write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
        print(json.dumps(status,ensure_ascii=False,indent=2))
        return 2
    status=output_artifacts(snap)
    print(json.dumps(status,ensure_ascii=False,indent=2))
    return 0 if snap["index"]["verified_constituents"]==100 else 2

if __name__=="__main__":sys.exit(main())
