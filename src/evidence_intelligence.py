"""CMC100 identity assurance, PIT-safe deltas and integrated evidence acceptance.

This module intentionally never infers a trading direction. Asset contract
identity, source publication dates and previous snapshot availability are
not interchangeable. Quality criteria fail closed on incomplete coverage.
"""
from __future__ import annotations
import collections
import datetime as dt
import gzip
import hashlib
import json
import math
from pathlib import Path
import re

UTC=dt.timezone.utc
EXPECTED_CLASSES=("NEWS","CROSS_SECTOR","GOVERNANCE","SECURITY","DEVELOPMENT",
                  "COMMUNITY","DERIVATIVES","ONCHAIN_NETWORK","DEX_LIQUIDITY",
                  "TOKENOMICS_SUPPLY","TOKEN_UNLOCKS","WALLET_TRANSFERS")
# Percentage heuristics are a TRIAGE tool, not statistical significance or alpha.
FRACTIONAL_CHANGE_THRESHOLDS={
    "tvl_usd":0.05,"circulating_usd":0.01,
    "circulating_supply":0.01,"total_supply":0.01,
    "openInterest":0.10,"open_interest_usd":0.10,"open_interest_base":0.10,
    "open_interest_contracts":0.10,"open_interest_base_units":0.10,
    "volume_usd_h24":0.5,"total_fee":0.5,"count":0.3,
    "fastestFee_sat_vbyte":0.4,"hourFee_sat_vbyte":0.4,
    "reserve_in_usd":0.10,"total_transactions":0.03
}
FUNDING_KEYS=("fundingRate","funding_rate","fundingRatePrediction")


def stamp(v):
    try:
        t=dt.datetime.fromisoformat(str(v).replace("Z","+00:00"))
        return t.astimezone(UTC) if t.tzinfo is not None else None
    except (ValueError,TypeError):return None


def validate_market(market):
    assets=market.get("assets") or []
    if market.get("index",{}).get("verified_constituents")!=100 or len(assets)!=100:
        raise ValueError("100_VERIFIED_CMC100_CONSTITUENTS_REQUIRED")
    ids=[int(a["cmc_id"]) for a in assets]
    if len(set(ids))!=100:raise ValueError("CMC_ID_DUPLICATE")
    return assets


