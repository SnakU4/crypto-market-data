# Stage 1: 9/10 evidence-quality target (v5 experimental)

**Status:** implementation committed; **live execution / 9-of-10 validation outstanding**. This is a new measurable quality gate, **not** a forecast upgrade. Neither a high URL count nor keyword-detected numbers establishes a valid trading edge.

## Why previous v4.1 does not meet the target

The 2026-11-10 09:56:14 UTC run showed 10,547 URL leads; only 333 (3.16%) carried a substantive excerpt according to a heuristic, while 240 Google News link resolution attempts yielded zero resolved articles and only 13 pages were fetched. Counting 10k similar headlines is not genuine evidence breadth.

## Implementation

New modules:
- `src/structured_evidence.py`: a small, independent **structured** collection tier. Snapshot Hub GraphQL governance proposals (selected spaces; source-generated creation timestamps), CISA KEV newly added CVEs (source date-only, *not* falsely given a midnight publication timestamp), DeFiLlama free protocol TVL observations (*observed at capture time*, not events), and Binance USD-M BTC/ETH funding settlements and open-interest samples (exchange market timestamps distinguished from when we learned them). Any 403/429/errors are individually audited. No paid account required. **Not every CMC100 coin has these sources.**
- `src/evidence_scorecard.py`: deterministic candidate-fact spans (numeric quantities, dates, action words) with **NOT_VERIFIED** labels and literal offsets into the excerpt. Reports a weighted six-dimension score and hard acceptance gates that **fail closed** for independent corroboration, PIT audit and missing on-chain/tokenomics breadth. This is not a claim of extracting verified facts.
- `src/expanded_discovery.py`: integrates the extra source families only in actual HTTP mode (offline tests need no external network), preserves source provenance, maintains existing broad 100-coin searches and immutable archives. Source query origin is never equated to true token relevance.
- `docs/expanded_discovery/evidence_candidates.json`: up to 600 substantive leads and primary structured items (strictly labelled **unverified**), to support later manual/AI causal review. The complete raw archive is kept separately.
- `docs/expanded_discovery/quality_scorecard.json`: score, weights, blockers, and counts. `status.json` also embeds the scorecard, while `daily_metrics.json` logs scores by run.
- `.github/workflows/expanded-discovery.yml`: offline regression tests for both old collector and new structured collectors. The 240 Google-News decoding requests that failed in v4.1 are disabled; a future version can re-enable a **working, authorized** direct-article source rather than waste requests.

## Weights and hard criteria

| Dimension | Weight | Target |
|---|---:|---|
| Breadth | 20% | All 100 official CMC100 members plus independent cross-sector research |
| Source quality | 20% | Diverse direct feeds, governance, security, structured DeFi and derivatives |
| Content depth | 25% | ≥40% substantive excerpts, traceable factual references; *numbers alone are not facts* |
| Temporal integrity | 15% | Capture timestamps, no future leaks, source publication/observation time separated |
| Incremental novelty | 10% | Measured new informative leads, not initial 9,940-URL baseline |
| Robustness | 10% | Tests, source audit, reproducible sampling, error containment |

**No automatic certification of 9/10.** The code deliberately sets independent-corroboration and point-in-time audit gates to false pending actual documented external review. It also does not claim comprehensive on-chain/tokenomics coverage just because a DeFiLlama metric is available. Missing feeds or inaccessible providers must be reported, not fabricated. Confirmed 9/10 requires an actual run, a validated source-by-source dataset, and completion of those audits.

## Mandatory next improvements to truly approach 9/10

1. **Verified asset identity**: identify official site / repository / blockchain contract and ticker aliases per current PIT CMC100 ID. Never link a governance proposal or protocol metric to a coin solely by ticker.
2. **Direct on-chain / tokenomics evidence**: chain/indexer and official token release schedules with proper block timestamps, contract IDs and point-in-time history. Compare independently of the news feed.
3. **Broad derivatives**: exchanges and derivatives instruments beyond BTC/ETH, mapping contracts to a validated underlying and recording funding, OI, liquidations and provider gaps; respect geographic access and limits.
4. **Independent claim corroboration**: an evidence-first verifier, not merely title similarity or the presence of dates/numbers. Log disagreements and conflicting claims.
5. **PIT validation**: replay selected archival observations at historical times, confirm no hindsight in mixed exchange/publication data.
6. **Economic validation**: measure whether information provides timely, distinct, tradable incremental signals; this is a separate Stage 2 question and cannot be proven from Stage 1 lead counts.

## Run/check

Open **GitHub Actions → CMC100 Expanded Evidence Discovery → Run workflow** on `main`. Examine step-level tests. Inspect `source_audit.csv` for failures, `status.json` for newly discovered evidence families, and `quality_scorecard.json` for actual measured scores and failed acceptance gates.

The last observed v4.1 run is the baseline; new v5 results must not be claimed before the workflow executes successfully. No forecast or live trading code was changed.

## Documentation of source APIs

- [Snapshot Hub GraphQL](https://github.com/snapshot-labs/snapshot-docs/blob/master/tools/api/README.md): documented governance proposals API and rate limit
- [CISA KEV repository](https://github.com/cisagov/kev-data): official published known-exploited vulnerability JSON
- [DefiLlama free API](https://api-docs.defillama.com/): protocol TVL and protocol metrics (free routes have distinct coverage/constraints)
- [Binance USD-M market data](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest): public open interest / funding endpoints; access dependent on region
