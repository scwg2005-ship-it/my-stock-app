import streamlit as st
import matplotlib
matplotlib.use('Agg')
import FinanceDataReader as fdr
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 1. 설정 ---
st.set_page_config(layout="wide", page_title="v16.4 Stable Quant")

# --- 2. 데이터 로드 (캐시 제거하여 충돌 방지) ---
def load_data(symbol):
    try:
        df = fdr.DataReader(symbol).tail(150)
        return df if not df.empty else None
    except:
        return None

# --- 3. UI 구성 (단순화) ---
st.title("🏛️ v16.4 Alpha Quant (Stable)")

# 사이드바 대신 상단 입력창으로 변경 (충돌 감소)
col_in1, col_in2 = st.columns([2, 1])
with col_in1:
    stock_input = st.text_input("종목명 또는 티커를 입력하세요", "ONDS")
with col_in2:
    if st.button("데이터 분석 시작 🚀"):
        st.rerun()

df = load_data(stock_input)

if df is not None:
    # 지표 요약 (단순 텍스트)
    curr = df['Close'].iloc[-1]
    prev = df['Close'].iloc[-2]
    diff = curr - prev
    
    st.subheader(f"📊 {stock_input} 현재 상황")
    st.write(f"**현재가:** {curr:,.2f} | **변동:** {diff:+.2f} ({(diff/prev)*100:+.2f}%)")

    # 차트 그리기 (Subplot 제거하고 단일 차트로 구성)
    fig = go.Figure()
    
    # 캔들차트
    fig.add_trace(go.Candlestick(
        x=df.index, 
        open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], 
        name='Price'
    ))

    # 이동평균선 하나만 추가
    ma20 = df['Close'].rolling(20).mean()
    fig.add_trace(go.Scatter(x=df.index, y=ma20, line=dict(color='yellow', width=1), name='MA20'))

    fig.update_layout(
        height=600, 
        template='plotly_dark', 
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=10, b=10) # 여백 최소화
    )
    
    # 차트 렌더링
    st.plotly_chart(fig, use_container_width=True, key="main_chart") # 고유 키 부여로 충돌 방지

    # 대응 가이드
    st.info(f"💡 {stock_input} 분석 결과: 현재 추세 유지 중입니다. (RSI: {((df['Close'].diff().where(df['Close'].diff() > 0, 0).rolling(14).mean()) / (df['Close'].diff().where(df['Close'].diff() > 0, 0).rolling(14).mean() + (-df['Close'].diff().where(df['Close'].diff() < 0, 0)).rolling(14).mean()) * 100).iloc[-1]:.1f})")

else:
    st.error("데이터를 불러올 수 없습니다. 종목명을 다시 확인해 주세요.")
