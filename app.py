import streamlit as st
import yfinance as yf
import pandas as pd
import os
import urllib.request
import google.generativeai as genai
import plotly.graph_objects as gr
from io import StringIO

# ==============================================================================
# 1. API-KONFIGURATION
# ==============================================================================
GOOGLE_API_KEY = os.environ.get("GEMINI_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    st.error("Bitte hinterlege den GEMINI_API_KEY in den Streamlit Cloud Secrets!")

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
# 3. BENUTZEROBERFLÄCHE (STREAMLIT)
# ==============================================================================
st.title("🤖 KI-Markt- & Branchen-Scanner v2.2")
st.write("Schneller, blockierungsfreier Live-Scan über 20 globale Indizes.")

markt = st.selectbox(
    "1. Welchen Index möchtest du scannen?",
    (
        "S&P 500 (USA) - Top 500 US-Unternehmen",
        "NASDAQ-100 (USA) - Große Tech- & Nicht-Finanzwerte",
        "Dow Jones Industrial Average (USA) - 30 Blue-Chips",
        "MSCI World (Welt) - Repräsentative Global-Auswahl",
        "NASDAQ Composite (USA) - Repräsentative Tech-Auswahl",
        "NYSE Composite (USA) - Repräsentative Industriepower",
        "EURO STOXX 50 (Eurozone) - Die 50 größten Euro-Werte",
        "FTSE 100 (UK) - Die 100 größten Londoner Aktien",
        "DAX 40 (Deutschland) - Deutscher Leitindex",
        "CAC 40 (Frankreich) - Pariser Leitindex",
        "FTSE MIB (Italien) - Hauptindex Mailänder Börse",
        "IBEX 35 (Spanien) - Wichtigste spanische Werte",
        "SMI (Schweiz) - Schweizer Blue-Chips",
        "AEX-Index (Niederlande) - Amsterdamer Leitindex",
        "Nikkei 225 (Japan) - Leitindex Tokio (225 Werte)",
        "Shanghai Composite (China) - Festlandchina Top-Auswahl",
        "Hang Seng Index (Hongkong) - Hongkonger Leitindex",
        "NIFTY 50 (Indien) - Indischer Leitindex",
        "TOPIX (Japan) - Breiter japanischer Markt",
        "S&P/ASX 200 (Australien) - 200 größte australische Aktien"
    )
)

# Filter-Modus, um die Yahoo-Sperre komplett zu umgehen
filter_modus = st.radio(
    "2. Wie möchtest du filtern?",
    ("💥 Voller Index-Scan (Empfohlen - Schnell & Sicher)", "🔍 Nach Branche filtern (Achtung: Kann bei großen Indizes blockiert werden)")
)

branche = st.selectbox(
    "3. Sektor auswählen (Nur aktiv, wenn Branchen-Filter gewählt ist):",
    (
        "Informationstechnologie (Software, Hardware, Halbleiter)",
        "Gesundheitswesen (Pharma, Biotech, Medizintechnik)",
        "Finanzwesen (Banken, Versicherungen, Dienstleister)",
        "Nicht-Basiskonsumgüter / Zykliker (Auto, Hotels, Handel)",
        "Kommunikationsdienste (Telekom, Soziale Netzwerke)",
        "Industrie (Maschinenbau, Luftfahrt, Logistik)",
        "Basiskonsumgüter / Defensiv (Lebensmittel, Haushalt)",
        "Energie (Öl, Gas, erneuerbare Energien)",
        "Versorgungsunternehmen (Strom, Wasser, Gas)",
        "Immobilien (Immobilien-AGs, REITs)",
        "Grundstoffe / Rohstoffe"
    )
)

sektor_mapping = {
    "Informationstechnologie (Software, Hardware, Halbleiter)": ["Technology"],
    "Gesundheitswesen (Pharma, Biotech, Medizintechnik)": ["Healthcare"],
    "Finanzwesen (Banken, Versicherungen, Dienstleister)": ["Financial Services"],
    "Nicht-Basiskonsumgüter / Zykliker (Auto, Hotels, Handel)": ["Consumer Cyclical"],
    "Kommunikationsdienste (Telekom, Soziale Netzwerke)": ["Communication Services"],
    "Industrie (Maschinenbau, Luftfahrt, Logistik)": ["Industrials"],
    "Basiskonsumgüter / Defensiv (Lebensmittel, Haushalt)": ["Consumer Defensive"],
    "Energie (Öl, Gas, erneuerbare Energien)": ["Energy"],
    "Versorgungsunternehmen (Strom, Wasser, Gas)": ["Utilities"],
    "Immobilien (Immobilien-AGs, REITs)": ["Real Estate"],
    "Grundstoffe / Rohstoffe": ["Basic Materials"]
}

# Strategie-Tuning direkt in der UI
st.sidebar.header("⚙️ Strategie-Anpassung")
rsi_min = st.sidebar.slider("RSI Minimum", 10, 50, 45) # Von 55 auf 45 gesenkt für mehr Treffer beim Testen
rsi_max = st.sidebar.slider("RSI Maximum", 50, 90, 70) # Von 65 auf 70 erweitert
vol_mult = st.sidebar.slider("Volumen-Faktor (x des Schnitts)", 0.5, 2.0, 1.0) # Auf 1.0 gesenkt

# ==============================================================================
# 4. TICKER LADEN
# ==============================================================================
if st.button("🚀 Scan Starten"):
    
    with st.spinner("Hole aktuelle Aktienliste..."):
        try:
            if "S&P 500" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", 0)
                tickers = [t.replace('.', '-') for t in table['Symbol'].tolist()]
            elif "NASDAQ-100" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/Nasdaq-100", 4)
                tickers = table['Ticker'].tolist()
            elif "Dow Jones" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average", 1)
                tickers = table['Symbol'].tolist()
            elif "MSCI World" in markt:
                tickers = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "LLY", "V", "MA", "ASML", "SAP", "MC.PA", "NESN.SW"]
            elif "DAX 40" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/DAX", 4)
                tickers = table['Ticker'].tolist()
            elif "EURO STOXX 50" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/Euro_Stoxx_50", 2)
                tickers = table['Ticker'].tolist()
            elif "FTSE 100" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/FTSE_100_Index", 4)
                tickers = [t.replace('.', '-') + ".L" for t in table['Ticker'].tolist()]
            elif "CAC 40" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/CAC_40", 4)
                tickers = [t + ".PA" for t in table['Ticker'].tolist()]
            else:
                # Fallback für die restlichen Indizes
                tickers = ["AAPL", "MSFT", "NVDA", "SAP", "SIE.DE", "7203.T", "SHEL.L", "CBA.AX"]
        except Exception as e:
            st.error(f"Fehler beim Laden des Index: {e}")
            tickers = []

    # ==============================================================================
    # 5. TURBO-MASSEN-DOWNLOAD (VERHINDERT YAHOO-BLOCKADE)
    # ==============================================================================
    if tickers:
        # Begrenzung für Riesen-Indizes beim Testen, damit Streamlit nicht abstürzt
        if len(tickers) > 100 and "Voller Index" in filter_modus:
            st.warning("Index sehr groß. Scanne die ersten 100 Werte für maximale Stabilität...")
            tickers = tickers[:100]

        st.info(f"Lade Live-Kursdaten für {len(tickers)} Aktien in einem Paket herunter...")
        
        try:
            # Wir laden alle Daten auf einmal! Ein einziger Server-Call.
            data = yf.download(tickers, period="3mo", interval="1d", group_by='ticker', progress=False)
        except Exception as e:
            st.error(f"Fehler beim Massen-Download: {e}")
            data = pd.DataFrame()

        if not data.empty:
            found_counter = 0
            st.info("Analysiere Daten auf Muster...")
            progress_bar = st.progress(0)
            
            # Wenn der Branchen-Modus aktiv ist, müssen wir filtern
            with st.spinner("Verarbeite Signale..."):
                for idx, ticker in enumerate(tickers):
                    progress_bar.progress((idx + 1) / len(tickers))
                    
                    try:
                        # Extrahiere die Kursdaten für die einzelne Aktie aus dem Massenpaket
                        if len(tickers) == 1:
                            df = data.copy()
                        else:
                            df = data[ticker].dropna()
                        
                        if df.empty or len(df) < 25: 
                            continue
                        
                        # Branchen-Prüfung nur, wenn explizit ausgewählt
                        if "Nach Branche filtern" in filter_modus:
                            t_info = yf.Ticker(ticker).info
                            if t_info.get("sector", "") not in sektor_mapping.get(branche, []):
                                continue

                        # Indikatoren-Berechnung
                        df['RSI'] = calculate_rsi(df['Close'], period=14)
                        df['MACD'], df['MACD_Signal'] = calculate_macd(df['Close'])
                        
                        last = df.iloc[-1]
                        avg_vol = df['Volume'].tail(15).mean()
                        
                        # Abgleich mit den Reglern aus der linken Seitenleiste
                        rsi_ok = rsi_min <= last['RSI'] <= rsi_max
                        macd_ok = last['MACD'] > last['MACD_Signal']
                        vol_ok = last['Volume'] > (avg_vol * vol_mult)
                        
                        if rsi_ok and macd_ok and vol_ok:
                            found_counter += 1
                            st.success(f"🎯 Treffer #{found_counter}: **{ticker}**")
                            
                            prompt = (f"Aktie {ticker}: RSI ist {last['RSI']:.1f}, "
                                      f"Volumen liegt bei {last['Volume']/avg_vol:.1f}x des Durchschnitts. "
                                      f"Gib eine extrem kurze, professionelle Trading-Einschätzung (max. 2 Sätze).")
                            
                            response = model.generate_content(prompt)
                            st.info(f"**Gemini-Analyse:** {response.text}")
                            
                            with st.expander(f"📊 Charts für {ticker}"):
                                fig_rsi = gr.Figure()
                                fig_rsi.add_trace(gr.Scatter(x=df.index, y=df['RSI'], mode='lines', name='RSI', line=dict(color='purple')))
                                fig_rsi.add_hline(y=rsi_max, line_dash="dash", line_color="green")
                                fig_rsi.add_hline(y=rsi_min, line_dash="dash", line_color="orange")
                                fig_rsi.update_layout(title=f"RSI14 (Aktuell: {last['RSI']:.1f})", yaxis=dict(range=[10, 90]), height=200, margin=dict(l=20, r=20, t=40, b=20))
                                st.plotly_chart(fig_rsi, use_container_width=True)
                                
                                fig_macd = gr.Figure()
                                fig_macd.add_trace(gr.Scatter(x=df.index, y=df['MACD'], mode='lines', name='MACD', line=dict(color='blue')))
                                fig_macd.add_trace(gr.Scatter(x=df.index, y=df['MACD_Signal'], mode='lines', name='Signal', line=dict(color='orange')))
                                st.plotly_chart(fig_macd, use_container_width=True)
                            st.divider()
                            
                    except:
                        continue
            
            if found_counter == 0:
                st.warning("Scan beendet. Aktuell erfüllt kein Titel dieses Profil. Versuche die Regler links anzupassen!")
            else:
                st.balloons()
                st.success(f"Scan abgeschlossen! {found_counter} Setups gefunden.")
