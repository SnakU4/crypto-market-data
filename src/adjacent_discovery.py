#!/usr/bin/env python3
"""No-key broad crypto-adjacent information discovery for the official CMC100.

Public research metadata and provider-supplied excerpts; no coin/sector-to-price mapping.
Preserve all unique observed leads in an immutable PIT archive. Publish a diversified
read index for the later AI investigation. Not a coin forecast or exhaustive search.
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
INDEX_CAP=500  # Bounds the AI read index; NEVER truncates the immutable full run archive.

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
    # Preserve meaningful article identifiers (?id=123, ?p=123). Only strip tracking.
    tracking={'fbclid','gclid','ref','ref_src','tracking','mc_cid','mc_eid','igshid'}
    params=[(k,v) for k,v in urllib.parse.parse_qsl(p.query,keep_blank_values=True)
            if not k.lower().startswith('utm_') and k.lower() not in tracking]
    return urllib.parse.urlunsplit((p.scheme.lower(),p.netloc.lower(),p.path.rstrip('/'),
                                    urllib.parse.urlencode(sorted(params)),''))

def clean(text,limit=300):return re.sub(r'\s+',' ',html.unescape(str(text or ''))).strip()[:limit]


def excerpt(text,limit=400):
    """Small provider-distributed description/abstract, not copied article text."""
    raw=html.unescape(str(text or ''))
    raw=re.sub(r'<(?:script|style)\b[^>]*>.*?</(?:script|style)\s*>',' ',raw,flags=re.I|re.S)
    raw=re.sub(r'<[^>]+>',' ',raw)
    return clean(raw,limit)


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
            if k in ('title','pubDate','published','updated','guid','id','description','summary','subtitle'):
                fields[k]=(x.text or '').strip()
        title=clean(fields.get('title'))
        target=link or fields.get('guid') or fields.get('id')
        when=parse_time(fields.get('published') or fields.get('pubDate') or fields.get('updated'))
        if title and target and str(target).startswith('http'):
            # Only RSS/Atom excerpts explicitly supplied by the publisher.
            abstract=fields.get('summary') or fields.get('description') or fields.get('subtitle')
            max_len=650 if source.startswith('arxiv_') else 360
            entries.append(dict(title=title,url=target,published_utc=iso(when) if when else None,
                                excerpt=excerpt(abstract,max_len),context_origin='PUBLISHER_FEED_EXCERPT' if abstract else 'TITLE_ONLY',
                                source_id=source,source_type='RSS',observed_utc=observed))
        if len(entries)>=limit:break
    return entries

def hn_items(obj,source,observed):
    return [{'title':clean(x.get('title')),
             'url':x.get('url') or 'https://news.ycombinator.com/item?id='+str(x.get('objectID')),
             'discussion_url':'https://news.ycombinator.com/item?id='+str(x.get('objectID')),
             'published_utc':iso(p) if (p:=parse_time(x.get('created_at') or x.get('created_at_i'))) else None,
             'source_id':source,'source_type':'HN_DISCUSSION','observed_utc':observed,
             'excerpt':excerpt(x.get('story_text') or '',400),
             'context_origin':'HN_SUBMITTED_STORY_TEXT' if x.get('story_text') else 'TITLE_ONLY',
             'engagement':{'points':x.get('points'),'comments':x.get('num_comments')}}
            for x in (obj.get('hits') or [])[:35] if isinstance(x,dict) and x.get('title')]

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
                    'author_handle':handle,'context_origin':'PUBLIC_POST_TEXT'})
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
                    'source_domain':a.get('domain'),'language':a.get('language'),
                    'context_origin':'TITLE_ONLY'})
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
                    'publication_time_basis':'GITHUB_PUBLISHED_AT_OR_CREATED_AT',
                    'excerpt':excerpt(item.get('body') or item.get('description'),520),
                    'context_origin':'GITHUB_AUTHOR_SUPPLIED_RELEASE_OR_ADVISORY' if (item.get('body') or item.get('description')) else 'TITLE_ONLY'})
    return out


def themes_for(text):
    return sorted([theme for theme,pattern in THEME_WORDS.items() if re.search(pattern,text,re.I)])


# Intentionally NO coin matching at collection time. Relevance and exposures are
# hypotheses for a later AI investigation; even a headline without a ticker may
# matter. CMC IDs are retained only in the separate market snapshot and in
# anomaly-triggered search provenance, not used for selection or evidence scoring.

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
    hn_cutoff_unix=int((utcnow()-dt.timedelta(days=7)).timestamp())
    for idx,(name,phrases) in enumerate(THEMES.items()):
        q=phrases[0]
        specs.append((f'google_theme_{name}','MULTISECTOR_NEWS','xml',url('https://news.google.com/rss/search',{'q':q+' when:2d','hl':'en-US','gl':'US','ceid':'US:en'})))
        if idx<11:specs.append((f'hn_theme_{name}','DEVELOPER_DISCUSSIONS','json',url('https://hn.algolia.com/api/v1/search_by_date',{'query':phrases[1],'tags':'story','hitsPerPage':'35','numericFilters':f'created_at_i>{hn_cutoff_unix}'})))
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


def balanced_index(all_events, source_families, cap=INDEX_CAP):
    """Round-robin families AND sources; never use coin mentions or themes.

    All source-derived events remain in the full immutable archive regardless
    of this compact connector read index. Within each source, newest first.
    """
    if cap is None or cap<0:raise ValueError('cap must be nonnegative or None')
    if cap==0:return []
    by_family=defaultdict(lambda:defaultdict(list))
    for item in all_events:
        family=source_families.get(item['source_id'],'OTHER')
        by_family[family][item['source_id']].append(item)
    # Round-robin sources within family. Round-robin families across the whole index.
    family_cursors={}
    for fam,sources in by_family.items():
        for v in sources.values():
            v.sort(key=lambda a:(a.get('published_utc') or a.get('first_observed_utc') or '',a['event_id']),reverse=True)
        family_cursors[fam]={'names':sorted(sources),'positions':{key:0 for key in sources},'rotation':0}
    selected=[];added=set()
    families=sorted(by_family)
    while len(selected)<cap:
        advanced=False
        for fam in families:
            cursor=family_cursors[fam];names=cursor['names']
            if not names:continue
            # Each visit picks one result from the next source with remaining entries.
            for shift in range(len(names)):
                idx=(cursor['rotation']+shift)%len(names);name=names[idx]
                rows=by_family[fam][name];pos=cursor['positions'][name]
                if pos>=len(rows):continue
                cursor['positions'][name]+=1;cursor['rotation']=(idx+1)%len(names)
                item=rows[pos]
                if item['event_id'] not in added:
                    selected.append(item);added.add(item['event_id'])
                    advanced=True
                break
            if len(selected)>=cap:break
        if not advanced:break
    return selected


def consolidate(market,network,previous=None,cap=INDEX_CAP,workers=4):
    assets=market.get('assets') or []
    if len(assets)!=100 or len(set(int(x['cmc_id']) for x in assets))!=100 or market.get('index',{}).get('verified_constituents')!=100:
        raise ValueError('Official CMC100 market snapshot requires 100 unique IDs')
    started=iso(utcnow());specs=plan(market,previous)
    source_families={ident:family for ident,family,kind,target in specs}
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
        e['source_family']=source_families.get(e['source_id'],'OTHER')
        e['publication_time_status']=('GDELT_FIRST_SEEN_NOT_PUBLISHED' if e['source_type']=='GDELT_NEWS' else
                                    'GITHUB_PUBLISHED_OR_CREATED' if e['source_type']=='GITHUB_RELEASE_OR_ADVISORY' else
                                    'VERIFIED_FEED_OR_PLATFORM') if when else 'UNKNOWN'
        # Theme labels are optional search navigation; they never exclude or rank a lead.
        e['theme_leads']=themes_for(e['title']+' '+e.get('excerpt',''))
        e['coin_relevance_status']='NOT_ASSESSED_BY_COLLECTOR'
        e['first_observed_utc']=first_seen.get(event_id) or e['observed_utc']
        if event_id in all_events:
            old=all_events[event_id]
            old['discovered_via']=sorted(set(old['discovered_via']+[e['source_id']]))
            if not old.get('published_utc') and e.get('published_utc'):old['published_utc']=e['published_utc']
        else:
            e['discovered_via']=[e['source_id']];all_events[event_id]=e
    all_sorted=sorted(all_events.values(),key=lambda a:(a['published_utc'] or a['first_observed_utc'],a['event_id']),reverse=True)
    # Archive ALL deduplicated eligible leads; only the connector index is bounded.
    # Keep historical evidence in the full archive, never surface stale stories as
    # current 24h catalysts simply to fill the balanced connector index.
    cutoff_for_index=capture_time-dt.timedelta(days=7)
    fresh_for_index=[e for e in all_sorted if (parse_time(e.get('published_utc')) or parse_time(e['first_observed_utc']))>=cutoff_for_index]
    events=balanced_index(fresh_for_index,source_families,cap)
    first_seen.update({e['event_id']:e['first_observed_utc'] for e in all_sorted})
    theme_counts=Counter(t for e in events for t in e['theme_leads'])
    family_full=Counter(source_families.get(e['source_id'],'OTHER') for e in all_sorted)
    family_index=Counter(source_families.get(e['source_id'],'OTHER') for e in events)
    source_full=Counter(e['source_id'] for e in all_sorted)
    source_index=Counter(e['source_id'] for e in events)
    source_rows=[];by_source={c['source_id']:c for c in network.calls}
    for ident,family,kind,target in specs:
        call=by_source.get(ident) or {}
        source_rows.append({'source_id':ident,'family':family,'transport_status':call.get('transport_status','UNOBSERVED'),
                            'valid_leads':parsed[ident],'url':target,'error':call.get('error'),
                            'observed_utc':call.get('observed_utc')})
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
            'unique_leads_stored':len(events), # LEGACY: index count, not full archive size
            'full_archive_leads':len(all_sorted),'read_index_leads':len(events),
            'read_index_capacity':cap,'read_index_selection':'FAMILY_AND_SOURCE_BALANCED_RECENT_7D_NO_COIN_MATCH',
            'index_older_than_7d_excluded':len(all_sorted)-len(fresh_for_index),'index_max_age_days':7,
            'coin_matching_performed':False,
            'read_index_source_counts':dict(source_index),'full_archive_source_counts':dict(source_full),
            'read_index_family_counts':dict(family_index),'full_archive_family_counts':dict(family_full),
            'full_archive_excerpts_available':sum(bool(e.get('excerpt')) for e in all_sorted),
            'read_index_excerpts_available':sum(bool(e.get('excerpt')) for e in events),
            'leads_with_themes':sum(bool(e['theme_leads']) for e in events),
            'theme_lead_counts':dict(theme_counts),
            'future_dated_excluded':future_count,'unverified_publication_dates':missing_date,
            'discovery_limits':['PROVIDER_DISTRIBUTED_EXCERPTS_NOT_FULL_ARTICLES',
                                 'THEMES_ARE_NAVIGATION_NOT_PRIORITIZATION','NO_COIN_ENTITY_LINKING',
                                 'NO_PREDICTION','FINITE_PER_SOURCE_API_REQUEST_RESULTS',
                                 'NO_FULL_INTERNET_COVERAGE','ARCHIVE_GIT_SIZE_MUST_BE_MONITORED'],
            'access_gaps':gaps,'source_audit':source_rows}
    return {'schema_version':'adjacent-discovery-v2','status':status,'events':events,
            'all_events':all_sorted,'first_seen':first_seen,
            'query_plan':[{'source_id':i,'family':f,'kind':k,'url':u} for i,f,k,u in specs]}


def write_bundle(data,out=OUT):
    out.mkdir(parents=True,exist_ok=True)
    ts=data['status']['capture_started_utc'].replace(':','').replace('-','')
    day=ts[:8];archive=out/'archive'/day/(ts+'_discovery.json')
    archive.parent.mkdir(parents=True,exist_ok=True)
    if archive.exists():raise FileExistsError('Immutable discovery archive already exists: '+str(archive))
    full=data['all_events']
    data['status']['full_archive_path']=archive.relative_to(ROOT).as_posix() if archive.is_relative_to(ROOT) else str(archive)
    archive_payload={'schema_version':data['schema_version'], 'status':data['status'],
                     'events':full,'query_plan':data['query_plan']}
    archive.write_text(json.dumps(archive_payload,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n',encoding='utf8')
    # The index is a connector-friendly selection. The full archive is never capped.
    (out/'status.json').write_text(json.dumps(data['status'],ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf8')
    compact={k:v for k,v in data.items() if k not in ('first_seen','all_events')}
    (out/'latest.json').write_text(json.dumps(compact,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n',encoding='utf8')
    (out/'first_seen.json').write_text(json.dumps(data['first_seen'],ensure_ascii=False,sort_keys=True)+'\n',encoding='utf8')
    columns=['event_id','source_id','source_family','source_type','title','excerpt','context_origin','url','published_utc',
             'publication_time_status','first_observed_utc','discovered_via','theme_leads','coin_relevance_status']
    def store_csv(path,rows):
        with path.open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader()
            for e in rows:
                r=dict(e);r['theme_leads']=';'.join(r['theme_leads'])
                r['discovered_via']=';'.join(r.get('discovered_via') or [])
                w.writerow(r)
    store_csv(out/'leads.csv',full)
    store_csv(out/'read_index.csv',data['events'])
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
    print(json.dumps({'status':'RECORDED','archive':str(archive),**{k:v for k,v in data['status'].items() if k in ('attempted_source_requests','successful_transport','sources_returning_leads','read_index_leads','full_archive_leads','coin_matching_performed')}},indent=2))
    # Partial sources are not a failure; audit always makes them visible.
    return 0

if __name__=='__main__':raise SystemExit(main())