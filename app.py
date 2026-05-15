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
# 3. POP-UP DETAILANSICHT (FINANZ-COCKPIT) VIA st.dialog
# ==============================================================================
@st.dialog("📊 Finanz-Cockpit & Details", width="large")
def show_details_popup(ticker):
    st.subheader(f"Detailanalyse für das Kürzel: {ticker}")
    st.divider()
    
    with st.spinner(f"Lade tiefgehende Finanzdetails für {ticker}..."):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            df = stock.history(period="6mo", interval="1d")
            
            df['RSI'] = calculate_rsi(df['Close'], period=14)
            df['MACD'], df['MACD_Signal'] = calculate_macd(df['Close'])
            last = df.iloc[-1]
            
            # Stammdaten abrufen
            isin = info.get("isin", "Nicht verfügbar")
            wkn = info.get("wkn", "Siehe ISIN") 
            name = info.get("longName", ticker)
            
            # Spalten-Layout für Stammdaten im Pop-up
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Unternehmen", name)
            col2.metric("Ticker", ticker)
            col3.metric("ISIN", isin)
            col4.metric("WKN / WSN", wkn)
            
            st.divider()
            
            # RECHNERISCHE AMPEL-LOGIK
            st.subheader("🚦 Technische Live-Ampel")
            rsi_val = last['RSI']
            macd_trend = last['MACD'] > last['MACD_Signal']
            
            if rsi_val < 35 and macd_trend:
                ampel_status = "KAUFEN (Stark überverkauft + Bullish Cross)"
                ampel_color = "🟢"
            elif 35 <= rsi_val <= 65 and macd_trend:
                ampel_status = "KAUFEN / AKKUMULIEREN (Gesunder Trend)"
                ampel_color = "🟢"
            elif rsi_val > 70:
                ampel_status = "VERKAUFEN (Stark überhitzt / Überkauft)"
                ampel_color = "🔴"
            else:
                ampel_status = "HALTEN (Neutraler Marktzustand)"
                ampel_color = "🟡"
                
            st.info(f"**Empfehlung auf Basis der mathematischen Indikatoren:** {ampel_color} {ampel_status}")
            st.divider()
            
            # CHARTS GENERIEREN
            st.subheader("📈 Technische Analyse & Charts")
            
            # 1. Live Candle Chart
            fig_chart = gr.Figure()
            fig_chart.add_trace(gr.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Kurs"))
            fig_chart.update_layout(title="Live Candlestick Chart (6 Monate)", xaxis_rangeslider_visible=False, height=300, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_chart, use_container_width=True)
            
            # 2. RSI Chart
            fig_rsi = gr.Figure()
            fig_rsi.add_trace(gr.Scatter(x=df.index, y=df['RSI'], mode='lines', name='RSI', line=dict(color='purple')))
            fig_rsi.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="Überkauft")
            fig_rsi.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="Überverkauft")
            fig_rsi.update_layout(title=f"RSI14 Indikator (Aktuell: {rsi_val:.1f})", yaxis=dict(range=[10, 90]), height=200, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_rsi, use_container_width=True)
            
            # 3. MACD Chart
            fig_macd = gr.Figure()
            fig_macd.add_trace(gr.Scatter(x=df.index, y=df['MACD'], mode='lines', name='MACD', line=dict(color='blue')))
            fig_macd.add_trace(gr.Scatter(x=df.index, y=df['MACD_Signal'], mode='lines', name='Signal', line=dict(color='orange')))
            df['Histo'] = df['MACD'] - df['MACD_Signal']
            fig_macd.add_trace(gr.Bar(x=df.index, y=df['Histo'], name='Histogramm', opacity=0.3))
            fig_macd.update_layout(title="MACD Momentum", height=200, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_macd, use_container_width=True)
            
            st.divider()
            
            # ANALYSTEN TABELLE
            st.subheader("👥 Analysten-Konsensus & Ratings")
            target_high = info.get("targetHighPrice", "N/A")
            target_low = info.get("targetLowPrice", "N/A")
            target_mean = info.get("targetMeanPrice", "N/A")
            current_price = info.get("currentPrice", last['Close'])
            recommendation = info.get("recommendationKey", "N/A").upper()
            
            analysten_data = {
                "Metrik": ["Aktueller Kurs", "Analysten-Ziel (Schnitt)", "Höchstes Kursziel", "Niedrigstes Kursziel", "Gesamturteil"],
                "Wert": [f"{current_price} USD", f"{target_mean} USD", f"{target_high} USD", f"{target_low} USD", recommendation]
            }
            analysten_df = pd.DataFrame(analysten_data)
            st.table(analysten_df)
            
        except Exception as e:
            st.error(f"Fehler beim Laden der Finanzdetails: {e}")

