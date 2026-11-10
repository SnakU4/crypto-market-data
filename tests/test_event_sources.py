import datetime as dt
import pathlib
import sys
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"src"))
from evidence_extensions import (
    parse_btc_recent_transactions,parse_ethereum_transactions,
    parse_patternplus_calendar,parse_patternplus_unlocks,schedule_date,
    parse_defillama_dex_volume,parse_defillama_fees)
from evidence_intelligence import integrated_quality

NOW=dt.datetime(2026,11,10,19,0,tzinfo=dt.timezone.utc)

class EventSourceTests(unittest.TestCase):
    def test_unconfirmed_btc_transaction_is_observed_not_published(self):
        ident="a"*64
        rows=parse_btc_recent_transactions([{"txid":ident,"fee":1300,"vsize":250,"value":8000000}],NOW)
        self.assertEqual(len(rows),1)
        self.assertIsNone(rows[0]["published_utc"])
        self.assertEqual(rows[0]["attributes"]["confirmation_status"],"UNCONFIRMED_WHEN_LISTED")
        self.assertEqual(rows[0]["source_item_id"],ident)
        self.assertNotIn("cmc_id",rows[0])
    def test_eth_explorer_block_time_is_not_publication_time(self):
        ident="0x"+"f"*64
        result=parse_ethereum_transactions({"items":[{
            "hash":ident,"value":"1000000000000000000","timestamp":"2026-11-10T18:00:00.000000Z",
            "status":"ok","block_number":2400000}]},NOW)
        self.assertEqual(len(result),1)
        self.assertIsNone(result[0]["published_utc"])
        self.assertIn("BLOCK_TIMESTAMP",result[0]["attributes"]["time_semantics_warning"])
    def test_unlock_schedule_preserves_date_without_inventing_time(self):
        rows=parse_patternplus_unlocks({"unlocks":[
            {"slug":"example","date":"2026-11-15","tokens":1000000,
             "percent_of_circulating":2.5},
            {"slug":"example","date":"2026-11-16","tokens":500000}]},NOW)
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]["attributes"]["scheduled_date_utc"],"2026-11-15")
        self.assertIsNone(rows[0]["published_utc"])
        self.assertEqual(rows[0]["attributes"]["verification"],"AGGREGATED_THIRD_PARTY_UNCORROBORATED")
    def test_real_unlock_schema_has_float_dilution_and_provenance(self):
        rows=parse_patternplus_unlocks({"unlocks":[
            {"token":"apt-aptos","name":"Aptos","symbol":"APT",
             "date":"2026-11-14","amount":11358962.17,
             "pct_circulating":1.1,"pct_total":0.4,
             "basis":"published","file":"schedule.json","categories":["team"]}]},NOW)
        self.assertEqual(rows[0]["metrics"]["reported_pct_circulating"],1.1)
        self.assertEqual(rows[0]["attributes"]["source_project_name"],"Aptos")
        self.assertEqual(rows[0]["attributes"]["source_symbol"],"APT")
        self.assertEqual(rows[0]["attributes"]["source_basis"],"published")
    def test_defillama_activity_protocols(self):
        raw={"protocols":[
            {"name":"DexA","defillamaId":"dex-a","gecko_id":"dexa",
             "total24h":40000000,"total7d":150000000,"change_1d":22.5},
            {"name":"NoActive","defillamaId":"inactive","total24h":None}]}
        x=parse_defillama_dex_volume(raw,NOW)
        y=parse_defillama_fees(raw,NOW)
        self.assertEqual(len(x),1)
        self.assertEqual(x[0]["metrics"]["total24h"],40000000)
        self.assertEqual(len(y),1)
        self.assertEqual(y[0]["source"],"defillama_fees")
    def test_calendar_source_allows_non_coin_macro_events(self):
        rows=parse_patternplus_calendar({"events":[
            {"title":"US CPI release","date":"2026-11-20","category":"macro"}]},NOW)
        self.assertEqual(len(rows),1)
        self.assertNotIn("cmc_id",rows[0])
        self.assertEqual(rows[0]["attributes"]["category"],"macro")
    def test_reject_malformed_source_schema_and_dates(self):
        with self.assertRaises(ValueError):parse_patternplus_unlocks({"random":{}},NOW)
        self.assertIsNone(schedule_date("yesterday"))
    def test_broad_classes_still_fail_universe_verification(self):
        payload={"records":2500,"records_by_family":{},"source_audit":[
            {"family":"TOKEN_UNLOCK_SCHEDULE_CANDIDATE","status":"OK","records":50},
            {"family":"DIRECT_WALLET_ACTIVITY_SAMPLE","status":"OK","records":40}],
            "identity_mapping":{"anchored_distinct_cmc_ids":100},"archive_sha256":"sha",
            "deltas":{"baseline":False}}
        report=integrated_quality(payload)
        self.assertTrue(report["source_class_coverage"]["TOKEN_UNLOCKS"])
        self.assertTrue(report["source_class_coverage"]["WALLET_TRANSFERS"])
        self.assertFalse(report["certified_9_out_of_10"])
        self.assertIn("verified_token_unlock_schedules_across_universe",report["acceptance_blockers"])

if __name__=="__main__":unittest.main()