def assign_identity(observations,market):
    """Exact exchange contract crosscheck is an anchored mapping, NOT a
    contract-address verification of the native or wrapped asset."""
    assets=validate_market(market)
    exchange_ids=collections.defaultdict(list)
    symbols=collections.defaultdict(list)
    names=collections.defaultdict(list)
    for a in assets:
        symbols[str(a.get("symbol","")).upper()].append(a)
        names[(str(a.get("name","")).casefold(),str(a.get("symbol","")).casefold())].append(a)
        p=a.get("perpetual") or {}
        inst=p.get("symbol")
        if (p.get("exchange")=="OKX" and p.get("trading_status")=="live"
                and str(p.get("mapping","")).startswith("EXACT_")
                and isinstance(inst,str) and inst.endswith("-SWAP")
                and inst.rsplit("-",2)[0].upper()==str(a.get("symbol","")).upper()):
            exchange_ids[inst].append(a)
    linked=set()
    direct=0
    candidates=0
    for record in observations:
        source=record.get("source")
        if source in ("okx_swap_tickers","okx_swap_open_interest"):
            pair=exchange_ids.get(record["source_item_id"],[])
            if len(pair)==1:
                item=pair[0]
                record["cmc_id"]=item["cmc_id"]
                record["coin_identity_status"]="CMC100_SNAPSHOT_OKX_CONTRACT_ANCHORED"
                record["identity_evidence"]={"cmc_index_snapshot":market.get("snapshot_completed_utc"),
                    "instrument_id":record["source_item_id"],
                    "method":"EXACT_SNAPSHOT_EXCHANGE_CONTRACT; NOT_CHAIN_CONTRACT_VERIFICATION"}
                linked.add(item["cmc_id"])
                direct+=1
        elif source=="coingecko_supply":
            attrs=record.get("attributes",{})
            key=(str(attrs.get("name","")).casefold(),str(attrs.get("symbol","")).casefold())
            matches=names.get(key,[])
            if len(matches)==1:
                record["candidate_cmc_id"]=matches[0]["cmc_id"]
                record["coin_identity_status"]="CROSS_PROVIDER_NAME_SYMBOL_CANDIDATE"
                candidates+=1
        elif source=="kraken_futures_tickers":
            pair=str(record.get("attributes",{}).get("pair") or "")
            base=pair.split(":")[0].upper() if ":" in pair else ""
            if base=="XBT":base="BTC"  # alias is ONLY a candidate
            matches=symbols.get(base,[])
            if len(matches)==1:
                record["candidate_cmc_id"]=matches[0]["cmc_id"]
                record["coin_identity_status"]="EXCHANGE_BASE_SYMBOL_CANDIDATE"
                candidates+=1
        elif source in ("btc_mempool","btc_fee_estimates"):
            matching=[a for a in assets if a["cmc_id"]==1 and a.get("symbol")=="BTC"]
            if matching:
                record["network_context_cmc_id"]=1
                record["coin_identity_status"]="BITCOIN_NETWORK_CONTEXT_NOT_TOKEN_TRANSACTION"
        elif source=="ethereum_blockscout_stats":
            matching=[a for a in assets if a["cmc_id"]==1027 and a.get("symbol")=="ETH"]
            if matching:
                record["network_context_cmc_id"]=1027
                record["coin_identity_status"]="ETHEREUM_NETWORK_CONTEXT_NOT_TOKEN_TRANSACTION"
    return {"anchored_observation_count":direct,
            "anchored_distinct_cmc_ids":len(linked),
            "anchored_cmc_ids":sorted(linked),
            "candidate_observation_count":candidates,
            "all_cmc100_have_verified_onchain_contract":False,
            "identity_scope":"EXCHANGE_CONTRACT_ONLY; OTHER ASSET LINKS NOT VERIFIED"}


def load_previous(root,out,current_time):
    """No synthesized baseline: use only a prior, checksum-verified archive."""
    status_path=out/"status.json"
    if not status_path.exists():return None,{"status":"NO_PRIOR_ARCHIVE"}
    try:
        meta=json.loads(status_path.read_text())
        ts=stamp(meta.get("capture_utc"))
        if ts is None or not ts<current_time:
            return None,{"status":"INVALID_PRIOR_TIMESTAMP"}
        if (current_time-ts).total_seconds()>7*86400:
            return None,{"status":"PRIOR_TOO_OLD"}
        rel=meta.get("archive_path","")
        path=(root/rel).resolve()
        if not path.is_relative_to(out.resolve()) or not path.exists():
            return None,{"status":"PRIOR_ARCHIVE_MISSING_OR_UNSAFE"}
        if hashlib.sha256(path.read_bytes()).hexdigest()!=meta.get("archive_sha256"):
            return None,{"status":"PRIOR_ARCHIVE_HASH_MISMATCH"}
        observations=[]
        with gzip.open(path,"rt",encoding="utf8") as f:
            for line in f:
                observations.append(json.loads(line))
                if len(observations)>100_000:
                    return None,{"status":"PRIOR_ARCHIVE_EXCESSIVE"}
        return {"capture_utc":meta["capture_utc"],"observations":observations},{"status":"VERIFIED_PRIOR_ARCHIVE",
            "elapsed_minutes":round((current_time-ts).total_seconds()/60,2),
            "prior_record_count":len(observations)}
    except (OSError,ValueError,TypeError,KeyError) as ex:
        return None,{"status":"PRIOR_READ_FAILED","error":str(ex)[:120]}


