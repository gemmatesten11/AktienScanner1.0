import streamlit as st
import yfinance as yf
import pandas as pd
import urllib.request
from io import StringIO
import plotly.graph_objects as gr
from plotly.subplots import make_subplots

# Streamlit Page Config
st.set_page_config(layout="wide", page_title="Schneller RSI-Scanner", page_icon="⚡")

# ==============================================================================
# 1. KORRIGIERTE RSI FUNKTION (WILDER'S SMOOTHING)
# ==============================================================================
def calculate_rsi(series, period=14):
    delta = series.diff()
    
    # Gewinne und Verluste trennen
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    # Wilder's Smoothing via Exponential Moving Average (EMA) mit alpha = 1/period
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    
    rs = avg_gain / avg_loss
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
# 2. SEITENLEISTE
# ==============================================================================
st.sidebar.header("⚡ RSI-Filter")
rsi_min = st.sidebar.slider("Minimaler RSI-Wert", 0, 100, 20, step=1)
rsi_max = st.sidebar.slider("Maximaler RSI-Wert", 0, 100, 40, step=1)

st.sidebar.write("---")
st.sidebar.header("📈 Chart-Signale")
golden_cross_active = st.sidebar.toggle("Nur mit Golden Cross (letzte 5 Tage)", value=False)

# ==============================================================================
# 3. POP-UP
# ==============================================================================
@st.dialog("📊 Aktien-Details & Signal", width="large")
def show_details_popup(ticker):
    with st.spinner("Lade Daten und Berechne Indikatoren..."):
        try:
            stock = yf.Ticker(ticker)
            try:
                company_name = stock.info.get('longName', ticker)
            except Exception:
                company_name = ticker
            
            st.write(f"## {company_name} (`{ticker}`)")
            
            # Immer 1 Jahr laden, um stabilen SMA200 und exakten RSI zu garantieren
            df = stock.history(period="1y", interval="1d")
            df['RSI'] = calculate_rsi(df['Close'], period=14)
            
            df['SMA50'] = df['Close'].rolling(window=50).mean()
            df['SMA200'] = df['Close'].rolling(window=200).mean()
            
            df['Above'] = df['SMA50'] > df['SMA200']
            df['Crossover'] = df['Above'] & (~df['Above'].shift(1).fillna(True))
            recent_golden_cross = df['Crossover'].tail(5).any()
            
            rsi_aktuell = df['RSI'].iloc[-1]
            df_last30 = df.tail(30)
            
            if rsi_aktuell < 30 or recent_golden_cross:
                ampel_signal = "🟢 KAUFEN (Buy)"
                grund = "Der RSI ist überverkauft (< 30) oder es gab ein frisches Golden Cross (letzte 5 Tage)."
            elif rsi_aktuell > 70:
                ampel_signal = "🔴 VERKAUFEN (Sell)"
                grund = "Der RSI ist überkauft (> 70). Korrekturrisiko erhöht."
            else:
                ampel_signal = "🟡 HALTEN (Hold)"
                grund = "RSI ist im neutralen Bereich und kein akutes Ausbruchsignal vorhanden."
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Aktueller RSI-Wert", f"{rsi_aktuell:.2f}")
            with col2:
                st.markdown(f"### Signal-Ampel: {ampel_signal}")
                st.caption(f"**Grund:** {grund}")
            
            st.write("---")
            st.write("### Chart-Analyse (Letzte 30 Handelstage)")
            
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.6, 0.4])
            fig.add_trace(gr.Scatter(x=df_last30.index, y=df_last30['Close'], mode='lines', name='Kurs', line=dict(color='#1f77b4', width=2)), row=1, col=1)
            fig.add_trace(gr.Scatter(x=df_last30.index, y=df_last30['SMA50'], mode='lines', name='SMA 50', line=dict(color='orange', width=1.5)), row=1, col=1)
            fig.add_trace(gr.Scatter(x=df_last30.index, y=df_last30['SMA200'], mode='lines', name='SMA 200', line=dict(color='red', width=1.5)), row=1, col=1)
            
            fig.add_trace(gr.Scatter(x=df_last30.index, y=df_last30['RSI'], mode='lines+markers', name='RSI 14', line=dict(color='purple', width=2)), row=2, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
            
            fig.update_layout(height=480, margin=dict(l=10, r=10, t=10, b=10), showlegend=True, yaxis2=dict(range=[0, 100]))
            st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            st.error(f"Fehler beim Laden der Details: {e}")

# ==============================================================================
# 4. HAUPTANSICHT
# ==============================================================================
st.title("⚡ Ultra-Schneller Globaler RSI-Scanner")
markt = st.selectbox("1. Welchen Markt / Index möchtest du scannen?", ("USA (S&P 500 Large Caps)", "USA (S&P 400 Mid Caps)", "USA (S&P 600 Small Caps)", "Deutschland (DAX 40 Large Caps)", "Deutschland (MDAX Mid Caps)", "Deutschland (SDAX Small Caps)", "Eurozone (EURO STOXX 50)", "Großbritannien (FTSE 100)", "Frankreich (CAC 40)", "Japan (Nikkei 225)"))

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
            elif "S&P 400" in markt:
                table = get_wikipedia_table("https://en.wikipedia.org/wiki/List_of_S%26P_400_companies", 0)
                tickers = [t.replace('.', '-') for t in table['Ticker symbol'].tolist()]
            elif "S&P 600" in markt:
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
        if len(tickers) > 60:
            tickers = tickers[:60]

        with st.spinner(f"Scanne {len(tickers)} Aktien parallel..."):
            try:
                # WICHTIG: Mindestens 3 Monate ("3mo") für korrekte RSI-Einschwingzeit laden!
                download_period = "1y" if golden_cross_active else "3mo"
                data = yf.download(tickers, period=download_period, interval="1d", group_by='ticker', progress=False)
                
                for ticker in tickers:
                    df = data[ticker].dropna(subset=['Close']) if len(tickers) > 1 else data.copy().dropna(subset=['Close'])
                    if df.empty or len(df) < 15: 
                        continue
                    
                    df['RSI'] = calculate_rsi(df['Close'], period=14)
                    rsi_aktuell = df['RSI'].iloc[-1]
                    
                    if not (rsi_min <= rsi_aktuell <= rsi_max):
                        continue
                    
                    if golden_cross_active:
                        if len(df) < 200:
                            continue
                        df['SMA50'] = df['Close'].rolling(window=50).mean()
                        df['SMA200'] = df['Close'].rolling(window=200).mean()
                        df['Above'] = df['SMA50'] > df['SMA200']
                        df['Crossover'] = df['Above'] & (~df['Above'].shift(1).fillna(True))
                        
                        if not df['Crossover'].tail(5).any():
                            continue
                    
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
        st.write(f"### 🎯 Treffer im gewählten Bereich ({len(st.session_state.scan_results)})")
        cols = st.columns(3)
        for idx, item in enumerate(st.session_state.scan_results):
            col_target = cols[idx % 3]
            with col_target:
                with st.container(border=True):
                    st.write(f"**{item['ticker']}**")
                    st.write(f"Aktueller RSI: `{item['rsi']}`")
                    if st.button("📊 Analysieren", key=f"btn_{item['ticker']}_{idx}"):
                        show_details_popup(item["ticker"])
    else:
        st.warning("Keine Aktien mit den gewählten Kriterien gefunden.")
