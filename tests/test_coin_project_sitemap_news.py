"""Quality tests for public publisher sitemap discovery, as-of dates, false matches."""
import datetime as dt
import json
import pathlib
import sys
import tempfile
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"src"))
import coin_project_sitemap_news as mod

NOW=dt.datetime.now(dt.timezone.utc)
DAY=(NOW-dt.timedelta(days=1)).strftime("%Y-%m-%d")
URL="https://example.org/blog/protocol-upgrade"
ASSET={"cmc_id":444,"symbol":"EXM","name":"Example Protocol"}
PROFILES={"444":{"primary_links_unverified":{"website":["https://example.org/"]}}}
SITEMAP=(f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    f'<url><loc>{URL}</loc><lastmod>{DAY}</lastmod></url>'
    '</urlset>').encode("utf-8")
TEXT=("Example Protocol introduced an upgrade proposal to improve node "
      "transaction validation, harden network message processing and align "
      "operator requirements across several protocol components. The "
      "announcement includes a rollout procedure for validators, technical "
      "testing conditions, deployment milestones and user migration steps "
      "with specific changes to account functionality and security controls.")

class SitemapTests(unittest.TestCase):
    def test_date_only_is_lastmod_not_publication(self):
        rows,_,status=mod.parse_sitemap(SITEMAP,"https://example.org/sitemap.xml",NOW)
        self.assertEqual(status,"URLSET")
        self.assertEqual(len(rows),1)
        self.assertIn(DAY,rows[0]["sitemap_lastmod_utc"])
    def test_real_article_text_not_website_url_satisfies_context(self):
        with tempfile.TemporaryDirectory() as root:
            events,cache,audit=mod.collect(root,[ASSET],PROFILES,[],NOW,network=True,
                download=lambda url:(SITEMAP,"OK"),
                extractor=lambda url:TEXT)
            self.assertEqual(audit["project_sitemaps_probed"],1)
            self.assertEqual(audit["new_substantive_undated_site_articles"],1)
            self.assertEqual(len(events),1)
            self.assertIsNone(events[0]["published_utc"])
            self.assertEqual(events[0]["source_date_caveat"],
                "SITEMAP_LASTMOD_IS_NOT_ARTICLE_PUBLICATION_TIME")
            p=pathlib.Path(root)/mod.HISTORY
            p.parent.mkdir(parents=True)
            p.write_text(json.dumps(cache),encoding="utf-8")
            replay,_,audit2=mod.collect(root,[ASSET],PROFILES,[],NOW+dt.timedelta(minutes=1),
                network=False,download=lambda _ : (_ for _ in ()).throw(AssertionError("network")))
            self.assertEqual(len(replay),1)
            self.assertEqual(audit2["project_sitemaps_probed"],0)
    def test_wrong_coin_is_never_counted_as_news(self):
        with tempfile.TemporaryDirectory() as root:
            rows,_,audit=mod.collect(root,[ASSET],PROFILES,[],NOW,network=True,
                download=lambda url:(SITEMAP,"OK"),
                extractor=lambda url:"Unrelated future market events with technical context "*15)
            self.assertEqual(rows,[])
            self.assertEqual(audit["new_substantive_undated_site_articles"],0)
    def test_other_beam_chain_website_quarantined(self):
        asset={"cmc_id":28298,"name":"Beam","symbol":"BEAM"}
        profiles={"28298":{"primary_links_unverified":{"website":["https://beam.mw/"]}}}
        with tempfile.TemporaryDirectory() as root:
            rows,_,audit=mod.collect(root,[asset],profiles,[],NOW,network=True,
                download=lambda _: (_ for _ in ()).throw(AssertionError("wrong project")))
            self.assertEqual(rows,[])
            self.assertTrue(audit["quarantine"])

if __name__=="__main__":unittest.main()