def delta_kind(source,field,old_value,new_value):
    """Never turn ordinary spot-price changes into independently new facts."""
    if any(term in field.lower() for term in ("price","change24h","market_cap","fdv","last","index")):
        return "MARKET_PRICE_CONTEXT"
    if field in FUNDING_KEYS:return "FUNDING_RATE_CHANGE"
    if source in ("btc_mempool","btc_fee_estimates","ethereum_blockscout_stats"):
        return "NETWORK_ACTIVITY_CHANGE"
    if any(term in field.lower() for term in ("supply","circulating")):
        return "SUPPLY_OBSERVATION_CHANGE_NOT_UNLOCK"
    if "open_interest" in field or field=="openInterest":
        return "OPEN_INTEREST_CHANGE"
    if any(term in field.lower() for term in ("tvl","reserve","liquidity")):
        return "LIQUIDITY_CHANGE"
    return "OTHER_OBSERVATION_CHANGE"


def compute_deltas(current,prior,now):
    if prior is None:
        return {"baseline":True,"prior_capture_utc":None,
                "compared":0,"changed_metrics":0,"triage_candidates":[],
                "first_seen_observations":len(current),"unchanged_observations":0,
                "novelty_caveat":"FIRST_BASELINE_NOT_NEW_EVENTS"}
    previous={r.get("observation_id"):r for r in prior["observations"]}
    prior_time=stamp(prior["capture_utc"])
    elapsed=(now-prior_time).total_seconds()/60 if prior_time else None
    delta=[];compared=0;first=0;unchanged=0;changed=0
    for r in current:
        old=previous.get(r.get("observation_id"))
        if old is None:
            first+=1
            continue
        compared+=1
        any_change=False
        for field,new in r.get("metrics",{}).items():
            before=old.get("metrics",{}).get(field)
            if not isinstance(new,(float,int)) or not isinstance(before,(float,int)):
                continue
            if not(math.isfinite(new) and math.isfinite(before)):continue
            absolute=new-before
            if abs(absolute)<1e-12*max(abs(new),abs(before),1):continue
            changed+=1;any_change=True
            relative=absolute/abs(before) if before!=0 else None
            typ=delta_kind(r.get("source",""),field,before,new)
            threshold=FRACTIONAL_CHANGE_THRESHOLDS.get(field,0.2)
            qualified=(abs(absolute)>=0.0001 if field in FUNDING_KEYS else
                       abs(relative)>=threshold if relative is not None else False)
            # These are heuristics; sparse observations cannot claim anomalies.
            if qualified:
                delta.append({
                    "observation_id":r["observation_id"],"source":r["source"],
                    "source_item_id":r["source_item_id"],"metric":field,
                    "old":before,"new":new,"absolute_change":absolute,
                    "relative_change":relative,"change_class":typ,
                    "cmc_id":r.get("cmc_id"),"candidate_cmc_id":r.get("candidate_cmc_id"),
                    "identity_status":r.get("coin_identity_status"),
                    "previous_observed_utc":prior["capture_utc"],
                    "observed_utc":r["observed_utc"],
                    "triage_status":"HEURISTIC_CHANGE_NOT_VERIFIED_EVENT",
                    "calendar_interval_minutes":round(elapsed,2) if elapsed is not None else None})
        if not any_change:unchanged+=1
    delta.sort(key=lambda e:(e["change_class"]=="MARKET_PRICE_CONTEXT",
                             -(abs(e["relative_change"]) if e["relative_change"] is not None else 0),
                             e["source"],e["source_item_id"]))
    return {"baseline":False,"prior_capture_utc":prior["capture_utc"],
            "compared":compared,"changed_metrics":changed,
            "triage_count":len(delta),
            "triage_candidates":delta[:400],
            "first_seen_observations":first,
            "unchanged_observations":unchanged,
            "novelty_caveat":"QUANTITATIVE_THRESHOLD_NOT_EVENT_OR_TRADABLE_ALPHA"}


