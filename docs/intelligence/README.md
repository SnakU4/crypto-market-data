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
The workflow limits itself to 20 adaptive RSS searches and 12 bounded publisher
article fetches per execution; no paywall bypass or unauthorized social scraping.

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
   bounded to 48 attempts per normal run, max 5 per host.
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

Current free integrated quality gate: TECHNICAL PASS, MATERIAL RESEARCH
PARTIAL. Approximately 5.4% of canonical event leads contain materially
additional readable context; only 6 direct publisher excerpts were
extracted in the tested run. A large URL count or technical coverage must
not be interpreted as evidence completeness or prediction skill.

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
