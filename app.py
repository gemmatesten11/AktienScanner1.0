import streamlit as st
import yfinance as yf
import pandas as pd
import urllib.request
from io import StringIO
import plotly.graph_objects as gr

# Streamlit Page Config
st.set_page_config(layout="wide", page_title="Schneller RSI-Scanner", page_icon="⚡")

# ==============================================================================
# 1. HILFSFUNKTIONEN & INITIALISIERUNG
# ==============================================================================
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
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
# 2. SEITENLEISTE (RSI SCHIEBEREGLER)
# ==============================================================================
st.sidebar.header("⚡ RSI-Filter")
rsi_min = st.sidebar.slider("Minimaler RSI-Wert", 0, 100, 20, step=1)
rsi_max = st.sidebar.slider("Maximaler RSI-Wert", 0, 100, 40, step=1)

# ==============================================================================
# 3. SCHNELLES POP-UP (NUR REINER RSI VERLAUF)
# ==============================================================================
@st.dialog("📊 RSI Detail-Verlauf", width="large")
def show_details_popup(ticker):
    st.write(f"### Letzte 30 Handelstage für: **{ticker}**")
    with st.spinner("Lade Chart..."):
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="3mo", interval="1d")
            df['RSI'] = calculate_rsi(df['Close'], period=14)
            df_last30 = df.tail(30)
            
            # RSI Chart
            fig = gr.Figure()
            fig.add_trace(gr.Scatter(x=df_last30.index, y=df_last30['RSI'], mode='lines+markers', name='RSI14', line=dict(color='purple', width=2)))
            fig.add_hline(y=70, line_dash="dash", line_color="red")
            fig.add_hline(y=30, line_dash="dash", line_color="green")
            fig.update_layout(height=300, yaxis=dict(range=[0, 100]), margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)
            
            st.metric("Aktueller RSI-Wert", f"{df['RSI'].iloc[-1]:.2f}")
        except Exception as e:
            st.error(f"Fehler: {e}")

# ==============================================================================
# 4. HAUPTANSICHT: AUSWAHL
# ==============================================================================
st.title("⚡ Ultra-Schneller Globaler RSI-Scanner")
st.write("Durchsuche die wichtigsten Indizes der Welt in Sekundenschnelle rein nach RSI-Grenzen.")

markt = st.selectbox(
    "1. Welchen Markt / Index möchtest du scannen?",
    (
        "USA (S&P 500 Large Caps)",
        "USA (S&P 400 Mid Caps)",
        "USA (S&P 600 Small Caps)",
        "Deutschland (DAX 40 Large Caps)",
        "Deutschland (MDAX Mid Caps)",
        "Deutschland (SDAX Small Caps)",
        "Eurozone (EURO STOXX 50)",
        "Großbritannien (FTSE 100)",
        "Frankreich (CAC 40)",
        "Japan (Nikkei 225)"
    )
)

# ==============================================================================
# 5. HIGH-SPEED SCAN LOGIK
# ==============================================================================
if st.button("🚀 High-Speed Scan Starten", use_container_width=True):
    st.session_state.scan_results = []
    st.session_state.has_scanned = True
    
    with st.spinner("Hole Ticker-Liste..."):
        try:
            if "S&P 500" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", 0)
                tickers = [t.replace('.', '-') for t in table['Symbol'].tolist()]
            elif "S%26P 400" in markt or "S&P 400" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/List_of_S%26P_400_companies", 0)
                tickers = [t.replace('.', '-') for t in table['Ticker symbol'].tolist()]
            elif "S%26P 600" in markt or "S&P 600" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/List_of_S%26P_600_companies", 1)
                tickers = [t.replace('.', '-') for t in table['Ticker symbol'].tolist()]
            elif "DAX 40" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/DAX", 4)
                tickers = table['Ticker'].tolist()
            elif "MDAX" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/MDAX", 3)
                tickers = [t + ".DE" for t in table['Ticker'].tolist()]
            elif "SDAX" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/SDAX", 3)
                tickers = [t + ".DE" for t in table['Ticker'].tolist()]
            elif "EURO STOXX" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/Euro_Stoxx_50", 2)
                tickers = table['Ticker'].tolist()
            elif "FTSE 100" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/FTSE_100_Index", 4)
                tickers = [t.replace('.', '-') + ".L" for t in table['Ticker'].tolist()]
            elif "CAC 40" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/CAC_40", 4)
                tickers = [t + ".PA" for t in table['Ticker'].tolist()]
            elif "Nikkei 225" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/Nikkei_225", 2)
                tickers = [str(t) + ".T" for t in table['Ticker'].tolist()]
        except Exception as e:
            st.error(f"Fehler beim Laden der Ticker: {e}")
            tickers = []

    if tickers:
        # Performance-Sicherheitsschranke: Große Indizes für ungedrosselte Geschwindigkeit kappen
        if len(tickers) > 60:
            tickers = tickers[:60]

        with st.spinner(f"Scanne {len(tickers)} Aktien parallel..."):
            try:
                # Schneller Batch-Download (nur 1 Monat nötig für den aktuellen RSI14)
                data = yf.download(tickers, period="1mo", interval="1d", group_by='ticker', progress=False)
                
                for ticker in tickers:
                    df = data[ticker].dropna() if len(tickers) > 1 else data.copy()
                    if df.empty or len(df) < 15: continue
                    
                    df['RSI'] = calculate_rsi(df['Close'], period=14)
                    rsi_aktuell = df['RSI'].iloc[-1]
                    
                    # Schneller numerischer Filter-Abgleich
                    if rsi_min <= rsi_aktuell <= rsi_max:
                        st.session_state.scan_results.append({
                            "ticker": ticker,
                            "rsi": f"{rsi_aktuell:.2f}"
                        })
            except Exception as e:
                st.error(f"Fehler beim Daten-Download: {e}")

# ==============================================================================
# 6. ERGEBNISSE RENDERN
# ==============================================================================
if st.session_state.has_scanned:
    st.write("---")
    if st.session_state.scan_results:
        st.write(f"### 🎯 Treffer im gewählten RSI-Bereich ({len(st.session_state.scan_results)})")
        
        # Grid-Layout für extrem schnelle, kompakte Ansicht ohne Scroll-Wege
        cols = st.columns(3)
        for idx, item in enumerate(st.session_state.scan_results):
            col_target = cols[idx % 3]
            with col_target:
                with st.container(border=True):
                    st.write(f"**{item['ticker']}**")
                    st.write(f"Aktueller RSI: `{item['rsi']}`")
                    if st.button("📊 RSI-Verlauf", key=f"btn_{item['ticker']}_{idx}"):
                        show_details_popup(item["ticker"])
    else:
        st.warning("Keine Aktien im gewählten RSI-Bereich gefunden. Ändere die Schieberegler in der linken Seitenleiste.")
