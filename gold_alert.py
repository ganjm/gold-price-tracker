import html
import json
import os
import re
import smtplib
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf
from bs4 import BeautifulSoup


DIP_PERCENTAGE = 0.05
OUNCE_TO_GRAMS = 31.1034768
PERTH_TIMEZONE = ZoneInfo("Australia/Perth")
PASSBOOK_PATH = Path("gold_passbook.csv")
HOLDINGS_PATH = Path("my_holdings.csv")
TAOBAO_APP_PRICES_PATH = Path("taobao_app_prices.csv")
PM_1G_URL = "https://www.perthmint.com/shop/bullion/minted-bars/kangaroo-1g-minted-gold-bar/"
PM_5G_URL = "https://www.perthmint.com/shop/bullion/minted-bars/kangaroo-5g-minted-gold-bar/"
DEFAULT_TAOBAO_1G_URL = "https://e.tb.cn/h.8ZEbY3FydVeQvrb?tk=5wG9gJeMRuD"

WA_HOLIDAYS_2026 = {
    "2026-01-01": "New Year's Day",
    "2026-01-26": "Australia Day",
    "2026-03-02": "Labour Day",
    "2026-04-03": "Good Friday",
    "2026-04-05": "Easter Sunday",
    "2026-04-06": "Easter Monday",
    "2026-04-25": "Anzac Day",
    "2026-04-27": "Anzac Day Holiday",
    "2026-06-01": "Western Australia Day",
    "2026-09-28": "King's Birthday",
    "2026-12-25": "Christmas Day",
    "2026-12-26": "Boxing Day",
    "2026-12-28": "Boxing Day Holiday",
}


@dataclass(frozen=True)
class MarketSnapshot:
    captured_at: datetime
    spot_aud: float
    spot_cny: float
    daily_change_pct: float
    ma50_aud: float
    ma200_aud: float
    pm_1g: float | None
    pm_5g: float | None
    taobao_1g_cny: float | None = None
    taobao_5g_cny: float | None = None
    taobao_5g_bean_cny: float | None = None
    taobao_share_1g_cny: float | None = None
    taobao_app_checked_on: str = ""
    portfolio_grams: float = 0.0
    portfolio_cost_aud: float = 0.0


def get_trading_status(now: datetime | None = None) -> tuple[str, bool]:
    now = now or datetime.now(PERTH_TIMEZONE)
    local_now = now.astimezone(PERTH_TIMEZONE)
    today = local_now.strftime("%Y-%m-%d")

    if today in WA_HOLIDAYS_2026:
        return f"Closed — {WA_HOLIDAYS_2026[today]}", False
    if local_now.weekday() == 6:
        return "Closed — Sunday", False
    if 9 <= local_now.hour < 17:
        return ("Open — Saturday 9am–5pm" if local_now.weekday() == 5 else "Open — Mon–Fri 9am–5pm"), True
    return "Closed — trading hours are 9am–5pm", False


def fetch_history(symbol: str, period: str) -> pd.DataFrame:
    history = yf.Ticker(symbol).history(period=period, auto_adjust=False)
    if history.empty or "Close" not in history:
        raise RuntimeError(f"No market data returned for {symbol}")
    close = history["Close"].dropna()
    if close.empty:
        raise RuntimeError(f"No closing prices returned for {symbol}")
    return history.loc[close.index]


def parse_perth_mint_price(page: str) -> float | None:
    soup = BeautifulSoup(page, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            payload = json.loads(script.string or script.get_text())
        except (json.JSONDecodeError, TypeError):
            continue

        products = payload if isinstance(payload, list) else [payload]
        for product in products:
            if not isinstance(product, dict) or product.get("@type") != "Product":
                continue
            offers = product.get("offers", [])
            offers = offers if isinstance(offers, list) else [offers]
            for offer in offers:
                if not isinstance(offer, dict):
                    continue
                try:
                    price = float(str(offer.get("price", "")).replace(",", ""))
                except ValueError:
                    continue
                if price > 0 and offer.get("priceCurrency", "AUD") == "AUD":
                    return price

    price_tag = soup.find("span", class_="price")
    if not price_tag:
        return None
    try:
        return float(price_tag.get_text(strip=True).replace("$", "").replace(",", ""))
    except ValueError:
        return None


def fetch_perth_mint_price(url: str) -> float | None:
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; PerthGoldTracker/1.0)"},
            timeout=15,
        )
        response.raise_for_status()
        return parse_perth_mint_price(response.text)
    except requests.RequestException:
        return None


