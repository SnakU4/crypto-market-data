# Stage 1 — Expanded Evidence Discovery v4.1

Implemented 2026-11-10. This is **collection and quality measurement only**, not coin matching, trading or forecasting. The existing append-only per-run archives and scheduled job remain intact.

## Changes

### 1. Public Google News links → actual publisher evidence, when possible
- Each RSS Google News URL remains the immutable original lead identifier and URL; it is **never replaced** with a guessed publisher URL.
- A separate, explicitly bounded resolution step (default 240 candidates/run) accepts only a validated explicit publisher target in the URL, normal HTTPS redirects, or a publisher-hosted canonical/OG URL. It does **not** use an unofficial Google decoder, consent/paywall bypass, or extract an arbitrary unrelated link.
- Separate `resolved_article_url`, `resolution_status`, `google_news_resolution_attempted`, `google_news_resolution_succeeded` counters. An opaque Google News ID may remain `UNRESOLVED`; **the implementation does not guarantee any Google News decoding success**.
- Resolved publisher pages may be fetched as part of the separate article budget.

### 2. Bounded publisher text extraction
- At most 320 article page attempts/run (hard code limit 450) and 240 Google News resolution attempts/run (hard configuration cap 300). Article requests use short timeouts, MIME checks, a 350KB response cap and at most 1,600 characters of publisher excerpt; no full copyrighted articles are stored.
- Public HTTPS URL and DNS checks, explicit HTTPS redirect validation, robots.txt policy checks, denial on inaccessible robots policy, six article workers, and **12 article requests per publisher host**. No access-control workaround.
- Prioritizes previously unseen leads and primary/community sources. Existing Google News snippets remain attached when article access fails.
- The 320 budget is an *upper bound*, not a guarantee. The actual number is shown in `article_fetch_attempted`.

### 3. Direct sources
- Beyond 18 earlier direct project/community feeds, 21 additional candidate GitHub release feeds now cover repositories across Avalanche, Cardano, Stellar, XRP, NEAR, Sui, Aptos, Litecoin, Dogecoin, Zcash, Monero, Polygon, Stacks, Sei, Injective, Celestia and more.
- Feed accessibility, whether a project is actually in the current CMC100, and emitted content are checked in the run audit. Feeds are supplemental, **not verified daily coverage of every coin**.
- No token-relevance judgments are made just because a query or feed relates to a coin.

### 4. Measurement
Inspect:
- `docs/expanded_discovery/status.json` → `information_quality` for `article_fetch_attempted`, `article_fetch_substantive`, `google_news_resolution_attempted`, `google_news_resolution_succeeded`, `resolved_google_articles_fetched`, `substantive_excerpts`, `title_equivalent_or_short`.
- `docs/expanded_discovery/daily_metrics.json` → the new per-run Google News resolution counts, plus existing new-URL/new-informative counts.
- `docs/expanded_discovery/source_audit.csv` → errors and active primary sources.
- `docs/expanded_discovery/latest_shards` → original `url`, optional `resolved_article_url`, provenance, text excerpts and source distinctions.

## Validation

Run GitHub Actions → **CMC100 Expanded Evidence Discovery** → Run workflow on `main`. Unit tests now also verify a Google News wrapped URL, a mocked successful and unsuccessful resolution, source preservation, article limits and host throttling. The job tests before collecting.

**Acceptance is empirical**: a successful workflow test and collector run are necessary. Compare informative context rates, newly informative URLs and producer-source share with the 2026-11-10 v4 baseline of 182 informative snippets / 10,158 URLs (1.79%), 18 informative among 614 new URLs, and 11 article fetch attempts (5 substantive). A higher URL total by itself is not an improvement. Do not proceed to Stage 2 on volume alone.

## Limitations

Opaque Google RSS URLs may not reveal their publisher through accessible redirects or canonical headers. Direct feed URLs may return 404/403/429. Public publisher robots restrictions and rate controls can reduce actual article throughput. The selection is budgeted rather than a complete article corpus. Longer article excerpts are evidence for *manual/AI review*, not independently corroborated event facts. The historical seen-registry window remains rolling 14 days; the daily metrics are **not** lifetime-global novelty.
