#!/usr/bin/env python3
"""100-CMC-ID research expansion: discovery provenance, NOT token relevance.

A public-source lead harvester, not a forecast. IDs on search requests mean only
'queried for', never that an article was correctly matched to or benefits a coin.
All fetched records are retained in compressed, immutable per-run archives.
"""
from __future__ import annotations
import concurrent.futures as cf
import csv
import datetime as dt
import gzip
import hashlib
import html
import io
import json
import os
import pathlib
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict, deque
from email.utils import parsedate_to_datetime
from discovery_quality import enrich

UTC = dt.timezone.utc
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs' / 'expanded_discovery'
MARKET = ROOT / 'docs' / 'latest.json'
USER_AGENT = 'CMC100-Evidence-Research/3.0 (+https://github.com/SnakU4/crypto-market-data)'
MAX_BYTES = 5_000_000
TARGET_UNIQUE = 10_000  # report gap, NEVER pad to target
INDEX_LIMIT = 1_000
FRESH_HOURS = 48
HISTORICAL_HOURS = 7*24
MAX_RSS_ITEMS = 100

# 6 different questions for EVERY official coin, independent of volatility or rank.
# A scoped query is a research direction, never an asset-to-event assertion.
COIN_LENSES = (
    ('NEWS', '{asset} cryptocurrency OR blockchain when:2d'),
    ('DEVELOPMENT', '{asset} blockchain protocol upgrade developers release when:7d'),
    ('SECURITY', '{asset} crypto exploit incident outage vulnerability when:7d'),
    ('TOKENOMICS', '{asset} token unlock staking governance burn supply when:7d'),
    ('ECOSYSTEM', '{asset} adoption partnership integrations ecosystem when:7d'),
    ('MARKETS', '{asset} crypto exchange listing liquidity institutional ETF when:2d'),
    ('COMMUNITY_INDEX', '{asset} site:reddit.com OR site:bitcointalk.org OR site:forum when:7d'),
    ('SOCIAL_INDEX', '{asset} site:x.com OR site:bsky.app when:7d'),
)
# Cross-sector lenses are NOT assumed to have a token connection.
WIDE_LENSES = {
    'AI_COMPUTE':('new inference AI agent accelerator datacenter decentralized GPU','AI chip cloud compute economics'),
    'SECURITY':('zero day cryptography software supply chain compromise','security cloud infrastructure outage'),
    'QUANTUM':('quantum resistant cryptography standard algorithm breakthrough','post quantum blockchain signatures'),
    'PAYMENTS':('cross border payment rails settlement banking real time','stablecoin infrastructure payment regulation'),
    'ROBOTICS':('autonomous robotics machine payments identity agents','machine to machine micropayments'),
    'ENERGY':('power grid datacenter mining electricity tariffs','energy demand battery supply'),
    'CHIPS':('semiconductor GPU export sanctions foundry capacity','NVIDIA AI GPU cloud price'),
    'IDENTITY':('biometric identity cybersecurity authentication zk','privacy identity proof personhood'),
    'REGULATORY':('securities legislation digital assets government enforcement','central bank crypto custody'),
    'RESEARCH':('distributed systems ZK privacy cryptographic breakthrough','distributed consensus security research'),
    'NETWORK':('cloud outage internet routing DNS infrastructure','software protocol vulnerability'),
    'FINANCE':('global liquidity credit spreads treasury yields funding','finance dollar market flows'),
}
# Author-controlled and community-published RSS: public availability checked per run.
COMMUNITY_FEEDS = (
    ('ethresearch','https://ethresear.ch/latest.rss'),
    ('ethmagicians','https://ethereum-magicians.org/latest.rss'),
    ('uniswapgov','https://gov.uniswap.org/latest.rss'),
    ('aavegov','https://governance.aave.com/latest.rss'),
    ('arbitrumgov','https://forum.arbitrum.foundation/latest.rss'),
    ('optimismgov','https://gov.optimism.io/latest.rss'),
    ('polkadotgov','https://forum.polkadot.network/latest.rss'),
    ('cosmoshub','https://forum.cosmos.network/latest.rss'),
    ('lido','https://research.lido.fi/latest.rss'),
    ('maker','https://forum.sky.money/latest.rss'),
    ('zcash','https://forum.zcashcommunity.com/latest.rss'),
    ('stacks','https://forum.stacks.org/latest.rss'),
)
# Direct project and developer primary sources, audited independently.
PROJECT_PRIMARY_FEEDS = (
    ('bitcoin_core','https://bitcoincore.org/en/releases.atom'),
    ('ethereum_foundation','https://blog.ethereum.org/feed.xml'),
    ('solana','https://solana.com/news/rss.xml'),
    ('chainlink','https://blog.chain.link/feed/'),
    ('uniswap','https://blog.uniswap.org/rss.xml'),
    ('aave','https://aave.com/blog/rss.xml'),
    ('polkadot','https://polkadot.com/blog/rss.xml'),
    ('arbitrum','https://blog.arbitrum.io/rss/'),
    ('optimism','https://www.optimism.io/blog/rss.xml'),
    ('cosmos','https://blog.cosmos.network/feed/'),
    ('github_bitcoin','https://github.com/bitcoin/bitcoin/releases.atom'),
    ('github_goethereum','https://github.com/ethereum/go-ethereum/releases.atom'),
    ('github_solana','https://github.com/anza-xyz/agave/releases.atom'),
    ('github_aave','https://github.com/aave/aave-v3-core/releases.atom'),
    ('github_uniswap','https://github.com/Uniswap/v4-core/releases.atom'),
    ('github_polkadot','https://github.com/paritytech/polkadot-sdk/releases.atom'),
    ('github_cosmos','https://github.com/cosmos/gaia/releases.atom'),
    ('github_optimism','https://github.com/ethereum-optimism/optimism/releases.atom'),
)
# Public issuer/standards/security feeds and non-crypto technology sources.
ADDITIONAL_FEEDS = (
    ('nist_cyber','https://www.nist.gov/news-events/cybersecurity/rss.xml'),
    ('cisa_advisories','https://www.cisa.gov/cybersecurity-advisories/all.xml'),
    ('krebsonsecurity','https://krebsonsecurity.com/feed/'),
    ('github_blog','https://github.blog/feed/'),
    ('linuxfoundation','https://www.linuxfoundation.org/blog/rss.xml'),
    ('the_register','https://www.theregister.com/headlines.atom'),
    ('arxiv_networks','https://rss.arxiv.org/rss/cs.NI'),
    ('arxiv_security','https://rss.arxiv.org/rss/cs.CR'),
)
# Explicit, separately labelled authorization gaps; no scraping workarounds.
ACCESS_GAPS = {
    'X_TWITTER':'NO_VERIFIED_FREE_BULK_OFFICIAL_ACCESS',
    'REDDIT':'APP_AUTHORIZATION_NEEDED;RSS_SUNSETS_2026-11-13',
    'BLUESKY_SEARCH':'PREVIOUS_GITHUB_ACTIONS_SEARCHPOSTS_RETURNED_HTTP_403',
    'GDELT_BULK':'PREVIOUS_GITHUB_ACTIONS_RETURNED_HTTP_429',
    'CLOSED_COMMUNITIES':'NO_AUTHORIZED_PUBLIC_ACCESS',
}


