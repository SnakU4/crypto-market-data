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

# Curated PROJECT-context hints, never proof of token economics or price impact.
# Source ID belongs to a known project repository or governance forum; verify
# each relationship before treating it as a direct token catalyst.
SOURCE_PROJECT_CONTEXT={
    "aave_blog":"AAVE",
    "aave_governance":"AAVE",
    "aave_v3_releases":"AAVE",
    "algorand_releases":"ALGO",
    "arbitrum_blog":"ARB",
    "arbitrum_governance":"ARB",
    "arbitrum_releases":"ARB",
    "arweave_releases":"AR",
    "axelar_releases":"AXL",
    "bnb_chain_releases":"BNB",
    "btc_core_notices":"BTC",
    "btc_core_releases":"BTC",
    "cardano_node_releases":"ADA",
    "celestia_releases":"TIA",
    "celo_releases":"CELO",
    "compound_releases":"COMP",
    "cosmos_blog":"ATOM",
    "cosmos_governance":"ATOM",
    "cosmos_releases":"ATOM",
    "cronos_releases":"CRO",
    "doge_releases":"DOGE",
    "eigenlayer_releases":"EIGEN",
    "ens_releases":"ENS",
    "eth_consensus_releases":"ETH",
    "eth_geth_releases":"ETH",
    "ethereum_blog":"ETH",
    "ethereum_governance":"ETH",
    "filecoin_releases":"FIL",
    "flare_releases":"FLR",
    "frax_releases":"FRAX",
    "graph_releases":"GRT",
    "hedera_releases":"HBAR",
    "helium_releases":"HNT",
    "icp_releases":"ICP",
    "injective_releases":"INJ",
    "iota_releases":"IOTA",
    "jupiter_releases":"JUP",
    "kaspa_releases":"KAS",
    "lido_governance":"LDO",
    "lido_releases":"LDO",
    "litecoin_releases":"LTC",
    "maker_governance":"SKY",
    "monero_releases":"XMR",
    "near_releases":"NEAR",
    "ondo_releases":"ONDO",
    "op_stack_releases":"OP",
    "optimism_blog":"OP",
    "optimism_governance":"OP",
    "optimism_releases":"OP",
    "osmosis_releases":"OSMO",
    "pancake_releases":"CAKE",
    "polkadot_blog":"DOT",
    "polkadot_governance":"DOT",
    "polkadot_releases":"DOT",
    "polygon_bor_releases":"POL",
    "polygon_core_releases":"POL",
    "polygon_heimdall_releases":"POL",
    "pyth_releases":"PYTH",
    "radix_releases":"XRD",
    "sei_releases":"SEI",
    "sky_governance":"SKY",
    "sol_agave_releases":"SOL",
    "solana_blog":"SOL",
    "solana_firedancer_releases":"SOL",
    "stacks_core_releases":"STX",
    "stacks_governance":"STX",
    "stellar_releases":"XLM",
    "synthetix_releases":"SNX",
    "tezos_releases":"XTZ",
    "ton_releases":"TON",
    "tron_releases":"TRX",
    "uniswap_blog":"UNI",
    "uniswap_governance":"UNI",
    "uniswap_v3_releases":"UNI",
    "uniswap_v4_releases":"UNI",
    "vechain_releases":"VET",
    "xrp_releases":"XRP",
    "zcash_governance":"ZEC",
    "zcash_releases":"ZEC",
    "zilliqa_releases":"ZIL",
    "zksync_releases":"ZK",
}

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

def load_full_research_events(root,research,status,cutoff):
    """Load EVERY direct source article from the SHA-checked source batches.

    Fails closed on incomplete/mismatched snapshots. Falls back to the old
    research read index only for historical repos / unit-test fixtures.
    """
    manifest_path=root/"docs/research/source_events_manifest.json"
    if not manifest_path.exists():
        return research.get("events") or [],{"mode":"LEGACY_READ_INDEX",
            "count":len(research.get("events") or [])}
    manifest=read(manifest_path)
    if manifest.get("capture_utc")!=status.get("capture_utc"):
        raise ValueError("research event batch capture does not match status")
    if parse_time(manifest["capture_utc"])>cutoff:
        raise ValueError("research batches after PIT cutoff")
    all_events=[]
    for entry in manifest.get("batches") or []:
        rel=entry.get("path")
        if not isinstance(rel,str) or not rel.startswith("docs/research/source_event_batches/"):
            raise ValueError("research source batch path unsafe")
        f=(root/rel).resolve()
        safe=(root/"docs/research/source_event_batches").resolve()
        if not f.is_relative_to(safe) or not f.is_file():
            raise ValueError("research source batch missing: "+str(rel))
        if digest(f)!=entry.get("sha256"):
            raise ValueError("research source batch SHA mismatch")
        batch=read(f)
        if batch.get("capture_utc")!=manifest["capture_utc"]:
            raise ValueError("research batch timestamp mismatch")
        events=batch.get("events") or []
        if len(events)!=entry.get("count"):
            raise ValueError("research event batch count mismatch")
        all_events+=events
    if len(all_events)!=manifest.get("total_events"):
        raise ValueError("research source batches total mismatch")
    if len(all_events)!=status.get("rss_events_stored"):
        raise ValueError("research status and full source events disagree")
    return all_events,{"mode":"FULL_SHA_VERIFIED_BATCHES","count":len(all_events),
        "batch_count":len(manifest["batches"])}


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
            "excerpt":clip(e.get("excerpt"),1000),
            "context_origin":e.get("context_origin") or "UNSPECIFIED","published_utc":e.get("published_utc"),
            "first_observed_utc":e.get("first_observed_utc") or e.get("observed_utc"),
            "scope":scope,"candidate_cmc_ids":sorted(set(ids)),
            "themes":sorted(set(map(str,themes))),"identity_status":"SEARCH_OR_TEXT_CANDIDATE_NOT_VERIFIED" if ids else "NO_ASSET_LINK_ASSERTED",
            "claim_status":"NOT_INDEPENDENTLY_VERIFIED",
            "source_family":e.get("source_family") or (e.get("source_families") or ["UNSPECIFIED"])[0],
            "source_id":e.get("source_id") or (e.get("source_ids") or [None])[0],
            "priority":priority(e)}

