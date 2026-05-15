import streamlit as st
import yfinance as yf
import pandas as pd
import urllib.request
import urllib.parse
from io import StringIO
import plotly.graph_objects as gr
from plotly.subplots import make_subplots
import random
import json  # Für die JSON-Verarbeitung der Suchvorschläge benötigt

# Streamlit Page Config
st.set_page_config(layout="wide", page_title="Schneller RSI-Scanner", page_icon="⚡")

# ==============================================================================
# 1. CACHING-LAYER
# ==============================================================================
@st.cache_data(ttl=300)  # Speichert Chartdaten für 5 Minuten im Cache
def load_cached_history(ticker, period, interval):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=86400)  # ISIN ändert sich nie, 24 Std. Cache
def load_cached_isin(ticker):
    try:
        stock = yf.Ticker(ticker)
        isin = stock.get_isin()
        if not isin or isin == '-':
            return "Nicht verfügbar"
        return isin
    except Exception:
        return "Nicht verfügbar"

# ==============================================================================
# 2. TECHNISCHE INDIKATOREN (RSI, MACD & BOLLINGER BÄNDER)
# ==============================================================================
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=signal, adjust=False).mean()
    macd_hist = macd - macd_signal
    macd_pct = (macd / ema_slow) * 100
    return macd, macd_signal, macd_hist, macd_pct

def calculate_bollinger_bands(series, period=20, num_std=2):
    sma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper_band = sma + (num_std * std)
    lower_band = sma - (num_std * std)
    return upper_band, sma, lower_band

