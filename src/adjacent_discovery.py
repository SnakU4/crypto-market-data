#!/usr/bin/env python3
"""No-key broad crypto-adjacent information discovery for the official CMC100.

Public metadata only, conservative identity tagging, archived first observations.
An open-ended *lead detector*, not a coin forecast or exhaustive internet search.
Only Python standard library; individual requests are audited and failures nonfatal.
"""
from __future__ import annotations
import concurrent.futures
import csv
import datetime as dt
import hashlib
import html
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from email.utils import parsedate_to_datetime

UTC=dt.timezone.utc
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'docs'/'discovery'
USER_AGENT='CMC100-Adjacent-Discovery/1.0 (public research, no credentials)'
MAX_RESPONSE=5_000_000

# Open registry: these are INITIAL SEARCH DIRECTIONS, not a taxonomy of all relevant signals.
THEMES={
 'AI_COMPUTE':('AI agents GPU cloud inference decentralized compute','AI agents inference GPU datacenter infrastructure'),
 'SEMICONDUCTORS':('semiconductor NVIDIA AMD chip supply export restriction','semiconductor foundry AI accelerator supply'),
 'QUANTUM_SECURITY':('quantum computing encryption cryptography post quantum','post quantum cryptography blockchain quantum security'),
 'CYBER_SECURITY':('cybersecurity exploit zero day software supply chain','security vulnerability hack zero day crypto infrastructure'),
 'PAYMENTS':('stablecoin payments merchants cross border settlement','digital payments stablecoin adoption regulation'),
 'TOKENIZATION':('tokenization real world assets bonds settlement','tokenized securities banks custody institutional blockchain'),
 'ENERGY_MINING':('electricity grid datacenters bitcoin mining power','bitcoin miner grid energy AI datacenters'),
 'PRIVACY_ZK':('zero knowledge privacy proof cryptography','ZK cryptography zero knowledge new applications'),
 'AUTONOMOUS_AGENTS':('AI agents digital identity micropayments autonomous','machine to machine payments agents identity'),
 'GAMING_CONSUMERS':('gaming virtual worlds web3 infrastructure adoption','gaming blockchain decentralized user adoption'),
 'MACRO_LIQUIDITY':('dollar yields risk appetite central bank liquidity','interest rates dollar global liquidity risk assets'),
 'REGULATION':('cryptocurrency securities law custody compliance legislation','digital assets court SEC CFTC policy'),
 'EXCHANGE_INFRA':('exchange trading outage crypto custody infrastructure','crypto exchange downtime market structure liquidity'),
 'DEVELOPER_NETWORKS':('developer open source decentralized network protocol','open source protocol vulnerability distributed systems'),
 'ETF_INSTITUTIONAL':('bitcoin ethereum crypto ETF flows institutional','crypto ETF approval redemption institutional allocation'),
 'BIO_IDENTITY':('digital identity privacy biometrics proof of personhood','digital identity decentralized authentication privacy'),
}
# Not a deterministic coin -> theme mapping. Themes are hypotheses needing review.
THEME_WORDS={
 'AI_COMPUTE':r'\b(ai|artificial intelligence|gpu|inference|language model|compute|datacenter|data center)\b',
 'SEMICONDUCTORS':r'\b(semiconductor|chipmaking|foundry|nvidia|amd|semiconductors?|chip supply)\b',
 'QUANTUM_SECURITY':r'\b(quantum|post.quantum|cryptography|lattice.based|encryption)\b',
 'CYBER_SECURITY':r'\b(cyber|exploit|zero.day|vulnerability|hack|breach|malware|security flaw)\b',
 'PAYMENTS':r'\b(payments?|remittance|settlement|stablecoin|cross.border|merchant)\b',
 'TOKENIZATION':r'\b(tokeniz|real.world.asset|rwa|tokenized bond|custody)\b',
 'ENERGY_MINING':r'\b(energy|electricity|power grid|mining|renewable|datacenter power)\b',
 'PRIVACY_ZK':r'\b(zero.knowledge|zk.rollup|privacy|zkp|proof system)\b',
 'AUTONOMOUS_AGENTS':r'\b(ai agents?|autonomous agents?|machine.to.machine|agentic)\b',
 'GAMING_CONSUMERS':r'\b(gaming|gamers|virtual worlds|metaverse|consumer adoption)\b',
 'MACRO_LIQUIDITY':r'\b(inflation|treasury yields?|interest rates?|federal reserve|liquidity|usd|dollar)\b',
 'REGULATION':r'\b(regulation|regulator|court|sec|cftc|legislation|compliance)\b',
 'EXCHANGE_INFRA':r'\b(exchange|outage|latency|custody|market maker|liquidation)\b',
 'DEVELOPER_NETWORKS':r'\b(github|open.source|developer|release|distributed system|consensus)\b',
 'ETF_INSTITUTIONAL':r'\b(etf|institutional|asset manager|blackrock|fund flow)\b',
 'BIO_IDENTITY':r'\b(biometric|identity|proof of personhood|authentication)\b',
}
# Source endpoints only; no brittle unauthorized social-media scraping.
STATIC_FEEDS=[
 ('arxiv_ai','ARXIV','https://rss.arxiv.org/rss/cs.AI'),
 ('arxiv_crypto','ARXIV','https://rss.arxiv.org/rss/cs.CR'),
 ('arxiv_distributed','ARXIV','https://rss.arxiv.org/rss/cs.DC'),
 ('arxiv_ml','ARXIV','https://rss.arxiv.org/rss/cs.LG'),
 ('arxiv_quantum','ARXIV','https://rss.arxiv.org/rss/quant-ph'),
 ('arxiv_econ','ARXIV','https://rss.arxiv.org/rss/econ.GN'),
 ('techcrunch','TECH_NEWS','https://techcrunch.com/feed/'),
 ('ars_technica','TECH_NEWS','https://feeds.arstechnica.com/arstechnica/index'),
 ('mit_tech_review','TECH_NEWS','https://www.technologyreview.com/feed/'),
 ('cloudflare_blog','INFRASTRUCTURE','https://blog.cloudflare.com/rss/'),
 ('cncf_blog','INFRASTRUCTURE','https://www.cncf.io/feed/'),
 ('huggingface_blog','AI_RESEARCH','https://huggingface.co/blog/feed.xml'),
]
# Selected primary-source project release feeds across crypto, security and AI infrastructure.
# NOT an exhaustive mapping of projects to CMC100 tokens. Repo identity is retained.
GITHUB_RELEASE_REPOS=[
 'bitcoin/bitcoin','ethereum/go-ethereum','paradigmxyz/reth',
 'zcash/zcash','lightningnetwork/lnd','libp2p/go-libp2p',
 'pytorch/pytorch','huggingface/transformers','vllm-project/vllm',
 'NVIDIA/TensorRT-LLM','microsoft/quantum','hashicorp/vault',
]
# Short/common tickers are never matched by bare word alone.
AMBIGUOUS={'AI','ONE','PI','SOL','LINK','ATOM','OP','NEAR','IN','ON','CC','M','AMP','GAS','STABLE','SKY','HYPE','NIGHT','LIT','TRUMP','JUP','TAO','W','MOVE','FLOW','POL','GT','APT','SUI','TON','INJ'}
STOPWORDS=set('the this that from with because about their after before into over under when where have more than new how not will may first ever across crypto blockchain bitcoin ethereum technology research open source using people company companies network systems large latest today tomorrow years government model models report news startup users token tokens future fund data world and for now all most some show study could should has had was were are its you your they our there they them being also'.split())


