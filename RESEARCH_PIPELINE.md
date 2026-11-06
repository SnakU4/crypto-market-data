# Stage 1 — Wide public research evidence collection (v1)

This is a **separate** standard-library-only workflow in `SnakU4/crypto-market-data`. It is additive: the existing official CMC100 snapshot workflow and forecast are not modified.

## Research principle: widest *defensible* reach, never closed source taxonomy

The registry `SOURCE_CATALOG` in `src/research_collector.py` is extensible, and **does not mean that these are all relevant sources**. New source adapters and categories may be added without changing the forecasting prompt. Collectors gather verifiable *observations*, not predictions or causal token-price claims. A broad but unvalidated source is worse than a declared coverage gap.

Current first-wave categories (33 source-registry attempts, including 3 CMC supply batches, plus one OKX contract-info and up to 100 public orderbook queries): protocol/chain TVL, protocol fees, protocol revenue, holder revenue, DEX trading, options, decentralized perpetual OI, stablecoin aggregate and chain supply, search attention, Fear & Greed, general crypto news, DeFi news, regulator announcements, macro/Fed/BLS releases, security incidents, network upgrades and exchange announcements. Existing `docs/latest.json` contributes 100 spot prices and available OKX-perpetual price/OI/funding observations. The research pipeline also creates **own timestamped OI observations** so a true 24h OI change can be measured on later days, conditional on the same exchange/instrument and the correct observation gap.

**Explicit gaps and next adapters**: structured token unlock schedules/vesting and historical token supply changes (current circulating, total and maximum supplies are sampled by explicit CMC ID), on-chain labelled CEX flows and whale transfers, liquidations, systematic spot orderbook depth for 100 coins, ETF creation/redemption/flows, macro calendars, governance proposals, on-chain MEV and exchange concentration, developer activity, sentiment time series, protocol-specific 24h catalysts. RSS notices about token unlocks or governance are **discovery leads only**, not confirmed occurrence, exact amount or final token effect.

Broad event source feeds include news/media plus project and regulator sources. For copyright and provenance, only feed metadata and headlines are archived, not full copied articles. Each headline is separately classified into expandable event categories (unlock, supply, listing, security, governance, upgrades, regulation, flows, DeFi, derivatives, macro, legal). Coin matching is a *candidate* link, not verified entity resolution; generic/short tickers are ignored unless explicit. Protocol-to-coin matching requires an explicit CMC ID or unique exact symbol **and** name; TVL or fees do not imply token value accrual.

## Files

- `docs/research/latest.json` — comprehensive structured research panel: sources, coverage, observations, article metadata and coin candidates.
- `docs/research/status.json` — per-source response/error and per-data-family coverage; no fabricated full-coverage flags.
- `docs/research/events.csv` — article/event metadata, explicit publication-UTC uncertainty, first observed time and candidate coin tags.
- `docs/research/coin_features.csv` — 100 coin rows and broad metrics/event references.
- `docs/research/oi_history/YYYYMMDD.jsonl` — append-only real observed OI measurements with provider/instrument/time. No interpolation or arbitrary OI change.
- `docs/research/event_first_seen.json` — first-seen registry across runs.
- `docs/research/archive/YYYYMMDD/...json` — immutable point-in-time research bundle, never overwritten.

## Schedule, access and limits

Runs at **17:19, 21:19, 22:19, 23:19 UTC** plus manual triggers. Timing is best effort. Uses existing latest market snapshot as a **possibly older separately timestamped source**. The 23:19 UTC research sample precedes the main spot collector 23:37/23:47 UTC. The forecast must read **both**, compare per-source observation timestamps, and never backdate late publications to the scheduled 00:00 UTC cutoff. The GitHub connector is the supported ChatGPT data path; web search is independent for adaptive investigation.

GitHub Pages is published by the existing `snapshot.yml`. This research workflow **does not compete to deploy Pages**; the connector can read `docs/research/...` as soon as the research commit lands. Research files are published to Pages on the next main snapshot deployment.

Source APIs may block GitHub runners with 403/429/451, change schemas or require a paid tier. These are explicitly logged; no proxies or bypass. DefiLlama free endpoints and RSS availability require first live-run validation. CoinGecko public endpoints may rate-limit; no keys used. Source access obeys site restrictions and reasonable request limits (one request per source per run; headlines only). No LLM calls, no money, no orders.

**Important**: This first version does not claim to gather "all" possible information. `status.json` reports every source attempt and known unserved families. This is an instrumented platform for progressively widening the research base without another prompt-writing cycle.

## One-time first test

1. Merge the feature PR into `main`.
2. GitHub → Actions → **CMC100 Wide Research Capture** → **Run workflow**.
3. Open `docs/research/status.json` in the repository (works with the GitHub connector). Look at `sources_ok`, `sources_failed`, `family_coverage`, and missing families. No assumption of success before live validation.
4. The existing CMC100 overnight workflow and forecasting task remain unchanged until the research audit is accepted.

## Running tests locally

```bash
python -m unittest discover -s tests -v
python src/research_collector.py --max-workers 5
```

The second command needs external HTTP connectivity. All tests are deterministic mock-based and make **zero** external requests.

## Source references

- DefiLlama official free API: https://github.com/DefiLlama/api-docs/blob/main/llms-free.txt
- CoinGecko free API overview: https://www.coingecko.com/en/api
- OKX public API: https://www.okx.com/docs-v5/en/
- GitHub Actions schedules: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule