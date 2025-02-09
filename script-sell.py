import yfinance as yf
import pandas as pd
import ta
import time
import requests
import io
from concurrent.futures import ThreadPoolExecutor, as_completed

# Define a threshold for "near the lower band" (e.g., within 2%)
threshold = 0.02  # 2%

# NSE CSV URL
NSE_CSV_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"

# Telegram Bot Details
TELEGRAM_BOT_TOKEN = "7896879656:AAG-3v7HhkmT20AnhC_CpBGKpiZyUmsu1Ao"
TELEGRAM_CHAT_ID = "6144704496"

# Function to send messages to Telegram
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print(f"✅ Alert sent: {message}")
        else:
            print(f"❌ Telegram Error: {response.text}")
    except Exception as e:
        print(f"❌ Telegram Exception: {e}")

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
def analyze_stock(symbol):
    df = get_stock_data(symbol)
    if df is None:
        return

    try:
        # Ensure the 'Close' column is available
        close_prices = df['Close'].squeeze()  # Convert to 1D
        latest_close = close_prices.iloc[-1]  # Get the latest closing price

        # **NEW: Skip if price is below ₹100**
        if latest_close < 100:
            print(f"⏭ Skipping {symbol}: Close price ₹{latest_close:.2f} is below ₹100.")
            return

        volumes = df['Volume'].squeeze()  # Convert to 1D

        # Calculate Bollinger Bands
        bb = ta.volatility.BollingerBands(close_prices, window=20, window_dev=2)
        df['BB_Lower'] = bb.bollinger_lband()
        df['BB_Middle'] = bb.bollinger_mavg()
        df['BB_Upper'] = bb.bollinger_hband()

        # Calculate OBV
        df['OBV'] = ta.volume.OnBalanceVolumeIndicator(close_prices, volumes).on_balance_volume()

        # Calculate RSI
        df['RSI'] = ta.momentum.RSIIndicator(close_prices, window=14).rsi()

        # Calculate MACD
        macd = ta.trend.MACD(close_prices)
        df['MACD'] = macd.macd()
        df['Signal'] = macd.macd_signal()

        # Get the latest row
        latest = df.iloc[-1]

        # Print indicator values for debugging
        print(f"\n📊 Indicator Values for {symbol} (Close: ₹{latest_close:.2f}):")
        print(f"  - RSI: {latest['RSI'].item():.2f}")
        print(f"  - Bollinger Upper Band: {latest['BB_Upper'].item():.2f}")
        print(f"  - MACD: {latest['MACD'].item():.2f}")

        # Define alert conditions
        alert_message = f"📢 *Stock Sell Alert: {symbol}* 🚀\n"
        alert_triggered = False

        # Check if ALL conditions are met
        rsi_condition = latest['RSI'].item() > 70  # RSI above 70
        bb_condition = latest['Close'].item() >= latest['BB_Upper'].item() * (1 - threshold)    # Close above upper band
        macd_condition = latest['MACD'].item() < latest['Signal'].item()  # MACD crossover

        if rsi_condition and bb_condition and macd_condition:
            alert_message += "🔹 RSI is above 70\n"
            alert_message += "🔹 Price is above upper Bollinger Band (Potential Reversal)\n"
            alert_message += "🔹 MACD Crossover (Bearish Signal)\n"
            alert_triggered = True

        # Send alert if conditions met
        if alert_triggered:
            send_telegram_message(alert_message)
        else:
            print(f"✅ {symbol} analyzed. No alerts triggered.")

    except Exception as e:
        print(f"❌ Error analyzing {symbol}: {e}")

# Main execution
if __name__ == "__main__":
    stock_list = get_nse_symbols()  # Fetch latest NSE stock symbols

    try:
        # Use ThreadPoolExecutor to parallelize stock analysis
        with ThreadPoolExecutor(max_workers=1) as executor:  # Adjust max_workers based on your system's capabilities
            futures = {executor.submit(analyze_stock, symbol): symbol for symbol in stock_list}
            
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    future.result()  # Wait for the task to complete
                except Exception as e:
                    print(f"❌ Error processing {symbol}: {e}")
    except KeyboardInterrupt:
        print("\n🛑 Script stopped by user.")