def load_manual_findings(root,cutoff,known_cmc_ids):
    """Optional, append-only human/ChatGPT-verified leads re-enter the next pack.

    Source verification *claims* are retained as user annotations, not
    accepted as independent machine validation. Historical PIT inclusion
    is governed by the FIRST time evidence became available to research.
    """
    path=root/"docs/intelligence/manual_inputs/findings.jsonl"
    if not path.exists():return [],{"rows":0,"eligible":0,"post_cutoff":0}
    rows=[];total=0;post=0;ids=set()
    valid_scopes={"GLOBAL","SECTOR","ASSET","MULTI_ASSET","UNRESOLVED"}
    with path.open(encoding="utf-8") as f:
        for n,line in enumerate(f,1):
            if not line.strip():continue
            total+=1
            if total>10000:raise ValueError("manual findings unbounded")
            item=json.loads(line)
            if not isinstance(item,dict):raise ValueError("manual nonobject line "+str(n))
            rid=str(item.get("id") or "")
            url=str(item.get("source_url") or "")
            title=clip(item.get("title"),230)
            excerpt=clip(item.get("source_excerpt"),650)
            scope=item.get("scope")
            first=parse_time(item.get("first_observed_utc"))
            published=parse_time(item.get("published_utc")) if item.get("published_utc") else None
            if not rid or not title or not url.startswith("https://") or scope not in valid_scopes or not first:
                raise ValueError("manual finding missing required provenance, line "+str(n))
            if rid in ids:raise ValueError("manual finding id duplicated: "+rid)
            ids.add(rid)
            if first>cutoff or (published and published>cutoff):
                post+=1;continue
            cmc_ids=[]
            for x in item.get("cmc_ids") or []:
                if not str(x).isdigit() or int(x) not in known_cmc_ids:
                    raise ValueError("manual unknown CMC ID in "+rid)
                cmc_ids.append(int(x))
            if scope in ("ASSET","MULTI_ASSET") and not cmc_ids:
                raise ValueError("manual ASSET scope missing CMC ID: "+rid)
            if scope=="MULTI_ASSET" and len(set(cmc_ids))<2:
                raise ValueError("MULTI_ASSET requires at least two CMC IDs: "+rid)
            rows.append({"id":"M:"+rid,"source_plane":"manual",
               "title":title,"url":url,"excerpt":excerpt,
               "published_utc":item.get("published_utc"),"first_observed_utc":item["first_observed_utc"],
               "scope":("ASSET_CANDIDATE" if scope in ("ASSET","MULTI_ASSET") else
                        "SECTOR" if scope=="SECTOR" else "GLOBAL_UNRESOLVED"),
               "manual_scope":scope,"candidate_cmc_ids":sorted(set(cmc_ids)),
               "themes":[clip(x,60) for x in (item.get("themes") or [])],
               "identity_status":"MANUAL_MAPPING_ASSERTED_NOT_AUTOMATICALLY_VERIFIED" if cmc_ids else "NO_ASSET_LINK_ASSERTED",
               "claim_status":"MANUAL_RESEARCH_SOURCE_ANNOTATION_RECHECK_REQUIRED",
               "source_family":"MANUAL_RESEARCH","source_id":str(item.get("reviewer") or "chatgpt_manual"),
               "priority":70,"provenance_ids":["M:"+rid],
               "source_note":clip(item.get("verification_note"),500)})
    return rows,{"rows":total,"eligible":len(rows),"post_cutoff":post}

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

