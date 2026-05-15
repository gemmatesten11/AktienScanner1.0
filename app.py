import streamlit as st
import yfinance as yf
import pandas as pd
import urllib.request
import urllib.parse
import plotly.graph_objects as gr
from plotly.subplots import make_subplots
import json

# ==============================================================================
# UI CONFIG & THEME
# ==============================================================================
st.set_page_config(
    layout="wide", 
    page_title="RSI Scanner", 
    page_icon="⚡"
)

st.markdown("""
    <style>
        .main-title { font-size: 2.2rem; font-weight: 800; }
        .sub-title { color: #64748b; font-size: 1rem; margin-bottom: 2rem; }
        .stock-card {
            border-radius: 12px; padding: 1.2rem;
            background-color: var(--background-color);
            border: 1px solid rgba(128, 128, 128, 0.2);
        }
        .rsi-badge {
            padding: 2px 8px; border-radius: 6px;
            font-weight: 700; font-size: 0.85rem; float: right;
        }
        .rsi-low { background-color: rgba(34, 197, 94, 0.2); color: #22c55e; }
        .rsi-mid { background-color: rgba(148, 163, 184, 0.2); color: #94a3b8; }
        .rsi-high { background-color: rgba(239, 68, 68, 0.2); color: #ef4444; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# INDIKATOREN RECHNER
# ==============================================================================
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_macd(series):
    f_ema = series.ewm(span=12, adjust=False).mean()
    s_ema = series.ewm(span=26, adjust=False).mean()
    macd = f_ema - s_ema
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    pct = (macd / s_ema) * 100
    return macd, signal, hist, pct

def calculate_bollinger(series):
    sma = series.rolling(window=20).mean()
    std = series.rolling(window=20).std()
    return (sma + (2 * std)), sma, (sma - (2 * std))

# ==============================================================================
# MARKT-POOLS (STATISCH GEGEN PARSING-FEHLER)
# ==============================================================================
def fetch_market_data(markt):
    pools = {
        "Deutschland (DAX 40)": [
            {"ticker": "ADS.DE", "name": "Adidas"}, 
            {"ticker": "ALV.DE", "name": "Allianz"},
            {"ticker": "BAS.DE", "name": "BASF"}, 
            {"ticker": "BAYN.DE", "name": "Bayer"},
            {"ticker": "BMW.DE", "name": "BMW"}, 
            {"ticker": "DBK.DE", "name": "Deutsche Bank"},
            {"ticker": "DTE.DE", "name": "Deutsche Telekom"}, 
            {"ticker": "SAP.DE", "name": "SAP"},
            {"ticker": "SIE.DE", "name": "Siemens"}, 
            {"ticker": "VOW3.DE", "name": "Volkswagen"},
            {"ticker": "IFX.DE", "name": "Infineon"}, 
            {"ticker": "MBG.DE", "name": "Mercedes-Benz"}
        ],
        "USA (S&P 500)": [
            {"ticker": "AAPL", "name": "Apple"}, 
            {"ticker": "MSFT", "name": "Microsoft"},
            {"ticker": "AMZN", "name": "Amazon"}, 
            {"ticker": "NVDA", "name": "NVIDIA"},
            {"ticker": "GOOGL", "name": "Alphabet"}, 
            {"ticker": "META", "name": "Meta"},
            {"ticker": "TSLA", "name": "Tesla"}, 
            {"ticker": "JPM", "name": "JPMorgan Chase"}, 
            {"ticker": "V", "name": "Visa"}
        ]
    }
    return pools.get(markt, pools["Deutschland (DAX 40)"])

# ==============================================================================
# DETAIL POP-UP & CHARTS
# ==============================================================================
@st.dialog("📊 Pro-Analyse", width="large")
def show_details_popup(ticker, company_name):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="1y", interval="1d")
        if df.empty:
            st.error("Keine Daten gefunden.")
            return
        
        price = df['Close'].iloc[-1]
        df['RSI'] = calculate_rsi(df['Close'])
        df['SMA50'] = df['Close'].rolling(window=50).mean()
        df['SMA200'] = df['Close'].rolling(window=200).mean()
        df['M'], df['S'], df['H'], df['P'] = calculate_macd(df['Close'])
        
        rsi_now = df['RSI'].iloc[-1]
        
        st.markdown(f"## {company_name} (`{ticker}`)")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Kurs", f"{price:,.2f}")
        c2.metric("RSI Daily", f"{rsi_now:.2f}")
        c3.metric("MACD %", f"{df['P'].iloc[-1]:+.2f}%")
        
        fig = make_subplots(
            rows=3, cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.05,
            row_heights=[0.5, 0.25, 0.25]
        )
        
        fig.add_trace(gr.Scatter(x=df.index, y=df['Close'], name='Kurs'), row=1, col=1)
        fig.add_trace(gr.Scatter(x=df.index, y=df['SMA50'], name='SMA50'), row=1, col=1)
        fig.add_trace(gr.Scatter(x=df.index, y=df['SMA200'], name='SMA200'), row=1, col=1)
        
        fig.add_trace(gr.Scatter(x=df.index, y=df['RSI'], name='RSI'), row=2, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="green", row=2, col=1)
        
        fig.add_trace(gr.Scatter(x=df.index, y=df['M'], name='MACD'), row=3, col=1)
        fig.add_trace(gr.Scatter(x=df.index, y=df['S'], name='Signal'), row=3, col=1)
        fig.add_trace(gr.Bar(x=df.index, y=df['H'], name='Hist'), row=3, col=1)
        
        fig.update_layout(height=450, template="plotly_white", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        
    except Exception as e:
        st.error(f"Fehler: {e}")

# ==============================================================================
# SIDEBAR CONTROLS
# ==============================================================================
st.sidebar.markdown("### ⚡ Parameter")
rsi_min = st.sidebar.slider("RSI Min", 0, 100, 20)
rsi_max = st.sidebar.slider("RSI Max", 0, 100, 45)

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔍 Suche")
search_query = st.sidebar.text_input("Aktie suchen:", placeholder="z.B. Apple")

if search_query:
    try:
        raw_url = f"https://query2.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(search_query)}&quotesCount=3"
        req = urllib.request.Request(raw_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as resp:
            js = json.loads(resp.read().decode('utf-8'))
            for q in js.get('quotes', []):
                if q.get('quoteType') == 'EQUITY':
                    sym = q.get('symbol')
                    nm = q.get('shortname', 'Asset')
                    if st.sidebar.button(f"📊 {sym}"):
                        show_details_popup(sym, nm)
    except:
        pass

# ==============================================================================
# MAIN APPLICATION LOGIC
# ==============================================================================
st.markdown("<div class='main-title'>⚡ RSI Scanner</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>Echtzeit Relative-Strength-Index Auswertung.</div>", unsafe_allow_html=True)

markt = st.selectbox("Markt wählen:", ("Deutschland (DAX 40)", "USA (S&P 500)"))

if "results" not in st.session_state:
    st.session_state.results = []
if "scanned" not in st.session_state:
    st.session_state.scanned = False

if st.button("🚀 High-Speed Scan Starten", use_container_width=True, type="primary"):
    st.session_state.results = []
    st.session_state.scanned = True
    
    m_data = fetch_market_data(markt)
    tickers = [item['ticker'] for item in m_data]
    
    # Zeile 113 repariert und extrem kurz gehalten:
    t_names = {}
    for item in m_data:
        t_names[item['ticker']] = item['name']
        
    with st.spinner("Lade Kurse..."):
        try:
            data = yf.download(tickers, period="3mo", interval="1d", group_by='ticker', progress=False)
            is_mi = isinstance(data.columns, pd.MultiIndex)
            
            for tk in tickers:
                try:
                    df = data[tk].dropna(subset=['Close']).copy() if is_mi else data.dropna(subset=['Close']).copy()
                    if df.empty or len(df) < 15:
                        continue
                    
                    df['RSI'] = calculate_rsi(df['Close'])
                    r_val = df['RSI'].iloc[-1]
                    
                    if rsi_min <= r_val <= rsi_max:
                        st.session_state.results.append({
                            "ticker": tk, 
                            "name": t_names.get(tk, tk), 
                            "rsi": r_val
                        })
                except:
                    continue
        except Exception as e:
            st.error(f"Download Fehler: {e}")

# ==============================================================================
# RESULTS RENDERING
# ==============================================================================
if st.session_state.scanned:
    st.markdown("---")
    if st.session_state.results:
        cols = st.columns(3)
        for idx, item in enumerate(st.session_state.results):
            with cols[idx % 3]:
