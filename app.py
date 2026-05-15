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

# CSS für dunkelblauen Hintergrund und optimierte Textfarben
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
    div[data-testid="stExpander"] {
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

# Session States initialisieren
if "detail_ticker" not in st.session_state:
    st.session_state.detail_ticker = None
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
# ANSICHT 2: TIEFE DETAILSEITE (WENN TICKER GEWÄHLT IST)
# ==============================================================================
if st.session_state.detail_ticker:
    ticker = st.session_state.detail_ticker
    
    if st.button("⬅️ Zurück zur Übersicht"):
        st.session_state.detail_ticker = None
        st.rerun()
        
    st.title(f"📊 Finanz-Cockpit: {ticker}")
    
    with st.spinner(f"Lade Finanzdetails für {ticker}..."):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            df = stock.history(period="6mo", interval="1d")
            
            df['RSI'] = calculate_rsi(df['Close'], period=14)
            df['MACD'], df['MACD_Signal'] = calculate_macd(df['Close'])
            last = df.iloc[-1]
            
            # Stammdaten
            isin = info.get("isin", "N/A")
            wkn = info.get("wkn", "Siehe ISIN")
            name = info.get("longName", ticker)
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Unternehmen", name)
            c2.metric("Ticker", ticker)
            c3.metric("ISIN", isin)
            c4.metric("WKN / WSN", wkn)
            
            st.divider()
            
            # AMPELEMPFEHLUNG
            st.subheader("🚦 Technische Analyse-Ampel")
            rsi_val = last['RSI']
            macd_trend = last['MACD'] > last['MACD_Signal']
            
            if rsi_val < 40 and macd_trend:
                st.markdown("### 🟢 KAUFEN (Überverkauftes Signal + Trendwendemuster)")
            elif 40 <= rsi_val <= 65 and macd_trend:
                st.markdown("### 🟢 KAUFEN / AKKUMULIEREN (Stabiler Aufwärtstrend)")
            elif rsi_val > 70:
                st.markdown("### 🔴 VERKAUFEN (Stark überhitzt)")
            else:
                st.markdown("### 🟡 HALTEN (Neutraler Trendkanal)")
                
            st.divider()
            
            # CHARTS GENERIEREN (Plotly Dark-Design kompatibel)
            fig_chart = gr.Figure()
            fig_chart.add_trace(gr.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Kurs"))
            fig_chart.update_layout(title="Live Candlestick Chart (6 Monate)", xaxis_rangeslider_visible=False, template="plotly_dark", height=300)
            st.plotly_chart(fig_chart, use_container_width=True)
            
            fig_rsi = gr.Figure()
            fig_rsi.add_trace(gr.Scatter(x=df.index, y=df['RSI'], mode='lines', name='RSI', line=dict(color='#64ffda')))
            fig_rsi.add_hline(y=70, line_dash="dash", line_color="red")
            fig_rsi.add_hline(y=30, line_dash="dash", line_color="green")
            fig_rsi.update_layout(title=f"RSI14 (Aktuell: {rsi_val:.1f})", yaxis=dict(range=[10, 90]), template="plotly_dark", height=200)
            st.plotly_chart(fig_rsi, use_container_width=True)
            
            fig_macd = gr.Figure()
            fig_macd.add_trace(gr.Scatter(x=df.index, y=df['MACD'], mode='lines', name='MACD'))
            fig_macd.add_trace(gr.Scatter(x=df.index, y=df['MACD_Signal'], mode='lines', name='Signal'))
            fig_macd.update_layout(title="MACD Momentum", template="plotly_dark", height=200)
            st.plotly_chart(fig_macd, use_container_width=True)
            
            st.divider()
            
            # ANALYSTEN RATINGS
            st.subheader("👥 Analysten-Konsensus & Targets")
            analysten_data = {
                "Kennzahl": ["Aktueller Kurs", "Analysten-Ziel (Schnitt)", "Höchstes Kursziel", "Konsensus-Urteil"],
                "Wert": [f"{info.get('currentPrice', last['Close'])} USD", f"{info.get('targetMeanPrice', 'N/A')} USD", f"{info.get('targetHighPrice', 'N/A')} USD", info.get("recommendationKey", "N/A").upper()]
            }
            st.table(pd.DataFrame(analysten_data))
            
        except Exception as e:
            st.error(f"Fehler beim Laden der Details: {e}")
            st.session_state.detail_ticker = None
            
    st.stop()

# ==============================================================================
# ANSICHT 1: BRANCHEN- & MARKT-SCANNER (HAUPTSEITE)
# ==============================================================================
st.title("🤖 KI-Markt- & Branchen-Scanner v2.6")

markt = st.selectbox(
    "1. Welchen Index möchtest du scannen?",
    ("S&P 500 (USA) - Top 500 US-Unternehmen", "NASDAQ-100 (USA) - Große Tech-Werte", "Dow Jones Industrial Average (USA) - 30 Blue-Chips", "DAX 40 (Deutschland) - Deutscher Leitindex", "EURO STOXX 50 (Eurozone) - Europa Top 50")
)

branche = st.selectbox(
    "2. Welche Branche möchtest du filtern?",
    ("Alle Branchen", "Grundindustrie (Rohstoffe, Bauwesen, Bergbau, Metalle, Öl & Gas, Chemie)", "Industriegüter & Dienstleistungen (Maschinen, Transport, Elektro, Luftfahrt)", "Konsumgüter (Automobil, Lebensmittel, Getränke, Haushaltsartikel)", "Verbraucherdienste (Medien, Tourismus, Einzelhandel, Freizeit)", "Gesundheitswesen (Pharma, Biotechnologie, med. Geräte)", "Versorger (Energie- und Versorgungssektor)", "Finanzwesen (Banken und Finanzdienstleister)", "Versicherungen", "Immobilien (Immobilieninvestmentgesellschaften, REITs)", "Technologie")
)

sektor_mapping = {
    "Grundindustrie (Rohstoffe, Bauwesen, Bergbau, Metalle, Öl & Gas, Chemie)": ["Basic Materials", "Energy"],
    "Industriegüter & Dienstleistungen (Maschinen, Transport, Elektro, Luftfahrt)": ["Industrials"],
    "Konsumgüter (Automobil, Lebensmittel, Getränke, Haushaltsartikel)": ["Consumer Cyclical", "Consumer Defensive"],
    "Verbraucherdienste (Medien, Tourismus, Einzelhandel, Freizeit)": ["Consumer Cyclical"],
    "Gesundheitswesen (Pharma, Biotechnologie, med. Geräte)": ["Healthcare"],
    "Versorger (Energie- und Versorgungssektor)": ["Utilities"],
    "Finanzwesen (Banken und Finanzdienstleister)": ["Financial Services"],
    "Versicherungen": ["Financial Services"],
    "Immobilien (Immobilieninvestmentgesellschaften, REITs)": ["Real Estate"],
    "Technologie": ["Technology", "Communication Services"]
}

st.sidebar.header("⚙️ Strategie-Anpassung")
rsi_min = st.sidebar.slider("RSI Minimum", 10, 50, 45)
rsi_max = st.sidebar.slider("RSI Maximum", 50, 90, 70)
vol_mult = st.sidebar.slider("Volumen-Faktor (x des Schnitts)", 0.5, 2.0, 1.0)

# SCAN LOGIK BUTTON
if st.button("🚀 Scan Starten"):
    st.session_state.scan_results = [] # Reset
    
    with st.spinner("Sammle Ticker-Daten..."):
        try:
            if "S&P 500" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", 0)
                tickers = [t.replace('.', '-') for t in table['Symbol'].tolist()][:80] # Begrenzung für Performance
            elif "NASDAQ-100" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/Nasdaq-100", 4)
                tickers = table['Ticker'].tolist()
            elif "DAX 40" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/DAX", 4)
                tickers = table['Ticker'].tolist()
            else:
                tickers = ["AAPL", "MSFT", "NVDA", "SAP", "SIE.DE", "AMZN"]
        except:
            tickers = ["AAPL", "MSFT", "NVDA", "SAP"]

    if tickers:
        with st.spinner("Lade Live-Kursdaten und filtere Profile..."):
            try:
                data = yf.download(tickers, period="3mo", interval="1d", group_by='ticker', progress=False)
                
                for ticker in tickers:
                    try:
                        df = data if len(tickers) == 1 else data[ticker].dropna()
                        if df.empty or len(df) < 25: continue
                        
                        if "Alle Branchen" not in branche:
                            t_info = yf.Ticker(ticker).info
                            if t_info.get("sector", "") not in sektor_mapping.get(branche, []): continue
                            if branche == "Versicherungen" and "Insurance" not in t_info.get("industry", ""): continue
                        
                        df['RSI'] = calculate_rsi(df['Close'], period=14)
                        df['MACD'], df['MACD_Signal'] = calculate_macd(df['Close'])
                        
                        last = df.iloc[-1]
                        avg_vol = df['Volume'].tail(15).mean()
                        
                        if (rsi_min <= last['RSI'] <= rsi_max) and (last['MACD'] > last['MACD_Signal']) and (last['Volume'] > avg_vol * vol_mult):
                            
                            # Generiere Gemini KI-Text sofort beim Scan
                            prompt = f"Aktie {ticker}: RSI {last['RSI']:.1f}. Gib eine extrem kurze Trading-Einschätzung (max 2 Sätze)."
                            response = model.generate_content(prompt)
                            
                            st.session_state.scan_results.append({
                                "ticker": ticker,
                                "rsi": f"{last['RSI']:.1f}",
                                "ai_text": response.text
                            })
                    except:
                        continue
            except Exception as e:
                st.error(f"Fehler beim Download: {e}")

# ERGEBNISSE PERMANENT RENDERN
if st.session_state.scan_results:
    st.write(f"### 🎯 Gefundene Setups ({len(st.session_state.scan_results)}):")
    
    for item in st.session_state.scan_results:
        t = item['ticker']
        
        # Jedes Ergebnis bekommt eine saubere, abgegrenzte Box
        with st.container():
            col_left, col_right = st.columns([3, 1])
            
            with col_left:
                st.write(f"**Aktie: {t}** (RSI: {item['rsi']})")
                st.info(f"**KI-Analyse:** {item['ai_text']}")
                
            with col_right:
                # Klick-Sicherheit durch separaten Key je Ticker
                if st.button(f"🔍 Details für {t}", key=f"select_{t}"):
                    st.session_state.detail_ticker = t
                    st.rerun()
            st.divider()