def parse_taobao_share_price(page: str) -> float | None:
    decoded = html.unescape(page)
    match = re.search(r"[?&]price=(\d+(?:\.\d+)?)", decoded)
    return float(match.group(1)) if match else None


def fetch_taobao_visible_price(url: str) -> float | None:
    if not url:
        return None

    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
            },
            timeout=20,
        )
        response.raise_for_status()
        return parse_taobao_share_price(response.text)
    except requests.RequestException:
        return None


def load_portfolio(path: Path = HOLDINGS_PATH) -> tuple[float, float]:
    if not path.exists():
        return 0.0, 0.0
    holdings = pd.read_csv(path)
    if "Grams" not in holdings.columns:
        raise RuntimeError(f"{path} must contain a Grams column")
    if "Total_Paid_AUD" not in holdings.columns and "Price_Paid_AUD" not in holdings.columns:
        raise RuntimeError(f"{path} must contain Total_Paid_AUD or Price_Paid_AUD")

    grams = pd.to_numeric(holdings["Grams"], errors="coerce")
    total_paid = pd.Series(float("nan"), index=holdings.index, dtype="float64")
    if "Total_Paid_AUD" in holdings.columns:
        total_paid = pd.to_numeric(holdings["Total_Paid_AUD"], errors="coerce")
    if "Price_Paid_AUD" in holdings.columns:
        unit_price = pd.to_numeric(holdings["Price_Paid_AUD"], errors="coerce")
        total_paid = total_paid.fillna(grams * unit_price)

    valid = grams.notna() & total_paid.notna() & (grams > 0) & (total_paid >= 0)
    return float(grams[valid].sum()), float(total_paid[valid].sum())


def load_taobao_app_prices(
    path: Path = TAOBAO_APP_PRICES_PATH,
) -> tuple[float | None, float | None, float | None, str]:
    if not path.exists():
        return None, None, None, ""
    prices = pd.read_csv(path)
    required = {"Date", "Variant", "Price_CNY"}
    if not required.issubset(prices.columns):
        raise RuntimeError(f"{path} must contain columns: {', '.join(sorted(required))}")

    prices["Date"] = pd.to_datetime(prices["Date"], errors="coerce")
    prices["Price_CNY"] = pd.to_numeric(prices["Price_CNY"], errors="coerce")
    prices["Variant"] = prices["Variant"].astype(str).str.strip().str.lower()
    valid = prices["Date"].notna() & prices["Price_CNY"].notna() & (prices["Price_CNY"] > 0)
    prices = prices.loc[valid]
    if prices.empty:
        return None, None, None, ""

    latest_date = prices["Date"].max()
    latest = prices.loc[prices["Date"] == latest_date].set_index("Variant")["Price_CNY"]

    def get_price(variant: str) -> float | None:
        value = latest.get(variant)
        return float(value) if value is not None else None

    return (
        get_price("1g_bar"),
        get_price("5g_bar"),
        get_price("5g_bean"),
        latest_date.strftime("%d %b %Y"),
    )


