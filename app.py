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

# ==============================================================================
# UI CONFIG & THEME CUSTOMIZATION
# ==============================================================================
st.set_page_config(layout="wide", page_title="High-Speed RSI Scanner", page_icon="⚡")

# Custom CSS für modernes Fintech-UI-Design
st.markdown("""
    <style>
        /* Hauptüberschrift Styling */
        .main-title {
            font-size: 2.2rem;
            font-weight: 800;
            letter-spacing: -0.05rem;
            margin-bottom: 0.5rem;
        }
        /* Subtitle */
        .sub-title {
            color: #64748b;
            font-size: 1rem;
            margin-bottom: 2rem;
        }
        /* Custom Card Styling für die Ergebnisse */
        .stock-card {
            border-radius: 12px;
            padding: 1.2rem;
            background-color: var(--background-color);
            border: 1px solid rgba(128, 128, 128, 0.2);
            transition: transform 0.2s, border-color 0.2s;
        }
        /* RSI Badges */
        .rsi-badge {
            padding: 2px 8px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 0.85rem;
            float: right;
        }
        .rsi-low { background-color: rgba(34, 197, 94, 0.2); color: #22c55e; }
        .rsi-mid { background-color: rgba(148, 163, 184, 0.2); color: #94a3b8; }
        .rsi-high { background-color: rgba(239, 68, 68, 0.2); color: #ef4444; }
    </style>
""", unsafe_allow_html=True)

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
        return isin if isin and isin != '-' else "Nicht verfügbar"
    except Exception:
        return "Nicht verfügbar"

# ==============================================================================
# 2. TECHNISCHE INDIKATOREN
# ==============================================================================
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=signal, adjust=False).mean()
    macd_hist = macd - macd_signal
    macd_pct = (macd / ema_slow) * 100
    return macd, macd_signal, macd_hist, macd_pct

def calculate_bollinger_bands(series, period=20, num_std=2):
    sma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper_band = sma + (num_std * std)
    lower_band = sma - (num_std * std)
    return upper_band, sma, lower_band

# ==============================================================================
# 3. TICKER SCRAPER (ROBUST & BEREINIGT)
# ==============================================================================
def fetch_market_data(markt):
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    def extract_from_df(df, market_type):
        cols_lower =
