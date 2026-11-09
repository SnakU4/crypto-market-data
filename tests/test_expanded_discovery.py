import datetime as dt
import gzip
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest
from collections import Counter

PATH=pathlib.Path(__file__).resolve().parents[1]/'src'/'expanded_discovery.py'
spec=importlib.util.spec_from_file_location('expanded_discovery',PATH)
x=importlib.util.module_from_spec(spec);spec.loader.exec_module(x)
BASE=dt.datetime(2026,11,9,20,0,tzinfo=dt.timezone.utc)


def market():
    assets=[{'cmc_id':i+1,'name':f'Project Number {i+1}','symbol':f'TKN{i+1}'} for i in range(100)]
    assets[0]={'cmc_id':1,'name':'Bitcoin','symbol':'BTC'}
    assets[1]={'cmc_id':2,'name':'Avalanche','symbol':'AVAX'}
    return {'assets':assets,'index':{'verified_constituents':100},'snapshot_completed_utc':'2026-11-09T19:50:00Z'}


def entry(url='https://example.com/story-one',title='Avalanche noise in physics',days=0):
    return {'url':url,'title':title,'excerpt':'Physics, not coins.','published_utc':x.iso(BASE-dt.timedelta(days=days)),
            'publication_time_status':'RSS_DATE','source_type':'RSS','observed_utc':x.iso(BASE),
            'context_origin':'FEED_EXCERPT'}


def job(cid=None,n='z',family='COIN_RESEARCH'):
    return {'id':n,'family':family,'lens':'NEWS','query_cmc_id':cid,'kind':'rss','target':'https://news.google.com'}


class FakeNetwork:
    def __init__(self):self.calls=[]
    def get(self,j):
        self.calls.append({'id':j['id'],'status':'OK','family':j['family'],'endpoint':j['endpoint'], 'error':None, 'target':j['target']})
        return b'<rss><channel><item><title>Sample headline</title><link>https://example.com/story</link><pubDate>Mon, 09 Nov 2026 19:00:00 GMT</pubDate><description>Article summary</description></item></channel></rss>'