def iso(x):
    return x.astimezone(UTC).isoformat(timespec='seconds').replace('+00:00','Z')


def parse_time(x):
    if x is None: return None
    try:
        if isinstance(x,(int,float)):
            return dt.datetime.fromtimestamp(float(x)/(1000 if x>1e11 else 1),UTC)
        s=str(x).strip()
        if re.fullmatch(r'\d{8}T\d{6}Z',s):
            return dt.datetime.strptime(s,'%Y%m%dT%H%M%SZ').replace(tzinfo=UTC)
        return dt.datetime.fromisoformat(s.replace('Z','+00:00')).astimezone(UTC)
    except (ValueError,OverflowError,TypeError):
        try:return parsedate_to_datetime(str(x)).astimezone(UTC)
        except (TypeError,ValueError,OverflowError):return None


def strip_html(s,limit=800):
    x=re.sub(r'<[^>]+>',' ',str(s or ''))
    return re.sub(r'\s+',' ',html.unescape(x)).strip()[:limit]


def canonical_url(u):
    if not isinstance(u,str) or not u.startswith(('https://','http://')):return None
    p=urllib.parse.urlsplit(u)
    if not p.netloc:return None
    # Google News opaque articles retain path. Ignore tracking/query parameters.
    return urllib.parse.urlunsplit((p.scheme.lower(),p.netloc.lower().removeprefix('www.'),p.path.rstrip('/'),'',''))


