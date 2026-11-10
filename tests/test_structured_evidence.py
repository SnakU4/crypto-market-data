import datetime as dt
import importlib.util
import pathlib
import sys
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from structured_evidence import (snapshot_records,kev_records,defillama_observations,
                                  funding_records,oi_records,collect_structured)
from evidence_scorecard import candidate_facts,evaluate
import expanded_discovery as ed

NOW=dt.datetime(2026,11,10,10,0,tzinfo=dt.timezone.utc)

class StructuredTests(unittest.TestCase):
    def test_proposals_are_independent_unique_events(self):
        payload={"data":{"proposals":[
          {"id":"QmProposal123456789A","title":"Increase lending cap","body":"Proposal for voting: increase cap to 50 million tokens after audit.",
           "created":int(NOW.timestamp())-3600,"start":int(NOW.timestamp()),"end":int(NOW.timestamp())+1000,"state":"active",
           "space":{"id":"aave.eth","name":"Aave"}},
          {"id":"QmProposal123456789B","title":"Change quorum","body":"A second proposal for risk management review.",
           "created":int(NOW.timestamp())-3600,"state":"active","space":{"id":"aave.eth","name":"Aave"}}]}}
        rows=snapshot_records(payload,NOW,NOW-dt.timedelta(days=7))
        self.assertEqual(len(rows),2)
        self.assertNotEqual(ed.event_id(rows[0]["url"]),ed.event_id(rows[1]["url"]))
        self.assertTrue(all(x["direct_primary"] for x in rows))
    def test_cisa_date_only_no_fake_midnight_publication(self):
        p={"vulnerabilities":[{"cveID":"CVE-2026-12345","dateAdded":"2026-11-10",
             "vulnerabilityName":"Test vulnerability","shortDescription":"A real published advisory",
             "vendorProject":"Example","product":"Router"}]}
        rows=kev_records(p,NOW,NOW-dt.timedelta(days=7))
        self.assertEqual(len(rows),1)
        self.assertIsNone(rows[0]["published_utc"])
        self.assertEqual(rows[0]["publication_time_status"],"DATE_ONLY_NOT_TIMESTAMP")
        self.assertNotEqual(ed.event_id(rows[0]["url"]),ed.event_id("https://www.cve.org/CVERecord?id=CVE-2026-99999"))
    def test_defillama_is_observation_not_event(self):
        rows=defillama_observations([{"name":"Aave","slug":"aave","tvl":4000000000,"symbol":"AAVE"},
                                    {"name":"Bad","tvl":"NaN"}],NOW)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["evidence_class"],"OBSERVATION_NOT_EVENT")
        self.assertIsNone(rows[0]["published_utc"])
    def test_derivatives_settlement_and_snapshot_distinct(self):
        ms=int((NOW-dt.timedelta(hours=1)).timestamp()*1000)
        f=funding_records([{"symbol":"BTCUSDT","fundingRate":"0.0001","fundingTime":ms}],NOW,"BTCUSDT")
        o=oi_records({"symbol":"BTCUSDT","openInterest":"1023.2","time":ms},NOW,"BTCUSDT")
        self.assertEqual(len(f),1)
        self.assertEqual(len(o),1)
        self.assertEqual(o[0]["publication_time_status"],"EXCHANGE_MARKET_TIMESTAMP_NOT_PUBLICATION")
        self.assertNotEqual(ed.event_id(f[0]["url"]),ed.event_id(
          f[0]["url"].replace(str(ms),str(ms+3600000))))
    def test_one_provider_error_does_not_block_others(self):
        def fetch(url,body):
            if "snapshot" in url:raise OSError("blocked")
            if "kev-data" in url:return {"vulnerabilities":[]}
            if "llama" in url:return []
            if "fundingRate" in url:return []
            if "openInterest" in url:return {"symbol":url.split("symbol=")[1],"openInterest":"1","time":int(NOW.timestamp()*1000)}
            raise ValueError("unknown")
        records,audit=collect_structured(NOW,fetcher=fetch)
        self.assertEqual(len(audit),7)
        self.assertEqual(sum(x["status"]=="ERROR" for x in audit),1)
        self.assertEqual(len(records),2)
    def test_fact_spans_are_not_verified_claims(self):
        e={"url":"https://example.org","excerpt":"The proposal approved 20 million tokens on 2026-11-09."}
        facts=candidate_facts(e)
        self.assertTrue(any(x["kind"]=="quantity" for x in facts))
        self.assertTrue(all(x["verification"]=="NOT_VERIFIED" for x in facts))
    def test_scorecard_cannot_claim_nine_without_external_validation(self):
        status={"coins_with_successful_query":100,"archive_is_complete":"ALL_DISTINCT_VALID_ITEMS",
                "requests_executed":894,"information_quality":{},
                "incremental_new_urls_with_substantive_context":50,"incremental_new_url_leads":100}
        e={"source_families":["PROJECT_PRIMARY","PUBLIC_COMMUNITY","GOVERNANCE_EVENTS",
                              "SECURITY_EVENTS","DEFI_METRICS"],"excerpt_adds_information":True,
           "candidate_fact_spans":[{"kind":"date"}],"evidence_class":"PRIMARY_GOVERNANCE_EVENT"}
        report=evaluate([e]*100,status)
        self.assertFalse(report["eligible_for_9_out_of_10"])
        self.assertFalse(report["acceptance_gates"]["independent_corroboration_review_passed"])

if __name__=="__main__":
    unittest.main()
