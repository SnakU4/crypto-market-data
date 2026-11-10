import datetime as dt
import gzip
import json
import pathlib
import sys
import tempfile
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"src"))

from evidence_extensions import (
    parse_okx_tickers,parse_okx_open_interest,parse_coingecko_supply,
    parse_bitcoin_mempool,parse_bitcoin_fees,parse_ethereum_stats,
    parse_geckoterminal_pools)
from evidence_intelligence import assign_identity,compute_deltas,integrated_quality
from crypto_evidence_engine import capture, save

NOW=dt.datetime(2026,11,10,18,0,tzinfo=dt.timezone.utc)

def market():
    assets=[]
    for i in range(100):
        symbol="BTC" if i==0 else "ETH" if i==1 else f"X{i:02d}"
        a={"cmc_id":1 if i==0 else 1027 if i==1 else i+300000,
           "name":"Bitcoin" if i==0 else "Ethereum" if i==1 else f"Token {i}",
           "symbol":symbol}
        if i<3:a["perpetual"]={"exchange":"OKX","mapping":"EXACT_BASE_ASSET_OKX",
                              "symbol":f"{symbol}-USDT-SWAP","trading_status":"live"}
        assets.append(a)
    return {"assets":assets,"index":{"verified_constituents":100},
            "snapshot_completed_utc":"2026-11-10T10:00:00Z"}

