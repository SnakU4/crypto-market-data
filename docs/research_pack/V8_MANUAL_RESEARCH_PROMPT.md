# CMC100 V8.2 — Evidence-calibrated individual assessment and unchanged paper ranking

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


### Evidence must be weighted by *relevance*, not quantity

Separate (1) **identity certainty**, (2) **fact verification**, (3) **temporal novelty**, (4) **token-price transmission**, and (5) **contradiction / already-priced risk** for each potentially decisive claim. These are distinct tests: a real corporate announcement can have negligible direct token demand, and a precisely reported funding rate can be a noisy market-state observation rather than a fresh catalyst.

Do not interpret generic relative price rises as independently confirmed momentum alpha; OI changes alone do not identify longs versus shorts. Do not double-count syndicated reprints, multiple price feeds or repeated coverage of one event as independent confirmations. Treat unresolved unlock amounts and dates as unresolved **hypotheses**, not completed future supply increases.

Do not classify a news **search-origin** lead as an independently coin-verified event unless the underlying source, token relevance, date and 24h causal mechanism were checked. Identify counterevidence and potential benefit to shorts and longs separately.


## Phase 4 — V8.2: Evidence-calibrated, truly individual 100-coin assessments

Retain the **paper-compatible scoring framework** from V8.1. Change only how the AI **researches and arrives at its original scores**. Investigate BOTH potential 24h upside and downside for ALL 100 official CMC IDs. Do not substitute generic paragraphs or an identical market-regime template for individual analysis.

### A. Research each asset even without a news catalyst

Build a short structured **two-sided fact sheet for each CMC ID**, preferably in a machine-readable working table, **BEFORE** issuing provisional attractiveness values:

- Identity, exact source mapping and timestamps. State clearly which spot/OKX/derivative records are absent, stale or only tentative. Distinguish missing *CMC spot quote* from missing *all independent valid price evidence*.
- Coin-specific market state and changes: price returns and volume across available horizons, matched-pair derivatives OI and funding (with the exact interval, units, venue and any useful baseline), comparable liquidity, supply/float, DEX/TVL/fees, verified token-linked on-chain flows, and relevant near-term events where actually available. **Not all columns will be available; state 'UNKNOWN' where absent.**
- Examine *both sides* of the evidence: e.g. strong 24h momentum can signal continuation OR overextension, OI increases can reflect new longs OR shorts, a chain announcement can be operationally significant while economically irrelevant to token holders. Do not infer direction from a single metric.
- Compare the asset with plausibly relevant CMC100 peers (similar protocol economics, exchange depth, derivatives exposure or sector) under matched timestamps, denominators and data quality. Explain specifically where its position differs. Pure historical return rank is NOT a substitute for this comparison.
- Assess separately (a) **relative 24h opportunity** and (b) **standalone action conviction**. The first drives attractiveness; the second drives BUY/WAIT/SELL.

**Critical nuance:** "No verified NEW event" does **not** mean the asset must receive attractiveness_1d=0.00. An asset can be relatively more or less attractive on independently verified, informative positioning, liquidity or valuation/usage evidence—even while decision=WAIT. Conversely, weak, symmetric or incomparable state data justify 0.00. Do not invent dispersion, trade signals, price impacts or conclusions to avoid zero scores.

**V8.1 failure to correct:** Around 70/100 coins were scored exactly zero, and the prior 24h return was highly associated with the scores. Investigate whether neutral scores resulted from an unsupported "no catalyst => zero" shortcut, copied explanations or an unconscious momentum heuristic. This is a **diagnostic**, not a target number of nonzero scores.

### B. Rank-free paired comparison to test differentiation — not a second ranking variable

Before scoring, challenge at least all plausible provisional top/bottom candidates, their closest peers, and ambiguous zero-score assets using **direct pairwise questions**:

- Does the evidence genuinely distinguish Coin A from Coin B over the **NEXT 24h**, or are their relative conclusions observationally indistinguishable?
- Are metrics cross-venue compatible (funding frequency, contract multipliers, OI currency, liquidity units, circulating supply)?
- Are observed changes economically material and unusual **relative to a defensible baseline**, not just a small-interval difference presented as a shock?
- Would the relative judgment survive removing the prior 24h return and removing duplicated general market language?
- What specific fact could falsify this pairwise thesis?

If differences are unsupported, ties and near-neutral scores are legitimate; never force extra score levels, ranks, BUY/SELL quotas or artificial strength. Pairwise work is *evidence checking* that informs the directly judged attractiveness_1d; it is NOT an additional rank score, optimizer, or deterministic formula.

### C. Evidence strength versus score magnitude

For all provisional nontrivial deviations from 0.00 and especially ALL eventual Top/Bottom candidates:

- Document **identity_confidence**, **fact_verification**, **causal_24h_strength**, **data_coverage** and **counterevidence** separately.
- State whether the key driver is a genuinely new verified development, an independently corroborated structural/derivatives market observation, or an uncertain unverified possibility.
- Explicitly assess whether and why the size of the attractiveness deviation is warranted. No automatic fixed confidence multiplier, score cap, or score=0 rule; this is a qualitative consistency check.
- Unverified unlock calendars, unobserved contract-wallet flows, opaque news leads and missing prices must NOT, **by themselves**, justify the strongest conviction scores.
- Flag decisions that would reverse if a disputed fact proved false. Seek primary documentation when a claim materially drives a ranking extreme.
- Check the nearest available independent price/volume and venue-specific liquidity reference for extreme candidates with no CMC quote. If unavailable, retain the gap and avoid pretending the assessment is precise.

A highly verified *fact* is not the same as a highly verified *24h price forecast*. Label uncertainty in both separately.

### D. Provisional judgments -> targeted deep-dive -> freeze FINAL judgments

Use this sequence; **do not start with a portfolio selection and reason backward**:

1. Draft **100 provisional six-horizon scores**, plus independent provisional BUY/WAIT/SELL labels from the individual fact sheets. Use no portfolio constraint. Identify tentative upper and lower score extremes, **including any assets near possible 10th-place boundaries**, and record their original evidence.
2. Conduct **targeted adversarial research** on every provisional extreme/boundary challenger in BOTH directions (not just the two existing BUY/SELL calls). Trace the strongest driver to the primary source, attempt corroboration, check timing and token identity, consider priced-in effects, and seek contradicting evidence. Where possible, check independently sourced pricing and market depth for coins lacking a CMC spot quote. The inquiry can discover new source categories.
3. Reassess the *individual* provisional judgments after these checks and record a **score_revision_log** with CMC ID, original score, final score, whether direction changed, what newly verified/rejected evidence caused it and exact source/cutoff. Do not change any score merely to enter/exit the Top 10 or avoid a tie.
4. **Freeze the final 100-row prediction panel**. Only after freezing may Phase 5 deterministically rank it by attractiveness_1d. Never retroactively alter finalized scores because of portfolio rank, tie size, the BUY/WAIT/SELL distribution or the desired research quality rating.

Mark the coverage of the deep-dive accurately: "all provisional extremes checked", "some checked", or "not independently checked". If new evidence is unavailable, preserve the uncertainty instead of manufacturing a confident adjustment. The provisional panel and revision log must not look ahead beyond the chosen forecast cutoff.

### E. Original paper scoring fields — UNCHANGED

Return **six independently judged** horizon-specific attractiveness scores for every official coin:
- attractiveness_1h
- attractiveness_6h
- **attractiveness_1d** (the ONLY 1-day portfolio ranking variable)
- attractiveness_3d
- attractiveness_1w
- attractiveness_1m

