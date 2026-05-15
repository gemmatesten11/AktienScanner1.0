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
# 2. MATHEMATISCHE HILFSFUNKTIONEN (ERSETZT PANDAS_TA)
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

# Hilfsfunktion für Wikipedia-Scraping (Browser-Tarnung)
def get_wikipedia_table(url, match_index=0):
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    )
    with urllib.request.urlopen(req) as response:
        html_text = response.read().decode('utf-8')
    
    html_file_like = StringIO(html_text)
    tables = pd.read_html(html_file_like)
    return tables[match_index]

# ==============================================================================
# 3. BENUTZEROBERFLÄCHE (STREAMLIT)
# ==============================================================================
st.title("🤖 KI-Markt- & Branchen-Scanner v2.1")
st.write("Wähle aus 20 globalen Indizes und filtere den Markt nach RSI-MACD-Volumen-Signalen.")

# Index-Auswahl
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

# Deine neue Branchen-Liste
branche = st.selectbox(
    "2. Welche Branche möchtest du filtern?",
    (
        "Alle Branchen",
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

# Mappt deine Bezeichnungen auf die offiziellen Sektoren von Yahoo Finance
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

# ==============================================================================
# 4. TICKER-DATA-MAPPING (DYNAMISCH ODER REPRÄSENTATIV)
# ==============================================================================
if st.button("🚀 Scan Starten"):
    
    with st.spinner("Hole aktuelle Aktienliste..."):
        try:
            # USA & Welt
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
                tickers = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "LLY", "V", "MA", "ASML", "SAP", "MC.PA", "NESN.SW", "NOVN.SW", "7203.T", "AZN.L", "SHEL.L", "BHP"]
            elif "NASDAQ Composite" in markt:
                tickers = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "AVGO", "COST", "NFLX", "AMD", "QCOM", "INTC", "PANW", "TXN", "ISRG", "AMGN", "HON"]
            elif "NYSE Composite" in markt:
                tickers = ["TSM", "V", "MA", "UNH", "XOM", "JNJ", "WMT", "PG", "JPM", "ORCL", "LLY", "HD", "BAC", "ABV", "KO", "PFE", "DIS", "NKE"]
            
            # Europa
            elif "EURO STOXX 50" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/Euro_Stoxx_50", 2)
                tickers = table['Ticker'].tolist()
            elif "FTSE 100" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/FTSE_100_Index", 4)
                tickers = [t.replace('.', '-') + ".L" for t in table['Ticker'].tolist()]
            elif "DAX 40" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/DAX", 4)
                tickers = table['Ticker'].tolist()
            elif "CAC 40" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/CAC_40", 4)
                tickers = [t + ".PA" for t in table['Ticker'].tolist()]
            elif "FTSE MIB" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/FTSE_MIB", 1)
                tickers = [t + ".MI" for t in table['Ticker'].tolist()]
            elif "IBEX 35" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/IBEX_35", 2)
                tickers = [t + ".MC" for t in table['Ticker'].tolist()]
            elif "SMI" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/Swiss_Market_Index", 3)
                tickers = [t + ".SW" for t in table['Ticker'].tolist()]
            elif "AEX-Index" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/AEX_Index", 2)
                tickers = [t + ".AS" for t in table['Ticker'].tolist()]
            
            # Asien & Pazifik
            elif "Nikkei 225" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/Nikkei_225", 1)
                tickers = [str(t) + ".T" for t in table['Ticker'].tolist()]
            elif "Shanghai Composite" in markt:
                tickers = ["601398.SS", "601857.SS", "601288.SS", "601988.SS", "600519.SS", "600036.SS", "601318.SS", "601628.SS", "600019.SS", "601088.SS"]
            elif "Hang Seng" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/Hang_Seng_Index", 6)
                tickers = [t.strip().zfill(4) + ".HK" for t in table['Ticker'].tolist() if t]
            elif "NIFTY 50" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/NIFTY_50", 2)
                tickers = [t + ".NS" for t in table['Symbol'].tolist()]
            elif "TOPIX" in markt:
                tickers = ["7203.T", "6758.T", "9984.T", "8306.T", "6861.T", "4502.T", "8031.T", "6501.T", "4063.T", "6954.T"]
            elif "S&P/ASX 200" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/S%26P/ASX_200", 2)
                tickers = [t + ".AX" for t in table['Code'].tolist()]
                
        except Exception as e:
            st.error(f"Fehler beim Auflösen der Index-Liste: {e}")
            tickers = []

    # ==============================================================================
    # 5. BRANCHENFILTER & ANALYSE
    # ==============================================================================
    if tickers:
        st.info(f"Index geladen ({len(tickers)} Aktien im Pool). Filtere nach Sektoren...")
        progress_bar = st.progress(0)
        found_counter = 0
        filtered_tickers = []
        
        with st.spinner("Prüfe Branchenzugehörigkeit..."):
            for ticker in tickers:
                if branchen_filter := sektor_mapping.get(branche):
                    try:
                        t_info = yf.Ticker(ticker).info
                        t_sector = t_info.get("sector", "")
                        
                        if t_sector in branchen_filter:
                            filtered_tickers.append(ticker)
                    except:
                        continue
                else:
                    filtered_tickers = tickers
                    break

        if not filtered_tickers:
            st.warning("Keine Aktien für diese Kombination gefunden.")
        else:
            st.info(f"Starte technischen Live-Scan für {len(filtered_tickers)} Werte...")
            
            for index, ticker in enumerate(filtered_tickers):
                progress_bar.progress((index + 1) / len(filtered_tickers))
                
                try:
                    df = yf.download(ticker, period="3mo", interval="1d", progress=False)
                    if df.empty or len(df) < 30: 
                        continue
                    
                    df['RSI'] = calculate_rsi(df['Close'], period=14)
                    df['MACD'], df['MACD_Signal'] = calculate_macd(df['Close'])
                    
                    last = df.iloc[-1]
                    avg_vol = df['Volume'].tail(15).mean()
                    
                    # Deine Strategie-Kriterien
                    rsi_ok = 55 <= last['RSI'] <= 65
                    macd_ok = last['MACD'] > last['MACD_Signal']
                    vol_ok = last['Volume'] > (avg_vol * 1.3)
                    
                    if rsi_ok and macd_ok and vol_ok:
                        found_counter += 1
                        st.success(f"🎯 Treffer #{found_counter} ({branche}): **{ticker}**")
                        
                        # Gemini Prompt & Auswertung
                        prompt =