class EvidenceIntelligenceTests(unittest.TestCase):
    def test_okx_contracts_and_observations(self):
        payload={"code":"0","data":[
          {"instId":"BTC-USDT-SWAP","last":"100000","volCcy24h":"1000000","ts":str(int(NOW.timestamp()*1000))},
          {"instId":"ETH-USDT-SWAP","oiUsd":"5000000","oiCcy":"3000","ts":str(int(NOW.timestamp()*1000))},
          {"instId":"fake","oiUsd":"123"}]}
        rows=parse_okx_tickers(payload,NOW)
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]["metrics"]["last_price"],100000)
        mapped=assign_identity(rows,market())
        self.assertEqual(mapped["anchored_distinct_cmc_ids"],2)
        self.assertEqual(rows[0]["cmc_id"],1)
        self.assertEqual(rows[0]["coin_identity_status"],"CMC100_SNAPSHOT_OKX_CONTRACT_ANCHORED")
    def test_reject_unvalidated_mapping(self):
        m=market()
        m["assets"][0]["perpetual"]["mapping"]="NOT_MATCHED_OR_REQUIRES_MANUAL_REVIEW"
        row=parse_okx_tickers({"code":"0","data":[{"instId":"BTC-USDT-SWAP","last":"5"}]},NOW)[0]
        self.assertEqual(assign_identity([row],m)["anchored_distinct_cmc_ids"],0)
        self.assertNotIn("cmc_id",row)
    def test_okx_oi_and_future_time_protection(self):
        ts=int(NOW.timestamp()*1000)
        x=parse_okx_open_interest({"code":"0","data":[{"instId":"BTC-USDT-SWAP","oiUsd":"200000","ts":str(ts)}]},NOW)
        self.assertEqual(x[0]["metrics"]["open_interest_usd"],200000)
        y=parse_okx_tickers({"code":"0","data":[{"instId":"ETH-USDT-SWAP","last":"1","ts":str(ts+10_000_000)}]},NOW)
        self.assertEqual(len(y),0)
    def test_coingecko_supply_is_candidate_not_contract_verified(self):
        rows=parse_coingecko_supply([{"id":"bitcoin","name":"Bitcoin","symbol":"btc",
             "circulating_supply":20000000,"total_supply":20000000,"max_supply":21000000}],NOW)
        mapping=assign_identity(rows,market())
        self.assertEqual(mapping["anchored_distinct_cmc_ids"],0)
        self.assertEqual(rows[0]["candidate_cmc_id"],1)
        self.assertNotIn("cmc_id",rows[0])
    def test_direct_chain_metrics_are_not_token_transfers(self):
        btc=parse_bitcoin_mempool({"count":1000,"vsize":500000,"total_fee":123},NOW)
        fees=parse_bitcoin_fees({"fastestFee":40,"hourFee":8},NOW)
        eth=parse_ethereum_stats({"total_transactions":"1,234,500","total_addresses":"5,000"},NOW)
        rows=btc+fees+eth
        assign_identity(rows,market())
        self.assertEqual(btc[0]["network_context_cmc_id"],1)
        self.assertEqual(eth[0]["network_context_cmc_id"],1027)
        self.assertTrue(all("cmc_id" not in r for r in rows))
        self.assertEqual(eth[0]["metrics"]["total_transactions"],1234500)
    def test_gecko_pool_is_not_assigned_coin(self):
        rows=parse_geckoterminal_pools({"data":[
          {"id":"eth_0xaaaa","attributes":{"name":"ETH/USDC","address":"0xaaaa",
              "reserve_in_usd":"4000000","volume_usd":{"h24":"500000"}}}]},NOW)
        assign_identity(rows,market())
        self.assertEqual(len(rows),1)
        self.assertTrue(rows[0]["attributes"]["token_contract_not_verified"])
        self.assertNotIn("cmc_id",rows[0])
    def test_deltas_are_source_and_pit_specific(self):
        old=parse_okx_open_interest({"code":"0","data":[{"instId":"BTC-USDT-SWAP","oiUsd":"100","ts":str(int(NOW.timestamp()*1000))}]},NOW)
        recent=NOW+dt.timedelta(hours=2)
        new=parse_okx_open_interest({"code":"0","data":[{"instId":"BTC-USDT-SWAP","oiUsd":"120","ts":str(int(recent.timestamp()*1000))}]},recent)
        assign_identity(new,market())
        prev={"capture_utc":"2026-11-10T18:00:00Z","observations":old}
        d=compute_deltas(new,prev,recent)
        self.assertFalse(d["baseline"])
        self.assertEqual(d["triage_count"],1)
        self.assertEqual(d["triage_candidates"][0]["change_class"],"OPEN_INTEREST_CHANGE")
        self.assertEqual(d["triage_candidates"][0]["cmc_id"],1)
        self.assertEqual(d["triage_candidates"][0]["triage_status"],"HEURISTIC_CHANGE_NOT_VERIFIED_EVENT")
    def test_first_snapshot_not_mislabelled_novel(self):
        rows=parse_bitcoin_mempool({"count":100},NOW)
        d=compute_deltas(rows,None,NOW)
        self.assertTrue(d["baseline"])
        self.assertEqual(d["first_seen_observations"],1)
        self.assertEqual(d["novelty_caveat"],"FIRST_BASELINE_NOT_NEW_EVENTS")
    def test_repeated_snapshot_does_not_become_event(self):
        rows=parse_bitcoin_mempool({"count":100},NOW)
        d=compute_deltas(rows,{"capture_utc":"2026-11-10T17:00:00Z","observations":rows},NOW)
        self.assertEqual(d["triage_count"],0)
        self.assertEqual(d["unchanged_observations"],1)
    def test_archives_verified_and_sequential(self):
        def fake(url,size):
            if "okx" in url:return {"code":"0","data":[{"instId":"BTC-USDT-SWAP","oiUsd":"100"}]}
            raise ValueError("mock")
        sources=({"key":"okx_swap_open_interest","family":"DERIVATIVES_OI",
                  "url":"https://example.org/okx","max_bytes":1000},)
        market_input=market()
        first=capture(market_input,fetcher=fake,now=NOW,sources=sources)
        second=capture(market_input,fetcher=fake,now=NOW+dt.timedelta(hours=2),sources=sources)
        with tempfile.TemporaryDirectory() as root:
            folder=pathlib.Path(root)
            # First status creation works even when discovery archive not present
            s1=save(first,folder)
            s2=save(second,folder)
            self.assertEqual(s1["deltas"]["baseline"],True)
            self.assertEqual(s2["prior_archive_audit"]["status"],"VERIFIED_PRIOR_ARCHIVE")
            self.assertFalse(s2["deltas"]["baseline"])
            self.assertEqual(s2["deltas"]["triage_count"],0)
            self.assertTrue((folder/"integrated_quality_report.json").exists())
            self.assertTrue((folder/"identity_audit.json").exists())
            self.assertEqual(json.loads((folder/"daily_metrics.json").read_text())["runs"][-1]["records"],1)
    def test_score_fail_closed_even_with_many_sources(self):
        payload={"records":2000,"records_by_family":{},"source_audit":[
            {"source":"x","family":"DERIVATIVES_MARKET","status":"OK","records":1000},
            {"source":"y","family":"TOKENOMICS_SUPPLY_PROXY","status":"OK","records":1000}],
            "identity_mapping":{"anchored_distinct_cmc_ids":100},
            "archive_sha256":"sha","deltas":{"baseline":False}}
        out=integrated_quality(payload)
        self.assertFalse(out["certified_9_out_of_10"])
        self.assertIn("direct_contract_wallet_events_across_universe",out["acceptance_blockers"])
        self.assertFalse(out["source_class_coverage"]["TOKEN_UNLOCKS"])
    def test_provider_failures_isolated_in_integrated_capture(self):
        sources=({"key":"btc_mempool","family":"DIRECT_ONCHAIN_NETWORK",
                  "url":"https://test.example/a","max_bytes":1000},
                 {"key":"coingecko_supply","family":"TOKENOMICS_SUPPLY_PROXY",
                  "url":"https://test.example/b","max_bytes":1000})
        def fetch(url,size):
            if url.endswith("/a"):return {"count":1,"vsize":2}
            raise OSError("blocked")
        r=capture(market(),fetcher=fetch,now=NOW,sources=sources)
        self.assertEqual(r["metrics"]["records"],1)
        self.assertEqual(len(r["metrics"]["source_audit"]),2)
        self.assertEqual(r["metrics"]["successful_sources"],1)

if __name__=="__main__": unittest.main()
