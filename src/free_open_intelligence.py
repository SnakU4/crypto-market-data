#!/usr/bin/env python3
"""Free Open Intelligence v1: four-plane PIT-safe research + bounded adaptive follow-ups.

No paid API, LLM, proprietary data, forecasts, or invented coin relevance.
The adaptive step really executes new public searches when --network is enabled.
Full raw archives are retained at their original source paths; exported facts
are metadata and short, attributed context, not copies of full articles.
"""
from __future__ import annotations
import argparse, collections, datetime as dt, gzip, hashlib, json, math
import pathlib, re, sys, urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT="docs/intelligence"
UTC=dt.timezone.utc
UA="CMC100-Free-Open-Intelligence/1.0 public research"
STOP=set("""about after again ahead also among been before being bitcoin blockchain breaking
could crypto cryptocurrency cryptocurrencies despite during finally first from have
inside into latest market markets more news over price prices since their there these
those through today under update updated when where which while will with would
world year years says said token tokens coin coins just next says what yesterday
news new crypto funds data research analysis report reports this that they them
than only some seen much make made main still more last current change""".split())
QNT_ID=3155
# Explicit quarantine prompted by primary-documentation conflict identified during V8.2 audit.
# It is deliberately *not* interpreted as evidence for any other product mapping.
DENY_EXCHANGE={(QNT_ID,"QNT-USDT-SWAP"):"QNT instrument identity disputed: Quant vs Quantinuum; no crypto instrument metrics until independently verified"}

def iso(t):
    return t.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00","Z")

def parse_time(x):
    if not x:return None
    try:
        v=dt.datetime.fromisoformat(str(x).replace("Z","+00:00"))
        return v.astimezone(UTC) if v.tzinfo else None
    except (ValueError,TypeError,OverflowError):return None

def read(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))

def write(path,obj):
    path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False,sort_keys=True)+"\n",encoding="utf-8")