All remain on the paper-compatible **−5.00 to +5.00** scale in **0.05 increments**, with 0 neutral. These are directional investment-attractiveness judgments, NOT forecast percent returns or calibrated probabilities. Do not convert the old V8 0–1 scale into the primary rank. If needed, report legacy_v8_normalized=(attractiveness_1d+5)/10 as a display-only comparison.

The other horizons do not replace, average into, normalize or modify attractiveness_1d. Do not fit the 1d scores to the realized forward returns. Do not use a mechanical 7-day-return rule, fixed trend offsets, momentum-only scoring, cross-sectional min/max normalization, enforced score spread, or fixed long/short quotas.

Return a separately judged **decision = BUY / WAIT / SELL** based on action conviction, WITHOUT assigning labels via attractiveness score thresholds. **WAIT can coexist with positive or negative attractiveness**, including scores that fall into the Top 10 or Bottom 10. No attempt to recreate published BUY/WAIT/SELL frequencies; rarity of BUY/SELL is a result, not an objective.

Continue to return separately described qualitative **market_sentiment, market_divergence, catalyst_score and overall_market_score**. Do not invent a proprietary formula that calculates attractiveness_1d from them. Provide source/evidence IDs, pro/con mechanisms, price-reference availability, evidence grade, uncertainty and individual rationale. If support is weak, say so plainly.

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

**New V8.2 audit outputs required in addition to the V8.1 outputs:**
- **coin_fact_sheets_100**: per-coin market-state data availability, cross-sectional peers and timestamp-compatible comparison, bullish evidence, bearish evidence, unknowns, and what is / is not verified. A missing catalyst is not proof of neutral relative attractiveness.
- **provisional_prediction_panel_100**: initial, pre-deep-dive six-horizon judgments and independent decisions for all coins. Preserve original numbers and timestamps.
- **score_revision_log**: all final-vs-provisional changes; why each changed, relevant IDs/links, fact verification and a "no change" result for audited extremes that remained stable. Do not generate fake revisions.
- **extreme_candidate_adversarial_audit**: every provisional top/bottom/boundary challenger tested for source truth, identity, currency/unit matching, counterevidence, price availability, possible already-priced effects and 24h causal mechanism. Include failures and gaps, not just positive findings.
- **score_differentiation_diagnostics**: number of distinct 1d scores, frequency at 0.00, 24h-return versus score relationship on matched available coins (if enough data), identical rationale counts and *whether removing price momentum materially changes the explanations*. The paper's historical distribution is background for diagnosis, NOT a benchmark quota to reproduce.

Scores may change **only during the pre-freeze deep-dive** with a documented evidence-based reason. The final panel must be frozen **BEFORE** the deterministic ranking in Phase 5. Prevent look-ahead: never incorporate information first known after the forecast cutoff.

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
- rank membership uses the model's FINAL FROZEN original AI-judged 1d scores, without ANY post-ranking retrofitting;
- all 100 provisional and final scores are present, with every factual change and reason logged;
- all provisional extreme/boundary candidates have an adversarial evidence review or explicitly recorded research-access gaps;
- no mandatory neutral score simply because an asset has no new catalyst, and no forced nonzero score simply to increase dispersion;
- extreme forecasts driven by disputed unlock calendars, missing prices or coin-identity uncertainty are flagged and subjected to source challenge;
- signal/rank separation and tie-aware portfolio construction remain exactly as in V8.1.

Quantify how many coins have at least one independently verified, newly relevant 24h catalyst, how many have only market-state information, and how many lack adequate evidence. 100 generic scores are NOT evidence of a comprehensive research investigation.

Mark PARTIAL_RESEARCH if critical source files were not read, the universe is incomplete, or research is materially deficient. Never claim exact reproduction of the undisclosed original prompt or a trading alpha from one manual test.

## Prospective cutoff protection

Before creating final forecasts, define the research cutoff UTC. Only count information that was accessible by that time; never use later outcome data. Record if source snapshots predate the forecast cutoff by many hours. This is a MANUAL PROMPT test, not an execution or forward-performance measurement.
