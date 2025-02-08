import yfinance as yf
import pandas as pd
import ta
import time
import telebot
import schedule

# Telegram Bot Setup
TELEGRAM_BOT_TOKEN = "7896879656:AAG-3v7HhkmT20AnhC_CpBGKpiZyUmsu1Ao"
CHAT_ID = "6144704496"
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# Stock list (Add more stocks here)
stock_symbols = ["FEDERALBNK.NS", "TCS.NS", "HDFCBANK.NS"]  

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

# Main function to check all stocks
def run_bot():
    for stock in stock_symbols:
        df = get_stock_data(stock)
        df = calculate_indicators(df)
        
        signal = check_signals(df)
        if signal:
            send_alert(stock, signal)

# Schedule the bot to run every 10 minutes
schedule.every(10).minutes.do(run_bot)

# Continuous loop to keep running
while True:
    schedule.run_pending()
    time.sleep(60)
