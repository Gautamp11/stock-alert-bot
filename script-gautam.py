import yfinance as yf
import pandas as pd
import ta
import time
import requests
import io
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from queue import Queue
import os

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = "7896879656:AAG-3v7HhkmT20AnhC_CpBGKpiZyUmsu1Ao"
TELEGRAM_CHAT_ID = "6144704496"

# NSE CSV URL
NSE_CSV_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"

# Threshold for "near the lower band" (e.g., within 2%)
threshold = 0.02  # 2%

# Global thread-safe queue to store analysis results
analysis_queue = Queue()

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
            symbols = df['SYMBOL'].unique().tolist()  # Use unique() to remove duplicates
            print(f"✅ Loaded {len(symbols)} unique stock symbols.")
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
        # Ensure the symbol ends with .NS
        symbol_with_suffix = f"{symbol}.NS" if not symbol.endswith('.NS') else symbol
        print(f"🔄 Fetching data for {symbol_with_suffix}...")
        
        # Fetch data using yfinance
        stock = yf.download(symbol_with_suffix, period="6mo", interval="1d", auto_adjust=True)
        time.sleep(2)  # Add a delay to avoid rate limits
        
        # Check if data is empty
        if stock.empty:
            print(f"⚠ No data found for {symbol_with_suffix}. Skipping...")
            return None
        
        # Reset index and return the DataFrame
        stock.reset_index(inplace=True)
        return symbol, stock  # Return both symbol and data
    except Exception as e:
        print(f"❌ Error fetching {symbol}: {e}")
        return None

# Function to analyze stock data
def analyze_stock(symbol, stock_data):
    try:
        # Handle missing or incomplete data
        if stock_data is None or stock_data.isnull().values.any():
            print(f"⚠ Skipping {symbol}: Missing or invalid data.")
            return

        # Ensure the 'Close' column is available
        close_prices = stock_data['Close'].squeeze()  # Convert to 1D
        latest_close = close_prices.iloc[-1].item()  # Get the latest closing price

        # Skip if price is below ₹50
        if latest_close < 50:
            print(f"⏭ Skipping {symbol}: Close price ₹{latest_close:.2f} is below ₹50.")
            return

        volumes = stock_data['Volume'].squeeze()  # Convert to 1D

        # Calculate OBV
        stock_data['OBV'] = ta.volume.OnBalanceVolumeIndicator(close_prices, volumes).on_balance_volume()
        latest_OBV = stock_data['OBV'].iloc[-1].item()

        # Calculate EMAs
        stock_data['EMA_10'] = ta.trend.EMAIndicator(close_prices, window=10).ema_indicator()
        stock_data['EMA_21'] = ta.trend.EMAIndicator(close_prices, window=21).ema_indicator()
        stock_data['EMA_50'] = ta.trend.EMAIndicator(close_prices, window=50).ema_indicator()

        # Calculate Bollinger Bands
        bb = ta.volatility.BollingerBands(close_prices, window=20, window_dev=2)
        stock_data['BB_Upper'] = bb.bollinger_hband()
        stock_data['BB_Lower'] = bb.bollinger_lband()
        stock_data['BB_Width'] = bb.bollinger_hband() - bb.bollinger_lband()  # Band width for squeeze detection

        # Calculate RSI
        stock_data['RSI'] = ta.momentum.RSIIndicator(close_prices, window=14).rsi()

        # Calculate MACD
        macd = ta.trend.MACD(close_prices)
        stock_data['MACD'] = macd.macd()
        stock_data['Signal'] = macd.macd_signal()

        # Calculate ATR
        high_prices = stock_data['High'].squeeze()
        low_prices = stock_data['Low'].squeeze()
        stock_data['ATR'] = ta.volatility.AverageTrueRange(high=high_prices, low=low_prices, close=close_prices, window=14).average_true_range()
        latest_ATR = stock_data['ATR'].iloc[-1].item()

        # Get the latest row and previous row for comparison
        latest = stock_data.iloc[-1]
        prev = stock_data.iloc[-2]

        # Define conditions
        ema_crossover = (prev['EMA_10'].item() <= prev['EMA_21'].item()) and (latest['EMA_10'].item() > latest['EMA_21'].item())
        rsi_rising = (latest['RSI'].item() > prev['RSI'].item()) and (latest['RSI'].item() > 40)  # Adjusted threshold
        macd_crossover = (prev['MACD'].item() <= prev['Signal'].item()) and (latest['MACD'].item() > latest['Signal'].item())
        obv_breakout = (latest_OBV > stock_data['OBV'].iloc[-3:].mean().item()) and (latest_OBV > prev['OBV'].item())
        bollinger_squeeze = (latest['BB_Width'].item() < stock_data['BB_Width'].rolling(window=20).mean().iloc[-1].item() * 1.2)  # Adjusted threshold
        # Additional checks for uptrend confirmation
        price_above_emas = (latest_close > latest['EMA_10'].item()) and (latest_close > latest['EMA_21'].item()) and (latest_close > latest['EMA_50'].item())
        macd_positive = (latest['MACD'].item() > 0) and (latest['Signal'].item() > 0)

        # Combine conditions to detect early-stage signals (relaxed logic with scoring)
        score = 0
        if macd_crossover: score += 1
        if rsi_rising: score += 1
        if obv_breakout: score += 1
        if bollinger_squeeze: score += 1
        if price_above_emas: score += 1
        if macd_positive: score += 1

        # Store results for Excel export
        result = {
            "Symbol": symbol,
            "Close Price": round(latest_close, 2),
            "RSI": round(latest['RSI'].item(), 2),
            "MACD": round(latest['MACD'].item(), 2),
            "EMA Crossover": ema_crossover,
            "OBV Breakout": obv_breakout,
            "Bollinger Squeeze": bollinger_squeeze,
            "ATR": round(latest_ATR, 2),
            "Score": score
        }
        analysis_queue.put(result)  # Add result to thread-safe queue

        if score >= 3:  # Trigger alert if at least 3 conditions are met
            print(f"{symbol} meets early-stage conditions!")
            stop_loss = round(latest_close - (2 * latest_ATR), 2)  # 2x ATR for stop-loss
            target = round(latest_close + (2 * latest_ATR), 2)     # 2x ATR for target

            alert_message = (
                f"🔔 ALERT: {symbol}\n"
                f"  - Close Price: ₹{round(latest_close, 2)}\n"
                f"  - RSI: {round(latest['RSI'].item(), 2)}\n"
                f"  - ATR: {round(latest_ATR, 2)}\n"
                f"  - Stop-Loss: ₹{stop_loss}\n"
                f"  - Target: ₹{target}"
            )
            send_telegram_alert(alert_message)
        else:
            print(f"✅ {symbol} analyzed. No alerts triggered.")
    except Exception as e:
        print(f"❌ Error analyzing {symbol}: {e}")

