import yfinance as yf
import pandas as pd

def fetch_data():
    nifty = yf.download('^NSEI', start='2010-01-01', end='2023-01-01')
    nifty_hourly = nifty.resample('H').ffill()  # Resample to hourly and forward fill
    return nifty_hourly.dropna()

# Generate signals based on Moving Average Crossover
def generate_signals(data):
    data['SMA_short'] = data['Close'].rolling(window=50).mean()
    data['SMA_long'] = data['Close'].rolling(window=200).mean()
    data['Signal'] = 0
    data.loc[data['SMA_short'] > data['SMA_long'], 'Signal'] = 1
    data.loc[data['SMA_short'] < data['SMA_long'], 'Signal'] = -1
    return data

# Define the strategy for backtesting
class SMACrossover(bt.Strategy):
    params = (
        ('short_window', 50),
        ('long_window', 200),
    )

    def __init__(self):
        self.data_close = self.datas[0].close
        self.order = None
        self.short_sma = bt.indicators.SimpleMovingAverage(
            self.datas[0], period=self.params.short_window)
        self.long_sma = bt.indicators.SimpleMovingAverage(
            self.datas[0], period=self.params.long_window)

    def next(self):
        if self.order:
            return

        if not self.position:
            if self.short_sma[0] > self.long_sma[0]:
                self.buy()
        else:
            if self.short_sma[0] < self.long_sma[0]:
                self.sell()

# Backtest the strategy
def backtest_strategy(data):
    cerebro = bt.Cerebro()
    cerebro.addstrategy(SMACrossover)
    
    # Reset index and rename columns to match backtrader's expectations
    data.reset_index(inplace=True)
    data.rename(columns={'Date': 'datetime'}, inplace=True)
    data.set_index('datetime', inplace=True)
    
    feed = bt.feeds.PandasData(dataname=data)
    cerebro.adddata(feed)
    cerebro.run()
    cerebro.plot()

# Main function to execute the steps
def main():
    # Step 1: Fetch Data
    nifty_data = fetch_data()
    
    # Step 2: Generate Signals
    nifty_data = generate_signals(nifty_data)
    print(nifty_data[['Close', 'SMA_short', 'SMA_long', 'Signal']].tail())

    # Step 3: Backtest Strategy
    backtest_strategy(nifty_data)

if __name__ == "__main__":
    main()