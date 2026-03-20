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
st.set_page_config(layout="wide", page_title="AI 프리미엄 퀀트", page_icon="👑")

st.markdown("""
    <style>
    .main { background-color: #0E1117; color: #FFFFFF; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { font-size: 1.1rem; font-weight: bold; color: #888; }
    .stTabs [aria-selected="true"] { color: #00FF00 !important; border-bottom-color: #00FF00 !important; }
    .ai-report { background: #1E1E1E; padding: 20px; border-radius: 10px; border-left: 5px solid #00FF00; margin-bottom: 20px; line-height: 1.6;}
    .news-box { background: #1a1c24; padding: 15px; border-radius: 8px; margin-bottom: 10px; border-left: 3px solid #00FF00; word-break: keep-all;}
    .news-box-market { border-left: 3px solid #00BFFF; }
    .news-title { font-size: 1.0rem; font-weight: bold; color: #ffffff; text-decoration: none;}
    .news-title:hover { color: #ff4b4b; text-decoration: underline;}
    .news-date { font-size: 0.8rem; color: #aaaaaa; margin-top: 5px;}
    .price-box { background: #2b2b36; padding: 15px; border-radius: 8px; text-align: center; margin-bottom: 15px; border: 1px solid #444;}
    div[data-testid="stMetricValue"] { font-size: 1.6rem !important; font-weight: 800; color: #00FF00; }

    @media (max-width: 768px) {
        .stTabs [data-baseweb="tab"] { font-size: 0.85rem; padding-left: 5px; padding-right: 5px; }
        div[data-testid="stMetricValue"] { font-size: 1.3rem !important; }
        .ai-report { padding: 15px; font-size: 0.95rem; }
        .news-box { padding: 12px; }
        .news-title { font-size: 0.95rem; }
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
    query_clean = query.replace(" ", "").upper()
    match = krx_df[krx_df['Name'].str.replace(" ", "").str.upper() == query_clean]
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
# 3. 사이드바 설정
# ==========================================
st.sidebar.title("⚙️ 시스템 설정")
quick_tickers = ["직접 입력...", "삼성전자", "SK하이닉스", "풍산", "한화솔루션", "테슬라", "엔비디아"]
selected_quick = st.sidebar.selectbox("⭐ 관심 종목 퀵뷰", quick_tickers)
default_input = "SK하이닉스" if selected_quick == "직접 입력..." else selected_quick
user_input = st.sidebar.text_input("종목명/코드 검색", value=default_input)

ticker = get_ticker_from_name(user_input)
st.sidebar.caption(f"🔍 자동 변환된 코드: **{ticker}**")
period = st.sidebar.select_slider("조회 기간", options=["3mo", "6mo", "1y", "2y"], value="6mo")

st.sidebar.markdown("---")
st.sidebar.subheader("🧮 포트폴리오 시뮬레이터")
buy_p = st.sidebar.number_input("평균 단가", value=0.0, step=0.1)
qty = st.sidebar.number_input("보유 수량", value=0, step=1)

# ==========================================
# 4. 퀀트 데이터 & 백테스팅 엔진 코어
# ==========================================
@st.cache_data(ttl=60)
def load_and_calc_data(symbol, p):
    try:
        today = datetime.today()
        days_map = {"3mo": 90, "6mo": 180, "1y": 365, "2y": 730}
        start_date = today - timedelta(days=days_map.get(p, 180))
        
        df = fdr.DataReader(symbol, start_date)
        if df.empty or len(df) < 30: return None
        
        # 기본 지표
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
        
        # --- 백테스팅을 위한 과거 AI 점수 일괄 계산 ---
        df['AI_Score'] = 50
        df.loc[df['Stoch_K'] < 20, 'AI_Score'] += 20
        df.loc[df['Stoch_K'] > 80, 'AI_Score'] -= 20
        df.loc[df['Close'] > df['MA20'], 'AI_Score'] += 15
        df.loc[df['Close'] <= df['MA20'], 'AI_Score'] -= 10
        df.loc[df['MACD_Hist'] > 0, 'AI_Score'] += 15
        df.loc[df['MACD_Hist'] <= 0, 'AI_Score'] -= 10
        df['AI_Score'] = df['AI_Score'].clip(0, 100)
        
        # AI 시그널: 70 이상이면 매수(포지션 1), 40 이하면 매도(포지션 0) 유지
        df['Position'] = np.nan
        df.loc[df['AI_Score'] >= 70, 'Position'] = 1
        df.loc[df['AI_Score'] <= 40, 'Position'] = 0
        df['Position'] = df['Position'].ffill().fillna(0) # 신호 유지
        
        # 수익률 계산
        df['Daily_Return'] = df['Close'].pct_change()
        # 포지션은 전날 종가 기준 신호로 오늘 수익률을 먹음 (미래 참조 방지)
        df['Strategy_Return'] = df['Position'].shift(1) * df['Daily_Return']
        
        # 누적 수익률 (Base 100)
        df['Cum_Market'] = (1 + df['Daily_Return']).cumprod() * 100
        df['Cum_Strategy'] = (1 + df['Strategy_Return']).cumprod() * 100
        
        return df, peaks, valleys
    except Exception:
        return None

# ==========================================
# 5. 메인 대시보드 출력
# ==========================================
result = load_and_calc_data(ticker, period)

if result is not None:
    df, peaks, valleys = result
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

    # --- 목표가 / 손절가 계산 로직 ---
    # 목표가: 최근 고점 파동 (없으면 현재가 +10%)
    recent_peak = df['High'].iloc[peaks[-1]] if len(peaks) > 0 else curr_p * 1.10
    target_price = max(recent_peak, curr_p * 1.05) # 최소 5% 이상 목표
    
    # 손절가: 최근 저점 파동 또는 20일선 중 더 가까운 것
    recent_valley = df['Low'].iloc[valleys[-1]] if len(valleys) > 0 else curr_p * 0.90
    ma20_price = df['MA20'].iloc[-1]
    stop_loss = max(min(recent_valley, ma20_price), curr_p * 0.85) # 최후의 마지노선 15% 하락
    # 현재가보다 높은 손절가 방지
    if stop_loss >= curr_p: stop_loss = curr_p * 0.95 

    ai_score = df['AI_Score'].iloc[-1]

    # --- 탭 구성 (백테스팅 탭 추가) ---
    tab1, tab2, tab3, tab4 = st.tabs(["📊 프리미엄 차트", "🧠 AI 리포트 & 목표가", "📉 AI 백테스팅", "⚡ 마켓 뉴스"])

    # [탭 1: 프리미엄 차트]
    with tab1:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.75, 0.25])
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="주가"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name="20일선", line=dict(color='orange', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], name="60일선", line=dict(color='cyan', width=1)), row=1, col=1)
        
        if len(peaks) > 0: fig.add_trace(go.Scatter(x=df.index[peaks], y=df['High'].iloc[peaks], mode='markers', marker=dict(color='red', size=8, symbol='triangle-down'), name="고점"), row=1, col=1)
        if len(valleys) > 0: fig.add_trace(go.Scatter(x=df.index[valleys], y=df['Low'].iloc[valleys], mode='markers', marker=dict(color='lime', size=8, symbol='triangle-up'), name="저점"), row=1, col=1)

        # 차트 위에 손절가/목표가 수평선 표시
        fig.add_hline(y=target_price, line_dash="dash", line_color="rgba(0, 255, 0, 0.5)", annotation_text="1차 목표가", row=1, col=1)
        fig.add_hline(y=stop_loss, line_dash="dash", line_color="rgba(255, 0, 0, 0.5)", annotation_text="손절 기준선", row=1, col=1)

        colors = ['red' if val < 0 else 'green' for val in df['MACD_Hist']]
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], name="MACD", marker_color=colors), row=2, col=1)
        
        fig.update_layout(height=550, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=5, r=5, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # [탭 2: AI 리포트 & 목표가/손절가]
    with tab2:
        # 온도계
        if ai_score >= 70: status_text, gauge_color = "🟢 매수 기회 (좋음)", "green"
        elif ai_score >= 40: status_text, gauge_color = "🟡 중립 및 관망 (보통)", "yellow"
        else: status_text, gauge_color = "🔴 위험 및 매도 (나쁨)", "red"
            
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number", value = ai_score, domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': f"AI 퀀트 점수<br><span style='font-size:0.7em;color:{gauge_color}'>{status_text}</span>", 'font': {'size': 20, 'color': 'white'}},
            gauge = {
                'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white"},
                'bar': {'color': gauge_color}, 'bgcolor': "black", 'borderwidth': 2, 'bordercolor': "gray",
                'steps': [{'range': [0, 40], 'color': "rgba(255,0,0,0.3)"}, {'range': [40, 70], 'color': "rgba(255,255,0,0.3)"}, {'range': [70, 100], 'color': "rgba(0,255,0,0.3)"}]
            }
        ))
        fig_gauge.update_layout(height=280, margin=dict(l=10, r=10, t=50, b=10), paper_bgcolor="#0E1117", font={'color': "white"})
        st.plotly_chart(fig_gauge, use_container_width=True, config={'displayModeBar': False})

        # 목표가 & 손절가 시각화 박스
        st.markdown(f"""
        <div style='display: flex; gap: 10px; margin-bottom: 20px;'>
            <div class='price-box' style='flex: 1;'>
                <div style='color:#aaaaaa; font-size: 0.9rem;'>🎯 AI 1차 목표가 (저항선)</div>
                <div style='color:#00FF00; font-size: 1.5rem; font-weight: bold;'>{target_price:,.0f} 원</div>
            </div>
            <div class='price-box' style='flex: 1;'>
                <div style='color:#aaaaaa; font-size: 0.9rem;'>🛡️ 기계적 손절가 (지지선)</div>
                <div style='color:#FF4B4B; font-size: 1.5rem; font-weight: bold;'>{stop_loss:,.0f} 원</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

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

        st.markdown("#### 📊 보조지표 시그널 요약")
        if df['Stoch_K'].iloc[-1] > 80: st.warning(f"• **스토캐스틱**: 과매수 구간 (단기 조정 유의)")
        elif df['Stoch_K'].iloc[-1] < 20: st.success(f"• **스토캐스틱**: 과매도 구간 (반등 가능성)")
        if df['MACD_Hist'].iloc[-1] > 0 and df['MACD_Hist'].iloc[-2] < 0: st.success("• **MACD**: 골든크로스 매수 신호 발생")
        elif df['MACD_Hist'].iloc[-1] < 0 and df['MACD_Hist'].iloc[-2] > 0: st.error("• **MACD**: 데드크로스 매도 신호 발생")
        st.markdown("</div>", unsafe_allow_html=True)

    # [탭 3: AI 백테스팅 시뮬레이터]
    with tab3:
        st.subheader("📉 AI 퀀트 전략 백테스팅")
        st.write(f"과거 **{period}** 동안, 이 퀀트 알고리즘(70점 이상 매수, 40점 이하 관망)대로 매매했다면 결과가 어땠을까요?")

        final_market = df['Cum_Market'].iloc[-1] - 100
        final_strategy = df['Cum_Strategy'].iloc[-1] - 100
        
        col_bt1, col_bt2 = st.columns(2)
        col_bt1.metric("존버(단순 보유) 수익률", f"{final_market:+.2f}%")
        col_bt2.metric("AI 퀀트 매매 수익률", f"{final_strategy:+.2f}%", f"{(final_strategy - final_market):+.2f}%p (초과 수익)")

        fig_bt = go.Figure()
        fig_bt.add_trace(go.Scatter(x=df.index, y=df['Cum_Market'], mode='lines', name="단순 보유 (Buy & Hold)", line=dict(color='gray', width=2)))
        fig_bt.add_trace(go.Scatter(x=df.index, y=df['Cum_Strategy'], mode='lines', name="AI 퀀트 매매", line=dict(color='#00FF00', width=3)))
        
        # 매수/매도 타이밍 배경색 표시
        buy_signals = df[df['Position'] == 1].index
        fig_bt.update_layout(height=400, template="plotly_dark", title="수익률 비교 곡선 (기본금 100 기준)", margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig_bt, use_container_width=True)
        
        st.info("💡 **백테스팅 조건:** AI 점수 70점 돌파 시 매수, 40점 붕괴 시 현금 보유(매도). 슬리피지와 수수료는 제외된 데이터입니다.")

    # [탭 4: 실시간 시장 뉴스]
    with tab4:
        st.subheader("⚡ 실시간 마켓 레이더")
        col_news1, col_news2 = st.columns(2)
        with col_news1:
            st.markdown("#### 🌐 증시 핫이슈")
            for item in get_market_news():
                st.markdown(f"<div class='news-box news-box-market'><a href='{item['link']}' target='_blank' class='news-title'>{item['title']}</a><div class='news-date'>🕒 {item['date']}</div></div>", unsafe_allow_html=True)
        with col_news2:
            st.markdown(f"#### 🎯 {user_input} 뉴스")
            ticker_news = get_latest_news(user_input)
            if ticker_news:
                for item in ticker_news:
                    st.markdown(f"<div class='news-box'><a href='{item['link']}' target='_blank' class='news-title'>{item['title']}</a><div class='news-date'>🕒 {item['date']}</div></div>", unsafe_allow_html=True)
            else: st.info(f"관련 뉴스가 없습니다.")

else:
    st.error("데이터를 불러오지 못했습니다. 종목을 다시 확인해주세요.")
