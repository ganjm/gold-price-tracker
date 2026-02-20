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

# --- 核心逻辑：自动维护行情存折 ---
def save_to_passbook(s_aud, s_cny, m50, m200):
    file_name = "gold_passbook.csv"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_entry = pd.DataFrame([{"Date": now, "Spot_AUD_g": round(s_aud, 2), "Spot_CNY_g": round(s_cny, 2), "MA50_AUD": round(m50, 2), "MA200_AUD": round(m200, 2), "Est_Shop_AUD": round(s_aud * EST_PREMIUM, 2)}])
    if not os.path.isfile(file_name):
        new_entry.to_csv(file_name, index=False)
    else:
        new_entry.to_csv(file_name, mode='a', header=False, index=False)

save_to_passbook(spot_aud, spot_cny, avg_50_aud, avg_200_aud)

# --- 新增逻辑：计算持仓成本与盈亏 ---
holdings_summary_en = ""
holdings_summary_zh = ""

if os.path.isfile("my_holdings.csv"):
    try:
        df_h = pd.read_csv("my_holdings.csv")
        if not df_h.empty:
            total_grams = df_h['Grams'].sum()
            total_cost = (df_h['Grams'] * df_h['Price_Paid_AUD']).sum()
            avg_cost = total_cost / total_grams
            current_value = total_grams * spot_aud
            profit_loss = current_value - total_cost
            pl_percent = (profit_loss / total_cost) * 100
            
            holdings_summary_en = (
                f"YOUR PORTFOLIO:\n"
                f"• Total Grams: {total_grams}g\n"
                f"• Avg Cost: ${avg_cost:.2f} AUD/g\n"
                f"• P/L: ${profit_loss:.2f} AUD ({pl_percent:+.2f}%)\n\n"
            )
            holdings_summary_zh = (
                f"您的投资组合:\n"
                f"• 总持有量: {total_grams}克\n"
                f"• 平均成本: ${avg_cost:.2f} AUD/克\n"
                f"• 当前盈亏: ${profit_loss:.2f} AUD ({pl_percent:+.2f}%)\n\n"
            )
    except Exception:
        pass

# 4. 邮件内容构建 (整合持仓信息)
is_urgent = spot_aud <= target_aud
last_5_days = hist_data['Close'].tail(5).iloc[::-1]
trend_zh = "最近5日金价趋势:\n"
for date, price in last_5_days.items():
    p_aud = (price / OUNCE_TO_GRAMS) * aud_rate
    p_cny = (price / OUNCE_TO_GRAMS) * cny_rate
    trend_zh += f"• {date.strftime('%m月%d日')}: ¥{p_cny:.2f} RMB (${p_aud:.2f} AUD)\n"

ma_explanation_zh = "均线小知识:\n• 50日线: 中期趋势。低5%是抄底机会。\n• 200日线: 长期牛熊线。接近此线是极佳买点。"
strategy_zh = "建议策略:\n• 连跌3天+? 可再等24h。\n• 今日反弹? 建议立即购买。"

mandarin_block = (
    f"--- 中文报告 ---\n"
    f"{holdings_summary_zh}"
    f"市场现货价: ¥{spot_cny:.2f} RMB (${spot_aud:.2f} AUD)\n"
    f"50日均线价: ¥{(avg_50_aud/aud_rate*cny_rate):.2f} RMB (${avg_50_aud:.2f} AUD)\n"
    f"目标买入价: ¥{(target_aud/aud_rate*cny_rate):.2f} RMB (${target_aud:.2f} AUD)\n\n"
    f"{ma_explanation_zh}\n\n"
    f"{trend_zh}\n"
    f"{strategy_zh}\n\n"
    f"珀斯铸币局1克金条价格: {PERTH_MINT_1G_URL}\n"
)

english_block = (
    f"--- ENGLISH REPORT ---\n"
    f"{holdings_summary_en}"
    f"Spot Price: ${spot_aud:.2f} AUD/g\n"
    f"50-Day Avg: ${avg_50_aud:.2f} AUD/g\n\n"
    f"STRATEGY:\n• Falling? Wait. • Bouncing? Buy.\n\n"
    f"Perth Mint 1g Price: {PERTH_MINT_1G_URL}\n"
)

# 5. 发送邮件 (代码同前，略)
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
        msg.set_content(f"{english_block}\n{mandarin_block}" if mode == "Bilingual" else mandarin_block)
        smtp.send_message(msg)
