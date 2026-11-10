import datetime as dt
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"src"))
from crypto_evidence_engine import (capture,save,parse_chains,parse_stablecoins,
                                    parse_bybit_tickers,parse_bybit_instruments,parse_kraken_tickers)
NOW=dt.datetime(2026,11,10,16,0,tzinfo=dt.timezone.utc)

def market():
    return {"assets":[{"cmc_id":i+1,"symbol":"T"+str(i)} for i in range(100)],
            "index":{"verified_constituents":100}}

class EngineTests(unittest.TestCase):
    def test_chains_skip_nonfinite_and_parse_tvl(self):
        result=parse_chains([{"name":"Ethereum","tvl":6000000},{"name":"Broken","tvl":"NaN"}],NOW)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["metrics"]["tvl_usd"],6000000)
        self.assertIsNone(result[0]["published_utc"])
    def test_stablecoin_supply(self):
        x=parse_stablecoins([{"name":"Ethereum","totalCirculating":{"peggedUSD":10000000}}],NOW)
        self.assertEqual(x[0]["metrics"]["circulating_usd"],10000000)
    def test_stablecoin_updated_api_schema(self):
        rows=parse_stablecoins([{"name":"Ethereum","totalCirculatingUSD":{"peggedUSD":1337000000}}],NOW)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["metrics"]["circulating_usd"],1337000000)
    def test_kraken_derivatives(self):
        rows=parse_kraken_tickers({"result":"success","tickers":[
            {"symbol":"pf_ethusd","tag":"perpetual","pair":"ETH:USD",
             "openInterest":1000.5,"fundingRate":0.0002,"markPrice":3000},
            {"symbol":"fi_btc_2027","tag":"month","openInterest":300}]},NOW)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["metrics"]["fundingRate"],0.0002)
        self.assertEqual(rows[0]["coin_identity_status"],"NOT_VERIFIED")
    def test_bybit_funding_open_interest_without_coin_guess(self):
        x=parse_bybit_tickers({"retCode":0,"result":{"list":[
          {"symbol":"ETHUSDT","lastPrice":"4000","openInterestValue":"12000000",
           "fundingRate":"0.0001","nextFundingTime":"1794336000000"}]}},NOW)
        self.assertEqual(x[0]["metrics"]["fundingRate"],0.0001)
        self.assertEqual(x[0]["coin_identity_status"],"NOT_VERIFIED")
        self.assertEqual(x[0]["time_semantics"],"LIVE_SNAPSHOT_NOT_HISTORICAL_PUBLICATION")
    def test_instruments_are_metadata(self):
        x=parse_bybit_instruments({"retCode":0,"result":{"list":[
          {"symbol":"BTCUSDT","baseCoin":"BTC","quoteCoin":"USDT",
           "status":"Trading","contractType":"LinearPerpetual"}]}},NOW)
        self.assertEqual(x[0]["attributes"]["baseCoin"],"BTC")
        self.assertEqual(x[0]["metrics"],{})
    def test_provider_isolation_and_immutable_archive(self):
        sources=(
          {"key":"defillama_chains","family":"ONCHAIN_AGGREGATE_PROXY","url":"https://one.example","max_bytes":1000},
          {"key":"bybit_linear_tickers","family":"DERIVATIVES_MARKET","url":"https://two.example","max_bytes":1000},
          {"key":"defillama_stablecoins","family":"STABLECOIN_SUPPLY","url":"https://three.example","max_bytes":1000})
        def fake(url,size):
            if "two" in url:raise OSError("restricted")
            if "one" in url:return [{"name":"Ethereum","tvl":100}]
            return [{"name":"Ethereum","totalCirculating":{"peggedUSD":50}}]
        result=capture(market(),fetcher=fake,now=NOW,sources=sources)
        self.assertEqual(result["metrics"]["successful_sources"],2)
        self.assertEqual(result["metrics"]["records"],2)
        self.assertFalse(result["metrics"]["stage1_9_of_10_verified"])
        with tempfile.TemporaryDirectory() as d:
            status=save(result,pathlib.Path(d))
            self.assertTrue((pathlib.Path(d)/"latest.json").exists())
            self.assertTrue(list(pathlib.Path(d).rglob("*.gz")))
            with self.assertRaises(FileExistsError):save(result,pathlib.Path(d))
    def test_reject_non_verified_cmc100(self):
        with self.assertRaises(ValueError):capture({"assets":[],"index":{}},fetcher=lambda *_:[],now=NOW,sources=())
    def test_malformed_bybit_is_hard_failure(self):
        with self.assertRaises(ValueError):parse_bybit_tickers({"retCode":10001,"result":{"list":[]}},NOW)

if __name__=="__main__":unittest.main()
