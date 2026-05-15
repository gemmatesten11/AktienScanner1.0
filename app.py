import streamlit as st
import yfinance as yf
import pandas as pd
import os
import urllib.request
import google.generativeai as genai
import plotly.graph_objects as gr
from plotly.subplots import make_subplots
from io import StringIO

# Streamlit Page Config für ein breiteres Layout
st.set_page_config(layout="wide", page_title="KI-Markt-Scanner", page_icon="🤖")

# ==============================================================================
# 1. API-KONFIGURATION & SESSION STATE
# ==============================================================================
GOOGLE_API_KEY = os.environ.get("GEMINI_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    st.error("Bitte hinterlege den GEMINI_API_KEY in den Streamlit Cloud Secrets!")

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
# 3. POP-UP DETAILANSICHT (FINANZ-COCKPIT)
# ==============================================================================
@st.dialog("📊 Interaktives Finanz-Cockpit", width="large")
def show_details_popup(ticker):
    st.write(f"### Live-Analyse für: **{ticker}**")
    
    # Interaktiver Intervall-Umschalter für die Chart-Ansicht
    intervall_auswahl = st.radio(
        "⏱️ Chart-Zeiteinheit auswählen:",
        options=["30 Min", "1 Std", "4 Std"],
        horizontal=True
    )
    
    # Mapping für yfinance Intervalle und Zeiträume
    mapping = {
        "30 Min": {"interval": "30m", "period": "1mo"},
        "1 Std": {"interval": "60m", "period": "2mo"},
        "4 Std": {"interval": "1h", "period": "3mo"} # yfinance unterstützt nativ kein 4h, daher 1h mit längerem Verlauf
    }
    
    selected_interval = mapping[intervall_auswahl]["interval"]
    selected_period = mapping[intervall_auswahl]["period"]
    
    st.divider()
    
    with st.spinner(f"Lade Live-Daten ({intervall_auswahl}) für {ticker}..."):
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=selected_period, interval=selected_interval)
            
            if df.empty:
                st.error("Keine Live-Kursdaten für dieses Intervall verfügbar.")
                return
                
            # Technische Indikatoren berechnen
            df['RSI'] = calculate_rsi(df['Close'], period=14)
            df['MACD'], df['MACD_Signal'] = calculate_macd(df['Close'])
            df['SMA200'] = df['Close'].rolling(window=200).mean()
            
            last = df.iloc[-1]
            rsi_aktuell = last['RSI']
            
            # ------------------------------------------------------------------
            # 1. KURS-LINIENCHART MIT SMA200 & MACD (Zwei Y-Achsen)
            # ------------------------------------------------------------------
            st.subheader("📈 Hauptchart (Kurs, SMA200 & MACD)")
            
            fig_main = make_subplots(specs=[[{"secondary_y": True}]])
            
            # Kurs als Linie
            fig_main.add_trace(
                gr.Scatter(x=df.index, y=df['Close'], mode='lines', name='Kurs (Schluss)', line=dict(color='blue', width=2)),
                secondary_y=False
            )
            # SMA200 Linie
            fig_main.add_trace(
                gr.Scatter(x=df.index, y=df['SMA200'], mode='lines', name='SMA 200', line=dict(color='red', width=1.5, dash='dash')),
                secondary_y=False
            )
            # MACD auf sekundärer Y-Achse
            fig_main.add_trace(
                gr.Scatter(x=df.index, y=df['MACD'], mode='lines', name='MACD Linie', line=dict(color='orange', width=1)),
                secondary_y=True
            )
            fig_main.add_trace(
                gr.Scatter(x=df.index, y=df['MACD_Signal'], mode='lines', name='MACD Signal', line=dict(color='gray', width=1, dash='dot')),
                secondary_y=True
            )
            
            fig_main.update_layout(
                height=400,
                xaxis_rangeslider_visible=False,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(l=10, r=10, t=10, b=10)
            )
            fig_main.update_yaxes(title_text="Kurs in USD / EUR", secondary_y=False)
            fig_main.update_yaxes(title_text="MACD Wert", secondary_y=True, showgrid=False)
            
            st.plotly_chart(fig_main, use_container_width=True)
            
            # ------------------------------------------------------------------
            # 2. VOLUMEN-CHART (Direkt darunter)
            # ------------------------------------------------------------------
            st.subheader("📊 Handelsvolumen")
            fig_vol = gr.Figure()
            fig_vol.add_trace(gr.Bar(x=df.index, y=df['Volume'], name='Volumen', marker_color='teal', opacity=0.7))
            fig_vol.update_layout(height=150, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig_vol, use_container_width=True)
            
            st.divider()
            
            # ------------------------------------------------------------------
            # 3. RSI ANSICHT (Letzte 14 Kerzen/Perioden) & INFOBOX DANEBEN
            # ------------------------------------------------------------------
            st.subheader("⏱️ RSI (Letzte 14 Perioden)")
            
            col_chart, col_info = st.columns([2, 1])
            
            # Letzte 14 Einträge für den RSI extrahieren
            df_rsi_last14 = df.tail(14)
            
            with col_chart:
                fig_rsi = gr.Figure()
                fig_rsi.add_trace(gr.Scatter(x=df_rsi_last14.index, y=df_rsi_last14['RSI'], mode='lines+markers', name='RSI14', line=dict(color='purple', width=2)))
                fig_rsi.add_hline(y=70, line_dash="dash", line_color="red")
                fig_rsi.add_hline(y=30, line_dash="dash", line_color="green")
                fig_rsi.update_layout(height=200, yaxis=dict(range=[10, 90]), margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig_rsi, use_container_width=True)
                
            with col_info:
                st.write("###") # Vertikaler Abstandhalter
                if rsi_aktuell > 70:
                    st.error(f"⚠️ **RSI14 Wert: {rsi_aktuell:.2f}**\n\nDer Markt ist aktuell stark überkauft (Überhitzt).")
                elif rsi_aktuell < 30:
                    st.success(f"✅ **RSI14 Wert: {rsi_aktuell:.2f}**\n\nDer Markt ist aktuell stark überverkauft.")
                else:
                    st.info(f"ℹ️ **RSI14 Wert: {rsi_aktuell:.2f}**\n\nDer Markt befindet sich im neutralen Bereich.")
            
        except Exception as e:
            st.error(f"Fehler beim Generieren der Live-Ansicht: {e}")