def event_id(u):
    return hashlib.sha256(canonical_url(u).encode()).hexdigest()[:24]


def story_title_id(title):
    # Only strict near-exact normalization: do not conflate genuinely distinct articles.
    s=re.sub(r'\s+-\s+[^-]{3,60}$','',strip_html(title,500).casefold())
    s=re.sub(r'[^\w]+',' ',s).strip()
    return hashlib.sha256(s.encode()).hexdigest()[:20]


def qurl(endpoint, params):return endpoint+'?'+urllib.parse.urlencode(params)


def market_assets(market):
    a=market.get('assets') or []
    if market.get('index',{}).get('verified_constituents')!=100 or len(a)!=100 or len(set(int(x['cmc_id']) for x in a))!=100:
        raise ValueError('Official CMC100 100 unique constituents required')
    return a


def query_name(asset):
    # Names are quoted in search syntax; ticker provided for ambiguity reduction.
    name=str(asset['name']).replace('"','').strip()
    symbol=str(asset['symbol']).replace('"','').strip()
    return '"'+name+'" '+symbol


def plan(market,previous=None):
    a=market_assets(market);jobs=[]
    for c in a:
        phrase=query_name(c)
        for lens,template in COIN_LENSES:
            query=template.format(asset=phrase)
            jobs.append({'id':f'coin_{c["cmc_id"]}_{lens}', 'family':'COIN_RESEARCH', 'kind':'rss',
                         'endpoint':'GOOGLE_NEWS','target':qurl('https://news.google.com/rss/search',{'q':query,'hl':'en-US','gl':'US','ceid':'US:en'}),
                         'query_cmc_id':int(c['cmc_id']),'query_symbol':c['symbol'], 'lens':lens})
    for tag,(q1,q2) in WIDE_LENSES.items():
        for k,query in enumerate((q1,q2)):
            jobs.append({'id':f'wide_{tag}_{k}', 'family':'CROSS_SECTOR', 'kind':'rss', 'endpoint':'GOOGLE_NEWS',
                         'target':qurl('https://news.google.com/rss/search',{'q':query+' when:7d','hl':'en-US','gl':'US','ceid':'US:en'}),
                         'lens':tag})
    for name,url in COMMUNITY_FEEDS:
        jobs.append({'id':f'community_{name}','family':'PUBLIC_COMMUNITY','kind':'rss','endpoint':'COMMUNITY_RSS','target':url,'lens':'COMMUNITY'})
    for name,url in PROJECT_PRIMARY_FEEDS:
        jobs.append({'id':f'primary_{name}','family':'PROJECT_PRIMARY','kind':'rss','endpoint':'PROJECT_DIRECT_RSS','target':url,'lens':'PRIMARY'})
    for name,url in ADDITIONAL_FEEDS:
        jobs.append({'id':f'additional_{name}','family':'TECH_SECURITY_RESEARCH','kind':'rss','endpoint':'PUBLIC_RSS','target':url,'lens':'ADJACENT'})
    # HN time filter is essential; prior version returned posts from 2018!
    cutoff=int((dt.datetime.now(UTC)-dt.timedelta(days=7)).timestamp())
    for tag,(_,q2) in WIDE_LENSES.items():
        jobs.append({'id':f'hn_{tag}','family':'DEVELOPER_COMMUNITY','kind':'hn','endpoint':'HN_ALGOLIA',
                     'target':qurl('https://hn.algolia.com/api/v1/search_by_date',{'query':q2,'tags':'story','hitsPerPage':100,'numericFilters':f'created_at_i>{cutoff}'}),
                     'lens':tag})
    return jobs


