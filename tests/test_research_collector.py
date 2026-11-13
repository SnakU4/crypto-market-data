import datetime as dt
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
import research_collector as r

T0='2026-11-06T20:00:00Z'


def fake_market():
    rows=[]
    for i in range(1,101):
        rows.append({'cmc_id':i,'name':'Coin'+str(i),'symbol':'Z'+str(i),
            'cmc_quote':{'price_usd':10,'quote_last_updated_utc':T0},
            'perpetual':{'exchange':'OKX','symbol':'Z'+str(i)+'-USDT-SWAP'},
            'perp_market':{'source_exchange':'OKX','oi_observed_utc':T0,'oi_usd':1000+i,
                           'estimated_next_funding_rate_fraction':.0001}})
    rows[0]['name']='Bitcoin';rows[0]['symbol']='BTC'
    rows[1]['name']='Ethereum';rows[1]['symbol']='ETH'
    return {'assets':rows,'status':'DATA_PARTIAL','snapshot_completed_utc':T0,
       'index':{'source':'official_coinmarketcap_cmc100_keyless_api',
                 'verified_constituents':100,'last_update':'2026-11-06T19:00:00Z'}}


class ResearchCollectorTests(unittest.TestCase):
    def test_identity_mapping_strict_ambiguous_name(self):
        coins=[{'cmc_id':1,'name':'Bitcoin','symbol':'BTC'},
               {'cmc_id':2,'name':'Sui','symbol':'SUI'}]
        protocols=[{'name':'Bitcoin','symbol':'BTC','cmcId':1,'tvl':100},
                   {'name':'Sui','symbol':'SUI','tvl':55},
                   {'name':'Another','symbol':'SUI','tvl':44},
                   {'name':'Bitcoin','symbol':'BTT','cmcId':1,'tvl':1234}]
        rows,_=r.protocols_rows(protocols,coins)
        self.assertEqual({x['cmc_id']:x['protocol_tvl_usd'] for x in rows},{1:100,2:55})
        self.assertEqual(rows[0]['mapping_confidence'],'EXPLICIT_CMC_ID')

    def test_protocol_mapping_rejects_duplicate_explicit_ids(self):
        assets=[{'cmc_id':1,'symbol':'BTC','name':'Bitcoin'}]
        rows,_=r.protocols_rows([{'name':'Bitcoin','symbol':'BTC','cmcId':1,'tvl':1},
                                  {'name':'Bitcoin','symbol':'BTC','cmcId':1,'tvl':2}],assets)
        self.assertEqual(rows,[])

    def test_feed_timestamp_and_event_classification(self):
        rss=b'''<rss><channel><item><title>Bitcoin token unlock after audit</title>
        <link>https://news.example.org/story1</link>
        <pubDate>Fri, 06 Nov 2026 19:00:00 GMT</pubDate></item>
        <item><title>Future article</title><link>https://news.example.org/future</link>
        <pubDate>Sat, 07 Nov 2026 19:00:00 GMT</pubDate></item></channel></rss>'''
        rows=r.parse_feed(rss,'feed',T0)
        self.assertEqual(len(rows),1)
        event=r.label_event(rows[0],[{'cmc_id':1,'name':'Bitcoin','symbol':'BTC'}])
        self.assertIn('TOKEN_UNLOCK',event['event_classes'])
        self.assertEqual(event['cmc_ids'],[1])
        self.assertFalse(event['coin_tags_are_verified_catalysts'])

    def test_publisher_feed_body_retained_for_research(self):
        rss=b'''<rss><channel><item><title>Example protocol security update</title>
        <link>https://source.example.org/update</link>
        <description><![CDATA[<p>Maintainers published a protocol migration timeline and
        changed validator requirements with explicit dates, deployment checks, and
        documented mitigation steps for operators.</p>]]></description>
        <pubDate>Fri, 06 Nov 2026 19:00:00 GMT</pubDate></item></channel></rss>'''
        rows=r.parse_feed(rss,'direct_source',T0)
        self.assertEqual(len(rows),1)
        self.assertIn('changed validator requirements',rows[0]['excerpt'])
        self.assertNotIn('<p>',rows[0]['excerpt'])
        self.assertEqual(rows[0]['context_origin'],'PUBLISHER_FEED_SUMMARY')

    def test_short_tickers_suppressed_and_explicit_dollar_match(self):
        coins=[{'cmc_id':1,'name':'Stable','symbol':'STABLE'},
               {'cmc_id':2,'name':'Near Protocol','symbol':'NEAR'}]
        self.assertEqual(r.match_asset('Markets are stable and near the peak',coins)[0],[])
        self.assertEqual(r.match_asset('Large $NEAR token release',coins)[0],[2])

    def test_stablecoin_hosts_are_separate_public_service(self):
        sources={name:url for name,_,_,url in r.SOURCE_CATALOG}
        self.assertEqual(sources['llama_stablecoin_supply'], 'https://stablecoins.llama.fi/stablecoincharts/all')
        self.assertEqual(sources['llama_stablecoin_chains'], 'https://stablecoins.llama.fi/stablecoinchains')

    def test_stablecoin_no_future_history_and_correct_window(self):
        raw=[{'date':str(int(dt.datetime(2026,11,i,tzinfo=dt.timezone.utc).timestamp())),
              'totalCirculating':{'peggedUSD':i*100}} for i in range(1,10)]
        result=r.stablecoin_global(raw,'2026-11-08T00:01:00Z')
        self.assertEqual(result['circulating_usd'],800)
        self.assertAlmostEqual(result['change_1d_pct'],100*(800/700-1),places=4)
        self.assertAlmostEqual(result['change_7d_pct'],700,places=4)

    def test_fear_greed(self):
        self.assertEqual(r.sentiment({'data':[{'value':'15','value_classification':'Extreme Fear','timestamp':'1793995200'}]})[0]['value'],15)

    def test_supply_mapped_by_cmc_id_no_inference(self):
        assets=fake_market()['assets']
        supply={'status':{'error_code':'0'},'data':[
            {'id':1,'symbol':'BTC','circulating_supply':19000000,'max_supply':21000000},
            {'id':2,'symbol':'WRONG','circulating_supply':99},
            {'id':999,'symbol':'BAD','circulating_supply':88}]}
        rows=r.supply_from_cmc(supply,assets)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['max_supply'],21000000)
        self.assertEqual(r.supply_from_cmc({'status':{'error_code':403},'data':[]},assets),[])

    def test_oi_rejects_stale_replays_and_matches_24h(self):
        market=fake_market()
        previous=r.iso(r.parse_utc(T0)-dt.timedelta(hours=24))
        with tempfile.TemporaryDirectory() as d:
            base=pathlib.Path(d)
            r.save_oi(base,[{'source_exchange':'OKX','instrument_id':'Z1-USDT-SWAP',
                 'cmc_id':1,'oi_observed_utc':previous,'oi_usd':900,
                 'source_market_snapshot_utc':previous}])
            entries,deltas=r.previous_oi(base,market)
            self.assertEqual(deltas['1']['value_pct'],r.rate(1001,900))
            r.save_oi(base,entries)
            replay_entries,replay_deltas=r.previous_oi(base,market)
            self.assertEqual(len(replay_entries),0)
            self.assertEqual(replay_deltas['1'],deltas['1'])

    def test_full_collect_with_mock_sources_outputs_100(self):
        market=fake_market()
        class FakeNetwork:
            def __init__(self):self.calls=[]
            def get(self,name,kind,url):
                self.calls.append({'source_id':name,'source_type':kind,'url':url,
                    'started_utc':T0,'observed_utc':T0,'status':'OK','error':None})
                if name=='okx_book_instruments':return {'code':'0','data':[{'instId':'Z'+str(i)+'-USDT-SWAP','ctVal':'0.1','ctValCcy':'Z'+str(i)} for i in range(1,101)]}
                if name.startswith('okx_book_'):
                    return {'code':'0','data':[{'bids':[['99','10','1','1']], 'asks':[['101','20','1','1']],'ts':'1793995200000'}]}
                if name=='llama_protocols':return [{'name':'Bitcoin','symbol':'BTC','cmcId':1,'tvl':10000,'change_1d':4}]
                if name=='llama_chains':return [{'name':'Ethereum','tvl':2000000}]
                if name=='llama_fees':return {'protocols':[{'name':'Bitcoin','symbol':'BTC','cmcId':1,'total24h':34}]}
                if name=='llama_stablecoin_supply':return [{'date':str(int(dt.datetime(2026,11,6,tzinfo=dt.timezone.utc).timestamp())),
                                                              'totalCirculating':{'peggedUSD':50000}}]
                if name=='alternative_fng':return {'data':[{'value':'20','timestamp':'1793995200'}]}
                if name=='coingecko_trending':return {'coins':[{'item':{'name':'Bitcoin','symbol':'BTC','score':1}}]}
                if name.startswith('cmc_supply_batch'):
                    return {'status':{'error_code':0},'data':[{'id':1,'symbol':'BTC','circulating_supply':19000,'total_supply':19900,'max_supply':21000}]}
                if kind=='rss':return b'''<rss><channel><item><title>Bitcoin token unlock expected</title><link>https://news.example.org/a</link><pubDate>Fri, 06 Nov 2026 19:00:00 GMT</pubDate></item></channel></rss>'''
                return {'protocols':[]} if name in ('llama_revenue','llama_holder_revenue','llama_dex','llama_options','llama_perp_oi') else []
        with tempfile.TemporaryDirectory() as d,patch.object(r,'now',lambda:T0):
            nn=FakeNetwork();out=r.collect(nn,market,{},pathlib.Path(d),workers=2)
            self.assertEqual(len(out['coins']),100)
            self.assertEqual(len(out['events']),1)
            self.assertEqual(out['status']['sources_ok'],len(r.SOURCE_CATALOG)+3+1+100)
            self.assertEqual(len(out['families']['okx_orderbooks']),100)
            self.assertEqual(out['status']['family_coverage']['ORDERBOOK_LIQUIDITY']['coin_coverage'],100)
            self.assertEqual(out['status']['family_coverage']['TOKEN_SUPPLY_REPORTED']['coin_coverage'],1)
            self.assertEqual(out['status']['family_coverage']['DEFI_PROTOCOL_TVL']['coin_coverage'],1)
            self.assertEqual(out['status']['coin_metrics_with_defillama'],2) # BTC TVL + ETH chain; CMC supply excluded
            self.assertEqual(out['status']['coin_count_with_event_candidate'],1)
            self.assertEqual(out['status']['family_coverage']['PROTOCOL_REVENUE']['status'],'SOURCE_OK_NO_VERIFIED_COIN_MAPPING')
            self.assertIn('PROTOCOL_REVENUE',out['status']['successful_sources_with_zero_coin_mapping'])
            self.assertEqual(out['status']['family_coverage']['TOKEN_UNLOCK_SCHEDULE']['status'],'UNAVAILABLE_OR_EVENT_ONLY')
            self.assertEqual(len(out['oi_new_records']),100)
            r.write_bundle(out,pathlib.Path(d))
            r.write_bundle(out,pathlib.Path(d)/'another')
            self.assertEqual(len((pathlib.Path(d)/'coin_features.csv').read_text().splitlines()),101)
            self.assertTrue((pathlib.Path(d)/'status.json').exists())
            self.assertEqual(len(list((pathlib.Path(d)/'archive').rglob('*.json.gz'))),1)

    def test_incomplete_index_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'100 officially verified'):
            r.collect(None,{'assets':fake_market()['assets'][:99],
                            'index':{'verified_constituents':99}},workers=2)

if __name__=='__main__':unittest.main()