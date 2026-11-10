# Crypto Evidence Engine — unified Stage 1 research intake and acceptance

**Operational status:** separate evidence pipeline and existing broad CMC100 discovery are both active. This implementation does **not** certify 9/10 research quality or claim a predictive trading edge.

## What is collected

| Class | Sources | Interpretation |
|---|---|---|
| Perpetual derivatives / OI | OKX swaps (all swap tickers and OI), Kraken perpetual tickers | Public market observations, not exchange-confirmed settlement history for all coins |
| Tokenomics / circulating supply | CoinGecko market/supply snapshots | Circulating/total supply *observations*, not proof of an unlock event |
| DeFi chain-level activity | DeFiLlama chain TVL and stablecoin circulation | Chain/aggregate context, not wallet transfers |
| Protocol activity | DeFiLlama free DEX volumes and protocol fees | Provider-reported 24h/7d metrics; not directly audited contracts |
| Direct network evidence | Bitcoin mempool, recommended fees, Ethereum Blockscout network statistics | Network-wide, not a statement about an individual ERC20 or a price catalyst |
| DEX pool context | GeckoTerminal public trending pools | Pool liquidity and volume, CMC identity not assumed |
| Individual observed transactions | Bitcoin mempool recent, Ethereum Blockscout recent | **Sampled** network transactions; not whale attribution, not complete CMC100 wallet history |
| Dated token schedules | PatternPlus public CC-BY 4.0 unlock JSON | Third-party schedule **candidates**, calendar day not an exact unlock hour; source confirmation still needed |
| Sector events | PatternPlus calendar JSON | Candidate macro/crypto scheduled events, not confirmed occurrences |
| Project releases, community, governance, security, research | Existing Expanded Evidence Discovery | Keeps every full raw lead archive; direct feeds/structured Snapshot & CISA separate from Google headlines |

Provider access or schema errors are logged independently. Bybit is disabled by default after repeat HTTP 403 on GitHub Actions; that access gap remains visible in the source audit. The full sources list is defined in `src/crypto_evidence_engine.py` and `src/evidence_extensions.py`. No API keys or paid services are required by default. CoinGecko/GeckoTerminal and third-party sources can rate-limit or change their public policies.

**Attribution for PatternPlus feeds:** Data: PatternPlus ([pattern.plus](https://pattern.plus/developers)), CC BY 4.0. Its unlock values and date confidence are reported as **third-party, uncorroborated**. These feeds must not be represented as project-confirmed vesting schedules.

## Coin identity assurance

Input must be the official verified 100-coin CMC100 snapshot, from `docs/latest.json`. Its 2026-11-10 baseline has **77 exact validated OKX swap identifiers**. The engine links only an EXACT_OKX instrument that appears in both the curated snapshot and the live OKX response. This is a verified **exchange instrument match**, not an independently authenticated chain contract identity.

Kraken contract base symbols, CoinGecko names/symbols, and third-party unlock name/symbol pairs can produce only `candidate_cmc_id` with an explicitly weaker status. Chain aggregate or general Bitcoin/Ethereum transaction observations keep network-context identifiers; they are not incorrectly asserted to be CMC100 coin-specific token flows.

Unknown or ambiguous identities stay unknown. There is no blanket "100 of 100 verified" claim.

## Information novelty and Point-in-Time

1. Each source is fetched separately and timestamped at **HTTP response completion**; it is not backdated to an inferred publication time.
2. The full result is written to `docs/evidence_engine/archive/YYYYMMDD/TIMESTAMP_observations.jsonl.gz`. The file is **immutable** and SHA-256 hashed.
3. The prior archive is loaded only when it exists, is safe relative to the output path, and its checksum matches the previous `status.json`.
4. Each observation is compared with the same provider + source item ID. Distinct metrics and absolute/relative changes are logged separately.
5. Changes above triage thresholds are **heuristic change candidates**, not verified events, abnormality statistics or forecast signals. A first snapshot is a **baseline**, never a new-event day. A newly observed BTC transaction hash or third-party calendar row is not necessarily a newly published announcement.
6. Calendar dates (`YYYY-MM-DD`) are not converted to fictional release times. Block inclusion timestamps and source observation times are separately retained.

## User-facing machine-readable outputs

- `docs/evidence_engine/status.json`: latest run time, coverage, per-source health, snapshot hash, identity coverage, novelty and scorecard
- `docs/evidence_engine/integrated_quality_report.json`: weighted six-dimension engineering-quality diagnostic and **hard acceptance blockers**
- `docs/evidence_engine/identity_audit.json`: anchored exact instruments and weak candidate counts
- `docs/evidence_engine/delta_candidates.json`: cross-snapshot numerical changes and first-seen counts
- `docs/evidence_engine/event_candidates.json`: transaction hashes, unlock schedules and event dates with source links and verification labels
- `docs/evidence_engine/latest.json`: **stratified** 500-row convenience preview, not the complete data
- `docs/evidence_engine/daily_metrics.json`: run history
- `docs/expanded_discovery/status.json` and `evidence_candidates.json`: independent news/primary-source feed and evidence candidates

## Automatic operation and acceptance

**Production workflow:** [Crypto Evidence Engine — Structured Sources](https://github.com/SnakU4/crypto-market-data/actions/workflows/crypto-evidence-engine.yml), schedule twice daily at 11:42 and 23:42 UTC and manual trigger. Source code commits run the **offline regression tests only**, not a competing live collection. Updating the production workflow file triggers an acceptance capture. This avoids concurrent output rebase conflicts caused during development.

**Separate regression workflow:** Stage 1 Evidence Regression Tests. It covers all previous tests and the latest source parsers, identity checks, PIT archive reconstruction, delta classification and token release candidates.

**9/10 requirements:** A diagnostic score alone cannot certify Stage 1. Full independent authentication of the 100 assets, a historically correct PIT replay, comprehensive on-chain wallet/contract coverage for the universe, project-confirmed unlock schedules, and independent corroboration of major event claims remain hard gates. The scorecard therefore cannot claim a verified 9/10 until these checks pass; and research data quality is separate from prospective 24-hour forecasting accuracy.

### API documentation

- [OKX public market data](https://www.okx.com/docs-v5/agent_en/)
- [Kraken Futures](https://docs.kraken.com/api/docs/futures-api/trading/)
- [DeFiLlama public API](https://api-docs.defillama.com/)
- [CoinGecko markets API](https://docs.coingecko.com/reference/coins-markets)
- [Mempool public API](https://mempool.space/docs/api/rest)
- [Blockscout V2 API](https://docs.blockscout.com/devs/apis/rest)
- [GeckoTerminal API](https://api.geckoterminal.com/docs/index.html)
- [PatternPlus open data](https://pattern.plus/developers)
