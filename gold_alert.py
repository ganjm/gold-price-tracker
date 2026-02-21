import yfinance as yf
import smtplib
from email.message import EmailMessage
import os
import pandas as pd
from datetime import datetime
import requests
from bs4 import BeautifulSoup

# 1. SETTINGS & TRADING CALENDAR 2026
DIP_PERCENTAGE = 0.05  
OUNCE_TO_GRAMS = 31.1034768
PM_1G_URL = "https://www.perthmint.com/shop/bullion/minted-bars/kangaroo-1g-minted-gold-bar/"
PM_5G_URL = "https://www.perthmint.com/shop/bullion/minted-bars/kangaroo-5g-minted-gold-bar/"

WA_HOLIDAYS_2026 = {
    "2026-01-01": "New Year's Day", "2026-01-26": "Australia Day",
    "2026-03-02": "Labour Day", "2026-04-03": "Good Friday",
    "2026-04-05": "Easter Sunday", "2026-04-06": "Easter Monday",
    "2026-04-25": "Anzac Day", "2026-04-27": "Anzac Day Holiday",
    "2026-06-01": "Western Australia Day", "2026-09-28": "King's Birthday",
    "2026-12-25": "Christmas Day", "2026-12-26": "Boxing Day",
    "2026-12-28": "Boxing Day Holiday"
}

RECEIVERS = {
    os.environ.get("GMAIL_ADDRESS"): "Bilingual",
    os.environ.get("SECONDARY_GMAIL_ADDRESS"): "Mandarin"
}

# 2. STATUS & SCRAPING LOGIC
def get_trading_status():
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    if now.weekday() == 5: return "OPEN (Saturday Trading 9am-5pm)"
    if now.weekday() == 6: return "Bullion Trading closed on Sunday"
    if today_str in WA_HOLIDAYS_2026:
        return f"Bullion Trading closed on Public Holiday ({WA_HOLIDAYS_2026[today_str]})"
    return "OPEN (Mon-Fri 9am-5pm)"

def get_pm_price(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        price_tag = soup.find('span', {'class': 'price'})
        return float(price_tag.text.replace('$', '').replace(',', '').strip()) if price_tag else None
    except: return None

# 3. CALCULATIONS
status_msg = get_trading_status()
is_open = "OPEN" in status_msg
gold_ticker = yf.Ticker("GC=F")
hist = gold_ticker.history(period="250d")
aud_rate = yf.Ticker("AUD=X").history(period="1d")['Close'].iloc[-1]
cny_rate = yf.Ticker("CNY=X").history(period="1d")['Close'].iloc[-1]

spot_aud = (hist['Close'].iloc[-1] / OUNCE_TO_GRAMS) * aud_rate
spot_cny = spot_aud / aud_rate * cny_rate
p1g = get_pm_price(PM_1G_URL)
p5g = get_pm_price(PM_5G_URL)

# 4. BILINGUAL FORMATTING
def format_price(val, weight, lang="en"):
    if val: return f"Official {weight} Price: ${val:.2f} AUD" if lang=="en" else f"官方 {weight} 价格: ¥{(val/aud_rate*cny_rate):.2f} RMB (${val:.2f} AUD)"
    if is_open: return "Official Price: [Web pricing unavailable - VISIT STORE]" if lang=="en" else "官方价格: [网站现价不可用 - 请前往门店咨询]"
    return "Official Price: [STORE CLOSED]" if lang=="en" else "官方价格: [门店已关闭]"

report_en = (
    f"--- PERTH MINT STATUS ---\nStatus: {status_msg}\nNote: Arrive by 4:00 PM.\n\n"
    f"Spot: ${spot_aud:.2f} AUD/g\n{format_price(p1g, '1g', 'en')}\n{format_price(p5g, '5g', 'en')}\n\n"
    f"STRATEGY: • Falling? Wait. • Bouncing? Buy now.\n"
)

report_zh = (
    f"--- 珀斯铸币局状态 ---\n今日状态: {status_msg.replace('OPEN', '开启').replace('closed on', '关闭于')}\n注意: 请在 16:00 前到达。\n\n"
    f"市场现货价: ¥{spot_cny:.2f} RMB (${spot_aud:.2f} AUD)\n{format_price(p1g, '1克', 'zh')}\n{format_price(p5g, '5克', 'zh')}\n\n"
    f"建议策略: • 连跌3天+? 可再等24h。 • 今日反弹? 建议立即购买。\n"
)

# 5. DELIVERY
sender_email = os.environ.get("GMAIL_ADDRESS")
app_password = os.environ.get("GMAIL_APP_PASSWORD")
with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
    smtp.login(sender_email, app_password)
    for email, mode in RECEIVERS.items():
        if not email: continue
        msg = EmailMessage()
        msg['From'] = sender_email
        msg['To'] = email
        msg['Subject'] = f"Gold Update: ${spot_aud:.2f} AUD ({status_msg})"
        msg.set_content(f"{report_en}\n{report_zh}" if mode == "Bilingual" else report_zh)
        smtp.send_message(msg)
