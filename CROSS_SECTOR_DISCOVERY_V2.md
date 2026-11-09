# Cross-Sector Discovery v2 — collect first, interpret later

This change revises only `src/adjacent_discovery.py` and its associated tests. The existing official CMC100 market collector, DeFi collector, daily V6 forecast task and GitHub workflow schedule are not changed.

## Responsibility boundary

- **Stage 1: observation.** Capture public, timestamped technological/scientific/news/developer/community leads without mapping them to CMC IDs, ranking them for tokens or predicting a market direction. The word “Avalanche” in a scientific title is just a word. **No `coins_for()` or `candidate_coin_ids`.**
- **Stage 2: reasoning (not implemented here).** AI opens selected primary material, investigates first- and second-order implications, verifies hypotheses, resolves entities and searches for counterevidence. A news item may have no relevant crypto consequence.
- **Market data remain different.** The upstream `docs/latest.json` still validates 100 distinct official CMC IDs. Its spot/perp observations remain instrument-keyed for integrity; anomaly-triggered searches use full coin names but cannot label unrelated research as a catalyst.

## Data retention and selection

The collector still has **finite per-request source limits** (e.g. bounded RSS entries, API page sizes) and no claim of entire-Internet coverage. Within the leads actually fetched and passed validation:

1. `docs/discovery/archive/YYYYMMDD/*_discovery.json`: **all unique captured leads** for each run; never truncated at the former global 500 record limit. Includes published/observed/first-observed timestamps, original URLs, per-source attribution, available provider excerpts, optional theme navigation and source audit. Archives remain immutable within the workflow; newer runs create new files.
2. `docs/discovery/leads.csv`: **all unique leads from the latest run** for bulk inspection. Its rows no longer contain coin tags.
3. `docs/discovery/latest.json`: bounded **500-entry connector read index**, selected in a deterministic round-robin over *source families* and then *individual source feeds*. Coin names, market reactions, sentiment and theme tags are never used to decide which leads enter this read index.
4. `docs/discovery/read_index.csv`: same balanced 500-entry index, for convenient inspection.
5. `docs/discovery/status.json`: explicitly counts full archive vs. read index, records selection strategy, full/index source and family distributions, excerpt availability, missing sources and the exact full archive path.
6. `docs/discovery/first_seen.json`: sticky first observed timestamp, preserved from earlier runs when canonical identifiers agree.

The full immutable archive is the authoritative source for Stage 2; the balanced index is only its navigation layer. The index can be filtered or prioritized *later* by an AI investigator without deleting candidates from the archived observation set.

## Context and limitations

- RSS/Atom: store short **publisher-provided** descriptions/abstracts (up to 360 characters; arXiv up to 650), stripped of markup; never scrape entire copyrighted articles.
- GitHub releases/security advisories: preserve short author-supplied body/description excerpts (up to 520 characters), release repo, published/created time and canonical URL.
- Hacker News: source story text excerpt when published in returned public API result (up to 400 characters), engagement and discussion URL.
- Bluesky: public post text/engagement if API works; it was blocked (403) in the 2026-11-09 run. X, Reddit and restricted communities remain explicitly unavailable until authorized access is validated.
- Google/GDELT: headline and provenance only where a description is not part of the response. A theme tag is only a string-search navigation hint, not a causal token claim.
- Deduplication now retains meaningful URL query parameters such as `?id=123`, stripping only recognized tracking parameters. This can cause some old `first_seen` hashes to change; old archives remain unchanged.

**Important:** Growing immutable archives in a Git repository increase repository size. Check Actions output and repository size; if retention becomes material, migrate older archives to immutable external object storage or GitHub Actions artifacts with a PIT hash manifest and documented retention. Do not silently drop records.

## Acceptance tests

Run from repo root:

```sh
python -m unittest discover -s tests -p 'test_adjacent_discovery.py' -v
```

Required properties:

- 100 IDs verified in upstream market snapshot.
- No coin matcher, no `candidate_coin_ids` and no price-impact labeling in collector output.
- Exact same index selection even when coin names or optional themes change, all else equal.
- Rare source families cannot be displaced by many recent arXiv or Google News results.
- Full archive contains every captured unique observation even when index is capped at 500.
- Per-source failed reads, missing publication timestamps, unverified causal relevance and provider-access gaps remain visible.

## Deployment

Merge the PR, then manually run **Actions → Cross-Sector Crypto Discovery → Run workflow**. Check the revised `docs/discovery/status.json` for `coin_matching_performed=false`, `full_archive_leads >= read_index_leads`, a plausible `full_archive_path`, and non-zero source-family breadth. Confirm that the file identified by `full_archive_path` exists and contains the same count as `full_archive_leads`.

The downstream V6 forecasting prompt is not changed automatically. It must later be updated to read `docs/discovery/latest.json` for discovery navigation and `status.full_archive_path` for full evidentiary access rather than relying on removed `per_coin_candidate_counts`.