class HTTP:
    """Conservative bounded parallelism; dampens 403/429 host-wide floods."""
    def __init__(self,opener=None,sleeper=time.sleep,clock=time.monotonic):
        self.opener=opener or urllib.request.urlopen
        self.sleeper=sleeper
        self.clock=clock
        self.lock=threading.Lock()
        self.last={};self.failures=Counter();self.calls=[]
    def get(self,job):
        host=urllib.parse.urlsplit(job['target']).netloc
        with self.lock:
            if self.failures[host]>=8:
                rec={'id':job['id'],'family':job['family'],'endpoint':job['endpoint'],'status':'HOST_CIRCUIT_OPEN','count':0,'error':'REPEATED_HTTP_403_OR_429'}
                self.calls.append(rec);return None
            gap=.12 if host=='news.google.com' else .25
            hold=max(0,self.last.get(host,0)+gap-self.clock())
            self.last[host]=self.clock()+hold
        if hold:self.sleeper(hold)
        output=None;err=None;status='ERROR'
        for attempt in range(2):
            try:
                req=urllib.request.Request(job['target'],headers={'User-Agent':USER_AGENT,
                    'Accept':'application/rss+xml, application/xml, application/json, */*'})
                with self.opener(req,timeout=16) as response:
                    raw=response.read(MAX_BYTES+1)
                    if len(raw)>MAX_BYTES:raise ValueError('RESPONSE_TOO_LARGE')
                output=json.loads(raw) if job['kind']=='hn' else raw
                status='OK';break
            except (urllib.error.HTTPError,urllib.error.URLError,OSError,ValueError,TimeoutError,TypeError) as e:
                err=type(e).__name__+': '+str(e)[:140]
                code=getattr(e,'code',None)
                if code in (403,429):
                    with self.lock:self.failures[host]+=1
                    break  # do not hammer rate-limited services
                if attempt==0:self.sleeper(.35)
        with self.lock:self.calls.append({'id':job['id'],'family':job['family'],'endpoint':job['endpoint'],
            'status':status,'count':None,'error':err,'target':job['target']})
        return output


def rss_records(body,job,observed,max_items=MAX_RSS_ITEMS):
    if not isinstance(body,bytes):return []
    try:root=ET.fromstring(body)
    except ET.ParseError:return []
    rows=[]
    for item in root.iter():
        if item.tag.rsplit('}',1)[-1] not in ('item','entry'):continue
        fields={};link=None
        for child in item:
            k=child.tag.rsplit('}',1)[-1]
            if k=='link':link=link or child.get('href') or (child.text or '').strip()
            if k in ('title','pubDate','published','updated','description','summary','subtitle','guid','id','encoded','content'):
                fields[k]=(child.text or '').strip()
        title=strip_html(fields.get('title'),300)
        url=link or fields.get('guid') or fields.get('id')
        if not title or not canonical_url(url):continue
        publication=parse_time(fields.get('published') or fields.get('pubDate') or fields.get('updated'))
        summary=strip_html(fields.get('content') or fields.get('encoded') or fields.get('summary') or fields.get('description') or fields.get('subtitle'),1600)
        rows.append({'url':url,'title':title,'excerpt':summary,'published_utc':iso(publication) if publication else None,
                     'publication_time_status':'RSS_DATE' if publication else 'UNKNOWN',
                     'source_type':'RSS','observed_utc':observed,'context_origin':'FEED_EXCERPT' if summary else 'TITLE_ONLY'})
        if len(rows)>=max_items:break
    return rows


def hn_records(obj,job,observed,max_items=100):
    if not isinstance(obj,dict):return []
    rows=[]
    for h in (obj.get('hits') or [])[:max_items]:
        if not isinstance(h,dict):continue
        title=strip_html(h.get('title') or h.get('story_title'),300)
        url=h.get('url') or ('https://news.ycombinator.com/item?id='+str(h.get('objectID'))) if h.get('objectID') else None
        if not title or not canonical_url(url):continue
        date=parse_time(h.get('created_at_i') or h.get('created_at'))
        rows.append({'url':url,'title':title,'excerpt':strip_html(h.get('story_text'),800),
                     'published_utc':iso(date) if date else None,
                     'publication_time_status':'HN_PLATFORM_DATE' if date else 'UNKNOWN',
                     'source_type':'HACKER_NEWS','observed_utc':observed,
                     'context_origin':'HN_TEXT' if h.get('story_text') else 'TITLE_ONLY',
                     'engagement':{'points':h.get('points'),'comments':h.get('num_comments')},
                     'discussion_url':'https://news.ycombinator.com/item?id='+str(h.get('objectID'))})
    return rows


