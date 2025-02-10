import yfinance as yf
import pandas as pd
import ta
import time
import requests
import io
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import smtplib
from email.message import EmailMessage
from datetime import datetime


# Get the current date in YYYY-MM-DD format
current_date = datetime.now().strftime("%Y-%m-%d")

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

        # Read CSV from response
        df = pd.read_csv(io.StringIO(response.text))
        
        # Check the correct column name (NSE CSV may change formats)
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

# Function to fetch stock data
def get_stock_data(symbol):
    try:
        print(f"🔄 Fetching data for {symbol}...")
        stock = yf.download(f"{symbol}.NS", period="6mo", interval="1d")

        if stock.empty:
            print(f"⚠ No data found for {symbol}. Skipping...")
            return None
        
        stock.reset_index(inplace=True)
        return stock
    except Exception as e:
        print(f"❌ Error fetching {symbol}: {e}")
        return None

# Function to analyze stock data
def analyze_stock(symbol,results):
    df = get_stock_data(symbol)
    if df is None:
        return

    try:
        # Ensure the 'Close' column is available
        close_prices = df['Close'].squeeze()  # Convert to 1D
        latest_close = close_prices.iloc[-1]  # Get the latest closing price

        # Skip if price is below ₹100
        if latest_close < 100:
            print(f"⏭ Skipping {symbol}: Close price ₹{latest_close:.2f} is below ₹100.")
            return
        
        volumes = df['Volume'].squeeze()  # Convert to 1D


        df['OBV'] = ta.volume.OnBalanceVolumeIndicator(close_prices, volumes).on_balance_volume()
        latest_OBV = df['OBV'].iloc[-1]


        # Calculate EMAs
        df['EMA_10'] = ta.trend.EMAIndicator(close_prices, window=10).ema_indicator()
        df['EMA_21'] = ta.trend.EMAIndicator(close_prices, window=21).ema_indicator()
        df['EMA_50'] = ta.trend.EMAIndicator(close_prices, window=50).ema_indicator()
       
       # Calculate Bollinger Bands
        bb = ta.volatility.BollingerBands(close_prices, window=20, window_dev=2)
        df['BB_Upper'] = bb.bollinger_hband()
        df['BB_Lower'] = bb.bollinger_lband()
        df['BB_Middle'] = bb.bollinger_mavg()

        # Calculate RSI
        df['RSI'] = ta.momentum.RSIIndicator(close_prices, window=14).rsi()

        # Calculate MACD
        macd = ta.trend.MACD(close_prices)
        df['MACD'] = macd.macd()
        df['Signal'] = macd.macd_signal()

        # Get the latest row
        latest = df.iloc[-1]
        # Define conditions
        # bb_near_lower = latest_close <= latest['BB_Lower'].item() * (1 + threshold)
        ema_condition = latest['EMA_10'].item() > latest['EMA_21'].item() > latest['EMA_50'].item()
        rsi_condition = latest['RSI'].item() > 50
        # adx_condition = latest['ADX'].item() > 20  # Strong trend confirmation
        macd_condition = latest['MACD'].item() > latest['Signal'].item() and latest['MACD'].item() > 0

        volume_condition = latest_OBV > df['OBV'].iloc[-3:].mean()  # OBV rising

                # Print indicator values for debugging
        print(f"\n📊 Indicator Values for {symbol} (Close: ₹{latest_close:.2f}):")
        print(f"  - RSI: {latest['RSI'].item():.2f}")
        # print(f"  - ADX: {latest['ADX'].item():.2f}")
        print(f"  - MACD: {latest['MACD'].item():.2f}")
        # print(f"  - Bollinger Lower Band: {latest['BB_Lower'].item():.2f}")
        print(f"  - EMA: {ema_condition}")
        print(f"  - OBV: {volume_condition}")



        if ema_condition and macd_condition and rsi_condition and volume_condition:
            print(f"{symbol} meets all conditions!")
            results.append({
                "Stock": symbol,
                "Close Price": round(latest_close, 2),
                "RSI": round(latest['RSI'].item(), 2),
                "EMA_10": round(latest['EMA_10'].item(), 2),
                "EMA_21": round(latest['EMA_21'].item(), 2),
                "EMA_50": round(latest['EMA_50'].item(), 2),
                "MACD": round(latest['MACD'].item(), 2),
                "OBV": round(latest['OBV'].item(),2)
                # "BB_Lower": round(latest['BB_Lower'].item(), 2),
                # "ADX": round(latest['ADX'], 2)
            })
        else:
            print(f"✅ {symbol} analyzed. No alerts triggered.")

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
# if __name__ == "__main__":

    # Create a DataFrame to store results

# Main execution
if __name__ == "__main__":
    stock_list = get_nse_symbols()  # Fetch latest NSE stock symbols
    try:
        results = []
        with ThreadPoolExecutor(max_workers=1) as executor:
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
    except KeyboardInterrupt:
        print("\n🛑 Script stopped by user.")



