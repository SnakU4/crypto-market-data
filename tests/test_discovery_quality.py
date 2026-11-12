import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("discovery_quality", ROOT/"src"/"discovery_quality.py")
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)


def lead(i, title, excerpt="", families=None):
    return dict(event_id=str(i), title=title, excerpt=excerpt,
                url=f"https://example.org/items/{i}", story_title_hash=str(title).lower(),
                published_utc="2026-11-10T00:00:00Z",
                source_families=families or ["COIN_RESEARCH"],
                context_origin="FEED_EXCERPT")


class QualityTests(unittest.TestCase):
    def test_main_tag_context_in_html_parser(self):
        parser=q.ArticleText()
        html="<html><main><h2>Governance transition</h2><p>" + (
            "The project provided detailed implementation requirements and a deployment "
            "calendar with phased network changes and documented validator obligations. " * 4
        ) + "</p></main></html>"
        parser.feed(html)
        self.assertGreater(len(" ".join(parser.main_parts)),250)
        self.assertEqual(parser.active,0)

    def test_title_only_is_not_substantive(self):
        self.assertFalse(q.has_additional_information("Protocol upgrade deployed", "Protocol upgrade deployed"))
    def test_long_new_text_adds_information(self):
        e="The team published the upgrade implementation with a measured validator downtime reduction of thirty percent. Mainnet deployment is scheduled for December, after a completed external audit and review of consensus changes."
        self.assertTrue(q.has_additional_information("Protocol upgrade deployed",e))
    def test_syndication_is_labelled_not_discarded(self):
        a=[lead(1,"Same news"),lead(2,"Same news"),lead(3,"Independent report")]
        stats=q.enrich(a,max_articles=0)
        self.assertEqual(len(a),3)
        self.assertEqual(stats["repeated_headline_urls"],2)
        self.assertEqual(stats["unique_title_clusters"],2)
        self.assertEqual(a[0]["information_status"],"REPEATED_HEADLINE")
    def test_article_enrichment_and_provenance(self):
        e=lead(1,"New open source release", families=["PROJECT_PRIMARY"])
        text="The maintainers published a signed release and detailed security notes after extensive regression testing. The patch changes peer discovery and improves handling of malformed network packets; independent reviewers verified the fix and a rollout is planned for the coming weeks."
        s=q.enrich([e],max_articles=1,fetcher=lambda url:text)
        self.assertEqual(s["article_fetch_substantive"],1)
        self.assertEqual(e["context_origin"],"PUBLIC_ARTICLE_EXTRACT")
        self.assertTrue(e["excerpt_adds_information"])
    def test_google_news_explicit_target_only(self):
        import urllib.parse
        link="https://publisher.example/story"
        wrapped="https://news.google.com/rss/articles/opaque?url="+urllib.parse.quote(link,safe="")
        self.assertEqual(q.direct_news_target(wrapped),link)
        self.assertIsNone(q.direct_news_target("https://news.google.com/rss/articles/opaque"))
        self.assertIsNone(q.direct_news_target("https://news.google.com/rss/articles/opaque?url=https://127.0.0.1/private"))

    def test_google_resolution_and_fetch_are_separate(self):
        e=lead(1,"Protocol update released")
        e["url"]="https://news.google.com/rss/articles/opaque"
        e["previously_seen"]=False
        paragraph=("The developers released the signed upgrade after six months of testing with validators "
                   "and independent reviewers. The release documents a new congestion control mechanism "
                   "and a deployment timeline with explicit rollback conditions for participating operators.")
        stats=q.enrich([e],max_articles=1,max_resolutions=1,
                       resolver=lambda _: "https://publisher.example/story",
                       fetcher=lambda _: paragraph)
        self.assertEqual(stats["google_news_resolution_succeeded"],1)
        self.assertEqual(stats["resolved_google_articles_fetched"],1)
        self.assertEqual(stats["article_fetch_substantive"],1)
        self.assertEqual(e["url"],"https://news.google.com/rss/articles/opaque")
        self.assertEqual(e["resolved_article_url"],"https://publisher.example/story")

    def test_unresolved_link_kept_without_fabrication(self):
        e=lead(1,"Breaking update")
        e["url"]="https://news.google.com/rss/articles/opaque"
        stats=q.enrich([e],max_articles=1,max_resolutions=1,resolver=lambda _:None,
                       fetcher=lambda _:self.fail("Should not attempt article fetch"))
        self.assertEqual(stats["google_news_resolution_attempted"],1)
        self.assertEqual(stats["article_fetch_attempted"],0)
        self.assertEqual(e["resolution_status"],"UNRESOLVED")
        self.assertEqual(e["information_status"],"LOW_INFORMATION")

    def test_budget_and_host_cap_preserve_all_leads(self):
        events=[lead(i,f"Report number {i}") for i in range(50)]
        for e in events:e["previously_seen"]=False
        stats=q.enrich(events,max_articles=30,max_resolutions=0,fetcher=lambda _:None)
        self.assertEqual(len(events),50)
        self.assertEqual(stats["article_fetch_attempted"],q.MAX_PER_HOST)
        self.assertEqual(sum(e["article_fetch_status"]=="NOT_ATTEMPTED" for e in events),50-q.MAX_PER_HOST)

    def test_private_addresses_blocked(self):
        for url in ("http://example.com/x","https://127.0.0.1/x","https://localhost/secret","https://10.0.0.1/x","file:///etc/passwd"):
            self.assertFalse(q.public_html_url(url))

if __name__=="__main__":
    unittest.main()