def merge_records(records,first_seen,cutoff,now_utc):
    """No inferred price impact; all search-to-event relations are QUERY PROVENANCE."""
    all_by_url={};future=0;dropped=0
    for rec,job in records:
        u=canonical_url(rec.get('url'))
        if u is None:continue
        published=parse_time(rec.get('published_utc'))
        if published and published>now_utc+dt.timedelta(minutes=2):
            future+=1;continue
        if published and published<cutoff:
            dropped+=1;continue
        k=event_id(rec['url']); item=all_by_url.get(k)
        search_origin={'source_id':job['id'],'family':job['family'],'lens':job['lens'],
                       'queried_cmc_id':job.get('query_cmc_id'),
                       'identity_status':'QUERY_ORIGIN_NOT_COIN_MATCH' if job.get('query_cmc_id') else 'NO_COIN_SCOPE'}
        if item is None:
            item={**rec,'event_id':k,'story_title_hash':story_title_id(rec['title']),
                  'first_observed_utc':first_seen.get(k) or rec['observed_utc'],
                  'search_origins':[search_origin],
                  'coin_relevance_status':'NOT_ASSESSED', 'price_direction':'NOT_ASSESSED'}
            all_by_url[k]=item
        else:
            scopes={(o['source_id'],o.get('queried_cmc_id')) for o in item['search_origins']}
            if (search_origin['source_id'],search_origin.get('queried_cmc_id')) not in scopes:
                item['search_origins'].append(search_origin)
            if len(rec.get('excerpt',''))>len(item.get('excerpt','')):
                item['excerpt']=rec['excerpt'];item['context_origin']=rec['context_origin']
            if not item['published_utc'] and rec.get('published_utc'):item['published_utc']=rec['published_utc']
    for item in all_by_url.values():
        item['source_families']=sorted({o['family'] for o in item['search_origins']})
        item['query_scoped_ids']=sorted({o['queried_cmc_id'] for o in item['search_origins'] if o['queried_cmc_id'] is not None})
    return list(all_by_url.values()),future,dropped


def index_select(events,cap=INDEX_LIMIT,now_utc=None):
    """Recency-first with guaranteed family & source diversity; never coin-match-based scoring."""
    if cap<0:raise ValueError('cap cannot be negative')
    if not events or cap==0:return []
    now_utc=now_utc or dt.datetime.now(UTC)
    # Use a stable primary family, and source, for balancing; do not imply relevance.
    groups=defaultdict(lambda:defaultdict(list))
    for e in events:
        primary=sorted(e['search_origins'],key=lambda o:(o['family'],o['source_id']))[0]
        family=primary['family'];source=primary['source_id']
        groups[family][source].append(e)
    fresh=lambda e:((now_utc-(parse_time(e.get('published_utc')) or parse_time(e['first_observed_utc']))).total_seconds()<=FRESH_HOURS*3600)
    for m in groups.values():
        for a in m.values():a.sort(key=lambda e:(fresh(e),e['published_utc'] or e['first_observed_utc'],e['event_id']),reverse=True)
    families=sorted(groups)
    sources={f:deque(sorted(groups[f])) for f in families}
    selected=[];seen=set()
    while len(selected)<cap:
        changed=False
        for f in families:
            q=sources[f]
            if not q:continue
            for _ in range(len(q)):
                key=q.popleft();rows=groups[f][key]
                if rows:
                    rec=rows.pop(0)
                    if rows:q.append(key)
                    if rec['event_id'] not in seen:
                        seen.add(rec['event_id']);selected.append(rec);changed=True
                    break
            if len(selected)>=cap:break
        if not changed:break
    return selected


