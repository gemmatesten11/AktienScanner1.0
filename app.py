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
# 3. KORRIGIERTER & ABSOLUT SICHERER SCRAPER (MIT AUTO-FALLBACK)
# ==============================================================================
def fetch_market_data(markt):
    # WICHTIG: Korrekter User-Agent nach Wikipedia-Richtlinien gegen 403-Forbidden-Fehler
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
    except Exception as e:
        st.sidebar.warning(f"Live-Scraping blockiert, nutze integriertes Backup.")
    
    # KUGELSICHERER FALLBACK: Damit die App NIEMALS abstürzt
    if "USA" in markt:
        return [{"ticker": "AAPL", "name": "Apple"}, {"ticker": "MSFT", "name": "Microsoft"}, {"ticker": "NVDA", "name": "NVIDIA"}, {"ticker": "AMZN", "name": "Amazon"}, {"ticker": "GOOGL", "name": "Alphabet"}, {"ticker": "META", "name": "Meta"}, {"ticker": "TSLA", "name": "Tesla"}]
    else:
        return [{"ticker": "SAP.DE", "name": "SAP"}, {"ticker": "SIE.DE", "name": "Siemens"}, {"ticker": "ALV.DE", "name": "Allianz"}, {"ticker": "DTE.DE", "name": "Deutsche Telekom"}, {"ticker": "BMW.DE", "name": "BMW"}, {"ticker": "BAS.DE", "name": "BASF"}, {"ticker": "BAYN.DE", "name": "Bayer"}]

# ==============================================================================
# 4. POP-UP (DETAILS & SIGNAL-AMPEL INKL. VOLUMEN-ANOMALIE)
# ==============================================================================
@st.dialog("📊 Aktien-Details & Signal", width="large")
def show_details_popup(ticker, company_name):
    with St.spinner("Lade optimierte Daten aus dem Cache..."):
        try:
            df_base = load_cached_history(ticker, "1y", "1d")
            if df_base.empty:
                St.error("Keine Daten von Yahoo Finance erhalten. Bitte versuche es gleich noch einmal.")
                return
            
            current_price = df_base['Close'].iloc[-1]
            isin = load_cached_isin(ticker)
            
            df_base['RSI'] = calculate_rsi(df_base['Close'], period=14)
            df_base['SMA50'] = df_base['Close'].rolling(window=50).mean()
            df_base['SMA200'] = df_base['Close'].rolling(window=200).mean()
            df_base['MACD'], df_base['MACD_Signal'], df_base['MACD_Hist'], df_base['MACD_Pct'] = calculate_macd(df_base['Close'])
            
            df_base['Vol_SMA20'] = df_base['Volume'].rolling(window=20).mean()
            volumen_aktuell = df_base['Volume'].iloc[-1]
            volumen_schnitt = df_base['Vol_SMA20'].iloc[-1]
            volumen_prozent = (volumen_aktuell / volumen_schnitt * 100) if volumen_schnitt > 0 else 100.0
            
            df_base['Above'] = df_base['SMA50'] > df_base['SMA200']
            df_base['Crossover'] = df_base['Above'] & (~df_base['Above'].shift(1).fillna(True))
            recent_golden_cross = df_base['Crossover'].tail(14).any()
            
            rsi_aktuell = df_base['RSI'].iloc[-1]
            macd_pct_aktuell = df_base['MACD_Pct'].iloc[-1]
            
            St.write(f"## {company_name} (`{ticker}`)")
            
            meta_col1, meta_col2, meta_col3, meta_col4 = st.columns(4)
            with meta_col1:
                St.metric("Live-Kurs (ca.)", f"{current_price:,.2f}")
            with meta_col2:
                St.metric("RSI (14) Aktuell", f"{rsi_aktuell:.2f}")
            with meta_col3:
                Vol_delta = f"{volumen_prozent:.1f}% vom Schnitt"
                St.metric("Handelsvolumen (vs 20d)", f"{volumen_aktuell:,.0f}", delta=vol_delta if volumen_prozent > 150 else None)
            with meta_col4:
                St.write(f"**Identifikation:** ISIN: `{isin}`")
                Tv_ticker = ticker.split('.')[0]
                Tradingview_url = f"https://de.tradingview.com/symbols/{tv_ticker}/"
                St.markdown(f"[➡️ **Auf TradingView**]({tradingview_url})")
            
            St.write("---")
            
            Volumen_ausbruch = volumen_prozent >= 150.0
            
            if rsi_aktuell > 70:
                Ampel_signal = "🔴 VERKAUFEN (Sell)"
                Grund = "Der RSI (Tagesbasis) ist überkauft (> 70). Das Korrekturrisiko ist kurzfristig erhöht."
                if volumen_ausbruch:
                    Ampel_signal = "🚨 STARKES VERKAUFSSIGNAL (Strong Sell)"
                    Grund += " ZU DEM zeigt ein massiver Volumenausbruch (> 150%) das finale Ende der Kaufwelle (Buying Climax) an."
            elif rsi_aktuell < 30:
                if volumen_ausbruch:
                    Ampel_signal = "🔥💥 ULTRA-BUY (Volume Climax)"
                    Grund = f"Extrem starkes Kapitulations-Signal! Der RSI ist überverkauft ({rsi_aktuell:.2f}) UND es gibt einen massiven Volumenausbruch von {volumen_prozent:.0f}%! Große Marktteilnehmer fangen die Verkäufe sehr wahrscheinlich auf."
                else:
                    Ampel_signal = "🟢 KAUFEN (Buy)"
                    Grund = "Der RSI ist überverkauft (< 30). Die Aktie ist technisch bereit für eine Erholung."
            elif recent_golden_cross:
                Ampel_signal = "🟢 KAUFEN (Buy)"
                Grund = "Es gab ein frisches Golden Cross (SMA50 schneidet SMA200) in den letzten 14 Tagen."
            else:
                Ampel_signal = "🟡 HALTEN (Hold)"
                Grund = "Die Aktie befindet sich auf Tagesbasis im neutralen Sektor."
            
            if volumen_ausbruch and rsi_aktuell < 30:
                St.error(f"### Signal-Ampel: {ampel_signal}")
            elif "KAUFEN" in ampel_signal or "BUY" in ampel_signal:
                St.success(f"### Signal-Ampel: {ampel_signal}")
            elif "VERKAUFEN" in ampel_signal:
                St.warning(f"### Signal-Ampel: {ampel_signal}")
            else:
                St.info(f"### Signal-Ampel: {ampel_signal}")
                
            St.markdown(f"**Analyse-Begründung:** {grund}")
            St.write("")

            Tab1, tab2, tab3, tab4 = st.tabs(["⏱️ 10 Min", "⏱️ 30 Min", "⏳ 4 Std", "📅 1 Tag (Klassisch)"])
            
            def render_chart(df_chart, title_suffix):
                if df_chart.empty or len(df_chart) < 2:
                    St.warning(f"Keine ausreichenden Intraday-Daten für {title_suffix} im Cache.")
                    return
                
                Df_chart['RSI'] = calculate_rsi(df_chart['Close'], period=14)
                Df_chart['MACD'], df_chart['MACD_Signal'], df_chart['MACD_Hist'], _ = calculate_macd(df_chart['Close'])
                Df_chart['BB_Upper'], df_chart['BB_Middle'], df_chart['BB_Lower'] = calculate_bollinger_bands(df_chart['Close'])
                
                Fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06, row_heights=[0.45, 0.25, 0.30])
