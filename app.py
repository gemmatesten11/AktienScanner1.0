import streamlit as st
import yfinance as yf
import pandas as pd
import urllib.request
import urllib.parse
from io import StringIO
import plotly.graph_objects as gr
from plotly.subplots import make_subplots
import random
import json

# Streamlit Page Config
st.set_page_config(layout="wide", page_title="Schneller RSI-Scanner", page_icon="⚡")

# ==============================================================================
# 1. CACHING-LAYER
# ==============================================================================
@st.cache_data(ttl=300)
def load_cached_history(ticker, period, interval):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=86400)
def load_cached_isin(ticker):
    try:
        stock = yf.Ticker(ticker)
        isin = stock.get_isin()
        if not isin or isin == '-':
            return "Nicht verfügbar"
        return isin
    except Exception:
        return "Nicht verfügbar"

# ==============================================================================
# 2. TECHNISCHE INDIKATOREN (RSI, MACD & BOLLINGER BÄNDER)
# ==============================================================================
def calculate_rsi(series, period=14):
    if len(series) < period:
        return pd.Series(index=series.index, dtype='float64')
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = avg_loss.replace(0, 0.00001)
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=signal, adjust=False).mean()
    macd_hist = macd - macd_signal
    macd_pct = (macd / ema_slow.replace(0, 0.00001)) * 100
    return macd, macd_signal, macd_hist, macd_pct

def calculate_bollinger_bands(series, period=20, num_std=2):
    sma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper_band = sma + (num_std * std)
    lower_band = sma - (num_std * std)
    return upper_band, sma, lower_band

