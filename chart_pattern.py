import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from scipy.signal import find_peaks
import feedparser
import urllib.parse

# ==========================================
# 1. UI/UX: 모바일 반응형 CSS 전면 적용
# ==========================================
# layout="wide"는 PC에서 넓게, 모바일에서는 알아서 1단으로 접히게 만듭니다.
st.set_page_config(layout="wide", page_title="AI 프리미엄 퀀트", page_icon="👑")

st.markdown("""
    <style>
    /* 기본 테마 (다크 모드) */
    .main { background-color: #0E1117; color: #FFFFFF; }
    
    /* 탭 디자인 */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { font-size: 1.1rem; font-weight: bold; color: #888; }
    .stTabs [aria-selected="true"] { color: #00FF00 !important; border-bottom-color: #00FF00 !important; }
    
    /* AI 리포트 및 뉴스 박스 */
    .ai-report { background: #1E1E1E; padding: 20px; border-radius: 10px; border-left: 5px solid #00FF00; margin-bottom: 20px; line-height: 1.6;}
    .news-box { background: #1a1c24; padding: 15px; border-radius: 8px; margin-bottom: 10px; border-left: 3px solid #00FF00; word-break: keep-all;}
    .news-box-market { border-left: 3px solid #00BFFF; }
    .news-title { font-size: 1.0rem; font-weight: bold; color: #ffffff; text-decoration: none;}
    .news-title:hover { color: #ff4b4b; text-decoration: underline;}
    .news-date { font-size: 0.8rem; color: #aaaaaa; margin-top: 5px;}
    
    /* 메트릭(현재가 등) 큰 글씨 설정 */
    div[data-testid="stMetricValue"] { font-size: 1.6rem !important; font-weight: 800; color: #00FF00; }

    /* 📱 모바일 전용 최적화 (화면 너비 768px 이하일 때 발동) */
    @media (max-width: 768px) {
        .stTabs [data-baseweb="tab"] { font-size: 0.95rem; padding-left: 5px; padding-right: 5px; }
        div[data-testid="stMetricValue"] { font-size: 1.3rem !important; }
        .ai-report { padding: 15px; font-size: 0.95rem; }
        .news-box { padding: 12px; }
        .news-title { font-size: 0.95rem; }
        h3 { font-size: 1.3rem !important; }
        h4 { font-size: 1.1rem !important; }
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 스마트 검색 & 실시간 뉴스 엔진
# ==========================================
@st.cache_data(ttl=86400)
def load_krx_listing():
    return fdr.StockListing('KRX')

krx_df = load_krx_listing()

def get_ticker_from_name(query):
    query = query.strip()
    if query.isdigit() and len(query) == 6: return query
    match = krx_df[krx_df['Name'] == query]
    if not match.empty: return match.iloc[0]['Code']
    us_map = {"테슬라": "TSLA", "애플": "AAPL", "엔비디아": "NVDA", "마이크로소프트": "MSFT"}
    return us_map.get(query, query.upper())

@st.cache_data(ttl=300)
def get_market_news():
    search_keyword = "증시 특징주 OR 주식 마감 OR 코스피 코스닥 OR 금리 인상"
    encoded_query = urllib.parse.quote(search_keyword)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        feed = feedparser.parse(url)
        return [{"title": entry.title, "link": entry.link, "date": entry.published[:-4] if hasattr(entry, 'published') else "최근"} for entry in feed.entries[:7]]
    except Exception: return []

@st.cache_data(ttl=300)
def get_latest_news(query):
    search_keyword = f"{query} 특징주 OR {query} 주가 OR {query} 실적"
    encoded_query = urllib.parse.quote(search_keyword)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        feed = feedparser.parse(url)
        return [{"title": entry.title, "link": entry.link, "date": entry.published[:-4] if hasattr(entry, 'published') else "최근"} for entry in feed.entries[:7]]
    except Exception: return []

# ==========================================
# 3. 사이드바 설정 (모바일에서는 자동으로 햄버거 메뉴로 숨겨짐)
# ==========================================
st.sidebar.title("⚙️ 시스템 설정")

quick_tickers = ["직접 입력...", "삼성전자", "풍산", "한화솔루션", "테슬라", "애플", "엔비디아"]
selected_quick = st.sidebar.selectbox("⭐ 관심 종목 퀵뷰", quick_tickers)
default_input = "풍산" if selected_quick == "직접 입력..." else selected_quick
user_input = st.sidebar.text_input("종목명/코드 검색", value=default_input)

ticker = get_ticker_from_name(user_input)
st.sidebar.caption(f"🔍 자동 변환된 코드: **{ticker}**")
period = st.sidebar.select_slider("조회 기간", options=["3mo", "6mo", "1y", "2y"], value="6mo")

st.sidebar.markdown("---")
st.sidebar.subheader("🧮 포트폴리오 시뮬레이터")
buy_p = st.sidebar.number_input("평균 단가", value=0.0, step=0.1)
qty = st.sidebar.number_input("보유 수량", value=0, step=1)

# ==========================================
# 4. 퀀트 데이터 코어 연산
# ==========================================
@st.cache_data(ttl=60)
def load_and_calc_data(symbol, p):
    try:
        today = datetime.today()
        days_map = {"3mo": 90, "6mo": 180, "1y": 365, "2y": 730}
        start_date = today - timedelta(days=days_map.get(p, 180))
        
        df = fdr.DataReader(symbol, start_date)
        if df.empty or len(df) < 30: return None
        
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        df['MACD'] = df['Close'].ewm(span=12).mean() - df['Close'].ewm(span=26).mean()
        df['Signal'] = df['MACD'].ewm(span=9).mean()
        df['MACD_Hist'] = df['MACD'] - df['Signal']
        
        low_min = df['Low'].rolling(window=14).min()
        high_max = df['High'].rolling(window=14).max()
        df['Stoch_K'] = 100 * ((df['Close'] - low_min) / (high_max - low_min))
        df['Stoch_D'] = df['Stoch_K'].rolling(window=3).mean()
        
        df['Body'] = abs(df['Close'] - df['Open'])
        df['Upper_Shadow'] = df['High'] - df[['Close', 'Open']].max(axis=1)
        df['Lower_Shadow'] = df[['Close', 'Open']].min(axis=1) - df['Low']
        
        prominence_high = df['High'].std() * 0.3
        prominence_low = df['Low'].std() * 0.3
        peaks, _ = find_peaks(df['High'].values, distance=10, prominence=prominence_high)
        valleys, _ = find_peaks(-df['Low'].values, distance=10, prominence=prominence_low)
        
        return df, peaks, valleys
    except Exception:
        return None

# ==========================================
# 5. 메인 대시보드 출력
# ==========================================
result = load_and_calc_data(ticker, period)

if result is not None:
    df, peaks, valleys = result
    
    # --- 상단 메트릭 ---
    curr_p = df['Close'].iloc[-1]
    prev_p = df['Close'].iloc[-2]
    change = ((curr_p - prev_p) / prev_p) * 100

    col1, col2, col3 = st.columns(3)
    price_format = f"{curr_p:,.0f}" if curr_p > 1000 else f"{curr_p:,.2f}"
    col1.metric(f"{user_input} 현재가", price_format, f"{change:+.2f}%")
    
    if buy_p > 0 and qty > 0:
        profit = ((curr_p - buy_p) / buy_p) * 100
        total_val = curr_p * qty
        col2.metric("보유 수익률", f"{profit:+.2f}%")
        col3.metric("평가 금액", f"{total_val:,.0f}")

    # --- AI 온도계 계산 ---
    ai_score = 50
    last_k = df['Stoch_K'].iloc[-1]
    if last_k < 20: ai_score += 20
    elif last_k > 80: ai_score -= 20
    if curr_p > df['MA20'].iloc[-1]: ai_score += 15
    else: ai_score -= 10
    if df['MACD_Hist'].iloc[-1] > 0: ai_score += 15
    else: ai_score -= 10
    ai_score = max(0, min(100, ai_score))

    # --- 탭 구성 ---
    tab1, tab2, tab3 = st.tabs(["📊 프리미엄 차트", "🧠 AI 리포트 & 온도계", "⚡ 실시간 시장 뉴스"])

    # [탭 1: 프리미엄 차트]
    with tab1:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.75, 0.25])
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="주가"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name="20일선", line=dict(color='orange', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], name="60일선", line=dict(color='cyan', width=1)), row=1, col=1)
        
        if len(peaks) > 0: fig.add_trace(go.Scatter(x=df.index[peaks], y=df['High'].iloc[peaks], mode='markers', marker=dict(color='red', size=8, symbol='triangle-down'), name="고점"), row=1, col=1)
        if len(valleys) > 0: fig.add_trace(go.Scatter(x=df.index[valleys], y=df['Low'].iloc[valleys], mode='markers', marker=dict(color='lime', size=8, symbol='triangle-up'), name="저점"), row=1, col=1)

        if len(peaks) >= 2: fig.add_trace(go.Scatter(x=df.index[peaks[-2:]], y=df['High'].iloc[peaks[-2:]], mode='lines', line=dict(color='pink', width=2, dash='dot'), name="저항선"), row=1, col=1)
        if len(valleys) >= 2: fig.add_trace(go.Scatter(x=df.index[valleys[-2:]], y=df['Low'].iloc[valleys[-2:]], mode='lines', line=dict(color='lightgreen', width=2, dash='dot'), name="지지선"), row=1, col=1)

        colors = ['red' if val < 0 else 'green' for val in df['MACD_Hist']]
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], name="MACD", marker_color=colors), row=2, col=1)
        
        # 모바일 환경을 고려하여 차트 높이를 700에서 550으로 줄여 스크롤 공간 확보
        fig.update_layout(height=550, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=5, r=5, t=10, b=10))
        
        # config 설정으로 모바일에서 차트 위를 터치해도 화면 스크롤이 가능하도록 조치
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # [탭 2: AI 리포트 & 온도계]
    with tab2:
        st.subheader("🌡️ AI 매수 매력도 온도계")
        
        if ai_score >= 70:
            status_text = "🟢 매수 기회 (좋음)"
            gauge_color = "green"
        elif ai_score >= 40:
            status_text = "🟡 중립 및 관망 (보통)"
            gauge_color = "yellow"
        else:
            status_text = "🔴 위험 및 매도 (나쁨)"
            gauge_color = "red"
            
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number", 
            value = ai_score,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': f"AI 퀀트 점수<br><span style='font-size:0.7em;color:{gauge_color}'>{status_text}</span>", 'font': {'size': 20, 'color': 'white'}},
            gauge = {
                'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white"},
                'bar': {'color': gauge_color}, 
                'bgcolor': "black", 
                'borderwidth': 2, 
                'bordercolor': "gray",
                'steps': [
                    {'range': [0, 40], 'color': "rgba(255,0,0,0.3)"}, 
                    {'range': [40, 70], 'color': "rgba(255,255,0,0.3)"}, 
                    {'range': [70, 100], 'color': "rgba(0,255,0,0.3)"}
                ]
            }
        ))
        # 모바일에 맞게 온도계 높이와 마진을 축소
        fig_gauge.update_layout(height=280, margin=dict(l=10, r=10, t=50, b=10), paper_bgcolor="#0E1117", font={'color': "white"})
        st.plotly_chart(fig_gauge, use_container_width=True, config={'displayModeBar': False})

        st.markdown("<div class='ai-report'>", unsafe_allow_html=True)
        st.markdown(f"### 💡 {user_input} 상세 퀀트 분석")
        
        st.markdown("#### 📐 추세 및 파동 (엘리어트 & 빗각)")
        if len(peaks) >= 2 and len(valleys) >= 2:
            peak_slope = df['High'].iloc[peaks[-1]] - df['High'].iloc[peaks[-2]]
            valley_slope = df['Low'].iloc[valleys[-1]] - df['Low'].iloc[valleys[-2]]
            if peak_slope < 0 and valley_slope > 0: st.warning("⚠️ **[대칭 삼각수렴]** 고점은 낮아지고 저점은 높아집니다. 곧 방향성이 터질 수 있습니다.")
            elif peak_slope > 0 and valley_slope > 0: st.success("✅ **[상승 채널/파동]** 고점과 저점을 지속적으로 높여가는 상승 국면입니다.")
            elif peak_slope < 0 and valley_slope < 0: st.error("🚨 **[하락 채널/파동]** 고점과 저점이 모두 낮아지고 있습니다. 빗각 돌파를 기다리세요.")
            else: st.write("현재 명확한 채널 방향성보다는 박스권 패턴을 보이고 있습니다.")
        else: st.write("파동을 분석하기에 데이터가 부족합니다.")

        st.markdown("#### 🕯️ 최근 캔들 패턴")
        recent_candle = df.iloc[-1]
        body_size = recent_candle['Body']
        if recent_candle['Lower_Shadow'] > body_size * 2 and recent_candle['Upper_Shadow'] < body_size: st.write("🔨 **[망치형 캔들 포착]** 아래꼬리가 긴 망치형 캔들이 발생했습니다. 바닥권 반등 신호일 수 있습니다.")
        elif body_size < (recent_candle['High'] - recent_candle['Low']) * 0.1: st.write("➕ **[도지형 캔들 포착]** 매수/매도세가 맞서는 도지 캔들이 떴습니다. 단기 전환점일 수 있습니다.")
        else: st.write("현재 특이한 반전 캔들 패턴은 관찰되지 않습니다.")

        st.markdown("#### 📊 보조지표 시그널")
        if last_k > 80: st.warning(f"• **스토캐스틱**: {last_k:.1f} (과매수 구간)")
        elif last_k < 20: st.success(f"• **스토캐스틱**: {last_k:.1f} (과매도 구간)")
        
        if df['MACD_Hist'].iloc[-1] > 0 and df['MACD_Hist'].iloc[-2] < 0: st.success("• **MACD**: 골든크로스 매수 신호 발생")
        elif df['MACD_Hist'].iloc[-1] < 0 and df['MACD_Hist'].iloc[-2] > 0: st.error("• **MACD**: 데드크로스 매도 신호 발생")
        
        if curr_p > df['MA20'].iloc[-1]: st.write("• **이동평균선**: 주가가 20일선 위에 있어 상승 흐름 유효")
        else: st.write("• **이동평균선**: 주가가 20일선 아래에 있어 하방 압력 존재")
        st.markdown("</div>", unsafe_allow_html=True)

    # [탭 3: 실시간 시장 뉴스 (모바일 최적화)]
    with tab3:
        st.markdown("### ⚡ 실시간 마켓 레이더")
        st.caption("가장 빠르고 주가에 영향을 줄 수 있는 뉴스를 업데이트합니다.")
        
        # 모바일에서는 st.columns가 자동으로 세로로 길게 접힙니다 (반응형 작동)
        col_news1, col_news2 = st.columns(2)
        
        with col_news1:
            st.markdown("#### 🌐 국내외 증시 핫이슈")
            market_news = get_market_news()
            if market_news:
                for item in market_news:
                    st.markdown(f"""
                    <div class='news-box news-box-market'>
                        <a href='{item['link']}' target='_blank' class='news-title'>{item['title']}</a>
                        <div class='news-date'>🕒 {item['date']}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else: st.info("증시 주요 뉴스를 불러오지 못했습니다.")

        with col_news2:
            st.markdown(f"#### 🎯 {user_input} 관련 뉴스")
            ticker_news = get_latest_news(user_input)
            if ticker_news:
                for item in ticker_news:
                    st.markdown(f"""
                    <div class='news-box'>
                        <a href='{item['link']}' target='_blank' class='news-title'>{item['title']}</a>
                        <div class='news-date'>🕒 {item['date']}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else: st.info(f"현재 '{user_input}'와(과) 관련된 최신 뉴스가 없습니다.")

else:
    st.error("데이터를 불러오지 못했습니다. 종목을 다시 확인해주세요.")