def collect_snapshot(now: datetime | None = None) -> MarketSnapshot:
    captured_at = now or datetime.now(PERTH_TIMEZONE)
    gold = fetch_history("GC=F", "1y")["Close"].dropna()
    if len(gold) < 200:
        raise RuntimeError(f"Only {len(gold)} gold observations returned; 200 are required")

    aud_usd = float(fetch_history("AUDUSD=X", "5d")["Close"].dropna().iloc[-1])
    usd_cny = float(fetch_history("CNY=X", "5d")["Close"].dropna().iloc[-1])
    if aud_usd <= 0 or usd_cny <= 0:
        raise RuntimeError("Invalid foreign-exchange rate returned")

    gold_usd_per_gram = gold / OUNCE_TO_GRAMS
    gold_aud_per_gram = gold_usd_per_gram / aud_usd
    spot_aud = float(gold_aud_per_gram.iloc[-1])
    spot_cny = float(gold_usd_per_gram.iloc[-1] * usd_cny)
    daily_change_pct = float(gold.iloc[-1] / gold.iloc[-2] - 1) * 100
    taobao_1g_url = os.environ.get("TAOBAO_1G_URL", "").strip() or DEFAULT_TAOBAO_1G_URL
    taobao_5g_url = os.environ.get("TAOBAO_5G_URL", "").strip()
    taobao_share_1g_cny = fetch_taobao_visible_price(taobao_1g_url)
    app_1g_cny, app_5g_cny, app_5g_bean_cny, app_checked_on = load_taobao_app_prices()
    taobao_1g_cny = app_1g_cny if app_1g_cny is not None else taobao_share_1g_cny
    taobao_5g_cny = app_5g_cny if app_5g_cny is not None else fetch_taobao_visible_price(taobao_5g_url)
    if taobao_5g_cny is None and taobao_1g_cny is not None:
        taobao_5g_cny = taobao_1g_cny * 5
    portfolio_grams, portfolio_cost_aud = load_portfolio()

    return MarketSnapshot(
        captured_at=captured_at.astimezone(PERTH_TIMEZONE),
        spot_aud=spot_aud,
        spot_cny=spot_cny,
        daily_change_pct=daily_change_pct,
        ma50_aud=float(gold_aud_per_gram.tail(50).mean()),
        ma200_aud=float(gold_aud_per_gram.tail(200).mean()),
        pm_1g=fetch_perth_mint_price(PM_1G_URL),
        pm_5g=fetch_perth_mint_price(PM_5G_URL),
        taobao_1g_cny=taobao_1g_cny,
        taobao_5g_cny=taobao_5g_cny,
        taobao_5g_bean_cny=app_5g_bean_cny,
        taobao_share_1g_cny=taobao_share_1g_cny,
        taobao_app_checked_on=app_checked_on,
        portfolio_grams=portfolio_grams,
        portfolio_cost_aud=portfolio_cost_aud,
    )


def get_signal(snapshot: MarketSnapshot) -> tuple[str, str, str]:
    dip_target = snapshot.ma50_aud * (1 - DIP_PERCENTAGE)
    if snapshot.spot_aud <= dip_target:
        return "BUY ZONE", "Spot is at least 5% below its 50-day average.", "#166534"
    if snapshot.spot_aud < snapshot.ma50_aud:
        return "WATCH", "Spot is below its 50-day average, but not yet at the 5% target.", "#a16207"
    return "WAIT", "Spot is at or above its 50-day average.", "#475569"


def premium(price: float | None, grams: int, spot_aud: float) -> float | None:
    if price is None:
        return None
    return (price / grams / spot_aud - 1) * 100


def price_text(price: float | None, grams: int, spot_aud: float) -> str:
    if price is None:
        return "Unavailable"
    markup = premium(price, grams, spot_aud)
    return f"${price:,.2f} AUD ({markup:+.1f}% premium)"


def taobao_price_text(price_cny: float | None, grams: int, snapshot: MarketSnapshot) -> str:
    if price_cny is None:
        return "Unavailable"
    cny_per_aud = snapshot.spot_cny / snapshot.spot_aud
    price_aud = price_cny / cny_per_aud
    markup = (price_cny / grams / snapshot.spot_cny - 1) * 100
    return f"¥{price_cny:,.2f} / A${price_aud:,.2f} ({markup:+.1f}% premium)"


def taobao_checked_label(snapshot: MarketSnapshot) -> str:
    if not snapshot.taobao_app_checked_on:
        return "Not verified"
    try:
        checked = datetime.strptime(snapshot.taobao_app_checked_on, "%d %b %Y").date()
        age_days = (snapshot.captured_at.date() - checked).days
    except ValueError:
        return snapshot.taobao_app_checked_on
    stale = " — STALE, recheck in app" if age_days > 7 else ""
    return f"{snapshot.taobao_app_checked_on}{stale}"


