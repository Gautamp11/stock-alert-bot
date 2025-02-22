import pandas as pd
import ta
import time
import requests
import io
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import smtplib
from email.message import EmailMessage
import datetime
from nsepython import *



# Get the current date in YYYY-MM-DD format
current_date = datetime.datetime.now().strftime("%Y-%m-%d")


# Define a threshold for "near the lower band" (e.g., within 2%)
threshold = 0.02  # 2%

# NSE CSV URL
NSE_CSV_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"

# Email Configuration
EMAIL_SENDER = "gautamstyles3@gmail.com"  # Replace with your email
EMAIL_PASSWORD = "yoyb ozep drlj ufwx"  # Replace with your email password
EMAIL_RECEIVER = "gautam1133p1@gmail.com"

# Function to fetch NSE stock symbols
def get_nse_symbols():
    try:
        print("🔄 Fetching stock symbols from NSE...")
        response = requests.get(NSE_CSV_URL)
        if response.status_code != 200:
            print(f"❌ Error fetching CSV (HTTP {response.status_code})")
            return []
        df = pd.read_csv(io.StringIO(response.text))
        if 'SYMBOL' in df.columns:
            symbols = df['SYMBOL'].tolist()
            print(f"✅ Loaded {len(symbols)} stock symbols.")
            return symbols
        else:
            print("❌ 'SYMBOL' column not found in CSV.")
            return []
    except Exception as e:
        print(f"❌ Error reading NSE CSV: {e}")
        return []

# Function to fetch stock data using nsepython
def get_stock_data(symbol):
    try:
        print(f"🔄 Fetching data for {symbol}...")
        stock = nse_fno_hist(symbol, "OPTSTK", "6M", "daily")
        if stock.empty:
            print(f"⚠ No data found for {symbol}. Skipping...")
            return None
        stock.reset_index(inplace=True)
        return stock
    except Exception as e:
        print(f"❌ Error fetching {symbol}: {e}")
        return None

# Function to analyze stock data
def analyze_stock(symbol, results):
    df = get_stock_data(symbol)
    if df is None:
        return
    try:
        close_prices = df['close'].squeeze()
        latest_close = close_prices.iloc[-1]
        if latest_close < 100:
            print(f"⏭ Skipping {symbol}: Close price ₹{latest_close:.2f} is below ₹100.")
            return
        volumes = df['volume'].squeeze()
        df['RSI'] = ta.momentum.RSIIndicator(close_prices, window=14).rsi()
        latest_RSI = df['RSI'].iloc[-1]
        print(f"📊 {symbol}: Close: ₹{latest_close:.2f}, RSI: {latest_RSI:.2f}")
        if latest_RSI > 50:
            results.append({"Stock": symbol, "Close Price": latest_close, "RSI": latest_RSI})
    except Exception as e:
        print(f"❌ Error analyzing {symbol}: {e}")

# Function to create an Excel report
def create_excel_report(data):
    df = pd.DataFrame(data)
    filename = f"Stock_Analysis_Report_{current_date}.xlsx"
    df.to_excel(filename, index=False)
    return filename

# Function to send email with attachment
def send_email(attachment_path):
    try:
        msg = EmailMessage()
        msg['Subject'] = "Stock Analysis Report"
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER
        msg.set_content("Find the attached stock analysis report.")
        with open(attachment_path, 'rb') as f:
            msg.add_attachment(f.read(), maintype='application', subtype='octet-stream', filename=os.path.basename(attachment_path))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        print("Email sent successfully!")
    except Exception as e:
        print(f"Error sending email: {e}")

# Main execution
if __name__ == "__main__":
    stock_list = get_nse_symbols()
    results = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(analyze_stock, symbol, results): symbol for symbol in stock_list}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"❌ Error processing {futures[future]}: {e}")
    if results:
        report_path = create_excel_report(results)
        send_email(report_path)
    else:
        print("✅ No alerts triggered. No email sent.")