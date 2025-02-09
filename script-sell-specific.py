import yfinance as yf
import pandas as pd
import ta
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# Define a threshold for "near the upper band" (e.g., within 2%)
threshold = 0.02  # 2%

# Telegram Bot Details
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID"

# List of specific stocks to analyze
stock_list = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK","Maruti"]  # Modify as needed

# Function to send messages to Telegram
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print(f"✅ Alert sent: {message}")
        else:
            print(f"❌ Telegram Error: {response.text}")
    except Exception as e:
        print(f"❌ Telegram Exception: {e}")

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
        close_prices = df['Close'].squeeze()
        latest_close = close_prices.iloc[-1]

        if latest_close < 100:
            print(f"⏭ Skipping {symbol}: Close price ₹{latest_close:.2f} is below ₹100.")
            return

        volumes = df['Volume'].squeeze()

        # Calculate Bollinger Bands
        bb = ta.volatility.BollingerBands(close_prices, window=20, window_dev=2)
        df['BB_Upper'] = bb.bollinger_hband()
        df['RSI'] = ta.momentum.RSIIndicator(close_prices, window=14).rsi()
        macd = ta.trend.MACD(close_prices)
        df['MACD'] = macd.macd()
        df['Signal'] = macd.macd_signal()

        latest = df.iloc[-1]

        # Define alert conditions
        alert_message = f"📢 *Stock Sell Alert: {symbol}* 🚀\n"
        alert_triggered = False

        rsi_condition = latest['RSI'].item() > 70
        bb_condition = latest['Close'].item() >= latest['BB_Upper'].item() * (1 - threshold)
        macd_condition = latest['MACD'].item() < latest['Signal'].item()

     # Print indicator values for debugging
        print(f"\n📊 Indicator Values for {symbol} (Close: ₹{latest_close:.2f}):")
        print(f"  - RSI: {latest['RSI'].item():.2f}")
        print(f"  - Bollinger Upper Band: {latest['BB_Upper'].item():.2f}")
        print(f"  - MACD: {latest['MACD'].item():.2f}")
        print(f"  - MACD: {latest['Signal'].item():.2f}")

        if rsi_condition and bb_condition and macd_condition:
            alert_message += "🔹 RSI is above 70\n"
            alert_message += "🔹 Price is above upper Bollinger Band\n"
            alert_message += "🔹 MACD Crossover (Bearish Signal)\n"
            alert_triggered = True

        if alert_triggered:
            send_telegram_message(alert_message)
        else:
            print(f"✅ {symbol} analyzed. No alerts triggered.")

    except Exception as e:
        print(f"❌ Error analyzing {symbol}: {e}")

# Main execution
if __name__ == "__main__":
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            futures = {executor.submit(analyze_stock, symbol): symbol for symbol in stock_list}
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    future.result()
                except Exception as e:
                    print(f"❌ Error processing {symbol}: {e}")
    except KeyboardInterrupt:
        print("\n🛑 Script stopped by user.")