class Tests(unittest.TestCase):
    def test_rejects_incomplete_or_duplicate_universe(self):
        m=market();m['assets'].pop();
        with self.assertRaises(ValueError):x.market_assets(m)
        m=market();m['assets'][2]['cmc_id']=2
        with self.assertRaises(ValueError):x.market_assets(m)

    def test_all_100_coins_multiple_query_lenses(self):
        queries=x.plan(market())
        coin=[q for q in queries if q['family']=='COIN_RESEARCH']
        self.assertEqual(len(coin),800)
        self.assertEqual(set(q['query_cmc_id'] for q in coin),set(range(1,101)))
        self.assertTrue(all(len([q for q in coin if q['query_cmc_id']==i])==8 for i in range(1,101)))
        self.assertTrue(all('when%3A' in q['target'] for q in coin))
        self.assertTrue(any('numericFilters' in q['target'] for q in queries if q['family']=='DEVELOPER_COMMUNITY'))

    def test_source_metadata_not_coin_matching(self):
        records=[(entry(),job(2,n='coin2')),(entry(),job(1,n='coin1'))]
        parsed,future,old=x.merge_records(records,{},BASE-dt.timedelta(days=7),BASE)
        self.assertEqual(len(parsed),1)
        self.assertEqual(parsed[0]['query_scoped_ids'],[1,2])
        self.assertEqual(parsed[0]['coin_relevance_status'],'NOT_ASSESSED')
        self.assertEqual(parsed[0]['price_direction'],'NOT_ASSESSED')
        self.assertFalse('candidate_coin_ids' in parsed[0])
        self.assertEqual(len(parsed[0]['search_origins']),2)

    def test_future_and_old_excluded(self):
        arr=[(entry(url='https://example.com/old',days=9),job(1)),
             (entry(url='https://example.com/new',days=0),job(1)),
             ({**entry(url='https://example.com/future'), 'published_utc':x.iso(BASE+dt.timedelta(days=1))},job(1))]
        parsed,fut,old=x.merge_records(arr,{},BASE-dt.timedelta(days=7),BASE)
        self.assertEqual((len(parsed),fut,old),(1,1,1))

    def test_retains_original_first_seen(self):
        k=x.event_id('https://example.com/story-one')
        prev={k:'2026-11-08T10:00:00Z'}
        parsed,_,_=x.merge_records([(entry(),job(1))],prev,BASE-dt.timedelta(days=7),BASE)
        self.assertEqual(parsed[0]['first_observed_utc'],prev[k])

    def test_google_news_rss_parsing(self):
        rss=b'<rss><channel><item><title>Testing a release</title><link>https://example.com/new</link><pubDate>Mon, 09 Nov 2026 19:00:00 GMT</pubDate><description>New code</description></item></channel></rss>'
        res=x.rss_records(rss,job(1),x.iso(BASE))
        self.assertEqual(len(res),1)
        self.assertEqual(res[0]['excerpt'],'New code')
        self.assertEqual(res[0]['published_utc'],'2026-11-09T19:00:00Z')

    def test_hn_recency_query_and_parser(self):
        h={'hits':[{'objectID':'1337','title':'Interesting development','points':34,'num_comments':3,'created_at_i':int(BASE.timestamp())}]}
        r=x.hn_records(h,{},x.iso(BASE))
        self.assertEqual(len(r),1)
        self.assertEqual(r[0]['engagement']['points'],34)

    def test_large_10000_distinct_and_archived(self):
        specs=[job(i,n=f'j{i}') for i in range(1,101)]
        rows=[]
        for i in range(10050):
            j=specs[i%100]
            rows.append((entry(url=f'https://research.example/unique/{i}',title=f'Research report {i}'),j))
        parsed,_,_=x.merge_records(rows,{},BASE-dt.timedelta(days=7),BASE)
        self.assertEqual(len(parsed),10050)
        # No arbitrary cap on full archive, only on reading index
        index=x.index_select(parsed,500,BASE)
        self.assertEqual(len(index),500)
        self.assertEqual(len({a['event_id'] for a in index}),500)
        self.assertEqual(len({v for e in index for v in e['query_scoped_ids']}),100)
        data={'events':parsed,'new_events':parsed,'index':index,'first_seen':{e['event_id']:e['first_observed_utc'] for e in parsed},
              'audit':[],'status':{'capture_utc':x.iso(BASE),'full_archive_leads':len(parsed)}}
        with tempfile.TemporaryDirectory() as td:
            status=x.write_bundle(data,pathlib.Path(td))
            full=pathlib.Path(td)/status['archive_path'].split('expanded_discovery/',1)[-1]
            if not full.exists():
                full=next(pathlib.Path(td).rglob('*_all.jsonl.gz'))
            with gzip.open(full,'rt',encoding='utf8') as f:
                self.assertEqual(sum(1 for _ in f),10050)
            latest=json.loads((pathlib.Path(td)/'latest.json').read_text())
            self.assertEqual(len(latest['events']),500)
            self.assertEqual(len(list((pathlib.Path(td)/'latest_shards').glob('*.json'))),20)

    def test_index_family_diversity_and_freshness(self):
        a=[]
        for i in range(300):
            a.append((entry(url=f'https://site.example/news/{i}',title='A',days=0),job(1,n='big',family='COIN_RESEARCH')))
        for i in range(10):
            a.append((entry(url=f'https://site.example/tech/{i}',title='B',days=6),job(None,n='rare',family='TECH_SECURITY_RESEARCH')))
        a,_,_=x.merge_records(a,{},BASE-dt.timedelta(days=7),BASE)
        index=x.index_select(a,100,BASE)
        self.assertTrue(any('TECH_SECURITY_RESEARCH' in e['source_families'] for e in index))
        self.assertEqual(len(index),100)

    def test_circuit_breaker_prevents_ban_like_flood(self):
        from urllib.error import HTTPError
        def denied(req,timeout):raise HTTPError(req.full_url,403,'Forbidden',{},None)
        h=x.HTTP(opener=denied,sleeper=lambda _:None,clock=lambda:0.0)
        spec=job(1,n='block');spec['endpoint']='GOOGLE_NEWS'
        for i in range(12):
            h.get({**spec,'id':str(i)})
        self.assertEqual(h.calls[-1]['status'],'HOST_CIRCUIT_OPEN')
        self.assertEqual(h.failures['news.google.com'],8)

    def test_collect_market_all_coins_even_fake_single_result(self):
        saved=x.plan
        try:
            x.plan=lambda m:[{'id':f'coin_{i}_NEWS','family':'COIN_RESEARCH','endpoint':'GOOGLE_NEWS','kind':'rss',
                                 'target':'https://news.google.com','query_cmc_id':i,'lens':'NEWS'} for i in range(1,101)]
            net=FakeNetwork()
            data=x.collect(market(),net,{},max_workers=3,now_utc=BASE)
            self.assertEqual(data['status']['raw_leads'],100)
            self.assertEqual(data['status']['distinct_url_leads'],1)
            self.assertTrue(data['status']['all_100_coins_planned'])
            self.assertEqual(data['status']['coins_with_successful_query'],100)
            self.assertEqual(len(data['status']['search_results_per_queried_coin']),100)
            self.assertFalse(data['status']['target_met'])
            self.assertEqual(data['status']['target_shortfall'],9999)
            self.assertEqual(len(data['new_events']),1)
        finally:x.plan=saved

    def test_title_clusters_not_claim_independent_information(self):
        rows=[(entry(url=f'https://source.example/{i}',title='Same finding'),job(i)) for i in range(15)]
        parsed,_,_=x.merge_records(rows,{},BASE-dt.timedelta(days=7),BASE)
        self.assertEqual(len(parsed),15)
        self.assertEqual(len({e['story_title_hash'] for e in parsed}),1)

if __name__=='__main__':unittest.main()