import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import feedparser
import urllib.parse

# ==========================================
# 1. UI/UX 전면 개편 & 모바일 최적화
# ==========================================
st.set_page_config(layout="wide", page_title="AI 프리미엄 퀀트", page_icon="👑")
st.markdown("""
    <style>
    .main { background-color: #0E1117; color: #FFFFFF; padding-top: 1rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { font-size: 1.1rem; font-weight: bold; color: #888; }
    .stTabs [aria-selected="true"] { color: #00FF00 !important; border-bottom-color: #00FF00 !important; }
    .ai-report { background: #1E1E1E; padding: 20px; border-radius: 10px; border-left: 5px solid #00FF00; margin-bottom: 20px;}
    div[data-testid="stMetricValue"] { font-size: 1.5rem !important; font-weight: 800; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 사이드바: 설정 및 퀵뷰
# ==========================================
st.sidebar.title("⚙️ 시스템 설정")

# 관심 종목 퀵버튼
st.sidebar.subheader("⭐ 관심 종목 퀵뷰")
quick_tickers = ["직접 입력...", "005930.KS", "ONDS", "042520.KQ", "432410.KS"]
selected_quick = st.sidebar.selectbox("빠른 선택", quick_tickers)

default_ticker = "005930.KS" if selected_quick == "직접 입력..." else selected_quick
ticker = st.sidebar.text_input("종목 코드 검색", value=default_ticker).upper()
period = st.sidebar.select_slider("조회 기간", options=["1mo", "3mo", "6mo", "1y"], value="6mo")

st.sidebar.markdown("---")
st.sidebar.subheader("🧮 포트폴리오 시뮬레이터")
buy_p = st.sidebar.number_input("평균 단가", value=0.0, step=0.1)
qty = st.sidebar.number_input("보유 수량", value=0, step=1)

# ==========================================
# 3. 데이터 수집 및 퀀트 연산 (캐싱)
# ==========================================
@st.cache_data(ttl=60, show_spinner=False)
def load_and_calc_data(symbol, p):
    try:
        df = yf.download(symbol, period=p, interval="1d", auto_adjust=True, progress=False)
        if df.empty or len(df) < 20: return None, None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
        
        # 기본 이평선
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        
        # MACD
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['Signal']
        
        # Stochastic & RSI
        df['Stoch_K'] = 100 * ((df['Close'] - df['Low'].rolling(14).min()) / (df['High'].rolling(14).max() - df['Low'].rolling(14).min()))
        df['Stoch_D'] = df['Stoch_K'].rolling(3).mean()
        
        delta = df['Close'].diff()
        rs = (delta.where(delta > 0, 0)).rolling(14).mean() / (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # 기업 재무 정보 (안정성을 위해 에러 처리)
        info = yf.Ticker(symbol).info
        return df.dropna(), info
    except Exception: return None, None

with st.spinner('AI가 데이터를 연산 중입니다...'):
    df, info = load_and_calc_data(ticker, period)

# ==========================================
# 4. 메인 대시보드 화면
# ==========================================
if df is not None:
    curr_p = df['Close'].iloc[-1]
    change_pct = ((curr_p - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100
    is_us = not (ticker.endswith(".KS") or ticker.endswith(".KQ"))
    unit = "$" if is_us else "₩"
    fmt = ",.2f" if is_us else ",.0f"

    st.header(f"📊 {ticker} 통합 분석")
    
    # 핵심 지표 메트릭 (모바일 고려 2열씩)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("현재가", f"{unit}{curr_p:{fmt}}", f"{change_pct:.2f}%")
    if buy_p > 0 and qty > 0:
        profit = (curr_p - buy_p) * qty
        m2.metric("내 평가손익", f"{unit}{profit:{fmt}}", f"{((curr_p - buy_p)/buy_p)*100:.2f}%")
    else:
        m2.metric("추세 (MA20)", "상승 지지" if curr_p > df['MA20'].iloc[-1] else "하락 이탈")
    m3.metric("RSI (심리도)", f"{df['RSI'].iloc[-1]:.1f}")
    m4.metric("MACD", "매수 우위" if df['MACD'].iloc[-1] > df['Signal'].iloc[-1] else "매도 우위")

    st.markdown("---")

    # 4대 탭 시스템
    tab1, tab2, tab3, tab4 = st.tabs(["📈 프로 차트", "🧭 AI 온도계", "🏢 기업 재무", "📰 뉴스"])

    with tab1:
        st.caption("💡 화면을 스크롤해도 차트가 확대되지 않습니다. 안심하고 스크롤하세요!")
        
        # 자동 지지선/저항선 (최근 60일 기준 최고/최저점)
        recent_high = df['High'][-60:].max()
        recent_low = df['Low'][-60:].min()

        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])
        
        # [1] 캔들 & 이평선 & 자동 지지/저항선
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='주가'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='yellow', width=1.5), name='5일선'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='magenta', width=2), name='20일선'), row=1, col=1)
        fig.add_hline(y=recent_high, line_dash="dash", line_color="red", annotation_text="강력 저항선", row=1, col=1)
        fig.add_hline(y=recent_low, line_dash="dash", line_color="green", annotation_text="강력 지지선", row=1, col=1)

        # [2] 거래량 & MACD
        v_colors = ['#FF4136' if o < c else '#0074D9' for o, c in zip(df['Open'], df['Close'])]
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], marker_color=v_colors, name='MACD Hist'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='yellow', width=1), name='MACD'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Signal'], line=dict(color='orange', width=1), name='Signal'), row=2, col=1)

        # [3] 스토캐스틱 (타점 잡기)
        fig.add_trace(go.Scatter(x=df.index, y=df['Stoch_K'], line=dict(color='cyan', width=1.5), name='%K'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Stoch_D'], line=dict(color='magenta', width=1.5), name='%D'), row=3, col=1)
        fig.add_hline(y=80, line_dash="dot", line_color="red", row=3, col=1)
        fig.add_hline(y=20, line_dash="dot", line_color="green", row=3, col=1)

        # ⛔ 모바일 스크롤 튕김 완벽 방지 세팅
        fig.update_layout(height=700, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False, margin=dict(l=0, r=0, t=10, b=0))
        fig.update_xaxes(fixedrange=True) # 가로 줌 잠금
        fig.update_yaxes(fixedrange=True) # 세로 줌 잠금
        
        # config로 터치 이벤트 최적화
        st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': False, 'displayModeBar': False})

    with tab2:
        # AI 투자 온도계 알고리즘 계산
        score = 50
        if df['RSI'].iloc[-1] < 40: score += 20
        elif df['RSI'].iloc[-1] > 70: score -= 20
        if df['MACD'].iloc[-1] > df['Signal'].iloc[-1]: score += 15
        else: score -= 15
        if curr_p > df['MA20'].iloc[-1]: score += 15
        else: score -= 15
        
        score = max(0, min(100, score)) # 0~100 사이 유지
        
        if score >= 80: status, color = "강력 매수", "green"
        elif score >= 60: status, color = "매수 우위", "lightgreen"
        elif score >= 40: status, color = "중립 (관망)", "yellow"
        elif score >= 20: status, color = "매도 우위", "orange"
        else: status, color = "강력 매도", "red"

        # 게이지 차트 그리기
        gauge_fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = score,
            title = {'text': f"AI 종합 투자 매력도: {status}", 'font': {'size': 24}},
            gauge = {
                'axis': {'range': [0, 100]},
                'bar': {'color': "white"},
                'steps': [
                    {'range': [0, 20], 'color': "red"},
                    {'range': [20, 40], 'color': "orange"},
                    {'range': [40, 60], 'color': "yellow"},
                    {'range': [60, 80], 'color': "lightgreen"},
                    {'range': [80, 100], 'color': "green"}],
            }
        ))
        gauge_fig.update_layout(height=350, template="plotly_dark", margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(gauge_fig, use_container_width=True, config={'staticPlot': True})

        # 한글 AI 브리핑
        st.markdown(f"""
        <div class="ai-report">
        <b>[AI 차트 해석]</b><br>
        현재 주가는 <b>{unit}{curr_p:{fmt}}</b>이며, 최고점 저항선({unit}{recent_high:{fmt}})과 최저점 지지선({unit}{recent_low:{fmt}}) 사이에서 움직이고 있습니다. 종합 점수는 <b>{score}점({status})</b>으로, MACD와 스토캐스틱 지표를 종합할 때 현재는 {status} 전략이 유리한 구간입니다.
        </div>
        """, unsafe_allow_html=True)

    with tab3:
        # 기업 재무(Fundamentals) 정보 표시
        st.subheader(f"🏢 {info.get('shortName', ticker)} 기본 정보")
        if info and 'marketCap' in info:
            c1, c2 = st.columns(2)
            # 숫자가 너무 길면 보기 좋게 변환
            mcap = info.get('marketCap', 0)
            mcap_str = f"{mcap/1000000000000:.2f}조 원" if not is_us else f"${mcap/1000000000:.2f}B"
            
            c1.write(f"**시가총액:** {mcap_str}")
            c1.write(f"**PER (주가수익비율):** {info.get('trailingPE', 'N/A')}")
            c2.write(f"**PBR (주가순자산비율):** {info.get('priceToBook', 'N/A')}")
            c2.write(f"**배당률:** {info.get('dividendYield', 0)*100:.2f}%" if info.get('dividendYield') else "**배당률:** 없음")
            
            st.markdown("---")
            with st.expander("📖 기업 요약 설명 보기 (영문일 수 있음)"):
                st.write(info.get('longBusinessSummary', '기업 정보가 제공되지 않습니다.'))
        else:
            st.info("이 종목의 상세 재무 데이터를 불러올 수 없습니다.")

    with tab4:
        # 실시간 뉴스
        q = urllib.parse.quote(ticker.split('.')[0])
        feed = feedparser.parse(f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko")
        for entry in feed.entries[:10]:
            st.markdown(f"🔹 **[{entry.title.rsplit(' - ', 1)[0]}]({entry.link})**")
            st.caption(entry.published[5:16])
            st.divider()
else:
    st.error("데이터 로딩 실패. 종목 코드를 확인하거나 잠시 후 다시 시도해 주세요.")
