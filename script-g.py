import yfinance as yf
 import pandas as pd
 import ta
 import time
 import requests
 import io
 from concurrent.futures import ThreadPoolExecutor, as_completed
 from datetime import datetime
 
 # Telegram Bot Configuration
 TELEGRAM_BOT_TOKEN = "7896879656:AAG-3v7HhkmT20AnhC_CpBGKpiZyUmsu1Ao"
 TELEGRAM_CHAT_ID = "6144704496"
 
 # NSE CSV URL
 NSE_CSV_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
 
 # Threshold for "near the lower band" (e.g., within 2%)
 threshold = 0.02  # 2%
 
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
         return stock
     except Exception as e:
         print(f"❌ Error fetching {symbol_with_suffix}: {e}")
         return None
 
 # Function to analyze stock data
 def analyze_stock(symbol):
     # Fetch data for the symbol
     df = get_stock_data(symbol)
     if df is None:
         return
 
     try:
         # Debugging: Log the first few rows of the DataFrame
         print(f"✅ Data fetched for {symbol}:")
         print(df.head())
 
         # Ensure the 'Close' column is available
         close_prices = df['Close'].squeeze()  # Convert to 1D
         latest_close = close_prices.iloc[-1].item()  # Get the latest closing price
 
         # Skip if price is below ₹100
         if latest_close < 100:
             print(f"⏭ Skipping {symbol}: Close price ₹{latest_close:.2f} is below ₹100.")
             return
 
         volumes = df['Volume'].squeeze()  # Convert to 1D
 
         # Calculate OBV
         df['OBV'] = ta.volume.OnBalanceVolumeIndicator(close_prices, volumes).on_balance_volume()
         latest_OBV = df['OBV'].iloc[-1].item()
 
         # Calculate EMAs
         df['EMA_10'] = ta.trend.EMAIndicator(close_prices, window=10).ema_indicator()
         df['EMA_21'] = ta.trend.EMAIndicator(close_prices, window=21).ema_indicator()
         df['EMA_50'] = ta.trend.EMAIndicator(close_prices, window=50).ema_indicator()
 
         # Calculate Bollinger Bands
         bb = ta.volatility.BollingerBands(close_prices, window=20, window_dev=2)
         df['BB_Upper'] = bb.bollinger_hband()
         df['BB_Lower'] = bb.bollinger_lband()
         df['BB_Width'] = bb.bollinger_hband() - bb.bollinger_lband()  # Band width for squeeze detection
 
         # Calculate RSI
         df['RSI'] = ta.momentum.RSIIndicator(close_prices, window=14).rsi()
 
         # Calculate MACD
         macd = ta.trend.MACD(close_prices)
         df['MACD'] = macd.macd()
         df['Signal'] = macd.macd_signal()
 
         # Calculate ATR
         high_prices = df['High'].squeeze()
         low_prices = df['Low'].squeeze()
         df['ATR'] = ta.volatility.AverageTrueRange(high=high_prices, low=low_prices, close=close_prices, window=14).average_true_range()
         latest_ATR = df['ATR'].iloc[-1].item()
 
         # Get the latest row and previous row for comparison
         latest = df.iloc[-1]
         prev = df.iloc[-2]
 
         # Define conditions
         ema_crossover = (prev['EMA_10'].item() <= prev['EMA_21'].item()) and (latest['EMA_10'].item() > latest['EMA_21'].item())
         rsi_rising = (latest['RSI'].item() > prev['RSI'].item()) and (latest['RSI'].item() > 50)
         macd_crossover = (prev['MACD'].item() <= prev['Signal'].item()) and (latest['MACD'].item() > latest['Signal'].item())
         obv_breakout = (latest_OBV > df['OBV'].iloc[-3:].mean().item()) and (latest_OBV > prev['OBV'].item())
         bollinger_squeeze = (latest['BB_Width'].item() < df['BB_Width'].rolling(window=20).mean().iloc[-1].item())  # Band width is narrowing
 
         # Print indicator values for debugging
         print(f"\n📊 Indicator Values for {symbol} (Close: ₹{latest_close:.2f}):")
         print(f"  - RSI: {latest['RSI'].item():.2f}")
         print(f"  - MACD: {latest['MACD'].item():.2f}")
         print(f"  - EMA Crossover: {ema_crossover}")
         print(f"  - OBV Breakout: {obv_breakout}")
         print(f"  - Bollinger Squeeze: {bollinger_squeeze}")
         print(f"  - ATR: {latest_ATR:.2f}")
 
         # Combine conditions to detect early-stage signals
         if ema_crossover and macd_crossover and rsi_rising and obv_breakout and bollinger_squeeze:
             print(f"{symbol} meets all early-stage conditions!")
             stop_loss = round(latest_close - (2 * latest_ATR), 2)  # 2x ATR for stop-loss
             target = round(latest_close + (2 * latest_ATR), 2)     # 2x ATR for target
 
             alert_message = (
                 f"🔔 ALERT: {symbol}\n"
                 f"  - Close Price: ₹{round(latest_close, 2)}\n"
                 f"  - RSI: {round(latest['RSI'].item(), 2)}\n"
                 f"  - EMA_10: {round(latest['EMA_10'].item(), 2)}\n"
                 f"  - EMA_21: {round(latest['EMA_21'].item(), 2)}\n"
                 f"  - EMA_50: {round(latest['EMA_50'].item(), 2)}\n"
                 f"  - MACD: {round(latest['MACD'].item(), 2)}\n"
                 f"  - OBV: {round(latest['OBV'].item(), 2)}\n"
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
 
 # Main execution
 if __name__ == "__main__":
     stock_list = get_nse_symbols()  # Fetch latest NSE stock symbols
 
     # Process all stocks (removed slicing)
     print(f"🎯 Processing all {len(stock_list)} stocks...")
 
     try:
         analyzed_count = 0
         skipped_count = 0
         alerts_triggered = 0
 
         # Increase max_workers to improve performance (adjust based on your system's capabilities)
         with ThreadPoolExecutor(max_workers=5) as executor:
         with ThreadPoolExecutor(max_workers=1) as executor:
             futures = {executor.submit(analyze_stock, symbol): symbol for symbol in stock_list}
             for future in as_completed(futures):
                 try:
                     future.result()
                     analyzed_count += 1
                 except Exception as e:
                     print(f"❌ Error processing {futures[future]}: {e}")
 
         print("\n📊 Analysis Summary:")
         print(f"  - Total Stocks Analyzed: {analyzed_count}")
         print(f"  - Stocks Skipped (Price < ₹100): {skipped_count}")
         print(f"  - Alerts Triggered: {alerts_triggered}")
         print("✅ Analysis completed for all stocks.")
     except KeyboardInterrupt:
        print("\n⏹ Analysis interrupted by user.")