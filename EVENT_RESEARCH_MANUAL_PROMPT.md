# Manual ChatGPT research – CMC100 NEWS & EVENTS, evidence-first (no API cost)

**Purpose.** Deepen the existing GitHub data collection without fabricating an
article for every coin. Project profiles are already complete; this work is
specifically for recent source-backed events and their relevant context.

## Inputs

Upload the most recent GitHub Actions artifact
\`CMC100-Free-Open-Intelligence-Evidence\`, or supply its contents:
\`manifest.json\`, \`news_event_coverage.json\`, \`coverage_audit.json\`,
\`deep_research_queue.json\`, five \`coin_batches/*.json\` files and
\`publisher_excerpts.json\`. Use \`manifest.cutoff_utc\` as the known
reference point. Verify all 100 CMC IDs against the official \`docs/latest.json\`
snapshot; do not remap on ticker alone.

## The prompt (copy into a normal ChatGPT conversation)

Act as an evidence-first crypto market researcher. I am supplying a complete
CMC100 GitHub source bundle and want a **manually researched source-enrichment
pass** across the entire universe, prioritizing those with the weakest
individual NEWS/EVENT context in \`news_event_coverage.json\`.

**Source discovery:**
1. Work outward, not from a fixed list. For each undercovered coin, search
   independently for first-party project release notes, protocol/consensus
   upgrades, governance votes and proposals, vesting/token-unlock schedules,
   supply/burn notices, security disclosures, ecosystem integrations,
   exchange listing/delisting announcements, regulatory filings, legal
   announcements, institutional flows, on-chain anomalies and derivative
   positioning. Investigate relevant global/sector developments and their
   exact asset linkage separately. Expand to new projects, non-English
   sources, independently reported news and community discussions when useful.
2. Follow original publisher links and read meaningful body text. Do not call
   a duplicated headline, generic token profile, price prediction, SEO page,
   automated bot post, or a list of links substantive event research.
3. Record project and asset identity by CMC ID + name + ticker and a
   corroborated link to the relevant project, contract, organization or
   network. Quarantine symbol collisions. A GitHub release of a connected
   repository is **technical project activity**, not proven token impact.
4. Use real document publication times when available, with separate
   timestamps for the date an underlying event occurs and the time it was
   first observable to this research. Distinguish 0–24h, 24–72h, 3–7d and
   longer background. Unknown publication time must remain UNKNOWN.
5. Cite a source URL and summarize the concrete new information in your
   own words: **what changed, when, who is involved, why it matters, which
   token mechanism could be affected, and what remains uncertain.** Clearly
   label competing explanations, unresolved information and evidence gaps.
6. Cross-check material claims with a second, independent source where
   feasible. The absence of an article after a broad source search must be
   labeled \`NO_VERIFIABLE_NEW_EVENT_FOUND\`, not
   \`PROJECT_NOT_RESEARCHED\` or an invented claim.
7. Do not infer price direction, forecasts, profitability or alpha from
   the number of articles or from vendor/source assertions. Save structured
   evidence suitable for a later separate quantitative assessment.

**Mandatory outputs:**
- A **coverage table for all 100 CMC IDs** with source families actually
  investigated, newest reliable dated publication, newest substantive
  event, and explicit status \`SUBSTANTIVE_CURRENT\`,
  \`SUBSTANTIVE_OLDER\`, \`SEARCHED_NO_VERIFIABLE_EVENT\`,
  \`ACCESS_LIMITED\` or \`NOT_YET_SEARCHED\`.
- A **source-backed event ledger** with short original-source excerpts
  (not full copied articles), publisher URL, observed UTC, source-published
  UTC if known, event date if distinct, mapped CMC IDs, source class,
  factual finding, possible mechanism and uncertainty. Include negative
  evidence and new cross-sector discoveries. No contentless placeholders.
- A **gap report** describing which exact source categories or direct
  publisher texts remain inaccessible, and what was tried, per coin.
- An append-only **\`findings.jsonl\`** compatible with
  \`docs/intelligence/manual_inputs/findings.jsonl\`. Include only findings
  that satisfy the schema:
  \`id\`, \`title\`, \`scope\` (ASSET/MULTI_ASSET/SECTOR/GLOBAL),
  \`cmc_ids\` when asset-scoped, \`source_url\`, \`source_excerpt\`,
  \`published_utc\` when proven, \`first_observed_utc\` as the **actual
  UTC time the document was first found in this manual investigation**,
  \`reviewer: "chatgpt_manual"\`, \`verification_note\`.
  The first-observed time must never be invented or backdated. Exclude
  unverifiable claim-only headlines from that file.

Do not stop once a few promising major coins have good news. Use explicit
progress counters **research attempted / 100**, **real substantive news
observed / 100**, **coins lacking independently accessible source text / 100**.
If time or context limits prevent finishing the universe, output partial
real findings, identify exactly which CMC IDs were not yet checked and
never claim 100/100 review.

**No paid APIs, automated LLM API calls or automatic trade recommendations.**
Use ChatGPT's ordinary manual conversation/research and publicly accessible
sources, obeying access controls and publisher policies.

## Interpretation

A 100/100 **substantive project background** metric does NOT prove there were
100 real news events. The pass/fail quality criterion is whether every coin
was seriously investigated with honest source coverage, not a requirement to
invent an event for each coin. Verified current events, old project releases,
and unsupported search leads must remain separate in every output.
