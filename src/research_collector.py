#!/usr/bin/env python3
"""Wide, low-cost public research collector for official CMC100 assets.

Research *observations*, never predictions. Does not claim that matching a protocol
or a headline to a token proves a causal token-price effect. Stdlib, no API keys.
Data is saved in docs/research, separate from the established spot/perp collector.
"""
from __future__ import annotations
import argparse
import concurrent.futures as cf
import csv
import datetime as dt
import email.utils
import hashlib
import html
import io
import json
import math
import pathlib
import re
import statistics
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from typing import Any

UTC=dt.timezone.utc
ROOT=pathlib.Path(__file__).resolve().parents[1]
DOCS=ROOT/'docs'
OUT=DOCS/'research'
UA='CMC100-Research-Observatory/1.0 (public/free sources; GitHub repo SnakU4/crypto-market-data)'
MAX_BYTES=16_000_000

# Add public sources here. The source register is deliberately open-ended; it is
# NOT a list of all possible alpha-bearing information on the Internet.
SOURCE_CATALOG=[
    ('llama_protocols','DEFI_PROTOCOL_TVL','json','https://api.llama.fi/protocols'),
    ('llama_chains','ONCHAIN_CHAIN_TVL','json','https://api.llama.fi/v2/chains'),
    ('llama_fees','PROTOCOL_FEES','json','https://api.llama.fi/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true&dataType=dailyFees'),
    ('llama_revenue','PROTOCOL_REVENUE','json','https://api.llama.fi/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true&dataType=dailyRevenue'),
    ('llama_holder_revenue','TOKEN_VALUE_ACCRUAL','json','https://api.llama.fi/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true&dataType=dailyHoldersRevenue'),
    ('llama_dex','DEX_VOLUME','json','https://api.llama.fi/overview/dexs?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true'),
    ('llama_options','OPTIONS_ACTIVITY','json','https://api.llama.fi/overview/options?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true'),
    ('llama_perp_oi','DECENTRALIZED_PERP_OI','json','https://api.llama.fi/overview/open-interest?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true'),
    ('llama_stablecoin_supply','STABLECOIN_SUPPLY','json','https://stablecoins.llama.fi/stablecoincharts/all'),
    ('llama_stablecoin_chains','STABLECOIN_CHAIN_SUPPLY','json','https://stablecoins.llama.fi/stablecoinchains'),
    ('coingecko_trending','SOCIAL_ATTENTION','json','https://api.coingecko.com/api/v3/search/trending'),
    ('alternative_fng','MARKET_SENTIMENT','json','https://api.alternative.me/fng/?limit=2'),
    ('coindesk','CRYPTO_NEWS','rss','https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml'),
    ('theblock','CRYPTO_NEWS','rss','https://www.theblock.co/rss.xml'),
    ('cointelegraph','CRYPTO_NEWS','rss','https://cointelegraph.com/rss'),
    ('decrypt','CRYPTO_NEWS','rss','https://decrypt.co/feed'),
    ('dlnews','CRYPTO_NEWS','rss','https://www.dlnews.com/arc/outboundfeeds/rss/'),
    ('defiant','DEFI_NEWS','rss','https://thedefiant.io/feed/'),
    ('bitcoinmag','CRYPTO_NEWS','rss','https://bitcoinmagazine.com/feed'),
    ('cryptoslate','CRYPTO_NEWS','rss','https://cryptoslate.com/feed/'),
    ('protos','CRYPTO_NEWS','rss','https://protos.com/feed'),
    ('sec','REGULATION_EVENTS','rss','https://www.sec.gov/news/pressreleases.rss'),
    ('fed_press','MACRO_POLICY_EVENTS','rss','https://www.federalreserve.gov/feeds/press_all.xml'),
    ('fed_monetary','MONETARY_POLICY_EVENTS','rss','https://www.federalreserve.gov/feeds/press_monetary.xml'),
    ('bls_jobs','MACRO_DATA_RELEASES','rss','https://www.bls.gov/feed/empsit.rss'),
    ('bls_cpi','MACRO_DATA_RELEASES','rss','https://www.bls.gov/feed/cpi.rss'),
    ('rekt_security','SECURITY_INCIDENTS','rss','https://rekt.news/rss.xml'),
    ('ethereum_blog','PROTOCOL_UPGRADE_EVENTS','rss','https://blog.ethereum.org/feed.xml'),
    ('solana_blog','PROTOCOL_UPGRADE_EVENTS','rss','https://solana.com/news/rss.xml'),
    ('coinbase_blog','EXCHANGE_LISTINGS_EVENTS','rss','https://www.coinbase.com/blog/rss.xml'),
    # PRIMARY-SOURCE FIRST: independently query project release notes, open
    # governance forums and central-bank communications instead of relying on
    # thousands of syndicated Google News headlines. Availability is audited:
    # an inaccessible feed never becomes a fabricated source.
    ('ecb_press','MACRO_POLICY_EVENTS','rss','https://www.ecb.europa.eu/rss/press.html'),
    ('btc_core_releases','PRIMARY_PROTOCOL_RELEASE','rss','https://github.com/bitcoin/bitcoin/releases.atom'),
    ('eth_geth_releases','PRIMARY_PROTOCOL_RELEASE','rss','https://github.com/ethereum/go-ethereum/releases.atom'),
    ('eth_consensus_releases','PRIMARY_PROTOCOL_RELEASE','rss','https://github.com/ethereum/consensus-specs/releases.atom'),
    ('sol_agave_releases','PRIMARY_PROTOCOL_RELEASE','rss','https://github.com/anza-xyz/agave/releases.atom'),
    ('sui_releases','PRIMARY_PROTOCOL_RELEASE','rss','https://github.com/MystenLabs/sui/releases.atom'),
    ('aptos_releases','PRIMARY_PROTOCOL_RELEASE','rss','https://github.com/aptos-labs/aptos-core/releases.atom'),
    ('avax_releases','PRIMARY_PROTOCOL_RELEASE','rss','https://github.com/ava-labs/avalanchego/releases.atom'),
    ('near_releases','PRIMARY_PROTOCOL_RELEASE','rss','https://github.com/near/nearcore/releases.atom'),
    ('polkadot_releases','PRIMARY_PROTOCOL_RELEASE','rss','https://github.com/paritytech/polkadot-sdk/releases.atom'),
    ('cosmos_releases','PRIMARY_PROTOCOL_RELEASE','rss','https://github.com/cosmos/gaia/releases.atom'),
    ('arbitrum_releases','PRIMARY_PROTOCOL_RELEASE','rss','https://github.com/OffchainLabs/nitro/releases.atom'),
    ('optimism_releases','PRIMARY_PROTOCOL_RELEASE','rss','https://github.com/ethereum-optimism/optimism/releases.atom'),
    ('aave_v3_releases','PRIMARY_PROTOCOL_RELEASE','rss','https://github.com/aave/aave-v3-core/releases.atom'),
    ('uniswap_v4_releases','PRIMARY_PROTOCOL_RELEASE','rss','https://github.com/Uniswap/v4-core/releases.atom'),
    ('chainlink_releases','PRIMARY_PROTOCOL_RELEASE','rss','https://github.com/smartcontractkit/chainlink/releases.atom'),
    ('zksync_releases','PRIMARY_PROTOCOL_RELEASE','rss','https://github.com/matter-labs/zksync-era/releases.atom'),
    ('stellar_releases','PRIMARY_PROTOCOL_RELEASE','rss','https://github.com/stellar/stellar-core/releases.atom'),
    ('xrp_releases','PRIMARY_PROTOCOL_RELEASE','rss','https://github.com/XRPLF/rippled/releases.atom'),
    ('doge_releases','PRIMARY_PROTOCOL_RELEASE','rss','https://github.com/dogecoin/dogecoin/releases.atom'),
    ('lightning_releases','NETWORK_INFRA_RELEASE','rss','https://github.com/lightningnetwork/lnd/releases.atom'),
    ('aave_governance','PRIMARY_GOVERNANCE','rss','https://governance.aave.com/latest.rss'),
    ('cosmos_governance','PRIMARY_GOVERNANCE','rss','https://forum.cosmos.network/latest.rss'),
    ('polkadot_governance','PRIMARY_GOVERNANCE','rss','https://forum.polkadot.network/latest.rss'),
    ('zcash_governance','PRIMARY_GOVERNANCE','rss','https://forum.zcashcommunity.com/latest.rss'),
    ('ethereum_governance','PRIMARY_GOVERNANCE','rss','https://ethereum-magicians.org/latest.rss'),
]