def utcnow():return dt.datetime.now(UTC)
def iso(value):return value.astimezone(UTC).isoformat(timespec='seconds').replace('+00:00','Z')
def parse_time(value):
    if value is None:return None
    try:
        if isinstance(value,(int,float)):
            return dt.datetime.fromtimestamp(value if value<1e11 else value/1000,UTC)
        v=str(value).strip()
        if not v:return None
        if re.fullmatch(r'\d{8}T\d{6}Z',v):return dt.datetime.strptime(v,'%Y%m%dT%H%M%SZ').replace(tzinfo=UTC)
        return dt.datetime.fromisoformat(v.replace('Z','+00:00')).astimezone(UTC)
    except (ValueError,TypeError,OverflowError):
        try:return parsedate_to_datetime(str(value)).astimezone(UTC)
        except (TypeError,ValueError,OverflowError):return None


def url(base,params):return base+'?'+urllib.parse.urlencode(params)
def key_url(u):
    if not isinstance(u,str) or not u.startswith(('http://','https://')):return None
    p=urllib.parse.urlsplit(u)
    if not p.netloc:return None
    return urllib.parse.urlunsplit((p.scheme.lower(),p.netloc.lower(),p.path.rstrip('/'),'', ''))

def clean(text,limit=300):return re.sub(r'\s+',' ',html.unescape(str(text or ''))).strip()[:limit]


