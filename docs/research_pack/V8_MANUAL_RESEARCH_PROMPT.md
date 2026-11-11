# CMC100 V8.1 — Manual research test with paper-compatible 1d attractiveness ranking

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

## Phase 4 — Paper-compatible 100-coin research scores

For EVERY official CMC100 constituent, investigate downside AND upside using the evidence ledger and open-ended independent inquiry. Keep the original CMC ID, name and token symbol in each output row.

**Use the published research framework from Sun, Wang & Zhang, Agentic AI Nowcasting and Cryptocurrency Return Predictability (2026). The exact original private model prompt is not public; replicate the disclosed scoring, ranking and public field structure, not an invented private decision algorithm.**

### A. Independent attractiveness fields (paper scale)

Return all six independent horizon-specific attractiveness scores:

- attractiveness_1h
- attractiveness_6h
- attractiveness_1d
- attractiveness_3d
- attractiveness_1w
- attractiveness_1m

Use the original bounded **−5.00 to +5.00** scoring convention in **0.05 increments**, where negative values indicate lower attractiveness and positive values higher attractiveness; 0.00 is neutral on this scale. This is an investment-attractiveness judgment, NOT a forecast percentage return, calibrated probability or fixed number of BUY / SELL recommendations.

The PRIMARY ranking variable and ONLY ranking variable for the one-day portfolio is attractiveness_1d.

**Do not continue using the old V8 0.00–1.00 score as the primary ranking.** If necessary for comparison against a legacy result, supply a separate calculated field legacy_v8_normalized=(attractiveness_1d + 5)/10. This conversion must NOT drive decisions or portfolio membership.

The other horizons are supporting assessments, not inputs to a weighted blend that substitutes for attractiveness_1d. Scores must arise from coin-specific reasoned judgment, not an automatic 7-day momentum rule, cross-sectional rank normalization, forced-score spread, arbitrary long/short quota, or uniform regime offset across 98 coins.

### B. Independent decision — NOT a ranking gate

Produce an additional **decision = BUY / WAIT / SELL** judgment for each asset, independently assessed from underlying evidence strength, downside/upside asymmetry and uncertainty.

- BUY, WAIT and SELL are **not** calculated by applying a threshold to attractiveness_1d.
- There is NO fixed numerical mapping from decision to attractiveness. A coin can be WAIT yet have negative or positive attractiveness.
- WAIT is an expression of insufficient standalone action conviction, not a mandatory score of 0.
- Do not imitate the historical BUY/WAIT/SELL frequencies or artificially manufacture signals to match the published data.
- No fabricated positive/negative price catalysts to push coins away from neutral.

Supply supporting evidence-quality labels, positive/negative 24h mechanisms, source IDs and uncertainty. Unknown factual coin mappings stay explicitly unverified.

### C. Supporting scores (separate fields, no formula imposed)

Also provide the four separately identified research fields in the authors' public panel:
market_sentiment, market_divergence, catalyst_score, overall_market_score.

Explain briefly the interpretation and scale actually used for these supporting assessments. Do NOT fabricate a proprietary scoring formula or equate any of them to the attractiveness_1d rank. The 1d attractiveness result is a direct final judgment, not mechanically computed from those four values.

## Phase 5 — Paper-compatible ranking and portfolio construction

**Rank every one of the 100 coins DESCENDING by attractiveness_1d, irrespective of decision.**

1. Primary LONG side: the 10 highest attractiveness_1d scores.
2. Primary SHORT side: the 10 lowest attractiveness_1d scores.
3. Full reference portfolio: equal-weight each side to **100% LONG and 100% SHORT**, **200% gross**, before any separate execution or eligibility filter.
4. BUY/WAIT/SELL must NEVER remove or add an asset to either ranking side. Neither the positive/negative sign of a score nor the WAIT share can reduce portfolio holdings.
5. Do not re-rank using confidence, news counts, evidence-quality grade, short-term momentum, token unlock severity or an additional risk factor. Those fields may annotate uncertainty, never override the paper score order.
6. If there are identical attractiveness_1d values, **preserve the ties**. Never invent finer-grained hidden scores or pretend that an arbitrary ticker/CMC-ID tiebreak is a superior investment signal.
7. Report the exact **10-name benchmark selection** only when the scores provide a unique boundary. If a tie crosses the 10th rank boundary, disclose the score and all boundary-tied members. Provide a clearly labelled **tie-aware inclusion sensitivity** that includes all coins tied at the boundary, with equal weights normalized to 100% on each leg. This can produce MORE than 10 included names on that leg; do not silently select arbitrary winners among ties.
8. If primary long and short sides overlap under extreme ties, report a **DEGENERATE / NON-DISCRIMINATING RANKING** and the overlap; do not fabricate an executable portfolio. Do not mix the tie-aware sensitivity portfolio with a unique ten-name benchmark.
9. For a secondary reproducibility-only 10-name list where strict 10 names are operationally required despite boundary ties, sort those tied candidates by ascending CMC ID, **explicitly label this as an arbitrary deterministic display/execution tiebreak**, and provide the alternate boundary-tied assets. Never present that arbitrary choice as research conviction.

