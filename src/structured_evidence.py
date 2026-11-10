"""Public structured evidence sources, strictly separate from price predictions.

Only published governance proposals and newly listed security advisories are
events. TVL/stablecoin values are *observations* at capture time, not dated
historical events or verified associations with CMC100 constituents.
"""
from __future__ import annotations
import datetime as dt
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT="CMC100-Evidence-Research/5.0 (+https://github.com/SnakU4/crypto-market-data)"
UTC=dt.timezone.utc
SPACES=("aave.eth","uniswapgovernance.eth","ens.eth","arbitrumfoundation.eth",
        "opcollective.eth","lido-snapshot.eth","stgdao.eth","balancer.eth")
CISA_URL="https://raw.githubusercontent.com/cisagov/kev-data/develop/known_exploited_vulnerabilities.json"
DEFILLAMA_URL="https://api.llama.fi/protocols"
SNAPSHOT_URL="https://hub.snapshot.org/graphql"
MAX_JSON=9_000_000


def clean(value,limit=1600):
    value=re.sub(r"<[^>]*>"," ",str(value or ""))
    return re.sub(r"\s+"," ",html.unescape(value)).strip()[:limit]


def iso(timestamp):
    return dt.datetime.fromtimestamp(int(timestamp),UTC).isoformat(timespec="seconds").replace("+00:00","Z")


def fetch_json(url,body=None,timeout=12):
    headers={"User-Agent":USER_AGENT,"Accept":"application/json"}
    if body is not None:
        headers["Content-Type"]="application/json"
    req=urllib.request.Request(url,data=json.dumps(body).encode("utf-8") if body is not None else None,headers=headers)
    with urllib.request.urlopen(req,timeout=timeout) as response:
        raw=response.read(MAX_JSON+1)
        if len(raw)>MAX_JSON:
            raise ValueError("STRUCTURED_RESPONSE_TOO_LARGE")
        return json.loads(raw)


def snapshot_query():
    # A single query over selected well-known spaces avoids broad API sweeps.
    return {"query":"""query {
      proposals(first: 100, where: {space_in: ["aave.eth","uniswapgovernance.eth",
        "ens.eth","arbitrumfoundation.eth","opcollective.eth",
        "lido-snapshot.eth","stgdao.eth","balancer.eth"]},
        orderBy: "created", orderDirection: desc) {
          id title body created start end state
          space { id name }
        }
      }"""}


def snapshot_records(payload,observed,cutoff):
    obj=payload.get("data") if isinstance(payload,dict) else None
    if not isinstance(obj,dict) or not isinstance(obj.get("proposals"),list):
        raise ValueError("INVALID_SNAPSHOT_RESPONSE")
    results=[]
    for p in obj["proposals"]:
        if not isinstance(p,dict) or not isinstance(p.get("space"),dict):
            continue
        space=p["space"].get("id")
        ident=p.get("id")
        if not space or not ident or not re.fullmatch(r"[a-zA-Z0-9_-]{8,150}",str(ident)):
            continue
        created=p.get("created")
        try:
            when=dt.datetime.fromtimestamp(int(created),UTC)
        except (TypeError,ValueError,OverflowError):
            continue
        if when<cutoff or when>observed+dt.timedelta(minutes=2):
            continue
        body=clean(p.get("body"))
        url="https://snapshot.box/#/"+urllib.parse.quote(str(space),safe="")+"/proposal/"+urllib.parse.quote(str(ident),safe="")
        results.append({
            "url":url,"title":clean(p.get("title"),300) or "Governance proposal",
            "excerpt":body,"published_utc":iso(created),
            "publication_time_status":"SNAPSHOT_CREATED",
            "source_type":"SNAPSHOT_GOVERNANCE","observed_utc":observed.isoformat(),
            "context_origin":"PRIMARY_STRUCTURED_BODY",
            "structured_fields":{"space":space,"proposal_id":str(ident),
                                 "state":str(p.get("state") or "UNKNOWN"),
                                 "start_utc":iso(p["start"]) if isinstance(p.get("start"),int) else None,
                                 "end_utc":iso(p["end"]) if isinstance(p.get("end"),int) else None},
            "evidence_class":"PRIMARY_GOVERNANCE_EVENT",
            "direct_primary":True})
    return results


