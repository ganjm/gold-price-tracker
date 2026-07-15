# Perth Gold Tracker

Automated gold-market monitoring for Perth and China. The tracker converts global gold prices into AUD and CNY per gram, compares Perth Mint retail premiums, records a historical passbook, and sends readable bilingual email reports.

## What the alert includes

- AUD and CNY spot prices per gram
- Daily percentage movement
- Distance from the 50-day and 200-day averages
- A transparent `BUY ZONE`, `WATCH`, or `WAIT` signal
- Perth Mint 1g and 5g prices and premiums when scraping is available
- Taobao Lingfeng 1g visible price plus a clearly labelled 5× estimate for 5g, in CNY and AUD with premium versus CNY spot
- Personal holdings cost basis, spot value, and unrealized P/L
- Perth-local store status, including 2026 WA public holidays
- Responsive HTML plus a plain-text fallback
- A bilingual primary report and Mandarin report for the optional secondary address

The signal is deliberately simple and explainable. It is market tracking, not financial advice or a price prediction.

## Why emails stopped in May 2026

The last scheduled workflow completed successfully on 12 May 2026. GitHub automatically disables scheduled workflows in public repositories after 60 days without repository activity. GitHub schedules can also be delayed—especially at the start of an hour—and do not provide an exact-time guarantee.

After merging this update:

1. Open **Actions → Daily Gold Alert**.
2. Select **Enable workflow** if GitHub shows it as disabled.
3. Select **Run workflow** once and confirm that the email arrives.

The repaired script appends `gold_passbook.csv` after successful delivery, and the workflow commits that update. This creates regular repository activity and avoids the same inactivity shutdown.

## GitHub setup

Add these repository secrets under **Settings → Secrets and variables → Actions**:

| Secret | Purpose |
| --- | --- |
| `GMAIL_ADDRESS` | Sender and bilingual primary recipient |
| `GMAIL_APP_PASSWORD` | Gmail App Password, not the normal account password |
| `SECONDARY_GMAIL_ADDRESS` | Optional Mandarin-only recipient |

Optional repository variables:

| Variable | Purpose |
| --- | --- |
| `TAOBAO_1G_URL` | Override the built-in Lingfeng 1g share link |
| `TAOBAO_5G_URL` | Lingfeng 5g Taobao share link |

Under **Settings → Actions → General → Workflow permissions**, enable **Read and write permissions** so the workflow can update the passbook.

The workflow is intentionally manual-dispatch only. A free Cloudflare Worker Cron Trigger dispatches it at 10:00 AM and 3:00 PM AWST, Monday–Saturday, using `0 2,7 * * 2-7` (Cloudflare cron uses UTC and numbers Sunday as day 1). Keeping the GitHub `schedule` trigger disabled prevents duplicate emails.

## Exact-time, zero-cost scheduling

For more reliable timing without a paid service:

1. **Cloudflare Worker Cron Trigger (configured cloud option):** the free plan dispatches this workflow at 02:00 and 07:00 UTC, Monday–Saturday. The Worker uses a fine-grained GitHub token stored as the encrypted `GITHUB_TOKEN` secret, restricted to this repository with `Actions: write`.
2. **Windows Task Scheduler:** run `python gold_alert.py` at 10:00 AM and 3:00 PM on an always-on computer. This avoids third-party tokens but depends on that computer and internet connection.

Do not enable both schedulers without adding duplicate-delivery protection.

## Local development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Set the email environment variables only when you intentionally want to send a live report. Unit tests never send email or require repository secrets.

## Data files

- `gold_passbook.csv`: automated market history used by the web dashboard
- `my_holdings.csv`: optional purchases in `Date,Grams,Price_Paid_AUD` format

## Planned upgrades

See [ROADMAP.md](ROADMAP.md) for the proposed Taobao comparison, portfolio analytics, probabilistic forecasting, and reliability work.
