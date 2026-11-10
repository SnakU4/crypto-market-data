# Crypto Evidence Engine — Independent structured data plane (v1)

## Purpose
The existing 10k+ Google News RSS URLs are *discovery leads*, not a trading signal. This separate collector prioritises facts and metrics with machine-readable provider provenance. It does **not** overwrite the established CMC100 and cross-sector collectors.

## Public API sources

- DefiLlama `/v2/chains`: chain-level TVL, an on-chain aggregate proxy rather than a wallet- or transaction-level event. Endpoint is substantially smaller than the previously failed `/protocols`.
- DefiLlama stablecoinchains: USD-pegged circulation per chain, an aggregate supply *observation*, not token unlocks.
- Bybit `/v5/market/tickers?category=linear`: available contract-level funding, open interest, OI notional, volume and market price snapshots. These are observations at capture time, **not** settled historical funding rows.
- Bybit `/v5/market/instruments-info?category=linear&limit=1000`: exchange instrument metadata. Since this endpoint can paginate, this initial v1 captures **only the first page**, and the source reports partial coverage; don't infer it contains all instruments. Tickers should be the main broad derivatives source.

All requests are independently audited; failure does not stop unrelated providers. Bybit access remains jurisdiction-dependent and can return 403/451. No circumvention attempts are made.

Official 100 CMC IDs are validated as an input, but **zero automatic coin identity mappings** are asserted. Bybit base/quote instrument metadata are not enough to match to CMC IDs, given ambiguous symbols, wrappers and exchanges. A future PIT verified ID mapping requires official contract/repository references.

## Time and storage

Every observation stores `observed_utc`, the exact capture run timestamp. `published_utc` stays null because a current market snapshot is not evidence of when it became publicly available historically. No backfilled data are called PIT market observations. A compressed complete `archive/YYYYMMDD/*_observations.jsonl.gz` is immutable and hashed. `latest.json` is a **500-row convenience preview only**; `status.json` reports complete counts, provider errors and limitations.

New workflow: **Crypto Evidence Engine - Structured Sources** at `.github/workflows/crypto-evidence-engine.yml`; twice daily at 11:42 and 23:42 UTC plus manual `workflow_dispatch`. Runs offline tests before live collection. The main CMC100 discovery continues independently.

## Quality and remaining gaps

This is phase 1 of a genuine evidence-centric architecture, **not a proven 9/10 system**. It does not yet supply direct token unlock schedules, wallet/contract event history, verified CMC100 contract-to-instrument maps, independent source corroboration or risk-adjusted 24-hour predictiveness. Data-access errors and coverage shortfalls remain explicit. The original 5.2/10 Stage-1 result does not change merely because new code has been committed. Before claiming 9/10, run the collectors, confirm public feed reachability, validate samples, add direct on-chain/tokenomics sources and perform PIT audits.

## Documentation
- <https://api-docs.defillama.com/>
- <https://bybit-exchange.github.io/docs/v5/market/tickers>
- <https://bybit-exchange.github.io/docs/v5/market/instrument>
