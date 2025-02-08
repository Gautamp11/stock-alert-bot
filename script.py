import yfinance as yf
import pandas as pd
import ta
import time
import telebot
import schedule
from nsepython import nse_get_quote, nse_eq

# Telegram Bot Setup
TELEGRAM_BOT_TOKEN = "7896879656:AAG-3v7HhkmT20AnhC_CpBGKpiZyUmsu1Ao"
CHAT_ID = "6144704496"
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
bot.send_message(CHAT_ID, "📢 Stock Alert: Your bot is active and scanning all NSE stocks!")
print("Bot started!")

# Function to fetch all NSE stock symbols dynamically
def get_all_nse_stocks():
    try:
        stock_list = nse_eq()  # Get all NSE stock symbols
        stock_symbols = [stock + ".NS" for stock in stock_list]  # Append ".NS" for Yahoo Finance
        print(f"Scanning {len(stock_symbols)} stocks from NSE.")
        return stock_symbols
    except Exception as e:
        print(f"Error fetching NSE stocks: {e}")
        return []

# Fetch NSE stock list dynamically
stock_symbols = get_all_nse_stocks()

# Function to fetch stock data
def get_stock_data(stock_symbol):
    try:
        stock = yf.download(stock_symbol, period="3mo", interval="1d")
        return stock
    except Exception as e:
        print(f"Error fetching data for {stock_symbol}: {e}")
        return None

# Function to calculate technical indicators
def calculate_indicators(df):
    if df is None or df.empty:
        return None

    # Bollinger Bands
    bb = ta.volatility.BollingerBands(df['Close'], window=20, window_dev=2)
    df['BB_Lower'] = bb.bollinger_lband()

    # On-Balance Volume (OBV)
    df['OBV'] = ta.volume.OnBalanceVolumeIndicator(df['Close'], df['Volume']).on_balance_volume()

    # RSI
    df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()

    # MACD
    macd = ta.trend.MACD(df['Close'])
    df['MACD'] = macd.macd()
    df['Signal'] = macd.macd_signal()

    return df

# Function to check Buy conditions
def check_signals(df):
    if df is None or df.empty:
        return None

    latest = df.iloc[-1]

    buy_signal = (
        latest['Close'] <= latest['BB_Lower'] and  # Price at lower Bollinger Band
        latest['OBV'] > df.iloc[-2]['OBV'] and  # OBV rising
        latest['RSI'] < 40 and  # RSI in oversold zone
        latest['MACD'] > latest['Signal']  # MACD crossover
    )

    if buy_signal:
        return "BUY Signal: Stock is at a strong support zone! 📈"
    
    return None

# Function to send alerts
def send_alert(stock, message):
    bot.send_message(CHAT_ID, f"{stock}: {message}")

# Main function to check all NSE stocks
def run_bot():
    for stock in stock_symbols:
        df = get_stock_data(stock)
        df = calculate_indicators(df)
        
        signal = check_signals(df)
        if signal:
            send_alert(stock, signal)

# Schedule the bot to run every 15 minutes
schedule.every(15).minutes.do(run_bot)

# Continuous loop to keep running
while True:
    schedule.run_pending()
    time.sleep(60)
