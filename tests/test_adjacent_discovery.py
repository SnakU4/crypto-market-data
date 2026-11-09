import datetime as dt
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
import adjacent_discovery as d

class DiscoveryTests(unittest.TestCase):
    def market(self):
        assets=[dict(cmc_id=i,name=f'Tokenname{i}',symbol=f'T{i}',
                     cmc_quote={'ret_24h_pct':(i%5)*10,'ret_1h_pct':i%3},
                     perp_market={'oi_usd':200}) for i in range(1,101)]
        assets[0]['name']='Ethereum';assets[0]['symbol']='ETH'
        assets[1]['name']='Solana';assets[1]['symbol']='SOL'
        return {'assets':assets,'index':{'verified_constituents':100},'snapshot_completed_utc':'2026-11-06T12:00:00Z'}

    def test_open_ended_plan_and_targeted_queries(self):
        p=d.plan(self.market(),None)
        self.assertGreater(len(p),40)
        self.assertTrue(any(x[1]=='ANOMALY_DRIVEN' for x in p))
        self.assertTrue(any(x[1]=='SOCIAL_DISCUSSIONS' for x in p))
        self.assertTrue(any(x[1]=='ARXIV' for x in p))
        self.assertTrue(all(x[3].startswith('https://') for x in p))

    def test_coin_mentions_conservative_and_theme_broader_than_coin(self):
        self.assertEqual(d.coins_for('AI datacenter chips',self.market()['assets']),[])
        self.assertEqual(d.coins_for('Ethereum infrastructure breakthrough',self.market()['assets']),[1])
        self.assertEqual(d.coins_for('SOL power generation',self.market()['assets']),[])
        self.assertEqual(d.coins_for('Buying $SOL',self.market()['assets']),[2])
        self.assertIn('QUANTUM_SECURITY',d.themes_for('Quantum computing cryptography breakthrough'))

    def test_rss_without_timestamp_cannot_claim_verified_publication(self):
        feed=b'<rss><channel><item><title>Quantum hardware</title><link>https://example.com/article/1</link></item></channel></rss>'
        rows=d.xml_items(feed,'test','2026-11-06T12:00:00Z')
        self.assertEqual(len(rows),1)
        self.assertIsNone(rows[0]['published_utc'])
        self.assertEqual(d.parse_time('Fri, 06 Nov 2026 12:00:00 GMT'),dt.datetime(2026,11,6,12,tzinfo=dt.timezone.utc))

    def test_canonical_dedup_and_publication_exclusion(self):
        events=[dict(title='Quantum encryption breakthrough',url='https://example.com/a?tracking=1',published_utc='2026-11-06T10:00:00Z',source_id='google_theme_QUANTUM_SECURITY',source_type='RSS',observed_utc='2026-11-06T12:00:00Z'),
                dict(title='Quantum encryption breakthrough',url='https://example.com/a?tracking=2',published_utc='2026-11-06T10:00:00Z',source_id='gdelt_theme_QUANTUM_SECURITY',source_type='GDELT',observed_utc='2026-11-06T12:00:00Z'),
                dict(title='Future news',url='https://example.com/b',published_utc='2099-01-01T00:00:00Z',source_id='google_theme_AI_COMPUTE',source_type='RSS',observed_utc='2026-11-06T12:00:00Z')]
        class Mock:
            def __init__(self):self.calls=[]
            def get(self,ident,kind,target):
                self.calls.append(dict(source_id=ident,transport_status='OK',observed_utc=d.iso(d.utcnow())))
                if ident.startswith('google_theme_QUANTUM_SECURITY'):
                    return b'<rss><channel><item><title>Quantum encryption breakthrough</title><link>https://example.com/a?tracking=1</link><pubDate>Fri, 06 Nov 2026 10:00:00 GMT</pubDate></item></channel></rss>'
                if ident.startswith('gdelt_theme_'):
                    return {'articles':[{'title':'Quantum encryption breakthrough','url':'https://example.com/a?tracking=2','seendate':'20261106T100000Z'}]} if ident.endswith('QUANTUM_SECURITY') else {'articles':[]}
                if ident.startswith('hn_'):return {'hits':[]}
                if ident.startswith('bluesky_'):return {'posts':[]}
                if ident.startswith('github_'):return []
                return b'<rss><channel/></rss>'
        m=Mock();result=d.consolidate(self.market(),m,workers=2)
        self.assertEqual(result['status']['official_cmc100_verified'],100)
        self.assertEqual(result['status']['successful_transport'],len(m.calls))
        self.assertEqual(result['status']['unique_leads_stored'],1)
        self.assertEqual(result['events'][0]['direct_price_catalyst_verification'],'NOT_VERIFIED')
        self.assertEqual(result['events'][0]['price_direction'],'UNKNOWN')

    def test_github_first_party_security_and_releases(self):
        now='2026-11-06T10:00:00Z'
        src=d.github_items([{'name':'Release 1.2.3','html_url':'https://github.com/example/repo/releases/tag/1.2.3','published_at':now}],
                           'github_releases_example__repo',now)
        self.assertEqual(src[0]['source_type'],'GITHUB_RELEASE_OR_ADVISORY')
        self.assertEqual(src[0]['repo'],'example__repo')
        self.assertEqual(src[0]['published_utc'],now)
        self.assertTrue(any(x[1]=='SOFTWARE_SECURITY_ADVISORIES' for x in d.plan(self.market())))

    def test_hackernews_and_bluesky_platform_metadata(self):
        h=d.hn_items({'hits':[{'title':'New AI research','objectID':'3','points':33,'num_comments':8,'created_at_i':1793966400}]},'hn_test','2026-11-06T12:00:00Z')
        self.assertEqual(h[0]['engagement']['points'],33)
        b=d.bluesky_items({'posts':[{'uri':'at://did:abc/app.bsky.feed.post/postid','author':{'handle':'abc.bsky.social'},'record':{'text':'Open source zero knowledge release','createdAt':'2026-11-06T10:00:00Z'},'likeCount':9}]},'bsky_test','2026-11-06T12:00:00Z')
        self.assertEqual(b[0]['author_handle'],'abc.bsky.social')
        self.assertEqual(b[0]['engagement']['likes'],9)

    def test_written_artifacts_immutable_and_csv_usable(self):
        status={'capture_started_utc':'2026-11-06T12:00:00Z','unique_leads_stored':1}
        event=dict(event_id='abc',title='Quantum AI',url='https://example.com',source_id='x',source_type='RSS',published_utc=None,publication_time_status='UNKNOWN',first_observed_utc='2026-11-06T12:00:00Z',candidate_coin_ids=[],theme_leads=['AI_COMPUTE'],direct_price_catalyst_verification='NOT_VERIFIED')
        data={'status':status,'events':[event],'first_seen':{'abc':'2026-11-06T12:00:00Z'},'query_plan':[], 'per_coin_candidate_counts':{}}
        with tempfile.TemporaryDirectory() as p:
            out=pathlib.Path(p);arch=d.write_bundle(data,out)
            self.assertTrue(arch.is_file());self.assertTrue((out/'leads.csv').exists())
            self.assertEqual(len(json.loads((out/'latest.json').read_text())['events']),1)
            with self.assertRaises(FileExistsError):d.write_bundle(data,out)

    def test_rejects_unverified_universe(self):
        bad=self.market();bad['assets']=bad['assets'][:-1]
        with self.assertRaisesRegex(ValueError,'100 unique'):
            d.consolidate(bad,None)

if __name__=='__main__':unittest.main()