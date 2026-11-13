"""Offline acceptance tests for free coin-specific project-background sources."""
import datetime as dt
import io
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import coin_context_sources as cc

UTC = dt.timezone.utc

class MockResponse:
    def __init__(self, data):
        self.raw = io.BytesIO(json.dumps(data).encode("utf-8"))
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def read(self, n=-1):
        return self.raw.read(n)

class CoinContextTests(unittest.TestCase):
    def test_exact_identity_rejects_ambiguous_tickers(self):
        assets = [{"cmc_id": 7, "name": "Alpha", "symbol": "ABC"}]
        rows = [{"id": "abc-alpha", "name": "Alpha", "symbol": "ABC"},
                {"id": "abc-different", "name": "Different", "symbol": "ABC"}]
        self.assertEqual(cc.exact_match(assets, rows), {"7": "abc-alpha"})
        rows.append({"id": "abc-duplicate", "name": "Alpha", "symbol": "ABC"})
        self.assertEqual(cc.exact_match(assets, rows), {})

    def test_display_annotation_normalization_and_unicode(self):
        assets=[{"cmc_id":10,"name":"Sun [New]","symbol":"SUN"},
                {"cmc_id":11,"name":"Polygon (prev. MATIC)","symbol":"POL"},
                {"cmc_id":12,"name":"币安人生","symbol":"币安人生"}]
        listed=[{"id":"sun","name":"Sun","symbol":"SUN"},
                {"id":"polygon","name":"Polygon","symbol":"POL"},
                {"id":"chinese","name":"币安人生","symbol":"币安人生"}]
        self.assertEqual(cc.exact_match(assets,listed),{"10":"sun","11":"polygon","12":"chinese"})
        self.assertEqual(cc.project_name("Polygon (prev. MATIC)"),cc.project_name("Polygon"))

    def test_short_generic_profiles_do_not_count_as_substantive(self):
        asset = {"cmc_id": 1, "name": "Alpha", "symbol": "ABC"}
        row = {"id": "abc-alpha", "name": "Alpha", "symbol": "ABC",
               "description": "Alpha is a coin.", "tags": [{"name": "DeFi"}]}
        profile = cc.valid_profile(asset, row, "coinpaprika", "2026-11-13T12:00:00Z")
        self.assertFalse(profile["has_substantive_descriptive_context"])
        row["description"] = ("Alpha supports a specific settlement network with verifiable "
            "open-source implementations and documented operating requirements across "
            "different chains, with explicit consensus assumptions and transaction "
            "processing constraints for platform integrators.")
        profile = cc.valid_profile(asset, row, "coinpaprika", "2026-11-13T12:00:00Z")
        self.assertTrue(profile["has_substantive_descriptive_context"])
        self.assertEqual(profile["provider_identity_validation"], "EXACT_NAME_AND_SYMBOL_MATCH")
        self.assertEqual(profile["context_type"], "EVERGREEN_PROJECT_BACKGROUND_NOT_DATED_CATALYST")

    def test_keyless_source_and_coin_gaps_are_audited(self):
        assets = [{"cmc_id": 1, "name": "Alpha", "symbol": "ABC"},
                  {"cmc_id": 2, "name": "Beta", "symbol": "BTA"}]
        listing = [{"id": "abc-alpha", "name": "Alpha", "symbol": "ABC"},
                   {"id": "bta-beta", "name": "Beta", "symbol": "BTA"}]
        item = {"id": "abc-alpha", "name": "Alpha", "symbol": "ABC",
                "description": ("Alpha supports secure cross-chain messaging with explicit "
                     "network validation requirements, published developer interfaces, "
                     "technical implementation details and operational assumptions "
                     "that explain its practical project role."),
                "tags": [{"name": "Infrastructure"}], "links": {"website": ["https://alpha.example.org"]}}
        rows = {cc.PAPRIKA + "/coins": listing,
                cc.PAPRIKA + "/coins/abc-alpha": item,
                cc.PAPRIKA + "/coins/bta-beta": {"id": "bta-beta", "name": "Beta",
                    "symbol": "BTA", "description": "A token."}}
        def fake(request, timeout):
            return MockResponse(rows[request.full_url])
        with tempfile.TemporaryDirectory() as d:
            cutoff = dt.datetime.now(UTC)
            doc, audit = cc.collect_profiles(d, assets, cutoff, network=True,
                                             opener=fake, max_gecko=0, max_extra_per_type=0)
            self.assertEqual(audit["calls"], 3)
            self.assertEqual(audit["substantive_project_profiles"], 1)
            self.assertEqual([x["cmc_id"] for x in audit["profile_gaps"]], [2])
            self.assertFalse(audit["all_100_substantive_background"])
            self.assertTrue(doc["profiles"]["1"]["has_substantive_descriptive_context"])
            self.assertFalse(doc["profiles"]["2"]["has_substantive_descriptive_context"])
            self.assertFalse(audit["recent_24h_catalyst_coverage_NOT_INFERRED"] is False)

    def test_events_are_dated_but_not_claimed_to_be_publication_or_price_catalysts(self):
        asof = dt.datetime(2026, 11, 13, 11, tzinfo=UTC)
        rows = [{"title": "Protocol upgrade vote", "date": "2026-11-18T10:00:00Z",
                 "description": ("The community plans a staged upgrade following an "
                                 "operator vote and published test deployment procedures "
                                 "that precede any prospective mainnet migration.")},
                {"title": "Outdated conference", "date": "2025-01-01T00:00:00Z"}]
        events = cc.extra_context("events", rows, "2026-11-13T11:00:00Z", asof)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_date_utc"], "2026-11-18T10:00:00Z")
        self.assertEqual(events[0]["relation_status"], "THIRD_PARTY_COIN_EVENT_DATE_NOT_PUBLICATION_DATE")

    def test_markets_are_labelled_as_non_unique_trade_volume(self):
        markets = cc.extra_context("markets", [{
            "exchange": {"name":"VenueA"}, "pair":"ABC/USD",
            "quotes":{"USD":{"volume_24h":1200}}},
            {"exchange":{"name":"VenueB"}, "pair":"ABC/USDT",
             "quotes":{"USD":{"volume_24h":500}}}], "2026-11-13T11:00:00Z",
             dt.datetime(2026, 11, 13, 11, tzinfo=UTC))
        self.assertEqual(markets["reported_pair_count_with_usd_volume"], 2)
        self.assertEqual(markets["total_reported_volume_across_pairs_usd_NOT_UNIQUE_TRADING_VOLUME"], 1700)

    def test_historical_replay_does_not_fetch_future_cached_profiles(self):
        assets = [{"cmc_id": 1, "name": "Alpha", "symbol": "ABC"}]
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / cc.CACHE_PATH
            p.parent.mkdir(parents=True)
            p.write_text(json.dumps({"profiles": {"1": {
                "cmc_id": 1, "name": "Alpha", "symbol": "ABC",
                "observed_utc": "2026-11-14T00:00:00Z",
                "has_substantive_descriptive_context": True}}}))
            cutoff = dt.datetime(2026, 11, 13, tzinfo=UTC)
            doc, audit = cc.collect_profiles(d, assets, cutoff, network=False)
            self.assertEqual(audit["profile_present"], 0)
            self.assertEqual(len(audit["profile_gaps"]), 1)
            self.assertEqual(doc["profiles"], {})

if __name__ == "__main__":
    unittest.main()
