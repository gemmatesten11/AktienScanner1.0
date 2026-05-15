import streamlit as st
import yfinance as yf
import pandas as pd
import urllib.request
from io import StringIO
import plotly.graph_objects as gr
from plotly.subplots import make_subplots
import random

# Streamlit Page Config
st.set_page_config(layout="wide", page_title="Schneller RSI-Scanner", page_icon="⚡")

# ==============================================================================
# 1. KORRIGIERTE RSI FUNKTION (WILDER'S SMOOTHING)
# ==============================================================================
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def get_wikipedia_table(url, match_index=0):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        html_text = response.read().decode('utf-8')
    return pd.read_html(StringIO(html_text))[match_index]

if "scan_results" not in st.session_state:
    st.session_state.scan_results = []
if "has_scanned" not in st.session_state:
    st.session_state.has_scanned = False

# ==============================================================================
# 2. SEITENLEISTE
# ==============================================================================
st.sidebar.header("⚡ RSI-Filter")
rsi_min = st.sidebar.slider("Minimaler RSI-Wert", 0, 100, 20, step=1)
rsi_max = st.sidebar.slider("Maximaler RSI-Wert", 0, 100, 40, step=1)

st.sidebar.write("---")
st.sidebar.header("📈 Chart-Signale")
golden_cross_active = st.sidebar.toggle("Nur mit Golden Cross (letzte 14 Tage)", value=False)

# ==============================================================================
# 3. POP-UP (DETAILS, LIVE-KURS & MULTI-TIMEFRAME CHARTS)
# ==============================================================================
@st.dialog("📊 Aktien-Details & Signal", width="large")
def show_details_popup(ticker):
    with st.spinner("Lade Live-Kurse und Zeitfenster..."):
        try:
            stock = yf.Ticker(ticker)
            
            try:
                company_name = stock.info.get('longName', ticker)
                current_price = stock.info.get('regularMarketPrice', None)
                currency = stock.info.get('currency', '$')
            except Exception:
                company_name = ticker
                current_price = None
                currency = ""
            
            try:
                isin = stock.get_isin()
                if not isin or isin == '-':
                    isin = "Nicht verfügbar"
            except Exception:
                isin = "Nicht verfügbar"
                
            st.write(f"## {company_name} (`{ticker}`)")
            
            meta_col1, meta_col2 = st.columns(2)
            with meta_col1:
                if current_price:
                    st.metric("Aktueller Live-Kurs", f"{current_price:,.2f} {currency}")
                else:
                    st.caption("Live-Kurs temporär nicht verfügbar")
            with meta_col2:
                st.write(f"**Identifikation:** ISIN/WKN: `{isin}`")
                tv_ticker = ticker.split('.')[0]
                tradingview_url = f"https://de.tradingview.com/symbols/{tv_ticker}/"
                st.markdown(f"[➡️ **Auf TradingView.de analysieren**]({tradingview_url})")
            
            st.write("---")
            
            df_base = stock.history(period="1y", interval="1d")
            df_base['RSI'] = calculate_rsi(df_base['Close'], period=14)
            df_base['SMA50'] = df_base['Close'].rolling(window=50).mean()
            df_base['SMA200'] = df_base['Close'].rolling(window=200).mean()
            df_base['Above'] = df_base['SMA50'] > df_base['SMA200']
            df_base['Crossover'] = df_base['Above'] & (~df_base['Above'].shift(1).fillna(True))
            recent_golden_cross = df_base['Crossover'].tail(14).any()
            rsi_aktuell = df_base['RSI'].iloc[-1]
            
            if rsi_aktuell > 70:
                ampel_signal = "🔴 VERKAUFEN (Sell)"
                grund = "Der RSI (Tagesbasis) ist überkauft (> 70). Das Korrekturrisiko ist kurzfristig erhöht."
            elif rsi_aktuell < 30 or recent_golden_cross:
                ampel_signal = "🟢 KAUFEN (Buy)"
                if rsi_aktuell < 30 and recent_golden_cross:
                    grund = "St
