import yfinance as yf
import pandas as pd
import ta
import time
import requests
import io


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
        print(f"✅ Data for {symbol}:\n{stock.head()}")  # Debug: Inspect the DataFrame
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
        # Ensure the 'Close' and 'Volume' columns are 1-dimensional
        close_prices = df['Close'].squeeze()  # Convert to 1D
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
        print(f"\n📊 Indicator Values for {symbol}:")
        print(f"  - RSI: {latest['RSI'].item():.2f}")
        print(f"  - Close Price: {latest['Close'].item():.2f}")
        print(f"  - Bollinger Lower Band: {latest['BB_Lower'].item():.2f}")
        print(f"  - Bollinger Middle Band: {latest['BB_Middle'].item():.2f}")
        print(f"  - Bollinger Upper Band: {latest['BB_Upper'].item():.2f}")
        print(f"  - MACD: {latest['MACD'].item():.2f}")
        print(f"  - MACD Signal: {latest['Signal'].item():.2f}")

        # Define alert conditions
        alert_message = f"📢 *Stock Alert: {symbol}* 🚀\n"
        alert_triggered = False

        # Define a threshold for "near the lower band" (e.g., within 2%)
        threshold = 0.02  # 2%

        # Check if ALL conditions are met
        rsi_condition = latest['RSI'].item() > 30  # RSI is above 30
        bb_condition = latest['Close'].item() <= latest['BB_Lower'].item() * (1 + threshold)  # Close is near the lower band
        macd_condition = latest['MACD'].item() > latest['Signal'].item()  # MACD Crossover (Bullish Signal)

        # Print conditions for debugging
        print(f"  - RSI Condition (RSI > 30): {rsi_condition}")
        print(f"  - Bollinger Band Condition (Close near Lower Band): {bb_condition}")
        print(f"  - MACD Condition (MACD > Signal): {macd_condition}")

        if rsi_condition and bb_condition and macd_condition:
            alert_message += "🔹 RSI is above 30\n"
            alert_message += "🔹 Price is near Lower Bollinger Band (Potential Reversal)\n"
            alert_message += "🔹 MACD Crossover (Bullish Signal)\n"
            alert_triggered = True

        # Send alert if ALL conditions are met
        if alert_triggered:
            send_telegram_message(alert_message)
        else:
            print(f"✅ {symbol} analyzed. No alerts triggered.")

    except Exception as e:
        print(f"❌ Error analyzing {symbol}: {e}")
    df = get_stock_data(symbol)
    if df is None:
        return

    try:
        # Ensure the 'Close' and 'Volume' columns are 1-dimensional
        close_prices = df['Close'].squeeze()  # Convert to 1D
        volumes = df['Volume'].squeeze()  # Convert to 1D

        # Calculate Bollinger Bands
        bb = ta.volatility.BollingerBands(close_prices, window=20, window_dev=2)
        df['BB_Lower'] = bb.bollinger_lband()

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
        print(f"\n📊 Indicator Values for {symbol}:")
        print(f"  - RSI: {latest['RSI'].item():.2f}")
        print(f"  - Close Price: {latest['Close'].item():.2f}")
        print(f"  - Bollinger Lower Band: {latest['BB_Lower'].item():.2f}")
        print(f"  - MACD: {latest['MACD'].item():.2f}")
        print(f"  - MACD Signal: {latest['Signal'].item():.2f}")

        # Define alert conditions
        alert_message = f"📢 *Stock Alert: {symbol}* 🚀\n"
        alert_triggered = False

        # Check if ALL conditions are met
        rsi_condition = latest['RSI'].item() > 30  # RSI is above 30
        bb_condition = latest['Close'].item() < latest['BB_Lower'].item()  # Price is below Lower Bollinger Band
        macd_condition = latest['MACD'].item() > latest['Signal'].item()  # MACD Crossover (Bullish Signal)

        # Print conditions for debugging
        print(f"  - RSI Condition (RSI > 30): {rsi_condition}")
        print(f"  - Bollinger Band Condition (Close < Lower Band): {bb_condition}")
        print(f"  - MACD Condition (MACD > Signal): {macd_condition}")

        if rsi_condition and bb_condition and macd_condition:
            alert_message += "🔹 RSI is above 30\n"
            alert_message += "🔹 Price is below Lower Bollinger Band (Potential Reversal)\n"
            alert_message += "🔹 MACD Crossover (Bullish Signal)\n"
            alert_triggered = True

        # Send alert if ALL conditions are met
        if alert_triggered:
            send_telegram_message(alert_message)
        else:
            print(f"✅ {symbol} analyzed. No alerts triggered.")

    except Exception as e:
        print(f"❌ Error analyzing {symbol}: {e}")
    df = get_stock_data(symbol)
    if df is None:
        return

    try:
        # Ensure the 'Close' and 'Volume' columns are 1-dimensional
        close_prices = df['Close'].squeeze()  # Convert to 1D
        volumes = df['Volume'].squeeze()  # Convert to 1D

        # Calculate Bollinger Bands
        bb = ta.volatility.BollingerBands(close_prices, window=20, window_dev=2)
        df['BB_Lower'] = bb.bollinger_lband()

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

        # Define alert conditions
        alert_message = f"📢 *Stock Alert: {symbol}* 🚀\n"
        alert_triggered = False

        # Check if ALL conditions are met
        rsi_condition = latest['RSI'].item() < 30  # RSI is below 30 (Oversold)
        bb_condition = latest['Close'].item() < latest['BB_Lower'].item()  # Price is below Lower Bollinger Band
        macd_condition = latest['MACD'].item() > latest['Signal'].item()  # MACD Crossover (Bullish Signal)

        if rsi_condition and bb_condition and macd_condition:
            alert_message += "🔹 RSI is below 30 (Oversold)\n"
            alert_message += "🔹 Price is below Lower Bollinger Band (Potential Reversal)\n"
            alert_message += "🔹 MACD Crossover (Bullish Signal)\n"
            alert_triggered = True

        # Send alert if ALL conditions are met
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
        for symbol in stock_list:
            analyze_stock(symbol)
            time.sleep(2)  # Prevents rate-limiting issues
    except KeyboardInterrupt:
        print("\n🛑 Script stopped by user.")