def taobao_plain_lines(snapshot: MarketSnapshot) -> str:
    if snapshot.taobao_app_checked_on:
        return "\n".join([
            f"Lingfeng 1g bar: {taobao_price_text(snapshot.taobao_1g_cny, 1, snapshot)}",
            f"Lingfeng 5g gold bar: {taobao_price_text(snapshot.taobao_5g_cny, 5, snapshot)}",
            f"Lingfeng 5g gold bean: {taobao_price_text(snapshot.taobao_5g_bean_cny, 5, snapshot)}",
            f"Prices checked: {taobao_checked_label(snapshot)}",
            f"Product: {DEFAULT_TAOBAO_1G_URL}",
        ])
    return "\n".join([
        f"Lingfeng 1g public share price: {taobao_price_text(snapshot.taobao_1g_cny, 1, snapshot)}",
        f"Lingfeng 5g (5× 1g estimate): {taobao_price_text(snapshot.taobao_5g_cny, 5, snapshot)}",
        "Variant prices were not recently verified.",
        f"Product: {DEFAULT_TAOBAO_1G_URL}",
    ])


def portfolio_metrics(snapshot: MarketSnapshot) -> tuple[float, float, float]:
    market_value = snapshot.portfolio_grams * snapshot.spot_aud
    profit = market_value - snapshot.portfolio_cost_aud
    return_pct = (profit / snapshot.portfolio_cost_aud * 100) if snapshot.portfolio_cost_aud else 0.0
    return market_value, profit, return_pct


def build_chinese_summary(snapshot: MarketSnapshot, store_status: str) -> str:
    signal, _, _ = get_signal(snapshot)
    signal_zh = {"BUY ZONE": "买入区间", "WATCH": "关注", "WAIT": "等待"}[signal]
    reason_zh = {
        "BUY ZONE": "现货价比50日均价低至少5%。",
        "WATCH": "现货价低于50日均价，但尚未达到5%的目标跌幅。",
        "WAIT": "现货价等于或高于50日均价。",
    }[signal]
    market_value, profit, return_pct = portfolio_metrics(snapshot)
    return f"""黄金更新（珀斯时间 {snapshot.captured_at:%Y-%m-%d %H:%M}）
信号：{signal_zh} — {reason_zh}
现货：A${snapshot.spot_aud:,.2f}/克 | ¥{snapshot.spot_cny:,.2f}/克
日变动：{snapshot.daily_change_pct:+.2f}%
50日均价：A${snapshot.ma50_aud:,.2f}/克
200日均价：A${snapshot.ma200_aud:,.2f}/克
珀斯铸币局：{store_status}
1克金条：{price_text(snapshot.pm_1g, 1, snapshot.spot_aud)}
5克金条：{price_text(snapshot.pm_5g, 5, snapshot.spot_aud)}
珀斯铸币局1克链接：{PM_1G_URL}
珀斯铸币局5克链接：{PM_5G_URL}
淘宝领丰金1克金条：{taobao_price_text(snapshot.taobao_1g_cny, 1, snapshot)}
淘宝领丰金5克金条：{taobao_price_text(snapshot.taobao_5g_cny, 5, snapshot)}
淘宝领丰金5克金豆：{taobao_price_text(snapshot.taobao_5g_bean_cny, 5, snapshot)}
淘宝价格核对日期：{taobao_checked_label(snapshot)}
淘宝商品链接：{DEFAULT_TAOBAO_1G_URL}
持仓：{snapshot.portfolio_grams:g}克 | 成本 A${snapshot.portfolio_cost_aud:,.2f} | 市值 A${market_value:,.2f} | 浮动盈亏 A${profit:+,.2f}（{return_pct:+.1f}%）
仅供市场跟踪，不构成投资建议。"""


