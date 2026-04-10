"""Small scratch script for manually probing yfinance data during development."""

import pandas as pd
import yfinance as yf

ticker = yf.Ticker("SNOW")
fi = ticker.fast_info
last_price = fi.get("lastPrice")
print(f"lastPrice: {last_price}")