def collect(market,network,previous_seen=None,max_workers=5,now_utc=None):
    assets=market_assets(market)
    now_utc=now_utc or dt.datetime.now(UTC)
    jobs=plan(market)
    cutoff=now_utc-dt.timedelta(days=7)
    findings=[];by_source=Counter();observed_by_source=Counter()
    def work(job):
        raw=network.get(job)
        observed=iso(now_utc) # freeze run time; network actual request status separately audited
        rows=(hn_records(raw,job,observed) if job['kind']=='hn' else rss_records(raw,job,observed))
        return job,rows
    with cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
        for job,rows in ex.map(work,jobs):
            by_source[job['id']]=len(rows)
            findings.extend((r,job) for r in rows)
    seen=previous_seen or {}
    all_events,future,old=merge_records(findings,seen,cutoff,now_utc)
    all_events.sort(key=lambda e:(e['published_utc'] or e['first_observed_utc'],e['event_id']),reverse=True)
    new_events=[e for e in all_events if e['event_id'] not in seen]
    quality=enrich(all_events, max_articles=max(0,min(200,int(os.environ.get('DISCOVERY_ARTICLE_BUDGET','80')))))
    # Distinguish newly observed URLs from distinct headlines and information.
    historic_titles={e['story_title_hash'] for e in all_events if e['event_id'] in seen}
    new_title_clusters={e['story_title_hash'] for e in new_events if e['story_title_hash'] not in historic_titles}
    novel_substantive=sum(e['excerpt_adds_information'] for e in new_events)
    index=index_select(all_events,INDEX_LIMIT,now_utc)
    merged_first={e['event_id']:e['first_observed_utc'] for e in all_events}
    # Keep only ~14 days of seen URLs; older immutably archived in compressed deltas.
    for k,t in seen.items():
        parsed=parse_time(t)
        if parsed and parsed>=now_utc-dt.timedelta(days=14):merged_first.setdefault(k,t)
    fams=Counter();raw_per_coins=Counter();unique_queries_per_coin=Counter();fresh=0;old7=0
    successful_coin_queries=Counter();nonempty_coin_queries=Counter()
    for j in jobs:
        if j.get('query_cmc_id') is None:continue
        if any(r['id']==j['id'] and r['status']=='OK' for r in network.calls):successful_coin_queries[str(j['query_cmc_id'])]+=1
        if by_source[j['id']]>0:nonempty_coin_queries[str(j['query_cmc_id'])]+=1
    for e in all_events:
        for fam in e['source_families']:fams[fam]+=1
        for cid in e['query_scoped_ids']:raw_per_coins[str(cid)]+=1
        p=parse_time(e['published_utc'])
        fresh+=bool(p and p>=now_utc-dt.timedelta(hours=24))
    for job in jobs:
        if 'query_cmc_id' in job:unique_queries_per_coin[str(job['query_cmc_id'])]+=1
    audit=network.calls
    blocked=[r for r in audit if r['status']!='OK']
    stats={'schema_version':'expanded-discovery-v3','capture_utc':iso(now_utc),
        'market_snapshot_utc':market.get('snapshot_completed_utc'),'official_cmc100_verified':100,
        'requests_planned':len(jobs),'requests_executed':len(audit),'requests_ok':sum(r['status']=='OK' for r in audit),
        'requests_blocked':len(blocked),'requests_with_leads':sum(bool(v) for v in by_source.values()),
        'raw_leads':len(findings),'distinct_url_leads':len(all_events), 'new_since_prior':len(new_events),
        'incremental_new_url_leads':len(new_events),
        'incremental_new_title_clusters_within_run':len(new_title_clusters),
        'incremental_new_urls_with_substantive_context':novel_substantive,
        'incremental_baseline':'ROLLING_14_DAY_URL_REGISTRY_NOT_GLOBAL_ALL_TIME',
        'first_run_baseline':not bool(seen),
        'new_urls_by_source_family':dict(Counter(f for e in new_events for f in e['source_families'])),
        'information_quality':quality,
        'distinct_story_title_hashes':len({x['story_title_hash'] for x in all_events}),
        'target_unique_per_run':TARGET_UNIQUE,'target_met':len(all_events)>=TARGET_UNIQUE,
        'target_shortfall':max(0,TARGET_UNIQUE-len(all_events)),
        'unique_urls_published_last_24h':fresh,'all_100_coins_planned':len(unique_queries_per_coin)==100,
        'coins_with_successful_query':len(successful_coin_queries),
        'successful_queries_per_coin':dict(successful_coin_queries),
        'coins_with_nonempty_query':len(nonempty_coin_queries),
        'query_count_per_coin':dict(unique_queries_per_coin), 'search_results_per_queried_coin':dict(raw_per_coins),
        'zero_result_coin_queries':[j['id'] for j in jobs if j.get('query_cmc_id') is not None and not by_source[j['id']]],
        'zero_result_coins':[x['cmc_id'] for x in assets if not raw_per_coins[str(x['cmc_id'])]],
        'family_unique_url_counts':dict(fams),'read_index_count':len(index),
        'full_archive_count':len(all_events),'full_archive_excerpts':sum(bool(e.get('excerpt')) for e in all_events),
        'archive_is_complete':'ALL_DISTINCT_VALID_ITEMS',
        'future_dated_excluded':future,'older_than_7days_excluded':old,
        'query_origin_is_relevance_verdict':False, 'coin_matching_performed':False,
        'source_error_examples':blocked[:40],
        'access_gaps':ACCESS_GAPS,
        'limits':['GOOGLE_NEWS_RSS_IS_NOT_ALL_NEWS','SEARCH_ENGINE_COVERAGE_VARIABLE',
                  'NETWORK_RATE_LIMITS_AND_SCHEDULE_DELAYS','BOUNDED_PUBLIC_ARTICLE_EXCERPTS_ONLY',
                  'QUERY_ORIGIN_NOT_COIN_MATCH','NUMBER_OF_LEADS_NOT_ALPHA_QUALITY']}
    return {'status':stats,'events':all_events,'new_events':new_events,'index':index,
            'first_seen':merged_first,'audit':audit,'jobs':jobs}