# ==============================================================================
# 3. INTELLIGENTER & DOPPELT GESICHERTER TICKER + NAMEN SCRAPER
# ==============================================================================
def fetch_market_data(markt):
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    def extract_from_df(df, market_type):
        cols_lower = [str(c).lower() for c in df.columns]
        t_idx = -1
        for idx, c in enumerate(cols_lower):
            if any(k in c for k in ['symbol', 'kürzel', 'ticker', 'epic']):
                t_idx = idx
                break
        n_idx = -1
        for idx, c in enumerate(cols_lower):
            if any(k in c for k in ['security', 'unternehmen', 'company', 'name', 'firma']) and idx != t_idx:
                n_idx = idx
                break
        if t_idx == -1: return []
        if n_idx == -1: n_idx = 0
        
        t_col = df.columns[t_idx]
        n_col = df.columns[n_idx]
        
        extracted = []
        for _, row in df.iterrows():
            ticker = str(row[t_col]).split('[')[0].strip().upper()
            name = str(row[n_col]).split('[')[0].strip()
            if not ticker or ticker == 'NAN': continue
            
            if "S&P" in market_type:
                ticker = ticker.replace('.', '-')
            elif any(m in market_type for m in ["DAX", "MDAX", "SDAX"]):
                if not ticker.endswith('.DE'): ticker += '.DE'
            elif "FTSE" in market_type:
                ticker = ticker.replace('.', '-') + ".L"
            elif "CAC" in market_type:
                if not ticker.endswith('.PA'): ticker += '.PA'
            elif "NIKKEI" in market_type:
                if not ticker.endswith('.T'): ticker += '.T'
            elif "EURO STOXX" in market_type:
                if '.' not in ticker:
                    suffix = ".DE"
                    c_listing = [c for c in df.columns if 'listing' in str(c).lower() or 'exchange' in str(c).lower()]
                    if c_listing:
                        listing = str(row[c_listing[0]]).lower()
                        if 'paris' in listing: suffix = ".PA"
                        elif 'amsterdam' in listing: suffix = ".AS"
                        elif 'milan' in listing or 'milano' in listing: suffix = ".MI"
                        elif 'madrid' in listing: suffix = ".MC"
                        elif 'brussels' in listing: suffix = ".BR"
                    ticker += suffix
            extracted.append({"ticker": ticker, "name": name})
        return extracted

    try:
        if "S&P 500" in markt:
            req = urllib.request.Request("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", headers=headers)
            with urllib.request.urlopen(req) as r: df = pd.read_html(StringIO(r.read().decode('utf-8')))[0]
            return extract_from_df(df, "S&P")
        elif "S&P 400" in markt:
            req = urllib.request.Request("https://en.wikipedia.org/wiki/List_of_S%26P_400_companies", headers=headers)
            with urllib.request.urlopen(req) as r: df = pd.read_html(StringIO(r.read().decode('utf-8')))[0]
            return extract_from_df(df, "S&P")
        elif "S&P 600" in markt:
            req = urllib.request.Request("https://en.wikipedia.org/wiki/List_of_S%26P_600_companies", headers=headers)
            with urllib.request.urlopen(req) as r: df = pd.read_html(StringIO(r.read().decode('utf-8')))[1]
            return extract_from_df(df, "S&P")
        elif "DAX 40" in markt:
            req = urllib.request.Request("https://de.wikipedia.org/wiki/DAX", headers=headers)
            with urllib.request.urlopen(req) as r: tables = pd.read_html(StringIO(r.read().decode('utf-8')))
            for df in tables:
                res = extract_from_df(df, "DAX")
                if len(res) >= 30: return res
        elif "MDAX" in markt:
            req = urllib.request.Request("https://de.wikipedia.org/wiki/MDAX", headers=headers)
            with urllib.request.urlopen(req) as r: tables = pd.read_html(StringIO(r.read().decode('utf-8')))
            for df in tables:
                res = extract_from_df(df, "MDAX")
                if len(res) >= 30: return res
        elif "SDAX" in markt:
            req = urllib.request.Request("https://de.wikipedia.org/wiki/SDAX", headers=headers)
            with urllib.request.urlopen(req) as r: tables = pd.read_html(StringIO(r.read().decode('utf-8')))
            for df in tables:
                res = extract_from_df(df, "SDAX")
                if len(res) >= 30: return res
        elif "EURO STOXX" in markt:
            req = urllib.request.Request("https://en.wikipedia.org/wiki/Euro_Stoxx_50", headers=headers)
            with urllib.request.urlopen(req) as r: tables = pd.read_html(StringIO(r.read().decode('utf-8')))
            for df in tables:
                res = extract_from_df(df, "EURO STOXX")
                if len(res) >= 30: return res
        elif "FTSE 100" in markt:
            req = urllib.request.Request("https://en.wikipedia.org/wiki/FTSE_100_Index", headers=headers)
            with urllib.request.urlopen(req) as r: tables = pd.read_html(StringIO(r.read().decode('utf-8')))
            for df in tables:
                res = extract_from_df(df, "FTSE 100")
                if len(res) >= 50: return res
        elif "CAC 40" in markt:
            req = urllib.request.Request("https://en.wikipedia.org/wiki/CAC_40", headers=headers)
            with urllib.request.urlopen(req) as r: tables = pd.read_html(StringIO(r.read().decode('utf-8')))
            for df in tables:
                res = extract_from_df(df, "CAC 40")
                if len(res) >= 30: return res
        elif "Nikkei 225" in markt:
            req = urllib.request.Request("https://en.wikipedia.org/wiki/Nikkei_225", headers=headers)
            with urllib.request.urlopen(req) as r: tables = pd.read_html(StringIO(r.read().decode('utf-8')))
            for df in tables:
                res = extract_from_df(df, "NIKKEI")
                if len(res) >= 50: return res
    except Exception as e:
        st.error(f"Fehler beim Live-Scraping von {markt}: {e}")
    
    if "DAX 40" in markt:
        return [{"ticker": "ADS.DE", "name": "Adidas"}, {"ticker": "ALV.DE", "name": "Allianz"}, {"ticker": "BAS.DE", "name": "BASF"}, {"ticker": "BAYN.DE", "name": "Bayer"}, {"ticker": "BMW.DE", "name": "BMW"}, {"ticker": "DBK.DE", "name": "Deutsche Bank"}, {"ticker": "DTE.DE", "name": "Deutsche Telekom"}, {"ticker": "SAP.DE", "name": "SAP"}, {"ticker": "SIE.DE", "name": "Siemens"}]
    return []

