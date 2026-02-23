# 🪙 Perth Gold Tracker & Portfolio Manager

An automated Python tool designed for residents of **East Perth** to track live gold prices, manage a personal gold "passbook," and receive timely alerts for local buying opportunities at **The Perth Mint**.

## ✨ Key Features

* **Dual-Frequency Alerts**: Automatically sends email updates at **10:00 AM** and **3:00 PM** AWST (Monday–Saturday).
* **Perth Mint Scraping**: Directly scrapes the live retail price for **1g and 5g gold bars** from the official Perth Mint website.
* **Intelligent Trading Status**: 
    * Detects if the Bullion Trading room is **Open** or **Closed** based on the time and day.
    * Pre-programmed with **2026 WA Public Holidays** (e.g., Labour Day, Anzac Day) to warn you before you walk to the shop.
    * Recognizes the **4:00 PM cut-off** for in-person trading.
* **Financial Analysis**: 
    * Calculates **50-day and 200-day Moving Averages** to identify "dip" buying opportunities.
    * Automated **"Gold Passbook"** (CSV) that logs market history every time the script runs.
    * **Portfolio Tracking**: Reads `my_holdings.csv` to calculate your average cost and current profit/loss.
* **Bilingual Reporting**: Sends a professional bilingual report (English/Mandarin) to your primary email and a streamlined Mandarin report to your secondary email.

---

## 🛠️ Setup & Installation

### 1. Repository Secrets
Add the following **Secrets** to your GitHub repository (**Settings > Secrets and variables > Actions**):

| Secret Name | Description |
| :--- | :--- |
| `GMAIL_ADDRESS` | Your primary Gmail address (sender and bilingual receiver). |
| `GMAIL_APP_PASSWORD` | A 16-digit App Password from your Google Account. |
| `SECONDARY_GMAIL_ADDRESS` | Your second Gmail address for Mandarin-only alerts. |

### 2. Enable Write Permissions
The script must be allowed to save the CSV files back to your repository:
1. Go to **Settings > Actions > General**.
2. Under **Workflow permissions**, select **"Read and write permissions"**.
3. Click **Save**.

### 3. Personal Holdings (Optional)
To track your profit, create a file named `my_holdings.csv` in the root folder with this format:
```csv
Date,Grams,Price_Paid_AUD
2026-02-21,1,268.50
