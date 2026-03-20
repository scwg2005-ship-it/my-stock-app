import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# ==========================================
# 1. UI/UX 설정 & 스타일링
# ==========================================
st.set_page_config(layout="wide", page_title="AI 프리미엄 퀀트", page_icon="👑")
st.markdown("""
    <style>
    .main { background-color: #0E1117; color: #FFFFFF; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { font-size: 1.1rem; font-weight: bold; color: #888; }
    .stTabs [aria-selected="true"] { color: #00FF00 !important; border-bottom-color: #00FF00 !important; }
    .ai-report { background: #1E1E1E; padding: 20px; border-radius: 10px; border-left: 5px solid #00FF00; margin-bottom: 20px;}
    div[data-testid="stMetricValue"] { font-size: 1.6rem !important; font-weight: 800; color: #00FF00; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 스마트 검색 엔진 (전종목 자동화)
# ==========================================
@st.cache_data(ttl=86400) # 하루에 한 번만 한국 거래소 종목 목록 업데이트
def load_krx_listing():
    return fdr.StockListing('KRX')

krx_df = load_krx_listing()

def get_ticker_from_name(query):
    query = query.strip()
    
    # 1. 이미 6자리 숫자인 경우 그대로 반환 (FDR은 한국 주식 검색시 .KS, .KQ 없이 숫자만 씁니다)
    if query.isdigit() and len(query) == 6:
        return query
        
    # 2. 한국 종목 이름으로 검색 (KRX 목록에서 찾기)
    match = krx_df[krx_df['Name'] == query]
    if not match.empty:
        return match.iloc[0]['Code']
        
    # 3. 미국 주식 등 자주 찾는 해외 주식 매핑 (미국은 영어 코드로 직접 검색)
    us_map = {
        "테슬라": "TSLA",
        "애플": "AAPL",
        "엔비디아": "NVDA",
        "마이크로소프트": "MSFT"
    }
    return us_map.get(query, query.upper())

# ==========================================
# 3. 사이드바 설정
# ==========================================
st.sidebar.title("⚙️ 시스템 설정")

quick_tickers = ["직접 입력...", "삼성전자", "풍산", "한화솔루션", "테슬라", "애플", "엔비디아", "쓰리빌리언"]
selected_quick = st.sidebar.selectbox("⭐ 관심 종목 퀵뷰", quick_tickers)

default_input = "풍산" if selected_quick == "직접 입력..." else selected_quick
user_input = st.sidebar.text_input("종목명/코드 검색", value=default_input)

ticker = get_ticker_from_name(user_input)
st.sidebar.caption(f"🔍 자동 변환된 코드: **{ticker}**")

period = st.sidebar.select_slider("조회 기간", options=["3mo", "6mo", "1y", "2y"], value="6mo")

st.sidebar.markdown("---")
st.sidebar.subheader("🧮 포트폴리오 계산기")
buy_p = st.sidebar.number_input("평균 단가", value=0.0, step=0.1)
qty = st.sidebar.number_input("보유 수량", value=0, step=1)

# ==========================================
# 4. 데이터 엔진 (FinanceDataReader 연동)
# ==========================================
@st.cache_data(ttl=60)
def load_and_calc_data(symbol, p):
    try:
        # FinanceDataReader를 위한 날짜 계산
        today = datetime.today()
        if p == "3mo": start_date = today - timedelta(days=90)
        elif p == "6mo": start_date = today - timedelta(days=180)
        elif p == "1y": start_date = today - timedelta(days=365)
        elif p == "2y": start_date = today - timedelta(days=730)
        else: start_date = today - timedelta(days=180)

        # 데이터 수집 (한국 주식은 네이버/KRX에서 정확한 종가로 가져옴)
        df = fdr.DataReader(symbol, start_date)
        
        if df.empty or len(df) < 20:
            return None
        
        # 이동평균선
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        
        # MACD
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['Signal']
        
        # 스토캐스틱
        low_min = df['Low'].rolling(window=14).min()
        high_max = df['High'].rolling(window=14).max()
        df['Stoch_K'] = 100 * ((df['Close'] - low_min) / (high_max - low_min))
        df['Stoch_D'] = df['Stoch_K'].rolling(window=3).mean()
        
        return df
    except Exception as e:
        return None

# ==========================================
# 5. 메인 화면 출력
# ==========================================
df = load_and_calc_data(ticker, period)

if df is not None:
    # 실시간 지표 요약
    curr_p = df['Close'].iloc[-1]
    prev_p = df['Close'].iloc[-2]
    change = ((curr_p - prev_p) / prev_p) * 100

    col1, col2, col3 = st.columns(3)
    # 1000 이상이면 소수점 제거 (한국 주식 최적화), 이하면 소수점 2자리 (미국 주식 최적화)
    price_format = f"{curr_p:,.0f}" if curr_p > 1000 else f"{curr_p:,.2f}"
    col1.metric(f"{user_input} 현재가", price_format, f"{change:+.2f}%")
    
    if buy_p > 0 and qty > 0:
        profit = ((curr_p - buy_p) / buy_p) * 100
        total_val = curr_p * qty
        col2.metric("보유 수익률", f"{profit:+.2f}%")
        col3.metric("평가 금액", f"{total_val:,.0f}")

    tab1, tab2 = st.tabs(["📊 인터랙티브 차트", "🧠 AI 전략 리포트"])

    with tab1:
        # 차트 생성 (주가 차트 + MACD 히스토그램)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                           vertical_spacing=0.05, row_heights=[0.7, 0.3])

        # 캔들스틱
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'],
                                   low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
        
        # 이평선
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name="MA20", line=dict(color='orange', width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], name="MA60", line=dict(color='cyan', width=1.5)), row=1, col=1)

        # MACD 히스토그램
        colors = ['red' if val < 0 else 'green' for val in df['MACD_Hist']]
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], name="MACD", marker_color=colors), row=2, col=1)

        fig.update_layout(height=650, template="plotly_dark", 
                          xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.markdown("<div class='ai-report'>", unsafe_allow_html=True)
        st.subheader("💡 퀀트 분석 결과")
        
        last_k = df['Stoch_K'].iloc[-1]
        last_d = df['Stoch_D'].iloc[-1]
        
        if last_k > 80:
            st.warning("⚠️ **과매수 상태**: 스토캐스틱 지표가 80을 초과했습니다. 단기 조정 및 차익 실현에 유의하세요.")
        elif last_k < 20:
            st.success("✅ **과매도 상태**: 지표가 20 미만입니다. 과도하게 하락한 상태로 기술적 반등 가능성이 높습니다.")
        else:
            st.info("ℹ️ **추세 지속**: 현재 중립 구간이며 기존 추세를 유지하고 있습니다.")
            
        if curr_p > df['MA20'].iloc[-1]:
            st.write("📈 현재 주가가 20일 이동평균선 위에 위치해 있어, **단기 상승 흐름**이 유효합니다.")
        else:
            st.write("📉 현재 주가가 20일 이동평균선 아래에 위치해 있어, **저항을 받고 있는 하락 추세**입니다.")
            
        if df['MACD_Hist'].iloc[-1] > 0 and df['MACD_Hist'].iloc[-2] < 0:
            st.write("🔥 **강력한 매수 신호**: MACD 히스토그램이 방금 양(+)으로 전환되었습니다 (골든크로스).")
            
        st.markdown("</div>", unsafe_allow_html=True)

else:
    st.error("데이터를 찾을 수 없거나 아직 상장된 지 얼마 안 된 종목입니다. (최소 20일의 데이터가 필요합니다)")
