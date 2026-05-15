import streamlit as st
import yfinance as yf
import pandas as pd
import os
import urllib.request
import google.generativeai as genai
import plotly.graph_objects as gr  # Für die interaktiven Charts

# Gemini API konfigurieren
GOOGLE_API_KEY = os.environ.get("GEMINI_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    st.error("Bitte hinterlege den GEMINI_API_KEY in den Streamlit Secrets!")

# Mathematische Funktionen als Ersatz für pandas_ta
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

# Hilfsfunktion für Wikipedia (User-Agent gegen 403 Error)
def get_wikipedia_table(url, match_index=0):
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    )
    with urllib.request.urlopen(req) as response:
        html = response.read()
    tables = pd.read_html(html)
    return tables[match_index]

st.title("🤖 KI-Markt- & Branchen-Scanner")
st.write("Wähle Index und Branche. Der Agent filtert den Markt nach deiner RSI-MACD-Volumen-Strategie.")

# 1. Auswahl des Marktes
markt = st.selectbox(
    "1. Welchen Index möchtest du scannen?",
    (
        "S&P 500 (USA - Große Unternehmen)", 
        "NASDAQ 100 (USA - Technologie)", 
        "DAX (Deutschland)", 
        "FTSE 100 (Großbritannien)", 
        "All-World (Auswahl globaler Top-Unternehmen)"
    )
)

# 2. Auswahl der Branche
branche = st.selectbox(
    "2. Welche Branche möchtest du filtern?",
    (
        "Alle Branchen",
        "Technologie & Software",
        "Halbleiter (Semiconductors)",
        "Energie, Öl & Gas",
        "Rohstoffe & Bergbau",
        "Lebensmittel & Agrar",
        "Lifestyle, Luxus &amp; Konsum",
        "Finanzen & Banken",
        "Gesundheit & Pharma"
    )
)

sektor_mapping = {
    "Technologie & Software": ["Technology", "Communication Services"],
    "Halbleiter (Semiconductors)": ["Semiconductors"],
    "Energie, Öl & Gas": ["Energy"],
    "Rohstoffe & Bergbau": ["Basic Materials"],
    "Lebensmittel & Agrar": ["Consumer Defensive"],
    "Lifestyle, Luxus & Konsum": ["Consumer Cyclical"],
    "Finanzen & Banken": ["Financial Services"],
    "Gesundheit & Pharma": ["Healthcare"]
}

