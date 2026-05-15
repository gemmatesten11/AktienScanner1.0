import streamlit as st
import yfinance as yf
import pandas as pd
import urllib.request
import urllib.parse
import plotly.graph_objects as gr
from plotly.subplots import make_subplots
import random
import json

# ==============================================================================
# UI CONFIG & THEME CUSTOMIZATION
# ==============================================================================
st.set_page_config(layout="wide", page_title="High-Speed RSI Scanner", page_icon="⚡")

st.markdown("""
    <style>
        .main-title {
            font-size: 2.2rem;
            font-weight: 800;
            letter-spacing: -0.05rem;
            margin-bottom: 0.5rem;
        }
        .sub-title {
            color: #64748b;
            font-size: 1rem;
            margin-bottom: 2rem;
        }
        .stock-card {
            border-radius: 12px;
            padding: 1.2rem;
            background-color: var(--background-color);
            border: 1px solid rgba(128, 128, 128, 0.2);
            transition: transform 0.2s, border-color 0.2s;
        }
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
        return stock.history(period=period, interval=interval)
    except:
        return pd.DataFrame()

@st.cache_data(ttl=86400)
def load_cached_isin(ticker):
    try:
        stock = yf.Ticker(ticker)
        isin = stock.get_isin()
        return isin if isin and isin != '-' else "Nicht verfügbar"
    except:
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
    return macd, macd_signal, (macd - macd_signal), ((macd / ema_slow) * 100)

def calculate_bollinger_bands(series, period=20, num_std=2):
    sma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    return (sma + (num_std * std)), sma, (sma - (num_std * std))

# ==============================================================================
# 3. STATISCHER TICKER-POOLS (SCHNELL & STABIL)
# ==============================================================================
def fetch_market_data(markt):
    # Statische Definitionen verhindern Parsing-Fehler komplett
    pools = {
        "Deutschland (DAX 40 Large Caps)": [
            {"ticker": "ADS.DE", "name": "Adidas"}, {"ticker": "ALV.DE", "name": "Allianz"},
            {"ticker": "BAS.DE", "name": "BASF"}, {"ticker": "BAYN.DE", "name": "Bayer"},
            {"ticker": "BMW.DE", "name": "BMW"}, {"ticker": "DBK.DE", "name": "Deutsche Bank"},
            {"ticker": "DTE.DE", "name": "Deutsche Telekom"}, {"ticker": "SAP.DE", "name": "SAP"},
            {"ticker": "SIE.DE", "name": "Siemens"}, {"ticker": "VOW3.DE", "name": "Volkswagen"},
            {"ticker": "IFX.DE", "name": "Infineon"}, {"ticker": "MBG.DE", "name": "Mercedes-Benz"}
        ],
        "USA (S&P 500 Large Caps)": [
            {"ticker": "AAPL", "name": "Apple"}, {"ticker": "MSFT", "name": "Microsoft"},
            {"ticker": "AMZN", "name": "Amazon"}, {"ticker": "NVDA", "name": "NVIDIA"},
            {"ticker": "GOOGL", "name": "Alphabet"}, {"ticker": "META", "name": "Meta"},
            {"ticker": "TSLA", "name": "Tesla"}, {"ticker": "BRK-B", "name": "Berkshire Hathaway"},
            {"ticker": "JPM", "name": "JPMorgan Chase"}, {"ticker": "V", "name": "Visa"}
        ],
        "Eurozone (EURO STOXX 50)": [
            {"ticker": "ASML.AS", "name": "ASML"}, {"ticker": "MC.PA", "name": "LVMH"},
            {"ticker": "OR.PA", "name": "L'Oreal"}, {"ticker": "LIN", "name": "Linde"},
            {"ticker": "SAN.MC", "name": "Banco Santander"}, {"ticker": "SU.PA", "name": "Schneider Electric"}
        ]
    }
    # Fallback, falls ein nicht-implementierter Markt geklickt wird
    return pools.get(markt, pools["Deutschland (DAX 40 Large Caps)"])

# ==============================================================================
# 4. POP-UP DETAILS & OPTIMIERTE CHARTS
# ==============================================================================
@st.dialog("📊 Pro-Analyse & Technische Signale", width="large")
def show_details_popup(ticker, company_name):
    with st.spinner("Generiere Chart-Ansichten..."):
        try:
            df_base = load_cached_history(ticker, "1y", "1d").copy()
            if df_base.empty:
                st.error("Keine historischen Daten verfügbar.")
                return
            
            current_price = df_base['Close'].iloc[-1]
            isin = load_cached_isin(ticker)
            
            df_base['RSI'] = calculate_rsi(df_base['Close'], period=14)
            df_base['SMA50'] = df_base['Close'].rolling(window=50).mean()
            df_base['SMA200'] = df_base['Close'].rolling(window=200).mean()
            df_base['MACD'], df_base['MACD_Sig'], df_base['MACD_Hist'], df_base['MACD_Pct'] = calculate_macd(df_base['Close'])
            
            recent_golden_cross = ((df_base['SMA50'] > df_base['SMA200']) & (~(df_base['SMA50'].shift(1) > df_base['SMA200'].shift(1)))).tail(14).any()
            rsi_aktuell = df_base['RSI'].iloc[-1]
            macd_pct_aktuell = df_base['MACD_Pct'].iloc[-1]
            
            st.markdown(f"## {company_name} <span style='color:#64748b; font-size:1.3rem;'>`{ticker}`</span>", unsafe_allow_html=True)
            
            meta_col1, meta_col2, meta_col3, meta_col4 = st.columns(4)
            meta_col1.metric("Letzter Kurs", f"{current_price:,.2f} EUR")
            meta_col2.metric("RSI (14) Daily", f"{rsi_aktuell:.2f}")
            meta_col3.metric("MACD vs. Baseline", f"{macd_pct_aktuell:+.2f}%")
            
            with meta_col4:
                st.markdown(f"<div style='padding-top:5px; font-size:0.9rem;'><b>ISIN:</b> `{isin}`</div>", unsafe_allow_html=True)
                st.markdown(f"[➡️ **TradingView Öffnen**](https://de.tradingview.com/symbols/{ticker.split('.')[0]}/)")
            
            if rsi_aktuell > 70:
                st.error(f"### 🔴 Signal: VERKAUFEN (Überkauft)\n**Grund:** Der RSI liegt aktuell bei {rsi_aktuell:.2f}. Der Markt signalisiert eine kurzfristige Überhitzung.")
            elif rsi_aktuell < 30:
                st.success(f"### 🟢 Signal: KAUFEN (Überverkauft)\n**Grund:** Der RSI-Wert von {rsi_aktuell:.2f} deutet auf eine massive Unterbewertung hin.")
            elif recent_golden_cross:
                st.success(f"### 🟢 Signal: KAUFEN (Golden Cross)\n**Grund:** Ein bullisches 'Golden Cross' (SMA50 schneidet SMA200 nach oben) ist aktiv.")
            else:
                st.info(f"### 🟡 Signal: HALTEN (Neutral)\n**Grund:** Der RSI befindet sich im gesunden Mittelfeld.")
            
            tab1, tab2 = st.tabs(["📅 1 Tag (Klassisch)", "⏱️ Intra-Day Snapshot"])
            
            def render_chart(df_chart, show_smas=False):
                if df_chart.empty or len(df_chart) < 2:
                    st.warning("Keine ausreichenden Daten vorhanden.")
                    return
                
                df_chart = df_chart.copy()
                df_chart['RSI'] = calculate_rsi(df_chart['Close'], period=14)
                df_chart['M'], df_chart['S'], df_chart['H'], _ = calculate_macd(df_chart['Close'])
                df_chart['BU'], df_chart['BM'], df_chart['BL'] = calculate_bollinger_bands(df_chart['Close'])
                
                fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=[0.5, 0.25, 0.25])
                fig.add_trace(gr.Scatter(x=df_chart.index, y=df_chart['Close'], mode='lines', name='Kurs', line=dict(color='#2563eb', width=2)), row=1, col=1)
                
                if show_smas:
                    df_chart['SMA50'] = df_chart['Close'].rolling(window=50).mean()
                    df_chart['SMA200'] = df_chart['Close'].rolling(window=200).mean()
                    fig.add_trace(gr.Scatter(x=df_chart.index, y=df_chart['SMA50'], mode='lines', name='SMA 50', line=dict(color='#f59e0b', width=1.2)), row=1, col=1)
                    fig.add_trace(gr.Scatter(x=df_chart.index, y=df_chart['SMA200'], mode='lines', name='SMA 200', line=dict(color='#ef4444', width=1.2)), row=1, col=1)
                
                fig.add_trace(gr.Scatter(x=df_chart.index, y=df_chart['BU'], mode='lines', name='BBU', line=dict(color='rgba(148,163,184,0.3)', width=1, dash='dash')), row=1, col=1)
                fig.add_trace(gr.Scatter(x=df_chart.index, y=df_chart['BL'], mode='lines', name='BBL', line=dict(color='rgba(148,163,184,0.3)', width=1, dash='dash')), row=1, col=1)
                
                fig.add_trace(gr.Scatter(x=df_chart.index, y=df_chart['RSI'], mode='lines', name='RSI', line=dict(color='#8b5cf6', width=1.5)), row=2, col=1)
                fig.add_hline(y=70, line_dash="dot", line_color="#ef4444", row=2, col=1, opacity=0.5)
                fig.add_hline(y=30, line_dash="dot", line_color="#22c55e", row=2, col=1, opacity=0.5)
                
                fig.add_trace(gr.Scatter(x=df_chart.index, y=df_chart['M'], mode='lines', name='MACD', line=dict(color='#3b82f6', width=1.2)), row=3, col=1)
                fig.add_trace(gr.Scatter(x=df_chart.index, y=df_chart['S'], mode='lines', name='Signal', line=dict(color='#f97316', width=1.2)), row=3, col=1)
                fig.add_trace(gr.Bar(x=df_chart.index, y=df_chart['H'], name='Hist', marker_color='rgba(148,163,184,0.4)'), row=3, col=1)
                
                fig.update_layout(height=480, margin=dict(l=10, r=10, t=10, b=10), showlegend=False, template="plotly_white")
                st.plotly_chart(fig, use_container_width=True)

            with tab1:
                render_chart(df_base.tail(45), show_smas=True)
            with tab2:
                render_chart(load_cached_history(ticker, "5d", "30m"), show_smas=False)
                
        except Exception as e:
            st.error(f"Fehler beim Chart-Rendering: {e}")

# ==============================================================================
# 5. SIDEBAR CONTROLS
# ==============================================================================
st.sidebar.markdown("### ⚡ Parameter & Filter")
rsi_min = st.sidebar.slider("Minimaler RSI-Wert", 0, 100, 20, step=1)
rsi_max = st.sidebar.slider("Maximaler RSI-Wert", 0, 100, 45, step=1)

st.sidebar.markdown("---")
st.sidebar.markdown("### 📈 Chart-Signale")
golden_cross_active = st.sidebar.toggle("Nur mit frischem Golden Cross", value=False)

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔍 Direkte Suche")

def get_ticker_suggestions(query):
    if not query or len(query) < 2: return []
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(query)}&quotesCount=5&newsCount=0"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            return [{"label": f"{q.get('symbol')} - {q.get('shortname', 'Asset')}", "ticker": q.get('symbol'), "name": q.get('shortname', 'Asset')} for q in data.get('quotes', []) if q.get('quoteType') == 'EQUITY']
    except:
        return []

search_query = st.sidebar.text_input("Aktie oder Kürzel eingeben:", placeholder="z.B. Apple")
if search_query:
    suggestions = get_ticker_suggestions(search_query)
    if suggestions:
        options_dict = {item["label"]: item for item in suggestions}
        selected_label = st.sidebar.selectbox("Gefundene Treffer:", options_dict.keys(), index=0)
        if selected_label and st.sidebar.button("📊 Analysieren", use_container_width=True):
            show_details_popup(options_dict[selected_label]["ticker"], options_dict[selected_label]["name"])

# ==============================================================================
# 6. MAIN CONTENT & LOGIC
# ==============================================================================
st.markdown("<div class='main-title'>⚡ Ultra-Schneller Globaler RSI-Scanner</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>Scanne Märkte weltweit in Echtzeit auf Basis von Relative-Strength-Index.</div>", unsafe_allow_html=True)

markt = st.selectbox("Wähle den Zielmarkt für die Analyse:", ("Deutschland (DAX 40 Large Caps)", "USA (S&P 500 Large Caps)", "Eurozone (EURO STOXX 50)"))

if "scan_results" not in st.session_state: st.session_state.scan_results = []
if "has_scanned" not in st.session_state: st.session_state.has_scanned = False

if st.button("🚀 High-Speed Scan Starten", use_container_width=True, type="primary"):
    st.session_state.scan_results = []
    st.session_state.has_scanned = True
    
    market_data = fetch_market_data(markt)

    if market_data:
        tickers = [item['ticker'] for item in market_data]
        ticker_to_name = {item['ticker']: item['name'] for item in market_