# ==============================================================================
# 4. HAUPTANSICHT: BRANCHEN- & MARKT-SCANNER
# ==============================================================================
st.title("🤖 KI-Markt- & Branchen-Scanner v2.5")
st.write("Massen-Live-Scan mit Candlestick-Charts, RSI, MACD und KI-Analyse.")

markt = st.selectbox(
    "1. Welchen Index möchtest du scannen?",
    (
        "S&P 500 (USA) - Top 500 US-Unternehmen",
        "NASDAQ-100 (USA) - Große Tech- & Nicht-Finanzwerte",
        "Dow Jones Industrial Average (USA) - 30 Blue-Chips",
        "MSCI World (Welt) - Repräsentative Global-Auswahl",
        "DAX 40 (Deutschland) - Deutscher Leitindex",
        "EURO STOXX 50 (Eurozone) - Die 50 größten Euro-Werte",
        "FTSE 100 (UK) - Die 100 größten Londoner Aktien",
        "CAC 40 (Frankreich) - Pariser Leitindex"
    )
)

branche = st.selectbox(
    "2. Welche Branche möchtest du filtern?",
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
vol_mult = st.sidebar.slider("Volumen-Faktor (x des Schnitts)", 0.5, 2.0, 1.0)

# ==============================================================================
# 5. DOWNLOAD & SCAN RUNNER
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
            else:
                tickers = ["AAPL", "MSFT", "NVDA", "SAP"]
        except Exception as e:
            st.error(f"Fehler beim Laden des Index: {e}")
            tickers = []

    if tickers:
        if len(tickers) > 100:
            st.warning("Index sehr groß. Scanne die ersten 100 Werte für maximale Geschwindigkeit...")
            tickers = tickers[:100]

        st.info(f"Lade Live-Kursdaten für {len(tickers)} Aktien herunter...")
        
        try:
            data = yf.download(tickers, period="3mo", interval="1d", group_by='ticker', progress=False)
        except Exception as e:
            st.error(f"Fehler beim Massen-Download: {e}")
            data = pd.DataFrame()

        if not data.empty:
            found_counter = 0
            progress_bar = st.progress(0)
            
            for idx, ticker in enumerate(tickers):
                progress_bar.progress((idx + 1) / len(tickers))
                
                try:
                    if len(tickers) == 1:
                        df = data.copy()
                    else:
                        df = data[ticker].dropna()
                    
                    if df.empty or len(df) < 25: 
                        continue
                    
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
                    avg_vol = df['Volume'].tail(15).mean()
                    
                    rsi_ok = rsi_min <= last['RSI'] <= rsi_max
                    macd_ok = last['MACD'] > last['MACD_Signal']
                    vol_ok = last['Volume'] > (avg_vol * vol_mult)
                    
                    if rsi_ok and macd_ok and vol_ok:
                        found_counter += 1
                        
                        with st.container():
                            st.success(f"🎯 Treffer #{found_counter}: **{ticker}**")
                            
                            # DIREKTER AUFRUF DES POP-UPS BEI KLICK
                            # Nutzt st.dialog. Das Pop-up öffnet sich über der App, ohne den Zustand der App zu löschen.
                            if st.button(f"🔍 Vollständige Finanzdetails für {ticker} anzeigen", key=f"btn_{ticker}"):
                                show_details_popup(ticker)
                                
                            prompt = f"""
                            Aktie {ticker}: RSI ist {last['RSI']:.1f}, 
                            Volumen liegt bei {last['Volume']/avg_vol:.1f}x des Durchschnitts. 
                            Gib eine extrem kurze, professionelle Trading-Einschätzung (max. 2 Sätze).
                            """
                            response = model.generate_content(prompt)
                            st.info(f"**Gemini-Analyse:** {response.text}")
                            st.divider()
                                
                except:
                    continue
            
            if found_counter == 0:
                st.warning("Scan beendet. Aktuell erfüllt kein Titel dieses Profil.")
            else:
                st.balloons()