# ==============================================================================
# 4. POP-UP (AKTIENNAME & BOLLINGER CHART INTEGRATION)
# ==============================================================================
@st.dialog("📊 Aktien-Details & Signal", width="large")
def show_details_popup(ticker, company_name):
    with st.spinner("Lade optimierte Daten aus dem Cache..."):
        try:
            df_base = load_cached_history(ticker, "1y", "1d")
            if df_base.empty:
                st.error("Keine Daten von Yahoo Finance erhalten. Bitte versuche es gleich noch einmal.")
                return
            
            current_price = df_base['Close'].iloc[-1]
            isin = load_cached_isin(ticker)
            
            df_base['RSI'] = calculate_rsi(df_base['Close'], period=14)
            df_base['SMA50'] = df_base['Close'].rolling(window=50).mean()
            df_base['SMA200'] = df_base['Close'].rolling(window=200).mean()
            df_base['MACD'], df_base['MACD_Signal'], df_base['MACD_Hist'], df_base['MACD_Pct'] = calculate_macd(df_base['Close'])
            
            df_base['Above'] = df_base['SMA50'] > df_base['SMA200']
            df_base['Crossover'] = df_base['Above'] & (~df_base['Above'].shift(1).fillna(True))
            recent_golden_cross = df_base['Crossover'].tail(14).any()
            
            rsi_aktuell = df_base['RSI'].iloc[-1]
            macd_pct_aktuell = df_base['MACD_Pct'].iloc[-1]
            
            st.write(f"## {company_name} (`{ticker}`)")
            
            meta_col1, meta_col2, meta_col3, meta_col4 = st.columns(4)
            with meta_col1:
                st.metric("Live-Kurs (ca.)", f"{current_price:,.2f}")
            with meta_col2:
                st.metric("RSI (14) Aktuell", f"{rsi_aktuell:.2f}")
            with meta_col3:
                st.metric("MACD vs. Null-Linie", f"{macd_pct_aktuell:+.2f}%")
            with meta_col4:
                st.write(f"**Identifikation:** ISIN: `{isin}`")
                tv_ticker = ticker.split('.')[0]
                tradingview_url = f"https://de.tradingview.com/symbols/{tv_ticker}/"
                st.markdown(f"[➡️ **Auf TradingView**]({tradingview_url})")
            
            st.write("---")
            
            if rsi_aktuell > 70:
                ampel_signal = "🔴 VERKAUFEN (Sell)"
                grund = "Der RSI (Tagesbasis) ist überkauft (> 70). Das Korrekturrisiko ist kurzfristig erhöht."
            elif rsi_aktuell < 30 or recent_golden_cross:
                ampel_signal = "🟢 KAUFEN (Buy)"
                if rsi_aktuell < 30 and recent_golden_cross:
                    grund = "Starkes Signal! RSI ist überverkauft (< 30) UND es liegt ein frisches Golden Cross vor."
                elif rsi_aktuell < 30:
                    grund = "Der RSI ist überverkauft (< 30). Die Aktie ist technisch reif für eine Erholung."
                else:
                    grund = "Es gab ein frisches Golden Cross (SMA50 schneidet SMA200) in den letzten 14 Tagen."
            else:
                ampel_signal = "🟡 HALTEN (Hold)"
                grund = "Die Aktie befindet sich auf Tagesbasis im neutralen Sektor."
            
            st.markdown(f"### Signal-Ampel (Tagesbasis): {ampel_signal}")
            st.caption(f"**Grund:** {grund}")
            st.write("")

            tab1, tab2, tab3, tab4 = st.tabs(["⏱️ 10 Min", "⏱️ 30 Min", "⏳ 4 Std", "📅 1 Tag (Klassisch)"])
            
            def render_chart(df_chart, title_suffix):
                if df_chart.empty or len(df_chart) < 2:
                    st.warning(f"Keine ausreichenden Intraday-Daten für {title_suffix} im Cache.")
                    return
                
                df_chart['RSI'] = calculate_rsi(df_chart['Close'], period=14)
                df_chart['MACD'], df_chart['MACD_Signal'], df_chart['MACD_Hist'], _ = calculate_macd(df_chart['Close'])
                df_chart['BB_Upper'], df_chart['BB_Middle'], df_chart['BB_Lower'] = calculate_bollinger_bands(df_chart['Close'])
                
                fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06, row_heights=[0.45, 0.25, 0.30])
                
                # --- ROW 1: KURS, SMAs & BOLLINGER BÄNDER ---
                fig.add_trace(gr.Scatter(x=df_chart.index, y=df_chart['Close'], mode='lines', name='Kurs', line=dict(color='#1f77b4', width=2.5)), row=1, col=1)
                
                if 'SMA50' in df_chart.columns:
                    fig.add_trace(gr.Scatter(x=df_chart.index, y=df_chart['SMA50'], mode='lines', name='SMA 50', line=dict(color='orange', width=1.5)), row=1, col=1)
                    fig.add_trace(gr.Scatter(x=df_chart.index, y=df_chart['SMA200'], mode='lines', name='SMA 200', line=dict(color='red', width=1.5)), row=1, col=1)
                
                fig.add_trace(gr.Scatter(x=df_chart.index, y=df_chart['BB_Upper'], mode='lines', name='BB Oben', line=dict(color='rgba(128, 128, 128, 0.5)', width=1.5, dash='dash')), row=1, col=1)
                fig.add_trace(gr.Scatter(x=df_chart.index, y=df_chart['BB_Middle'], mode='lines', name='BB Mitte (Basis)', line=dict(color='rgba(128, 128, 128, 0.3)', width=1, dash='dot')), row=1, col=1)
                fig.add_trace(gr.Scatter(x=df_chart.index, y=df_chart['BB_Lower'], mode='lines', name='BB Unten', line=dict(color='rgba(128, 128, 128, 0.5)', width=1.5, dash='dash')), row=1, col=1)
                
                # --- ROW 2: RSI ---
                fig.add_trace(gr.Scatter(x=df_chart.index, y=df_chart['RSI'], mode='lines', name='RSI 14', line=dict(color='purple', width=1.5)), row=2, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
                
                # --- ROW 3: MACD ---
                fig.add_trace(gr.Scatter(x=df_chart.index, y=df_chart['MACD'], mode='lines', name='MACD', line=dict(color='blue', width=1.5)), row=3, col=1)
                fig.add_trace(gr.Scatter(x=df_chart.index, y=df_chart['MACD_Signal'], mode='lines', name='Signal (Geglättet)', line=dict(color='orange', width=1.5)), row=3, col=1)
                fig.add_trace(gr.Bar(x=df_chart.index, y=df_chart['MACD_Hist'], name='Histogramm', marker_color='lightgray', opacity=0.7), row=3, col=1)
                fig.add_hline(y=0, line_dash="solid", line_color="gray", row=3, col=1)
                
                fig.update_layout(height=580, margin=dict(l=10, r=10, t=10, b=10), showlegend=True, yaxis2=dict(range=[0, 100]))
                st.plotly_chart(fig, use_container_width=True)

            with tab1:
                st.write("### 10-Minuten-Chart (Letzte 5 Handelstage)")
                df_10m = load_cached_history(ticker, "5d", "10m")
                render_chart(df_10m, "10 Min")

            with tab2:
                st.write("### 30-Minuten-Chart (Letzte 14 Tage)")
                df_30m = load_cached_history(ticker, "14d", "30m")
                render_chart(df_30m, "30 Min")

            with tab3:
                st.write("### 4-Stunden-Chart (Letzte 2 Monate)")
                df_1h = load_cached_history(ticker, "60d", "1h")
                if not df_1h.empty:
                    df_4h = df_1h.resample('4h').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()
                else:
                    df_4h = pd.DataFrame()
                render_chart(df_4h, "4 Std")

            with tab4:
                st.write("### 1-Tages-Chart (Letzte 30 Handelstage)")
                df_day_focus = df_base.tail(30)
                render_chart(df_day_focus, "1 Tag")
            
        except Exception as e:
            st.error(f"Fehler im Analyse-Fenster: {e}")

# ==============================================================================
# 5. SEITENLEISTE (Inklusive Suchfunktion)
# ==============================================================================
if "scan_results" not in st.session_state:
    st.session_state.scan_results = []
if "has_scanned" not in st.session_state:
    st.session_state.has_scanned = False

st.sidebar.header("⚡ RSI-Filter")
rsi_min = st.sidebar.slider("Minimaler RSI-Wert", 0, 100, 20, step=1)
rsi_max = st.sidebar.slider("Maximaler RSI-Wert", 0, 100, 40, step=1)

st.sidebar.write("---")
st.sidebar.header("📈 Chart-Signale")
golden_cross_active = st.sidebar.toggle("Nur mit Golden Cross (letzte 14 Tage)", value=False)

st.sidebar.write("---")
st.sidebar.header("🔍 Direkte Aktiensuche")

def get_ticker_suggestions(query):
    if not query or len(query) < 2:
        return []
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(query)}&quotesCount=5&newsCount=0"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            suggestions = []
            for quote in data.get('quotes', []):
                if quote.get('quoteType') in ['EQUITY', 'ETF']:
                    symbol = quote.get('symbol')
                    name = quote.get('shortname', quote.get('longname', 'Unbekannt'))
                    suggestions.append({"label": f"{symbol} - {name}", "ticker": symbol, "name": name})
            return suggestions
    except Exception:
        return []