def keyword_pairs(events,planes=("adjacent","research")):
    """Source-derived discoveries only. No hardwired sector taxonomy or predicted alpha."""
    scores=collections.defaultdict(lambda:{"sources":set(),"examples":[],"theme":set()})
    for e in events:
        if e["source_plane"] not in planes:continue
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
        add('"'+str(a["name"]).replace('"',"")+'" crypto when:2d',
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

def second_hop_tasks(first_results,earlier_tasks,limit=8):
    """A second search direction is mined from returned stories, not hardcoded."""
    existing=" ".join(t["query"].lower() for t in earlier_tasks)
    tasks=[];known=set()
    for p in keyword_pairs(first_results,planes=("adaptive",)):
        term=p["term"]
        if term in existing or term in known or len(tasks)>=limit:continue
        # Multiple independent result URLs are still *leads*, not independent proof.
        known.add(term)
        query='"'+term+'" crypto blockchain when:2d'
        tasks.append({"task_id":"T:"+hashlib.sha256(query.encode()).hexdigest()[:12],
          "query":query,"scope":"GLOBAL_OR_SECTOR",
          "trigger":"SECOND_HOP_FROM_NEW_FINDINGS","evidence_ids":p["examples"],
          "status":"PLANNED","results":0})
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
                        "first_observed_utc":iso(dt.datetime.now(UTC)),"scope":t["scope"],
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

def publisher_excerpt_useful(title,text):
    """Reject obvious generic web-UI noise masquerading as article substance."""
    try:from discovery_quality import has_additional_information
    except ImportError:from src.discovery_quality import has_additional_information
    value=str(text or "").casefold()
    noise=("sorry, something went wrong","filter loading","loading uh oh",
           "sign in to view","enable javascript to continue")
    if sum(value.count(x) for x in noise)>=2:return False
    return has_additional_information(title,text)


def enrich_direct(events,budget=64,fetcher=None,skip_urls=()):
    """Try multiple publisher URLs per host; attach auditable short excerpts.

    Independent *content* is the goal, not raw URL volume. The full source
    remains linked, while only a bounded quotation/context is copied.
    """
    if budget<=0:return [],{"attempted":0,"succeeded":0,"substantive":0,"by_scope":{},
                          "selected_urls":[]}
    if fetcher is None:
        try:from discovery_quality import extract_article as fetcher
        except ImportError:from src.discovery_quality import extract_article as fetcher
    try:from discovery_quality import has_additional_information
    except ImportError:from src.discovery_quality import has_additional_information
    from concurrent.futures import ThreadPoolExecutor
    def article_priority(e):
        published=parse_time(e.get("published_utc") or e.get("first_observed_utc"))
        return (-e["priority"], -(published.timestamp() if published else 0), e["id"])
    ordered=sorted((e for e in events if e.get("url","").startswith("https://")
      and "news.google." not in urllib.parse.urlsplit(e["url"]).netloc
      and e["url"] not in skip_urls
      and not publisher_excerpt_useful(e["title"],e["excerpt"])),
      key=article_priority)
    # Select publisher links from UNCOVERED individual coins first. The old
    # scope-round-robin gave only ~1/3 of the 80 attempts to assets, although
    # a >50-coin context gap remained. Selection is not a semantic verification.
    already_rich={cid for e in events
        if has_additional_information(e["title"],e["excerpt"])
        for cid in e.get("candidate_cmc_ids") or []}
    by_coin=collections.defaultdict(list)
    groups=collections.defaultdict(list)
    for e in ordered:
        groups[e["scope"]].append(e)
        if e["scope"]=="ASSET_CANDIDATE":
            for cid in e.get("candidate_cmc_ids") or []:
                by_coin[cid].append(e)
    selected=[];host_counts=collections.Counter();used=set()
    selected_coin_ids=set()
    def take(e):
        host=urllib.parse.urlsplit(e["url"]).hostname
        if not host or host_counts[host]>=5 or e["url"] in used:
            return False
        host_counts[host]+=1;used.add(e["url"]);selected.append(e)
        selected_coin_ids.update(e.get("candidate_cmc_ids") or [])
        return True
    coin_order=sorted(by_coin, key=lambda cid:(cid in already_rich,len(by_coin[cid]),cid))
    asset_target=max(1,int(budget*.80))
    # Two passes: reach as many undercovered assets as possible, then deepen.
    for pass_id in (0,1):
        if len(selected)>=asset_target:break
        for cid in coin_order:
            if len(selected)>=asset_target:break
            if pass_id==0 and cid in selected_coin_ids:continue
            for e in by_coin[cid]:
                if take(e):break
    # Preserve cross-sector and global evidence, then use any spare capacity
    # for further coin-relevant publisher articles.
    for scope in ("SECTOR","GLOBAL_UNRESOLVED"):
        for e in groups[scope]:
            if len(selected)>=budget:break
            if len([x for x in selected if x["scope"]==scope])>=max(1,int(budget*.1)):break
            take(e)
    for e in ordered:
        if len(selected)>=budget:break
        take(e)
    def get(e):
        try:return fetcher(e["url"])
        except (OSError,ValueError,TimeoutError):return None
    with ThreadPoolExecutor(max_workers=6) as pool:
        retrieved=list(pool.map(get,selected))
    out=[];by_scope=collections.Counter()
    for e,raw in zip(selected,retrieved):
        if not raw or not publisher_excerpt_useful(e["title"],raw):continue
        excerpt=clip(raw,650)
        if not publisher_excerpt_useful(e["title"],excerpt):continue
        out.append({"evidence_id":e["id"],"url":e["url"],"scope":e["scope"],
            "source_excerpt":excerpt,"content_origin":"DIRECT_PUBLISHER_PUBLIC_ARTICLE",
            "verification":"TEXT_EXTRACTED_NOT_FACT_VERIFIED",
            "fetched_utc":iso(dt.datetime.now(UTC))})
        by_scope[e["scope"]]+=1
    mapped_substantive={cid for e in selected for cid in (e.get("candidate_cmc_ids") or [])
        if e["id"] in {x["evidence_id"] for x in out}}
    return out,{"attempted":len(selected),"succeeded":sum(bool(x) for x in retrieved),
                "substantive":len(out),"by_scope":dict(by_scope),
                "candidate_coins_targeted":len(selected_coin_ids),
                "candidate_coins_with_substantive_publisher_excerpt":len(mapped_substantive),
                "selection_policy":"PREFER_UNCOVERED_COINS_THEN_SECTOR_AND_GLOBAL",
                "selected_urls":[e["url"] for e in selected]}


def build(root=ROOT,out=None,cutoff=None,network=False,max_followups=22,max_articles=16,
          fetcher=None,search_opener=None,live_collection=False):
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
    direct_events,direct_events_audit=load_full_research_events(root,research,rs,cutoff)
    adjacent=usable_json(root,"docs/discovery/latest.json",ds["capture_completed_utc"],cutoff)
    # The adjacent /discovery/latest.json is only a 500-event read index.
    # Preserve the entire immutable archive (~938 events) when available.
    adjacent_source={"mode":"READ_INDEX_ONLY","records":len(adjacent.get("events") or [])}
    raw_adj=ds.get("full_archive_path")
    if raw_adj:
        ap=(root/raw_adj).resolve()
        safe=(root/"docs/discovery/archive").resolve()
        if not ap.is_relative_to(safe) or not ap.is_file():
            raise ValueError("adjacent immutable archive missing or path escaped")
        adjacent_full=read(ap)
        full_count=len(adjacent_full.get("events") or [])
        if full_count!=int(ds.get("full_archive_leads",full_count)):
            raise ValueError("adjacent archive count mismatch")
        adjacent=adjacent_full
        adjacent_source={"mode":"FULL_ARCHIVE","records":full_count,
                         "path":raw_adj,"sha256":digest(ap)}
    valid_ids=set(ids)
    # Independently collected source-backed PROJECT BACKGROUND. No fabricated
    # catalysts or title-only leads: retain missing data and provenance.
    try:from coin_context_sources import collect_profiles
    except ImportError:from src.coin_context_sources import collect_profiles
    profile_doc,profile_audit=collect_profiles(root,assets,cutoff,
        network=bool(network and live_collection))
    try:from targeted_primary_context import collect as collect_primary_context
    except ImportError:from src.targeted_primary_context import collect as collect_primary_context
    primary_doc,primary_audit=collect_primary_context(root,assets,cutoff,
        network=bool(network and live_collection))
    all_events=[]
    for kind,rows in (("expanded",xr),("research",direct_events),
                      ("adjacent",adjacent.get("events") or [])):
        for e in rows:
            z=event_doc(kind,e,cutoff)
            if z:
                z["candidate_cmc_ids"]=[i for i in z["candidate_cmc_ids"] if i in valid_ids]
                all_events.append(z)
    manual,manual_status=load_manual_findings(root,cutoff,valid_ids)
    dynamic_events=[];dynamic_audit={"domains_attempted":0,"domains_found_content":0,
                                     "new_feed_items":0,"substantive_feed_items":0,"sources":[]}
    history_file=root/"docs/intelligence/source_probe_history.json"
    probe_history=read(history_file) if history_file.exists() else {}
    if not isinstance(probe_history,dict):raise ValueError("malformed source probe history")
    cooldown_domains=[]
    for domain,entry in probe_history.items():
        when=parse_time(entry.get("last_probed_utc")) if isinstance(entry,dict) else None
        if when and dt.timedelta(0)<=cutoff-when<=dt.timedelta(hours=72):
            cooldown_domains.append(domain)
    # Only LIVE runs discover new publisher feeds. Historical research must never
    # fetch today's web and silently backdate it to a prior forecast cutoff.
    if network and live_collection:
        previous_registry=root/"docs/intelligence/source_registry_proposals.json"
        if previous_registry.exists():
            try:from primary_source_discovery import discover
            except ImportError:from src.primary_source_discovery import discover
            dynamic_events,dynamic_audit=discover(read(previous_registry),iso(cutoff),
                max_sites=14,skip_domains=cooldown_domains,
                known_feed_urls=[entry["url"] for entry in research.get("source_catalog",[])
                    if entry.get("kind")=="rss" and entry.get("url")])
            observed_at=iso(dt.datetime.now(UTC))
            for entry in dynamic_audit.get("sources",[]):
                probe_history[entry["domain"]]={
                    "last_probed_utc":observed_at,"home_status":entry.get("home_status"),
                    "feed_status":entry.get("feed_status"),
                    "substantive":entry.get("substantive",0),
                    "article_count":entry.get("article_count",0)}
    dynamic_audit["domain_cooldown_hours"]=72
    dynamic_audit["domains_skipped_due_to_recent_probe"]=len(cooldown_domains)
    events=deduplicate(all_events+manual+dynamic_events)
    # Feed-provided descriptions and newly retrieved publisher text are BOTH
    # first-class research context. Previously the latter was exported but
    # never fed back into coin/global/sector dossiers or the quality metric.
    # Persistent, timestamped publisher context accumulates across runs.
    # Avoid re-fetching the same 80 headlines on every scheduled execution.
    pub_path=root/"docs/intelligence/publisher_excerpts.json"
    earlier_pub=read(pub_path).get("items",[]) if pub_path.is_file() else []
    event_index={e["id"]:e for e in events}
    earlier_good=[]
    for item in earlier_pub:
        if not isinstance(item,dict):continue
        original=event_index.get(item.get("evidence_id"))
        fetched=parse_time(item.get("fetched_utc"))
        # Old cache records without a fetch timestamp can be used on live
        # runs, never when replaying a historical point-in-time cutoff.
        if not original or item.get("url")!=original.get("url"):continue
        if not (fetched and fetched<=cutoff or live_collection and (fetched is None or fetched<=dt.datetime.now(UTC))):
            continue
        if not publisher_excerpt_useful(original["title"],item.get("source_excerpt")):
            continue
        earlier_good.append(item)
        original["excerpt"]=item["source_excerpt"]
        original["context_origin"]="CACHED_DIRECT_PUBLISHER_PUBLIC_ARTICLE"
    attempts_path=root/"docs/intelligence/article_attempt_history.json"
    past_attempts=read(attempts_path).get("attempts",{}) if attempts_path.is_file() else {}
    if not isinstance(past_attempts,dict):past_attempts={}
    skip_urls=set()
    if live_collection:
        for url,when in past_attempts.items():
            t=parse_time(when)
            if t and dt.timedelta(0)<=cutoff-t<=dt.timedelta(hours=72):
                skip_urls.add(url)
    new_article,article_audit=enrich_direct(events,max_articles if network else 0,
        fetcher,skip_urls=skip_urls)
    observed=iso(dt.datetime.now(UTC))
    for url in article_audit.pop("selected_urls",[]):
        past_attempts[url]=observed
    retention_now=dt.datetime.now(UTC)
    past_attempts={url:when for url,when in past_attempts.items()
        if parse_time(when) and dt.timedelta(0)<=retention_now-parse_time(when)<=dt.timedelta(days=35)}
    article_by_id={x["evidence_id"]:x for x in earlier_good+new_article}
    article=list(article_by_id.values())
    article_audit["cached_substantive_reused"]=len(earlier_good)
    article_audit["cumulative_substantive_current_corpus"]=len(article)
    for e in events:
        detail=article_by_id.get(e["id"])
        if detail:
            e["excerpt"]=detail["source_excerpt"]
            e["context_origin"]=detail["content_origin"]
            e["article_text_attribution"]=detail["url"]
            e["article_text_verification"]=detail["verification"]
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
    quarantined_structured=0
    global_structured_counts=collections.Counter()
    global_structured_samples=collections.defaultdict(list)
    for e in er:
        cid=e.get("cmc_id") or e.get("candidate_cmc_id")
        if not is_before(e,cutoff):continue
        if cid not in valid_ids:
            family=str(e.get("source") or "UNSPECIFIED")
            global_structured_counts[family]+=1
            if len(global_structured_samples[family])<8:
                global_structured_samples[family].append({
                    "evidence_id":e.get("observation_id"),
                    "source":family,
                    "observed_utc":e.get("observed_utc"),
                    "network_context_cmc_id":e.get("network_context_cmc_id"),
                    "network_context_is_not_verified_token_flow":True,
                    "metrics":e.get("metrics") or {}})
            continue
        if cid==QNT_ID and str(e.get("source") or "").startswith("okx_"):
            quarantined_structured+=1
            continue
        structured[cid][str(e.get("source") or "UNSPECIFIED")]+=1
        if len(struct_references[cid])<12:
            struct_references[cid].append({"ref":e.get("observation_id"),
               "source":e.get("source"),"identity_status":e.get("coin_identity_status")})
    # Expose directly collected protocol publications to corresponding
    # project dossiers WITHOUT converting project activity into token alpha.
    symbol_to_id={str(a["symbol"]):int(a["cmc_id"]) for a in assets}
    project_context=collections.defaultdict(list)
    seen_project_urls=collections.defaultdict(set)
    try:from discovery_quality import has_additional_information
    except ImportError:from src.discovery_quality import has_additional_information
    for row in direct_events:
        symbol=SOURCE_PROJECT_CONTEXT.get(row.get("source_id"))
        cid=symbol_to_id.get(symbol)
        if cid is None or not is_before(row,cutoff):continue
        url=str(row.get("url") or "")
        if not url or url in seen_project_urls[cid]:continue
        seen_project_urls[cid].add(url)
        project_context[cid].append({
            "title":clip(row.get("headline"),230),"url":url,
            "source_id":row.get("source_id"),
            "published_utc":row.get("published_utc"),
            "first_observed_utc":row.get("first_observed_utc"),
            "excerpt":clip(row.get("excerpt"),850),
            "has_substantive_context":has_additional_information(
                row.get("headline"),row.get("excerpt")),
            "relation_status":"CURATED_PROJECT_CONTEXT_NOT_VERIFIED_TOKEN_EFFECT"})
    for rows in project_context.values():
        rows.sort(key=lambda x:x.get("published_utc") or "",reverse=True)
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
        valid_perp=bool(perp.get("symbol") and perp.get("mapping")=="EXACT_BASE_ASSET_OKX" and not denied)
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
        background=profile_doc["profiles"].get(str(cid))
        primary_source=primary_doc["profiles"].get(str(cid))
        issuer_source=bool(primary_source and primary_source.get("substantive") and
            primary_source.get("source_kind")=="ISSUER_DOCUMENTATION")
        context_origins=[]
        if background and background.get("has_substantive_descriptive_context"):
            context_origins.append("EXACT_MATCH_PUBLIC_COIN_PROFILE")
        if issuer_source:
            context_origins.append("EXACT_CURATED_PROJECT_ORIGINAL_DOCUMENTATION")
        elif primary_source and primary_source.get("substantive"):
            context_origins.append("EXACT_CURATED_EXCHANGE_LISTING_NOT_ISSUER_DOCUMENTATION")
        if background and any(e.get("has_substantive_event_details")
                              for e in background.get("coin_events",[])):
            context_origins.append("EXACT_MATCH_THIRD_PARTY_DATED_EVENT_DESCRIPTION")
        if any(row.get("has_substantive_context") for row in project_context[cid]):
            context_origins.append("CURATED_PROJECT_PUBLICATION_NOT_TOKEN_EFFECT_VERIFIED")
        card={
            "source_backed_project_profile":background,
            "targeted_project_primary_context":primary_source,
            "substantive_original_issuer_context":issuer_source,
            "substantive_coin_specific_context_present":bool(context_origins),
            "substantive_coin_specific_context_origins":context_origins,
            "source_backed_project_profile_substantive":bool(
                background and background.get("has_substantive_descriptive_context")),
            "cmc_id":cid,"name":a["name"],"symbol":a["symbol"],
            "cmc100_weight":a.get("cmc100_weight"),"spot_quote":q,
            "perpetual":perp if valid_perp else None,
            "perp_market":a.get("perp_market") if valid_perp else None,
            "perp_identity_status":"QUARANTINED" if denied else
               "EXCHANGE_SYMBOL_MATCH_NOT_INDEPENDENT_CONTRACT_VERIFICATION" if valid_perp else "NOT_MATCHED_OR_UNVERIFIED",
            "research_coin_features":{k:v for k,v in original.items()
                if k not in (("research_event_candidate_ids","perp_oi_usd",
                             "perp_funding_estimate","okx_orderbook_spread_bps",
                             "okx_orderbook_top5_ask_usd","okx_orderbook_top5_bid_usd",
                             "perp_exchange","perp_oi_change_24h_pct") if denied else
                            ("research_event_candidate_ids","perp_oi_usd",
                             "perp_funding_estimate","okx_orderbook_spread_bps",
                             "okx_orderbook_top5_ask_usd","okx_orderbook_top5_bid_usd"))},
            "quantitative_research_families":ff,
            "engine_record_counts_by_source":dict(structured[cid]),
            "engine_provenance_sample":struct_references[cid],
            "project_protocol_context_total":len(project_context[cid]),
            "project_protocol_context_substantive_count":sum(
                bool(x["has_substantive_context"]) for x in project_context[cid]),
            "project_protocol_context_NOT_TOKEN_SIGNAL":project_context[cid][:12],
            "candidate_event_count":len(by_asset[cid]),
            "candidate_events_NOT_VERIFIED":[{k:e[k] for k in
                ("id","title","url","excerpt","published_utc","claim_status","identity_status")}
                for e in select],
            "missing_data":[key for key,ok in (("cmc_spot",bool(q.get("price_usd"))),
                            ("mapped_perp_research_proxy",valid_perp),
                            ("mapped_protocol_fundamentals",bool(ff)),
                            ("coin_relevant_article_text",any(len(e["excerpt"])>=150 for e in by_asset[cid])),
                            ("source_backed_coin_description",bool(
                                (background and background.get("has_substantive_descriptive_context"))
                                or issuer_source)))
                             if not ok]
        }
        cards.append(card)
    emergent=keyword_pairs(events)
    # Open provider discovery: candidate publisher domains are harvested from
    # ALL real URLs, not restricted to a static hand-authored source register.
    provider_domains=collections.defaultdict(lambda:{"count":0,"examples":[],"scopes":collections.Counter(),"source_planes":set()})
    for e in events:
        host=(urllib.parse.urlsplit(e["url"]).hostname or "").lower().removeprefix("www.")
        if not host or host.endswith("google.com") or host.endswith("google.co.uk"):
            continue
        z=provider_domains[host];z["count"]+=1
        z["scopes"][e["scope"]]+=1;z["source_planes"].add(e["source_plane"])
        if len(z["examples"])<3:z["examples"].append({"evidence_id":e["id"],"url":e["url"]})
    source_proposals=[{"domain":host,"lead_count":z["count"],
                       "source_plane_count":len(z["source_planes"]),
                       "scopes":dict(z["scopes"]),"examples":z["examples"],
                       "status":"DISCOVERED_PUBLISHER_CANDIDATE_NOT_AUTOMATICALLY_TRUSTED"}
                      for host,z in sorted(provider_domains.items(),key=lambda x:(-x[1]["count"],x[0]))[:100]]
    tasks=research_tasks(cards,events,market,max_followups)
    if network and max_followups>0:
        first_count=max(1,int(max_followups*0.65))
        first=tasks[:first_count]
        a1,r1=adaptive_fetch(first,cutoff,len(first),opener=search_opener)
        fresh=second_hop_tasks(a1,first,max_followups-first_count)
        leftovers=tasks[first_count:first_count+max(0,max_followups-first_count-len(fresh))]
        a2,r2=adaptive_fetch(fresh+leftovers,cutoff,max_followups-first_count,opener=search_opener)
        tasks=first+fresh+leftovers
        adaptive,audit=a1+a2,r1+r2
        search_hops=2 if fresh else 1
    else:
        adaptive,audit=[],[]
        search_hops=0
    # New web results from a historical replay are NOT part of information
    # known by that historical cutoff; retain the query audit only.
    if not live_collection:
        adaptive=[e for e in adaptive if is_before(e,cutoff)]
    for e in adaptive:e["provenance_ids"]=[e["id"]]
    evidence=events+adaptive
    sectors=[{"theme":k,"lead_count":len(v),
              "sample":[{x:e[x] for x in ("id","title","url","excerpt","published_utc","claim_status")}
                        for e in sorted(v,key=lambda e:-e["priority"])[:10]]}
             for k,v in sorted(sector.items(),key=lambda z:(-len(z[1]),z[0]))]
    global_research_families={}
    for k,rows in fam.items():
        if isinstance(rows,list):
            unattached=[z for z in rows if isinstance(z,dict) and z.get("cmc_id") not in valid_ids]
            if unattached:
                global_research_families[k]={"observations":len(unattached),
                                            "sample":unattached[:40],
                                            "scope":"GLOBAL_OR_NETWORK_STATE_NOT_TOKEN_FLOW"}
        elif isinstance(rows,dict):
            global_research_families[k]={"scope":"GLOBAL_STATE","observation":rows}
    # Freeze a live snapshot only AFTER source and adaptive network collection.
    # This avoids claiming evidence first seen during the run was known earlier.
    if live_collection:cutoff=dt.datetime.now(UTC)
    g={"cutoff_utc":iso(cutoff),"market_context":market.get("market_context"),
       "global_research_quantitative_families":global_research_families,
       "unassigned_structured_counts_by_source":dict(global_structured_counts),
       "unassigned_structured_samples_by_source":dict(global_structured_samples),
       "unassigned_observations_remain_available_in_source_archive":True,
       "global_unresolved_leads":len(glob),
       "headline_only_claims_are_NOT_verified":True,
       "global_research_sample":[{x:e[x] for x in ("id","title","url","excerpt","published_utc","claim_status")}
                                 for e in sorted(glob,key=lambda e:-e["priority"])[:75]],
       "adaptive_followups":[{k:t[k] for k in ("task_id","query","scope","status","results")}
                             for t in tasks],
       "adaptive_discovery_findings":[{k:e[k] for k in ("id","title","url","published_utc","scope")}
                                      for e in adaptive[:100]]}
    try:
        from discovery_quality import has_additional_information
    except ImportError:
        from src.discovery_quality import has_additional_information
    # Manual research bridge: a genuinely richer, broad-context queue.
    # Its 200-300 items are a SELECTION, never substituted for the full-corpus
    # denominator or represented as independently validated facts.
    rich=[e for e in events if has_additional_information(e["title"],e["excerpt"])]
    rich_by_scope=collections.defaultdict(list)
    for e in rich:rich_by_scope[e["scope"]].append(e)
    for group in rich_by_scope.values():
        def order_key(e):
            t=parse_time(e["published_utc"] or e["first_observed_utc"])
            age=(cutoff-t).total_seconds()/3600 if t else 99999
            # Prioritize new substantive material, not obsolete releases.
            return (0 if age<=72 else 1 if age<=168 else 2,
                    -e["priority"],-t.timestamp() if t else 0,e["id"])
        group.sort(key=order_key)
    selected_context=[];source_counters=collections.Counter()
    while len(selected_context)<300:
        moved=False
        for scope in ("GLOBAL_UNRESOLVED","SECTOR","ASSET_CANDIDATE"):
            group=rich_by_scope[scope]
            for i,e in enumerate(group):
                src=e["source_id"] or e["source_plane"]
                if source_counters[str(src)]>=18:continue
                group.pop(i)
                selected_context.append(e);source_counters[str(src)]+=1
                moved=True
                break
            if len(selected_context)>=300:break
        if not moved:break
    manual_context={
      "selection_size":len(selected_context),
      "selection_is_not_full_corpus":True,
      "global_sector_coins_all_preserved_in_full_archive":True,
      "notes":"Short original-source passages for guided research, NOT verified factual claims.",
      "items":[{k:e.get(k) for k in ("id","source_plane","source_id","title",
               "url","excerpt","scope","candidate_cmc_ids","themes",
               "published_utc","first_observed_utc","claim_status","identity_status",
               "provenance_ids","context_origin")} for e in selected_context],
      "background_profile_gaps":profile_audit["profile_gaps"],
      "background_context_is_not_fresh_news":True,
      "undercovered_coins":[{"cmc_id":a["cmc_id"],"symbol":a["symbol"],
            "reason":"No substantively contextual asset-specific source in current collection"}
            for a in assets if not any(e["candidate_cmc_ids"] and a["cmc_id"] in e["candidate_cmc_ids"]
                    for e in rich)]
    }

    effective_project_gaps=[{"cmc_id":x["cmc_id"],"symbol":x["symbol"],"name":x["name"]}
        for x in assets if not (
            profile_doc["profiles"].get(str(x["cmc_id"]),{}).get("has_substantive_descriptive_context")
            or primary_doc["profiles"].get(str(x["cmc_id"]),{}).get("source_kind")=="ISSUER_DOCUMENTATION"
            and primary_doc["profiles"].get(str(x["cmc_id"]),{}).get("substantive"))]
    # Observe the true information quality by access type. Do NOT improve
    # the full-corpus rate merely by excluding low-context headlines.
    source_depth=collections.defaultdict(lambda:{"total":0,"substantive":0,
        "feed_summary_count":0,"article_extract_count":0,"domains":set(),
        "published_last_24h":0,"published_last_72h":0,"substantive_published_last_72h":0,
        "published_date_missing":0})
    by_source_id=collections.defaultdict(lambda:{"total":0,"substantive":0})
    for e in events:
        host=(urllib.parse.urlsplit(e.get("url") or "").hostname or "").lower()
        typ="GOOGLE_NEWS_AGGREGATOR" if host.startswith("news.google.") else "DIRECT_SOURCE"
        key=e["source_plane"]+":"+typ
        d=source_depth[key]
        d["total"]+=1
        is_sub=has_additional_information(e["title"],e["excerpt"])
        d["substantive"]+=int(is_sub)
        when=parse_time(e.get("published_utc"))
        if when is None:
            d["published_date_missing"]+=1
        else:
            age=(cutoff-when).total_seconds()
            if 0<=age<=86400:d["published_last_24h"]+=1
            if 0<=age<=72*3600:
                d["published_last_72h"]+=1
                d["substantive_published_last_72h"]+=int(is_sub)
        d["feed_summary_count"]+=int(e.get("context_origin")=="PUBLISHER_FEED_SUMMARY")
        d["article_extract_count"]+=int(e.get("context_origin")=="DIRECT_PUBLISHER_PUBLIC_ARTICLE")
        if host:d["domains"].add(host)
        z=by_source_id[str(e.get("source_id") or e.get("source_family") or "UNSPECIFIED")]
        z["total"]+=1
        z["substantive"]+=int(is_sub)
    research_base=source_depth["research:DIRECT_SOURCE"]
    source_context_audit={
        "by_plane_and_access_type":{
            k:{**{a:v for a,v in x.items() if a!="domains"},
               "distinct_source_domains":len(x["domains"])}
            for k,x in sorted(source_depth.items())},
        "by_source_id":dict(sorted(by_source_id.items(),
            key=lambda x:(-x[1]["substantive"],-x[1]["total"],x[0]))),
        "direct_research_substantive_ratio":round(
            research_base["substantive"]/research_base["total"],4)
            if research_base["total"] else None,
        "direct_research_substantive_count":research_base["substantive"],
        "direct_research_total":research_base["total"],
        "disclaimer":"Substantive source text, not verified 24h causal evidence."}
    coverage={
      "official_assets":100,"source_planes_integrated":["market","evidence_engine",
          "expanded_discovery","research","adjacent_discovery"],
      "source_capture_utc":caps,
      "evidence_counts":{"engine_rows":len(er),"expanded_rows":len(xr),
          "research_event_rows":len(direct_events),
          "new_source_discovery_items":len(dynamic_events),
          "manual_verified_source_annotations_loaded":manual_status["eligible"],
          "adjacent_full_event_rows":len(adjacent.get("events") or []),
          "adjacent_read_index_event_rows":int(ds.get("read_index_leads") or adjacent_source["records"]),
          "integrated_event_rows_before_dedup":len(all_events),
          "canonical_research_leads":len(events),
          "free_adaptive_followup_leads":len(adaptive),
          "substantive_source_excerpt_leads":sum(has_additional_information(e["title"],e["excerpt"]) for e in events),
          "long_excerpts_by_character_count_not_claim_verification":sum(len(e["excerpt"])>=140 for e in events),
          "non_asset_structured_market_and_network_observations":sum(global_structured_counts.values()),
          "global_research_quantitative_data_families":len(global_research_families),
          "direct_publisher_article_excerpts":len(article),
          "direct_publisher_article_fetch_attempted":article_audit["attempted"],
          "manual_high_context_selection_count":len(selected_context)},
      "per_coin":{"spot_prices":sum(bool((a.get("cmc_quote") or {}).get("price_usd")) for a in assets),
          "perp_markets_unquarantined":sum(bool((a.get("perpetual") or {}).get("symbol")) and
               (a.get("perpetual") or {}).get("mapping")=="EXACT_BASE_ASSET_OKX" and
               (int(a["cmc_id"]),str((a.get("perpetual") or {}).get("symbol") or "")) not in DENY_EXCHANGE for a in assets),
          "any_mapped_research_family_including_reported_supply":sum(bool(family_by_coin[i]) for i in ids),
          "research_mapped_quantitative_families_beyond_supply_and_trending":
              sum(any(x["family"] not in ("token_supply","trending","okx_orderbooks") for x in family_by_coin[i]) for i in ids),
          "candidate_news_links":sum(bool(by_asset[i]) for i in ids),
          "third_party_coin_profiles_available":profile_audit["profile_present"],
          "curated_issuer_docs_substantive":primary_audit["substantive_issuer_dossiers"],
          "curated_exchange_only_docs_substantive":primary_audit["substantive_exchange_only_dossiers"],
          "coins_with_substantive_project_background_combined":100-len(effective_project_gaps),
          "coins_missing_substantive_project_background_combined":len(effective_project_gaps),
          "coins_with_substantive_coin_specific_context":sum(
              x["substantive_coin_specific_context_present"] for x in cards),
          "coins_missing_substantive_coin_specific_context":sum(
              not x["substantive_coin_specific_context_present"] for x in cards),
          "coins_with_substantive_dated_third_party_events":
              profile_audit["coins_with_substantive_dated_event_details"],
          "coins_with_public_cross_exchange_market_data":
              profile_audit["coins_with_cross_exchange_market_observations"],
          "source_backed_substantive_project_background":profile_audit["substantive_project_profiles"],
          "coins_without_substantive_project_background":len(profile_audit["profile_gaps"]),
          "coins_with_substantive_coinspecific_article_context":100-len(manual_context["undercovered_coins"]),
          "coins_without_substantive_coinspecific_article_context":len(manual_context["undercovered_coins"]),
          "coins_with_curated_project_source_context":sum(bool(project_context[i]) for i in ids),
          "coins_with_substantive_project_source_context":sum(
              any(x["has_substantive_context"] for x in project_context[i]) for i in ids),
          "project_source_hint_caveat":"Project affiliation is contextual, NOT independent verification of token-price impact."},
      "direct_research_full_source_audit":direct_events_audit,
      "new_public_source_discovery_audit":dynamic_audit,
      "identity_quarantine":quarantined,
      "manual_research_evidence_input":manual_status,
      "excluded_ambiguous_okx_structured_records":quarantined_structured,
      "adjacent_discovery_source":adjacent_source,
      "adaptive_search_hops_executed":search_hops,
      "quality_caveat":"Search origin and provider metrics are NOT independently verified causal asset claims.",
      "source_failures":{"engine":es.get("limitations",[]),
         "expanded":xs.get("access_gaps",{}),
         "research":[x for x in rs.get("source_attempts",[]) if x.get("status")!="OK"][:25],
         "adjacent":ds.get("access_gaps",[])},
      "adaptive_search_results":audit,
      "publisher_article_enrichment_audit":article_audit,
      "coin_descriptive_sources_audit":profile_audit,
      "curated_original_project_sources_audit":primary_audit,
      "combined_project_background_gaps":effective_project_gaps,
      "source_context_audit":source_context_audit,
      "global_observation_classification":"Noncoin/unlinked data are first-class global/network evidence, NOT token cash flows."}
    total_leads=max(1,coverage["evidence_counts"]["canonical_research_leads"])
    depth_rate=coverage["evidence_counts"]["substantive_source_excerpt_leads"]/total_leads
    coverage["research_quality_gate"]={
        "all_100_coins_have_substantive_source_linked_context":
            coverage["per_coin"]["coins_with_substantive_coin_specific_context"]==100,
        "all_100_substantive_project_background":not effective_project_gaps,
        "project_background_context_status":"COMPLETE" if not effective_project_gaps else "INCOMPLETE",
        "coin_specific_event_text_status":"COMPLETE" if not manual_context["undercovered_coins"] else "INCOMPLETE",
        "project_background_not_fresh_catalyst":True,
        "technical_source_integration":"PASSED",
        "independently_primary_verified_claims":0,
        "independently_primary_claims_verification_status":"NOT_PERFORMED_BY_FREE_PYTHON",
        "substantive_context_share":round(depth_rate,4),
        "raw_all_leads_denominator_unchanged":True,
        "manual_high_context_queue_is_not_the_denominator":True,
        "substantive_context_target_met":depth_rate>=0.20,
        "publisher_excerpts":len(article),
        "deep_article_target_met":len(article)>=30,
        "publisher_source_attempted":article_audit["attempted"],
        "all_100_contracts_verified":False,
        "material_research_status":"PARTIAL_RESEARCH" if (
            depth_rate<0.20 or len(article)<30 or effective_project_gaps
            or manual_context["undercovered_coins"]
            or coverage["per_coin"]["coins_missing_substantive_coin_specific_context"]
        ) else "REQUIRES_INDEPENDENT_SEMANTIC_VALIDATION",
        "reason":"Extraction and discovery are not proof of independently verified 24h causal facts."}
    manifest={"schema_version":"cmc100-open-intelligence-free-v1","cutoff_utc":iso(cutoff),
       "no_paid_api_used":True,"llm_calls":0,
       "all_100_verified":True,"source_snapshots":caps,"direct_research_event_audit":direct_events_audit,"archives":{"engine":ea,"expanded":xa},
       "coverage_file":"docs/intelligence/coverage_audit.json",
       "global_file":"docs/intelligence/global_intelligence.json",
       "sector_file":"docs/intelligence/sector_intelligence.json",
       "task_file":"docs/intelligence/research_tasks.json",
       "source_proposals_file":"docs/intelligence/source_registry_proposals.json",
       "manual_research_context_file":"docs/intelligence/deep_research_queue.json",
       "manual_append_only_input":"docs/intelligence/manual_inputs/findings.jsonl",
       "new_public_source_discovery_file":"docs/intelligence/discovered_public_feeds.json",
       "source_probe_history_file":"docs/intelligence/source_probe_history.json",
       "article_attempt_history_file":"docs/intelligence/article_attempt_history.json",
       "knowledge_file":"docs/intelligence/knowledge_index.json",
       "source_backed_project_profile_file":"docs/intelligence/coin_profiles.json",
       "original_issuer_project_context_file":"docs/intelligence/primary_coin_context.json",
       "coin_batch_files":[f"docs/intelligence/coin_batches/batch_{i+1:02d}.json" for i in range(5)],
       "full_evidence_export":"docs/intelligence/export/evidence_index.jsonl",
       "full_evidence_export_is_actions_artifact_only":True,
       "adjacent_full_archive":adjacent_source,
       "adaptive_search_hops_executed":search_hops,
       "limitation":"Deterministic adaptive follow-up, NOT an autonomous LLM researcher or alpha signal."}
    for i in range(5):
        write(out/f"coin_batches/batch_{i+1:02d}.json",
              {"coins":cards[i*20:(i+1)*20],"version":"free-open-intelligence-v1"})
    write(out/"global_intelligence.json",g)
    write(out/"sector_intelligence.json",{"sectors":sectors,"open_ended_scope":True})
    write(out/"open_discovery.json",{"emergent_terms":emergent,
          "unresolved_global_count":len(glob),
          "source_discovery_notes":"Themes and asset associations are leads, never verified causality."})
    write(out/"source_probe_history.json",probe_history)
    write(out/"discovered_public_feeds.json",dynamic_audit)
    write(out/"source_registry_proposals.json",{"candidate_publishers":source_proposals,
          "auto_added_to_collector":0,
          "note":"Source expansion suggestions; access, safety and licensing require review."})
    write(out/"deep_research_queue.json",manual_context)
    write(out/"research_tasks.json",{"tasks":tasks,
          "audit":audit,"no_auto_source_installation":True})
    write(out/"coin_profiles.json",profile_doc)
    write(out/"primary_coin_context.json",primary_doc)
    write(out/"coverage_audit.json",coverage)
    write(out/"knowledge_index.json",{"evidence_count":len(evidence),
          "by_plane":dict(collections.Counter(e["source_plane"] for e in evidence)),
          "scope_counts":dict(collections.Counter(e["scope"] for e in evidence)),
          "primary_claims_verified_by_system":0,
          "note":"All original archives are referenced in manifest; data not omitted from source files."})
    write(out/"publisher_excerpts.json",{"items":article[-2000:],
          "policy":"Short attributed text only; timestamped accumulated cache; robots respected; NOT verified claims."})
    write(out/"article_attempt_history.json",{"attempts":past_attempts,
          "cooldown_hours":72,"never_conflate_url_with_verified_event":True})
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
    if a.max_followups>40 or a.max_articles>80:p.error("Free tier bounded to 40 searches/80 articles")
    manifest,coverage=build(a.root,a.out,cutoff,a.network,a.max_followups,a.max_articles,
                            live_collection=(a.cutoff is None))
    print(json.dumps({"status":"SUCCESS","manifest":manifest,
       "evidence_counts":coverage["evidence_counts"],
       "coverage":coverage["per_coin"]},ensure_ascii=False))

if __name__=="__main__":main()