def kev_records(payload,observed,cutoff):
    rows=payload.get("vulnerabilities") if isinstance(payload,dict) else None
    if not isinstance(rows,list):
        raise ValueError("INVALID_CISA_KEV_RESPONSE")
    out=[]
    for v in rows:
        if not isinstance(v,dict):
            continue
        cve=v.get("cveID","")
        if not re.fullmatch(r"CVE-\d{4}-\d{4,}",cve):
            continue
        try:
            when=dt.datetime.strptime(v["dateAdded"],"%Y-%m-%d").replace(tzinfo=UTC)
        except (KeyError,TypeError,ValueError):
            continue
        # Calendar dates are not exact announcement instants: apply inclusive
        # date comparison, and do NOT treat dateAdded as publication timestamp.
        if when.date()<cutoff.date() or when.date()>observed.date():
            continue
        title=clean(f"{cve}: {v.get('vulnerabilityName') or v.get('product') or 'Known exploited vulnerability'}",300)
        out.append({
            "url":"https://www.cve.org/CVERecord?id="+cve,
            "title":title,
            "excerpt":clean(v.get("shortDescription","")),
            "published_utc":None,
            "publication_time_status":"DATE_ONLY_NOT_TIMESTAMP",
            "observed_utc":observed.isoformat(),"source_type":"CISA_KEV",
            "context_origin":"PRIMARY_STRUCTURED_DESCRIPTION",
            "structured_fields":{"cve_id":cve,"date_added":v["dateAdded"],
                "vendor":clean(v.get("vendorProject"),100),"product":clean(v.get("product"),100),
                "ransomware_use":v.get("knownRansomwareCampaignUse")},
            "evidence_class":"PRIMARY_SECURITY_CATALOG_ENTRY",
            "direct_primary":True})
    return out


def defillama_observations(payload,observed,limit=40):
    if not isinstance(payload,list):
        raise ValueError("INVALID_DEFILLAMA_RESPONSE")
    rows=[]
    for p in payload:
        if not isinstance(p,dict) or not p.get("name"):
            continue
        try: tvl=float(p.get("tvl"))
        except (ValueError,TypeError):continue
        if not 0<=tvl<1e15:continue
        rows.append((tvl,p))
    rows.sort(key=lambda e:e[0],reverse=True)
    out=[]
    for tvl,p in rows[:limit]:
        slug=p.get("slug") or p.get("name","")
        if not re.fullmatch(r"[a-zA-Z0-9_-]+",str(slug)):
            continue
        out.append({"url":"https://defillama.com/protocol/"+urllib.parse.quote(str(slug),safe=""),
                    "title":"Protocol TVL observation: "+clean(p.get("name"),160),
                    "excerpt":clean(f"Observed TVL USD {tvl:.2f}; category {p.get('category','UNKNOWN')}; chains {', '.join(str(c) for c in (p.get('chains') or [])[:6])}"),
                    "published_utc":None,
                    "publication_time_status":"OBSERVED_ONLY_NOT_HISTORICAL_EVENT",
                    "observed_utc":observed.isoformat(),"source_type":"DEFILLAMA_PROTOCOL_TVL",
                    "context_origin":"STRUCTURED_MARKET_OBSERVATION",
                    "structured_fields":{"tvl_usd":tvl,"symbol":p.get("symbol"),
                                         "protocol_id":str(p.get("id") or ""),"slug":slug},
                    "evidence_class":"OBSERVATION_NOT_EVENT",
                    "direct_primary":False})
    return out


