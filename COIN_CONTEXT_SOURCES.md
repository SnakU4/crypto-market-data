# CMC100: free, source-backed context for every coin

This is an **additional** evidence plane, not a replacement for the structured
market/derivatives/on-chain collection or the original event corpus.

## Sources, cost and access

- CoinPaprika keyless **coin directory** and per-coin `/coins/{id}` profiles:
  descriptive project text, technical attributes, tags, website, repository and
  whitepaper references.
- CoinPaprika keyless **`/coins/{id}/events`**: dated event descriptions where
  available. Event date is **not** publication date or confirmed impact.
- CoinPaprika keyless **`/coins/{id}/markets`**: individual listed markets
  and reported 24h pair volumes, **not execution-ready liquidity**.
- CoinGecko **public** `/coins/list` plus `/coins/{id}` used only when a
  substantive CoinPaprika profile is missing. 15 calls maximum per scheduled run,
  paced at ~7 seconds/call to respect variable public API rate limits.

All calls are free and keyless. The CoinPaprika free/keyless API is intended for
**personal/non-commercial use with attribution** (“Powered by CoinPaprika”);
check licensing before commercial redistribution or deployment in a trading
company. CoinGecko public API rate limits are variable. Both services may
change their terms and accessible endpoints.

## Identity and provenance

CMC100 IDs come exclusively from the official snapshot in `docs/latest.json`.
Cross-provider matching requires an **exact normalized name AND ticker** and
rejects duplicates; it does not trust ambiguous symbol-only matches. The
system carries third-party source URLs and original observation timestamps.

The current full snapshot is retained in
`docs/intelligence/coin_profiles.json`; each of the 100 per-coin dossiers
references its own entry. Profiles are rechecked after 72 hours; public
per-coin events and market distributions are refreshed no more than every
24 hours. Failed provider requests never produce invented data.

## Quality gates (read all independently)

- `coverage_audit.json → per_coin → source_backed_substantive_project_background`:
  how many of the 100 coins have a sufficiently descriptive third-party
  project account, plus other meaningful project-specific fields.
- `coverage_audit.json → per_coin → coins_with_substantive_coinspecific_article_context`:
  how many coins independently received substantial asset-specific
  article/event evidence from the existing public-source research corpus.
- `research_quality_gate → project_background_context_status` and
  `coin_specific_event_text_status` remain **INCOMPLETE** until their
  respective independent requirements hold for all 100 coins.
- `coverage_audit.json → coin_descriptive_sources_audit → profile_gaps`:
  exact missing CMC IDs and symbols, with no automatic positive substitutions.
- `source_context_audit` continues to score the original **full** research
  corpus; the prior 16.42% source-depth baseline cannot be inflated by adding
  evergreen profiles or dropping low-quality search leads.

**Do not conflate** project descriptions, event listings, recent project
disclosures, first observed times and confirmed tradeable 24h catalysts.
The dataset explicitly preserves their separate status labels.

## Run and publication

The scheduled `CMC100 Free Open Intelligence – Broad Discovery` workflow
calls `src/free_open_intelligence.py --network` and publishes profile data,
per-coin dossiers and quality audit. Existing scheduled execution stays in
place. No new push-triggered workflow, paid API, token, proprietary data or
automated LLM calls were added.

Run the offline unit tests manually through the **workflow_dispatch-only**
`Stage 1 Evidence Regression Tests` workflow. No push-trigger test workflow
was introduced.

## Coin-specific article enrichment from opaque Google News links

When original publisher URLs are missing, `src/coin_news_resolution.py`
tries up to 32 previously unattempted Google News candidate links per run,
prioritizing coins with no substantive individual article. It accepts only
a normal redirect or documented canonical **direct publisher URL**, checks
public robots/access restrictions, extracts a limited attributed passage and
checks the coin identity again in the actual publisher text. It does not
decode Google News opaque IDs through unapproved services, evade paywalls,
or mark price stories as independently verified catalysts. Rejected links
stay in a seven-day retry history at
`docs/intelligence/google_news_resolution_history.json`.
Results are auditable separately in
`coverage_audit.json → safe_google_news_to_publisher_audit`; they only improve
the article coverage when substantive original text was actually retrieved.

## Publisher RSS/Atom, public releases and project-site articles

`src/coin_primary_feed_research.py` discovers RSS/Atom links from exact-linked
coin project websites, with robots checks. Dedicated-project feeds may use generic
titles if substantive body text identifies the project; multi-asset exchanges
require an asset match in both title and text. Probe results are stored with
a per-domain cooldown in `docs/intelligence/coin_feed_probe_history.json`.

`src/coin_repository_releases.py` retrieves source-linked software releases
using the **public GitHub REST API** (no API key). Repositories must be linked
by exact CMC-ID/name/ticker-matched provider profiles and pass explicit
identity safeguards. In particular, the unrelated Mimblewimble `BeamMW/beam`
repository is quarantined for CMC #28298 gaming BEAM. Source release notes
are labelled project software activity, **not** token-price catalysts.
Results and source failures persist in
`docs/intelligence/coin_repository_releases.json`.

`src/coin_project_sitemap_news.py` examines public project sitemaps and
links to newer blog/news pages, subject to HTTP, DNS, robots and text-depth
checks. Sitemap `lastmod` is *not* treated as a publication timestamp.
Results are preserved in
`docs/intelligence/coin_project_sitemap_history.json`.

`docs/intelligence/news_event_coverage.json` separately reports whether
each coin has substantive individual article/event context, plus items
with source-proven publication dates in the last 24h, 72h, and 7 days.
No reliable new article does **not** imply no event happened. All original
low-quality search leads remain in the full-corpus denominator.

The opaque Google News redirect experiment yielded **0 substantive original
articles out of 32 attempts**. The collector stops repeating that approach
after sustained failures rather than incurring unnecessary network load.

## Verified live result – 14 November 2026

A fresh Github Actions run at cutoff **2026-11-14T13:36:14Z** completed
successfully: workflow run
`https://github.com/SnakU4/crypto-market-data/actions/runs/43595070607`.

- **100/100** coins have individually distinct, substantive, source-backed
  **project background** descriptions.
- **56/100** coins now have substantive **individual news, software release,
  governance or project-article context**; **44/100** remain without adequate
  individual event/article context in the available source collection.
  This count increased from **42/100** during the current improvements.
- **17/100** coins have a source-published substantial event/article in the
  last 24 hours, **33/100** in the last 72 hours, and **34/100** in the last
  7 days. These are *source observations*, not verified market catalysts.
- The substantive original-corpus excerpt share is **19.75%**. The raw
  denominator is unchanged; background profile text does not inflate it.
- Official GitHub REST API retrievals produced **eight** additional
  substantive release notes in the initial successful run. Public website
  sitemap inspection found **three** original substantive articles for two
  projects in its first live run, at least one previously undercovered.
- The overall gate correctly remains **`PARTIAL_RESEARCH`**. Full
  coin-specific news coverage and independent causal verification are NOT
  complete.

For a zero-API-cost manual ChatGPT enrichment pass across the remaining
gaps and all 100 coins, use `EVENT_RESEARCH_MANUAL_PROMPT.md` together with
the latest GitHub Actions evidence artifact. The prompt distinguishes
source-backed events from `NO_VERIFIABLE_NEW_EVENT_FOUND` and
`NOT_YET_SEARCHED` and does not require inventing news for quiet coins.

The previous primary-documentation matching and source license warnings
continue to apply. All new additions are source-backed research **candidates**,
not trade signals, investment advice, or proof of source claims.