def digest(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()

def archive(root,status,domain):
    rel=status.get("archive_path")
    if not rel:raise ValueError(domain+": missing archive path")
    p=(root/rel).resolve()
    safe=(root/("docs/evidence_engine/archive" if domain=="engine" else "docs/expanded_discovery/archive")).resolve()
    if not p.is_relative_to(safe) or p.suffix!=".gz" or not p.exists():raise ValueError(domain+": bad or missing raw archive")
    if digest(p)!=status.get("archive_sha256"):raise ValueError(domain+": archive SHA mismatch")
    expected=int(status["records"] if domain=="engine" else status["full_archive_count"])
    rows=[]
    with gzip.open(p,"rt",encoding="utf-8") as f:
        for line in f:
            if line.strip():rows.append(json.loads(line))
    if len(rows)!=expected:raise ValueError(domain+": archive count mismatch")
    return rows,{"path":rel,"sha256":digest(p),"records":len(rows),"verified":True}

def is_before(event,cutoff):
    observed=parse_time(event.get("observed_utc") or event.get("first_observed_utc"))
    published=parse_time(event.get("published_utc"))
    return bool(observed and observed<=cutoff and (published is None or published<=cutoff))

def usable_json(root,rel,status_time,cutoff,required=True):
    p=root/rel
    if not p.exists():
        if required:raise ValueError("missing input: "+rel)
        return None
    if status_time and (not parse_time(status_time) or parse_time(status_time)>cutoff):
        if required:raise ValueError("post-cutoff input: "+rel)
        return None
    return read(p)

def clip(x,n=330):
    return re.sub(r"\s+"," ",str(x or "")).strip()[:n]

def ref(kind,item):
    value=str(item.get("event_id") or item.get("observation_id") or item.get("id") or item.get("url") or "")
    return kind+":"+hashlib.sha256(value.encode()).hexdigest()[:18]

def priority(event):
    text=str(event.get("excerpt") or "")
    title=str(event.get("title") or event.get("headline") or "")
    origins=event.get("source_families") or [event.get("source_family","")]
    origin=" ".join(origins)
    return (50 if len(text)>len(title)+80 else 0)+(18 if "PRIMARY" in origin or "GITHUB" in origin else 0)+(12 if "SECURITY" in origin or "GOVERNANCE" in origin else 0)+(8 if event.get("published_utc") else 0)

def event_doc(kind,e,cutoff):
    """Structured events are leads, not independently verified facts."""
    if not is_before(e,cutoff):return None
    title=clip(e.get("title") or e.get("headline"),230)
    url=str(e.get("resolved_article_url") or e.get("url") or "")[:550]
    if not title and not url:return None
    # Original provenance is never confused with verified relevance.
    ids=e.get("query_scoped_ids") if kind=="expanded" else e.get("cmc_ids") if kind=="research" else []
    ids=[int(x) for x in (ids or []) if str(x).isdigit()]
    themes=e.get("theme_leads") or []
    if kind=="expanded":
        themes+= [str(z.get("lens")) for z in e.get("search_origins",[]) if z.get("family")=="CROSS_SECTOR" and z.get("lens")]
    scope="SECTOR" if themes else "ASSET_CANDIDATE" if ids else "GLOBAL_UNRESOLVED"
    return {"id":ref(kind,e),"source_plane":kind,"title":title,"url":url,
            "excerpt":clip(e.get("excerpt"),380),"published_utc":e.get("published_utc"),
            "first_observed_utc":e.get("first_observed_utc") or e.get("observed_utc"),
            "scope":scope,"candidate_cmc_ids":sorted(set(ids)),
            "themes":sorted(set(map(str,themes))),"identity_status":"SEARCH_OR_TEXT_CANDIDATE_NOT_VERIFIED" if ids else "NO_ASSET_LINK_ASSERTED",
            "claim_status":"NOT_INDEPENDENTLY_VERIFIED",
            "source_family":e.get("source_family") or (e.get("source_families") or ["UNSPECIFIED"])[0],
            "source_id":e.get("source_id") or (e.get("source_ids") or [None])[0],
            "priority":priority(e)}

def deduplicate(events):
    """Deduplicate syndicated URLs within each stream, retain multiple provenance IDs."""
    by_key={}
    for e in events:
        u=urllib.parse.urlsplit(e["url"])
        key=(u.scheme,u.hostname or "",u.path.rstrip("/")) if u.hostname and "news.google." not in (u.hostname or "") else ("title",re.sub(r"[^a-z0-9]+"," ",e["title"].lower()).strip())
        if not any(key):key=("id",e["id"])
        if key not in by_key:
            by_key[key]={**e,"provenance_ids":[e["id"]]}
        else:
            old=by_key[key];old["provenance_ids"].append(e["id"])
            old["candidate_cmc_ids"]=sorted(set(old["candidate_cmc_ids"]+e["candidate_cmc_ids"]))
            old["themes"]=sorted(set(old["themes"]+e["themes"]))
            if e["priority"]>old["priority"]:
                old.update({k:e[k] for k in ("excerpt","source_family","source_id","priority")})
    return list(by_key.values())

def keyword_pairs(events):
    """Source-derived discoveries only. No hardwired sector taxonomy or predicted alpha."""
    scores=collections.defaultdict(lambda:{"sources":set(),"examples":[],"theme":set()})
    for e in events:
        if e["source_plane"] not in ("adjacent","research"):continue
        tokens=[w.lower() for w in re.findall(r"[A-Za-z][A-Za-z-]{3,22}",e["title"])
                if w.lower() not in STOP]
        tokens=tokens[:20]
        for i in range(len(tokens)-1):
            a,b=tokens[i:i+2]
            if a in STOP or b in STOP or len(a)<4 or len(b)<4:continue
            term=a+" "+b
            z=scores[term];z["sources"].add(str(e["source_id"] or e["source_plane"]))
            if len(z["examples"])<3:z["examples"].append(e["id"])
            z["theme"].update(e["themes"])
    return [{"term":k,"independent_source_count":len(v["sources"]),"examples":v["examples"],
             "themes":sorted(v["theme"])} for k,v in
            sorted(scores.items(),key=lambda x:(-len(x[1]["sources"]),-len(x[1]["examples"]),x[0]))
            if len(v["sources"])>=2][:30]

def research_tasks(coins,events,market,limit=22):
    """Deterministic multi-hop discovery: source-emergent themes, event clues, anomalies."""
    seen=set();tasks=[]
    def add(query,scope,reason,ids=()):
        q=clip(query,150)
        key=q.casefold()
        if key in seen:return
        if len(tasks)>=limit:return
        seen.add(key)
        tasks.append({"task_id":"T:"+hashlib.sha256(q.encode()).hexdigest()[:12],
                      "query":q,"scope":scope,"trigger":reason,"evidence_ids":list(ids)[:4],
                      "status":"PLANNED","results":0})
    # Search phrases actually *discovered* across distinct existing source streams.
    for phrase in keyword_pairs(events)[:9]:
        add('"'+phrase["term"]+'" crypto financial markets when:2d',
            "GLOBAL_OR_SECTOR","NEW_CROSS_SOURCE_TOPIC",phrase["examples"])
    # Follow up on unusually positioned official CMC100 assets. Never invent a catalyst.
    ranked=[]
    for a in market["assets"]:
        quote=a.get("cmc_quote") or {}
        v=quote.get("volume_change_24h_pct")
        ret=quote.get("ret_24h_pct")
        try:
            x=abs(float(v or 0))/35 + abs(float(ret or 0))/8
        except (TypeError,ValueError):continue
        if x>0:ranked.append((x,a))
    for _,a in sorted(ranked,key=lambda x:-x[0])[:7]:
        add('"'+str(a["name"]).replace('"',"")+'" crypto" '
            'liquidity derivatives security governance when:2d',
            "ASSET_RESEARCH","OBSERVED_MARKET_ANOMALY")
    # Follow up on important *unresolved* leads, independently of coin attribution.
    for e in sorted(events,key=lambda x:-x["priority"]):
        if len(tasks)>=limit:break
        if e["source_plane"] not in ("adjacent","research") or e["candidate_cmc_ids"]:continue
        if len(e["excerpt"])<90:continue
        tokens=[w for w in re.findall(r"[A-Za-z][A-Za-z-]{4,25}",e["title"]) if w.lower() not in STOP][:5]
        if len(tokens)<3:continue
        add('"'+ " ".join(tokens[:3])+'" crypto financial impact when:3d',
            "UNRESOLVED","SUBSTANTIVE_UNLINKED_LEAD",[e["id"]])
    return tasks

def adaptive_fetch(tasks,cutoff,max_requests=22,opener=None):
    """Execute free follow-up searches, record failures; never fabricate results."""
    op=opener or urllib.request.urlopen
    found=[];audit=[]
    for t in tasks[:max_requests]:
        query=t["query"]
        u="https://news.google.com/rss/search?"+urllib.parse.urlencode(
            {"q":query,"hl":"en-US","gl":"US","ceid":"US:en"})
        try:
            req=urllib.request.Request(u,headers={"User-Agent":UA,"Accept":"application/rss+xml"})
            with op(req,timeout=7) as resp:
                payload=resp.read(350_001)
            if len(payload)>350000:raise ValueError("OVERSIZED_RSS")
            root=ET.fromstring(payload)
            count=0
            for item in root.findall(".//item")[:12]:
                title=clip(item.findtext("title"),220);url=clip(item.findtext("link"),520)
                pub=item.findtext("pubDate")
                published=None
                try:published=parsedate_to_datetime(pub).astimezone(UTC) if pub else None
                except (ValueError,TypeError):pass
                if published and published>cutoff:continue
                if not title or not url:continue
                found.append({"id":ref("followup",{"url":url}),"source_plane":"adaptive",
                        "title":title,"url":url,"excerpt":clip(item.findtext("description"),320),
                        "published_utc":iso(published) if published else None,
                        "first_observed_utc":iso(cutoff),"scope":t["scope"],
                        "candidate_cmc_ids":[],"themes":[],"identity_status":"NOT_ASSESSED",
                        "claim_status":"SEARCH_RESULT_ONLY","source_family":"ADAPTIVE_SEARCH",
                        "source_id":t["task_id"],"priority":0,"origin_task_id":t["task_id"]})
                count+=1
            t["status"]="QUERIED";t["results"]=count
            audit.append({"task_id":t["task_id"],"status":"OK","results":count})
        except (ValueError,ET.ParseError,urllib.error.URLError,TimeoutError,OSError) as exc:
            t["status"]="FAILED";t["error"]=type(exc).__name__+": "+clip(exc,120)
            audit.append({"task_id":t["task_id"],"status":"FAILED","error":t["error"]})
    return found,audit

def enrich_direct(events,budget=16,fetcher=None):
    if budget<=0:return []
    if fetcher is None:
        try:from discovery_quality import extract_article as fetcher
        except ImportError:from src.discovery_quality import extract_article as fetcher
    selected=[];seen_hosts=set()
    # Diverse publisher-first sampling, including independent non-coin global/sector research.
    for scope in ("SECTOR","GLOBAL_UNRESOLVED","ASSET_CANDIDATE"):
        xs=sorted((e for e in events if e["scope"]==scope and e["url"].startswith("https://")
                  and "news.google." not in urllib.parse.urlsplit(e["url"]).netloc
                  and len(e["excerpt"])<150),key=lambda x:-x["priority"])
        for e in xs:
            if len(selected)>=budget:break
            host=urllib.parse.urlsplit(e["url"]).netloc
            if host in seen_hosts:continue
            seen_hosts.add(host);selected.append(e)
    out=[]
    for e in selected:
        try:raw=fetcher(e["url"])
        except Exception:raw=None
        if raw and len(raw)>=130:
            out.append({"evidence_id":e["id"],"url":e["url"],
                        "source_excerpt":clip(raw,350),
                        "verification":"TEXT_EXTRACTED_NOT_FACT_VERIFIED"})
    return out

def build(root=ROOT,out=None,cutoff=None,network=False,max_followups=22,max_articles=16,
          fetcher=None,search_opener=None):
    root=pathlib.Path(root).resolve();out=pathlib.Path(out or root/OUT)
    cutoff=cutoff or dt.datetime.now(UTC)
    market=read(root/"docs/latest.json")
    assets=market.get("assets") or []
    ids=[int(a["cmc_id"]) for a in assets]
    if len(ids)!=100 or len(set(ids))!=100 or market.get("index",{}).get("verified_constituents")!=100:
        raise ValueError("CMC100 universe not verified 100/100")
    if not parse_time(market.get("snapshot_completed_utc")) or parse_time(market["snapshot_completed_utc"])>cutoff:
        raise ValueError("market snapshot after cutoff")
    es=read(root/"docs/evidence_engine/status.json")
    xs=read(root/"docs/expanded_discovery/status.json")
    rs=read(root/"docs/research/status.json")
    ds=read(root/"docs/discovery/status.json")
    caps={"market":market["snapshot_completed_utc"],"engine":es["capture_utc"],
          "expanded":xs["capture_utc"],"research":rs["capture_utc"],
          "adjacent":ds["capture_completed_utc"]}
    for k,v in caps.items():
        if not parse_time(v) or parse_time(v)>cutoff:raise ValueError("source capture after cutoff: "+k)
    er,ea=archive(root,es,"engine")
    xr,xa=archive(root,xs,"expanded")
    research=usable_json(root,"docs/research/latest.json",rs["capture_utc"],cutoff)
    adjacent=usable_json(root,"docs/discovery/latest.json",ds["capture_completed_utc"],cutoff)
    valid_ids=set(ids)
    all_events=[]
    for kind,rows in (("expanded",xr),("research",research.get("events") or []),
                      ("adjacent",adjacent.get("events") or [])):
        for e in rows:
            z=event_doc(kind,e,cutoff)
            if z:
                z["candidate_cmc_ids"]=[i for i in z["candidate_cmc_ids"] if i in valid_ids]
                all_events.append(z)
    events=deduplicate(all_events)
    features={int(x["cmc_id"]):x for x in research.get("coins") or []}
    fam=research.get("families") or {}
    family_by_coin=collections.defaultdict(list)
    for name,rows in fam.items():
        if not isinstance(rows,list):continue
        for row in rows:
            if not isinstance(row,dict):continue
            cid=row.get("cmc_id")
            if cid in valid_ids:
                family_by_coin[cid].append({"family":name,"observation":row})
    structured=collections.defaultdict(lambda:collections.Counter())
    struct_references=collections.defaultdict(list)
    for e in er:
        cid=e.get("cmc_id") or e.get("candidate_cmc_id")
        if cid not in valid_ids or not is_before(e,cutoff):continue
        structured[cid][str(e.get("source") or "UNSPECIFIED")]+=1
        if len(struct_references[cid])<12:
            struct_references[cid].append({"ref":e.get("observation_id"),
               "source":e.get("source"),"identity_status":e.get("coin_identity_status")})
    by_asset=collections.defaultdict(list);glob=[];sector=collections.defaultdict(list)
    for e in events:
        if e["scope"]=="SECTOR":
            for theme in e["themes"]:sector[theme].append(e)
        elif e["scope"]=="ASSET_CANDIDATE":
            for cid in e["candidate_cmc_ids"]:by_asset[cid].append(e)
        else:glob.append(e)
    cards=[]
    quarantined=[]
    for a in assets:
        cid=int(a["cmc_id"]);q=a.get("cmc_quote") or {};perp=a.get("perpetual") or {}
        instr=str(perp.get("symbol") or "")
        denied=DENY_EXCHANGE.get((cid,instr))
        if denied:quarantined.append({"cmc_id":cid,"instrument":instr,"reason":denied})
        original=features.get(cid) or {}
        ff=[]
        for entry in family_by_coin[cid]:
            ob=entry["observation"]
            instrument=ob.get("instrument_id")
            if denied and (entry["family"]=="okx_orderbooks" or instrument==instr):
                continue
            ff.append(entry)
        select=sorted(by_asset[cid],key=lambda x:(-x["priority"],x["id"]))[:10]
        card={
            "cmc_id":cid,"name":a["name"],"symbol":a["symbol"],
            "cmc100_weight":a.get("cmc100_weight"),"spot_quote":q,
            "perpetual":None if denied else perp,
            "perp_market":None if denied else a.get("perp_market"),
            "perp_identity_status":"QUARANTINED" if denied else
               "EXCHANGE_SYMBOL_MATCH_NOT_INDEPENDENT_CONTRACT_VERIFICATION" if perp else "NOT_AVAILABLE",
            "research_coin_features":{k:v for k,v in original.items()
                if k not in ("research_event_candidate_ids","perp_oi_usd",
                             "perp_funding_estimate","okx_orderbook_spread_bps",
                             "okx_orderbook_top5_ask_usd","okx_orderbook_top5_bid_usd")},
            "quantitative_research_families":ff,
            "engine_record_counts_by_source":dict(structured[cid]),
            "engine_provenance_sample":struct_references[cid],
            "candidate_event_count":len(by_asset[cid]),
            "candidate_events_NOT_VERIFIED":[{k:e[k] for k in
                ("id","title","url","excerpt","published_utc","claim_status","identity_status")}
                for e in select],
            "missing_data":[key for key,ok in (("cmc_spot",bool(q.get("price_usd"))),
                            ("verified_perp_contract",bool(perp and not denied)),
                            ("mapped_protocol_fundamentals",bool(ff)),
                            ("coin_relevant_article_text",any(len(e["excerpt"])>=150 for e in by_asset[cid])))
                             if not ok]
        }
        cards.append(card)
    emergent=keyword_pairs(events)
    tasks=research_tasks(cards,events,market,max_followups)
    adaptive,audit=adaptive_fetch(tasks,cutoff,max_followups,opener=search_opener) if network else ([],[])
    article=enrich_direct(events,max_articles if network else 0,fetcher)
    for e in adaptive:e["provenance_ids"]=[e["id"]]
    evidence=events+adaptive
    sectors=[{"theme":k,"lead_count":len(v),
              "sample":[{x:e[x] for x in ("id","title","url","excerpt","published_utc","claim_status")}
                        for e in sorted(v,key=lambda e:-e["priority"])[:10]]}
             for k,v in sorted(sector.items(),key=lambda z:(-len(z[1]),z[0]))]
    g={"cutoff_utc":iso(cutoff),"market_context":market.get("market_context"),
       "global_unresolved_leads":len(glob),
       "headline_only_claims_are_NOT_verified":True,
       "global_research_sample":[{x:e[x] for x in ("id","title","url","excerpt","published_utc","claim_status")}
                                 for e in sorted(glob,key=lambda e:-e["priority"])[:75]],
       "adaptive_followups":[{k:t[k] for k in ("task_id","query","scope","status","results")}
                             for t in tasks],
       "adaptive_discovery_findings":[{k:e[k] for k in ("id","title","url","published_utc","scope")}
                                      for e in adaptive[:100]]}
    coverage={
      "official_assets":100,"source_planes_integrated":["market","evidence_engine",
          "expanded_discovery","research","adjacent_discovery"],
      "source_capture_utc":caps,
      "evidence_counts":{"engine_rows":len(er),"expanded_rows":len(xr),
          "research_event_rows":len(research.get("events") or []),
          "adjacent_latest_event_rows":len(adjacent.get("events") or []),
          "integrated_event_rows_before_dedup":len(all_events),
          "canonical_research_leads":len(events),
          "free_adaptive_followup_leads":len(adaptive),
          "substantive_source_excerpt_leads":sum(len(e["excerpt"])>=140 for e in events),
          "direct_publisher_article_excerpts":len(article)},
      "per_coin":{"spot_prices":sum(bool((a.get("cmc_quote") or {}).get("price_usd")) for a in assets),
          "perp_markets_unquarantined":sum(bool(a.get("perpetual")) and
               (int(a["cmc_id"]),str((a.get("perpetual") or {}).get("symbol") or "")) not in DENY_EXCHANGE for a in assets),
          "research_mapped_quantitative_families":sum(bool(family_by_coin[i]) for i in ids),
          "candidate_news_links":sum(bool(by_asset[i]) for i in ids)},
      "identity_quarantine":quarantined,
      "quality_caveat":"Search origin and provider metrics are NOT independently verified causal asset claims.",
      "source_failures":{"engine":es.get("limitations",[]),
         "expanded":xs.get("access_gaps",{}),
         "research":[x for x in rs.get("source_attempts",[]) if x.get("status")!="OK"][:25],
         "adjacent":ds.get("access_gaps",[])},
      "adaptive_search_results":audit}
    manifest={"schema_version":"cmc100-open-intelligence-free-v1","cutoff_utc":iso(cutoff),
       "no_paid_api_used":True,"llm_calls":0,
       "all_100_verified":True,"source_snapshots":caps,"archives":{"engine":ea,"expanded":xa},
       "coverage_file":"docs/intelligence/coverage_audit.json",
       "global_file":"docs/intelligence/global_intelligence.json",
       "sector_file":"docs/intelligence/sector_intelligence.json",
       "task_file":"docs/intelligence/research_tasks.json",
       "knowledge_file":"docs/intelligence/knowledge_index.json",
       "coin_batch_files":[f"docs/intelligence/coin_batches/batch_{i+1:02d}.json" for i in range(5)],
       "full_evidence_export":"docs/intelligence/export/evidence_index.jsonl",
       "full_evidence_export_is_actions_artifact_only":True,
       "limitation":"Deterministic adaptive follow-up, NOT an autonomous LLM researcher or alpha signal."}
    for i in range(5):
        write(out/f"coin_batches/batch_{i+1:02d}.json",
              {"coins":cards[i*20:(i+1)*20],"version":"free-open-intelligence-v1"})
    write(out/"global_intelligence.json",g)
    write(out/"sector_intelligence.json",{"sectors":sectors,"open_ended_scope":True})
    write(out/"open_discovery.json",{"emergent_terms":emergent,
          "unresolved_global_count":len(glob),
          "source_discovery_notes":"Themes and asset associations are leads, never verified causality."})
    write(out/"research_tasks.json",{"tasks":tasks,
          "audit":audit,"no_auto_source_installation":True})
    write(out/"coverage_audit.json",coverage)
    write(out/"knowledge_index.json",{"evidence_count":len(evidence),
          "by_plane":dict(collections.Counter(e["source_plane"] for e in evidence)),
          "scope_counts":dict(collections.Counter(e["scope"] for e in evidence)),
          "primary_claims_verified_by_system":0,
          "note":"All original archives are referenced in manifest; data not omitted from source files."})
    write(out/"publisher_excerpts.json",{"items":article,
          "policy":"Short attributed text only; robots respected; NOT verified claims."})
    export=out/"export";export.mkdir(parents=True,exist_ok=True)
    p=export/"evidence_index.jsonl"
    with p.open("w",encoding="utf-8") as f:
        for e in evidence:f.write(json.dumps(e,ensure_ascii=False,allow_nan=False,separators=(",",":"))+"\n")
    manifest["full_evidence_sha256"]=digest(p)
    manifest["full_evidence_count"]=len(evidence)
    manifest["published_bundle_bytes"]=sum(x.stat().st_size for x in out.rglob("*.json"))
    write(out/"manifest.json",manifest)
    return manifest,coverage

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=pathlib.Path,default=ROOT)
    p.add_argument("--out",type=pathlib.Path,default=None)
    p.add_argument("--cutoff",type=str,default=None)
    p.add_argument("--network",action="store_true")
    p.add_argument("--max-followups",type=int,default=22)
    p.add_argument("--max-articles",type=int,default=16)
    a=p.parse_args()
    cutoff=parse_time(a.cutoff) if a.cutoff else dt.datetime.now(UTC)
    if not cutoff:p.error("Invalid cutoff")
    if a.max_followups>40 or a.max_articles>30:p.error("Free tier bounded to 40 searches/30 articles")
    manifest,coverage=build(a.root,a.out,cutoff,a.network,a.max_followups,a.max_articles)
    print(json.dumps({"status":"SUCCESS","manifest":manifest,
       "evidence_counts":coverage["evidence_counts"],
       "coverage":coverage["per_coin"]},ensure_ascii=False))

if __name__=="__main__":main()
