import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import plotly.graph_objects as go

# --- 1. 설정 ---
st.set_page_config(layout="wide", page_title="v16.4 Stable Quant")

# --- 2. 함수 정의 ---
def get_rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=period - 1, adjust=False).mean()
    ema_down = down.ewm(com=period - 1, adjust=False).mean()
    rs = ema_up / ema_down
    return 100 - (100 / (1 + rs))

@st.cache_data # 데이터 캐싱으로 속도 향상 및 충돌 방지
def load_data(symbol):
    try:
        # 150일치보다 넉넉히 가져와야 지표 계산이 정확합니다
        df = fdr.DataReader(symbol)
        if df is not None and not df.empty:
            return df.tail(150)
        return None
    except Exception as e:
        return None

# --- 3. UI 구성 ---
st.title("🏛️ v16.4 Alpha Quant (Stable)")

col_in1, col_in2 = st.columns([3, 1])
with col_in1:
    # 팁: 미국주는 티커 그대로, 한국주는 종목코드 6자리를 권장합니다.
    stock_input = st.text_input("티커(예: NVDA, 005930)를 입력하세요", "ONDS").upper()
with col_in2:
    st.write(" ") # 간격 맞춤
    btn = st.button("데이터 분석 시작 🚀")

# 데이터 로드
df = load_data(stock_input)

if df is not None and len(df) > 20: # 최소 20일치 데이터 필요 (MA20 위해)
    # 지표 계산
    curr = df['Close'].iloc[-1]
    prev = df['Close'].iloc[-2]
    diff = curr - prev
    pct_chg = (diff / prev) * 100
    
    rsi_val = get_rsi(df['Close']).iloc[-1]
    ma20 = df['Close'].rolling(20).mean()

    # --- 출력부 ---
    st.subheader(f"📊 {stock_input} 현재 상황")
    
    # 지표를 깔끔한 카드로 표시
    m1, m2, m3 = st.columns(3)
    m1.metric("현재가", f"{curr:,.2f}")
    m2.metric("전일대비", f"{diff:+.2f}", f"{pct_chg:+.2f}%")
    m3.metric("RSI (14)", f"{rsi_val:.1f}")

    # 차트 그리기
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'
    ))
    fig.add_trace(go.Scatter(x=df.index, y=ma20, line=dict(color='yellow', width=1.5), name='MA20'))

    fig.update_layout(
        height=500, template='plotly_dark',
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=10, b=10)
    )
    
    st.plotly_chart(fig, use_container_width=True, key="main_chart")

    # 대응 가이드
    if rsi_val > 70:
        st.warning("⚠️ RSI가 70 이상입니다. 과매수 구간일 가능성이 있습니다.")
    elif rsi_val < 30:
        st.success("✅ RSI가 30 이하입니다. 과매도 구간일 가능성이 있습니다.")
    else:
        st.info("💡 현재 안정적인 추세 유지 중입니다.")

else:
    st.error(f"'{stock_input}' 데이터를 불러올 수 없습니다. 티커(종목코드)가 정확한지 확인해 주세요.")
