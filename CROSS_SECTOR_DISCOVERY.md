# Cross-Sector Crypto Discovery — Stage 1 extension

**Why:** The CMC100 cannot be researched effectively using only crypto market feeds, token metrics and crypto headlines. Relevant 24h catalysts can arise from AI/cloud compute, semiconductor supply, quantum/cryptography, new security bugs, global liquidity, regulation, consumer adoption and developer discussions *before* conventional crypto news picks them up.

This standalone, standard-library collector adds a non-LLM **signal-discovery and evidence-ingestion layer** on top of the official 100-ID market snapshot. It **does not** automatically predict token returns, assign an ex-ante positive/negative direction, or claim that a thematic article necessarily benefits a token.

## Source channels

| Channel | What is ingested | Type | Notes |
|---|---|---|---|
| Cross-industry Google News RSS searches | headlines, original feed date where available, URL | Meta-news | Multiple topics and anomaly-driven coin-name searches, `when:2d` |
| GDELT worldwide news index | article title, URL, indexed time, publication domain | Meta-news | GDELT `seendate` is not original publisher timestamp |
| Bluesky public searchPosts | public post excerpts, author handle, likes/reposts/replies | Social | Public AppView; provider rate limits may prevent reads |
| Hacker News Algolia | technical discussions, title, votes, comments | Tech community | Public read-only search API |
| arXiv subject feeds | AI, ML, cryptography, distributed computing, quantum, economics | Scholarly | Paper title is a research lead, not confirmed commercial adoption |
| Technology / infrastructure feeds | selected broad technology, AI and developer blogs | Tech news | Includes Cloudflare, CNCF, Hugging Face and general technology media |
| GitHub releases and security advisories | selected open-source project releases plus software advisories | Primary source | Repository provenance preserved; sample selection not exhaustive |
| Market-anomaly driven queries | full *coin name*, triggered by spot, perp, funding or volume anomalies | Adaptive | Query priority is not a forecast or evidence of direction |
| Cross-source emerging terms | terms mentioned by at least two distinct source families, searched in a later run | Adaptive | Keywords are *leads*, never automatically mapped to tokens |

**Reddit:** Reddit publicly announced its RSS shutdown on 13 November 2026 and public API migration to Developer Platform. This collector does not rely on soon-to-be-retired RSS or unauthorized API scraping. Add a compliant Reddit adapter **only after** obtaining an approved access mechanism; report `NOT_COLLECTED` until then.

**X/Twitter:** No proven, free, broad official historical/full-text API access. Do not mislabel secondary citations/news syndication as X API coverage. A separate authorized adapter can be added if access exists.

**Additional follow-up adapters** worth investigating (not implied to work yet): government technical procurement filings, industry patent metadata, Google Trends (with an authorized stable retrieval route), protocol GitHub issue/event streams, real-world hardware prices/capacity, cloud/GPU rental markets, crypto ETF creations/redemptions, security vulnerability databases, energy grid constraints, exchange service-status feeds, verified developer forums, public governance proposal feeds and opt-in token teams' communication channels.

## Dynamic discovery, not a closed source taxonomy

The `THEMES` mapping and `STATIC_FEEDS` catalog provide initial breadth. They are **open registries**, not a claim to cover all events. Each run:

1. Collects broad adjacent technology / economic news and social & developer posts from public endpoints.
2. Triggers extra queries for *market-anomalous* CMC100 assets using **full names**, not ambiguous tickers.
3. Mines terms repeatedly reported across distinct sources to propose additional open-topic searches on the next run.
4. Saves every accessible lead with provenance and publication/observation time; independently deduplicates links.
5. Assigns only **potential explicit coin mentions** and **theme leads**. It never infers a directional 24h price impact from theme keywords alone.
6. Audits failed requests, valid-lead counts, coverage and known blind spots. An HTTP 200 with zero usable leads is *not* called full research coverage.

**Limitations:** Without an LLM at this phase, open-ended hypothesis generation is a bounded *adaptive retrieval heuristic*, not deep semantic exploration. Stage 2 is necessary to investigate potential causal effects, cross-sector exposure graphs, confirmations/counter-evidence and unpriced 24h catalysts. No single public collector can prove it searched *every possible* relevant information source.

## Outputs (created only after first successful Actions run)

- `docs/discovery/latest.json`: bounded latest research leads (max 500), full query plan and source-status audit.
- `docs/discovery/status.json`: source-level counts for attempted, successful, zero-valid-lead and blocked sources, plus gaps.
- `docs/discovery/leads.csv`: flat audit for human inspection.
- `docs/discovery/first_seen.json`: persistent first observed time by canonical URL hash.
- `docs/discovery/archive/YYYYMMDD/*.json`: immutable research snapshots for prospective audit.

### Integrity and costs

- No OpenAI API; no paid data provider; no private keys; no trades.
- Uses the **existing official CMC100** snapshot for 100 unique ID universe validation. No generic market-cap top-100 substitutes.
- Publication times are separately recorded from observed times; GDELT first-seen time is not original publication time.
- Future-dated items are excluded. Missing article publication time remains unknown.
- Ambiguous short tickers require `$TICKER` to create a tentative coin mention. Technical themes must not automatically be mapped to a coin or interpreted as a price catalyst.
- Every request has a public URL, status, time and count; service/API access must be verified on **GitHub Actions** (local tests mock network).
- Some feeds may return `403`, `429`, `404`, or a schema mismatch. Such failures are visible and do not silently become zero-signal observations.
- The archive persists metadata; future workflow runs can become large. Periodically monitor git repository size and switch old archives to Actions artifacts/object storage when needed (with PIT hash manifest).

## Activation

The `.github/workflows/adjacent-discovery.yml` workflow runs at **00:13, 06:13, 12:13, 18:13 UTC**. GitHub's scheduled execution can be delayed. Start with **Actions → Cross-Sector Crypto Discovery → Run workflow** after merging. Inspect `docs/discovery/status.json` and `docs/discovery/latest.json` to validate actual successful source parsing and time attribution.

Run offline unit tests:

```bash
python -m unittest discover -s tests -p 'test_adjacent_discovery.py' -v
```

The V6 forecast automation is intentionally not changed by this PR. A future V6 prompt/ingestion revision must read this independent research store **in addition to** `docs/latest.json` and `docs/research/latest.json`, then test availability and incremental predictive usefulness.

## Primary documentation / limitations checked 2026-11-06

- Bluesky public API: https://docs.bsky.app/docs/api/ and https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts
- Hacker News Algolia search API: https://hn.algolia.com/api
- arXiv RSS: https://info.arxiv.org/help/rss.html
- GDELT DOC: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
- Reddit API/RSS retirement: https://support.reddithelp.com/hc/en-us/articles/54353370049684-Changelog-October-8-2026
- GitHub public releases: https://docs.github.com/en/rest/releases/releases
- GitHub public security advisories: https://docs.github.com/en/rest/security-advisories/global-advisories