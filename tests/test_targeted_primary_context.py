"""Keyless primary-project docs: exact identity, evidence depth and PIT tests."""
import datetime as dt
import json
import pathlib
import sys
import tempfile
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"src"))
import targeted_primary_context as src

UTC=dt.timezone.utc

class PrimaryContextTests(unittest.TestCase):
    def test_project_identity_cannot_be_inferred_from_symbol_only(self):
        rec=src.REGISTRY[3957]
        self.assertFalse(src.valid_project({"name":"Fake project","symbol":"LEO"},rec))
        self.assertTrue(src.valid_project({"name":"UNUS SED LEO","symbol":"LEO"},rec))
        self.assertFalse(src.has_identity("LEOPARD token","LEO"))

    def test_original_issuer_and_exchange_source_are_not_conflated(self):
        assets=[{"cmc_id":3957,"name":"UNUS SED LEO","symbol":"LEO"},
                {"cmc_id":38590,"name":"币安人生","symbol":"币安人生"}]
        text=("UNUS SED LEO is a utility token with a published issuer description. "
              "The publication documents operational fee discounts and detailed "
              "holder eligibility requirements, including the transaction process "
              "and related token mechanisms, blockchain integrations and service "
              "usage. These details make the document specifically informative "
              "rather than an exchange price ticker or a bare project title.")
        secondary=("币安人生 is a community meme token trading on BNB Chain. "
                   "The exchange notice identifies its chain, basic asset type "
                   "and listing characteristics, explaining that this is a "
                   "community-oriented memecoin with potential market volatility "
                   "and no guaranteed financial outcome or underlying project "
                   "utility. The exchange warning does not endorse the token.")
        def fake(url):
            return secondary if "binance.com" in url else text
        with tempfile.TemporaryDirectory() as d:
            doc,audit=src.collect(d,assets,dt.datetime.now(UTC),network=True,fetcher=fake)
            self.assertEqual(audit["substantive_issuer_dossiers"],1)
            self.assertEqual(audit["substantive_exchange_only_dossiers"],1)
            self.assertEqual(len(audit["targeted_gaps"]),0)
            self.assertEqual(doc["profiles"]["3957"]["source_kind"],"ISSUER_DOCUMENTATION")
            self.assertEqual(doc["profiles"]["38590"]["source_kind"],"EXCHANGE_ANNOUNCEMENT_NOT_ISSUER")

    def test_mismatched_text_not_counted(self):
        assets=[{"cmc_id":39064,"name":"Midnight","symbol":"NIGHT"}]
        with tempfile.TemporaryDirectory() as d:
            _,audit=src.collect(d,assets,dt.datetime.now(UTC),network=True,
                                fetcher=lambda url:"Generic landing page about unrelated tokens and trading."*10)
            self.assertEqual(audit["substantive_issuer_dossiers"],0)
            self.assertEqual(len(audit["targeted_gaps"]),1)

    def test_historical_replay_cannot_use_later_primary_fetch(self):
        asset={"cmc_id":3957,"name":"UNUS SED LEO","symbol":"LEO"}
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/src.CACHE
            p.parent.mkdir(parents=True)
            p.write_text(json.dumps({"profiles":{"3957":{
                "cmc_id":3957,"name":"UNUS SED LEO","symbol":"LEO",
                "source_url":src.REGISTRY[3957][2][0][0],
                "first_observed_utc":"2026-11-14T15:00:00Z",
                "source_kind":"ISSUER_DOCUMENTATION","substantive":True}}}))
            doc,a=src.collect(d,[asset],dt.datetime(2026,11,13,tzinfo=UTC),network=False)
            self.assertEqual(doc["profiles"],{})
            self.assertEqual(a["substantive_issuer_dossiers"],0)

if __name__=="__main__":
    unittest.main()