def build_plain_report(snapshot: MarketSnapshot, store_status: str, bilingual: bool = True) -> str:
    signal, reason, _ = get_signal(snapshot)
    ma50_distance = (snapshot.spot_aud / snapshot.ma50_aud - 1) * 100
    ma200_distance = (snapshot.spot_aud / snapshot.ma200_aud - 1) * 100
    market_value, profit, return_pct = portfolio_metrics(snapshot)
    return f"""PERTH GOLD UPDATE
{snapshot.captured_at:%A, %d %B %Y at %I:%M %p} AWST

SIGNAL: {signal}
{reason}

MARKET
Spot: ${snapshot.spot_aud:,.2f} AUD/g | ¥{snapshot.spot_cny:,.2f} CNY/g
Daily move: {snapshot.daily_change_pct:+.2f}%
50-day average: ${snapshot.ma50_aud:,.2f} AUD/g ({ma50_distance:+.2f}%)
200-day average: ${snapshot.ma200_aud:,.2f} AUD/g ({ma200_distance:+.2f}%)

PERTH MINT
Store: {store_status}
1g bar: {price_text(snapshot.pm_1g, 1, snapshot.spot_aud)} — {PM_1G_URL}
5g bar: {price_text(snapshot.pm_5g, 5, snapshot.spot_aud)} — {PM_5G_URL}

TAOBAO PRICES
{taobao_plain_lines(snapshot)}

YOUR HOLDINGS
Gold: {snapshot.portfolio_grams:g}g
Cost basis: ${snapshot.portfolio_cost_aud:,.2f} AUD
Spot value: ${market_value:,.2f} AUD
Unrealized P/L: ${profit:+,.2f} AUD ({return_pct:+.1f}%)

This is a market-tracking alert, not financial advice. Retail prices may change before purchase.
""" + (f"\n中文摘要\n{build_chinese_summary(snapshot, store_status)}\n" if bilingual else "")


def metric_row(label: str, value: str, href: str | None = None) -> str:
    label_html = html.escape(label)
    value_html = html.escape(value)
    if href:
        safe_href = html.escape(href, quote=True)
        link_style = "color:#2563eb;text-decoration:underline;"
        label_html = f'<a href="{safe_href}" style="{link_style}">{label_html}</a>'
        value_html = f'<a href="{safe_href}" style="{link_style}font-weight:700;">{value_html}</a>'
    return (
        '<tr><td style="padding:8px 0;color:#64748b;font-size:14px;">'
        f"{label_html}</td><td style=\"padding:8px 0;text-align:right;font-weight:700;font-size:14px;\">{value_html}</td></tr>"
    )


