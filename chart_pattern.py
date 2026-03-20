import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import feedparser
import urllib.parse

# ==========================================
# 1. UI/UX 전면 개편 (Custom CSS & Page Config)
# ==========================================
st.set_page_config(layout="wide", page_title="AI 프리미엄 퀀트", page_icon="👑")
st.markdown("""
    <style>
    /* 프리미엄 다크 테마 & 카드 UI */
    .main { background-color: #0E1117; color: #FFFFFF; }
    .stTabs [data-baseweb="tab-list"] { gap: 20px; }
    .stTabs [data-baseweb="tab"] { font-size: 1.2rem; font-weight: bold; color: #888; }
    .stTabs [aria-selected="true"] { color: #00FF00 !important; border-bottom-color: #00FF00 !important; }
    .ai-report { background: linear-gradient(145deg, #1e1e1e, #2d2d2d); padding: 20px; border-radius: 15px; border-left: 5px solid #00FF00; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
    div[data-testid="stMetricValue"] { font-size: 1.8rem !important; font-weight: 800; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 견고한 설정 & 예외 처리 (Stability)
# ==========================================
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2933/2933116.png", width=50)
st.sidebar.title("설정 패널")

# 관심 종목 퀵버튼 (원하는 종목으로 즉시 이동)
st.sidebar.subheader("⭐ 관심 종목 퀵뷰")
quick_tickers = ["005930.KS", "ONDS", "042520.KQ", "042110.KQ"]
selected_quick = st.sidebar.selectbox("빠른 선택", ["직접 입력..."] + quick_tickers)

if selected_quick != "직접 입력...":
    default_ticker = selected_quick
else:
    default_ticker = "005930.KS"

ticker = st.sidebar.text_input("종목 코드 검색", value=default_ticker).upper()
period = st.sidebar.select_slider("조회 기간", options=["1mo", "3mo", "6mo", "1y", "2y"], value="6mo")

@st.cache_data(ttl=60, show_spinner=False)
def load_and_calc_data(symbol, p):
    try:
        df = yf.download(symbol, period=p, interval="1d", auto_adjust=True, progress=False)
        if df.empty or len(df) < 20: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
        
        # [기술적 분석 정교화]
        # 1. 이동평균선
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        
        # 2. MACD
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['Signal']
        
        # 3. Stochastic Oscillator
        low14 = df['Low'].rolling(14).min()
        high14 = df['High'].rolling(14).max()
        df['Stoch_K'] = 100 * ((df['Close'] - low14) / (high14 - low14))
        df['Stoch_D'] = df['Stoch_K'].rolling(3).mean()
        
        # 4. RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / loss)))
        
        return df.dropna()
    except Exception: return None

with st.spinner('AI가 데이터를 수집하고 연산 중입니다...'):
    df = load_and_calc_data(ticker, period)

if df is not None:
    curr_p = df['Close'].iloc[-1]
    prev_p = df['Close'].iloc[-2]
    change_pct = ((curr_p - prev_p) / prev_p) * 100
    is_us = not (ticker.endswith(".KS") or ticker.endswith(".KQ"))
    unit = "$" if is_us else "₩"
    fmt = ",.2f" if is_us else ",.0f"

    st.header(f"📊 {ticker} 통합 분석")
    
    # 상단 핵심 메트릭 (열 구성)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("현재가", f"{unit}{curr_p:{fmt}}", f"{change_pct:.2f}%")
    m2.metric("단기 추세 (MA5)", "상승" if curr_p > df['MA5'].iloc[-1] else "하락", "지지" if curr_p > df['MA20'].iloc[-1] else "이탈")
    m3.metric("RSI (과열도)", f"{df['RSI'].iloc[-1]:.1f}", "과매도" if df['RSI'].iloc[-1]<30 else "과매수" if df['RSI'].iloc[-1]>70 else "중립")
    m4.metric("MACD 시그널", "매수 우위" if df['MACD'].iloc[-1] > df['Signal'].iloc[-1] else "매도 우위")

    st.markdown("<br>", unsafe_allow_html=True)

    # ==========================================
    # 3. 탭 시스템 도입 (Dashboarding)
    # ==========================================
    tab1, tab2, tab3 = st.tabs(["📈 프로페셔널 차트", "🤖 AI 자동 리포트", "📰 실시간 시장 뉴스"])

    with tab1:
        # 매물대(Volume Profile) 계산
        y_bins = pd.cut(df['Close'], bins=20)
        vp = df.groupby(y_bins)['Volume'].sum()
        vp_y = [b.mid for b in vp.index]
        vp_x = vp.values
        vp_x_scaled = vp_x / vp_x.max() * (len(df) * 0.3) # 차트의 30% 영역까지만 표시

        # 3단 복합 차트 (캔들+이평+매물대 / 거래량+MACD / 스토캐스틱)
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, 
                            row_heights=[0.6, 0.2, 0.2])
        
        # Row 1: 캔들 & 이평선
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='주가'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='#FFD700', width=1.5), name='5일선'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#FF00FF', width=2), name='20일선'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], line=dict(color='#00FFFF', width=2), name='60일선'), row=1, col=1)
        
        # Row 1: 매물대 (가로 막대그래프 중첩)
        fig.add_trace(go.Bar(x=df.index[:len(vp_x_scaled)], y=vp_y, orientation='h', marker_color='rgba(255,255,255,0.1)', name='매물대', hoverinfo='skip'), row=1, col=1)

        # Row 2: 거래량 & MACD
        colors = ['red' if o < c else 'blue' for o, c in zip(df['Open'], df['Close'])]
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], marker_color=colors, name='MACD 히스토그램'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='yellow', width=1), name='MACD'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Signal'], line=dict(color='orange', width=1), name='Signal'), row=2, col=1)

        # Row 3: 스토캐스틱
        fig.add_trace(go.Scatter(x=df.index, y=df['Stoch_K'], line=dict(color='cyan', width=1.5), name='Stoch %K'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Stoch_D'], line=dict(color='magenta', width=1.5), name='Stoch %D'), row=3, col=1)
        # 스토캐스틱 과매수/과매도 기준선
        fig.add_hline(y=80, line_dash="dash", line_color="red", opacity=0.5, row=3, col=1)
        fig.add_hline(y=20, line_dash="dash", line_color="green", opacity=0.5, row=3, col=1)

        fig.update_layout(height=900, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False, margin=dict(l=10, r=10, t=10, b=10))
        
        # 💡 모바일 스크롤 튕김 방지 (터치 줌/이동 잠금)
        fig.update_xaxes(fixedrange=True)
        fig.update_yaxes(fixedrange=True)
        
        # config 설정을 통해 모바일 터치 최적화
        st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': False, 'displayModeBar': False})

    with tab2:
        # ==========================================
        # 4. AI 기반 자동 요약 리포트 생성
        # ==========================================
        last_macd = df['MACD'].iloc[-1]
        last_sig = df['Signal'].iloc[-1]
        last_k = df['Stoch_K'].iloc[-1]
        last_d = df['Stoch_D'].iloc[-1]
        
        ai_summary = f"### 💡 {ticker} AI 퀀트 분석 브리핑\n\n"
        
        # 추세 판독
        if curr_p > df['MA20'].iloc[-1] and df['MA5'].iloc[-1] > df['MA20'].iloc[-1]:
            ai_summary += "**[추세]** 완연한 **상승 정배열** 구간입니다. 20일선 지지를 받으며 추세가 살아있습니다.\n"
        elif curr_p < df['MA20'].iloc[-1]:
            ai_summary += "**[추세]** 현재 20일선 아래에서 **조정 또는 하락** 추세에 있습니다. 리스크 관리가 필요합니다.\n"
        else:
            ai_summary += "**[추세]** 방향성을 탐색하는 **횡보(박스권)** 흐름을 보이고 있습니다.\n"

        # 타이밍 판독 (MACD & Stochastic)
        if last_macd > last_sig and last_macd > 0:
            ai_summary += "**[타이밍]** MACD가 영선 위에서 골든크로스를 유지 중입니다. **강한 매수 심리**가 작용하고 있습니다.\n"
        elif last_k < 20 and last_k > last_d:
            ai_summary += "**[타이밍]** 스토캐스틱 침체권에서 %K가 %D를 상향 돌파했습니다. **단기 반등을 노려볼 만한 바닥권**입니다.\n"
        elif last_k > 80:
            ai_summary += "**[타이밍]** 스토캐스틱 과매수 구간(80 이상)에 진입했습니다. **추격 매수는 자제하고 익절을 고려**할 시점입니다.\n"
        
        # 매물대 코멘트
        max_vol_price = vp_y[np.argmax(vp_x)]
        ai_summary += f"**[매물대]** 가장 강력한 거래량이 몰려있는 가격대는 **{unit}{max_vol_price:{fmt}}** 부근입니다. 이 가격대가 핵심 지지/저항선으로 작용할 것입니다."

        st.markdown(f'<div class="ai-report">{ai_summary}</div>', unsafe_allow_html=True)
        
        st.markdown("---")
        st.subheader("🧮 나의 포트폴리오 수익률 시뮬레이터")
        col_calc1, col_calc2 = st.columns(2)
        with col_calc1:
            buy_p = st.number_input("평균 단가 입력", value=0.0, step=0.1)
        with col_calc2:
            qty = st.number_input("보유 수량 입력", value=0, step=1)
            
        if buy_p > 0 and qty > 0:
            profit = (curr_p - buy_p) * qty
            rate = ((curr_p - buy_p) / buy_p) * 100
            st.success(f"현재 평가 손익: **{unit}{profit:{fmt}}** ({rate:.2f}%)")

    with tab3:
        # 뉴스 탭
        q = urllib.parse.quote(ticker.split('.')[0])
        feed = feedparser.parse(f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko")
        if feed.entries:
            for entry in feed.entries[:8]:
                st.markdown(f"🔹 [{entry.title.rsplit(' - ', 1)[0]}]({entry.link})")
        else:
            st.info("현재 수집된 최신 뉴스가 없습니다.")

else:
    st.error("""
    **데이터를 불러오지 못했습니다.** 1. 종목 코드가 정확한지 확인해 주세요. (예: 005930.KS)
    2. 상장 폐지되었거나 최근 상장하여 데이터가 부족한 종목일 수 있습니다.
    3. 일시적인 야후 파이낸스 서버 오류일 수 있으니 잠시 후 새로고침 해보세요.
    """)
