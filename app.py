# ==============================================================================
# app.py
# KI-Aktien Screener mit RSI-Filter, Golden Cross & Live-Tickersuche
# ==============================================================================

import streamlit as st
import pandas as pd
import yfinance as yf
import ta
import urllib.parse
import urllib.request
import json
from datetime import datetime, timedelta

# ==============================================================================
# 1. APP CONFIG
# ==============================================================================

st.set_page_config(
    page_title="KI Aktien Screener",
    page_icon="📈",
    layout="wide"
)

st.title("📈 KI Aktien Screener")
st.caption("RSI-Scanner + Golden Cross + Live Yahoo Finance Suche")

# ==============================================================================
# 2. SIDEBAR
# ==============================================================================

st.sidebar.header("⚡ RSI-Filter")

rsi_min = st.sidebar.slider(
    "Minimaler RSI-Wert",
    0,
    100,
    20,
    step=1
)

rsi_max = st.sidebar.slider(
    "Maximaler RSI-Wert",
    0,
    100,
    40,
    step=1
)

# ------------------------------------------------------------------------------
# Golden Cross Filter
# ------------------------------------------------------------------------------

st.sidebar.write("---")
st.sidebar.header("📈 Chart-Signale")

golden_cross_active = st.sidebar.toggle(
    "Nur mit Golden Cross (letzte 14 Tage)",
    value=False
)

# ------------------------------------------------------------------------------
# Direkte Aktiensuche
# ------------------------------------------------------------------------------

st.sidebar.write("---")
st.sidebar.header("🔍 Direkte Aktiensuche")

# ==============================================================================
# 3. TICKER SUCHE
# ==============================================================================

@st.cache_data(ttl=300)
def get_ticker_suggestions(query):

    if not query or len(query) < 2:
        return []

    try:

        url = (
            "https://query2.finance.yahoo.com/v1/finance/search"
            f"?q={urllib.parse.quote(query)}"
            "&quotesCount=8"
            "&newsCount=0"
        )

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json"
        }

        req = urllib.request.Request(url, headers=headers)

        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))

        suggestions = []

        for quote in data.get("quotes", []):

            if quote.get("quoteType") not in ["EQUITY", "ETF"]:
                continue

            symbol = quote.get("symbol")

            name = (
                quote.get("shortname")
                or quote.get("longname")
                or "Unbekannt"
            )

            exchange = quote.get("exchange", "")

            suggestions.append({
                "label": f"{symbol} ({exchange}) - {name}",
                "ticker": symbol,
                "name": name
            })

        return suggestions

    except Exception as e:
        st.sidebar.error(f"Yahoo-Suche fehlgeschlagen: {e}")
        return []

# ------------------------------------------------------------------------------
# Suchfeld
# ------------------------------------------------------------------------------

search_query = st.sidebar.text_input(
    "Aktienname oder Ticker eingeben:",
    placeholder="z.B. Apple oder AAPL"
)

if len(search_query) >= 2:

    suggestions = get_ticker_suggestions(search_query)

    if suggestions:

        options_dict = {
            item["label"]: item
            for item in suggestions
        }

        selected_label = st.sidebar.selectbox(
            "Gefundene Treffer:",
            list(options_dict.keys()),
            index=0,
            key="search_autocomplete"
        )

        selected_stock = options_dict[selected_label]

        if st.sidebar.button(
            f"📊 {selected_stock['ticker']} analysieren",
            use_container_width=True
        ):
            st.session_state["selected_ticker"] = selected_stock["ticker"]
            st.session_state["selected_name"] = selected_stock["name"]

    else:
        st.sidebar.caption("Keine Vorschläge gefunden.")

# ==============================================================================
# 4. AKTIENLISTE
# ==============================================================================

DEFAULT_TICKERS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "META",
    "GOOGL",
    "TSLA",
    "NFLX",
    "AMD",
    "PLTR",
    "SPY",
    "QQQ"
]

# ==============================================================================
# 5. RSI + GOLDEN CROSS ANALYSE
# ==============================================================================

@st.cache_data(ttl=3600)
def analyze_stock(ticker):

    try:

        data = yf.download(
            ticker,
            period="1y",
            progress=False,
            auto_adjust=True
        )

        if data.empty:
            return None

        # RSI
        data["RSI"] = ta.momentum.RSIIndicator(
            close=data["Close"],
            window=14
        ).rsi()

        # Moving Averages
        data["SMA50"] = data["Close"].rolling(50).mean()
        data["SMA200"] = data["Close"].rolling(200).mean()

        latest = data.iloc[-1]

        # Golden Cross prüfen
        recent = data.tail(14)

        golden_cross = False

        for i in range(1, len(recent)):

            prev_50 = recent["SMA50"].iloc[i - 1]
            prev_200 = recent["SMA200"].iloc[i - 1]

            curr_50 = recent["SMA50"].iloc[i]
            curr_200 = recent["SMA200"].iloc[i]

            if prev_50 < prev_200 and curr_50 > curr_200:
                golden_cross = True
                break

        return {
            "Ticker": ticker,
            "Preis": round(float(latest["Close"]), 2),
            "RSI": round(float(latest["RSI"]), 2),
            "GoldenCross": golden_cross,
            "SMA50": round(float(latest["SMA50"]), 2),
            "SMA200": round(float(latest["SMA200"]), 2),
            "Data": data
        }

    except Exception:
        return None

# ==============================================================================
# 6. SCREENER
# ==============================================================================

st.subheader("📊 Gefilterte Aktien")

results = []

progress = st.progress(0)

for idx, ticker in enumerate(DEFAULT_TICKERS):

    stock = analyze_stock(ticker)

    if stock:

        rsi_ok = rsi_min <= stock["RSI"] <= rsi_max

        golden_ok = (
            stock["GoldenCross"]
            if golden_cross_active
            else True
        )

        if rsi_ok and golden_ok:
            results.append(stock)

    progress.progress((idx + 1) / len(DEFAULT_TICKERS))

progress.empty()

# ==============================================================================
# 7. RESULTATE
# ==============================================================================

if results:

    df = pd.DataFrame(results)

    display_df = df[
        [
            "Ticker",
            "Preis",
            "RSI",
            "GoldenCross",
            "SMA50",
            "SMA200"
        ]
    ]

    st.dataframe(
        display_df,
        use_container_width=True
    )

else:
    st.warning("Keine Aktien entsprechen den aktuellen Filtern.")

# ==============================================================================
# 8. DETAILANSICHT
# ==============================================================================

if "selected_ticker" in st.session_state:

    ticker = st.session_state["selected_ticker"]
    name = st.session_state["selected_name"]

    st.write("---")
    st.header(f"📈 Detailanalyse: {ticker}")

    stock = analyze_stock(ticker)

    if stock:

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Aktueller Preis",
            f"${stock['Preis']}"
        )

        col2.metric(
            "RSI",
            stock["RSI"]
        )

        col3.metric(
            "Golden Cross",
            "JA" if stock["GoldenCross"] else "NEIN"
        )

        chart_df = stock["Data"][[
            "Close",
            "SMA50",
            "SMA200"
        ]]

        st.line_chart(chart_df)

        st.dataframe(
            stock["Data"].tail(30),
            use_container_width=True
        )

    else:
        st.error("Fehler beim Laden der Aktiendaten.")

# ==============================================================================
# 9. FOOTER
# ==============================================================================

st.write("---")
st.caption("Entwickelt mit Streamlit • Yahoo Finance • TA-Lib")
