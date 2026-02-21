import yfinance as yf
import smtplib
from email.message import EmailMessage
import os
import pandas as pd
from datetime import datetime
import requests
from bs4 import BeautifulSoup

# 1. SETTINGS & 2026 WA PUBLIC HOLIDAY CALENDAR
DIP_PERCENTAGE = 0.05  
OUNCE_TO_GRAMS = 31.1034768
PM_1G_URL = "https://www.perthmint.com/shop/bullion/minted-bars/kangaroo-1g-minted-gold-bar/"
PM_5G_URL = "https://www.perthmint.com/shop/bullion/minted-bars/kangaroo-5g-minted-gold-bar/"

# Official 2026 WA Public Holidays
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
    "2026-12-28": "Boxing Day Holiday"
}

RECEIVERS = {
    os.environ.get("GMAIL_ADDRESS"): "Bilingual",
    os.environ.get("SECONDARY_GMAIL_ADDRESS"): "Mandarin"
}

# 2. STATUS CHECKER
def get_trading_status():
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    
    # Check for Sunday first
    if now.weekday() == 6:  # 6 is Sunday
        return "Bullion Trading closed on Sunday"
    
    # Check for Public Holidays
    if today_str in WA_HOLIDAYS_2026:
        holiday_name = WA_HOLIDAYS_2026[today_str]
        return f"Bullion Trading closed on Public Holiday ({holiday_name})"
    
    return "OPEN (Arrive by 4:00 PM)"

# 3. DATA FETCHING (Gold & Scraping)
def get_pm_price(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        price_tag = soup.find('span', {'class': 'price'})
        return float(price_tag.text.replace('$', '').replace(',', '').strip()) if price_tag else None
    except Exception:
        return None

# Fetch Market Data
gold_ticker = yf.Ticker("GC=F")
hist_data = gold_ticker.history(period="250d")
spot_aud = (hist_data['Close'].iloc[-1] / OUNCE_TO_GRAMS) * yf.Ticker("AUD=X").history(period="1d")['Close'].iloc[-1]

status_msg = get_trading_status()
p1g = get_pm_price(PM_1G_URL)
p5g = get_pm_price(PM_5G_URL)

# 4. REPORT BUILDING
def format_price(val, weight):
    # Hide price and prompt store visit if trading is closed
    if "closed" in status_msg.lower():
        return f"Official {weight} Price: [VISIT STORE NEXT TRADING DAY]"
    return f"Official {weight} Price: ${val:.2f} AUD" if val else f"Official {weight} Price: [Check Link]"

report_en = (
    f"--- PERTH MINT STATUS ---\n"
    f"{status_msg}\n\n"
    f"Market Spot: ${spot_aud:.2f} AUD/g\n"
    f"{format_price(p1g, '1g')}\n"
    f"{format_price(p5g, '5g')}\n"
)

report_zh = (
    f"--- 珀斯铸币局状态 ---\n"
    f"{status_msg.replace('Bullion Trading closed on Sunday', '交易中心周日关闭').replace('Bullion Trading closed on Public Holiday', '交易中心公休日关闭')}\n\n"
    f"市场现货价: ${spot_aud:.2f} AUD\n"
    f"{format_price(p1g, '1克').replace('VISIT STORE', '请在营业日前往门店')}\n"
    f"{format_price(p5g, '5克')}\n"
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
        msg['Subject'] = f"Gold Alert: ${spot_aud:.2f} AUD ({status_msg})"
        msg.set_content(f"{report_en}\n{report_zh}" if mode == "Bilingual" else report_zh)
        smtp.send_message(msg)