def build_html_report(snapshot: MarketSnapshot, store_status: str, bilingual: bool = True) -> str:
    signal, reason, signal_colour = get_signal(snapshot)
    ma50_distance = (snapshot.spot_aud / snapshot.ma50_aud - 1) * 100
    ma200_distance = (snapshot.spot_aud / snapshot.ma200_aud - 1) * 100
    market_value, profit, return_pct = portfolio_metrics(snapshot)
    market_rows = "".join([
        metric_row("Spot (AUD)", f"${snapshot.spot_aud:,.2f} / g"),
        metric_row("Spot (CNY)", f"¥{snapshot.spot_cny:,.2f} / g"),
        metric_row("Daily move", f"{snapshot.daily_change_pct:+.2f}%"),
        metric_row("vs 50-day average", f"{ma50_distance:+.2f}%"),
        metric_row("vs 200-day average", f"{ma200_distance:+.2f}%"),
    ])
    mint_rows = "".join([
        metric_row("Store", store_status),
        metric_row("1g minted bar", price_text(snapshot.pm_1g, 1, snapshot.spot_aud), PM_1G_URL),
        metric_row("5g minted bar", price_text(snapshot.pm_5g, 5, snapshot.spot_aud), PM_5G_URL),
    ])
    if snapshot.taobao_app_checked_on:
        taobao_rows = "".join([
            metric_row("Lingfeng 1g bar", taobao_price_text(snapshot.taobao_1g_cny, 1, snapshot), DEFAULT_TAOBAO_1G_URL),
            metric_row("Lingfeng 5g gold bar", taobao_price_text(snapshot.taobao_5g_cny, 5, snapshot), DEFAULT_TAOBAO_1G_URL),
            metric_row("Lingfeng 5g gold bean", taobao_price_text(snapshot.taobao_5g_bean_cny, 5, snapshot), DEFAULT_TAOBAO_1G_URL),
            metric_row("Prices checked", taobao_checked_label(snapshot)),
        ])
    else:
        taobao_rows = "".join([
            metric_row("Lingfeng 1g public share price", taobao_price_text(snapshot.taobao_1g_cny, 1, snapshot)),
            metric_row("Lingfeng 5g (5× estimate)", taobao_price_text(snapshot.taobao_5g_cny, 5, snapshot)),
            metric_row("SKU verification", "Variant prices not recently verified"),
        ])
    portfolio_rows = "".join([
        metric_row("Gold held", f"{snapshot.portfolio_grams:g}g"),
        metric_row("Cost basis", f"${snapshot.portfolio_cost_aud:,.2f} AUD"),
        metric_row("Spot value", f"${market_value:,.2f} AUD"),
        metric_row("Unrealized P/L", f"${profit:+,.2f} AUD ({return_pct:+.1f}%)"),
    ])
    chinese_card = ""
    if bilingual:
        chinese_card = (
            '<div style="margin-top:24px;background:#fffbeb;padding:16px;border-radius:8px;white-space:pre-line;'
            'font-size:14px;line-height:1.6;">'
            '<strong>中文摘要</strong><br>'
            f"{html.escape(build_chinese_summary(snapshot, store_status))}</div>"
        )

    return f"""<!doctype html>
<html><body style="margin:0;background:#f1f5f9;font-family:Arial,sans-serif;color:#0f172a;">
<div style="display:none;max-height:0;overflow:hidden;">{html.escape(signal)} — gold is {snapshot.daily_change_pct:+.2f}% today.</div>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f1f5f9;padding:20px 8px;"><tr><td align="center">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:620px;background:#ffffff;border-radius:16px;overflow:hidden;">
<tr><td style="background:#0f172a;padding:24px;color:#ffffff;">
  <div style="font-size:12px;letter-spacing:1.5px;color:#fbbf24;font-weight:700;">PERTH GOLD UPDATE</div>
  <div style="font-size:26px;font-weight:800;margin-top:8px;">${snapshot.spot_aud:,.2f} AUD/g</div>
  <div style="font-size:13px;color:#cbd5e1;margin-top:6px;">{snapshot.captured_at:%A, %d %B %Y · %I:%M %p} AWST</div>
</td></tr>
<tr><td style="padding:24px;">
  <div style="border-left:5px solid {signal_colour};background:#f8fafc;padding:16px;border-radius:8px;">
    <div style="font-size:12px;color:{signal_colour};font-weight:800;letter-spacing:1px;">{html.escape(signal)}</div>
    <div style="font-size:15px;margin-top:6px;line-height:1.45;">{html.escape(reason)}</div>
  </div>
  <h2 style="font-size:16px;margin:26px 0 8px;">Market snapshot</h2>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0">{market_rows}</table>
  <h2 style="font-size:16px;margin:26px 0 8px;">Perth Mint</h2>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0">{mint_rows}</table>
  <h2 style="font-size:16px;margin:26px 0 8px;">Taobao prices</h2>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0">{taobao_rows}</table>
  <h2 style="font-size:16px;margin:26px 0 8px;">Your holdings</h2>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0">{portfolio_rows}</table>
  {chinese_card}
  <div style="margin-top:24px;padding-top:16px;border-top:1px solid #e2e8f0;color:#64748b;font-size:11px;line-height:1.5;">
    Market-tracking alert only; not financial advice. Retail prices may change before purchase.
  </div>
</td></tr></table>
</td></tr></table>
</body></html>"""


def build_mandarin_html_report(snapshot: MarketSnapshot, store_status: str) -> str:
    signal = {"BUY ZONE": "买入区间", "WATCH": "关注", "WAIT": "等待"}[get_signal(snapshot)[0]]
    content = html.escape(build_chinese_summary(snapshot, store_status)).replace("\n", "<br>")
    return f"""<!doctype html><html><body style="margin:0;background:#f1f5f9;font-family:Arial,sans-serif;color:#0f172a;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:20px 8px;"><tr><td align="center">
<table role="presentation" width="100%" style="max-width:620px;background:#fff;border-radius:16px;overflow:hidden;">
<tr><td style="background:#0f172a;padding:24px;color:#fff;"><div style="color:#fbbf24;font-size:12px;font-weight:700;">珀斯黄金更新</div>
<div style="font-size:26px;font-weight:800;margin-top:8px;">A${snapshot.spot_aud:,.2f}/克</div></td></tr>
<tr><td style="padding:24px;"><div style="font-size:18px;font-weight:800;margin-bottom:14px;">{signal}</div>
<div style="font-size:14px;line-height:1.8;">{content}</div></td></tr></table>
</td></tr></table></body></html>"""


