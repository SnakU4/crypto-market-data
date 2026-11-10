#!/usr/bin/env python3
"""V8 evidence handoff: FULL SHA-verified archives -> 100 LLM-readable coin cards.

No LLM, web searches or trading calls. Exact OKX exchange-instrument linkage is
not a verified native-token contract. News query provenance is not coin relevance.
Raw records are fully parsed; untruncated JSONL exports go to Actions artifacts.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path

UTC=dt.timezone.utc
ROOT=Path(__file__).resolve().parents[1]
ENGINE="docs/evidence_engine"
DISCOVERY="docs/expanded_discovery"
OUT="docs/research_pack"

def moment(value):
    try:
        t=dt.datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return t.astimezone(UTC) if t.tzinfo else None
    except (ValueError,TypeError):return None

def as_utc(t):return t.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00","Z")

def get(path):return json.loads(Path(path).read_text(encoding="utf8"))

def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""):h.update(chunk)
    return h.hexdigest()

def write(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,separators=(",",":"),
                               sort_keys=True,allow_nan=False)+"\n",encoding="utf8")

def read_archive(root,meta,domain):
    rel=meta.get("archive_path")
    if not isinstance(rel,str):raise ValueError(domain+"_NO_ARCHIVE")
    path=(root/rel).resolve()
    safe=(root/("docs/evidence_engine/archive" if domain=="engine"
                else "docs/expanded_discovery/archive")).resolve()
    if not path.is_relative_to(safe) or path.suffix!=".gz":
        raise ValueError(domain+"_INVALID_ARCHIVE_PATH")
    if not path.exists() or sha(path)!=meta.get("archive_sha256"):
        raise ValueError(domain+"_MISSING_OR_UNVERIFIED_ARCHIVE")
    rows=[]
    with gzip.open(path,"rt",encoding="utf8") as f:
        for i,line in enumerate(f):
            if i>=100000:raise ValueError(domain+"_TOO_MANY_ROWS")
            obj=json.loads(line)
            if not isinstance(obj,dict):raise ValueError(domain+"_NONOBJECT")
            rows.append(obj)
    expected=int(meta["records"] if domain=="engine" else
                 meta.get("full_archive_count",meta["distinct_url_leads"]))
    if len(rows)!=expected:raise ValueError(domain+"_COUNT_MISMATCH")
    return rows,{"path":rel,"sha256":meta["archive_sha256"],
                 "expected":expected,"decompressed":len(rows),"verified":True}

def cutoff_check(rows,cutoff,domain):
    okay=[];quarantined=0
    for row in rows:
        seen=moment(row.get("observed_utc") or row.get("first_observed_utc"))
        published=moment(row.get("published_utc"))
        if seen is None or seen>cutoff or (published and published>cutoff):
            quarantined+=1
        else:okay.append(row)
    return okay,{"asof_eligible":len(okay),"quarantined_unknown_or_future":quarantined}

def led_score(e):
    fam=set(e.get("source_families") or [])
    return (90*bool(e.get("direct_primary"))+
            45*bool(e.get("excerpt_adds_information"))+
            35*bool(fam&{"PROJECT_PRIMARY","GOVERNANCE_EVENTS","SECURITY_EVENTS"})+
            15*bool(fam&{"PUBLIC_COMMUNITY","TECH_SECURITY_RESEARCH"})+
            8*bool(e.get("candidate_fact_spans"))+
            8*not bool(e.get("previously_seen"))-
            25*(e.get("context_origin")=="TITLE_ONLY"))

def direct(x):
    return {"evidence_id":"S:"+str(x["observation_id"]),"source":x.get("source"),
            "item":x.get("source_item_id"),"metrics":x.get("metrics") or {},
            "attributes":x.get("attributes") or {},
            "identity_status":x.get("coin_identity_status"),
            "observed_utc":x.get("observed_utc"),"published_utc":x.get("published_utc")}

def lead(e):
    return {"evidence_id":"D:"+str(e["event_id"]),"title":e.get("title"),
            "url":e.get("url"),"excerpt":(e.get("excerpt") or "")[:1200],
            "source_families":e.get("source_families") or [],
            "published_utc":e.get("published_utc"),
            "observed_utc":e.get("observed_utc"),
            "content_substantive":bool(e.get("excerpt_adds_information")),
            "direct_primary":bool(e.get("direct_primary")),
            "identity_status":"SEARCH_ORIGIN_ONLY_NOT_COIN_MATCH",
            "claim_status":"NOT_VERIFIED","research_priority_not_price_impact":led_score(e)}

def build(root=ROOT,cutoff=None):
    root=Path(root).resolve()
    cutoff=(cutoff or dt.datetime.now(UTC)).astimezone(UTC)
    market=get(root/"docs/latest.json")
    assets=market.get("assets") or []
    ids=[int(x["cmc_id"]) for x in assets]
    if len(ids)!=100 or len(set(ids))!=100 or market.get("index",{}).get("verified_constituents")!=100:
        raise ValueError("NOT_VERIFIED_100_CMC_INDEX")
    if moment(market.get("snapshot_completed_utc")) is None or moment(market["snapshot_completed_utc"])>cutoff:
        raise ValueError("MARKET_POST_CUTOFF")
    es=get(root/ENGINE/"status.json");ds=get(root/DISCOVERY/"status.json")
    for label,s in (("engine",es),("discovery",ds)):
        if moment(s.get("capture_utc")) is None or moment(s["capture_utc"])>cutoff:
            raise ValueError(label+"_POST_CUTOFF")
    struct,ea=read_archive(root,es,"engine")
    news,da=read_archive(root,ds,"discovery")
    struct,es_filter=cutoff_check(struct,cutoff,"engine")
    news,ds_filter=cutoff_check(news,cutoff,"discovery")
    if any(not x.get("observation_id") for x in struct):
        raise ValueError("ENGINE_ID_MISSING")
    if any(not x.get("event_id") for x in news):
        raise ValueError("NEWS_ID_MISSING")
    exact=defaultdict(list);possible=defaultdict(list);network=defaultdict(list);unassigned=[]
    known=set(ids)
    for x in struct:
        cmc=x.get("cmc_id");candidate=x.get("candidate_cmc_id");context=x.get("network_context_cmc_id")
        if (cmc in known and x.get("coin_identity_status")=="CMC100_SNAPSHOT_OKX_CONTRACT_ANCHORED"
                and x.get("source") in ("okx_swap_tickers","okx_swap_open_interest")):
            exact[cmc].append(x)
        elif candidate in known:possible[candidate].append(x)
        elif context in known:network[context].append(x)
        else:unassigned.append(x)
    partition={"anchored_exchange":sum(map(len,exact.values())),
               "cross_provider_candidates":sum(map(len,possible.values())),
               "network_only":sum(map(len,network.values())),
               "unassigned":len(unassigned)}
    if sum(partition.values())!=len(struct):raise ValueError("STRUCTURED_PARTITION_LOSS")
    query=defaultdict(list);global_news=[];multi=0
    for e in news:
        keys={int(k) for k in (e.get("query_scoped_ids") or []) if str(k).isdigit() and int(k) in known}
        if not keys:global_news.append(e)
        else:
            multi+=len(keys)>1
            for k in keys:query[k].append(e)
    cards=[]
    for a in assets:
        cid=int(a["cmc_id"]);market_quote=a.get("cmc_quote") or {};perp=a.get("perpetual") or {}
        selection=sorted(query[cid],key=lambda x:(-led_score(x),str(x.get("event_id"))))
        picked=[];seen_titles=set()
        for e in selection:
            story=e.get("story_title_hash") or e["event_id"]
            if story in seen_titles:continue
            seen_titles.add(story);picked.append(lead(e))
            if len(picked)>=18:break
        tentative=sorted(possible[cid],key=lambda x:(
            x.get("source")!="patternplus_unlocks",str(x.get("source_item_id"))))
        cards.append({
            "cmc_id":cid,"symbol":a.get("symbol"),"name":a.get("name"),
            "weight":a.get("cmc100_weight"),
            "spot_snapshot":{"market_snapshot_utc":market.get("snapshot_completed_utc"),
                "price_usd":market_quote.get("price_usd"),
                "ret_1h_pct":market_quote.get("ret_1h_pct"),
                "ret_24h_pct":market_quote.get("ret_24h_pct"),
                "ret_7d_pct":market_quote.get("ret_7d_pct"),
                "volume_24h_usd":market_quote.get("volume_24h_usd"),
                "market_cap_usd":market_quote.get("market_cap_usd")},
            "exchange_perpetual_reference":{"symbol":perp.get("symbol"),
                "exchange":perp.get("exchange"),"mapping":perp.get("mapping"),
                "source_type":"RESEARCH_PROXY_NOT_EXECUTION"},
            "anchored_okx_instrument_observations":[direct(x) for x in exact[cid]],
            "unverified_coin_candidate_observations":[direct(x) for x in tentative[:18]],
            "network_context_NOT_coin_flows":[direct(x) for x in network[cid][:8]],
            "news_search_origin_leads_UNVERIFIED":picked,
            "full_source_counts":{"anchored":len(exact[cid]),"candidate":len(tentative),
                "network":len(network[cid]),"query_origin":len(query[cid]),
                "shown_news":len(picked)},
            "validation_tasks":["Verify primary factual relevance for this exact CMC ID.",
                "Identify both potential upside and downside for the NEXT 24h.",
                "Do not interpret generic network tx or a title-only RSS lead as catalyst.",
                "Determine what is already priced and what remains uncertain."]})
    deltas=get(root/ENGINE/"delta_candidates.json")
    events=get(root/ENGINE/"event_candidates.json")
    if deltas.get("capture_utc")!=es["capture_utc"] or events.get("capture_utc")!=es["capture_utc"]:
        raise ValueError("MISMATCHED_SOURCE_TIMESTAMPS")
    global_doc={"schema_version":"research-global-v1",
        "unassigned_structured_count":len(unassigned),
        "unassigned_by_source":dict(Counter(x.get("source") for x in unassigned)),
        "unassigned_structured_samples":[direct(x) for x in sorted(unassigned,key=lambda x:(
            x.get("source") not in ("patternplus_unlocks","patternplus_calendar"),
            str(x.get("source_item_id"))))[:100]],
        "global_news_count":len(global_news),
        "global_news_selection_UNVERIFIED":[lead(x) for x in sorted(global_news,key=lambda x:(
            -led_score(x),str(x.get("event_id"))))[:100]],
        "caveat":"No automatic claim that market-wide context impacts each coin."}
    queue={"schema_version":"research-queue-v1","cutoff_utc":as_utc(cutoff),
           "delta_candidates":(deltas.get("triage_candidates") or [])[:120],
           "delta_count":deltas.get("triage_count",0),
           "event_candidates":(events.get("events") or [])[:120],
           "event_count":events.get("total_event_candidates",0),
           "warnings":["Short-interval deltas are noisy triage, NOT verified anomalies.",
              "Calendar rows are third-party schedules, NOT primary-confirmed unlocks.",
              "Sampled network transactions are NOT CMC100 token exchange flows.",
              "No coin score or future return may be inferred mechanically."]}
    manifest={"schema_version":"cmc100-v8-research-pack-v1",
              "status":"ALL_AVAILABLE_ARCHIVES_PARSED; COIN_CLAIM_VERIFICATION_PARTIAL",
              "cutoff_utc":as_utc(cutoff),"coin_cards":len(cards),
              "source_captures":{"market":market.get("snapshot_completed_utc"),
                  "engine":es.get("capture_utc"),"discovery":ds.get("capture_utc")},
              "sha_verified_archives":{"engine":ea,"discovery":da},
              "pit_record_filter":{"engine":es_filter,"discovery":ds_filter},
              "structured_partition":partition,
              "anchored_distinct_cmc_ids":sum(bool(exact[x]) for x in ids),
              "coin_anchoring_is_native_contract_verification":False,
              "discovery_search_leads_with_multiple_coin_queries":multi,
              "discovery_global_leads":len(global_news),
              "all_news_primary_claims_verified":False,
              "all_token_unlocks_venue_confirmed":False,
              "verified_9_out_of_10":False,
              "scope_note":"The full archives were parsed by the offline builder; the LLM only receives curated coin packets unless it explicitly reads full exported JSONL."}
    return {"cards":cards,"global":global_doc,"queue":queue,
            "manifest":manifest,"structured":struct,"discovery":news}

def publish(data,root=ROOT,out=None,full_export=True):
    root=Path(root).resolve();base=(Path(out) if out else root/OUT).resolve()
    coin_dir=base/"coin_batches";coin_dir.mkdir(parents=True,exist_ok=True)
    for x in coin_dir.glob("batch_*.json"):x.unlink()
    cards=sorted(data["cards"],key=lambda x:x["cmc_id"])
    batches=[]
    for start in range(0,100,20):
        path=coin_dir/("batch_%02d.json"%(start//20+1))
        write(path,{"schema_version":"cmc100-coin-batch-v1",
                    "coins":cards[start:start+20],
                    "count":len(cards[start:start+20])})
        batches.append({"path":str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
                        "sha256":sha(path),"count":20})
    write(base/"global_context.json",data["global"])
    write(base/"research_queue.json",data["queue"])
    m=data["manifest"];m["coin_batches"]=batches
    if full_export:
        export=base/"export";export.mkdir(parents=True,exist_ok=True)
        audits={}
        for key in ("structured","discovery"):
            p=export/(key+"_complete.jsonl")
            with p.open("w",encoding="utf8") as f:
                for row in data[key]:
                    f.write(json.dumps(row,ensure_ascii=False,separators=(",",":"),allow_nan=False)+"\n")
            audits[key]={"count":len(data[key]),"sha256":sha(p),"bytes":p.stat().st_size}
        m["full_text_export_for_actions_artifact"]=audits
    write(base/"manifest.json",m)
    return m

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",type=Path,default=ROOT)
    parser.add_argument("--cutoff",type=str)
    parser.add_argument("--no-full-export",action="store_true")
    args=parser.parse_args()
    fixed=moment(args.cutoff) if args.cutoff else None
    if args.cutoff and fixed is None:parser.error("invalid UTC cutoff")
    manifest=publish(build(args.root,fixed),args.root,full_export=not args.no_full_export)
    print(json.dumps({"coin_cards":manifest["coin_cards"],
          "archive_rows":{k:v["decompressed"] for k,v in manifest["sha_verified_archives"].items()},
          "structured_partition":manifest["structured_partition"],
          "anchored_coin_count":manifest["anchored_distinct_cmc_ids"],
          "exports":manifest.get("full_text_export_for_actions_artifact"),
          "status":manifest["status"]},indent=2))

if __name__=="__main__":main()