def funding_records(payload, observed, symbol):
    if not isinstance(payload,list):
        raise ValueError("INVALID_BINANCE_FUNDING")
    out=[]
    for p in payload[:3]:
        if not isinstance(p,dict) or p.get("symbol")!=symbol:
            continue
        try:
            rate=float(p["fundingRate"])
            millis=int(p["fundingTime"])
            when=dt.datetime.fromtimestamp(millis/1000,UTC)
        except (ValueError,TypeError,KeyError,OverflowError):
            continue
        if when>observed+dt.timedelta(minutes=2) or when<observed-dt.timedelta(days=7):
            continue
        out.append({"url":"https://www.binance.com/en/futures/"+symbol+"?fundingTime="+str(millis),
                    "title":"Perpetual funding observation "+symbol,
                    "excerpt":f"Settled funding rate for {symbol}: {rate:.8f} at {iso(millis//1000)}",
                    "published_utc":iso(millis//1000),
                    "publication_time_status":"EXCHANGE_FUNDING_SETTLEMENT_TIME",
                    "observed_utc":observed.isoformat(),"source_type":"BINANCE_FUNDING",
                    "context_origin":"STRUCTURED_DERIVATIVES_OBSERVATION",
                    "structured_fields":{"exchange_symbol":symbol,"funding_rate":rate,
                                         "funding_time_ms":millis},
                    "evidence_class":"DERIVATIVE_MARKET_OBSERVATION",
                    "direct_primary":True})
    return out


def oi_records(payload, observed, symbol):
    if not isinstance(payload,dict) or payload.get("symbol")!=symbol:
        raise ValueError("INVALID_BINANCE_OPEN_INTEREST")
    try:
        amount=float(payload["openInterest"])
        millis=int(payload["time"])
        when=dt.datetime.fromtimestamp(millis/1000,UTC)
    except (ValueError,TypeError,KeyError,OverflowError):
        return []
    if when>observed+dt.timedelta(minutes=2) or when<observed-dt.timedelta(days=1):
        return []
    return [{"url":"https://www.binance.com/en/futures/"+symbol+"/openInterest",
             "title":"Open interest snapshot "+symbol,
             "excerpt":f"Observed open interest on Binance USD-M {symbol}: {amount:.6f} base units",
             "published_utc":None,
             "publication_time_status":"EXCHANGE_MARKET_TIMESTAMP_NOT_PUBLICATION",
             "observed_utc":observed.isoformat(),"source_type":"BINANCE_OPEN_INTEREST",
             "context_origin":"STRUCTURED_DERIVATIVES_OBSERVATION",
             "structured_fields":{"exchange_symbol":symbol,"open_interest_base_units":amount,
                                  "market_timestamp_ms":millis},
             "evidence_class":"OBSERVATION_NOT_EVENT","direct_primary":True}]

def collect_structured(observed, fetcher=fetch_json):
    """All providers independent. Return records paired with provenance jobs."""
    cutoff=observed-dt.timedelta(days=7)
    specs=[
      ("snapshot","GOVERNANCE_EVENTS","SNAPSHOT_HUB",SNAPSHOT_URL,snapshot_query(),snapshot_records),
      ("cisa_kev","SECURITY_EVENTS","CISA_KEV_GITHUB",CISA_URL,None,kev_records),
      ("defillama_tvl","DEFI_METRICS","DEFILLAMA_PUBLIC_API",DEFILLAMA_URL,None,defillama_observations),
    ]
    for symbol in ("BTCUSDT","ETHUSDT"):
        specs.append(("funding_"+symbol,"DERIVATIVES_METRICS","BINANCE_FUNDING",
                      "https://fapi.binance.com/fapi/v1/fundingRate?symbol="+symbol+"&limit=3",
                      None,lambda raw, now, sym=symbol: funding_records(raw,now,sym)))
        specs.append(("oi_"+symbol,"DERIVATIVES_METRICS","BINANCE_OPEN_INTEREST",
                      "https://fapi.binance.com/fapi/v1/openInterest?symbol="+symbol,
                      None,lambda raw, now, sym=symbol: oi_records(raw,now,sym)))
    findings=[];audit=[]
    for name,family,endpoint,url,body,parser in specs:
        job={"id":"structured_"+name,"family":family,"lens":family,"endpoint":endpoint,
             "kind":"structured","target":url}
        try:
            raw=fetcher(url,body)
            rows=parser(raw,observed,cutoff) if name in ("snapshot","cisa_kev") else parser(raw,observed)
            findings.extend((r,job) for r in rows)
            audit.append({"id":job["id"],"family":family,"endpoint":endpoint,
                          "status":"OK","count":len(rows),"error":None,"target":url})
        except (OSError,ValueError,TypeError,KeyError,urllib.error.URLError) as exc:
            audit.append({"id":job["id"],"family":family,"endpoint":endpoint,
                          "status":"ERROR","count":0,"error":type(exc).__name__+": "+str(exc)[:140],"target":url})
    return findings,audit
