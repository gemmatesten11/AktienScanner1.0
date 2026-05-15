import streamlit as st
import yfinance as yf
import pandas as pd
import os
import time
import urllib.request
import google.generativeai as genai
import plotly.graph_objects as go  # FIX #1: war fälschlich 'gr' (Gradio-Konvention)
from io import StringIO

# Streamlit Page Config
st.set_page_config(layout="wide", page_title="KI-Markt-Scanner", page_icon="🤖")

# ==============================================================================
# 1. API-KONFIGURATION & SESSION STATE
# ==============================================================================
GOOGLE_API_KEY = os.environ.get("GEMINI_API_KEY")
model = None  # FIX #8: Fallback-Definition, verhindert NameError wenn Key fehlt

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    st.error("Bitte hinterlege den GEMINI_API_KEY in den Streamlit Cloud Secrets!")

# Session States initialisieren
if "scan_results" not in st.session_state:
    st.session_state.scan_results = []
if "has_scanned" not in st.session_state:
    st.session_state.has_scanned = False
if "balloons_shown" not in st.session_state:  # FIX #12: Balloons nur einmal anzeigen
    st.session_state.balloons_shown = False

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

def get_wikipedia_table(url, column_hint=None, index=0):
    """
    FIX #5: Robusteres Wikipedia-Scraping.
    Sucht zuerst nach einer Tabelle mit der gewünschten Spalte (column_hint),
    fällt sonst auf den numerischen Index zurück.
    """
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            )
        }
    )
    with urllib.request.urlopen(req) as response:
        html_text = response.read().decode('utf-8')
    tables = pd.read_html(StringIO(html_text))

    if column_hint:
        for table in tables:
            if column_hint in table.columns:
                return table
    return tables[index]

def get_currency_symbol(ticker):
    """FIX #11: Währung anhand des Ticker-Suffixes bestimmen."""
    if ticker.endswith(".DE") or ticker.endswith(".F"):
        return "EUR"
    elif ticker.endswith(".L"):
        return "GBP"
    else:
        return "USD"

# ==============================================================================
# 3. POP-UP DETAILANSICHT (FINANZ-COCKPIT)
# ==============================================================================
@st.dialog("📊 Finanz-Cockpit & Details", width="large")
def show_details_popup(ticker):
    st.write(f"### Detailanalyse für: **{ticker}**")
    st.divider()

    with st.spinner(f"Lade tiefgehende Finanzdetails für {ticker}..."):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            # FIX #9: Einheitlich 6mo für Download und Popup
            df = stock.history(period="6mo", interval="1d")

            if df.empty:
                st.error("Keine historischen Kursdaten für diesen Zeitraum verfügbar.")
                return

            df['RSI'] = calculate_rsi(df['Close'], period=14)
            df['MACD'], df['MACD_Signal'] = calculate_macd(df['Close'])
            last = df.iloc[-1]
            rsi_val = last['RSI']
            currency = get_currency_symbol(ticker)

            # FIX #4: ISIN/WKN kommen nicht von yfinance → ehrlich kommunizieren
            name = info.get("longName", ticker)
            exchange = info.get("exchange", "N/A")
            sector = info.get("sector", "N/A")
            industry = info.get("industry", "N/A")

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Unternehmen", name)
            col2.metric("Ticker", ticker)
            col3.metric("Börse", exchange)
            col4.metric("Sektor", sector)
            st.caption(f"Branche: {industry}")

            st.divider()

            # TECHNISCHE AMPEL-LOGIK (RSI & MACD)
            st.subheader("🚦 Technische Live-Ampel")
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

            st.info(
                f"**Empfehlung auf Basis der mathematischen Indikatoren:** "
                f"{ampel_color} {ampel_status}"
            )
            st.divider()

            # CHARTS
            st.subheader("📈 Technische Analyse & Charts")

            # 1. Candlestick Chart
            fig_chart = go.Figure()
            fig_chart.add_trace(go.Candlestick(
                x=df.index,
                open=df['Open'], high=df['High'],
                low=df['Low'], close=df['Close'],
                name="Kurs"
            ))
            fig_chart.update_layout(
                title="Live Candlestick Chart (6 Monate)",
                xaxis_rangeslider_visible=False,
                height=280
            )
            st.plotly_chart(fig_chart, use_container_width=True)

            # 2. RSI Chart
            fig_rsi = go.Figure()
            fig_rsi.add_trace(go.Scatter(
                x=df.index, y=df['RSI'],
                mode='lines', name='RSI',
                line=dict(color='purple')
            ))
            fig_rsi.add_hline(y=70, line_dash="dash", line_color="red",
                              annotation_text="Überkauft")
            fig_rsi.add_hline(y=30, line_dash="dash", line_color="green",
                              annotation_text="Überverkauft")
            fig_rsi.update_layout(
                title=f"RSI14 Indikator (Aktuell: {rsi_val:.1f})",
                yaxis=dict(range=[10, 90]),
                height=180
            )
            st.plotly_chart(fig_rsi, use_container_width=True)

            # 3. MACD Chart
            df['Histo'] = df['MACD'] - df['MACD_Signal']
            fig_macd = go.Figure()
            fig_macd.add_trace(go.Scatter(
                x=df.index, y=df['MACD'],
                mode='lines', name='MACD',
                line=dict(color='blue')
            ))
            fig_macd.add_trace(go.Scatter(
                x=df.index, y=df['MACD_Signal'],
                mode='lines', name='Signal',
                line=dict(color='orange')
            ))
            fig_macd.add_trace(go.Bar(
                x=df.index, y=df['Histo'],
                name='Histogramm', opacity=0.3
            ))
            fig_macd.update_layout(title="MACD Momentum", height=180)
            st.plotly_chart(fig_macd, use_container_width=True)

            st.divider()

            # ANALYSTEN TABELLE
            st.subheader("👥 Analysten-Konsensus & Ratings")
            target_high = info.get("targetHighPrice", "N/A")
            target_low = info.get("targetLowPrice", "N/A")
            target_mean = info.get("targetMeanPrice", "N/A")
            current_price = info.get("currentPrice", last['Close'])
            recommendation = info.get("recommendationKey", "N/A").upper()

            # FIX #11: Korrekte Währungseinheit je nach Markt
            def fmt(val):
                return f"{val} {currency}" if val != "N/A" else "N/A"

            analysten_data = {
                "Metrik": [
                    "Aktueller Kurs",
                    "Analysten-Ziel (Schnitt)",
                    "Höchstes Kursziel",
                    "Niedrigstes Kursziel",
                    "Gesamturteil"
                ],
                "Wert": [
                    fmt(current_price),
                    fmt(target_mean),
                    fmt(target_high),
                    fmt(target_low),
                    recommendation
                ]
            }
            st.table(pd.DataFrame(analysten_data))

        except Exception as e:
            st.error(f"Fehler beim Laden der Finanzdetails: {e}")

