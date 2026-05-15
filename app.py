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
                    grund = "Starkes Signal! RSI ist überverkauft (< 30) UND es liegt ein frisches Golden Cross vor."
                elif rsi_aktuell < 30:
                    grund = "Der RSI ist überverkauft (< 30). Die Aktie ist technisch reif für eine Erholung."
                else:
                    grund = "Es gab ein frisches Golden Cross (SMA50 schneidet SMA200) in den letzten 14 Tagen."
            else:
                ampel_signal = "🟡 HALTEN (Hold)"
                grund = "Die Aktie befindet sich im Antwortbereich auf Tagesbasis im neutralen Sektor."
            
            st.markdown(f"### Signal-Ampel (Tagesbasis): {ampel_signal}")
            st.caption(f"**Grund:** {grund}")
            st.write("")

            tab1, tab2, tab3, tab4 = st.tabs(["⏱️ 10 Min", "⏱️ 30 Min", "⏳ 4 Std", "📅 1 Tag (Klassisch)"])
            
            def render_chart(df_chart, title_suffix):
                if df_chart.empty or len(df_chart) < 2:
                    st.warning(f"Keine ausreichenden Chartdaten für {title_suffix} verfügbar.")
                    return
                
                df_chart['RSI'] = calculate_rsi(df_chart['Close'], period=14)
                
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.6, 0.4])
                fig.add_trace(gr.Scatter(x=df_chart.index, y=df_chart['Close'], mode='lines', name='Kurs', line=dict(color='#1f77b4', width=2)), row=1, col=1)
                
                if 'SMA50' in df_chart.columns:
                    fig.add_trace(gr.Scatter(x=df_chart.index, y=df_chart['SMA50'], mode='lines', name='SMA 50', line=dict(color='orange', width=1.5)), row=1, col=1)
                    fig.add_trace(gr.Scatter(x=df_chart.index, y=df_chart['SMA200'], mode='lines', name='SMA 200', line=dict(color='red', width=1.5)), row=1, col=1)
                
                fig.add_trace(gr.Scatter(x=df_chart.index, y=df_chart['RSI'], mode='lines', name='RSI 14', line=dict(color='purple', width=1.5)), row=2, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
                
                fig.update_layout(height=400, margin=dict(l=10, r=10, t=10, b=10), showlegend=True, yaxis2=dict(range=[0, 100]))
                st.plotly_chart(fig, use_container_width=True)

            with tab1:
                st.write("### 10-Minuten-Chart (Letzte 5 Handelstage)")
                df_10m = stock.history(period="5d", interval="10m")
                render_chart(df_10m, "10 Min")

            with tab2:
                st.write("### 30-Minuten-Chart (Letzte 14 Tage)")
                df_30m = stock.history(period="14d", interval="30m")
                render_chart(df_30m, "30 Min")

            with tab3:
                st.write("### 4-Stunden-Chart (Letzte 2 Monate)")
                df_1h = stock.history(period="60d", interval="1h")
                if not df_1h.empty:
                    df_4h = df_1h.resample('4h').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()
                else:
                    df_4h = pd.DataFrame()
                render_chart(df_4h, "4 Std")

            with tab4:
