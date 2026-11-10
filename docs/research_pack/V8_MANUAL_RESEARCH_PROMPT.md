# CMC100 V8 – Manual research test (copy into a new chat with GitHub + Web Search)

## Mission

Assess the prospective relative attractiveness for the next 24 hours of **all 100 official CMC100 assets**, using genuine open-ended investigation. This is a **manual quality test**, not a scheduled agent, backtest, live order, or trading recommendation. Do not assume that the existing source list captures all possible relevant information.

The research engine already processed the complete archived raw data. Your job is to independently **interpret, verify and extend** it—not to award scores for the number of observed API records.

## Mandatory input sequence

Repository: https://github.com/SnakU4/crypto-market-data

Read with the GitHub connector:

1. docs/research_pack/manifest.json. Verify the source-capture dates, SHA-verified archive counts, coverage and quarantine counts. Check that all 100 coin cards were produced and all five batch checksums are available.
2. ALL FIVE files:
   - docs/research_pack/coin_batches/batch_01.json
   - docs/research_pack/coin_batches/batch_02.json
   - docs/research_pack/coin_batches/batch_03.json
   - docs/research_pack/coin_batches/batch_04.json
   - docs/research_pack/coin_batches/batch_05.json

   Count 100 unique CMC IDs. Do not stop after a single batch or the first 20 coins.

3. docs/research_pack/global_context.json and docs/research_pack/research_queue.json. These contain genuinely unmatched cross-sector leads, observed market changes, potential token-unlock calendars and sampled network transactions. Preserve all uncertainty labels.
4. When source details matter, read docs/evidence_engine/status.json and docs/expanded_discovery/status.json, and, if actually accessible, the **plain UTF-8 complete JSONL files** in the latest GitHub Actions artifact titled CMC100-V8-Full-Evidence-Pack (workflow: CMC100 V8 Research Evidence Pack). You can also ask for the artifact ZIP to be uploaded in the chat.

IMPORTANT distinction: 'archive full_archive_read=true' means the deterministic Python builder read and audited every raw record. **It does not mean you personally analysed all 10,000+ discovery leads or the raw JSONL files.** Do not claim full independent verification if you only read the condensed coin cards.

If files are inaccessible, report exactly which input was missing; mark the test PARTIAL rather than silently substituting guesses.

## Phase 1 — Research readiness audit

State: 100/100 coins loaded, read batch count, exact and unverified entity matching, substantive source coverage, age of observations and archive integrity. Distinguish the 77 currently instrument-anchored coins from independently verified on-chain token identities. Do not count Google News query matching as token identification.

For each evidence item remember:
- 'S:' indicates a structured provider observation, with captured time, not necessarily a published event.
- 'D:' indicates a discovery search lead, whose association with a coin is NOT independently verified.
- A token-unlock schedule candidate is a third-party estimate until official vesting or project confirmation.
- A random BTC/ETH transaction is NOT automatically an exchange inflow/outflow.
- Funding, OI, TVL, supply and fees are quantitative market state. Identify true new information vs repeated observations.

## Phase 2 — Independent open-ended exploration

Generate and follow your OWN research hypotheses, beyond the fixed source list. Investigate every plausible channel that could affect 24h expectations: protocol releases and security, project communications, governance, derivatives positioning and liquidation, order-book and liquidity, token vesting and real on-chain transfers, DEX/protocol economics, institutional and regulatory flows, funding rates and OI, sector rotations, macroeconomic catalysts, communities and new event categories discovered while researching.

Do not merely summarise GitHub data. Seek primary evidence and independent corroboration, including negative and contradictory information. Record also rejected hypotheses and research areas with missing/blocked data.

Prioritise factual freshness for real prospective forecasts, but for an explicit archived architecture test report age separately rather than pretending a historical observation was available earlier than it was.

## Phase 3 — Evidence ledger BEFORE forecasting

Construct an evidence ledger. Each material claim requires:
- exact CMC ID or a justified global scope;
- evidence ID S: or D: if from the pack, plus the original URL;
- concrete claim and precise publication / event / first-observed times as available;
- independent validation: VERIFIED_PRIMARY, CORROBORATED, SECONDARY_ONLY, or UNVERIFIED;
- whether it is actually new, repeated, dated for the future, or merely market state;
- plausible 24h mechanism, competing explanation and already-priced risk.

Do not infer coin-specific price direction from chain-wide statistics without a demonstrated token value-accrual or causal link.

## Phase 4 — Independent 100-coin assessments

Analyse BOTH upside and downside for all 100 CMC IDs, and evaluate relative 24h attractiveness on the original 0.00–1.00 scale in increments of 0.05. No quota for Long/Short, no cross-sectional normalization and no requirement for a positive mean.

The score must be an **outcome of reasoned research**, not a mechanical 7-day-return / trend score plus a uniform regime offset. Where no corroborated catalyst exists, explicitly state 'MARKET_STATE_ONLY' or 'INSUFFICIENT_EVIDENCE'. Avoid making up differentiated narrative. For each asset supply:
- CMC ID, name, symbol and attractiveness_1d;
- short-side drivers AND long-side drivers;
- specific evidence references and identity/relevance status;
- already-priced / stale-content considerations;
- uncertainty and evidence-quality grade;
- 24h expected direction with no claim of calibrated hit rate.

Use fewer words per coin when no material evidence exists rather than inventing apparently detailed but unsupported forecasts.

## Phase 5 — Output and independent quality audit

Deliver a complete structured CSV/JSON with all 100 predictions, plus:
1. Detailed evidence ledger (including rejected/disputed claims).
2. Real source coverage audit (which complete batch files were **personally** read vs builder-processed).
3. New-source discovery log (new searches and links, not a copy of the source list).
4. Risk and contradiction report.
5. Detailed explanation for at least Top 10 and Bottom 10, with primary confirmations where possible.
6. Research-quality grade **1–10**, distinct from technical Evidence Engine's 8.6/10 engineering diagnostic.

Explicitly quantify: how many coins have at least one independently validated, 24h-relevant NEW factual catalyst, how many are market-only, and how many lack suitable data. Do not count 100 generic trend-based scores as a complete evidence investigation.

**Reject test as PARTIAL_RESEARCH** if critical source files cannot be accessed or coin coverage is incomplete; explain which additional review must be performed. Even with full archive ingestion, a 9/10 research score requires genuine sourced reasoning, original investigation and 24h causality, not a cosmetic score inflation.

## Prospective cutoff protection

Before creating final forecasts, define the research cutoff UTC. Only count information that was accessible by that time; never use later outcome data. Record if source snapshots predate the forecast cutoff by many hours. This is a MANUAL PROMPT test, not an execution or forward-performance measurement.
