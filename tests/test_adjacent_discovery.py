import csv
import datetime as dt
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))
import adjacent_discovery as d


class DiscoveryTests(unittest.TestCase):
    def market(self):
        assets = [dict(cmc_id=i, name=f'Tokenname{i}', symbol=f'T{i}',
                       cmc_quote={'ret_24h_pct': (i % 5)*10, 'ret_1h_pct': i % 3},
                       perp_market={'oi_usd': 200}) for i in range(1, 101)]
        assets[0]['name']='Ethereum';assets[0]['symbol']='ETH'
        assets[1]['name']='Solana';assets[1]['symbol']='SOL'
        return {'assets': assets, 'index': {'verified_constituents': 100},
                'snapshot_completed_utc':'2026-11-09T02:00:00Z'}

    def test_open_ended_plan_and_targeted_queries(self):
        plans=d.plan(self.market(),None)
        self.assertGreater(len(plans),40)
        self.assertTrue(any(x[1]=='ANOMALY_DRIVEN' for x in plans))
        self.assertTrue(any(x[1]=='SOCIAL_DISCUSSIONS' for x in plans))
        self.assertTrue(any(x[1]=='ARXIV' for x in plans))
        self.assertTrue(all(x[3].startswith('https://') for x in plans))

    def test_no_coin_matcher_or_coin_relevance_scoring(self):
        self.assertFalse(hasattr(d,'coins_for'))
        self.assertIn('QUANTUM_SECURITY',d.themes_for('Quantum computing cryptography breakthrough'))
        m=self.market()
        # Words like Ethereum/Solana/Avalanche in science titles have no decision role.
        class Mock:
            def __init__(self):self.calls=[]
            def get(self,ident,kind,target):
                self.calls.append(dict(source_id=ident,transport_status='OK',observed_utc=d.iso(d.utcnow())))
                if ident=='arxiv_crypto':
                    return b'<rss><channel><item><title>Avalanche noise in silicon circuits</title><link>https://example.com/science</link></item></channel></rss>'
                return {'hits':[]} if ident.startswith('hn_') else {'posts':[]} if ident.startswith('bluesky_') else [] if ident.startswith('github_') else {'articles':[]} if kind=='json' else b'<rss><channel/></rss>'
        out=d.consolidate(m,Mock(),cap=1,workers=2)
        self.assertFalse(out['status']['coin_matching_performed'])
        self.assertNotIn('candidate_coin_ids',out['events'][0])
        self.assertNotIn('per_coin_candidate_counts',out)
        self.assertEqual(out['events'][0]['coin_relevance_status'],'NOT_ASSESSED_BY_COLLECTOR')

    def test_rss_excerpt_sanitization_and_time_provenance(self):
        feed=b'<rss><channel><item><title>Quantum hardware</title><link>https://example.com/article/1</link><description>&lt;p&gt;Abstract: new work on proof systems.&lt;/p&gt;</description></item></channel></rss>'
        rows=d.xml_items(feed,'arxiv_crypto','2026-11-09T12:00:00Z')
        self.assertEqual(len(rows),1)
        self.assertIsNone(rows[0]['published_utc'])
        self.assertEqual(rows[0]['excerpt'],'Abstract: new work on proof systems.')
        self.assertEqual(rows[0]['context_origin'],'PUBLISHER_FEED_EXCERPT')
        self.assertEqual(d.parse_time('Mon, 09 Nov 2026 12:00:00 GMT'),dt.datetime(2026,11,9,12,tzinfo=dt.timezone.utc))

    def test_canonical_url_preserves_article_identity_not_tracking(self):
        self.assertEqual(d.key_url('https://EXAMPLE.com/story?id=12&utm_source=x'), 'https://example.com/story?id=12')
        self.assertNotEqual(d.key_url('https://example.com/story?id=12'),d.key_url('https://example.com/story?id=13'))
        self.assertEqual(d.key_url('https://example.com/a?tracking=1'),d.key_url('https://example.com/a?tracking=2'))

    def test_balanced_index_preserves_rare_sources(self):
        events=[];families={}
        for fam,count in [('ARXIV',75),('GITHUB_DEVELOPER_RELEASES',5),('TECH_NEWS',7),('SOFTWARE_SECURITY_ADVISORIES',3)]:
            for i in range(count):
                source=fam.lower()+'_'+str(i%3)
                families[source]=fam
                events.append(dict(event_id=f'{fam}{i}',title=f'{fam} {i}',source_id=source,
                                   published_utc=f'2026-11-09T06:{i%60:02d}:00Z',first_observed_utc='2026-11-09T06:00:00Z'))
        selected=d.balanced_index(events,families,cap=12)
        self.assertEqual(len(selected),12)
        self.assertEqual(set(families[e['source_id']] for e in selected),set(fam for fam,_ in [('ARXIV',75),('GITHUB_DEVELOPER_RELEASES',5),('TECH_NEWS',7),('SOFTWARE_SECURITY_ADVISORIES',3)]))
        self.assertEqual(len(set(x['event_id'] for x in selected)),12)
        self.assertEqual(d.balanced_index(events,families,cap=0),[])

    def test_round_robin_does_not_use_coin_names_or_themes(self):
        items=[dict(event_id=f'{i:02}',title=('Avalanche release' if i%2==0 else 'Quantum chip breakthrough'),
                    source_id=('a' if i<50 else 'b'),published_utc='2026-11-09T10:00:00Z',
                    first_observed_utc='2026-11-09T10:00:00Z',theme_leads=[] if i%2 else ['AI_COMPUTE'])
               for i in range(60)]
        sel=d.balanced_index(items,{'a':'ARXIV','b':'TECH_NEWS'},cap=10)
        self.assertEqual({i['source_id'] for i in sel},{'a','b'})
        changed=[dict(x,title='SHIB tokens!',theme_leads=['ETF_INSTITUTIONAL']) for x in items]
        self.assertEqual([x['event_id'] for x in sel],
                         [x['event_id'] for x in d.balanced_index(changed,{'a':'ARXIV','b':'TECH_NEWS'},cap=10)])

    def test_canonical_dedup_and_future_exclusion(self):
        class Mock:
            def __init__(self):self.calls=[]
            def get(self,ident,kind,target):
                self.calls.append(dict(source_id=ident,transport_status='OK',observed_utc=d.iso(d.utcnow())))
                if ident=='google_theme_QUANTUM_SECURITY':
                    return b'<rss><channel><item><title>Quantum encryption breakthrough</title><link>https://example.com/a?tracking=1</link><pubDate>Fri, 06 Nov 2026 10:00:00 GMT</pubDate></item></channel></rss>'
                if ident=='gdelt_theme_QUANTUM_SECURITY':
                    return {'articles':[{'title':'Quantum encryption breakthrough','url':'https://example.com/a?tracking=2','seendate':'20261106T100000Z'}]}
                if ident=='google_theme_REGULATION':
                    return b'<rss><channel><item><title>Future event</title><link>https://example.com/future</link><pubDate>Tue, 09 Nov 2099 12:00:00 GMT</pubDate></item></channel></rss>'
                if ident.startswith('hn_'):return {'hits':[]}
                if ident.startswith('bluesky_'):return {'posts':[]}
                if ident.startswith('github_'):return []
                return {'articles':[]} if kind=='json' else b'<rss><channel/></rss>'
        m=Mock();result=d.consolidate(self.market(),m,workers=2)
        self.assertEqual(result['status']['official_cmc100_verified'],100)
        self.assertEqual(result['status']['successful_transport'],len(m.calls))
        self.assertEqual(result['status']['full_archive_leads'],1)
        self.assertEqual(result['status']['future_dated_excluded'],1)
        self.assertIn('gdelt_theme_QUANTUM_SECURITY',result['all_events'][0]['discovered_via'])
        self.assertEqual(result['events'][0]['coin_relevance_status'],'NOT_ASSESSED_BY_COLLECTOR')

    def test_github_release_and_hn_social_context(self):
        now='2026-11-09T10:00:00Z'
        src=d.github_items([{'name':'Release 1.2.3','body':'**Network patch** fixing protocol behavior.','html_url':'https://github.com/example/repo/releases/tag/1.2.3','published_at':now}], 'github_releases_example__repo',now)
        self.assertEqual(src[0]['source_type'],'GITHUB_RELEASE_OR_ADVISORY')
        self.assertEqual(src[0]['repo'],'example__repo')
        self.assertIn('Network patch',src[0]['excerpt'])
        h=d.hn_items({'hits':[{'title':'New AI research','story_text':'A new approach to AI coordination','objectID':'3','points':33,'num_comments':8,'created_at':now}]},'hn_test',now)
        self.assertEqual(h[0]['engagement']['points'],33)
        self.assertEqual(h[0]['excerpt'],'A new approach to AI coordination')
        b=d.bluesky_items({'posts':[{'uri':'at://did:abc/app.bsky.feed.post/postid','author':{'handle':'abc.bsky.social'},'record':{'text':'Open source zero knowledge release','createdAt':now},'likeCount':9}]},'bsky_test',now)
        self.assertEqual(b[0]['engagement']['likes'],9)

    def test_full_archive_and_index_separate(self):
        observed='2026-11-09T12:00:00Z'
        rows=[dict(event_id=str(i),title='Research '+str(i),url='https://example.com/'+str(i),source_id='s',
                   source_type='RSS',published_utc=observed,publication_time_status='VERIFIED_FEED_OR_PLATFORM',
                   first_observed_utc=observed,discovered_via=['s'],theme_leads=[],coin_relevance_status='NOT_ASSESSED_BY_COLLECTOR') for i in range(12)]
        status={'capture_started_utc':observed,'unique_leads_stored':4,'read_index_leads':4,'full_archive_leads':12}
        data={'schema_version':'adjacent-discovery-v2','status':status,'events':rows[:4], 'all_events':rows,
              'first_seen':{x['event_id']:observed for x in rows},'query_plan':[]}
        with tempfile.TemporaryDirectory() as p:
            out=pathlib.Path(p);arch=d.write_bundle(data,out)
            self.assertTrue(arch.exists())
            self.assertEqual(len(json.loads(arch.read_text())['events']),12)
            self.assertEqual(len(json.loads((out/'latest.json').read_text())['events']),4)
            with (out/'leads.csv').open() as f:self.assertEqual(len(list(csv.DictReader(f))),12)
            with (out/'read_index.csv').open() as f:self.assertEqual(len(list(csv.DictReader(f))),4)
            self.assertFalse('candidate_coin_ids' in (out/'leads.csv').read_text())
            with self.assertRaises(FileExistsError):d.write_bundle(data,out)

    def test_collector_keeps_all_records_when_read_index_capped(self):
        class Mock:
            def __init__(self):self.calls=[]
            def get(self,ident,kind,target):
                self.calls.append(dict(source_id=ident,transport_status='OK',observed_utc=d.iso(d.utcnow())))
                if ident.startswith('google_theme_'):
                    xml='<rss><channel>'+''.join(f'<item><title>Research {ident} {j}</title><link>https://example.com/{ident}/{j}</link></item>' for j in range(15))+'</channel></rss>'
                    return xml.encode('utf8')
                if ident.startswith('hn_'):return {'hits':[]}
                if ident.startswith('bluesky_'):return {'posts':[]}
                if ident.startswith('github_'):return []
                return {'articles':[]} if kind=='json' else b'<rss><channel/></rss>'
        b=d.consolidate(self.market(),Mock(),cap=13,workers=2)
        self.assertEqual(b['status']['read_index_leads'],13)
        self.assertGreater(b['status']['full_archive_leads'],100)
        self.assertEqual(len(b['all_events']),b['status']['full_archive_leads'])
        self.assertEqual(len(b['events']),13)

    def test_rejects_unverified_universe(self):
        bad=self.market();bad['assets']=bad['assets'][:-1]
        with self.assertRaisesRegex(ValueError,'100 unique'):
            d.consolidate(bad,None)

if __name__=='__main__':unittest.main()