search_query = st.sidebar.text_input("Aktienname oder Ticker eingeben:", placeholder="z.B. Apple oder AAPL")

if search_query:
    suggestions = get_ticker_suggestions(search_query)
    if suggestions:
        options_dict = {item["label"]: item for item in suggestions}
        selected_label = st.sidebar.selectbox("Gefundene Treffer:", options_dict.keys(), index=0, key="search_autocomplete")
        
        if selected_label:
            selected_stock = options_dict[selected_label]
            if st.sidebar.button(f"📊 {selected_stock['ticker']} analysieren", use_container_width=True):
                show_details_popup(selected_stock["ticker"], selected_stock["name"])
    else:
        st.sidebar.caption("❌ Keine Vorschläge gefunden.")

# ==============================================================================
# 6. HAUPTANSICHT (INDEX MULTI-SCANNER)
# ==============================================================================
st.title("⚡ Ultra-Schneller Globaler RSI-Scanner")
markt = st.selectbox("1. Welchen Markt / Index möchtest du scannen?", ("USA (S&P 500 Large Caps)", "USA (S&P 400 Mid Caps)", "USA (S&P 600 Small Caps)", "Deutschland (DAX 40 Large Caps)", "Deutschland (MDAX Mid Caps)", "Deutschland (SDAX Small Caps)", "Eurozone (EURO STOXX 50)", "Großbritannien (FTSE 100)", "Frankreich (CAC 40)", "Japan (Nikkei 225)"))

