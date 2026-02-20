import yfinance as yf
import smtplib
from email.message import EmailMessage
import os
import pandas as pd
from datetime import datetime

# 1. 设置衡量标准
DIP_PERCENTAGE = 0.05  
OUNCE_TO_GRAMS = 31.1034768
EST_PREMIUM = 1.15     
PERTH_MINT_1G_URL = "https://www.perthmint.com/shop/bullion/minted-bars/kangaroo-1g-minted-gold-bar/"

RECEIVERS = {
    os.environ.get("GMAIL_ADDRESS"): "Bilingual",
    os.environ.get("SECONDARY_GMAIL_ADDRESS"): "Mandarin"
}

# 2. 获取数据
gold_ticker = yf.Ticker("GC=F")
hist_data = gold_ticker.history(period="250d")

moving_avg_50 = hist_data['Close'].rolling(window=50).mean().iloc[-1]
moving_avg_200 = hist_data['Close'].rolling(window=200).mean().iloc[-1]
current_usd = hist_data['Close'].iloc[-1]

aud_rate = yf.Ticker("AUD=X").history(period="1d")['Close'].iloc[-1]
cny_rate = yf.Ticker("CNY=X").history(period="1d")['Close'].iloc[-1]

# 3. 价格计算
spot_aud = (current_usd / OUNCE_TO_GRAMS) * aud_rate
spot_cny = (current_usd / OUNCE_TO_GRAMS) * cny_rate
avg_50_aud = (moving_avg_50 / OUNCE_TO_GRAMS) * aud_rate
avg_200_aud = (moving_avg_200 / OUNCE_TO_GRAMS) * aud_rate
target_aud = avg_50_aud * (1 - DIP_PERCENTAGE)

# --- 新增：自动维护黄金存折 (CSV) ---
def save_to_passbook(s_aud, s_cny, m50, m200):
    file_name = "gold_passbook.csv"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # 准备新数据
    new_entry = pd.DataFrame([{
        "Date": now,
        "Spot_AUD_g": round(s_aud, 2),
        "Spot_CNY_g": round(s_cny, 2),
        "MA50_AUD": round(m50, 2),
        "MA200_AUD": round(m200, 2),
        "Est_Shop_AUD": round(s_aud * EST_PREMIUM, 2)
    }])
    
    # 如果文件不存在，写入表头；否则追加
    if not os.path.isfile(file_name):
        new_entry.to_csv(file_name, index=False)
    else:
        new_entry.to_csv(file_name, mode='a', header=False, index=False)

# 执行保存
save_to_passbook(spot_aud, spot_cny, avg_50_aud, avg_200_aud)
# --------------------------------

# 4. 5日趋势表
last_5_days = hist_data['Close'].tail(5).iloc[::-1]
trend_en = "Last 5 Days (Spot AUD/g):\n"
trend_zh = "最近5日金价趋势 (现货):\n"

for date, price in last_5_days.items():
    p_aud = (price / OUNCE_TO_GRAMS) * aud_rate
    p_cny = (price / OUNCE_TO_GRAMS) * cny_rate
    trend_en += f"• {date.strftime('%d %b')}: ${p_aud:.2f}\n"
    trend_zh += f"• {date.strftime('%m月%d日')}: ¥{p_cny:.2f} RMB (${p_aud:.2f} AUD)\n"

# 5. 构建内容块
is_urgent = spot_aud <= target_aud

ma_explanation_zh = (
    "均线小知识:\n"
    "• 50日线: 中期趋势。价格低于此线5%是绝佳“抄底”机会。\n"
    "• 200日线: 长期牛熊线。若价格接近此线，是几年一遇的极低买点。"
)

strategy_zh = (
    "建议策略:\n"
    "• 连跌3天+? 可再等24小时看是否有更低价。\n"
    "• 今日反弹? 价格回升开始，建议立即购买。"
)

mandarin_block = (
    f"--- 中文报告 ---\n"
    f"市场现货价: ¥{spot_cny:.2f} RMB/克 (${spot_aud:.2f} AUD)\n"
    f"预计门店价: ¥{spot_cny * EST_PREMIUM:.2f} RMB/克 (${spot_aud * EST_PREMIUM:.2f} AUD)\n"
    f"50日均线价: ¥{(avg_50_aud/aud_rate*cny_rate):.2f} RMB/克 (${avg_50_aud:.2f} AUD)\n"
    f"200日均线价: ¥{(avg_200_aud/aud_rate*cny_rate):.2f} RMB/克 (${avg_200_aud:.2f} AUD)\n"
    f"目标价格 (5%跌幅): ¥{(target_aud/aud_rate*cny_rate):.2f} RMB/克 (${target_aud:.2f} AUD)\n\n"
    f"{ma_explanation_zh}\n\n"
    f"{trend_zh}\n"
    f"{strategy_zh}\n\n"
    f"珀斯铸币局1克金条价格: {PERTH_MINT_1G_URL}\n"
)

english_block = (
    f"--- ENGLISH REPORT ---\n"
    f"Spot Price: ${spot_aud:.2f} AUD/g\n"
    f"Est. Shop Price: ${spot_aud * EST_PREMIUM:.2f} AUD/g\n"
    f"50-Day Avg: ${avg_50_aud:.2f} AUD/g (Target: ${target_aud:.2f})\n"
    f"200-Day Avg: ${avg_200_aud:.2f} AUD/g\n\n"
    f"{trend_en}\n"
    f"STRATEGY:\n• Falling? Wait. • Bouncing? Buy.\n\n"
    f"Perth Mint 1g Price: {PERTH_MINT_1G_URL}\n"
)

# 6. 发送邮件
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
