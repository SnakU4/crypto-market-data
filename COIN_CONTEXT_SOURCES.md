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

## Live verification, 14 November 2026

Multiple direct GitHub Actions runs of the `CMC100 Free Open Intelligence`
workflow passed. At the latest verified run, **100/100** CMC100 coins had
substantive source-linked individual **project background**. This is achieved
through 98 substantial third-party profiles plus complementary original issuer
documentation; eight original-issuer dossiers were extracted successfully.

Every individual dossier has a source and identity association. Further audits
require 100 distinct meaningful narrative excerpts (no repeated boilerplate)
and explicitly reject insufficient or duplicated accounts.

**Still NOT complete:** only **41/100** coins have substantive *individual
article/event text*, leaving **59/100** without enough coin-specific news
detail. The full original-corpus substantive excerpt ratio was **18.75%**,
below the 20% threshold. The overall status therefore remains
`PARTIAL_RESEARCH`, independent of complete background coverage.
Event announcements cannot be inferred from static profiles. Primary-source
claims and 24-hour price effects are not independently verified by this system.

The source context pipeline now also includes
`src/targeted_primary_context.py` (16 explicit CMC ID, name, and symbol
mappings to official issuer or distinctly labelled secondary exchange
documentation). See `docs/intelligence/primary_coin_context.json` and
`coverage_audit.json → curated_original_project_sources_audit`.
The 402/403/404 public-endpoint issue is handled by stopping repeated
large-scale calls after a limited probe. Public rate limits, source licensing
and availability can change.
