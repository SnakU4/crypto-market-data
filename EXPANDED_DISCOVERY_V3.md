# CMC100 Expanded Evidence Discovery v3 — **Stage 1, not forecasting**

## Purpose

Capture substantially broader public information about **every official CMC100 constituent**, adjacent technology, developer discussions and project communities. **10,000+ deduplicated URL leads per run is an aspirational research-volume target, not a guaranteed outcome**: rate limits, lack of news on smaller coins, syndication and search-provider indexing are real constraints. This program reports the actual total and shortfall instead of padding or inventing records. **Volume is not predictive quality** and is not itself a success measure.

**No automated coin/entity matching.** A request tagged `query_cmc_id=...` means *we searched for that coin*. It does **not** mean an article is about the coin, was confirmed, is timely or moves its price. Every stored record has `coin_relevance_status=NOT_ASSESSED` and `price_direction=NOT_ASSESSED` for downstream AI review.

## Querying / coverage

- **100 official CMC ID members**, verified from `docs/latest.json`, no fallback to market-cap top 100.
- **Eight independent searches per coin: 800 planned**, including current news, software development, exploits, tokenomics, ecosystem/adoption, market structure, indexed community discussion and indexed social references. Uses both full asset name and ticker in queries for better disambiguation; the resulting records still receive **no coin relevance verdict**. Source of the queries: public Google News RSS (RSS search indexing is not a Twitter or Reddit API).
- Additional **24 unrelated thematic searches** on AI compute, security, cryptography, semiconductor supply, energy and hardware, identity, payments, macro, science, robotics and infrastructure. No token name required.
- **12 public project/governance Discourse RSS candidates** (not assumed reachable), **8 technology/cybersecurity/science feeds** and **12 Hacker News searches**. Hacker News uses a seven-day date filter rather than inadvertently collecting discussions from 2018.
- Other existing feeds and the main `Cross-Sector Crypto Discovery` remain independent and are not silently replaced.
- **No unauthorized Reddit, X or Bluesky scraping**. Access is explicitly tracked as a gap. Note Reddit's announced RSS retirement on 2026-11-13.

**Configured requests per run:** 856: 800 coin + 24 thematic + 12 community + 8 other + 12 HN. Endpoint availability remains to be checked on GitHub Actions, where specific hosts may issue 403, 429 or return an empty feed. The collector has a host-level circuit breaker to avoid repeated 403/429 floods, bounded concurrent requests, and timeouts. No paid APIs, credentials, OpenAI API, or trading.

## Storage / measurable coverage

- `docs/expanded_discovery/status.json`: source status, attempted and successful requests, verified CMC100 count, coins with actually successful responses, empty searches, 24h freshness, counts by family, unique URLs, normalized-title diversity, **10k target / shortfall** and access gaps.
- `docs/expanded_discovery/latest.json`: up to 1,000 diverse **unverified** leads, sources and excerpts for rapid reading.
- `docs/expanded_discovery/latest_shards/shard_00.json` ... `shard_19.json`: full current deduplicated run partitioned into 20 **text-readable** JSON files, independently accessible via the connected GitHub plugin. The shards are not limited to the first 1,000 leads.
- `docs/expanded_discovery/archive/YYYYMMDD/*_all.jsonl.gz`: immutable, gzip-compressed full run archive (all source-provided URLs, one record per canonical URL). The SHA-256 is written in the status file.
- `docs/expanded_discovery/archive/YYYYMMDD/*_new.jsonl.gz`: compressed *newly first-observed* records, to distinguish repeated leads from incremental discoveries.
- `docs/expanded_discovery/source_audit.csv`: all planned requests and HTTP/provider errors.
- `docs/expanded_discovery/seen_registry.json`: rolling 14-day event-hash → first-observed timestamp registry; beyond this window the immutable archives retain earlier observations. If an old link reappears after registry expiry it can be counted as new — do not claim a global-ever-new metric from this rolling counter.

The full run is **not truncated to 10,000**. Every provider-returned unique eligible URL is archived. Titles have a separate near-exact normalized hash: comparing `distinct_story_title_hashes` against `distinct_url_leads` exposes repeated syndication. These are still only **leads**, not independently verified events.

The index is family-and-source balanced and prioritizes newer material within each source. Provider snippets and source dates are explicitly labelled. Information older than seven days is excluded from this pipeline's active collection; older contextual sources remain accessible through other stage-1 archives. Unknown publication time remains unknown (only first observation can establish availability), and future-dated records are removed.

**Growth warning:** Twice-daily archives and full text-readable shards can grow a Git repository rapidly. Monitor repository size/Actions storage. Before unattended long-term deployment, migrate immutable raw archives to GitHub Actions artifacts or object storage with immutable checksums, while preserving the connector-accessible index. The current implementation is a research prototype, not indefinitely scalable storage.

## Activation and validation

1. Review and merge the corresponding PR.
2. Actions → **CMC100 Expanded Evidence Discovery** → **Run workflow**.
3. Inspect `docs/expanded_discovery/status.json`: `distinct_url_leads`, `distinct_story_title_hashes`, `unique_urls_published_last_24h`, `coins_with_successful_query`, `coins_with_nonempty_query`, `requests_ok`, `target_shortfall`, source errors.
4. Verify the actual gzip run archive count, at least one readable shard, and no automatic coin assignment.
5. Adapt sources and request budget based on live hit rates; the target must not encourage irrelevant duplicates.

Run local deterministic offline tests (including a 10,050-lead fixture):
`python -m unittest discover -s tests -p 'test_expanded_discovery.py' -v`

## Source-access notes

Google News RSS syntax is available through ordinary RSS queries but is not a guaranteed high-volume API. GitHub's `GITHUB_TOKEN` has specific limits and any future authenticated repository-research layer should adhere to its request limits and throttling. Reddit's RSS retirement and API access changes require an authorized integration for full coverage.

Stage 2 needs to ingest **market**, **structured DeFi research**, **cross-sector** and **expanded CMC100** sources, and *then* perform causal coin matching and independently source-check high-impact claims. The previous V6 forecast task is intentionally unchanged by this PR.