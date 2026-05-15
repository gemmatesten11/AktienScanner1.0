import yfinance as yf
import pandas as pd
import numpy as np

# ---------------------------
# RSI Berechnung
# ---------------------------
def compute_rsi(series, period=14):
    delta = series.diff()

    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


# ---------------------------
# Screening Funktion
# ---------------------------
def analyze_stock(ticker):
    df = yf.download(ticker, period="3mo", interval="1d", progress=False)

    if df.empty or len(df) < 20:
        return None

    df["RSI"] = compute_rsi(df["Close"])

    last_close = df["Close"].iloc[-1]

    # 5-Tage-Trend
    last_5 = df["Close"].iloc[-6:]
    trend_return = (last_5.iloc[-1] / last_5.iloc[0] - 1) * 100

    rsi = df["RSI"].iloc[-1]

    return {
        "Ticker": ticker,
        "Trend_5d_%": round(trend_return, 2),
        "RSI": round(rsi, 2),
        "Price": round(last_close, 2)
    }


# ---------------------------
# Universe (kann erweitert werden)
# ---------------------------
tickers = [
    "MSFT",
    "NVDA",
    "AMD",
    "AAPL",
    "AMZN",
    "LIN",
    "NVO",   # Novo Nordisk ADR
    "ASML"
]

results = []

for t in tickers:
    try:
        res = analyze_stock(t)
        if res:
            # Filter: 5-Tage Uptrend + RSI < 70
            if res["Trend_5d_%"] > 0 and res["RSI"] < 70:
                results.append(res)
    except Exception as e:
        print(f"Error with {t}: {e}")


# ---------------------------
# Output wie „Scanner“
# ---------------------------
df_out = pd.DataFrame(results)

if df_out.empty:
    print("Keine passenden Aktien gefunden.")
else:
    df_out = df_out.sort_values(by="Trend_5d_%", ascending=False)

    print("\n🟢 MOMENTUM + DEFENSIVE SCANNER (5D Trend + RSI < 70)\n")
    print(df_out.to_string(index=False))

    print("\n📊 Interpretation:")
    print("- 5D Trend > 0 = kurzfristiger Aufwärtstrend")
    print("- RSI < 70 = nicht überkauft")
    print("- Fokus: Quality Momentum statt High Risk Spekulation")