def integrated_quality(structured,discovery=None,now=None):
    """Deterministic diagnostic quality score, strict acceptance blockers.

    Quoted scores reflect data engineering coverage, NOT 24h alpha performance.
    A score of 9 cannot be certified without verified contract identities,
    PIT replay, independent corroboration and event-class breadth.
    """
    now=now or dt.datetime.now(UTC)
    audit=structured.get("source_audit",[])
    families={x["family"] for x in audit if x["status"]=="OK" and x.get("records",0)>0}
    raw_families=(discovery or {}).get("family_unique_url_counts",{})
    age=None
    if discovery:
        t=stamp(discovery.get("capture_utc"))
        age=(now-t).total_seconds()/3600 if t else None
    news_fresh=bool(age is not None and 0<=age<=24)
    catalog={
        "NEWS":news_fresh and raw_families.get("COIN_RESEARCH",0)>0,
        "CROSS_SECTOR":news_fresh and raw_families.get("CROSS_SECTOR",0)>0,
        "GOVERNANCE":news_fresh and raw_families.get("GOVERNANCE_EVENTS",0)>0,
        "SECURITY":news_fresh and raw_families.get("SECURITY_EVENTS",0)>0,
        "DEVELOPMENT":news_fresh and raw_families.get("PROJECT_PRIMARY",0)>0,
        "COMMUNITY":news_fresh and raw_families.get("PUBLIC_COMMUNITY",0)>0,
        "DERIVATIVES":bool(families&{"DERIVATIVES_MARKET","DERIVATIVES_OI"}),
        "ONCHAIN_NETWORK":"DIRECT_ONCHAIN_NETWORK" in families,
        "DEX_LIQUIDITY":"DEX_ONCHAIN_MARKET" in families,
        "TOKENOMICS_SUPPLY":bool(families&{"TOKENOMICS_SUPPLY_PROXY","STABLECOIN_SUPPLY"}),
        "TOKEN_UNLOCKS":False,
        "WALLET_TRANSFERS":False,
    }
    verified=structured.get("identity_mapping",{}).get("anchored_distinct_cmc_ids",0)
    provider_ok=sum(x["status"]=="OK" and x.get("records",0)>0 for x in audit)
    active=len(audit)
    counts=structured.get("records_by_family",{})
    score={
        "breadth":round(10*sum(catalog.values())/len(catalog),2),
        "direct_source_availability":round(10*provider_ok/max(1,active),2),
        "identity_assurance":round(10*min(verified,100)/100,2),
        "structured_data_depth":round(10*min(1,structured.get("records",0)/1500),2),
        "temporal_integrity":7.5 if structured.get("archive_sha256") else 5.0,
        "novelty_assurance":6.0 if structured.get("deltas",{}).get("baseline") is False else 2.0,
    }
    weights={"breadth":0.25,"direct_source_availability":0.15,
             "identity_assurance":0.20,"structured_data_depth":0.15,
             "temporal_integrity":0.15,"novelty_assurance":0.10}
    total=round(sum(score[k]*w for k,w in weights.items()),2)
    blockers={
       "all_100_cmc100_assets_independently_contract_verified":False,
       "direct_contract_wallet_events_across_universe":False,
       "verified_token_unlock_schedules_across_universe":False,
       "historical_point_in_time_replay_verified":False,
       "independent_multisource_claim_corroboration":False,
       "coverage_of_all_12_classes":all(catalog.values()),
    }
    return {"schema_version":"evidence-engine-integrated-quality-v1",
            "diagnostic_score_out_of_10":total,"weighted_dimensions":score,
            "dimension_weights":weights,"target":9.0,
            "certified_9_out_of_10":total>=9 and all(blockers.values()),
            "acceptance_blockers":{k:v for k,v in blockers.items() if not v},
            "source_class_coverage":catalog,"sources_with_data":provider_ok,
            "sources_attempted":active,"records_by_family":counts,
            "anchored_cmc100_asset_count":verified,
            "discovery_age_hours":round(age,2) if age is not None else None,
            "warning":"ENGINEERING_EVIDENCE_COVERAGE_SCORE_NOT_TRADING_ALPHA_OR_CAUSAL_QUALITY"}