# ==============================================================================
# 4. HAUPTANSICHT: BRANCHEN- & MARKT-SCANNER
# ==============================================================================
st.title("🤖 KI-Markt- & Branchen-Scanner v2.6")
st.write("Massen-Live-Scan mit Candlestick-Charts, RSI, MACD und KI-Analyse.")

markt = st.selectbox(
    "1. Welchen Index möchtest du scannen?",
    (
        "S&P 500 (USA) - Top 500 US-Unternehmen",
        "NASDAQ-100 (USA) - Große Tech-Werte",
        "Dow Jones Industrial Average (USA) - 30 Blue-Chips",
        "DAX 40 (Deutschland) - Deutscher Leitindex",
        "EURO STOXX 50 (Eurozone) - Die 50 größten Euro-Werte"
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
# FIX #10: Sinnvollere Mindest-Untergrenze für Volumen-Faktor
vol_mult = st.sidebar.slider("Volumen-Faktor (x des Schnitts)", 0.8, 3.0, 1.0)

# ==============================================================================
# 5. DOWNLOAD & SCAN RUNNER
# ==============================================================================
if st.button("🚀 Scan Starten"):
    st.session_state.scan_results = []
    st.session_state.has_scanned = True
    st.session_state.balloons_shown = False  # Reset für neuen Scan

    with st.spinner("Hole aktuelle Aktienliste..."):
        try:
            # FIX #5: column_hint statt hardcodiertem Index
            if "S&P 500" in markt:
                table = get_wikipedia_table(
                    "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
                    column_hint="Symbol"
                )
                tickers = [t.replace('.', '-') for t in table['Symbol'].tolist()]

            elif "NASDAQ-100" in markt:
                table = get_wikipedia_table(
                    "https://en.wikipedia.org/wiki/Nasdaq-100",
                    column_hint="Ticker"
                )
                tickers = table['Ticker'].tolist()

            elif "Dow Jones" in markt:
                table = get_wikipedia_table(
                    "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average",
                    column_hint="Symbol"
                )
                tickers = table['Symbol'].tolist()

            elif "DAX 40" in markt:
                table = get_wikipedia_table(
                    "https://en.wikipedia.org/wiki/DAX",
                    column_hint="Ticker"
                )
                tickers = table['Ticker'].tolist()

            elif "EURO STOXX 50" in markt:
                table = get_wikipedia_table(
                    "https://en.wikipedia.org/wiki/Euro_Stoxx_50",
                    column_hint="Ticker"
                )
                tickers = table['Ticker'].tolist()

            else:
                tickers = ["AAPL", "MSFT", "NVDA", "SAP"]

        except Exception as e:
            st.error(f"Fehler beim Laden des Index von Wikipedia: {e}")
            tickers = []

    if tickers:
        if len(tickers) > 50:
            st.warning("Index sehr groß. Scanne die ersten 50 Werte für maximale Stabilität...")
            tickers = tickers[:50]

        st.info(f"Lade Live-Kursdaten für {len(tickers)} Aktien herunter...")

        try:
            # FIX #9: Einheitlich 6mo für Download und Popup
            data = yf.download(
                tickers, period="6mo", interval="1d",
                group_by='ticker', progress=False, auto_adjust=True
            )
        except Exception as e:
            st.error(f"Fehler beim Massen-Download von Yahoo Finance: {e}")
            data = pd.DataFrame()

        if not data.empty:
            progress_bar = st.progress(0)

            with st.spinner("Verarbeite technische Signale und generiere KI-Analysen..."):
                for idx, ticker in enumerate(tickers):
                    progress_bar.progress((idx + 1) / len(tickers))

                    try:
                        # FIX #2: Robuster Zugriff bei Ein- und Mehr-Ticker-Downloads
                        if len(tickers) > 1:
                            if ticker not in data.columns.get_level_values(0):
                                continue
                            df = data[ticker].dropna()
                        else:
                            df = data.copy().dropna()

                        if df.empty or len(df) < 25:
                            continue

                        # FIX #6: Sektor-Infos nur wenn wirklich gebraucht
                        if "Alle Branchen" not in branche:
                            t_info = yf.Ticker(ticker).info
                            t_sector = t_info.get("sector", "")
                            t_industry = t_info.get("industry", "")

                            if branche == "Versicherungen":
                                if "Insurance" not in t_industry:
                                    continue
                            elif "Finanzwesen" in branche:
                                if "Insurance" in t_industry or t_sector != "Financial Services":
                                    continue
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
                            ai_text = "KI-Analyse nicht verfügbar (kein API-Key)."

                            # FIX #8: Nur aufrufen wenn model initialisiert wurde
                            if model is not None:
                                try:
                                    prompt = (
                                        f"Aktie {ticker}: RSI ist {last['RSI']:.1f}, "
                                        f"Volumen liegt bei {last['Volume']/avg_vol:.1f}x des Durchschnitts. "
                                        f"Gib eine extrem kurze, professionelle Trading-Einschätzung (max. 2 Sätze)."
                                    )
                                    response = model.generate_content(prompt)
                                    ai_text = response.text
                                    time.sleep(1)  # FIX #7: Rate-Limiting gegen 429-Fehler
                                except Exception as ai_err:
                                    ai_text = f"KI-Analyse fehlgeschlagen: {ai_err}"

                            st.session_state.scan_results.append({
                                "ticker": ticker,
                                "rsi": f"{last['RSI']:.1f}",
                                "ai_text": ai_text
                            })

                    # FIX #3: Fehler loggen statt still ignorieren
                    except Exception as e:
                        st.warning(f"⚠️ Fehler bei {ticker}: {e}")
                        continue

# ==============================================================================
# 6. ERGEBNIS-ANZEIGE & POP-UP LOGIK
# ==============================================================================
if st.session_state.has_scanned:
    if st.session_state.scan_results:
        st.write(f"### 🎯 Gefundene Markt-Treffer ({len(st.session_state.scan_results)})")
        st.divider()

        for idx, item in enumerate(st.session_state.scan_results):
            with st.container():
                st.success(f"🎯 Treffer: **{item['ticker']}** (Aktueller RSI: {item['rsi']})")

                if st.button(
                    f"🔍 Vollständige Finanzdetails für {item['ticker']} anzeigen",
                    key=f"btn_{item['ticker']}_{idx}"
                ):
                    show_details_popup(item["ticker"])

                st.info(f"**Gemini-Analyse:** {item['ai_text']}")
                st.divider()

        # FIX #12: Ballons nur einmal nach dem Scan anzeigen, nicht bei jedem Re-Render
        if not st.session_state.balloons_shown:
            st.balloons()
            st.session_state.balloons_shown = True

    else:
        st.warning(
            "Scan beendet. Aktuell erfüllt kein Titel dieses Profil. "
            "Lockere die Kriterien in der Seitenleiste!"
        )
