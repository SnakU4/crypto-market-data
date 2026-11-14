"""Offline tests for strictly publisher-grounded, bounded Google News resolution."""
import datetime as dt
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"src"))
import coin_news_resolution as mod

UTC=dt.timezone.utc
NOW=dt.datetime(2026,11,14,12,tzinfo=UTC)
ARTICLE=("The XRP Ledger published details explaining how new settlement "
         "infrastructure would improve operational controls, implement a phased "
         "system migration, and mitigate counterparty settlement risks. "
         "The technical documentation specifies data validation steps, performance "
         "requirements, governance approval and planned integration testing before rollout.")

def fixture():
    asset={"cmc_id":52,"name":"XRP","symbol":"XRP"}
    event={"id":"google:1","title":"XRP Ledger update details settlement infrastructure",
           "url":"https://news.google.com/rss/articles/aaa",
           "excerpt":"XRP Ledger update details settlement infrastructure",
           "candidate_cmc_ids":[52],"scope":"ASSET_CANDIDATE",
           "priority":25,"published_utc":"2026-11-14T11:00:00Z"}
    return [asset],[event]

class Tests(unittest.TestCase):
    def test_one_valid_original_publisher_and_cache(self):
        a,e=fixture();calls=[]
        def resolve(url): calls.append(url);return "https://example.org/publisher/xrp-research"
        with tempfile.TemporaryDirectory() as d:
            articles,history,audit=mod.collect(d,a,e,network=True,cutoff=NOW,
                resolver=resolve,fetcher=lambda u:ARTICLE)
            self.assertEqual(audit["resolved_substantive_articles"],1)
            self.assertEqual(audit["newly_covered_coins"],1)
            self.assertEqual(len(articles),1)
            self.assertEqual(articles[0]["lead_url"],e[0]["url"])
            self.assertEqual(articles[0]["url"],"https://example.org/publisher/xrp-research")
            p=pathlib.Path(d)/mod.HISTORY;p.parent.mkdir(parents=True)
            p.write_text(json.dumps(history),encoding="utf8")
            articles2,_,audit2=mod.collect(d,a,e,network=True,cutoff=NOW,
                resolver=resolve,fetcher=lambda u:ARTICLE)
            self.assertEqual(audit2["attempted"],0)
            self.assertEqual(len(calls),1)
            self.assertEqual(articles2,[])

    def test_no_article_from_title_or_google_itself(self):
        a,e=fixture()
        with tempfile.TemporaryDirectory() as d:
            for url in (None,"https://news.google.com/rss/articles/other"):
                articles,_,audit=mod.collect(d,a,e,network=True,cutoff=NOW,
                    resolver=lambda _:url,fetcher=lambda _:ARTICLE)
                self.assertEqual(articles,[])
                self.assertEqual(audit["resolved_substantive_articles"],0)

    def test_no_wrong_coin_substitution(self):
        a,e=fixture()
        with tempfile.TemporaryDirectory() as d:
            articles,_,audit=mod.collect(d,a,e,network=True,cutoff=NOW,
                resolver=lambda _:"https://example.org/other",
                fetcher=lambda _:("A different protocol has announced entirely different "
                     "technical infrastructure plans with governance consultation and "
                     "technical implementation activities."*3))
            self.assertEqual(audit["resolved_substantive_articles"],0)
            self.assertEqual(articles,[])

    def test_cannot_use_nonmatching_title_or_historical_live_network(self):
        a,e=fixture();e[0]["title"]="Unrelated football update"
        with tempfile.TemporaryDirectory() as d:
            _,_,audit=mod.collect(d,a,e,network=True,cutoff=NOW,
                resolver=lambda _:"https://example.org/research",fetcher=lambda _:ARTICLE)
            self.assertEqual(audit["attempted"],0)
            _,_,audit=mod.collect(d,a,e,network=False,cutoff=NOW)
            self.assertTrue(audit["historical_network_disabled"])
            self.assertEqual(audit["attempted"],0)

if __name__=="__main__":unittest.main()
