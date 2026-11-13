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

Run the offline unit tests manually via `python -m unittest
tests/test_coin_context_sources.py` (or `unittest discover`).
The initial rollout has not yet established that 100/100 have qualifying
descriptive and event context. Missing coverage is an explicit, measurable
failure of the research target, not silently relabelled as completed.