def write_bundle(bundle,out=OUT):
    out.mkdir(parents=True,exist_ok=True)
    stamp=bundle['status']['capture_utc'].replace(':','').replace('-','')
    date=stamp[:8]
    archive=out/'archive'/date/(stamp+'_all.jsonl.gz')
    delta=out/'archive'/date/(stamp+'_new.jsonl.gz')
    archive.parent.mkdir(parents=True,exist_ok=True)
    if archive.exists() or delta.exists():raise FileExistsError('Immutable PIT research archive already exists')
    def write_gz(path,events):
        with path.open('wb') as f:
            with gzip.GzipFile(filename='',mode='wb',fileobj=f,compresslevel=6,mtime=0) as gz:
                for e in events:gz.write((json.dumps(e,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf8'))
    write_gz(archive,bundle['events']);write_gz(delta,bundle['new_events'])
    status=dict(bundle['status'],archive_path=str(archive.relative_to(ROOT) if archive.is_relative_to(ROOT) else archive.relative_to(out)),new_archive_path=str(delta.relative_to(ROOT) if delta.is_relative_to(ROOT) else delta.relative_to(out)),
                archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                new_archive_sha256=hashlib.sha256(delta.read_bytes()).hexdigest())
    def write_json(p,obj):
        p.write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n',encoding='utf8')
    write_json(out/'status.json',status)
    write_json(out/'latest.json',{'schema_version':'expanded-discovery-v3','status':{k:v for k,v in status.items() if k not in ('query_count_per_coin','search_results_per_queried_coin','zero_result_coin_queries','source_error_examples')},
                                  'events':bundle['index']})
    # Human- and connector-readable shards (not a substitute for the immutable gzip).
    shard_dir=out/'latest_shards';shard_dir.mkdir(exist_ok=True)
    for idx in range(20):
        rows=bundle['events'][idx::20]
        write_json(shard_dir/f'shard_{idx:02}.json',{'capture_utc':status['capture_utc'],'events':rows})
    with (out/'source_audit.csv').open('w',encoding='utf8',newline='') as f:
        fieldnames=['id','family','endpoint','status','error','target']
        w=csv.DictWriter(f,fieldnames=fieldnames,extrasaction='ignore');w.writeheader();w.writerows(bundle['audit'])
    # bounded persisted first-seen registry, avoids pretending old articles are new on next pass.
    write_json(out/'seen_registry.json',bundle['first_seen'])
    return status


def main():
    if not MARKET.exists():raise SystemExit('Missing official market snapshot docs/latest.json')
    market=json.loads(MARKET.read_text(encoding='utf8'))
    previous={}; seen_path=OUT/'seen_registry.json'
    if seen_path.exists():previous=json.loads(seen_path.read_text(encoding='utf8'))
    max_workers=max(1,min(8,int(os.environ.get('DISCOVERY_WORKERS','5'))))
    data=collect(market,HTTP(),previous,max_workers)
    result=write_bundle(data)
    print(json.dumps({key:result[key] for key in ('requests_planned','requests_ok','distinct_url_leads',
        'distinct_story_title_hashes','target_met','target_shortfall','new_since_prior','information_quality','archive_path')} ,indent=2))
    return 0

if __name__=='__main__':raise SystemExit(main())