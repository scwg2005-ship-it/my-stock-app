import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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
# 2. 스마트 검색 엔진 & 티커 매핑
# ==========================================
TICKER_MAP = {
    "삼성전자": "005930.KS",
    "카카오": "035720.KS",
    "테슬라": "TSLA",
    "애플": "AAPL",
    "엔비디아": "NVDA",
    "ONDS": "ONDS",
    "쓰리빌리언": "394990.KQ"
}

def get_ticker_from_name(query):
    query = query.strip()
    if query in TICKER_MAP:
        return TICKER_MAP[query]
    # 숫자로만 된 한국 종목 코드 처리 (예: 005930 -> 005930.KS)
    if query.isdigit() and len(query) == 6:
        return f"{query}.KS"
    return query.upper()

# ==========================================
# 3. 사이드바 설정
# ==========================================
st.sidebar.title("⚙️ 시스템 설정")

quick_tickers = ["직접 입력...", "삼성전자", "테슬라", "애플", "엔비디아", "ONDS", "쓰리빌리언"]
selected_quick = st.sidebar.selectbox("⭐ 관심 종목 퀵뷰", quick_tickers)

default_input = "삼성전자" if selected_quick == "직접 입력..." else selected_quick
user_input = st.sidebar.text_input("종목명/코드 검색", value=default_input)

ticker = get_ticker_from_name(user_input)
st.sidebar.caption(f"🔍 검색된 티커: **{ticker}**")

period = st.sidebar.select_slider("조회 기간", options=["3mo", "6mo", "1y", "2y"], value="6mo")

st.sidebar.markdown("---")
st.sidebar.subheader("🧮 포트폴리오 계산기")
buy_p = st.sidebar.number_input("평균 단가", value=0.0, step=0.1)
qty = st.sidebar.number_input("보유 수량", value=0, step=1)

# ==========================================
# 4. 데이터 엔진 (오류 수정 및 연산)
# ==========================================
@st.cache_data(ttl=60)
def load_and_calc_data(symbol, p):
    try:
        df = yf.download(symbol, period=p, interval="1d", auto_adjust=True, progress=False)
        if df.empty or len(df) < 20:
            return None
        
        # 멀티인덱스 컬럼 정리
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        
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
        
        # 스토캐스틱 (91번 라인 수정 완료)
        low_min = df['Low'].rolling(window=14).min()
        high_max = df['High'].rolling(window=14).max()
        df['Stoch_K'] = 100 * ((df['Close'] - low_min) / (high_max - low_min))
        df['Stoch_D'] = df['Stoch_K'].rolling(window=3).mean()
        
        return df
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
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
    col1.metric(f"{ticker} 현재가", f"{curr_p:,.2f}", f"{change:+.2f}%")
    
    if buy_p > 0 and qty > 0:
        profit = ((curr_p - buy_p) / buy_p) * 100
        total_val = curr_p * qty
        col2.metric("보유 수익률", f"{profit:+.2f}%")
        col3.metric("평가 금액", f"{total_val:,.0f}")

    tab1, tab2 = st.tabs(["📊 인터랙티브 차트", "🧠 AI 전략 리포트"])

    with tab1:
        # 차트 생성
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                           vertical_spacing=0.05, row_heights=[0.7, 0.3])

        # 캔들스틱
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'],
                                   low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
        
        # 이평선
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name="MA20", line=dict(color='orange', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], name="MA60", line=dict(color='cyan', width=1)), row=1, col=1)

        # MACD 히스토그램
        colors = ['red' if val < 0 else 'green' for val in df['MACD_Hist']]
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], name="MACD", marker_color=colors), row=2, col=1)

        fig.update_layout(height=600, template="plotly_dark", 
                          xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.markdown("<div class='ai-report'>", unsafe_allow_html=True)
        st.subheader("💡 퀀트 분석 결과")
        
        last_k = df['Stoch_K'].iloc[-1]
        last_d = df['Stoch_D'].iloc[-1]
        
        if last_k > 80:
            st.warning("⚠️ **과매수 상태**: 스토캐스틱 지표가 80을 초과했습니다. 단기 조정에 유의하세요.")
        elif last_k < 20:
            st.success("✅ **과매도 상태**: 지표가 20 미만입니다. 기술적 반등 가능성이 높습니다.")
        else:
            st.info("ℹ️ **추세 지속**: 현재 중립 구간이며 기존 추세를 유지하고 있습니다.")
            
        if curr_p > df['MA20'].iloc[-1]:
            st.write("📈 현재 주가가 20일 이동평균선 위에 있어 단기 상승 흐름입니다.")
        else:
            st.write("📉 현재 주가가 20일 이동평균선 아래에 있어 주의가 필요합니다.")
        st.markdown("</div>", unsafe_allow_html=True)

else:
    st.info("분석할 데이터를 찾을 수 없습니다. 왼쪽 사이드바에서 종목을 다시 검색해주세요.")

# 마무리 멘트
st.sidebar.info("Tip: 한국 종목은 '삼성전자' 또는 '005930'으로 검색하세요.")
