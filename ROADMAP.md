# Product roadmap

## 1. Reliability and delivery health

- Move the clock to a free Cloudflare Worker or an always-on local scheduler.
- Add a delivery ledger and idempotency key so retries cannot send duplicate emails.
- Send a separate health alert if market data, SMTP, or a retailer fails repeatedly.
- Track source freshness in every report.

## 2. Taobao physical-gold comparison

Initial listing: Lingfeng Gold 足金9999 1g, Taobao item `992105119294`. Its share page currently exposes a visible price of ¥909. The tracker records that value, converts it to AUD, calculates its premium versus CNY spot, and labels the 5g figure as a five-times estimate when no separate 5g price is available.

The shared link exposed a snapshot price of ¥909, but the stable listing page did not expose a live price without Taobao's authenticated dynamic API. The production feature should:

- use an official/authenticated Taobao data route where available;
- normalize price to CNY per gram and adjust for stated purity;
- omit shipping, import duty, and Australian tax because the item remains in China;
- show premium versus CNY spot, seller/listing identity, and observation time;
- mark stale or blocked prices clearly and never stop the main email.

## 3. Portfolio intelligence

- Current market value, cost basis, unrealized P/L, and return percentage
- Allocation by location, product size, and currency
- Break-even spot price and retail-premium recovery
- Purchase journal with notes and receipt references

## 4. Probabilistic outlook

Build forecasts as calibrated ranges and probabilities, not a single target. Candidate inputs:

- gold returns, trend, realized volatility, and options-implied volatility;
- USD/AUD/CNY FX and US real yields;
- inflation and central-bank expectations;
- ETF flows and futures positioning;
- geopolitical and financial-news sentiment;
- Perth Mint and Taobao physical premiums.

Required safeguards:

- time-series splits and walk-forward backtesting;
- no future-data leakage;
- comparison with simple momentum and no-change baselines;
- confidence intervals, feature attribution, and historical hit rate;
- separate 1-day, 1-week, and 1-month horizons;
- explicit low-confidence output when data is missing or regimes change.

Start with a transparent gradient-boosting or regularized model. Use an LLM to classify and summarize news, not as the sole price predictor.

## 5. Dashboard

- Interactive price, moving-average, premium, and portfolio charts
- Filterable Perth/Taobao purchase opportunities
- Model forecast ranges and driver explanations
- Source-health and last-success indicators
