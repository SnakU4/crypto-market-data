"""Offline quality tests for public project-site feed candidate research."""
import datetime as dt
import json
import pathlib
import sys
import tempfile
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"src"))
import coin_primary_feed_research as m

UTC=dt.timezone.utc
NOW=dt.datetime.now(UTC)
ASSETS=[{"cmc_id":52,"name":"XRP","symbol":"XRP"}]
PROFILES={"52":{"primary_links_unverified":{"website":["https://ripple.example.org/"]}}}
HTML=b'<html><head><link rel="alternate" type="application/rss+xml" href="/blog/feed.xml" /></head></html>'
EXCERPT=("XRP Ledger developers have announced a detailed release process for "
         "the network infrastructure, including validator configuration changes, "
         "network consensus testing, technical acceptance criteria and a new "
         "integration plan for affected XRP Ledger application operators.")
RSS=("<rss><channel><item><title>XRP Ledger validator network migration plan</title>"
     "<link>https://ripple.example.org/blog/xrp-validator</link>"
     "<pubDate>Fri, 13 Nov 2026 11:00:00 GMT</pubDate>"
     "<description>"+EXCERPT+"</description>"
     "</item></channel></rss>").encode()

def fetch(url):
    if url=="https://ripple.example.org/":return HTML,"OK"
    if url=="https://ripple.example.org/blog/feed.xml":return RSS,"OK"
    return None,"HTTP_404"

class SourceTests(unittest.TestCase):
    def test_project_feed_yields_individually_substantive_article(self):
        with tempfile.TemporaryDirectory() as temp:
            rows,h,a=m.collect(temp,ASSETS,PROFILES,[],NOW,network=True,
                               max_coins=1,get=fetch)
            self.assertEqual(a["project_domains_attempted"],1)
            self.assertEqual(a["coins_with_new_source_excerpts"],1)
            self.assertEqual(len(rows),1)
            row=rows[0]
            self.assertEqual(row["candidate_cmc_ids"],[52])
            self.assertEqual(row["scope"],"ASSET_CANDIDATE")
            self.assertEqual(row["context_origin"],"PUBLIC_PROJECT_WEBSITE_RSS_OR_ATOM")
            self.assertEqual(row["claim_status"],"PUBLISHER_TEXT_NOT_FACT_VERIFIED")
            self.assertEqual(h["domains"]["ripple.example.org"]["substantive_items"],1)
            p=pathlib.Path(temp)/m.HISTORY;p.parent.mkdir(parents=True)
            p.write_text(json.dumps(h),encoding="utf8")
            _,_,b=m.collect(temp,ASSETS,PROFILES,[],NOW,network=True,
                            max_coins=1,get=fetch)
            self.assertEqual(b["project_domains_attempted"],0)

    def test_unrelated_headline_is_not_coin_news(self):
        fake=RSS.replace(b"XRP Ledger validator network migration plan",
                         b"Unrelated payment service plan")
        with tempfile.TemporaryDirectory() as temp:
            out,_,a=m.collect(temp,ASSETS,PROFILES,[],NOW,network=True,
                get=lambda url:(fake,"OK") if url.endswith(".xml") else fetch(url))
            self.assertEqual(a["coins_with_new_source_excerpts"],0)
            self.assertEqual(out,[])


    def test_project_specific_feed_allows_generic_release_title_but_not_exchange(self):
        generic=RSS.replace(b"XRP Ledger validator network migration plan",
                            b"Validator network migration plan")
        with tempfile.TemporaryDirectory() as temp:
            items,_,audit=m.collect(temp,ASSETS,PROFILES,[],NOW,network=True,
                get=lambda url:(generic,"OK") if url.endswith(".xml") else fetch(url))
            self.assertEqual(audit["coins_with_new_source_excerpts"],1)
            self.assertEqual(len(items),1)
        exchange={"52":{"primary_links_unverified":{"website":["https://binance.com/"]}}}
        def exchange_feed(url):
            if url=="https://binance.com/":
                return HTML,"OK"
            return generic,"OK"
        with tempfile.TemporaryDirectory() as temp:
            items,_,audit=m.collect(temp,ASSETS,exchange,[],NOW,network=True,get=exchange_feed)
            self.assertEqual(audit["coins_with_new_source_excerpts"],0)
            self.assertEqual(items,[])

    def test_historical_replay_never_queries_the_network(self):
        with tempfile.TemporaryDirectory() as temp:
            rows,_,audit=m.collect(temp,ASSETS,PROFILES,[],NOW,network=False,
                get=lambda _: (_ for _ in ()).throw(AssertionError("network used")))
            self.assertEqual(rows,[])
            self.assertEqual(audit["project_domains_attempted"],0)

if __name__=="__main__": unittest.main()