# ==============================================================================
# 4. HAUPTANSICHT: BRANCHEN- & MARKT-SCANNER
# ==============================================================================
st.title("🤖 KI-Markt- & Branchen-Scanner v2.5")
st.write("Massen-Live-Scan mit technischen Indikatoren und Pop-up-Finanzcockpit.")

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
# 5. DOWNLOAD & SCAN RUNNER
# ==============================================================================
if st.button("🚀 Scan Starten"):
    st.session_state.scan_results = []
    st.session_state.has_scanned = True
    
    with st.spinner("Hole aktuelle Aktienliste..."):
        try:
            if "S&P 500" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", 0)
                tickers = [t.replace('.', '-') for t in table['Symbol'].tolist()][:30] # Limit für Geschwindigkeit
            elif "NASDAQ-100" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/Nasdaq-100", 4)
                tickers = table['Ticker'].tolist()[:30]
            else:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/DAX", 4)
                tickers = table['Ticker'].tolist()
        except Exception as e:
            st.error(f"Fehler beim Laden des Index: {e}")
            tickers = []

    if tickers:
        st.info(f"Analysiere Live-Kursdaten für {len(tickers)} Aktien...")
        try:
            data = yf.download(tickers, period="3mo", interval="1d", group_by='ticker', progress=False)
            
            for ticker in tickers:
                df = data[ticker].dropna() if len(tickers) > 1 else data.copy()
                if df.empty or len(df) < 25: continue
                
                if "Alle Branchen" not in branche:
                    t_info = yf.Ticker(ticker).info
                    if t_info.get("sector", "") not in sektor_mapping.get(branche, []): continue

                df['RSI'] = calculate_rsi(df['Close'], period=14)
                df['MACD'], df['MACD_Signal'] = calculate_macd(df['Close'])
                
                last = df.iloc[-1]
                avg_vol = df['Volume'].tail(15).mean()
                
                if (rsi_min <= last['RSI'] <= rsi_max) and (last['MACD'] > last['MACD_Signal']) and (last['Volume'] > (avg_vol * vol_mult)):
                    prompt = f"Aktie {ticker}: RSI ist {last['RSI']:.1f}. Extrem kurze Trading-Einschätzung (max. 2 Sätze)."
                    ai_response = model.generate_content(prompt).text
                    
                    st.session_state.scan_results.append({
                        "ticker": ticker,
                        "rsi": f"{last['RSI']:.1f}",
                        "ai_text": ai_response
                    })
        except Exception as e:
            st.error(f"Fehler während der Analyse: {e}")

# ==============================================================================
# 6. ERGEBNIS-ANZEIGE
# ==============================================================================
if st.session_state.has_scanned:
    if st.session_state.scan_results:
        st.write(f"### 🎯 Gefundene Markt-Treffer ({len(st.session_state.scan_results)})")
        
        for idx, item in enumerate(st.session_state.scan_results):
            with st.container():
                st.success(f"🎯 Treffer: **{item['ticker']}** (RSI: {item['rsi']})")
                
                # Button öffnet das neue, hochgradig interaktive Pop-up
                if st.button(f"🔍 Interaktives Finanz-Cockpit öffnen für {item['ticker']}", key=f"btn_{item['ticker']}_{idx}"):
                    show_details_popup(item["ticker"])
                    
                st.info(f"**Gemini-Analyse:** {item['ai_text']}")
                st.divider()
        st.balloons()
    else:
        st.warning("Keine Titel erfüllen aktuell dieses Profil.")