class HTTP:
    def __init__(self):self.calls=[]
    def get(self,source,kind,target):
        start=iso(utcnow());attempt_error=None;obj=None
        for attempt in range(2):
            try:
                req=urllib.request.Request(target,headers={'User-Agent':USER_AGENT,'Accept':'application/json, application/xml, text/xml, */*'})
                with urllib.request.urlopen(req,timeout=15) as resp:
                    payload=resp.read(MAX_RESPONSE+1)
                    if len(payload)>MAX_RESPONSE:raise ValueError('PAYLOAD_TOO_LARGE')
                obj=json.loads(payload) if kind=='json' else payload
                break
            except (ValueError,urllib.error.URLError,TimeoutError,OSError,TypeError) as ex:
                attempt_error=type(ex).__name__+': '+str(ex)[:100]
                if isinstance(ex,urllib.error.HTTPError) and ex.code not in (429,500,502,503,504):break
                if attempt==0:time.sleep(.4)
        self.calls.append({'source_id':source,'kind':kind,'url':target,'attempt_started_utc':start,'observed_utc':iso(utcnow()),
                           'transport_status':'OK' if obj is not None else 'ERROR',
                           'error':None if obj is not None else attempt_error})
        return obj


def xml_items(payload,source,observed,limit=35):
    if not isinstance(payload,bytes):return []
    try:root=ET.fromstring(payload)
    except ET.ParseError:return []
    entries=[]
    for element in root.iter():
        if element.tag.rsplit('}',1)[-1] not in ('item','entry'):continue
        fields={};link=None
        for x in list(element):
            k=x.tag.rsplit('}',1)[-1]
            if k=='link':link=link or x.get('href') or (x.text or '').strip()
            if k in ('title','pubDate','published','updated','guid','id'):fields[k]=(x.text or '').strip()
        title=clean(fields.get('title'))
        target=link or fields.get('guid') or fields.get('id')
        when=parse_time(fields.get('published') or fields.get('pubDate') or fields.get('updated'))
        if title and target and str(target).startswith('http'):
            entries.append(dict(title=title,url=target,published_utc=iso(when) if when else None,
                                source_id=source,source_type='RSS',observed_utc=observed))
        if len(entries)>=limit:break
    return entries


def hn_items(obj,source,observed):
    return [{'title':clean(x.get('title')),'url':x.get('url') or 'https://news.ycombinator.com/item?id='+str(x.get('objectID')),
             'published_utc':iso(p) if (p:=parse_time(x.get('created_at') or x.get('created_at_i'))) else None,
             'source_id':source,'source_type':'HN_DISCUSSION','observed_utc':observed,
             'engagement':{'points':x.get('points'),'comments':x.get('num_comments')}} for x in (obj.get('hits') or [])[:35]
            if isinstance(x,dict) and x.get('title')]