# Categories are data provenance labels; they do not establish that an event is true.
EVENT_TERMS={
    'TOKEN_UNLOCK':r'\b(unlock|vesting|token release|cliff|airdrops?)\b',
    'TOKEN_SUPPLY':r'\b(issuance|mint(?:ed|ing)?|burn(?:ed|ing)?|emission|buyback|supply|inflation)\b',
    'LISTING_DELISTING':r'\b(listed|listing|delisting|delisted|exchange support)\b',
    'SECURITY':r'\b(exploit|hack(?:ed)?|attack|breach|drain(?:ed)?|vulnerability|compromised)\b',
    'GOVERNANCE':r'\b(governance|vote|proposal|dao vote|referendum)\b',
    'UPGRADE':r'\b(hard fork|upgrade|mainnet|testnet|network launch|release|rollout)\b',
    'REGULATION':r'\b(sec\b|cftc|regulat|lawsuit|court|etf|approval|no.action)\b',
    'INSTITUTIONAL_FLOW':r'\b(etf|fund inflow|fund outflow|institutional|treasury|custody)\b',
    'DEFI_ACTIVITY':r'\b(tvl|dex|defi|on.chain|liquid stak|staking|fees|revenue|bridge)\b',
    'DERIVATIVES':r'\b(open interest|funding|liquidat|perpetual|futures|short squeeze|leverage)\b',
    'MACRO':r'\b(cpi|payroll|inflation|fed|fomc|interest.rate|tariff|dollar|yields)\b',
    'LEGAL_CORPORATE':r'\b(partnership|acquisition|bankruptcy|insolven|settlement|merger)\b',
}
# Short, generic tickers need explicit $TICKER notation or full-name phrases.
AMBIGUOUS={'M','CC','PI','FF','OP','SOL','NEAR','LIT','NIGHT','SKY','TRUMP','STABLE','SUN','BEAM','LINK','ONE','ATOM','GT','POL','FLR','INJ'}


def now():
    return dt.datetime.now(UTC).isoformat(timespec='seconds').replace('+00:00','Z')


def parse_utc(x):
    if not x:return None
    if isinstance(x,(int,float)):
        try:return dt.datetime.fromtimestamp(x/1000 if x>1e11 else x,UTC)
        except (ValueError,OverflowError):return None
    if isinstance(x,str):
        if x.isdigit() and len(x) in (10,13):return parse_utc(int(x))
        try:return dt.datetime.fromisoformat(x.replace('Z','+00:00')).astimezone(UTC)
        except ValueError:
            try:return email.utils.parsedate_to_datetime(x).astimezone(UTC)
            except (TypeError,ValueError,IndexError):return None
    return None


def iso(x):return x.astimezone(UTC).isoformat(timespec='seconds').replace('+00:00','Z') if x else None


def number(x):
    if x is None or isinstance(x,bool):return None
    try:
        z=float(x)
        return z if math.isfinite(z) else None
    except (ValueError,TypeError,OverflowError):return None


def rnd(x,places=6):
    z=number(x)
    return round(z,places) if z is not None else None


def normalize_name(s):
    s=unicodedata.normalize('NFKC',str(s or '')).casefold()
    return ' '.join(re.findall(r'[\w]+',s))


def dollars(x):
    if isinstance(x,dict):
        for k in ('peggedUSD','total','usd','USD'):
            if k in x and number(x[k]) is not None:return number(x[k])
        return None
    return number(x)


def rate(end,start):
    a,b=number(end),number(start)
    return round((a/b-1)*100,6) if a is not None and b is not None and b>0 else None


