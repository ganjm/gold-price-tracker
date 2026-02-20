import yfinance as yf
import smtplib
from email.message import EmailMessage
import os

# 1. Set our targets and recipients
TARGET_PRICE_AUD = 235.00
OUNCE_TO_GRAMS = 31.1034768

# This tells Python to go to the GitHub "Vault" to find the addresses
RECEIVERS = {
    os.environ.get("GMAIL_ADDRESS"): "English",
    os.environ.get("SECONDARY_GMAIL_ADDRESS"): "Mandarin"
}

# 2. Fetch Live Market Data
gold_ticker = yf.Ticker("GC=F")
aud_ticker = yf.Ticker("AUD=X")
cny_ticker = yf.Ticker("CNY=X") # Fetches USD/CNY exchange rate

# Get the most recent closing prices
gold_usd_oz = gold_ticker.history(period="1d")['Close'].iloc[-1]
usd_to_aud = aud_ticker.history(period="1d")['Close'].iloc[-1]
usd_to_cny = cny_ticker.history(period="1d")['Close'].iloc[-1]

# 3. Calculate Gold Prices
gold_usd_gram = gold_usd_oz / OUNCE_TO_GRAMS
gold_aud_gram = gold_usd_gram * usd_to_aud
gold_cny_gram = gold_usd_gram * usd_to_cny # Calculate price in CNY

# 4. Connect to Gmail and Send Emails
sender_email = os.environ.get("GMAIL_ADDRESS")
app_password = os.environ.get("GMAIL_APP_PASSWORD")

with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
    smtp.login(sender_email, app_password)
    
    for receiver_email, language in RECEIVERS.items():
        if not receiver_email: continue # Skip if secret is missing
        msg = EmailMessage()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        
        # --- ENGLISH EMAIL ---
        if language == "English":
            if gold_aud_gram <= TARGET_PRICE_AUD:
                msg['Subject'] = f"URGENT: Gold dropped to ${gold_aud_gram:.2f} AUD!"
                msg['X-Priority'] = '1'
                msg['X-MSMail-Priority'] = 'High'
                msg['Importance'] = 'High'
                msg.set_content(
                    f"ACTION REQUIRED: The price of gold has reached your target!\n\n"
                    f"Current Price: ${gold_aud_gram:.2f} AUD/gram\n"
                    f"Target Price: ${TARGET_PRICE_AUD:.2f} AUD/gram\n\n"
                    f"The market conditions are currently meeting your requirements."
                )
            else:
                msg['Subject'] = f"Daily Gold Update: ${gold_aud_gram:.2f} AUD"
                msg.set_content(
                    f"Here is your daily gold price update.\n\n"
                    f"Current Price: ${gold_aud_gram:.2f} AUD/gram\n"
                    f"Target Price: ${TARGET_PRICE_AUD:.2f} AUD/gram"
                )
                
        # --- MANDARIN SIMPLIFIED EMAIL ---
        elif language == "Mandarin":
            if gold_aud_gram <= TARGET_PRICE_AUD:
                msg['Subject'] = f"紧急通知：金价已降至 ${gold_aud_gram:.2f} AUD!"
                msg['X-Priority'] = '1'
                msg['X-MSMail-Priority'] = 'High'
                msg['Importance'] = 'High'
                msg.set_content(
                    f"需要采取行动：金价已达到您的目标价格！\n\n"
                    f"当前价格 (AUD): ${gold_aud_gram:.2f} AUD/克\n"
                    f"当前价格 (CNY): ¥{gold_cny_gram:.2f} RMB/克\n"
                    f"目标价格: ${TARGET_PRICE_AUD:.2f} AUD/克\n\n"
                    f"目前的市场状况符合您的要求。"
                )
            else:
                msg['Subject'] = f"每日黄金价格更新：${gold_aud_gram:.2f} AUD"
                msg.set_content(
                    f"这是您的每日黄金价格更新。\n\n"
                    f"当前价格 (AUD): ${gold_aud_gram:.2f} AUD/克\n"
                    f"当前价格 (CNY): ¥{gold_cny_gram:.2f} RMB/克\n"
                    f"目标价格: ${TARGET_PRICE_AUD:.2f} AUD/克\n\n"
                    f"价格尚未达到您的目标。"
                )
                
        smtp.send_message(msg)

print(f"Updates sent! AUD: {gold_aud_gram:.2f} | CNY: {gold_cny_gram:.2f}")
