import streamlit as st
import yfinance as yf
import pandas as pd
import os
import urllib.request
import google.generativeai as genai
import plotly.graph_objects as gr
from io import StringIO

# ==============================================================================
# CONFIG & HINTERGRUND-DESIGN (BLAU)
# ==============================================================================
st.set_page_config(page_title="KI-Markt-Scanner", layout="wide")

st.markdown("""
    <style>
    .stApp {
        background-color: #0a192f;
        color: #e6f1ff;
    }
    h1, h2, h3, .stSelectbox label, .stSlider label {
        color: #64ffda !important;
    }
    .stButton>button {
        background-color: #172a45 !important;
        color: #64ffda !important;
        border: 1px solid #64ffda !important;
    }
    .stButton>button:hover {
        background-color: #64ffda !important;
        color: #0a192f !important;
    }
    div[data-testid="stExpander"], div[data-testid="stDialog"] {
        background-color: #172a45 !important;
        border: 1px solid #233554 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# API-Konfiguration
GOOGLE_API_KEY = os.environ.get("GEMINI_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    st.error("Bitte hinterlege den GEMINI_API_KEY in den Streamlit Cloud Secrets!")

# Speicher für die Scan-Ergebnisse reservieren
if "scan_results" not in st.session_state:
    st.session_state.scan_results = []

# ==============================================================================
# MATHEMATISCHE HILFSFUNKTIONEN
# ==============================================================================
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(series, slow=26, fast=12, signal=9):
    exp1 = series.ewm(span=fast, adjust=False).mean()
    exp2 = series.ewm(span=slow, adjust=False).mean()
    macd_line = exp1 - exp2
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line

def get_wikipedia_table(url, match_index=0):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        html_text = response.read().decode('utf-8')
    return pd.read_html(StringIO(html_text))[match_index]

# ==============================================================================
# POPUP-DIALOG (FINANZ-COCKPIT)
# ==============================================================================
@st.dialog("📊 Finanz-Cockpit & Details", width="large")
def show_details_popup(ticker):
    st.write(f"### Analyse für **{ticker}**")
    
    with st.spinner("Lade fundamentale und technische Details..."):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            df = stock.history(period="6mo", interval="1d")
            
            df['RSI'] = calculate_rsi(df['Close'], period=14)
            df['MACD'], df['MACD_Signal'] = calculate_macd(df['Close'])
            last = df.iloc[-1]
            
            # 1. Stammdaten-Tabelle
            isin = info.get("isin", "N/A")
            wkn = info.get("wkn", "Siehe ISIN")
            name = info.get("longName", ticker)
            
            st.markdown(f"""
            | Parameter | Wert |
            | :--- | :--- |
            | **Unternehmen** | {name} |
            | **Ticker** | {ticker} |
            | **ISIN** | {isin} |
            | **WKN / WSN** | {wkn} |
            """)
            
            st.divider()
            
            # 2. Technische Live-Ampel
            st.write("#### 🚦 Technische Live-Ampel")
            rsi_val = last['RSI']
            macd_trend = last['MACD'] > last['MACD_Signal']
            
            if rsi_val < 40 and macd_trend:
                st.success("🟢 KAUFEN (Überverkauft + Bullish Cross)")
            elif 40 <= rsi_val <= 65 and macd_trend:
                st.success("🟢 KAUFEN / AKKUMULIEREN (Stabiler Trend)")
            elif rsi_val > 70:
                st.error("🔴 VERKAUFEN (Markt überhitzt)")
            else:
                st.warning("🟡 HALTEN (Neutraler Marktzustand)")
                
            st.divider()
            
            # 3. Drei interaktive Charts untereinander
            st.write("#### 📈 Charts")
            
            # Candlestick
            fig_chart = gr.Figure()
            fig_chart.add_trace(gr.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Kurs"))
            fig_chart.update_layout(title="Live Candlestick (6 Monate)", xaxis_rangeslider_visible=False, template="plotly_dark", height=250, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig_chart, use_container_width=True)
            
            # RSI
            fig_rsi = gr.Figure()
            fig_rsi.add_trace(gr.Scatter(x=df.index, y=df['RSI'], mode='lines', name='RSI', line=dict(color='#64ffda')))
            fig_rsi.add_hline(y=70, line_dash="dash", line_color="red")
            fig_rsi.add_hline(y=30, line_dash="dash", line_color="green")
            fig_rsi.update_layout(title=f"RSI14 (Aktuell: {rsi_val:.1f})", yaxis=dict(range=[10, 90]), template="plotly_dark", height=180, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig_rsi, use_container_width=True)
            
            # MACD
            fig_macd = gr.Figure()
            fig_macd.add_trace(gr.Scatter(x=df.index, y=df['MACD'], mode='lines', name='MACD'))
            fig_macd.add_trace(gr.Scatter(x=df.index, y=df['MACD_Signal'], mode='lines', name='Signal'))
            fig_macd.update_layout(title="MACD Momentum", template="plotly_dark", height=180, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig_macd, use_container_width=True)
            
            st.divider()
            
            # 4. Analysten-Tabelle
            st.write("#### 👥 Analysten-Konsensus & Ratings")
            analysten_data = {
                "Metrik": ["Aktueller Kurs", "Kursziel (Schnitt)", "Höchstes Kursziel", "Gesamturteil"],
                "Wert": [
                    f"{info.get('currentPrice', last['Close'])} USD", 
                    f"{info.get('targetMeanPrice', 'N/A')} USD", 
                    f"{info.get('targetHighPrice', 'N/A')} USD", 
                    info.get("recommendationKey", "N/A").upper()
                ]
            }
            st.table(pd.DataFrame(analysten_data))
            
        except Exception as e:
            st.error(f"Fehler beim Abrufen der Popup-Daten: {e}")

# ==============================================================================
# HAUPTANSICHT: SCANNER FORMULAR
# ==============================================================================
st.title("🤖 KI-Markt- & Branchen-Scanner v2.7")

markt = st.selectbox(
    "1. Welchen Index möchtest du scannen?",
    ("S&P 500 (USA) - Top 500 US-Unternehmen", "NASDAQ-100 (USA) - Große Tech-Werte", "Dow Jones Industrial Average (USA) - 30 Blue-Chips", "DAX 40 (Deutschland) - Deutscher Leitindex", "EURO STOXX 50 (Eurozone) - Europa Top 50")
)

branche = st.selectbox(
    "2. Welche Branche möchtest du filtern?",
    ("Alle Branchen", "Grundindustrie (Rohstoffe, Bauwesen,
