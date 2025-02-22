import yfinance as yf
import pandas as pd
import ta
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import time
import warnings

# Suppress sklearn warnings
warnings.filterwarnings("ignore", category=UserWarning)

# Nifty Symbol
NIFTY_SYMBOL = "^NSEI"

# Function to fetch Nifty data with retries
def get_nifty_data():
    for attempt in range(3):
        try:
            print(f"🔄 Fetching Nifty data... (Attempt {attempt + 1})")
            nifty_data = yf.download(NIFTY_SYMBOL, period="59d", interval="5m")
            
            if nifty_data.empty:
                print("⚠ No data found for Nifty. Retrying...")
                time.sleep(2)
                continue
            
            nifty_data.reset_index(inplace=True)
            if isinstance(nifty_data.columns, pd.MultiIndex):
                nifty_data.columns = nifty_data.columns.get_level_values(0)
            
            print(f"✅ Data fetched successfully! Shape: {nifty_data.shape}")
            return nifty_data
        except Exception as e:
            print(f"❌ Error fetching Nifty data: {e}")
    print("🚫 Failed to fetch data after multiple attempts.")
    return None

# Function to calculate indicators
def calculate_indicators(df):
    try:
        print("📊 Calculating indicators...")
        
        df.dropna(inplace=True)
        df['EMA_10'] = ta.trend.EMAIndicator(df['Close'].squeeze(), window=10).ema_indicator()
        df['EMA_21'] = ta.trend.EMAIndicator(df['Close'].squeeze(), window=21).ema_indicator()
        df['EMA_50'] = ta.trend.EMAIndicator(df['Close'].squeeze(), window=50).ema_indicator()
        df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
        df['RSI'] = ta.momentum.RSIIndicator(df['Close'].squeeze(), window=14).rsi()
        
        macd = ta.trend.MACD(df['Close'].squeeze())
        df['MACD'] = macd.macd()
        df['Signal'] = macd.macd_signal()
        df['MACD_Hist'] = macd.macd_diff()
        
        df['ATR'] = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], window=14).average_true_range()
        df['ADX'] = ta.trend.ADXIndicator(df['High'], df['Low'], df['Close'], window=14).adx()
        df['Volume_MA'] = df['Volume'].rolling(window=50).mean()
        
        # Derived Features
        df['Price_Change'] = df['Close'].pct_change() * 100
        df['Volatility'] = df['Close'].rolling(window=14).std()
        df['Trend'] = (df['Close'] > df['EMA_200']).astype(int)  # 1 for uptrend, 0 for downtrend
        
        print("✅ Indicators calculated successfully!")
        return df
    except Exception as e:
        print(f"❌ Error in calculating indicators: {e}")
        return None

# Labeling Function
def label_data(df):
    df['Target'] = 0
    df['Target'] = ((df['Close'].shift(-1) > df['Close']) & (df['Close'].shift(-2) > df['Close'].shift(-1))).astype(int)
    df.dropna(inplace=True)  # Drop rows with NaN values caused by shifting
    return df

# Function to train the model
def train_model(df):
    # Features and Target
    features = ['EMA_10', 'EMA_21', 'EMA_50', 'EMA_200', 'RSI', 'MACD', 'Signal', 'MACD_Hist', 'ATR', 'ADX', 'Volume_MA', 'Price_Change', 'Volatility', 'Trend']
    X = df[features]
    y = df['Target']
    
    # Train-Test Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, shuffle=False)
    
    # Train Random Forest Classifier
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    # Evaluate Model
    y_pred = model.predict(X_test)
    print("\n🎯 Model Evaluation:")
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.2f}")
    print(classification_report(y_test, y_pred))
    
    return model, features  # Return both the model and feature names

# Function to backtest the strategy with ML signals
def backtest_strategy_with_ml(df, model, features):
    trades = []
    in_position = False
    entry_price = stop_loss_call = take_profit_call = stop_loss_put = take_profit_put = 0
    
    for i in range(len(df)):
        row = df.iloc[i]
        # Use a DataFrame with feature names for prediction
        X = pd.DataFrame([row[features]], columns=features)
        ml_signal = model.predict(X)[0]  # Predict buy/sell signal
        
        if ml_signal == 1 and not in_position:
            in_position = True
            entry_price = row['Close']
            stop_loss_call = entry_price - 1.5 * row['ATR']  # Dynamic stop-loss
            take_profit_call = entry_price + 3 * row['ATR']  # Dynamic take-profit
            stop_loss_put = entry_price + 1.5 * row['ATR']
            take_profit_put = entry_price - 3 * row['ATR']
            
            print(f"🚀 Entering trade at {row['Datetime']} (Entry Price: {entry_price:.2f}, Stop Loss Call: {stop_loss_call:.2f}, Take Profit Call: {take_profit_call:.2f}, Stop Loss Put: {stop_loss_put:.2f}, Take Profit Put: {take_profit_put:.2f})")
            
            trades.append({
                'Entry Time': row['Datetime'], 'Entry Price': entry_price,
                'Stop Loss Call': stop_loss_call, 'Take Profit Call': take_profit_call,
                'Stop Loss Put': stop_loss_put, 'Take Profit Put': take_profit_put,
                'Exit Time': None, 'Exit Price': None, 'Profit Call': None, 'Profit Put': None
            })
        
        if in_position:
            if row['Low'] <= stop_loss_call or row['High'] >= take_profit_call or row['Low'] <= take_profit_put or row['High'] >= stop_loss_put:
                in_position = False
                exit_price_call = stop_loss_call if row['Low'] <= stop_loss_call else take_profit_call
                exit_price_put = stop_loss_put if row['High'] >= stop_loss_put else take_profit_put
                
                print(f"⏹️ Exiting trade at {row['Datetime']} (Exit Price: {(exit_price_call + exit_price_put) / 2:.2f}, Profit Call: {(exit_price_call - entry_price) / entry_price * 100:.2f}%, Profit Put: {(entry_price - exit_price_put) / entry_price * 100:.2f}%)")
                
                trades[-1]['Exit Time'] = row['Datetime']
                trades[-1]['Exit Price'] = (exit_price_call + exit_price_put) / 2
                trades[-1]['Profit Call'] = (exit_price_call - entry_price) / entry_price * 100
                trades[-1]['Profit Put'] = (entry_price - exit_price_put) / entry_price * 100
    
    return trades

# Function to generate a report
def generate_report(trades):
    if not trades:
        print("⚠ No trades executed during the backtest period.")
        return
    
    trades_df = pd.DataFrame(trades)
    total_trades = len(trades_df)
    win_rate = len(trades_df[trades_df['Profit Call'] > 0]) / total_trades * 100 if total_trades > 0 else 0
    avg_profit_call = trades_df['Profit Call'].mean()
    avg_profit_put = trades_df['Profit Put'].mean()
    total_profit = trades_df[['Profit Call', 'Profit Put']].sum().sum()
    
    print("\n📊 Dual-Side Backtest Report:")
    print(f"Total Trades: {total_trades}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Average Profit (Call): {avg_profit_call:.2f}%")
    print(f"Average Profit (Put): {avg_profit_put:.2f}%")
    print(f"Total Profit: {total_profit:.2f}%")
    
    if not trades_df.empty:
        trades_df['Cumulative Profit'] = trades_df[['Profit Call', 'Profit Put']].sum(axis=1).cumsum()
        
        # Plot Equity Curve
        plt.figure(figsize=(12, 6))
        plt.plot(trades_df['Exit Time'], trades_df['Cumulative Profit'], label='Cumulative Profit', color='blue')
        plt.title('Equity Curve')
        plt.xlabel('Time')
        plt.ylabel('Cumulative Profit (%)')
        plt.legend()
        plt.grid()
        plt.show()
        
        # Plot Profit Distribution
        plt.figure(figsize=(10, 6))
        plt.hist(trades_df['Profit Call'], bins=20, alpha=0.7, label='Call Profits', color='green')
        plt.hist(trades_df['Profit Put'], bins=20, alpha=0.7, label='Put Profits', color='red')
        plt.title('Profit Distribution')
        plt.xlabel('Profit (%)')
        plt.ylabel('Frequency')
        plt.legend()
        plt.grid()
        plt.show()

# Main execution
if __name__ == "__main__":
    df = get_nifty_data()
    if df is not None:
        df = calculate_indicators(df)
        if df is not None:
            df = label_data(df)  # Add labels for supervised learning
            model, features = train_model(df)  # Train the ML model and get feature names
            trades = backtest_strategy_with_ml(df, model, features)  # Backtest with ML signals
            generate_report(trades)  # Generate the backtest report