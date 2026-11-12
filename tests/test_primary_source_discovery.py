"""Offline tests for safe, actually executed new publisher feed discovery."""
import datetime as dt, pathlib, sys, unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"src"))
import primary_source_discovery as d

class DiscoveryTests(unittest.TestCase):
    def test_feed_autodiscovery_and_context(self):
        url="https://new-financial-publisher.org/"
        html=b'''<html><head><link rel="alternate" type="application/rss+xml"
                href="/news/feed.xml"></head></html>'''
        links=d.inspect_feed_links(html.decode(),url)
        self.assertEqual(links,["https://new-financial-publisher.org/news/feed.xml"])
        rss=b'''<rss><channel><item>
        <title>Central-bank consultation on digital settlement</title>
        <link>https://new-financial-publisher.org/press/one</link>
        <pubDate>Thu, 12 Nov 2026 07:00:00 GMT</pubDate>
        <description><![CDATA[Detailed public consultation material on a new
        financial settlement interface. The document specifies a proposed
        operational timetable, participating bank requirements and review steps.
        It does not prove any token-price effect.]]></description>
        </item></channel></rss>'''
        items=d.parsed_feed(rss,"DYNAMIC_TEST","2026-11-12T07:30:00Z")
        self.assertEqual(len(items),1)
        self.assertTrue(items[0]["excerpt"].startswith("Detailed"))
        self.assertEqual(items[0]["claim_status"],
                         "PUBLISHER_SOURCE_UNVERIFIED_COIN_RELEVANCE")
        self.assertFalse(items[0]["candidate_cmc_ids"])
    def test_network_source_chain_bounded(self):
        html=b'''<html><link rel="alternate" type="application/atom+xml"
              href="/atom.xml"></html>'''
        xml=b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
            <title>Economic release</title>
            <link href="https://publisher.com/article"/>
            <updated>2026-11-12T07:00:00Z</updated>
            <summary>Details show an independently published financial infrastructure
            roadmap with a deployment timetable and defined supervisory milestones.</summary>
            </entry></feed>'''
        class Response:
            def __init__(self,url):self.url=url
            def __enter__(self):return self
            def __exit__(self,*a):return False
            def geturl(self):return self.url
            def read(self,limit):return xml if self.url.endswith("atom.xml") else html
        def opener(req,timeout):return Response(req.full_url)
        proposals={"candidate_publishers":[{"domain":"publisher.com"}]}
        with patch.object(d,"public_dns",lambda u:True),patch.object(d,"robots_permit",lambda u:True):
            items,audit=d.discover(proposals,"2026-11-12T07:30:00Z",max_sites=1,opener=opener)
        self.assertEqual(len(items),1)
        self.assertEqual(audit["domains_attempted"],1)
        self.assertEqual(audit["domains_found_content"],1)
        more,new_audit=d.discover(proposals,"2026-11-12T07:30:00Z",
                                  max_sites=1,skip_domains=["publisher.com"])
        self.assertEqual(more,[])
        self.assertEqual(new_audit["domains_attempted"],0)
    def test_rejects_unsafe_links(self):
        html='<link rel="alternate" type="application/rss+xml" href="http://localhost/rss">'
        self.assertEqual(d.inspect_feed_links(html,"https://example.com/"),[])
        self.assertFalse(d.is_valid_source_url("http://localhost/rss"))
if __name__=="__main__":unittest.main()
