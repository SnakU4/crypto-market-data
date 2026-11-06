import datetime as dt
import pathlib
import sys
import tempfile
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
import collector as c

class CollectorTests(unittest.TestCase):
    def make_index(self, size=100):
        return {'status':{'error_code':0},'data':{'constituents':[{'id':i+1,'name':'Asset'+str(i+1),'symbol':'A'+str(i+1),'weight':1.0/100} for i in range(size)],'last_update':'2026-11-05T23:00:00Z'}}

    def test_official_index_gate_and_uniqueness(self):
        rows,updated=c.normalize_index(self.make_index())
        self.assertEqual(len(rows),100)
        self.assertEqual(updated,'2026-11-05T23:00:00Z')
        with self.assertRaisesRegex(ValueError,'full-universe gate'):
            c.normalize_index(self.make_index(99))
        broken=self.make_index(); broken['data']['constituents'][1]['id']=1
        with self.assertRaisesRegex(ValueError,'full-universe gate'):
            c.normalize_index(broken)
        with self.assertRaisesRegex(ValueError,'lacks'):
            c.normalize_index({'data':{'data':[]}})

    def test_quotes_are_keyed_by_cmc_id_not_symbol(self):
        q=c.normalize_quotes({'status':{'error_code':0},'data':[{'id':1,'symbol':'TICKER','quote':[{'symbol':'USD','price':3,'percent_change_24h':-6,'volume_24h':400,'last_updated':'2026-11-05T22:00:00Z'}]}]})
        self.assertEqual(q[1]['ret_24h_pct'],-6)
        self.assertEqual(q[1]['volume_24h_usd'],400)

    def test_only_exact_trading_contracts_are_matched(self):
        bybase=c.normalize_exchange_info({'symbols':[{'symbol':'BTCUSDT','baseAsset':'BTC','quoteAsset':'USDT','contractType':'PERPETUAL','status':'TRADING'}, {'symbol':'1000PEPEUSDT','baseAsset':'1000PEPE','quoteAsset':'USDT','contractType':'PERPETUAL','status':'TRADING'},{'symbol':'ETHUSDT','baseAsset':'ETH','quoteAsset':'USDT','contractType':'PERPETUAL','status':'BREAK'}]})
        self.assertEqual(c.map_perp({'symbol':'BTC'},bybase)['symbol'],'BTCUSDT')
        self.assertIsNone(c.map_perp({'symbol':'PEPE'},bybase)['symbol'])
        self.assertEqual(c.map_perp({'symbol':'PEPE'},bybase)['review_candidates'],['1000PEPEUSDT'])
        self.assertIsNone(c.map_perp({'symbol':'ETH'},bybase)['symbol'])

    def test_kline_features_ignore_open_or_future_bars(self):
        start=dt.datetime(2026,11,5,0,tzinfo=dt.timezone.utc)
        kl=[]
        for i in range(175):
            opens=int((start+dt.timedelta(hours=i)).timestamp()*1000)
            close=opens+3600000-1
            kl.append([opens,'1','1','1',str(100+i),'1',close,'1000',1,'1','700','0'])
        # Ends 2026-11-12T06:00. At 2026-11-12T05:30, last 1h bar is open.
        snap='2026-11-12T05:30:00Z'
        f=c.compute_kline_features(kl,snap)
        self.assertEqual(f['bars_available'],173)
        self.assertAlmostEqual(f['perp_ret_24h_pct'],100*(272/248-1),places=5)
        self.assertGreater(f['perp_taker_imbalance_24h'],0)
        self.assertEqual(f['perp_volume_ratio_24h_vs_prior24h'],1)

    def test_oi_does_not_use_future_value(self):
        observed=dt.datetime(2026,11,4,12,tzinfo=dt.timezone.utc)
        ms=lambda t:int(t.timestamp()*1000)
        history=[{'timestamp':ms(observed-dt.timedelta(hours=24)),'sumOpenInterestValue':'100'}, {'timestamp':ms(observed),'sumOpenInterestValue':'110'},{'timestamp':ms(observed+dt.timedelta(hours=1)),'sumOpenInterestValue':'500'}]
        o=c.compute_oi_features(history,'2026-11-04T12:00:00Z')
        self.assertEqual(o['oi_usd'],110)
        self.assertEqual(o['oi_change_24h_pct'],10)

    def test_full_collector_integration_with_mocked_network(self):
        now=dt.datetime.now(dt.timezone.utc)
        here=now.isoformat(timespec="seconds").replace("+00:00","Z")
        base_ms=int((now.replace(minute=0,second=0,microsecond=0)-dt.timedelta(hours=200)).timestamp()*1000)
        bars=[]
        for i in range(200):
            op=base_ms+i*3_600_000
            bars.append([op,"100","110","90",str(100+i*.01),"100",op+3599999,"10000",10,"30","6000","0"])
        oi=[]
        for i in range(27):
            t=int((now-dt.timedelta(hours=26-i)).timestamp()*1000)
            oi.append({"timestamp":t,"sumOpenInterestValue":str(100000+i*100)})
        class FakeClient:
            def __init__(self):self.calls=[]
            def fetch(self,url,params=None,required=False):
                self.calls.append({"url":url,"status":"OK"})
                if url.endswith("cmc100-latest"):
                    d={'status':{'error_code':0},'data':{'constituents':[{'id':i+1,'name':f'Coin {i+1}','symbol':f'A{i+1}','weight':0.01} for i in range(100)],'last_update':here}}
                    return d
                if url.endswith('quotes/latest'):
                    return {'status':{'error_code':0},'data':[{'id':int(x),'quote':[{'symbol':'USD','price':10,'volume_24h':5000,'percent_change_1h':1,'percent_change_24h':2,'percent_change_7d':3,'last_updated':here}]} for x in params['id'].split(',')]}
                if url.endswith('exchangeInfo'):
                    return {'symbols':[{'symbol':f'A{i}USDT','baseAsset':f'A{i}','quoteAsset':'USDT','contractType':'PERPETUAL','status':'TRADING'} for i in range(1,66)]}
                if url.endswith('premiumIndex'):
                    return [{'symbol':f'A{i}USDT','lastFundingRate':'0.0001','time':int(now.timestamp()*1000)} for i in range(1,66)]
                if url.endswith('/global'): return {'data':{'active_cryptocurrencies':9999}}
                if url.endswith('/v2/chains'):return [{'name':'TestChain','tvl':100}]
                if url.endswith('/klines'):return bars
                if url.endswith('openInterestHist'):return oi
                raise AssertionError('Unexpected mocked URL: '+url)
        snap=c.collect(FakeClient(),strict=True,max_workers=2)
        self.assertEqual(snap['status'],'DATA_PASS')
        self.assertEqual(snap['coverage']['official_cmc100_verified'],100)
        self.assertEqual(snap['coverage']['cmc_usd_quote_count'],100)
        self.assertEqual(snap['coverage']['binance_hourly_klines'],65)
        self.assertEqual(snap['coverage']['binance_open_interest_history'],65)
        self.assertEqual(len(snap['assets']),100)
        with tempfile.TemporaryDirectory() as d:
            c.output_artifacts(snap,pathlib.Path(d))
            self.assertEqual(len((pathlib.Path(d)/'latest.csv').read_text().splitlines()),101)

    def test_snapshot_export_100_without_fake_data(self):
        snap={'status':'DATA_PARTIAL','snapshot_completed_utc':'2026-11-05T23:40:00Z','coverage':{'official_cmc100_verified':100,'cmc_usd_quote_count':0,'binance_usd_m_exact_contract_mapping':0,'binance_hourly_klines':0,'binance_open_interest_history':0},'problems':[], 'source_access_log':[], 'index':{'verified_constituents':100,'last_update':'2026-11-05T22:00:00Z'},'assets':[]}
        for i in range(100):snap['assets'].append({'cmc_id':i+1,'symbol':f'T{i+1}','name':f'Token{i+1}','cmc_quote':None,'perp_market':None,'perpetual':{'symbol':None,'mapping':'NOT_MATCHED'},'cmc100_weight':.01})
        with tempfile.TemporaryDirectory() as d:
            result=c.output_artifacts(snap,pathlib.Path(d))
            self.assertEqual(result['status'],'DATA_PARTIAL')
            self.assertEqual(len((pathlib.Path(d)/'latest.csv').read_text().splitlines()),101)
            self.assertEqual(len(list((pathlib.Path(d)/'archive').rglob('*.json'))),1)
            self.assertIn('Snapshot collected', (pathlib.Path(d)/'forecast_context.md').read_text())
        snap['index']['verified_constituents']=0
        with tempfile.TemporaryDirectory() as d:
            c.output_artifacts(snap,pathlib.Path(d))
            self.assertFalse((pathlib.Path(d)/'latest.json').exists())

if __name__=='__main__':unittest.main()
