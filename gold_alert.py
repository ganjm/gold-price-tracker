import yfinance as yf
import smtplib
from email.message import EmailMessage
import os
import pandas as pd
from datetime import datetime
import requests
from bs4 import BeautifulSoup

# 1. SETTINGS
DIP_PERCENTAGE = 0.05  
OUNCE_TO_GRAMS = 31.1034768
EST_PREMIUM = 1.15     
PERTH_MINT_1G_URL = "https://www.perthmint.com/shop/bullion/minted-bars/kangaroo-1g-minted-gold-bar/"

RECEIVERS = {
    os.environ.get("GMAIL_ADDRESS"): "Bilingual",
    os.environ.get("SECONDARY_GMAIL_ADDRESS"): "Mandarin"
}

# --- ENHANCED: Scrape Perth Mint Price with Status Detection ---
def get_perth_mint_data():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(PERTH_MINT_1G_URL, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Check for "Unavailable" or "Closed" indicators
        page_text = soup.get_text().lower()
        if "pricing is unavailable" in page_text or "buying closed" in page_text or "unavailable" in page_text:
            return "Closed"
            
        price_tag = soup.find('span', {'class': 'price'})
        if price_tag:
            clean_price = float(price_tag.text.replace('$', '').replace(',', '').strip())
            return clean_price
        return None
    except Exception:
        return None

# 2. Fetch Market Data
gold_ticker = yf.Ticker("GC=F")
hist_data = gold_ticker.history(period="250d")
moving_avg_50 = hist_data['Close'].rolling(window=50).mean().iloc[-1]
moving_avg_200 = hist_data['Close'].rolling(window=200).mean().iloc[-1]
current_usd = hist_data['Close'].iloc[-1]
aud_rate = yf.Ticker("AUD=X").history(period="1d")['Close'].iloc[-1]
cny_rate = yf.Ticker("CNY=X").history(period="1d")['Close'].iloc[-1]

# 3. Calculations
spot_aud = (current_usd / OUNCE_TO_GRAMS) * aud_rate
spot_cny = (current_usd / OUNCE_TO_GRAMS) * cny_rate
avg_50_aud = (moving_avg_50 / OUNCE_TO_GRAMS) * aud_rate
avg_200_aud = (moving_avg_200 / OUNCE_TO_GRAMS) * aud_rate
target_aud = avg_50_aud * (1 - DIP_PERCENTAGE)

# Handle the Scraped Status
retail_status = get_perth_mint_data()
real_retail_aud = retail_status if isinstance(retail_status, float) else None
real_retail_cny = (real_retail_aud / aud_rate * cny_rate) if real_retail_aud else None

# 4. Content Logic
is_urgent = spot_aud <= target_aud

if retail_status == "Closed":
    retail_info_en = "Official Perth Mint Price: CLOSED/UNAVAILABLE. Please visit the East Perth store for live quotes."
    retail_info_zh = "珀斯铸币局官方价: 暂时关闭或不可用。请直接前往 East Perth 门店咨询实时报价。"
elif real_retail_aud:
    retail_info_en = f"Official Perth Mint 1g Price: ${real_retail_aud:.2f} AUD"
    retail_info_zh = f"珀斯铸币局官方1克价格: ¥{real_retail_cny:.2f} RMB (${real_retail_aud:.2f} AUD)"
else:
    retail_info_en = "Official Perth Mint Price: [Unavailable - Check Link Below]"
    retail_info_zh = "珀斯铸币局官方价格: [暂时不可用 - 请点击下方链接确认]"

# (Trend Table and Strategy text logic same as before)
last_5_days = hist_data['Close'].tail(5).iloc[::-1]
trend_zh = "最近5日金价趋势 (现货):\n"
for date, price in last_5_days.items():
    p_aud = (price / OUNCE_TO_GRAMS) * aud_rate
    p_cny = (price / OUNCE_TO_GRAMS) * cny_rate
    trend_zh += f"• {date.strftime('%m月%d日')}: ¥{p_cny:.2f} RMB (${p_aud:.2f} AUD)\n"

ma_explanation_zh = "均线小知识:\n• 50日线: 中期趋势。低5%是抄底机会。\n• 200日线: 长期牛熊线。接近此线是极佳买点。"
strategy_zh = "建议策略:\n• 连跌3天+? 可再等24h。\n• 今日反弹? 建议立即购买。"

mandarin_block = (
    f"--- 中文报告 ---\n"
    f"市场现货价: ¥{spot_cny:.2f} RMB (${spot_aud:.2f} AUD)\n"
    f"{retail_info_zh}\n"
    f"50日均线价: ¥{(avg_50_aud/aud_rate*cny_rate):.2f} RMB (${avg_50_aud:.2f} AUD)\n"
    f"200日均线价: ¥{(avg_200_aud/aud_rate*cny_rate):.2f} RMB (${avg_200_aud:.2f} AUD)\n\n"
    f"{ma_explanation_zh}\n\n"
    f"{trend_zh}\n"
    f"{strategy_zh}\n\n"
    f"直达链接: {PERTH_MINT_1G_URL}\n"
)

# Email Delivery (Shortened for brevity)
sender_email = os.environ.get("GMAIL_ADDRESS")
app_password = os.environ.get("GMAIL_APP_PASSWORD")
with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
    smtp.login(sender_email, app_password)
    for email, mode in RECEIVERS.items():
        if not email: continue
        msg = EmailMessage()
        msg['From'] = sender_email
        msg['To'] = email
        msg['Subject'] = f"{'!! URGENT !! ' if is_urgent else ''}Gold Update: ${spot_aud:.2f} AUD"
        msg.set_content(mandarin_block if mode == "Mandarin" else f"--- ENGLISH REPORT ---\nSpot: ${spot_aud:.2f}\n{retail_info_en}\n\n{mandarin_block}")
        smtp.send_message(msg)
