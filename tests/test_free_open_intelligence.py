"""Regression tests for the zero-fee four-plane intelligence collector."""
import datetime as dt, gzip, hashlib, json, pathlib, sys, tempfile, unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"src"))
import free_open_intelligence as foi

UTC=dt.timezone.utc
T=dt.datetime(2026,11,12,5,0,tzinfo=UTC)
OBS="2026-11-12T04:30:00Z"

def write(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,ensure_ascii=False),encoding="utf-8")

def archive(p,rows):
    p.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(p,"wt",encoding="utf-8") as f:
        for r in rows:f.write(json.dumps(r)+"\n")
    return hashlib.sha256(p.read_bytes()).hexdigest()

class FreeIntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=pathlib.Path(self.tmp.name)
        ids=[3155]+list(range(1,100))
        a=[]
        for n,cid in enumerate(ids):
            sym="QNT" if cid==3155 else "C"+str(cid)
            a.append({"cmc_id":cid,"name":"Quant" if cid==3155 else "Asset"+str(cid),
               "symbol":sym,"cmc100_weight":0.01,
               "cmc_quote":{"price_usd":10.0,"ret_24h_pct":float(n),"volume_change_24h_pct":float(n)/2},
               "perpetual":{"symbol":"QNT-USDT-SWAP" if cid==3155 else sym+"-USDT-SWAP"},
               "perp_market":{"oi_usd":321.2}})
        write(self.root/"docs/latest.json",{"index":{"verified_constituents":100},
               "assets":a,"market_context":{"risk_indicator":"TEST"},
               "snapshot_completed_utc":OBS})
        engine=[{"observation_id":"r1","cmc_id":1,"source":"okx_swap_tickers",
                 "coin_identity_status":"CMC100_SNAPSHOT_OKX_CONTRACT_ANCHORED",
                 "observed_utc":OBS},
                {"observation_id":"global","source":"stablecoin_network",
                 "observed_utc":OBS,"metrics":{"supply_usd":4200}},
                {"observation_id":"qntwrong","cmc_id":3155,"source":"okx_swap_tickers",
                 "observed_utc":OBS,"metrics":{"oi_usd":1}}]
        extr=[{"event_id":"x1","title":"Cross border payment system announced",
               "excerpt":"A brand new event was announced by a payments provider",
               "url":"https://example.com/news1","observed_utc":OBS,
               "source_families":["CROSS_SECTOR"],"query_scoped_ids":[]},
              {"event_id":"x2","title":"Asset1 token upgrade",
               "url":"https://example.com/news2","observed_utc":OBS,
               "source_families":["COIN_RESEARCH"],"query_scoped_ids":[1]}]
        p=self.root/"docs/evidence_engine/archive/e.gz"
        p2=self.root/"docs/expanded_discovery/archive/d.gz"
        write(self.root/"docs/evidence_engine/status.json",
              {"capture_utc":OBS,"archive_path":"docs/evidence_engine/archive/e.gz",
               "archive_sha256":archive(p,engine),"records":3})
        write(self.root/"docs/expanded_discovery/status.json",
              {"capture_utc":OBS,"archive_path":"docs/expanded_discovery/archive/d.gz",
               "archive_sha256":archive(p2,extr),"full_archive_count":2})
        write(self.root/"docs/research/status.json",
              {"capture_utc":OBS,"source_attempts":[]})
        write(self.root/"docs/discovery/status.json",
              {"capture_completed_utc":OBS,"access_gaps":[]})
        write(self.root/"docs/research/latest.json",{"coins":[{"cmc_id":1,"symbol":"C1"}],
              "events":[{"event_id":"research-1","headline":"Company announces new payment platform",
                         "published_utc":OBS,"first_observed_utc":OBS,
                         "url":"https://example.org/payment","cmc_ids":[]}],
              "families":{"stablecoin_global":{"total_supply_usd":1234567},
                          "protocol_tvl":[{"cmc_id":1,"protocol_name":"TEST","tvl_usd":500.0}],
                          "okx_orderbooks":[{"cmc_id":3155,"instrument_id":"QNT-USDT-SWAP",
                                             "spread_bps":20}]}})
        write(self.root/"docs/discovery/latest.json",
              {"events":[{"event_id":"adj-1","title":"Novel network energy technology breakthrough",
                          "excerpt":"This technology involves a new infrastructure solution for high volume settlement",
                          "url":"https://other.org/tech","published_utc":OBS,
                          "observed_utc":OBS,"theme_leads":["UNEXPECTED_NEW_DOMAIN"],
                          "source_family":"TECH_NEWS","source_id":"technology"}]})
    def tearDown(self):
        self.tmp.cleanup()
    def test_full_four_plane_no_network(self):
        m,c=foi.build(self.root,cutoff=T,network=False)
        self.assertEqual(c["official_assets"],100)
        self.assertEqual(len(c["source_planes_integrated"]),5)
        self.assertEqual(c["evidence_counts"]["engine_rows"],3)
        self.assertEqual(c["evidence_counts"]["expanded_rows"],2)
        self.assertEqual(c["evidence_counts"]["research_event_rows"],1)
        self.assertEqual(c["evidence_counts"]["adjacent_full_event_rows"],1)
        self.assertEqual(c["evidence_counts"]["canonical_research_leads"],4)
        self.assertEqual(c["identity_quarantine"][0]["cmc_id"],3155)
        cards=[]
        for i in range(1,6):
            cards+=foi.read(self.root/f"docs/intelligence/coin_batches/batch_{i:02d}.json")["coins"]
        self.assertEqual(len(cards),100)
        qnt=next(x for x in cards if x["cmc_id"]==3155)
        self.assertIsNone(qnt["perpetual"])
        self.assertFalse(qnt["quantitative_research_families"])
        self.assertEqual(c["excluded_ambiguous_okx_structured_records"],1)
        self.assertFalse(qnt["engine_record_counts_by_source"])
        coin1=next(x for x in cards if x["cmc_id"]==1)
        self.assertEqual(len(coin1["quantitative_research_families"]),1)
        self.assertEqual(coin1["candidate_event_count"],1)
        self.assertTrue(foi.read(self.root/"docs/intelligence/sector_intelligence.json")["sectors"])
        self.assertTrue(foi.read(self.root/"docs/intelligence/global_intelligence.json")["global_unresolved_leads"])
        g=foi.read(self.root/"docs/intelligence/global_intelligence.json")
        self.assertEqual(g["global_research_quantitative_families"]["stablecoin_global"]["observation"]["total_supply_usd"],1234567)
        self.assertEqual(g["unassigned_structured_counts_by_source"]["stablecoin_network"],1)
        self.assertEqual(g["unassigned_structured_samples_by_source"]["stablecoin_network"][0]["metrics"]["supply_usd"],4200)
        self.assertGreater(len(foi.read(self.root/"docs/intelligence/research_tasks.json")["tasks"]),0)
        self.assertEqual(m["llm_calls"],0)
        self.assertTrue(m["archives"]["engine"]["verified"])
        self.assertTrue(m["archives"]["expanded"]["verified"])
    def test_archive_integrity_fails_closed(self):
        p=self.root/"docs/evidence_engine/archive/e.gz"
        p.write_bytes(p.read_bytes()+b"tamper")
        with self.assertRaisesRegex(ValueError,"SHA mismatch"):foi.build(self.root,cutoff=T)
    def test_full_adjacent_archive_not_just_limited_read_index(self):
        archive_path=self.root/"docs/discovery/archive/20261112/events.json"
        full=foi.read(self.root/"docs/discovery/latest.json")
        original=full["events"][0]
        full["events"]= [original,{**original,"event_id":"another","title":"Unexpected global signal",
                          "url":"https://another.example/news"}]
        write(archive_path,full)
        st=foi.read(self.root/"docs/discovery/status.json")
        st["full_archive_path"]="docs/discovery/archive/20261112/events.json"
        st["full_archive_leads"]=2
        st["read_index_leads"]=1
        write(self.root/"docs/discovery/status.json",st)
        _,cov=foi.build(self.root,cutoff=T)
        self.assertEqual(cov["adjacent_discovery_source"]["mode"],"FULL_ARCHIVE")
        self.assertEqual(cov["evidence_counts"]["adjacent_full_event_rows"],2)
        self.assertEqual(cov["evidence_counts"]["adjacent_read_index_event_rows"],1)
    def test_second_hop_uses_newly_returned_sources(self):
        earlier=[{"query":"original liquidity infrastructure","task_id":"first"}]
        hits=[{"id":"eventA","source_plane":"adaptive","source_id":"taskA",
               "title":"Emerging settlement architecture adoption","themes":[]},
              {"id":"eventB","source_plane":"adaptive","source_id":"taskB",
               "title":"Emerging settlement architecture acceleration","themes":[]}]
        next_tasks=foi.second_hop_tasks(hits,earlier,limit=2)
        self.assertTrue(any(t["trigger"]=="SECOND_HOP_FROM_NEW_FINDINGS" for t in next_tasks))
        self.assertIn("emerging settlement",next_tasks[0]["query"])
    def test_future_data_not_leaked(self):
        extr=self.root/"docs/expanded_discovery/archive/d.gz"
        with gzip.open(extr,"wt",encoding="utf-8") as f:
            f.write(json.dumps({"event_id":"future","title":"Should not appear",
               "url":"https://example.com/f","observed_utc":"2026-11-13T00:00:00Z"})+"\n")
        st=foi.read(self.root/"docs/expanded_discovery/status.json")
        st["archive_sha256"]=foi.digest(extr);st["full_archive_count"]=1
        write(self.root/"docs/expanded_discovery/status.json",st)
        m,c=foi.build(self.root,cutoff=T)
        self.assertEqual(c["evidence_counts"]["canonical_research_leads"],2)
    def test_dynamic_discovery_dependent_on_actual_sources(self):
        docs=[]
        for x,source in (("Cloud processor deployment rises","alpha"),
                         ("Cloud processor demand increases","beta")):
            docs.append({"id":source,"source_plane":"adjacent","source_id":source,
                         "title":x,"themes":["NEW_TECH"]})
        terms=foi.keyword_pairs(docs)
        self.assertTrue(any(x["term"]=="cloud processor" for x in terms))
        self.assertEqual(next(x for x in terms if x["term"]=="cloud processor")["independent_source_count"],2)
    def test_no_fake_token_linking(self):
        x={"event_id":"test","title":"Quantinuum announces shares",
           "url":"https://example.com/news","observed_utc":OBS,
           "query_scoped_ids":[3155]}
        e=foi.event_doc("expanded",x,T)
        self.assertEqual(e["claim_status"],"NOT_INDEPENDENTLY_VERIFIED")
        self.assertEqual(e["identity_status"],"SEARCH_OR_TEXT_CANDIDATE_NOT_VERIFIED")
    def test_network_fetch_is_bounded_and_audited(self):
        xml=b'<rss><channel><item><title>Test market shock</title><link>https://example.org/test</link><pubDate>Thu, 12 Nov 2026 04:00:00 GMT</pubDate></item></channel></rss>'
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):return xml
        def opener(req,timeout):return Response()
        tasks=[{"task_id":"test","query":"unexpected test","scope":"GLOBAL","status":"PLANNED","results":0}]
        found,audit=foi.adaptive_fetch(tasks,T,max_requests=1,opener=opener)
        self.assertEqual(len(found),1)
        self.assertEqual(audit[0]["status"],"OK")
        self.assertEqual(tasks[0]["status"],"QUERIED")
if __name__=="__main__":unittest.main()
