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
    
    intervall_auswahl = st.radio(
        "⏱️ Chart-Zeiteinheit auswählen:",
        options=["30 Min", "1 Std", "4 Std"],
        horizontal=True
    )
    
    mapping = {
        "30 Min": {"interval": "30m", "period": "1mo"},
        "1 Std": {"interval": "60m", "period": "2mo"},
        "4 Std": {"interval": "1h", "period": "3mo"}
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
                
            df['RSI'] = calculate_rsi(df['Close'], period=14)
            df['MACD'], df['MACD_Signal'] = calculate_macd(df['Close'])
            df['SMA200'] = df['Close'].rolling(window=200).mean()
            
            last = df.iloc[-1]
            rsi_aktuell = last['RSI']
            
            # 1. KURS-LINIENCHART MIT SMA200 & MACD
            st.subheader("📈 Hauptchart (Kurs, SMA200 & MACD)")
            fig_main = make_subplots(specs=[[{"secondary_y": True}]])
            
            fig_main.add_trace(
                gr.Scatter(x=df.index, y=df['Close'], mode='lines', name='Kurs (Schluss)', line=dict(color='blue', width=2)),
                secondary_y=False
            )
            fig_main.add_trace(
                gr.Scatter(x=df.index, y=df['SMA200'], mode='lines', name='SMA 200', line=dict(color='red', width=1.5, dash='dash')),
                secondary_y=False
            )
            fig_main.add_trace(
                gr.Scatter(x=df.index, y=df['MACD'], mode='lines', name='MACD Linie', line=dict(color='orange', width=1)),
                secondary_y=True
            )
            fig_main.add_trace(
                gr.Scatter(x=df.index, y=df['MACD_Signal'], mode='lines', name='MACD Signal', line=dict(color='gray', width=1, dash='dot')),
                secondary_y=True
            )
            
            fig_main.update_layout(
                height=400, xaxis_rangeslider_visible=False,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(l=10, r=10, t=10, b=10)
            )
            fig_main.update_yaxes(title_text="Kurs", secondary_y=False)
            fig_main.update_yaxes(title_text="MACD Wert", secondary_y=True, showgrid=False)
            st.plotly_chart(fig_main, use_container_width=True)
            
            # 2. VOLUMEN-CHART
            st.subheader("📊 Handelsvolumen")
            fig_vol = gr.Figure()
            fig_vol.add_trace(gr.Bar(x=df.index, y=df['Volume'], name='Volumen', marker_color='teal', opacity=0.7))
            fig_vol.update_layout(height=150, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig_vol, use_container_width=True)
            
            st.divider()
            
            # 3. RSI ANSICHT & INFOBOX
            st.subheader("⏱️ RSI (Letzte 14 Perioden)")
            col_chart, col_info = st.columns([2, 1])
            df_rsi_last14 = df.tail(14)
            
            with col_chart:
                fig_rsi = gr.Figure()
                fig_rsi.add_trace(gr.Scatter(x=df_rsi_last14.index, y=df_rsi_last14['RSI'], mode='lines+markers', name='RSI14', line=dict(color='purple', width=2)))
                fig_rsi.add_hline(y=70, line_dash="dash", line_color="red")
                fig_rsi.add_hline(y=30, line_dash="dash", line_color="green")
                fig_rsi.update_layout(height=200, yaxis=dict(range=[10, 90]), margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig_rsi, use_container_width=True)
                
            with col_info:
                st.write("###") 
                if rsi_aktuell > 70:
                    st.error(f"⚠️ **RSI14 Wert: {rsi_aktuell:.2f}**\n\nDer Markt ist aktuell überkauft.")
                elif rsi_aktuell < 30:
                    st.success(f"✅ **RSI14 Wert: {rsi_aktuell:.2f}**\n\nDer Markt ist aktuell überverkauft.")
                else:
                    st.info(f"ℹ️ **RSI14 Wert: {rsi_aktuell:.2f}**\n\nDer Markt befindet sich im neutralen Bereich.")
            
        except Exception as e:
            st.error(f"Fehler beim Generieren der Live-Ansicht: {e}")

# ==============================================================================
# 4. HAUPTANSICHT: BRANCHEN- & MARKT-SCANNER
# ==============================================================================
st.title("🤖 KI-Markt- & Branchen-Scanner v3.0")
st.write("Massen-Live-Scan mit globaler Marktabdeckung und flexiblen Index-Klassen.")

# 1. Erweiterte Indizes der Welt
markt = st.selectbox(
    "1. Welchen Markt / Index möchtest du scannen?",
    (
        "USA (S&P Universum / NASDAQ)",
        "Deutschland (DAX / MDAX / SDAX)",
        "Eurozone (EURO STOXX 50)",
        "Großbritannien (FTSE 100)",
        "Frankreich (CAC 40)",
        "Japan (Nikkei 225)",
        "Hongkong (Hang Seng Index)",
        "MSCI World (Globale Blue-Chips-Auswahl)"
    )
)

# 2. Dropdown für Marktkapitalisierung (Caps)
cap_groesse = st.selectbox(
    "2. Welche Unternehmensgröße (Marktkapitalisierung)?",
    ("Large Caps (Großkonzerne)", "Mid Caps (Mittelstand)", "Small Caps (Nebenwerte)")
)

# 3. Branchen-Filter
branche = st.selectbox(
    "3. Welche Branche möchtest du filtern?",
    (
        "Alle Branchen",
        "Grundindustrie (Rohstoffe, Bauwesen, Bergbau, Metalle, Öl & Gas, Chemie)",
        "Industriegüter & Dienstleistungen (Maschinen, Transport, Elektro, Luftfahrt)",
        "Konsumgüter (Automobil, Lebensmittel, Getränke, Haushaltsartikel)",
        "Verbraucherdienste (Medien, Tourismus, Einzelhandel, Freizeit)",
        "Gesundheitswesen (Pharma, Biotechnologie, med. Geräte)",
        "Versorger (Energie- und Versorgungssektor)",
        "Finanzwesen (Banken und Finanzdienstleister)",
        "Versicherungen",
        "Immobilien (Immobilieninvestmentgesellschaften, REITs)",
        "Technologie"
    )
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

# ==============================================================================
# 5. DYNAMISCHES TICKER-ROUTING (INDEX & CAP MAPPING)
# ==============================================================================
if st.button("🚀 Scan Starten"):
    st.session_state.scan_results = []
    st.session_state.has_scanned = True
    
    with st.spinner("Hole aktuelle Ticker-Liste aus globalen Indizes..."):
        try:
            tickers = []
            # USA Routing
            if "USA" in markt:
                if "Large" in cap_groesse:
                    table = get_wikipedia_table("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", 0)
                    tickers = [t.replace('.', '-') for t in table['Symbol'].tolist()]
                elif "Mid" in cap_groesse:
                    table = get_wikipedia_table("https://en.wikipedia.org/wiki/List_of_S%26P_400_companies", 0)
                    tickers = [t.replace('.', '-') for t in table['Ticker symbol'].tolist()]
                else:
                    table = get_wikipedia_table("https://en.wikipedia.org/wiki/List_of_S%26P_600_companies", 1)
                    tickers = [t.replace('.', '-') for t in table['Ticker symbol'].tolist()]
            
            # Deutschland Routing
            elif "Deutschland" in markt:
                if "Large" in cap_groesse:
                    table = get_wikipedia_table("https://en.wikipedia.org/wiki/DAX", 4)
                    tickers = table['Ticker'].tolist()
                elif "Mid" in cap_groesse:
                    table = get_wikipedia_table("https://en.wikipedia.org/wiki/MDAX", 3)
                    tickers = [t + ".DE" for t in table['Ticker'].tolist()]
                else:
                    table = get_wikipedia_table("https://en.wikipedia.org/wiki/SDAX", 3)
                    tickers = [t + ".DE" for t in table['Ticker'].tolist()]
            
            # Internationale Märkte
            elif "Eurozone" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/Euro_Stoxx_50", 2)
                tickers = table['Ticker'].tolist()
            elif "Großbritannien" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/FTSE_100_Index", 4)
                tickers = [t.replace('.', '-') + ".L" for t in table['Ticker'].tolist()]
            elif "Frankreich" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/CAC_40", 4)
                tickers = [t + ".PA" for t in table['Ticker'].tolist()]
            elif "Japan" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/Nikkei_225", 2)
                tickers = [str(t) + ".T" for t in table['Ticker'].tolist()]
            elif "Hongkong" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/Hang_Seng_Index", 6)
                tickers = [str(t).zfill(4) + ".HK" for t in table['Ticker'].tolist()]
            elif "MSCI World" in markt:
                tickers = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "LLY", "V", "MA", "ASML", "SAP", "MC.PA", "NESN.SW", "NOVN.SW", "AZN.L"]

            # Generelles Abfangen nicht gepflegter Mid/Small-Kombinationen im Ausland
            if not tickers:
                st.warning(f"Für {markt} im Bereich {cap_groesse} wird auf Large-Caps ausgewichen.")
                tickers = ["AAPL", "MSFT", "NVDA", "SAP", "SIE.DE"]

        except Exception as e:
            st.error(f"Fehler beim Abrufen der Indexliste: {e}")
            tickers = []

    # ==============================================================================
    # 6. DOWNLOAD & DATA ANALYSIS (OHNE VOLUMEN)
    # ==============================================================================
    if tickers:
        if len(tickers) > 40:
            st.warning("Index/Segment sehr groß. Scanne die ersten 40 Werte für optimale Performance...")
            tickers = tickers[:40]

        st.info(f"Analysiere technische Daten für {len(tickers)} Wertpapiere...")
        try:
            data = yf.download(tickers, period="4mo", interval="1d", group_by='ticker', progress=False)
            
            for ticker in tickers:
                df = data[ticker].dropna() if len(tickers) > 1 else data.copy()
                if df.empty or len(df) < 30: continue
                
                # Sektorenfilter
                if "Alle Branchen" not in branche:
                    t_info = yf.Ticker(ticker).info
                    t_sector = t_info.get("sector", "")
                    t_industry = t_info.get("industry", "")
                    
                    if branche == "Versicherungen":
                        if "Insurance" not in t_industry: continue
                    elif "Finanzwesen" in branche:
                        if "Insurance" in t_industry or t_sector != "Financial Services": continue
                    elif t_sector not in sektor_mapping.get(branche, []):
                        continue

                df['RSI'] = calculate_rsi(df['Close'], period=14)
                df['MACD'], df['MACD_Signal'] = calculate_macd(df['Close'])
                
                last = df.iloc[-1]
                
                rsi_ok = rsi_min <= last['RSI'] <= rsi_max
                macd_ok = last['MACD'] > last['MACD_Signal'] # Bullish Momentum Cross
                
                if rsi_ok and macd_ok:
                    prompt = f"Aktie {ticker}: RSI ist {last['RSI']:.1f}. Gib eine extrem kurze, professionelle Trading-Einschätzung ab (max. 2 Sätze)."
                    ai_response = model.generate_content(prompt).text
                    
                    st.session_state.scan_results.append({
                        "ticker": ticker,
                        "rsi": f"{last['RSI']:.1f}",
                        "ai_text": ai_response
                    })
        except Exception as e:
            st.error(f"Fehler während der Datenanalyse: {e}")

# ==============================================================================
# 7. ERGEBNIS-ANZEIGE
# ==============================================================================
if st.session_state.has_scanned:
    if st.session_state.scan_results:
        st.write(f"### 🎯 Gefundene Markt-Treffer ({len(st.session_state.scan_results)})")
        
        for idx, item in enumerate(st.session_state.scan_results):
            with st.container():
                st.success(f"🎯 Treffer: **{item['ticker']}** (RSI: {item['rsi']})")
                
                if st.button(f"🔍 Interaktives Finanz-Cockpit öffnen für {item['ticker']}", key=f"btn_{item['ticker']}_{idx}"):
                    show_details_popup(item["ticker"])
                    
                st.info(f"**Gemini-Analyse:** {item['ai_text']}")
                st.divider()
        st.balloons()
    else:
        st.warning("Keine Titel erfüllen aktuell dieses Profil. Passe den RSI-Filter an oder wähle ein anderes Marktsegment.")
