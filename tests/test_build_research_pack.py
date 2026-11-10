import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from build_research_pack import build,publish

TIMESTAMP="2026-11-10T18:40:00Z"
CUTOFF=dt.datetime(2026,11,10,19,0,tzinfo=dt.timezone.utc)

class PackTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        assets=[{"cmc_id":i+1,"name":"Token "+str(i+1),"symbol":"T"+str(i+1),
                 "cmc_quote":{"price_usd":1.0,"ret_7d_pct":0},
                 "perpetual":{}} for i in range(100)]
        assets[0].update({"name":"Bitcoin","symbol":"BTC",
                          "perpetual":{"exchange":"OKX",
                                       "mapping":"EXACT_BASE_ASSET_OKX",
                                       "symbol":"BTC-USDT-SWAP"}})
        self.save("docs/latest.json",{"assets":assets,"snapshot_completed_utc":TIMESTAMP,
                                      "index":{"verified_constituents":100}})
        self.structured=[
          {"observation_id":"s1","source":"okx_swap_tickers","source_item_id":"BTC-USDT-SWAP",
           "cmc_id":1,"coin_identity_status":"CMC100_SNAPSHOT_OKX_CONTRACT_ANCHORED",
           "metrics":{"last_price":100},"observed_utc":TIMESTAMP},
          {"observation_id":"s2","source":"patternplus_unlocks","source_item_id":"project-unknown",
           "candidate_cmc_id":2,"coin_identity_status":"THIRD_PARTY_UNLOCK_NAME_SYMBOL_CANDIDATE",
           "metrics":{"reported_amount":1000000},"observed_utc":TIMESTAMP},
          {"observation_id":"s3","source":"btc_recent_transactions","source_item_id":"abc",
           "network_context_cmc_id":1,"coin_identity_status":"BITCOIN_NETWORK_CONTEXT_NOT_TOKEN_TRANSACTION",
           "metrics":{},"observed_utc":TIMESTAMP},
          {"observation_id":"s4","source":"defillama_chains","source_item_id":"Polygon",
           "metrics":{"tvl_usd":100},"observed_utc":TIMESTAMP}]
        self.news=[
          {"event_id":"d1","story_title_hash":"t1","title":"BTC query result",
           "url":"https://example.org/btc","query_scoped_ids":[1],
           "source_families":["COIN_RESEARCH"],"observed_utc":TIMESTAMP,
           "excerpt":"A long headline","excerpt_adds_information":True},
          {"event_id":"d2","story_title_hash":"t2","title":"Macro update",
           "url":"https://example.org/macro","query_scoped_ids":[],
           "source_families":["CROSS_SECTOR"],"observed_utc":TIMESTAMP,
           "excerpt":"sector-wide","excerpt_adds_information":False}]
        self.engine_archive=self.archive("evidence_engine",self.structured)
        self.discovery_archive=self.archive("expanded_discovery",self.news)
        self.save("docs/evidence_engine/delta_candidates.json",
                  {"capture_utc":TIMESTAMP,"triage_count":0,"triage_candidates":[]})
        self.save("docs/evidence_engine/event_candidates.json",
                  {"capture_utc":TIMESTAMP,"total_event_candidates":0,"events":[]})

    def tearDown(self):
        self.tmp.cleanup()

    def save(self,path,obj):
        out=self.root/path
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(obj),encoding="utf8")
        return out

    def archive(self,folder,rows):
        path=self.root/"docs"/folder/"archive"/"20261110"/"test.jsonl.gz"
        path.parent.mkdir(parents=True,exist_ok=True)
        with gzip.open(path,"wt",encoding="utf8") as f:
            for row in rows:f.write(json.dumps(row)+"\n")
        meta={"capture_utc":TIMESTAMP,
              "archive_path":str(path.relative_to(self.root)),
              "archive_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
              "records":len(rows),"distinct_url_leads":len(rows),
              "full_archive_count":len(rows)}
        self.save("docs/"+folder+"/status.json",meta)
        return path

    def test_full_archives_parsed_and_100_cards(self):
        value=build(self.root,CUTOFF)
        self.assertEqual(len(value["cards"]),100)
        self.assertEqual(value["manifest"]["sha_verified_archives"]["engine"]["decompressed"],4)
        self.assertEqual(value["manifest"]["sha_verified_archives"]["discovery"]["decompressed"],2)
        self.assertFalse(value["manifest"]["all_news_primary_claims_verified"])
        self.assertFalse(value["manifest"]["verified_9_out_of_10"])

    def test_strict_identity_and_provenance(self):
        value=build(self.root,CUTOFF)
        first=value["cards"][0]
        self.assertEqual(len(first["anchored_okx_instrument_observations"]),1)
        self.assertEqual(first["anchored_okx_instrument_observations"][0]["evidence_id"],"S:s1")
        self.assertEqual(first["news_search_origin_leads_UNVERIFIED"][0]["claim_status"],"NOT_VERIFIED")
        self.assertEqual(first["network_context_NOT_coin_flows"][0]["evidence_id"],"S:s3")
        second=value["cards"][1]
        self.assertEqual(len(second["anchored_okx_instrument_observations"]),0)
        self.assertEqual(len(second["unverified_coin_candidate_observations"]),1)
        self.assertEqual(value["manifest"]["structured_partition"],
              {"anchored_exchange":1,"cross_provider_candidates":1,
               "network_only":1,"unassigned":1})

    def test_full_plaintext_export_and_batches(self):
        value=build(self.root,CUTOFF)
        man=publish(value,self.root)
        self.assertEqual(len(man["coin_batches"]),5)
        self.assertEqual(man["full_text_export_for_actions_artifact"]["discovery"]["count"],2)
        self.assertEqual(man["full_text_export_for_actions_artifact"]["structured"]["count"],4)
        ex=self.root/"docs/research_pack/export/discovery_complete.jsonl"
        self.assertEqual(len(ex.read_text().splitlines()),2)
        coin_json=self.root/"docs/research_pack/coin_batches/batch_01.json"
        self.assertEqual(len(json.loads(coin_json.read_text())["coins"]),20)

    def test_wrong_checksum_fails_closed(self):
        self.engine_archive.write_bytes(self.engine_archive.read_bytes()+b"x")
        with self.assertRaisesRegex(ValueError,"UNVERIFIED_ARCHIVE"):
            build(self.root,CUTOFF)

    def test_unavailable_future_archive_fails_closed(self):
        earlier=dt.datetime(2026,11,10,18,0,tzinfo=dt.timezone.utc)
        with self.assertRaisesRegex(ValueError,"POST_CUTOFF"):
            build(self.root,earlier)

    def test_future_dated_event_record_is_quarantined(self):
        self.news.append({"event_id":"future","title":"Future fake","url":"https://example.org",
            "source_families":["COIN_RESEARCH"],"query_scoped_ids":[1],
            "observed_utc":TIMESTAMP,"published_utc":"2026-11-11T00:00:00Z"})
        self.archive("expanded_discovery",self.news)
        result=build(self.root,CUTOFF)
        self.assertEqual(result["manifest"]["pit_record_filter"]["discovery"]["quarantined_unknown_or_future"],1)
        self.assertEqual(len(result["discovery"]),2)
        self.assertEqual(len(result["cards"][0]["news_search_origin_leads_UNVERIFIED"]),1)

    def test_coin_query_provenance_is_not_verified_relevance(self):
        self.news[0]["query_scoped_ids"]=[1,2]
        self.archive("expanded_discovery",self.news)
        result=build(self.root,CUTOFF)
        self.assertEqual(result["manifest"]["discovery_search_leads_with_multiple_coin_queries"],1)
        self.assertEqual(result["cards"][1]["news_search_origin_leads_UNVERIFIED"][0]["identity_status"],
                         "SEARCH_ORIGIN_ONLY_NOT_COIN_MATCH")

    def test_delta_snapshot_mismatch_fails(self):
        self.save("docs/evidence_engine/delta_candidates.json",
                  {"capture_utc":"2026-11-09T18:00:00Z","triage_candidates":[]})
        with self.assertRaisesRegex(ValueError,"MISMATCHED_SOURCE_TIMESTAMPS"):
            build(self.root,CUTOFF)

    def test_missing_archive_fails_closed(self):
        self.discovery_archive.unlink()
        with self.assertRaisesRegex(ValueError,"UNVERIFIED_ARCHIVE"):
            build(self.root,CUTOFF)

if __name__=="__main__":
    unittest.main()