# 3. Der Start-Button
if st.button("🚀 Scan Starten"):
    
    with st.spinner("Hole aktuelle Aktienliste..."):
        try:
            if "S&P 500" in markt:
                url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
                table = get_wikipedia_table(url, 0)
                tickers = table['Symbol'].tolist()
                tickers = [t.replace('.', '-') for t in tickers]
            elif "NASDAQ 100" in markt:
                url = "https://en.wikipedia.org/wiki/Nasdaq-100"
                table = get_wikipedia_table(url, 4)
                tickers = table['Ticker'].tolist()
            elif "DAX" in markt:
                url = "https://en.wikipedia.org/wiki/DAX"
                table = get_wikipedia_table(url, 4)
                tickers = table['Ticker'].tolist()
            elif "FTSE 100" in markt:
                url = "https://en.wikipedia.org/wiki/FTSE_100_Index"
                table = get_wikipedia_table(url, 4)
                tickers = table['Ticker'].tolist()
                tickers = [t + ".L" for t in tickers]
            elif "All-World" in markt:
                tickers = [
                    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "LLY", "V", "MA",
                    "ASML", "MC.PA", "OR.PA", "SAP", "SIE.DE", "TTE", "NESN.SW", "NOVN.SW",
                    "7203.T", "6758.T", "9984.T", "BABA", "TCEHY"
                ]
        except Exception as e:
            st.error(f"Fehler beim Laden der Index-Liste: {e}")
            tickers = []

    if tickers:
        st.info(f"Basis-Index geladen. Analysiere und filtere Branchen...")
        progress_bar = st.progress(0)
        found_counter = 0
        filtered_tickers = []
        
        with st.spinner("Filtere nach Branche..."):
            for ticker in tickers:
                if branchen_filter := sektor_mapping.get(branche):
                    try:
                        t_info = yf.Ticker(ticker).info
                        t_sector = t_info.get("sector", "")
                        t_industry = t_info.get("industry", "")
                        
                        if branchen_filter == ["Semiconductors"]:
                            if "Semiconductor" in t_industry:
                                filtered_tickers.append(ticker)
                        elif t_sector in branchen_filter:
                            filtered_tickers.append(ticker)
                    except:
                        continue
                else:
                    filtered_tickers = tickers
                    break

        if not filtered_tickers:
            st.warning(f"Keine Aktien für die gewählte Kombination gefunden.")
        else:
            st.info(f"Starte technischen Scan für {len(filtered_tickers)} Aktien...")
            
            for index, ticker in enumerate(filtered_tickers):
                progress_bar.progress((index + 1) / len(filtered_tickers))
                
                try:
                    df = yf.download(ticker, period="3mo", interval="1d", progress=False)
                    if df.empty or len(df) < 30: continue
                    
                    df['RSI'] = calculate_rsi(df['Close'], period=14)
                    df['MACD'], df['MACD_Signal'] = calculate_macd(df['Close'])
                    
                    last = df.iloc[-1]
                    avg_vol = df['Volume'].tail(15).mean()
                    
                    rsi_ok = 55 <= last['RSI'] <= 65
                    macd_ok = last['MACD'] > last['MACD_Signal']
                    vol_ok = last['Volume'] > (avg_vol * 1.3)
                    
                    if rsi_ok and macd_ok and vol_ok:
                        found_counter += 1
                        st.success(f"🎯 Treffer #{found_counter} ({branche}): **{ticker}** erfüllt alle Kriterien!")
                        
                        # Gemini KI-Einschätzung
                        prompt = (f"Aktie {ticker} aus der Branche {branche}: "
                                  f"RSI ist {last['RSI']:.1f}, Volumen liegt bei {last['Volume']/avg_vol:.1f}x des Durchschnitts. "
                                  f"Gib eine extrem kurze, professionelle Trading-Einschätzung (max. 2 Sätze).")
                        
                        response = model.generate_content(prompt)
                        st.info(f"**Gemini-Analyse:** {response.text}")
                        
                        # NEU: Aufklappbares Fenster für die Charts
                        with st.expander(f"📊 Technische Charts für {ticker} anzeigen"):
                            
                            # 1. RSI Chart erzeugen
                            fig_rsi = gr.Figure()
                            fig_rsi.add_trace(gr.Scatter(x=df.index, y=df['RSI'], mode='lines', name='RSI (14)', line=dict(color='purple')))
                            # Hilfslinien für Strategie-Bereich (55 - 65) und Standard-Grenzen
                            fig_rsi.add_hline(y=65, line_dash="dash", line_color="green", annotation_text="Strategie Max (65)")
                            fig_rsi.add_hline(y=55, line_dash="dash", line_color="orange", annotation_text="Strategie Min (55)")
                            fig_rsi.add_hline(y=70, line_dash="dot", line_color="red", annotation_text="Overbought (70)")
                            fig_rsi.add_hline(y=30, line_dash="dot", line_color="blue", annotation_text="Oversold (30)")
                            fig_rsi.update_layout(title=f"RSI (Aktueller Wert: {last['RSI']:.1f})", yaxis=dict(range=[10, 90]), height=250, margin=dict(l=20, r=20, t=40, b=20))
                            st.plotly_chart(fig_rsi, use_container_width=True)
                            
                            # 2. MACD Chart erzeugen
                            fig_macd = gr.Figure()
                            fig_macd.add_trace(gr.Scatter(x=df.index, y=df['MACD'], mode='lines', name='MACD', line=dict(color='blue')))
                            fig_macd.add_trace(gr.Scatter(x=df.index, y=df['MACD_Signal'], mode='lines', name='Signal', line=dict(color='orange')))
                            # Histogramm (Differenz) zeichnen
                            df['Histogramm'] = df['MACD'] - df['MACD_Signal']
                            fig_macd.add_trace(gr.Bar(x=df.index, y=df['Histogramm'], name='Histogramm', marker_color='gray', opacity=0.4))
                            fig_macd.update_layout(title="MACD Indikator (Bullish Crossover)", height=250, margin=dict(l=20, r=20, t=40, b=20))
                            st.plotly_chart(fig_macd, use_container_width=True)
                        
                        st.divider()
                        
                except Exception:
                    continue
                    
            if found_counter == 0:
                st.warning("Muster-Scan beendet. Aktuell erfüllt keine Aktie dieses spezifische Profil.")
            else:
                st.balloons()
                st.success(f"Scan abgeschlossen! {found_counter} Setups gefunden.")
