# Expanded Evidence Discovery v4 — richer Stage 1, not Stage 2

## Changes

1. **Content depth.** RSS/Atom `content:encoded` or Atom `content` is considered before short description fields. The public article enrichment pass attempts at most 80 eligible non-Google URLs per run (configurable through `DISCOVERY_ARTICLE_BUDGET`, hard cap 200). It records up to 1,600 text characters from an HTML article or the page's description metadata, **not complete copyrighted articles**. Requests have a seven-second timeout and 350 KB transfer cap; unsuccessful, blocked and short content is explicitly labelled. Google News opaque redirects are not treated as acquired article text. There is no paid API and no bypass of login/paywalls/robots requirements; publishers may disallow access.

2. **Direct evidence.** In addition to the prior 800 coin-scoped Google News searches, 24 cross-sector searches, governance RSS feeds, non-crypto research RSS feeds and 12 HN searches, there are 18 direct project-owned blogs, core development and GitHub release Atom feeds. Availability varies; every failure is audited in `source_audit.csv`. **These feeds do not claim to cover all 100 coins**; all 100 retain their existing eight broad searches. Further official project feeds can be added after verifying actual availability and usefulness.

3. **Information quality.** Raw leads are **never silently thrown away** for lacking token names. The complete eligible URL archive remains available. Each lead receives `content_quality`, `excerpt_adds_information`, `information_status`, `same_title_url_count`, `article_fetch_status`, and `context_origin`. Exact/near-exact normalized headline syndication is tagged rather than deleted. A short/overlapping description is **not** counted as substantive. The heuristic is an audit approximation, not semantic verification; labels are not forecasts or coin matches.

4. **Daily novelty.** `docs/expanded_discovery/daily_metrics.json` retains the last 120 run-level metrics and a UTC daily aggregate. Report `new_url_leads` and `new_urls_with_substantive_context` separately. `first_run_baseline` flags the initial collection; the initial 9,940 URLs must never be presented as daily natural growth. Novelty is determined against the persisted rolling 14-day registry, **not** all-time global distinctness. The `new_title_clusters_within_run` value is approximate and does not prove novelty compared with all previous runs.

## Operational checks

- Run **CMC100 Expanded Evidence Discovery** with `workflow_dispatch` or inspect the next scheduled run.
- Verify the GitHub Actions test step; the workflow runs `test_*discovery*.py`.
- Inspect `docs/expanded_discovery/status.json` → `information_quality`, `new_urls_by_source_family`, `incremental_new_url_leads`, `incremental_new_urls_with_substantive_context`.
- Inspect `docs/expanded_discovery/daily_metrics.json`: compare subsequent run totals; **do not** count the baseline day as a daily acquisition rate.
- Inspect `source_audit.csv` to see which direct feeds actually responded.
- Check `latest_shards` for `PUBLIC_ARTICLE_EXTRACT` vs `TITLE_EQUIVALENT_OR_SHORT`. The 97.6% previously non-informative excerpt figure remains the baseline until the next live run confirms improvement.

## Limits and next decisions

Direct article extraction covers a capped sample for performance and respecting publisher access. It is deliberately **not an uncontrolled 10,000-URL scraper**. Headlines from Google News RSS may still dominate. To materially enlarge coverage later, add compliant publisher APIs, direct issuer feeds, official GitHub events, authorized Reddit/community APIs, and a budgeted per-source scheduling tier. A validated Stage-2 causal analysis requires **source claims**, time-valid evidence, coin identity resolution, and independent corroboration — none is claimed here.

This upgrade does not change trading, ranking, or crypto forecast behaviour.
