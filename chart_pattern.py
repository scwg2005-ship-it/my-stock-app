import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import plotly.graph_objects as go

# --- 1. 설정 ---
st.set_page_config(layout="wide", page_title="v16.5 Stable Quant")

# --- 2. 안정적인 데이터 로드 함수 ---
@st.cache_data(ttl=3600)  # 1시간 동안 캐시 유지하여 불필요한 재로드 방지
def load_data(symbol):
    try:
        df = fdr.DataReader(symbol)
        if df is not None and not df.empty:
            return df.tail(150)
        return None
    except:
        return None

# --- 3. UI 구성 ---
st.title("🏛️ v16.5 Alpha Quant")

# 폼(Form)을 사용하면 버튼을 누를 때까지 실행을 대기시켜 충돌을 막습니다.
with st.form(key='search_form'):
    col_in1, col_in2 = st.columns([3, 1])
    with col_in1:
        stock_input = st.text_input("티커를 입력하세요 (예: NVDA, 005930)", value="ONDS").upper()
    with col_in2:
        st.write(" ") # 정렬용
        submit_button = st.form_submit_button(label='데이터 분석 시작 🚀')

# 버튼을 눌렀을 때만 혹은 처음 실행될 때만 데이터 로드
if stock_input:
    df = load_data(stock_input)

    if df is not None and len(df) > 20:
        # 지표 요약
        curr = df['Close'].iloc[-1]
        prev = df['Close'].iloc[-2]
        diff = curr - prev
        
        st.subheader(f"📊 {stock_input} 분석 결과")
        
        # 메트릭 표시
        m1, m2 = st.columns(2)
        m1.metric("현재가", f"{curr:,.2f}")
        m2.metric("전일대비", f"{diff:+.2f}", f"{(diff/prev)*100:+.2f}%")

        # 차트 (키 값을 동적으로 부여하여 충돌 방지)
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'
        ))
        
        ma20 = df['Close'].rolling(20).mean()
        fig.add_trace(go.Scatter(x=df.index, y=ma20, line=dict(color='yellow', width=1), name='MA20'))

        fig.update_layout(
            height=500, template='plotly_dark',
            xaxis_rangeslider_visible=False,
            margin=dict(l=10, r=10, t=10, b=10)
        )
        
        # use_container_width를 True로 설정하고 고유 키 부여
        st.plotly_chart(fig, use_container_width=True, key=f"chart_{stock_input}")

    else:
        st.error("데이터를 불러올 수 없거나 종목코드가 올바르지 않습니다.")
