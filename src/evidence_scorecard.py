"""Auditable Stage-1 9/10 acceptance gate, not a prediction-quality score.

A substantive excerpt or a detected number is not a verified factual claim.
Coverage cannot be inferred from the coin named in an RSS search query.
"""
from __future__ import annotations
import re
from collections import Counter

DATE=re.compile(r"\b(?:20\d{2}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]20\d{2})\b")
QUANTITY=re.compile(r"(?<!\w)(?:\$|€)?\d+(?:[.,]\d+)?\s*(?:%|bps|bp|million|billion|tokens|usd|eth|btc|days|hours|validators|transactions|users)\b",re.I)
ACTION=re.compile(r"\b(?:approved|executed|deployed|launched|patched|exploited|unlocked|burned|listed|delisted|voted|released|proposed|halted|resumed|upgraded)\b",re.I)


def candidate_facts(event):
    """Literal text snippets only, with traceable source; no LLM factual inference."""
    excerpt=str(event.get("excerpt") or "")
    patterns={"date":DATE,"quantity":QUANTITY,"action":ACTION}
    out=[]
    for kind,pattern in patterns.items():
        for m in list(pattern.finditer(excerpt))[:5]:
            out.append({"kind":kind,"literal":m.group(0),"span":[m.start(),m.end()],
                        "verification":"NOT_VERIFIED",
                        "source_url":event.get("resolved_article_url") or event.get("url")})
    return out[:12]


def evaluate(events, status):
    """Six dimensions, weighted to 10; explicit hard gates for a claimed 9/10."""
    n=len(events)
    family=Counter(f for e in events for f in e.get("source_families",[]))
    nonsearch=sum(not ({"COIN_RESEARCH","CROSS_SECTOR"} & set(e.get("source_families",[])))
                  for e in events)
    deep=sum(bool(e.get("excerpt_adds_information")) for e in events)
    candidate=sum(bool(e.get("candidate_fact_spans")) for e in events)
    structured=sum(e.get("evidence_class") in
                   ("PRIMARY_GOVERNANCE_EVENT","PRIMARY_SECURITY_CATALOG_ENTRY") for e in events)
    root=family
    # Coverage measures successful search requests, not verified entity linkage.
    queried=min(1.0,status.get("coins_with_successful_query",0)/100)
    primary_sources=sum(1 for key in ("PROJECT_PRIMARY","PUBLIC_COMMUNITY","GOVERNANCE_EVENTS",
                                      "SECURITY_EVENTS","DEFI_METRICS","TECH_SECURITY_RESEARCH")
                        if root[key]>0)
    depth_ratio=deep/max(1,n)
    nonsearch_ratio=nonsearch/max(1,n)
    score={
      "information_breadth":round(10*queried,2),
      "source_quality":round(10*min(1,nonsearch_ratio/0.30)*0.6+
                             4*min(1,primary_sources/6),2),
      "content_depth":round(10*min(1,depth_ratio/0.40)*0.75+
                            2.5*min(1,candidate/max(1,n)/0.30),2),
      "temporal_integrity":round(8 if status.get("archive_is_complete")=="ALL_DISTINCT_VALID_ITEMS" else 2,2),
      "novelty":round(10*min(1,status.get("incremental_new_urls_with_substantive_context",0)/
                             max(1,status.get("incremental_new_url_leads",0))/0.40),2),
      "measurement":round(8 if status.get("requests_executed",0)>0 and
                          "information_quality" in status else 3,2),
    }
    weights={"information_breadth":0.20,"source_quality":0.20,"content_depth":0.25,
             "temporal_integrity":0.15,"novelty":0.10,"measurement":0.10}
    total=round(sum(score[k]*v for k,v in weights.items()),2)
    gates={
      "all_100_coins_queried":queried==1,
      "substantive_context_at_least_40pct":depth_ratio>=0.40,
      "non_search_family_share_at_least_30pct":nonsearch_ratio>=0.30,
      "structured_primary_events_observed":structured>=10,
      "all_required_evidence_families_present":all(root[k]>0 for k in
          ("PROJECT_PRIMARY","PUBLIC_COMMUNITY","GOVERNANCE_EVENTS","SECURITY_EVENTS","DEFI_METRICS","DERIVATIVES_METRICS")),
      "derivatives_data_live":root["DERIVATIVES_METRICS"]>0,
      "direct_onchain_and_tokenomics_sources_covered":False,
      "data_freshness_and_PIT_review_passed":False,
      "independent_corroboration_review_passed":False,
    }
    # PIT and corroboration audits are deliberately not automated/pretended.
    return {"schema_version":"stage1-scorecard-v1",
            "score_out_of_10":total,"dimension_scores":score,"weights":weights,
            "eligible_for_9_out_of_10":total>=9 and all(gates.values()),
            "acceptance_gates":gates,
            "counts":{"events":n,"non_search_events":nonsearch,"substantive":deep,
                      "events_with_candidate_fact_spans":candidate,
                      "structured_primary_event_records":structured},
            "limitations":["QUERIED_COIN_NOT_VERIFIED_MATCH","FACT_SPANS_NOT_VERIFIED_CLAIMS",
                           "UNREVIEWED_PIT_AND_CORROBORATION_GATES_FAIL_CLOSED",
                           "STRUCTURED_TVL_OBSERVATIONS_NOT_PUBLICATION_TIME_EVENTS",
                           "NO_COMPREHENSIVE_DERIVATIVES_OR_ONCHAIN_COVERAGE_WITHOUT_LIVE_SOURCE"]}