# Function to send Telegram alert
def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("Telegram alert sent successfully!")
        else:
            print(f"Failed to send Telegram alert: {response.text}")
    except Exception as e:
        print(f"Error sending Telegram alert: {e}")

# Function to send Excel file via Telegram
def send_excel_file(file_path):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    with open(file_path, "rb") as file:
        files = {"document": file}
        payload = {"chat_id": TELEGRAM_CHAT_ID}
        try:
            response = requests.post(url, data=payload, files=files)
            if response.status_code == 200:
                print("Excel file sent successfully!")
            else:
                print(f"Failed to send Excel file: {response.text}")
        except Exception as e:
            print(f"Error sending Excel file: {e}")

# Main execution
if __name__ == "__main__":
    stock_list = get_nse_symbols()  # Fetch latest NSE stock symbols
    
    # Process all stocks
    print(f"🎯 Processing all {len(stock_list)} stocks...")

    try:
        analyzed_count = 0
        skipped_count = 0
        alerts_triggered = 0

        # Optimal max_workers based on CPU count
        max_workers = min(32, os.cpu_count() + 4)

        # Step 1: Fetch stock data in parallel
        stock_data_map = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(get_stock_data, symbol): symbol for symbol in stock_list}
            for future in as_completed(futures):
                symbol, stock_data = future.result() or (None, None)
                if symbol and stock_data is not None:
                    stock_data_map[symbol] = stock_data

        print(f"✅ Fetched data for {len(stock_data_map)} stocks.")

        # Step 2: Analyze stock data in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(analyze_stock, symbol, stock_data_map[symbol]): symbol for symbol in stock_data_map}
            for future in as_completed(futures):
                try:
                    future.result()
                    analyzed_count += 1
                except Exception as e:
                    print(f"❌ Error processing {futures[future]}: {e}")

        print("\n📊 Analysis Summary:")
        print(f"  - Total Stocks Analyzed: {analyzed_count}")
        print(f"  - Stocks Skipped (Price < ₹50): {skipped_count}")
        print(f"  - Alerts Triggered: {alerts_triggered}")
        print("✅ Analysis completed for all stocks.")

        # Export analysis results to Excel
        if not analysis_queue.empty():
            analysis_results = []
            while not analysis_queue.empty():
                analysis_results.append(analysis_queue.get())
            
            results_df = pd.DataFrame(analysis_results)
            excel_file_path = "stock_analysis_results.xlsx"
            results_df.to_excel(excel_file_path, index=False)
            print(f"✅ Analysis results saved to {excel_file_path}")

            # Send Excel file via Telegram
            send_excel_file(excel_file_path)
    except KeyboardInterrupt:
        print("\n🛑 Script stopped by user.")