def bluesky_items(obj,source,observed):
    ret=[]
    for x in (obj.get('posts') or [])[:40]:
        if not isinstance(x,dict):continue
        record=x.get('record') or {};author=x.get('author') or {}
        text=clean(record.get('text'),320)
        uri=x.get('uri') or '';handle=author.get('handle') or ''
        suffix=uri.rsplit('/',1)[-1]
        target=f'https://bsky.app/profile/{handle}/post/{suffix}' if handle and suffix else None
        if not text or not target:continue
        when=parse_time(record.get('createdAt') or x.get('indexedAt'))
        ret.append({'title':text,'url':target,'published_utc':iso(when) if when else None,
                    'source_id':source,'source_type':'BLUESKY_POST','observed_utc':observed,
                    'engagement':{'likes':x.get('likeCount'),'reposts':x.get('repostCount'),'replies':x.get('replyCount')},
                    'author_handle':handle})
    return ret


def gdelt_items(obj,source,observed):
    ret=[]
    for a in (obj.get('articles') or [])[:65]:
        if not isinstance(a,dict):continue
        target=a.get('url');title=clean(a.get('title'))
        if not title or not target:continue
        when=parse_time(a.get('seendate'))
        ret.append({'title':title,'url':target,'published_utc':iso(when) if when else None,
                    'source_id':source,'source_type':'GDELT_NEWS','observed_utc':observed,
                    'publication_time_basis':'GDELT_SEEN_TIME_NOT_ORIGINAL_PUBLISH_DATE',
                    'source_domain':a.get('domain'),'language':a.get('language')})
    return ret


def github_items(obj,source,observed,limit=16):
    """Only first-party public release/advisory metadata; no commit volume as alpha proxy."""
    if not isinstance(obj,list):return []
    out=[]
    for item in obj[:limit]:
        if not isinstance(item,dict):continue
        title=clean(item.get('name') or item.get('summary') or item.get('tag_name'))
        target=item.get('html_url') or item.get('url')
        if not title or not target:continue
        when=parse_time(item.get('published_at') or item.get('created_at'))
        out.append({'title':title,'url':target,'published_utc':iso(when) if when else None,
                    'source_id':source,'source_type':'GITHUB_RELEASE_OR_ADVISORY','observed_utc':observed,
                    'repo':source.removeprefix('github_releases_') if source.startswith('github_releases_') else None,
                    'severity':item.get('severity') if source=='github_advisories' else None,
                    'publication_time_basis':'GITHUB_PUBLISHED_AT_OR_CREATED_AT'})
    return out


def themes_for(text):
    return sorted([theme for theme,pattern in THEME_WORDS.items() if re.search(pattern,text,re.I)])


def coins_for(text,assets):
    # Candidate mentions only, never interpreted as a catalyst or directional effect.
    hits=[];low=text.casefold()
    for c in assets:
        name=str(c.get('name') or '');symbol=str(c.get('symbol') or '').upper()
        name_match=bool(len(name)>=5 and re.search(r'(?<!\w)'+re.escape(name.casefold())+r'(?!\w)',low))
        cashtag=bool(re.search(r'(?<!\w)\$'+re.escape(symbol)+r'(?!\w)',text,re.I)) if symbol else False
        if name_match or cashtag:hits.append(c['cmc_id'])
    return sorted(set(hits))


def anomaly_coins(market,n=7):
    """Ex-ante *query priorities*, not forecast rankings.

    A high return/funding/volume move triggers more research, with NO claim of future direction.
    """
    weighted=[]
    for c in market.get('assets',[]):
        q=c.get('cmc_quote') or {};p=c.get('perp_market') or {}
        def absnum(v):
            try:return abs(float(v)) if v is not None else 0.
            except (ValueError,TypeError):return 0.
        strength=max(absnum(q.get('ret_1h_pct'))*5,absnum(q.get('ret_24h_pct')),
                     absnum(p.get('perp_ret_6h_pct'))*2,absnum(p.get('estimated_next_funding_rate_fraction'))*2000)
        if q.get('volume_change_24h_pct') is not None:strength=max(strength,absnum(q.get('volume_change_24h_pct'))*.2)
        if strength:weighted.append((strength,int(c['cmc_id']),c))
    return [c for _,__,c in sorted(weighted,key=lambda z:(-z[0],z[1]))[:n]]