if st.button("🚀 High-Speed Scan Starten", use_container_width=True):
    st.session_state.scan_results = []
    st.session_state.has_scanned = True
    
    with st.spinner(f"Hole Ticker- und Namensdaten für {markt}..."):
        market_data = fetch_market_data(markt)

    if market_data:
        if len(market_data) > 60:
            market_data = random.sample(market_data, 60)

        tickers = [item['ticker'] for item in market_data]
        ticker_to_name = {item['ticker']: item['name'] for item in market_data}

        with st.spinner(f"Scanne {len(tickers)} Aktien parallel aus {markt}..."):
            try:
                download_period = "1y" if golden_cross_active else "3mo"
                data = yf.download(tickers, period=download_period, interval="1d", group_by='ticker', progress=False)
                
                for ticker in tickers:
                    if len(tickers) > 1:
                        if ticker not in data.columns.levels[0]: 
                            continue
                        df = data[ticker].dropna(subset=['Close'])
                    else:
                        df = data.copy().dropna(subset=['Close'])
                        
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
                        
                        if not df['Crossover'].tail(14).any():
                            continue
                    
                    st.session_state.scan_results.append({
                        "ticker": ticker,
                        "name": ticker_to_name.get(ticker, ticker),
                        "rsi": f"{rsi_aktuell:.2f}"
                    })
            except Exception as e:
                st.error(f"Fehler beim Daten-Download: {e}")

# ==============================================================================
# 7. ERGEBNISSE RENDERN
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
                    st.write(f"**{item['name']}**")
                    st.caption(f"Ticker: `{item['ticker']}` | RSI: `{item['rsi']}`")
                    if st.button("📊 Analysieren", key=f"btn_{item['ticker']}_{idx}"):
                        show_details_popup(item["ticker"], item["name"])
    else:
        st.warning("Keine Aktien mit den gewählten Kriterien gefunden. Passe deine RSI-Filter an oder starte den Scan erneut.")