class Network:
    def __init__(self):self.calls=[]
    def get(self,name,kind,url):
        started=now();err=None;status='ERROR';result=None
        for i in range(2):
            try:
                req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json,application/rss+xml,application/xml,text/xml,*/*'})
                with urllib.request.urlopen(req,timeout=20) as resp:
                    content=resp.read(MAX_BYTES+1)
                    if len(content)>MAX_BYTES:raise ValueError('response >16 MB')
                result=json.loads(content) if kind=='json' else content
                status='OK';err=None;break
            except urllib.error.HTTPError as ex:
                err='HTTP '+str(ex.code)
                if ex.code not in (429,500,502,503,504):break
            except Exception as ex:err=type(ex).__name__+': '+str(ex)[:100]
            if i==0:time.sleep(.5)
        rec={'source_id':name,'source_type':kind,'url':url,'started_utc':started,'observed_utc':now(),'status':status,'error':err}
        # Transport success is not evidence that the payload had usable values or a verified CMC match.
        if status=='OK' and kind=='json':
            rec['response_shape']='object' if isinstance(result,dict) else 'array' if isinstance(result,list) else type(result).__name__
            if isinstance(result,dict):
                rec['response_top_level_keys']=sorted(str(k) for k in result)[:30]
                if 'protocols' in result:
                    records=result['protocols']
                    rec['response_protocol_records']=len(records) if isinstance(records,(list,dict)) else None
            elif isinstance(result,list):rec['response_records']=len(result)
        self.calls.append(rec)
        return result


def parse_feed(body,source,observed,limit=40):
    try:root=ET.fromstring(body)
    except (ET.ParseError,TypeError):return []
    # RSS and Atom; namespace-neutral selectors.
    tags=lambda e:{ch.tag.split('}')[-1]:ch for ch in e}
    candidates=[e for e in root.iter() if e.tag.split('}')[-1] in ('item','entry')]
    out=[]
    for item in candidates[:limit]:
        children=tags(item)
        title=''.join(children.get('title',ET.Element('title')).itertext()).strip()
        title=re.sub(r'\s+',' ',html.unescape(title))[:280]
        link=children.get('link')
        url=link.attrib.get('href') if link is not None else None
        if link is not None and not url:url=(link.text or '').strip()
        url=(url or '').strip()
        if not (url.startswith('https://') or url.startswith('http://')) or not title:continue
        published=None
        for label in ('pubDate','published','updated','date'):
            if label in children:
                published=parse_utc((children[label].text or '').strip())
                if published:break
        obs=parse_utc(observed)
        if published and obs and published>obs+dt.timedelta(minutes=3):continue
        # Preserve provider-published summaries instead of discarding them.
        # RSS content:encoded, Atom content/summary and HTML descriptions
        # are treated as source snippets, NOT independently verified claims.
        raw_summary=''
        for label in ('encoded','content','summary','description','subtitle'):
            node=children.get(label)
            if node is None:continue
            value=''.join(node.itertext()).strip()
            if len(value)>len(raw_summary):raw_summary=value
        summary=re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',raw_summary))).strip()[:1300]
        if len(summary)<35:summary=''
        # A feed item with unknown publication time is saved only as unverified.
        item_id=hashlib.sha256((url.split('?')[0].lower()).encode()).hexdigest()[:24]
        out.append({'event_id':item_id,'source_id':source,'headline':title,'url':url,
                    'excerpt':summary,'context_origin':'PUBLISHER_FEED_SUMMARY' if summary else 'TITLE_ONLY',
                    'published_utc':iso(published),'published_time_status':'VERIFIED_FEED_DATE' if published else 'UNKNOWN',
                    'observed_utc':observed})
    return out


def match_asset(headline,coins):
    """Only candidate mention tags, not verified relevance. Suppress common-word tickers."""
    ids=set();methods={}
    text=unicodedata.normalize('NFKC',headline)
    low=text.casefold()
    for c in coins:
        name=c['name'];symbol=c['symbol'];cid=int(c['cmc_id'])
        full=normalize_name(name)
        norm_text=normalize_name(text)
        # Names shorter than 5 chars often collide with generic text.
        matched_name=(len(full)>=5 and name.upper() not in AMBIGUOUS and re.search(r'(?<!\w)'+re.escape(full)+r'(?!\w)',norm_text) is not None)
        matched_cash=(re.search(r'(?<!\w)\$'+re.escape(symbol)+r'(?!\w)',text,re.I) is not None)
        matched_symbol=(len(symbol)>=4 and symbol.upper() not in AMBIGUOUS and
                        re.search(r'(?<!\w)'+re.escape(symbol)+r'(?!\w)',text,re.I) is not None)
        if matched_name or matched_cash or matched_symbol:
            ids.add(cid);methods[str(cid)]='FULL_NAME' if matched_name else ('DOLLAR_TICKER' if matched_cash else 'UNAMBIGUOUS_TICKER_CANDIDATE')
    return sorted(ids),methods


def label_event(e,coins):
    text=e['headline'].lower()
    e['event_classes']=sorted(k for k,pat in EVENT_TERMS.items() if re.search(pat,text,re.I)) or ['GENERAL_NEWS']
    e['cmc_ids'],e['match_methods']=match_asset(e['headline'],coins)
    e['coin_tags_are_verified_catalysts']=False
    return e


def build_match_index(coins,items,strict_symbol=True):
    """Explicit CMC ID > exact name+symbol, never loose ticker match.
    Duplicate or conflicting provider mappings are not mapped to an asset.
    """
    per_id=defaultdict(list);named=defaultdict(list)
    by_id={int(c['cmc_id']):c for c in coins}
    for entry in items:
        if not isinstance(entry,dict):continue
        name=normalize_name(entry.get('name') or entry.get('displayName'))
        symbol=str(entry.get('symbol') or '').upper()
        cid=entry.get('cmcId') or entry.get('cmc_id')
        try:cid=int(cid)
        except (ValueError,TypeError):cid=None
        if cid in by_id:
            if name and symbol and (normalize_name(by_id[cid]['name'])!=name or by_id[cid]['symbol'].upper()!=symbol):
                continue
            per_id[cid].append((entry,'EXPLICIT_CMC_ID'))
        elif name and symbol:
            named[(name,symbol)].append(entry)
    for cid,coin in by_id.items():
        if cid not in per_id:
            key=(normalize_name(coin['name']),coin['symbol'].upper())
            if len(named[key])==1:per_id[cid]=[(named[key][0],'EXACT_NAME_AND_SYMBOL')]
    return {cid:v[0] for cid,v in per_id.items() if len(v)==1}


def protocols_rows(raw,coins):
    if not isinstance(raw,list):return [],{}
    matches=build_match_index(coins,raw)
    rows=[]
    for cid,(p,match) in matches.items():
        rows.append({'cmc_id':cid,'protocol_id':p.get('id'),'protocol_slug':p.get('slug'),
                     'protocol_name':p.get('name'),'mapping_confidence':match,
                     'chain_count':len(p.get('chains') or []),'protocol_tvl_usd':rnd(p.get('tvl'),2),
                     'protocol_tvl_change_1d_pct':rnd(p.get('change_1d')),
                     'protocol_tvl_change_7d_pct':rnd(p.get('change_7d')),
                     'interpretation':'PROTOCOL_ACTIVITY_NOT_TOKEN_PRICE_OR_VALUE_ACCRUAL'})
    return rows,matches


def chain_rows(raw,coins):
    if not isinstance(raw,list):return []
    by_name={normalize_name(c['name']):c for c in coins}
    duplicate=Counter(normalize_name(x.get('name','')) for x in raw if isinstance(x,dict))
    result=[]
    for x in raw:
        if not isinstance(x,dict):continue
        key=normalize_name(x.get('name'))
        if duplicate[key]!=1:continue
        c=by_name.get(key)
        if not c:continue
        result.append({'cmc_id':c['cmc_id'],'chain':x.get('name'),'chain_tvl_usd':rnd(x.get('tvl'),2),
                      'mapping_confidence':'EXACT_CHAIN_NAME',
                      'interpretation':'CHAIN_ACTIVITY_NOT_TOKEN_VALUE_ACCRUAL'})
    return result


def protocol_metric_rows(raw,coins,metric):
    items=raw.get('protocols',[]) if isinstance(raw,dict) else []
    if isinstance(items,dict):items=list(items.values())
    if not isinstance(items,list):return []
    mapped=build_match_index(coins,items)
    records=[]
    for cid,(v,typ) in mapped.items():
        records.append({'cmc_id':cid,'protocol_name':v.get('name'),'metric':metric,
                        'total24h_usd':rnd(v.get('total24h'),2),'prior24h_usd':rnd(v.get('total48hto24h'),2),
                        'total7d_usd':rnd(v.get('total7d'),2),'mapping_confidence':typ,
                        'interpretation':'PROTOCOL_METRIC_NOT_UNCONDITIONAL_TOKEN_ACCRUAL'})
    return records


def stablecoin_global(raw,captured):
    if not isinstance(raw,list):return {'status':'UNAVAILABLE','reason':'MALFORMED_SOURCE'}
    points=[]
    for p in raw:
        if not isinstance(p,dict):continue
        tm=parse_utc(p.get('date'))
        val=dollars(p.get('totalCirculatingUSD')) or dollars(p.get('totalCirculating'))
        if tm and val is not None and (parse_utc(captured) is None or tm<=parse_utc(captured)):
            points.append((tm,val))
    points.sort()
    if not points:return {'status':'UNAVAILABLE','reason':'NO_VALID_OBSERVATIONS'}
    last,v=points[-1];res={'status':'AVAILABLE','last_data_utc':iso(last),'circulating_usd':round(v,2),'change_1d_pct':None,'change_7d_pct':None}
    for days,key in ((1,'change_1d_pct'),(7,'change_7d_pct')):
        target=last-dt.timedelta(days=days)
        matches=[x for x in points if abs((x[0]-target).total_seconds())<=24*3600/2]
        if matches:
            prior=min(matches,key=lambda x:abs((x[0]-target).total_seconds()))
            res[key]=rate(v,prior[1])
    return res


def sentiment(raw):
    vals=raw.get('data',[]) if isinstance(raw,dict) else []
    return [{'value':rnd(v.get('value')),'classification':v.get('value_classification'),
             'observation_utc':iso(parse_utc(v.get('timestamp')))} for v in vals[:2] if isinstance(v,dict)]


def trending(raw,coins):
    entries=raw.get('coins',[]) if isinstance(raw,dict) else []
    map_id={int(x['cmc_id']):x for x in coins}
    # CoinGecko ID != CMC ID: match only exact name + ticker, unique item.
    valid=[]
    for x in entries:
        item=x.get('item') if isinstance(x,dict) else None
        if isinstance(item,dict):valid.append(item)
    matches=build_match_index(coins,valid)
    return [{'cmc_id':cid,'name':x.get('name'),'rank':x.get('score'),
             'mapping':mt,'interpretation':'SEARCH_ATTENTION_NOT_BUY_PRESSURE'} for cid,(x,mt) in matches.items()]




def orderbook_features(raw,instrument,contract):
    """Best bid/ask and USD 5-level depth; depth ONLY for validated contract units.

    SWAP order book sizes are contracts, not base coins. An unverified multiplier
    must produce NA for dollar-depth, never guessed market liquidity.
    """
    if not isinstance(raw,dict) or raw.get('code') not in ('0',0):return None
    data=raw.get('data')
    if not isinstance(data,list) or not data or not isinstance(data[0],dict):return None
    x=data[0];bids=x.get('bids') or [];asks=x.get('asks') or []
    if not bids or not asks:return None
    try:
        bid=number(bids[0][0]);ask=number(asks[0][0]);
        if bid is None or ask is None or bid<=0 or ask<=bid:return None
    except (IndexError,TypeError,ValueError):return None
    mid=(ask+bid)/2
    val=number(contract.get('ctVal')) if isinstance(contract,dict) else None
    val_ccy=(contract.get('ctValCcy') or '').upper() if isinstance(contract,dict) else ''
    base=instrument.split('-')[0].upper()
    if val is not None and val>0 and val_ccy in (base,'USDT','USD'):
        def side_depth(rows):
            total=0
            for row in rows[:5]:
                try:
                    px=number(row[0]);sz=number(row[1]);
                    if px is None or sz is None or sz<0:return None
                    total+=sz*val*(px if val_ccy==base else 1)
                except (TypeError,ValueError,IndexError):return None
            return round(total,2)
        buy=side_depth(bids);sell=side_depth(asks)
        depth_status='VALIDATED_CONTRACT_VALUE'
    else:buy=None;sell=None;depth_status='UNKNOWN_CONTRACT_MULTIPLIER'
    return {'instrument_id':instrument,'bid':bid,'ask':ask,'spread_bps':round(10000*(ask-bid)/mid,5),
            'top5_bid_usd':buy,'top5_ask_usd':sell,'depth_status':depth_status,
            'book_source_utc':iso(parse_utc(x.get('ts'))),'source':'OKX_ORDERBOOK_LEVEL5'}


def collect_orderbooks(network,market,workers=5):
    """Capture actual executable-proxy market microstructure, independent of spot quotes."""
    contracts=[]
    for a in market.get('assets',[]):
        p=a.get('perpetual') or {}
        if p.get('exchange')=='OKX' and p.get('symbol'):
            contracts.append((int(a['cmc_id']),p['symbol']))
    if not contracts:return []
    info=network.get('okx_book_instruments','json','https://www.okx.com/api/v5/public/instruments?instType=SWAP')
    lookup={r.get('instId'):r for r in info.get('data',[]) if isinstance(r,dict)} if isinstance(info,dict) and info.get('code') in ('0',0) else {}
    def task(item):
        cid,inst=item
        url='https://www.okx.com/api/v5/market/books?'+urllib.parse.urlencode({'instId':inst,'sz':'5'})
        raw=network.get('okx_book_'+str(cid),'json',url)
        row=orderbook_features(raw,inst,lookup.get(inst,{}))
        if row:row['cmc_id']=cid
        return row
    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        return [x for x in pool.map(task,contracts) if x is not None]

def supply_from_cmc(payload,assets):
    """Circulating/total/max supply from public CMC ID-keyed quotes; not an unlock calendar.

    The published top-level last_updated is kept separately from collection time.
    Values are never estimated from market cap or price.
    """
    if not isinstance(payload,dict):return []
    status=payload.get('status') or {}
    if not isinstance(status,dict) or status.get('error_code') not in (0,'0',None):return []
    raw=payload.get('data')
    if isinstance(raw,dict):raw=list(raw.values())
    if not isinstance(raw,list):return []
    by_id={int(x['cmc_id']):x for x in assets}
    out=[]
    for v in raw:
        if not isinstance(v,dict):continue
        try:cid=int(v['id'])
        except (TypeError,ValueError,KeyError):continue
        if cid not in by_id:continue
        item=by_id[cid]
        if v.get('symbol') and v.get('symbol')!=item['symbol']:continue
        row={'cmc_id':cid,'symbol':item['symbol'],
             'circulating_supply':rnd(v.get('circulating_supply'),6),
             'total_supply':rnd(v.get('total_supply'),6),
             'max_supply':rnd(v.get('max_supply'),6),
             'supply_last_updated_utc':v.get('last_updated'),
             'mapping_confidence':'EXACT_OFFICIAL_CMC_ID',
             'interpretation':'REPORTED_SUPPLY_SNAPSHOT_NOT_A_VERIFIED_UNLOCK_EVENT'}
        if any(row[k] is not None for k in ('circulating_supply','total_supply','max_supply')):out.append(row)
    return out


def fetch_supply(network,assets):
    by_id={}
    for i in range(0,len(assets),40):
        ids=','.join(str(x['cmc_id']) for x in assets[i:i+40])
        params=urllib.parse.urlencode({'id':ids,'convert':'USD','skip_invalid':'true'})
        raw=network.get('cmc_supply_batch_'+str(i//40+1),'json',
            'https://pro-api.coinmarketcap.com/public-api/v3/cryptocurrency/quotes/latest?'+params)
        for row in supply_from_cmc(raw,assets):by_id[row['cmc_id']]=row
    return sorted(by_id.values(),key=lambda x:x['cmc_id'])

def previous_oi(base,market):
    """Compute exact-exchange 24h OI changes from OBSERVED records in own archive.

    Source market quote timestamps are authoritative. Repeated stale market snapshots
    do not produce new history points or artificial OI changes.
    """
    started=parse_utc(market.get('snapshot_completed_utc'))
    if not started:return [],{}
    relevant_dates={(started-dt.timedelta(days=d)).strftime('%Y%m%d') for d in (0,1,2)}
    previous={}
    for date in relevant_dates:
        fp=base/'oi_history'/(date+'.jsonl')
        if not fp.exists():continue
        for line in fp.read_text(encoding='utf8').splitlines():
            try:x=json.loads(line)
            except ValueError:continue
            key=(str(x.get('source_exchange')),str(x.get('instrument_id')))
            t=parse_utc(x.get('oi_observed_utc'))
            v=number(x.get('oi_usd'))
            if t and v is not None and t<=started:previous[(key,iso(t))]=x
    updates=[];deltas={}
    for a in market.get('assets',[]):
        p=a.get('perp_market') or {};contract=a.get('perpetual') or {}
        exch=p.get('source_exchange');inst=contract.get('symbol')
        t=parse_utc(p.get('oi_observed_utc'));v=number(p.get('oi_usd'))
        if not (exch and inst and t and v is not None and v>=0 and t<=started):continue
        identity=(str(exch),str(inst))
        entry={'source_exchange':exch,'instrument_id':inst,'oi_observed_utc':iso(t),
               'oi_usd':v,'cmc_id':a['cmc_id'],'source_market_snapshot_utc':market['snapshot_completed_utc']}
        if (identity,iso(t)) not in previous:updates.append(entry)
        previous[(identity,iso(t))]=entry
        candidates=[]
        for (key,stamp),old in previous.items():
            if key!=identity:continue
            prior=parse_utc(stamp);gap=(t-prior).total_seconds()/3600
            if 23.5<=gap<=24.5:candidates.append((abs(gap-24),old))
        if candidates:
            old=min(candidates,key=lambda x:x[0])[1]
            deltas[str(a['cmc_id'])]={'value_pct':rate(v,old['oi_usd']),'from_utc':old['oi_observed_utc'],
                'to_utc':iso(t),'exchange':exch,'contract':inst,'status':'MEASURED_SAME_CONTRACT_24H'}
    return updates,deltas


def save_oi(base,records):
    grouped=defaultdict(list)
    for x in records:
        date=x['oi_observed_utc'][:10].replace('-','')
        grouped[date].append(x)
    for day,items in grouped.items():
        fp=base/'oi_history'/(day+'.jsonl');fp.parent.mkdir(parents=True,exist_ok=True)
        with fp.open('a',encoding='utf8') as f:
            for x in sorted(items,key=lambda i:(i['oi_observed_utc'],i['instrument_id'])):
                f.write(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n')


def output_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf8')


def compact_csv(path,rows,keys):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');w.writeheader();w.writerows(rows)


def collect(network,market,previous_events=None,oi_base=None,workers=5):
    assets=market.get('assets',[])
    if len(assets)!=100 or len({int(c['cmc_id']) for c in assets})!=100 or market.get('index',{}).get('verified_constituents')!=100:
        raise ValueError('Market baseline needs 100 officially verified CMC IDs')
    captured=now()
    source_data={}
    def load(s):
        ident,family,kind,url=s
        return ident,network.get(ident,kind,url)
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for ident,data in ex.map(load,SOURCE_CATALOG):source_data[ident]=data
    # CMC ID-keyed token-supply observations are separate from the older spot snapshot.
    supply_rows=fetch_supply(network,assets)
    books=collect_orderbooks(network,market,workers=workers)
    calls={r['source_id']:r for r in network.calls}
    coins=[{'cmc_id':c['cmc_id'],'name':c['name'],'symbol':c['symbol']} for c in assets]
    findings={'protocol_tvl':[],'chain_tvl':[],'protocol_fees':[],'protocol_revenue':[],
              'token_holder_revenue':[],'dex_protocol_volume':[], 'options_activity':[],
              'decentralized_perp_oi':[],'trending':[], 'stablecoin_chains':[],
              'stablecoin_global':{}, 'market_sentiment':[],'token_supply':supply_rows,'okx_orderbooks':books}
    findings['protocol_tvl'],_ = protocols_rows(source_data.get('llama_protocols'),coins)
    findings['chain_tvl']=chain_rows(source_data.get('llama_chains'),coins)
    for ident,key in [('llama_fees','protocol_fees'),('llama_revenue','protocol_revenue'),
                      ('llama_holder_revenue','token_holder_revenue'),('llama_dex','dex_protocol_volume'),
                      ('llama_options','options_activity'),('llama_perp_oi','decentralized_perp_oi')]:
        findings[key]=protocol_metric_rows(source_data.get(ident),coins,key)
    findings['stablecoin_global']=stablecoin_global(source_data.get('llama_stablecoin_supply'),captured)
    if isinstance(source_data.get('llama_stablecoin_chains'),list):
        findings['stablecoin_chains']=[{'chain':x.get('name'),'supply_usd':rnd(dollars(x.get('totalCirculating')),2)}
            for x in source_data['llama_stablecoin_chains'] if isinstance(x,dict) and x.get('name')]
    findings['trending']=trending(source_data.get('coingecko_trending'),coins)
    findings['market_sentiment']=sentiment(source_data.get('alternative_fng'))
    # Bounded incremental evidence ledger. Persist first_seen across scheduled runs.
    old=previous_events or {};all_events={}
    for ident,cat,kind,url in SOURCE_CATALOG:
        if kind!='rss' or not isinstance(source_data.get(ident),bytes):continue
        for e in parse_feed(source_data[ident],ident,calls[ident]['observed_utc']):
            e=label_event(e,coins)
            old_e=old.get(e['event_id'])
            e['first_observed_utc']=(old_e or {}).get('first_observed_utc') or e['observed_utc']
            e['last_observed_utc']=e.pop('observed_utc')
            if e['event_id'] in all_events:
                old_existing=all_events[e['event_id']]
                e['source_ids']=sorted(set(old_existing['source_ids']+[ident]))
                if old_existing['published_utc'] and not e['published_utc']:e['published_utc']=old_existing['published_utc']
            else:e['source_ids']=[ident]
            all_events[e['event_id']]=e
    # Keep event history bounded for connector usability. Archive all active events per run.
    # Preserve direct source breadth: the old 420-item cap silently discarded
    # genuine primary release/governance updates after collector expansion.
    # This is still a bounded *readable index*; no source completeness claimed.
    events=sorted(all_events.values(),key=lambda e:(e['published_utc'] or '',e['event_id']),reverse=True)[:1800]
    updates,deltas=previous_oi(oi_base or OUT,market)
    coin_row=[];pmap=defaultdict(list)
    books_by_id={str(x['cmc_id']):x for x in books}
    for field in ('protocol_tvl','chain_tvl','protocol_fees','protocol_revenue','token_holder_revenue',
                  'dex_protocol_volume','options_activity','decentralized_perp_oi','trending','token_supply'):
        for x in findings[field]:pmap[str(x['cmc_id'])].append(field)
    emap=defaultdict(list)
    for e in events:
        for cid in e['cmc_ids']:emap[str(cid)].append(e['event_id'])
    for c in assets:
        cid=str(c['cmc_id']);p=c.get('perp_market') or {}
        coin_row.append({'cmc_id':int(cid),'symbol':c['symbol'],'coin_name':c['name'],
                         'spot_quote_updated_utc':(c.get('cmc_quote') or {}).get('quote_last_updated_utc'),
                         'perp_exchange':p.get('source_exchange'), 'perp_oi_usd':p.get('oi_usd'),
                         'perp_oi_change_24h_pct':(deltas.get(cid) or {}).get('value_pct'),
                         'perp_funding_estimate':p.get('estimated_next_funding_rate_fraction'),
                         'circulating_supply':next((r['circulating_supply'] for r in supply_rows if r['cmc_id']==int(cid)),None),
                         'total_supply':next((r['total_supply'] for r in supply_rows if r['cmc_id']==int(cid)),None),
                         'max_supply':next((r['max_supply'] for r in supply_rows if r['cmc_id']==int(cid)),None),
                         'okx_orderbook_spread_bps':(books_by_id.get(cid) or {}).get('spread_bps'),
                         'okx_orderbook_top5_bid_usd':(books_by_id.get(cid) or {}).get('top5_bid_usd'),
                         'okx_orderbook_top5_ask_usd':(books_by_id.get(cid) or {}).get('top5_ask_usd'),
                         'research_metric_families':sorted(set(pmap[cid])),
                         'research_event_candidate_ids':emap[cid],
                         'evidence_is_price_catalyst':'UNDETERMINED'})
    families=defaultdict(lambda:{'source_count':0,'successful_sources':0,'coin_coverage':0,'status':'UNAVAILABLE'})
    for ident,family,kind,url in SOURCE_CATALOG:
        families[family]['source_count']+=1
        if calls.get(ident,{}).get('status')=='OK':families[family]['successful_sources']+=1
    for family,v in families.items():v['status']='PARTIAL' if v['successful_sources']>0 else 'UNAVAILABLE'
    families['ORDERBOOK_LIQUIDITY']={'source_count':sum(x['source_id'].startswith('okx_book_') for x in network.calls),
        'successful_sources':sum(x['status']=='OK' for x in network.calls if x['source_id'].startswith('okx_book_')),
        'coin_coverage':len(books),'status':'PARTIAL' if books else 'UNAVAILABLE',
        'gap':'SWAP_ORDERBOOK_SNAPSHOT_ONLY;USD_DEPTH_REQUIRES_VERIFIED_CONTRACT_SIZE'}
    families['TOKEN_SUPPLY_REPORTED']={'source_count':3,'successful_sources':sum(r['status']=='OK' for r in network.calls if r['source_id'].startswith('cmc_supply_batch_')),
        'coin_coverage':len(supply_rows),'status':'PARTIAL' if supply_rows else 'UNAVAILABLE',
        'gap':'ACTUAL_TOKEN_UNLOCKS_AND_VESTING_ARE_NOT_INFERRED_FROM_SUPPLY'}
    family_map={
        'DEFI_PROTOCOL_TVL':'protocol_tvl','ONCHAIN_CHAIN_TVL':'chain_tvl','PROTOCOL_FEES':'protocol_fees',
        'PROTOCOL_REVENUE':'protocol_revenue','TOKEN_VALUE_ACCRUAL':'token_holder_revenue',
        'DEX_VOLUME':'dex_protocol_volume','OPTIONS_ACTIVITY':'options_activity',
        'DECENTRALIZED_PERP_OI':'decentralized_perp_oi','SOCIAL_ATTENTION':'trending','TOKEN_SUPPLY_REPORTED':'token_supply'}
    for family,key in family_map.items():
        families[family]['coin_coverage']=len({r['cmc_id'] for r in findings[key]})
        if families[family]['coin_coverage']==0 and families[family]['successful_sources']>0:
            families[family]['status']='SOURCE_OK_NO_VERIFIED_COIN_MAPPING'
            families[family]['gap']='HTTP_OK_BUT_NO_EXTRACTED_CMC_ID_MATCH;RAW_PROVIDER_AGGREGATES_NOT_COIN_SIGNALS'
    family_gaps={
       'TOKEN_UNLOCK_SCHEDULE':'NO_VERIFIED_FREE_BULK_PIT_TOKEN_UNLOCK_CALENDAR;RSS_EVENT_DISCOVERY_ONLY',
       'TOKEN_SUPPLY_CHAIN':'NO_FULL_POINT_IN_TIME_CIRCULATING_SUPPLY_HISTORY',
       'CEFI_LIQUIDATIONS':'NO_VERIFIED_COIN_LEVEL_LIQUIDATION_HISTORY',
       'SPOT_ORDERBOOK_LIQUIDITY':'NO_BROAD_100_COIN_SPOT_DEPTH_COMPARISON',
       'CEX_NETFLOWS':'NO_VALIDATED_EXCHANGE_WALLET_LABELS_OR_COIN_NETFLOWS',
       'ETF_FLOWS':'NO_VERIFIED_TIME_STAMPED_ETF_FUND_FLOW_FEED',
       'MACRO_CALENDAR':'NO_VERIFIED_FREE_SCHEDULED_EVENT_API',
       'GOVERNANCE_PROPOSALS':'NO_BROAD_STRUCTURED_PIT_PROPOSAL_INDEX',
       'GITHUB_CODE_ACTIVITY':'NO_OFFICIAL_PROJECT_REPO_TO_CMC_ID_MAPPING',
       'WHALE_ADDRESS_ACTIVITY':'NO_TRUSTED_LABELLED_WALLET_MAPPING',
       'OPTIONS_SKEW':'NO_COMPLETE_TOKEN_LEVEL_OPTIONS_SURFACE',
       'SOCIAL_SENTIMENT':'TRENDING_AND_NEWS_ONLY;NOT_FULL_SOCIAL_TIME_SERIES',
    }
    for fam,why in family_gaps.items():families[fam]={'source_count':0,'successful_sources':0,'coin_coverage':0,
                                                      'status':'UNAVAILABLE_OR_EVENT_ONLY','gap':why}
    families['SPOT_MARKET']={'source_count':1,'successful_sources':1,'coin_coverage':sum(1 for c in assets if (c.get('cmc_quote') or {}).get('price_usd') is not None),'status':'FROM_VERIFIED_MARKET_SNAPSHOT'}
    families['PERPETUAL_DERIVATIVES']={'source_count':1,'successful_sources':1,'coin_coverage':sum(1 for c in assets if (c.get('perp_market') or {}).get('oi_usd') is not None),'status':'FROM_VERIFIED_MARKET_SNAPSHOT'}
    families['OI_CHANGE_24H']={'source_count':1,'successful_sources':1,'coin_coverage':len(deltas),'status':'MEASURED_ONLY_WHEN_HISTORY_AVAILABLE'}
    status={'status':'COLLECTED_PARTIAL' if any(v.get('successful_sources',0) for v in families.values()) else 'ALL_EXTERNAL_SOURCES_FAILED',
            'capture_utc':captured,'source_market_snapshot_utc':market['snapshot_completed_utc'],
            'market_index_last_update':market['index']['last_update'],'cmc100_verified':100,
            'sources_configured':len(network.calls),'sources_ok':sum(r['status']=='OK' for r in network.calls),
            'sources_failed':sum(r['status']!='OK' for r in network.calls),'rss_events_stored':len(events),
            'rss_events_with_cmc_candidate':sum(bool(e['cmc_ids']) for e in events),
            # Exclude CMC supply and CoinGecko trending: neither is DefiLlama.
            'coin_metrics_with_defillama':sum(bool(set(x['research_metric_families']) & {
                 'chain_tvl','protocol_tvl','protocol_fees','protocol_revenue','token_holder_revenue',
                 'dex_protocol_volume','options_activity','decentralized_perp_oi'}) for x in coin_row),
            'coin_count_with_event_candidate':sum(bool(x['research_event_candidate_ids']) for x in coin_row),
            'successful_sources_with_zero_coin_mapping':[f for f,v in families.items()
                 if v.get('status')=='SOURCE_OK_NO_VERIFIED_COIN_MAPPING'],
            'perp_oi_change_24h_measured':len(deltas),
            'family_coverage':dict(families),'source_attempts':sorted(network.calls,key=lambda x:x['source_id']),
            'limitations':['OPEN_ENDED_RESEARCH_NOT_EXHAUSTIVE','EVENT_HEADLINE_IS_NOT_PROOF_OF_EVENT',
                           'CMC_SYMBOL_NEWS_TAGS_ARE_CANDIDATE_MATCHES','PROTOCOL_REVENUE_IS_NOT_TOKEN_HOLDER_REVENUE',
                           'SOURCE_PUBLISHED_UTC_CAN_BE_UNKNOWN','MARKET_SNAPSHOT_AND_RESEARCH_CAPTURE_TIMES_DIFFER']}
    return {'schema_version':'research-v1','status':status,'source_catalog':[{'id':i,'family':f,'kind':k,'url':u} for i,f,k,u in SOURCE_CATALOG],
            'families':findings,'coins':coin_row,'events':events,'oi_new_records':updates,
            'oi_24h_deltas':deltas}


def write_bundle(bundle,out=OUT):
    out.mkdir(parents=True,exist_ok=True)
    # A 1MB+ latest.json becomes unreadable through GitHub Contents API.
    # Publish a compact index AND every source event in SHA-verified <=80-row
    # batches. The full events remain PIT-available, never silently discarded.
    status=bundle['status'];events=bundle['events']
    doc={k:v for k,v in bundle.items() if k!='oi_new_records'}
    doc['events']=events[:200]
    doc['events_read_index_count']=len(doc['events'])
    doc['full_source_events_manifest']='docs/research/source_events_manifest.json'
    event_dir=out/'source_event_batches'
    event_dir.mkdir(parents=True,exist_ok=True)
    parts=[]
    for pos in range(0,len(events),80):
        batch=events[pos:pos+80]
        fp=event_dir/('batch_%02d.json'%(pos//80+1))
        output_json(fp,{'capture_utc':status['capture_utc'],'events':batch})
        h=hashlib.sha256(fp.read_bytes()).hexdigest()
        parts.append({'path':'docs/research/source_event_batches/'+fp.name,
                      'sha256':h,'count':len(batch)})
    output_json(out/'source_events_manifest.json',{
         'capture_utc':status['capture_utc'],'total_events':len(events),
         'read_index_count':len(doc['events']),'batches':parts,
         'all_source_events_preserved':True})
    output_json(out/'latest.json',doc);output_json(out/'status.json',status)
    compact_csv(out/'events.csv',[{'event_id':e['event_id'],'source_id':e['source_id'],
        'published_utc':e['published_utc'],'first_observed_utc':e['first_observed_utc'],
        'headline':e['headline'],'url':e['url'],'event_classes':';'.join(e['event_classes']),
        'cmc_ids':';'.join(map(str,e['cmc_ids'])),'tags_unverified':True} for e in events],
        ['event_id','source_id','published_utc','first_observed_utc','headline','url','event_classes','cmc_ids','tags_unverified'])
    coins=bundle['coins']
    compact_csv(out/'coin_features.csv',[{**x,'research_metric_families':';'.join(x['research_metric_families']),
            'research_event_candidate_ids':';'.join(x['research_event_candidate_ids'])} for x in coins],
        ['cmc_id','symbol','coin_name','spot_quote_updated_utc','perp_exchange','perp_oi_usd',
         'perp_oi_change_24h_pct','perp_funding_estimate','circulating_supply','total_supply','max_supply','okx_orderbook_spread_bps','okx_orderbook_top5_bid_usd','okx_orderbook_top5_ask_usd','research_metric_families',
         'research_event_candidate_ids','evidence_is_price_catalyst'])
    save_oi(out,bundle['oi_new_records'])
    stamp=status['capture_utc'].replace('-','').replace(':','')
    # Immutable by unique capture timestamp+digest; never overwrite an existing archive.
    serialized=json.dumps(doc,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    digest=hashlib.sha256(serialized).hexdigest()[:10]
    archive=out/'archive'/status['capture_utc'][:10].replace('-','')/(stamp+'_'+digest+'.json')
    archive.parent.mkdir(parents=True,exist_ok=True)
    with archive.open('x',encoding='utf8') as f:json.dump(doc,f,ensure_ascii=False,sort_keys=True)
    # Keep first-observed evidence index, without swallowing earlier event metadata.
    old_index={}
    index_path=out/'event_first_seen.json'
    if index_path.exists():
        try:old_index=json.loads(index_path.read_text('utf8'))
        except (ValueError,TypeError):old_index={}
    for e in events:old_index.setdefault(e['event_id'],{'first_observed_utc':e['first_observed_utc']})
    output_json(index_path,old_index)
    return status


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--max-workers',type=int,default=5)
    args=ap.parse_args()
    if not 1<=args.max_workers<=8:raise ValueError('max-workers must be 1..8')
    if not (DOCS/'latest.json').exists():
        print('MARKET_SNAPSHOT_MISSING; no research bundle written');return 2
    market=json.loads((DOCS/'latest.json').read_text('utf8'))
    first_seen={}
    fp=OUT/'event_first_seen.json'
    if fp.exists():
        try:first_seen=json.loads(fp.read_text('utf8'))
        except (ValueError,TypeError):first_seen={}
    try:
        bundle=collect(Network(),market,first_seen,OUT,args.max_workers)
        status=write_bundle(bundle,OUT)
        print(json.dumps({k:v for k,v in status.items() if k not in ('source_attempts','family_coverage')},ensure_ascii=False,indent=2))
        return 0
    except Exception as exc:
        output_json(OUT/'status.json',{'status':'FAILED_NO_RESEARCH_BUNDLE','error':str(exc),'capture_utc':now()})
        raise

if __name__=='__main__':raise SystemExit(main())