def emerging_terms(previous):
    """Cross-source terms are only query leads, never automatic financial explanations."""
    events=(previous or {}).get('events') or []
    domains=defaultdict(set)
    for e in events:
        if not isinstance(e,dict):continue
        src=e.get('source_id','')
        for token in re.findall(r'\b[a-zA-Z][a-zA-Z-]{4,20}\b',(e.get('title') or '').lower()):
            if token not in STOPWORDS and token not in THEMES:domains[token].add(src.split('_')[0])
    terms=[(len(s),t) for t,s in domains.items() if len(s)>=2]
    return [t for _,t in sorted(terms,key=lambda x:(-x[0],x[1]))[:6]]


def plan(market,previous=None):
    specs=[]
    for ident,family,target in STATIC_FEEDS:specs.append((ident,family,'xml',target))
    # Separate discovery channels: technology media, broad news search, developer social posts,
    # specialized technical discussions, worldwide news monitoring. Theme list is extendable.
    for idx,(name,phrases) in enumerate(THEMES.items()):
        q=phrases[0]
        specs.append((f'google_theme_{name}','MULTISECTOR_NEWS','xml',url('https://news.google.com/rss/search',{'q':q+' when:2d','hl':'en-US','gl':'US','ceid':'US:en'})))
        if idx<11:specs.append((f'hn_theme_{name}','DEVELOPER_DISCUSSIONS','json',url('https://hn.algolia.com/api/v1/search_by_date',{'query':phrases[1],'tags':'story','hitsPerPage':'35'})))
        if idx<9:specs.append((f'bluesky_theme_{name}','SOCIAL_DISCUSSIONS','json',url('https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts',{'q':name.replace('_',' ').lower(),'sort':'latest','limit':'35'})))
        if idx<3:specs.append((f'gdelt_theme_{name}','WORLD_NEWS','json',url('https://api.gdeltproject.org/api/v2/doc/doc',{'query':phrases[1],'mode':'ArtList','format':'json','maxrecords':'50','timespan':'2d'})))
    for repo in GITHUB_RELEASE_REPOS:
        specs.append((f'github_releases_{repo.replace("/","__")}','GITHUB_DEVELOPER_RELEASES','json',
                      url(f'https://api.github.com/repos/{repo}/releases',{'per_page':'8'})))
    specs.append(('github_advisories','SOFTWARE_SECURITY_ADVISORIES','json',
                  url('https://api.github.com/advisories',{'per_page':'30','type':'reviewed'})))
    for a in anomaly_coins(market):
        # Proper name, not ticker, to disambiguate. Theme-agnostic follow-up.
        cid=a['cmc_id'];term=a['name']+' crypto'
        specs.append((f'google_coin_{cid}','ANOMALY_DRIVEN','xml',url('https://news.google.com/rss/search',{'q':term+' when:2d','hl':'en-US','gl':'US','ceid':'US:en'})))
    for i,token in enumerate(emerging_terms(previous)):
        specs.append((f'google_emergent_{i}','EMERGENT_TOPIC','xml',url('https://news.google.com/rss/search',{'q':f'"{token}" technology OR crypto when:2d','hl':'en-US','gl':'US','ceid':'US:en'})))
    return specs


