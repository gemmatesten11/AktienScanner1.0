# ==============================================================================
# app.py
# KI Aktien Screener ohne TA-Library
# RSI + Golden Cross + Yahoo Live Suche
# ==============================================================================

import streamlit as st
import pandas as pd
import yfinance as yf
import urllib.parse
import urllib.request
import json

# ==============================================================================
# PAGE CONFIG
# ==============================================================================

st.set_page_config(
    page_title="KI Aktien Screener",
    page_icon="📈",
    layout="wide"
)

st.title("📈 KI Aktien Screener")
st.caption("RSI Scanner + Golden Cross + Live Yahoo Suche")

# ==============================================================================
# SIDEBAR
# ==============================================================================

st.sidebar.header("⚡ RSI Filter")

rsi_min = st.sidebar.slider(
    "Minimaler RSI",
    0,
    100,
    20
)

rsi_max = st.sidebar.slider(
    "Maximaler RSI",
    0,
    100,
    40
)

# ------------------------------------------------------------------------------
# Golden Cross
# ------------------------------------------------------------------------------

st.sidebar.write("---")

golden_cross_active = st.sidebar.checkbox(
    "Nur Golden Cross Aktien",
    value=False
)

# ------------------------------------------------------------------------------
# Live Suche
# ------------------------------------------------------------------------------

st.sidebar.write("---")
st.sidebar.header("🔍 Direkte Aktiensuche")

# ==============================================================================
# YAHOO SEARCH
# ==============================================================================

@st.cache_data(ttl=300)
def get_ticker_suggestions(query):

    if len(query) < 2:
        return []

    try:

        url = (
            "https://query2.finance.yahoo.com/v1/finance/search"
            f"?q={urllib.parse.quote(query)}"
            "&quotesCount=8"
            "&newsCount=0"
        )

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        req = urllib.request.Request(
            url,
            headers=headers
        )

        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(
                response.read().decode("utf-8")
            )

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

    except Exception:
        return []

# ==============================================================================
# SUCHFELD
# ==============================================================================

search_query = st.sidebar.text_input(
    "Ticker oder Name:",
    placeholder="z.B. Apple oder AAPL"
)

if len(search_query) >= 2:

    suggestions = get_ticker_suggestions(search_query)

    if suggestions:

        options = {
            item["label"]: item
            for item in suggestions
        }

        selected_label = st.sidebar.selectbox(
            "Treffer:",
            list(options.keys())
        )

        selected_stock = options[selected_label]

        if st.sidebar.button(
            f"📊 {selected_stock['ticker']} analysieren",
            use_container_width=True
        ):

            st.session_state["selected_ticker"] = (
                selected_stock["ticker"]
            )

            st.session_state["selected_name"] = (
                selected_stock["name"]
            )

    else:
        st.sidebar.warning("Keine Treffer gefunden")

# ==============================================================================
# STANDARD AKTIEN
# ==============================================================================

TICKERS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "META",
    "GOOGL",
    "TSLA",
    "AMD",
    "NFLX",
    "PLTR",
    "SPY",
    "QQQ"
]

# ==============================================================================
# RSI BERECHNUNG
# ==============================================================================

def calculate_rsi(data, window=14):

    delta = data.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(window=window).mean()
    avg_loss = loss.rolling(window=window).mean()

    rs = avg_gain / avg_loss

    rsi = 100 - (100 / (1 + rs))

    return rsi

# ==============================================================================
# ANALYSE
# ==============================================================================

@st.cache_data(ttl=3600)
def analyze_stock(ticker):

    try:

        data = yf.download(
            ticker,
            period="1y",
            auto_adjust=True,
            progress=False
        )

        if data.empty:
            return None

        # RSI
        data["RSI"] = calculate_rsi(data["Close"])

        # SMA
        data["SMA50"] = (
            data["Close"]
            .rolling(50)
            .mean()
        )

        data["SMA200"] = (
            data["Close"]
            .rolling(200)
            .mean()
        )

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
# SCREENER
# ==============================================================================

st.subheader("📊 Gefilterte Aktien")

results = []

progress = st.progress(0)

for index, ticker in enumerate(TICKERS):

    stock = analyze_stock(ticker)

    if stock:

        rsi_ok = (
            rsi_min <= stock["RSI"] <= rsi_max
        )

        golden_ok = (
            stock["GoldenCross"]
            if golden_cross_active
            else True
        )

        if rsi_ok and golden_ok:
            results.append(stock)

    progress.progress(
        (index + 1) / len(TICKERS)
    )

progress.empty()

# ==============================================================================
# RESULTATE
# ==============================================================================

if results:

    df = pd.DataFrame(results)

    st.dataframe(
        df[
            [
                "Ticker",
                "Preis",
                "RSI",
                "GoldenCross",
                "SMA50",
                "SMA200"
            ]
        ],
        use_container_width=True
    )

else:
    st.warning(
        "Keine Aktien entsprechen dem Filter."
    )

# ==============================================================================
# DETAILANSICHT
# ==============================================================================

if "selected_ticker" in st.session_state:

    ticker = st.session_state["selected_ticker"]
    name = st.session_state["selected_name"]

    st.write("---")

    st.header(f"📈 {ticker} — {name}")

    stock = analyze_stock(ticker)

    if stock:

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Preis",
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

        # Chart
        chart_data = stock["Data"][
            [
                "Close",
                "SMA50",
                "SMA200"
            ]
        ]

        st.line_chart(chart_data)

        # Rohdaten
        with st.expander("📋 Letzte 30 Tage"):

            st.dataframe(
                stock["Data"].tail(30),
                use_container_width=True
            )

    else:
        st.error("Aktie konnte nicht geladen werden.")

# ==============================================================================
# FOOTER
# ==============================================================================

st.write("---")

st.caption(
    "Entwickelt mit Streamlit + Yahoo Finance"
)
