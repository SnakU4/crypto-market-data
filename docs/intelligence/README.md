# CMC100 Free Open Intelligence — Architecture and operator guide (v1)

## Target and cost constraint

Produce an open-ended research *evidence base* for **all 100 official CMC100 assets**
and the global, industry, technology, macroeconomic, geopolitical and market-wide
environment in which they trade. An item may be GLOBAL, SECTOR, ASSET_CANDIDATE,
or UNRESOLVED. Never discard useful information merely because it has no verified
token link. No forecast, portfolio ranking or BUY/WAIT/SELL labels in this layer.

**Operating mode:** public GitHub Actions standard runners + public/free sources.
No API key or credit-card requirement, **zero paid LLM/API calls** in this pipeline.
Standard public-repository Actions usage is free subject to GitHub's terms and
reasonable execution/storage limits; external services can rate-limit or block.
The workflow limits itself to 20 adaptive RSS searches, 80 bounded public
publisher article attempts and 14 candidate-domain feed-discovery checks per
execution; no paywall bypass or unauthorized social scraping. External access
failures are retained in the audit, never hidden.

## What has been implemented and actually runs

1. Five input planes, including the official market snapshot, are integrated:
   - docs/latest.json (official 100 CMC IDs and market context)
   - docs/evidence_engine/archive + status.json (SHA-verified structured source archive)
   - docs/expanded_discovery/archive + status.json (SHA-verified full multi-theme search archive)
   - docs/research/latest.json + status.json (wide DeFi, derivatives, order-book, market and event collection)
   - docs/discovery/archive + status.json (FULL adjacent-sector archive, not the truncated read index)
2. Coin identity is conserved as official CMC ID. News search origin is *candidate*
   relevance only. QNT/OKX QNT-USDT-SWAP is explicitly quarantined pending
   trustworthy instrument/product confirmation. No false contract verification.
3. Dynamic, free follow-up queries are derived from **cross-source emergent phrases,
   unusual observed market states, and unattributed substantive leads**.
   The workflow **executes** public RSS searches. Returned findings can trigger a
   second wave of different queries. These are deterministic open-discovery heuristics,
   NOT an autonomous LLM researcher or verified market explanations.
4. Independently preserved global / sector / coin / unresolved content,
   with timestamps, source URLs, origin labels and explicit identity uncertainty.
5. Short attributable snippets for accessible public publisher articles, respecting
   robots.txt; it does NOT archive full copyrighted articles. Publisher feed
   summaries are retained instead of dropped. Direct source extracts
   flow BACK into the global/sector/asset dossiers; prior versions exported
   them separately without enriching the dossiers. Extraction now checks
   article/main HTML and RSS/Atom descriptions. The publisher budget is
   bounded to 80 attempts per normal run, max 5 per host.
6. SHA-checked full evidence index and status in a workflow artifact. Compact
   results are published to docs/intelligence/. Source archives stay where they are.

## Outputs

- manifest.json: timestamps, SHA/audit, full export references and free-cost assurance
- coverage_audit.json: effective data coverage; true source-context and mismatch counts;
  source failures; adaptive search status, not an invented 9/10 quality score
- global_intelligence.json: global/unresolved leads, original market context and follow-up output
- sector_intelligence.json: industry and multi-sector events, regardless of token linkage
- coin_batches/batch_01..05.json: 100 official CMC IDs, quantitative observations,
  asset-level evidence *candidates* and limitations
- open_discovery.json: cross-source emerging concepts, original evidence references
- research_tasks.json: actual queries, evidence triggers, completed/failed statuses and result counts
- publisher_excerpts.json: short public page excerpts with source URLs
- deep_research_queue.json: diversified contextual research leads (up to 300),
  with sources and undercovered coins; separate from the COMPLETE raw archives
- MANUAL_CHATGPT_RESEARCH_PROMPT.md: executable manual ChatGPT research
  instructions, open-ended global/sector/coin discovery and independent Web research
- knowledge_index.json: lead and scope counts; no generated prediction
- discovered_public_feeds.json: bounded RSS/Atom autodiscovery from the
  actually observed publisher-domain registry, including transparent errors
- source_probe_history.json: 72-hour cooldown per publisher domain; the next
  free run tests DIFFERENT domains rather than repeating the same failures
- direct publisher content from dozens of new official project GitHub release
  feeds, public governance forums, central-bank releases, plus independent
  cross-sector technology and infrastructure sources. This is an evolving
  starter set, not the limit of allowed information sources
