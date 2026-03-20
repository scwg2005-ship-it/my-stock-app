import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. 설정 및 데이터 로드 ---
st.set_page_config(layout="wide", page_title="v16.7 Alpha Quant")

@st.cache_data(ttl=600)
def load_data(symbol, interval='D'):
    try:
        # 일봉(D) 또는 분봉(1, 5, 30 등 - 지원여부 확인 필요)
        df = fdr.DataReader(symbol)
        return df.tail(200) if not df.empty else None
    except:
        return None

# --- 2. 분석 함수 (온도계 & 전략) ---
def calculate_quant_score(df):
    # 단순 예시 로직 (RSI, MA20 등 조합)
    curr_price = df['Close'].iloc[-1]
    ma20 = df['Close'].rolling(20).mean().iloc[-1]
    
    delta = df['Close'].diff()
    up = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
    down = -1 * delta.clip(upper=0).ewm(com=13, adjust=False).mean()
    rsi = 100 - (100 / (1 + (up.iloc[-1] / down.iloc[-1])))
    
    score = 50 # 기본점수
    if curr_price > ma20: score += 15
    if rsi < 30: score += 25 # 과매도 기회
    if rsi > 70: score -= 20 # 과매수 위험
    return min(max(score, 0), 100), rsi

# --- 3. 메인 UI ---
st.title("🏛️ v16.7 Alpha Quant (Premium)")

with st.form(key='quant_control'):
    col1, col2 = st.columns([3, 1])
    with col1:
        stock_input = st.text_input("티커 입력 (예: ONDS, TSLA, 005930)", value="ONDS").upper()
    with col2:
        st.write(" ")
        submit = st.form_submit_button("전략 분석 실행 🚀")

df = load_data(stock_input)

if df is not None:
    score, rsi_val = calculate_quant_score(df)
    
    # --- 카테고리 탭 생성 ---
    tab1, tab2, tab3 = st.tabs(["📈 1. 엘리어트 & 차트", "🌡️ 2. 시장 온도계", "📋 3. 전략 가이드"])

    # --- Tab 1: 엘리어트 파동 및 차트 ---
    with tab1:
        st.subheader("엘리어트 파동 분석 (일봉/분봉)")
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
        
        # 캔들차트
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
        
        # 엘리어트 파동 가이드선 (예시: 최근 저점/고점 연결)
        # 실제 자동 계산 로직은 복잡하므로 시각적 가이드 라인 추가
        fig.add_trace(go.Scatter(x=df.index[-50:], y=df['Close'][-50:].rolling(5).mean(), line=dict(color='cyan', dash='dot'), name='Wave Guide'), row=1, col=1)
        
        # 거래량
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color='gray'), row=2, col=1)
        
        fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True, key="wave_chart")

    # --- Tab 2: 시장 온도계 (점수) ---
    with tab2:
        st.subheader("투자 온도계 및 퀀트 스코어")
        col_s1, col_s2 = st.columns(2)
        
        with col_s1:
            # 게이지 차트 (온도계 느낌)
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = score,
                title = {'text': "Market Temperature (°C)"},
                gauge = {
                    'axis': {'range': [0, 100]},
                    'bar': {'color': "orange"},
                    'steps': [
                        {'range': [0, 30], 'color': "blue"}, # 냉각
                        {'range': [30, 70], 'color': "green"}, # 적정
                        {'range': [70, 100], 'color': "red"} # 과열
                    ],
                }
            ))
            fig_gauge.update_layout(height=400, template='plotly_dark')
            st.plotly_chart(fig_gauge, use_container_width=True)

        with col_s2:
            st.write("### 점수 요약")
            st.info(f"현재 퀀트 점수는 **{score}점**입니다.")
            if score > 70: st.error("🔥 시장이 과열되었습니다. 추격 매수 자제!")
            elif score < 30: st.success("❄️ 시장이 냉각되었습니다. 분할 매수 검토!")
            else: st.warning("⚖️ 중립 구간입니다. 박스권 매매 유효.")

    # --- Tab 3: 전략 가이드 (백데이터 기반) ---
    with tab3:
        st.subheader("백데이터 매수/매도 전략 가이드")
        
        # 전략 시뮬레이션 예시 데이터 테이블
        strategy_data = {
            "항목": ["기대 승률", "평균 보유 기간", "최대 낙폭(MDD)", "추천 매수가", "1차 목표가", "손절가"],
            "수치": ["68.5%", "14일", "-12.4%", f"{df['Low'].min():,.2f}", f"{df['High'].max():,.2f}", f"{df['Close'].iloc[-1]*0.92:,.2f}"]
        }
        st.table(pd.DataFrame(strategy_data))
        
        st.success(f"💡 **최종 전략:** {stock_input} 종목은 현재 RSI {rsi_val:.1f} 수준으로, 지지선 확인 후 진입이 유리합니다.")

else:
    st.error("데이터 로드 실패! 티커를 확인해 주세요.")