This ranking stage must be a deterministic sort of the scores already issued by the AI. The AI must **not** revise its scores to create cleaner top/bottom portfolios or to reach a target number of BUY/SELL labels.

Reference paper: https://ssrn.com/abstract=7231679
Authors' public scoring panel and tie diagnostics: https://github.com/Moonooo24/agentic-ai-crypto-nowcasting
The released research data contain 1h, 6h, 1d, 3d, 1w, 1m attractiveness and an independent decision label. The full proprietary prompts are NOT publicly released, so exact replication of private internal reasoning cannot be claimed.

## Phase 6 — Mandatory output and independent quality audit

Deliver complete machine-readable CSV and/or JSON with **100 unique CMC IDs** and these **required columns**:

- cmc_id, coin_name, token_symbol
- attractiveness_1h, attractiveness_6h, attractiveness_1d, attractiveness_3d, attractiveness_1w, attractiveness_1m
- decision (BUY/WAIT/SELL)
- market_sentiment, market_divergence, catalyst_score, overall_market_score
- evidence_quality, research_status, evidence_ids, positive_drivers, negative_drivers, uncertainty, cutoff_utc
- rank_1d, top10_boundary_tie_status, bottom10_boundary_tie_status, rank_only_side, tie_aware_side

Issue three **independent outputs**:
A. prediction_panel_100: 100 original model judgments, before any portfolio logic.
B. paper_ranked_100: deterministic descending attractiveness_1d ranking, including all ties and boundary diagnostics.
C. paper_top10_bottom10: primary 10-per-side benchmark when unambiguous, plus separately identified boundary-tie sensitivity and optional reproducibility-only deterministic tiebreak.

Also deliver:
1. Evidence ledger (including rejected and disputed claims).
2. Full 100-coin source coverage and data-access audit (builder-processed archive vs raw files PERSONALLY read by the model).
3. Independently discovered new sources and new research directions.
4. Risk / contradiction report.
5. Evidence-based explanations for all ranking extremes (at least the top and bottom 10 or all boundary-tied coins).
6. BUY / WAIT / SELL class counts and separately 1d attractiveness-score distribution. These are DIFFERENT measurements.
7. Research-quality grade from 1 to 10, independent of technical infrastructure's 8.6/10 diagnostic and predictive trading performance.

**Consistency checks must pass:**
- exactly 100 distinct official CMC IDs; no missing, invented or duplicated coin;
- all 1d scores within −5 to +5 on a 0.05 grid; all six horizon fields present;
- all 100 decisions in {BUY,WAIT,SELL}, assigned independently;
- ranking is monotonic descending in attractiveness_1d;
- no BUY/WAIT/SELL filter, uniform trend penalty or arbitrary extra ranking variable;
- each portfolio side has total weight 1.0 where defined, and ties/overlap are disclosed;
- rank membership uses the model's ORIGINAL 1d scores without retrofitting.

Quantify how many coins have at least one independently verified, newly relevant 24h catalyst, how many have only market-state information, and how many lack adequate evidence. 100 generic scores are NOT evidence of a comprehensive research investigation.

Mark PARTIAL_RESEARCH if critical source files were not read, the universe is incomplete, or research is materially deficient. Never claim exact reproduction of the undisclosed original prompt or a trading alpha from one manual test.

## Prospective cutoff protection

Before creating final forecasts, define the research cutoff UTC. Only count information that was accessible by that time; never use later outcome data. Record if source snapshots predate the forecast cutoff by many hours. This is a MANUAL PROMPT test, not an execution or forward-performance measurement.