- docs/research/source_events_manifest.json: all original research events
  in SHA-verified 80-row batch files. latest.json keeps a readable 200-row
  index; this prevents GitHub API's 1MB content limit from hiding actual work
- coverage_audit.json/source_context_audit: separately measure *directly*
  sourced contextual information versus Google News aggregator headline leads;
  published-last-24h/72h data stop old rich release notes from being mistaken
  for fresh 24h evidence. The historical full-corpus denominator stays intact
- source_registry_proposals.json: publisher domains discovered from actual evidence;
  candidates are not auto-installed or trusted without access/identity review
- coverage_audit.json/research_quality_gate: explicitly PARTIAL_RESEARCH
  if substantive context or deep article coverage is too low
- Actions artifact: export/evidence_index.jsonl — full deduplicated source index,
  includes origin/provenance IDs and late adaptive searches

**Run it:** GitHub → Actions → "CMC100 Free Open Intelligence – Broad Discovery" →
"Run workflow", or let the bounded twice-daily schedule execute. No secrets.

**Manual ChatGPT research at no extra model API cost:** Open
docs/intelligence/MANUAL_CHATGPT_RESEARCH_PROMPT.md and paste its full
instructions into a new ChatGPT conversation with GitHub and Web available.
This is the primary next-step qualitative research process; the GitHub
Python workflow does NOT attempt autonomous semantic analysis.

The manual prompt reads raw coverage plus the more substantive 300-item
source-diverse queue, then independently explores new global/sector/coin
questions, verifies primary claims and preserves unlinked global
information. The low full-corpus coverage share must remain in the audit.

In a normal chat ask the
assistant to inspect manifest, global_intelligence, sector_intelligence, all five
coin batches, research_tasks, publisher_excerpts and the Actions artifact.
Allow additional open web exploration, especially of unverified primary-source
claims and unknown global-to-sector relationships. Ask it to preserve all fact
citations and mark **facts vs hypotheses**, investigate any fresh research topic
not in the initial taxonomy, and only subsequently produce the paper-compatible
individual attractiveness scores. This is interactive use of ChatGPT, NOT a free
unattended model hosted inside GitHub.

## Objective acceptance criteria (do not optimize a subjective 6.x rating)

- 100 unique official CMC IDs, five batches, no ticker-based fabricated identity
- all four original research pipelines read; both large archives SHA-checked
- complete adjacent archive read rather than only the 500-result index
- global and sector leads explicitly exist even without coin association
- adaptive search includes actual searches, query/result audit and follow-up hop
- actionable depth: increase *verified, independently sourceable research facts*,
  not merely URL count or characters in excerpts
- accurate absence labels for OI history, ETF flows, options, wallet labels, token unlocks
- point-in-time cutoff and no future information
- repeatable test suite and strict CI acceptance

**Current limitations:** The free adaptive search is not capable of full semantic
open-ended multi-hop investigative reasoning. Google News often exposes titles
rather than resolved articles; source text still needs deeper authorized
retrieval and manual/ChatGPT evaluation. Neither 100% substantive article
coverage nor 24h alpha has been demonstrated. Meaningful historical changes in
funding, OI, net flows, governance and supply still need per-provider,
point-in-time data enhancements. If the next few runs show only more URLs and
no substantive facts, this version is **not a successful research solution**.

## Failed source-access experiment — 12 Nov 2026

An actual free test of Google News link resolution was conducted in the
expanded-discovery GitHub workflow. **80 links were attempted; 0 resolved.**
The resolution budget was restored to 0 rather than spending repeated
GitHub runner time on an unproductive path. This does not imply that
underlying original publisher information is unavailable: it means the
current direct-link resolver cannot retrieve it reliably. Prioritize
public primary RSS feeds, release documents, direct publisher pages,
official APIs, and authorized source-domain research.

Baseline before the source-first expansion (12 November 2026):
TECHNICAL PASS, MATERIAL RESEARCH PARTIAL, 5.56% substantive context
(603 of 10,838 canonical leads). The source-first rollout added 48 direct
primary/governance/technology sources and audited the achieved result
against this fixed initial baseline. Do not claim the remaining generic
Google News titles are substantive facts. Earlier measured ~5.4% of
canonical event leads contained materially
additional readable context; only 6 direct publisher excerpts were
extracted in the tested run. A large URL count or technical coverage must
not be interpreted as evidence completeness or prediction skill.

## Source-first acceptance measurements – 12 November 2026

