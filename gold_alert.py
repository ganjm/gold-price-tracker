import yfinance as yf
import smtplib
from email.message import EmailMessage
import os
import pandas as pd

# 1. SET YOUR EDUCATED MEASURES
DIP_PERCENTAGE = 0.05  
OUNCE_TO_GRAMS = 31.1034768
EST_PREMIUM = 1.15     
# Direct link to the 1g Minted Bar page
PERTH_MINT_1G_URL = "https://www.perthmint.com/shop/bullion/minted-bars/kangaroo-1g-minted-gold-bar/"

RECEIVERS = {
    os.environ.get("GMAIL_ADDRESS"): "Bilingual",
    os.environ.get("SECONDARY_GMAIL_ADDRESS"): "Mandarin"
}

# 2. Fetch Historical & Live Data
gold_ticker = yf.Ticker("GC=F")
hist_data = gold_ticker.history(period="60d")
moving_avg_50 = hist_data['Close'].rolling(window=50).mean().iloc[-1]
current_usd = hist_data['Close'].iloc[-1]

aud_rate = yf.Ticker("AUD=X").history(period="1d")['Close'].iloc[-1]
cny_rate = yf.Ticker("CNY=X").history(period="1d")['Close'].iloc[-1]

# 3. Perform Calculations
spot_aud = (current_usd / OUNCE_TO_GRAMS) * aud_rate
spot_cny = (current_usd / OUNCE_TO_GRAMS) * cny_rate
avg_aud_gram = (moving_avg_50 / OUNCE_TO_GRAMS) * aud_rate
target_aud = avg_aud_gram * (1 - DIP_PERCENTAGE)

# 4. Create 5-Day Trend Tables
last_5_days = hist_data['Close'].tail(5).iloc[::-1]
trend_en = "Last 5 Days (Spot AUD/g):\n"
trend_zh = "最近5日金价趋势 (现货 AUD/克):\n"

for date, price in last_5_days.items():
    p_aud = (price / OUNCE_TO_GRAMS) * aud_rate
    trend_en += f"{date.strftime('%d %b')}: ${p_aud:.2f}\n"
    trend_zh += f"{date.strftime('%m月%d日')}: ${p_aud:.2f} AUD\n"

# 5. Build Content Blocks
is_urgent = spot_aud <= target_aud

strategy_en = (
    "STRATEGY:\n"
    "• Dropping 3+ days? Wait 24h for a possible lower 'floor'.\n"
    "• Price higher than yesterday? The 'bounce' may have started; buy now."
)

strategy_zh = (
    "建议策略:\n"
    "• 连续下跌3天以上? 可再等24小时观察是否有更低“底部”。\n"
    "• 今日价格高于昨日? 价格可能已经开始反弹，建议立即前往购买。"
)

english_block = (
    f"--- ENGLISH REPORT ---\n"
    f"Spot Price: ${spot_aud:.2f} AUD/g\n"
    f"Est. Shop Price: ${spot_aud * EST_PREMIUM:.2f} AUD/g (15% Premium)\n"
    f"50-Day Avg: ${avg_aud_gram:.2f} AUD/g\n"
    f"Target (5% dip): ${target_aud:.2f} AUD/g\n\n"
    f"{trend_en}\n"
    f"{strategy_en}\n\n"
    f"Perth Mint 1g Bar Price: {PERTH_MINT_1G_URL}\n"
)

mandarin_block = (
    f"--- 中文报告 ---\n"
    f"市场现货价: ¥{spot_cny:.2f} RMB/克 (${spot_aud:.2f} AUD)\n"
    f"预计门店价: ¥{spot_cny * EST_PREMIUM:.2f} RMB/克 (含15%溢价)\n"
    f"50日均线价: ¥{(avg_aud_gram/aud_rate*cny_rate):.2f} RMB/克\n"
    f"目标价格 (5% 跌幅): ¥{(target_aud/aud_rate*cny_rate):.2f} RMB/克\n\n"
    f"{trend_zh}\n"
    f"{strategy_zh}\n\n"
    f"珀斯铸币局1克金条价格: {PERTH_MINT_1G_URL}\n"
)

# 6. Email Delivery
sender_email = os.environ.get("GMAIL_ADDRESS")
app_password = os.environ.get("GMAIL_APP_PASSWORD")

with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
    smtp.login(sender_email, app_password)
    for email, mode in RECEIVERS.items():
        if not email: continue
        msg = EmailMessage()
        msg['From'] = sender_email
        msg['To'] = email
        
        prefix = ("!! URGENT !! " if is_urgent else "")
        msg['Subject'] = f"{prefix}Gold Update | 黄金更新: ${spot_aud:.2f} AUD"
        
        if mode == "Bilingual":
            msg.set_content(f"{english_block}\n{mandarin_block}")
        else:
            msg.set_content(mandarin_block)
            
        smtp.send_message(msg)