def build_message(
    snapshot: MarketSnapshot,
    store_status: str,
    sender: str,
    recipient: str,
    mode: str = "Bilingual",
) -> EmailMessage:
    signal, _, _ = get_signal(snapshot)
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    if mode == "Mandarin":
        signal_zh = {"BUY ZONE": "买入区间", "WATCH": "关注", "WAIT": "等待"}[signal]
        message["Subject"] = f"黄金{signal_zh}：A${snapshot.spot_aud:,.2f}/克（{snapshot.daily_change_pct:+.2f}%）"
        message.set_content(build_chinese_summary(snapshot, store_status))
        message.add_alternative(build_mandarin_html_report(snapshot, store_status), subtype="html")
    else:
        message["Subject"] = f"Gold {signal}: ${snapshot.spot_aud:,.2f}/g ({snapshot.daily_change_pct:+.2f}%)"
        message.set_content(build_plain_report(snapshot, store_status, bilingual=True))
        message.add_alternative(build_html_report(snapshot, store_status, bilingual=True), subtype="html")
    return message


def get_email_settings() -> tuple[str, str, list[tuple[str, str]]]:
    sender = os.environ.get("GMAIL_ADDRESS", "").strip()
    password = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")
    secondary = os.environ.get("SECONDARY_GMAIL_ADDRESS", "").strip()
    recipients = [(sender, "Bilingual")]
    if secondary and secondary != sender:
        recipients.append((secondary, "Mandarin"))
    missing = [name for name, value in {"GMAIL_ADDRESS": sender, "GMAIL_APP_PASSWORD": password}.items() if not value]
    if missing:
        raise RuntimeError(f"Missing required GitHub Actions secrets: {', '.join(missing)}")
    return sender, password, recipients


def send_reports(snapshot: MarketSnapshot, store_status: str) -> int:
    sender, password, recipients = get_email_settings()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(sender, password)
        for recipient, mode in recipients:
            smtp.send_message(build_message(snapshot, store_status, sender, recipient, mode))
    return len(recipients)


def append_passbook(snapshot: MarketSnapshot) -> None:
    columns = [
        "Date", "Spot_AUD_g", "Spot_CNY_g", "MA50_AUD", "MA200_AUD",
        "Est_Shop_AUD", "Taobao_1g_CNY", "Taobao_5g_CNY",
    ]
    row = pd.DataFrame([{
        "Date": snapshot.captured_at.strftime("%Y-%m-%d %H:%M"),
        "Spot_AUD_g": round(snapshot.spot_aud, 2),
        "Spot_CNY_g": round(snapshot.spot_cny, 2),
        "MA50_AUD": round(snapshot.ma50_aud, 2),
        "MA200_AUD": round(snapshot.ma200_aud, 2),
        "Est_Shop_AUD": round(snapshot.pm_1g, 2) if snapshot.pm_1g is not None else "N/A",
        "Taobao_1g_CNY": round(snapshot.taobao_1g_cny, 2) if snapshot.taobao_1g_cny is not None else "N/A",
        "Taobao_5g_CNY": round(snapshot.taobao_5g_cny, 2) if snapshot.taobao_5g_cny is not None else "N/A",
    }], columns=columns)
    if PASSBOOK_PATH.exists():
        existing = pd.read_csv(PASSBOOK_PATH).reindex(columns=columns)
        row = pd.concat([existing, row], ignore_index=True)
    row.to_csv(PASSBOOK_PATH, index=False)


def main() -> None:
    snapshot = collect_snapshot()
    store_status, _ = get_trading_status(snapshot.captured_at)
    recipient_count = send_reports(snapshot, store_status)
    append_passbook(snapshot)
    print(f"Sent {recipient_count} email report(s) and updated {PASSBOOK_PATH}")


if __name__ == "__main__":
    main()