- Baseline raw headline-inclusive corpus: 603/10,838 (5.56%) with
  additional substantive excerpt content.
- Source-first intermediate acceptance: 941/10,617 (8.86%) without
  dropping the low-information Google News titles from the denominator.
- Direct original research sources: 596/817 (72.95%) with contextual text,
  BUT only 121 of these direct-source substantive items had a known
  publication time within the last 72 hours. Rich archival release notes
  must not be mistaken for fresh, coin-relevant 24h catalysts.
- Full source collector: 48 new original release/governance/macro feeds
  were added to the source list; 47 responded successfully in the tested
  runs. The combined set of data requests also includes many non-news
  quantitative endpoints. These counts are NOT distinct verified claims.
- The complete direct-source event stream is available in 13 SHA-verified
  event batch files (965 rows at the measured capture) rather than an
  inaccessible oversized latest.json.
- The source-first expansion remained PARTIAL_RESEARCH: 78 official
  coins had no substantive individual news lead at the last audit.
  Global, sector and quantitative findings are preserved nevertheless.
- Dynamically advertised publisher feeds are checked within small,
  reproducible limits. The first attempted domains included previously
  known feeds, repeated access restrictions and weak-context feeds. The
  cumulative cooldown history now makes future discovery explore
  untested domains, not inflate findings through duplicates.

These are independently rerunnable source-coverage tests, NOT claims that
any token's next-day return is predictably explained. **Do not optimize
the 8.86% solely by removing unresolvable Google headlines**; keep the
raw coverage and original-source quality metrics distinct.

## Verified free source-first improvement – 13 November 2026

Two controlled integrations were completed successfully, without paid APIs
or model calls. The subsequent workflow files are **not triggered by each
code commit**; unit tests now run only on explicit manual dispatch.

| Audited measure | Before | After |
| --- | ---: | ---: |
| Substantive context among ALL canonical leads | 8.87% | **16.42%** |
| Numerator | 941 | **2,114** |
| Denominator, including unresolved Google News titles | 10,617 | **12,877** |
| Direct original-source research context | 72.95% | **69.62%** |
| Full original-source events retained in SHA batches | 965 | **2,893** |
| Successful source acquisition attempts | 150 | **261** |
| Contextualized DIRECT source items published within previous 72h | N/A | **887** |
| Coins with curated project-source context | N/A | **36** |
| Coins with substantive project-source context | N/A | **33** |
| Coin identities in official universe | 100 | **100** |

All sources retained unverified causal and price-effect annotations. **No
independently verified 24h price-causality claims** were produced by Python.
The *raw full-corpus denominator is still 12,877*, so 16.42% is not
achieved by dropping poor Google News titles. The original 5.56% baseline
predates the first source-first wave. Publication freshness and protocol
context are separate fields; do not conflate stale releases with new events.

Verified acceptance file: docs/intelligence/source_first_acceptance.json
GitHub Actions run: https://github.com/SnakU4/crypto-market-data/actions/runs/43383831804

Source status remains PARTIAL_RESEARCH, not a guarantee of useful alpha.
60 coins still have no substantive **individual news item**, while 33
have substantive curated project/developer/governance context that is
**not a verified token catalyst**. The manual ChatGPT investigation remains
separate and has not been started as part of this source expansion.

### Email-noise reduction

The separate regression tests are now manual-only in
.github/workflows/quality-tests.yml. Scheduled production collection
validates syntax and data-integrity, not the full unit test suite on
every change. The one-shot acceptance workflow's push trigger is removed
after the successful run. GitHub notification preferences belong to
the user's account (Settings → Notifications → System → Actions).
Disabling workflow emails there does NOT disable the Actions run history.

## Next evidence-led improvement sequence, only after measuring actual outputs

1. Inspect 20 sampled cross-sector and 20 candidate coin-event leads. Count
   independently useful factual claims and unresolved ambiguities.
2. Repair failing high-value primary-source URLs; expand legally accessible
   article metadata/context and exchange/contract identity registries.
3. Add genuine observed PIT time-series and matched-unit derivatives/DeFi data.
4. Use manually verified ChatGPT explorations to validate new topic/source
   discovery and build a registry of useful new sources (no automated unsafe code
   execution or automatic trust escalation).
5. Only then assess whether the *independent* paper-compatible forecast ranking
   improves against the old V8.x research inputs.

No trading recommendations, no measured 24h skill, no proof that all internet
sources have been investigated.
