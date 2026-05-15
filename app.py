import streamlit as st
import yfinance as yf
import pandas as pd
import os
import urllib.request
import google.generativeai as genai
import plotly.graph_objects as gr
from io import StringIO

# Streamlit Page Config für breiteres Layout (wichtig für Charts im Pop-up)
st.set_page_config(layout="wide")

# ==============================================================================
# 1. API-KONFIGURATION & SESSION STATE
# ==============================================================================
GOOGLE_API_KEY = os.environ.get("GEMINI_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    st.error("Bitte hinterlege den GEMINI_API_KEY in den Streamlit Cloud Secrets!")

# Wichtig: Gefundene Aktien speichern, damit sie beim Öffnen des Pop-ups nicht verschwinden
if "scan_results" not in st.session_state:
    st.session_state.scan_results = []
if "has_scanned" not in st.session_state:
    st.session_state.has_scanned = False

# ==============================================================================
# 2. MATHEMATISCHE HILFSFUNKTIONEN
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
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    )
    with urllib.request.urlopen(req) as response:
        html_text = response.read().decode('utf-8')
    return pd.read_html(StringIO(html_text))[match_index]

# ==============================================================================
# 3. DIE DIAGLOG-FUNKTION (DAS ECHTE POP-UP)
# ==============================================================================
@st.dialog("📊 Finanz-Cockpit & Details", width="large")
def show_details_popup(ticker):
    st.write(f"### Detailanalyse für: **{ticker}**")
    st.divider()
    
    with st.spinner(f"Lade Live-Indikatoren und Charts für {ticker}..."):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            df = stock.history(period="6mo", interval="1d")
            
            df['RSI'] = calculate_rsi(df['Close'], period=14)
            df['MACD'], df['MACD_Signal'] = calculate_macd(df['Close'])
            last = df.iloc[-1]
            rsi_val = last['RSI']
            
            # Stammdaten
            isin = info.get("isin", "Nicht verfügbar")
            wkn = info.get("wkn", "Siehe ISIN") 
            name = info.get("longName", ticker)
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Unternehmen", name)
            col2.metric("Ticker", ticker)
            col3.metric("ISIN", isin)
            col4.metric("WKN", wkn)
            
            st.divider()
            
            # Rechnerische Ampel
            macd_trend = last['MACD'] > last['MACD_Signal']
            if rsi_val < 35 and macd_trend:
                ampel_status, ampel_color = "KAUFEN (Überverkauft + Bullish)", "🟢"
            elif 35 <= rsi_val <= 65 and macd_trend:
                ampel_status, ampel_color = "KAUFEN / AKKUMULIEREN", "🟢"
            elif rsi_val > 70:
                ampel_status, ampel_color = "VERKAUFEN (Überhitzt)", "🔴"
            else:
                ampel_status, ampel_color = "HALTEN (Neutral)", "🟡"
                
            st.info(f"**Technische Live-Ampel:** {ampel_color} {ampel_status}")
            st.divider()
            
            # CHARTS GENERIEREN
            # 1. Candlestick
            fig_chart = gr.Figure()
            fig_chart.add_trace(gr.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Kurs"))
            fig_chart.update_layout(title="Live Candlestick Chart (6 Monate)", xaxis_rangeslider_visible=False, height=280)
            st.plotly_chart(fig_chart, use_container_width=True)
            
            # 2. RSI
            fig_rsi = gr.Figure()
            fig_rsi.add_trace(gr.Scatter(x=df.index, y=df['RSI'], mode='lines', name='RSI', line=dict(color='purple')))
            fig_rsi.add_hline(y=70, line_dash="dash", line_color="red")
            fig_rsi.add_hline(y=30, line_dash="dash", line_color="green")
            fig_rsi.update_layout(title=f"RSI14 Indikator (Aktuell: {rsi_val:.1f})", yaxis=dict(range=[10, 90]), height=180)
            st.plotly_chart(fig_rsi, use_container_width=True)
            
            # 3. MACD
            fig_macd = gr.Figure()
            fig_macd.add_trace(gr.Scatter(x=df.index, y=df['MACD'], mode='lines', name='MACD', line=dict(color='blue')))
            fig_macd.add_trace(gr.Scatter(x=df.index, y=df['MACD_Signal'], mode='lines', name='Signal', line=dict(color='orange')))
            df['Histo'] = df['MACD'] - df['MACD_Signal']
            fig_macd.add_trace(gr.Bar(x=df.index, y=df['Histo'], name='Histogramm', opacity=0.3))
            fig_macd.update_layout(title="MACD Momentum", height=180)
            st.plotly_chart(fig_macd, use_container_width=True)
            
        except Exception as e:
            st.error(f"Fehler beim Laden der Details: {e}")

# ==============================================================================
# 4. HAUPTANSICHT: BRANCHEN- & MARKT-SCANNER
# ==============================================================================
st.title("🤖 KI-Markt- & Branchen-Scanner v2.5")
st.write("Massen-Live-Scan mit Candlestick-Charts, RSI, MACD und KI-Analyse.")

markt = st.selectbox(
    "1. Welchen Index möchtest du scannen?",
    ("S&P 500 (USA) - Top 500 US-Unternehmen", "NASDAQ-100 (USA) - Große Tech-Werte", "DAX 40 (Deutschland) - Deutscher Leitindex")
)

branche = st.selectbox(
    "2. Welche Branche möchtest du filtern?",
    ("Alle Branchen", "Technologie", "Finanzwesen (Banken und Finanzdienstleister)", "Gesundheitswesen (Pharma, Biotechnologie, med. Geräte)")
)

sektor_mapping = {
    "Technologie": ["Technology", "Communication Services"],
    "Finanzwesen (Banken und Finanzdienstleister)": ["Financial Services"],
    "Gesundheitswesen (Pharma, Biotechnologie, med. Geräte)": ["Healthcare"]
}

st.sidebar.header("⚙️ Strategie-Anpassung")
rsi_min = st.sidebar.slider("RSI Minimum", 10, 50, 45)
rsi_max = st.sidebar.slider("RSI Maximum", 50, 90, 70)
vol_mult = st.sidebar.slider("Volumen-Faktor (x des Schnitts)", 0.5, 2.0, 1.0)

# ==============================================================================
# 5. SCAN LOGIK
# ==============================================================================
if st.button("🚀 Scan Starten"):
    st.session_state.scan_results = [] # Reset bei Neustart
    st.session_state.has_scanned = True
    
    with st.spinner("Hole aktuelle Aktienliste und analysiere Live-Daten..."):
        try:
            if "S&P 500" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", 0)
                tickers = [t.replace('.', '-') for t in table['Symbol'].tolist()][:40] # Auf 40 limitiert für Performance
            elif "NASDAQ-100" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/Nasdaq-100", 4)
                tickers = table['Ticker'].tolist()[:40]
            else:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/DAX", 4)
                tickers = table['Ticker'].tolist()
        except Exception as e:
            st.error(f"Fehler beim Laden des Index: {e}")
            tickers = []

        if tickers:
            try:
                data = yf.download(tickers, period="3mo", interval="1d", group_by='ticker', progress=False)
                
                for ticker in tickers:
                    df = data[ticker].dropna() if len(tickers) > 1 else data.copy()
                    if df.empty or len(df) < 25: continue
                    
                    # Branchenfilter
                    if "Alle Branchen" not in branche:
                        t_info = yf.Ticker(ticker).info
                        if t_info.get("sector", "") not in sektor_mapping.get(branche, []): continue

                    df['RSI'] = calculate_rsi(df['Close'], period=14)
                    df['MACD'], df['MACD_Signal'] = calculate_macd(df['Close'])
                    
                    last = df.iloc[-1]
                    avg_vol = df['Volume'].tail(15).mean()
                    
                    if (rsi_min <= last['RSI'] <= rsi_max) and (last['MACD'] > last['MACD_Signal']) and (last['Volume'] > (avg_vol * vol_mult)):
                        # KI Prompt generieren
                        prompt = f"Aktie {ticker}: RSI ist {last['RSI']:.1f}, Volumen liegt bei {last['Volume']/avg_vol:.1f}x des Schnitts. Extrem kurze Trading-Einschätzung (max 2 Sätze)."
                        ai_response = model.generate_content(prompt).text
                        
                        # Ergebnisse im State sichern
                        st.session_state.scan_results.append({
                            "ticker": ticker,
                            "rsi": f"{last['RSI']:.1f}",
                            "ai_text": ai_text
                        })
            except Exception as e:
                st.error(f"Fehler während der Analyse: {e}")

# ==============================================================================
# 6. RENDERING DER ERGEBNISSE AUS DEM STATE (Garantiert sichtbare Pop-ups)
# ==============================================================================
if st.session_state.has_scanned:
    if st.session_state.scan_results:
        st.write(f"### 🎯 Gefundene Treffer ({len(st.session_state.scan_results)})")
        
        for idx, item in enumerate(st.session_state.scan_results):
            with st.container():
                st.success(f"**{item['ticker']}** (RSI: {item['rsi']})")
                
                # Wenn dieser Button geklickt wird, lädt Streamlit neu, ABBER die Ergebnisse
                # stehen noch in st.session_state.scan_results, weshalb das Pop-up sauber triggert!
                if st.button(f"🔍 Vollständige Finanzdetails für {item['ticker']} anzeigen", key=f"popup_{item['ticker']}_{idx}"):
                    show_details_popup(item["ticker"])
                
                st.info(f"**Gemini-Analyse:** {item['ai_text']}")
                st.divider()
    else:
        st.warning("Keine Treffer erzielt. Lockere die Kriterien in der Seitenleiste!")