def consolidate(market,network,previous=None,cap=500,workers=4):
    assets=market.get('assets') or []
    if len(assets)!=100 or len(set(int(x['cmc_id']) for x in assets))!=100 or market.get('index',{}).get('verified_constituents')!=100:
        raise ValueError('Official CMC100 market snapshot requires 100 unique IDs')
    started=iso(utcnow());specs=plan(market,previous)
    def job(spec):
        ident,family,kind,target=spec
        raw=network.get(ident,kind,target)
        observed=iso(utcnow())
        if kind=='xml':entries=xml_items(raw,ident,observed)
        elif ident.startswith('hn_'):entries=hn_items(raw,ident,observed) if isinstance(raw,dict) else []
        elif ident.startswith('bluesky_'):entries=bluesky_items(raw,ident,observed) if isinstance(raw,dict) else []
        elif ident.startswith('github_'):entries=github_items(raw,ident,observed)
        else:entries=gdelt_items(raw,ident,observed) if isinstance(raw,dict) else []
        return ident,family,entries
    findings=[];parsed=Counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for ident,family,rows in pool.map(job,specs):
            findings.extend(rows);parsed[ident]=len(rows)
    # Restrict to observations genuinely available at capture; unverified publication is marked.
    all_events={};first_seen=(previous or {}).get('first_seen') or {}
    capture_time=parse_time(started)
    future_count=0;missing_date=0
    for e in findings:
        canon=key_url(e.get('url'))
        if canon is None:continue
        when=parse_time(e.get('published_utc'))
        if when and capture_time and when>capture_time+dt.timedelta(minutes=2):future_count+=1;continue
        if not when:missing_date+=1
        event_id=hashlib.sha256(canon.encode()).hexdigest()[:24]
        e['event_id']=event_id;e['title']=clean(e['title'])
        e['publication_time_status']=('GDELT_FIRST_SEEN_NOT_PUBLISHED' if e['source_type']=='GDELT_NEWS' else
                                    'GITHUB_PUBLISHED_OR_CREATED' if e['source_type']=='GITHUB_RELEASE_OR_ADVISORY' else
                                    'VERIFIED_FEED_OR_PLATFORM') if when else 'UNKNOWN'
        e['candidate_coin_ids']=coins_for(e['title'],assets)
        e['theme_leads']=themes_for(e['title'])
        e['direct_price_catalyst_verification']='NOT_VERIFIED'
        e['price_direction']='UNKNOWN'
        e['first_observed_utc']=first_seen.get(event_id) or e['observed_utc']
        if event_id in all_events:
            old=all_events[event_id]
            old['discovered_via']=sorted(set(old['discovered_via']+[e['source_id']]))
            if not old.get('published_utc') and e.get('published_utc'):old['published_utc']=e['published_utc']
        else:
            e['discovered_via']=[e['source_id']];all_events[event_id]=e
    all_sorted=sorted(all_events.values(),key=lambda a:(a['published_utc'] or a['first_observed_utc'],a['event_id']),reverse=True)
    events=all_sorted[:cap]
    first_seen.update({e['event_id']:e['first_observed_utc'] for e in all_sorted})
    coin_counts=Counter(str(cid) for e in events for cid in e['candidate_coin_ids'])
    theme_counts=Counter(t for e in events for t in e['theme_leads'])
    source_rows=[];by_source={c['source_id']:c for c in network.calls}
    for ident,family,kind,target in specs:
        call=by_source.get(ident) or {}
        source_rows.append({'source_id':ident,'family':family,'transport_status':call.get('transport_status','UNOBSERVED'),
                            'valid_leads':parsed[ident],'url':target,'error':call.get('error'),
                            'observed_utc':call.get('observed_utc')})
    statuses={s['source_id']:s for s in source_rows}
    # No fabricated X/Reddit coverage. This is a proper API integration backlog, not a proxy claim.
    gaps=[{'channel':'X_TWITTER','status':'NOT_COLLECTED','reason':'NO_VALIDATED_FREE_OFFICIAL_HIGH_COVERAGE_API'},
          {'channel':'REDDIT','status':'NOT_COLLECTED','reason':'PUBLIC_API_APP_AUTHORIZATION_NEEDED;RSS_RETIRES_2026-11-13'},
          {'channel':'CLOSED_COMMUNITIES','status':'NOT_COLLECTED','reason':'NO_AUTHORIZED_PUBLIC_ACCESS'},
          {'channel':'DIRECT_PROPRIETARY_TECH_SIGNALS','status':'NOT_COLLECTED','reason':'NO_VERIFIED_PUBLIC_BULK_DATA_SOURCE'}]
    status={'capture_started_utc':started,'capture_completed_utc':iso(utcnow()),
            'market_snapshot_completed_utc':market.get('snapshot_completed_utc'),
            'official_cmc100_verified':100,'attempted_source_requests':len(specs),
            'successful_transport':sum(s['transport_status']=='OK' for s in source_rows),
            'sources_returning_leads':sum(s['valid_leads']>0 for s in source_rows),
            'sources_no_valid_leads':[s['source_id'] for s in source_rows if s['valid_leads']==0],
            'raw_leads':len(findings),'unique_leads_before_cap':len(all_sorted),
            'unique_leads_stored':len(events),'leads_with_coin_candidate':sum(bool(e['candidate_coin_ids']) for e in events),
            'unique_coins_with_candidate':len(coin_counts),
            'leads_with_themes':sum(bool(e['theme_leads']) for e in events),
            'theme_lead_counts':dict(theme_counts),
            'future_dated_excluded':future_count,'unverified_publication_dates':missing_date,
            'discovery_limits':['HEADLINES_AND_PUBLIC_POST_EXCERPTS_NOT_FULL_ARTICLE_TEXT',
                                 'THEME_IS_NOT_A_VERIFIED_COIN_CATALYST','COIN_MENTIONS_ARE_UNVERIFIED_CANDIDATES',
                                 'NO_DETERMINISTIC_THEME_TO_COIN_ALPHA_MAPPING','NO_PRICE_FORECASTING',
                                 'MAXIMUM_RECORDS_BOUNDED_TO_CONTROL_GITHUB_SIZE'],
            'access_gaps':gaps,'source_audit':source_rows}
    return {'schema_version':'adjacent-discovery-v1','status':status,'events':events,
            'first_seen':first_seen,'query_plan':[{'source_id':i,'family':f,'kind':k,'url':u} for i,f,k,u in specs],
            'per_coin_candidate_counts':dict(coin_counts)}


def write_bundle(data,out=OUT):
    out.mkdir(parents=True,exist_ok=True)
    for key,name in [('status','status.json')]:
        (out/name).write_text(json.dumps(data[key],ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf8')
    # Provide a compact text-only latest record for connector ingestion, plus JSON audit.
    compact={k:v for k,v in data.items() if k!='first_seen'}
    (out/'latest.json').write_text(json.dumps(compact,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n',encoding='utf8')
    (out/'first_seen.json').write_text(json.dumps(data['first_seen'],ensure_ascii=False,sort_keys=True)+'\n',encoding='utf8')
    columns=['event_id','source_id','source_type','title','url','published_utc','publication_time_status',
             'first_observed_utc','candidate_coin_ids','theme_leads','direct_price_catalyst_verification']
    with (out/'leads.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader()
        for e in data['events']:
            r=dict(e);r['candidate_coin_ids']=';'.join(map(str,r['candidate_coin_ids']))
            r['theme_leads']=';'.join(r['theme_leads']);w.writerow(r)
    ts=(data['status']['capture_started_utc']).replace(':','').replace('-','')
    day=ts[:8];archive=out/'archive'/day/(ts+'_discovery.json')
    archive.parent.mkdir(parents=True,exist_ok=True)
    if archive.exists():raise FileExistsError('Immutable discovery archive already exists: '+str(archive))
    archive.write_text(json.dumps({'status':data['status'],'events':data['events']},ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf8')
    return archive


def main():
    market_path=ROOT/'docs'/'latest.json'
    if not market_path.exists():
        print('No docs/latest.json: market snapshot missing',file=sys.stderr);return 2
    market=json.loads(market_path.read_text(encoding='utf-8'))
    previous={}
    latest=OUT/'latest.json'
    if latest.exists():
        try:previous=json.loads(latest.read_text(encoding='utf8'))
        except (ValueError,OSError):pass
    seen=OUT/'first_seen.json'
    if seen.exists():
        try:previous['first_seen']=json.loads(seen.read_text(encoding='utf8'))
        except (ValueError,OSError):pass
    data=consolidate(market,HTTP(),previous)
    archive=write_bundle(data)
    print(json.dumps({'status':'RECORDED','archive':str(archive),**{k:v for k,v in data['status'].items() if k in ('attempted_source_requests','successful_transport','sources_returning_leads','unique_leads_stored','unique_coins_with_candidate')}},indent=2))
    # Partial sources are not a failure; audit always makes them visible.
    return 0

if __name__=='__main__':raise SystemExit(main())