# ==============================================================================
# 3. SCRAPER ENGINE (MIT AUTO-FALLBACK)
# ==============================================================================
def fetch_market_data(markt):
    headers = {'User-Agent': 'RSI-Scanner-Bot/1.0 (contact@example.com) Mozilla/5.0'}
    
    def extract_from_df(df, market_type):
        cols_lower = [str(c).lower() for c in df.columns]
        t_idx = -1
        for idx, c in enumerate(cols_lower):
            if any(k in c for k in ['symbol', 'kürzel', 'ticker', 'epic']):
                t_idx = idx
                break
        n_idx = -1
        for idx, c in enumerate(cols_lower):
            if any(k in c for k in ['security', 'unternehmen', 'company', 'name', 'firma']) and idx != t_idx:
                n_idx = idx
                break
        if t_idx == -1: return []
        if n_idx == -1: n_idx = 0
        
        t_col = df.columns[t_idx]
        n_col = df.columns[n_idx]
        
        extracted = []
        for _, row in df.iterrows():
            ticker = str(row[t_col]).split('[')[0].strip().upper()
            name = str(row[n_col]).split('[')[0].strip()
            if not ticker or ticker == 'NAN': continue
            
            if "S&P" in market_type:
                ticker = ticker.replace('.', '-')
            elif any(m in market_type for m in ["DAX", "MDAX", "SDAX"]):
                if not ticker.endswith('.DE'): ticker += '.DE'
            elif "FTSE" in market_type:
                ticker = ticker.replace('.', '-') + ".L"
            elif "CAC" in market_type:
                if not ticker.endswith('.PA'): ticker += '.PA'
            elif "NIKKEI" in market_type:
                if not ticker.endswith('.T'): ticker += '.T'
            elif "EURO STOXX" in market_type:
                if '.' not in ticker:
                    suffix = ".DE"
                    c_listing = [c for c in df.columns if 'listing' in str(c).lower() or 'exchange' in str(c).lower()]
                    if c_listing:
                        listing = str(row[c_listing[0]]).lower()
                        if 'paris' in listing: suffix = ".PA"
                        elif 'amsterdam' in listing: suffix = ".AS"
                        elif 'milan' in listing or 'milano' in listing: suffix = ".MI"
                        elif 'madrid' in listing: suffix = ".MC"
                        elif 'brussels' in listing: suffix = ".BR"
                    ticker += suffix
            extracted.append({"ticker": ticker, "name": name})
        return extracted

    try:
        if "S&P 500" in markt:
            req = urllib.request.Request("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", headers=headers)
            with urllib.request.urlopen(req) as r: df = pd.read_html(StringIO(r.read().decode('utf-8')))[0]
            return extract_from_df(df, "S&P")
        elif "S&P 400" in markt:
            req = urllib.request.Request("https://en.wikipedia.org/wiki/List_of_S%26P_400_companies", headers=headers)
            with urllib.request.urlopen(req) as r: df = pd.read_html(StringIO(r.read().decode('utf-8')))[0]
            return extract_from_df(df, "S&P")
        elif "S&P 600" in markt:
            req = urllib.request.Request("https://en.wikipedia.org/wiki/List_of_S%26P_600_companies", headers=headers)
            with urllib.request.urlopen(req) as r: df = pd.read_html(StringIO(r.read().decode('utf-8')))[1]
            return extract_from_df(df, "S&P")
        elif "DAX 40" in markt:
            req = urllib.request.Request("https://de.wikipedia.org/wiki/DAX", headers=headers)
            with urllib.request.urlopen(req) as r: tables = pd.read_html(StringIO(r.read().decode('utf-8')))
            for df in tables:
                res = extract_from_df(df, "DAX")
                if len(res) >= 30: return res
        elif "MDAX" in markt:
            req = urllib.request.Request("https://de.wikipedia.org/wiki/MDAX", headers=headers)
            with urllib.request.urlopen(req) as r: tables = pd.read_html(StringIO(r.read().decode('utf-8')))
            for df in tables:
                res = extract_from_df(df, "MDAX")
                if len(res) >= 30: return res
        elif "SDAX" in markt:
            req = urllib.request.Request("https://de.wikipedia.org/wiki/SDAX", headers=headers)
            with urllib.request.urlopen(req) as r: tables = pd.read_html(StringIO(r.read().decode('utf-8')))
            for df in tables:
                res = extract_from_df(df, "SDAX")
                if len(res) >= 30: return res
        elif "EURO STOXX" in markt:
            req = urllib.request.Request("https://en.wikipedia.org/wiki/Euro_Stoxx_50", headers=headers)
            with urllib.request.urlopen(req) as r: tables = pd.read_html(StringIO(r.read().decode('utf-8')))
            for df in tables:
                res = extract_from_df(df, "EURO STOXX")
                if len(res) >= 30: return res
        elif "FTSE 100" in markt:
            req = urllib.request.Request("https://en.wikipedia.org/wiki/FTSE_100_Index", headers=headers)
            with urllib.request.urlopen(req) as r: tables = pd.read_html(StringIO(r.read().decode('utf-8')))
            for df in tables:
                res = extract_from_df(df, "FTSE 100")
                if len(res) >= 50: return res
        elif "CAC 40" in markt:
            req = urllib.request.Request("https://en.wikipedia.org/wiki/CAC_40", headers=headers)
            with urllib.request.urlopen(req) as r: tables = pd.read_html(StringIO(r.read().decode('utf-8')))
            for df in tables:
                res = extract_from_df(df, "CAC 40")
                if len(res) >= 30: return res
        elif "Nikkei 225" in markt:
            req = urllib.request.Request("https://en.wikipedia.org/wiki/Nikkei_225", headers=headers)
            with urllib.request.urlopen(req) as r: tables = pd.read_html(StringIO(r.read().decode('utf-8')))
            for df in tables:
                res = extract_from_df(df, "NIKKEI")
                if len(res) >= 50: return res
    except Exception:
        st.sidebar.warning("Live-Scraping blockiert, nutze integriertes Backup.")
    
    if "USA" in markt:
        return [{"ticker": "AAPL", "name": "Apple"}, {"ticker": "MSFT", "name": "Microsoft"}, {"ticker": "NVDA", "name": "NVIDIA"}, {"ticker": "AMZN", "name": "Amazon"}, {"ticker": "GOOGL", "name": "Alphabet"}, {"ticker": "META", "name": "Meta"}, {"ticker": "TSLA", "name": "Tesla"}]
    else:
        return [{"ticker": "SAP.DE", "name": "SAP"}, {"ticker": "SIE.DE", "name": "Siemens"}, {"ticker": "ALV.DE", "name": "Allianz"}, {"ticker": "DTE.DE", "name": "Deutsche Telekom"}, {"ticker": "BMW.DE", "name": "BMW"}, {"ticker": "BAS.DE", "name": "BASF"}, {"ticker": "BAYN.DE", "name": "Bayer"}]

# ==============================================================================
# 4. CHART RENDERING ENGINE
# ==============================================================================
def render_chart(df_chart, title_suffix):
    if df_chart.empty or len(df_chart) < 2:
        st.warning(f"Keine ausreichenden Intraday-Daten für {title_suffix} im Cache.")
        return
    
    df_chart['RSI'] = calculate_rsi(df_chart['Close'], period=14)
    df_chart['MACD'], df_chart['MACD_Signal'], df_chart['MACD_Hist'], _ = calculate_macd(df_chart['Close'])
    df_chart['BB_Upper'], df_chart['BB_Middle'], df_chart['BB_Lower'] = calculate_bollinger_bands(df_chart['Close'])
    
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06, row_heights=[0.45, 0.25, 0.30])
    
    fig.add_trace(gr.Scatter(x=df_chart.index, y=df_chart['Close'], mode='lines', name='Kurs', line=dict(color='#1f77b4', width=2.5)), row=1, col=1)
    if 'SMA50' in df_chart.columns:
        fig.add_trace(gr.Scatter(x=df_chart.index, y=df_chart['SMA50'], mode='lines', name='SMA 50', line=dict(color='orange', width=1.5)), row=1, col=1)
        fig.add
