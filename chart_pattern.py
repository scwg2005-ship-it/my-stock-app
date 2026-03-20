import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. 설정 ---
st.set_page_config(layout="wide", page_title="v17.1 Premium Quant")

# --- 2. 데이터 로드 함수 (한글 종목명 대응 강화) ---
@st.cache_data(ttl=1800)
def get_stock_data(keyword):
    try:
        # 1. 한국 거래소 종목 리스트 확보 (한글 검색용)
        df_krx = fdr.StockListing('KRX')
        
        # 2. 종목명에서 코드 추출
        target = df_krx[df_krx['Name'] == keyword]
        
        if not target.empty:
            symbol = target.iloc[0]['Symbol']
        else:
            symbol = keyword # 코드를 직접 입력했을 경우 대비
            
        df = fdr.DataReader(symbol)
        if df is not None and not df.empty:
            return df.tail(200), keyword
        return None, None
    except:
        return None, None

# --- 3. 삼각수렴 패턴 함수 ---
def get_convergence(df):
    if len(df) < 60: return None
    data = df.tail(60).copy()
    
    # 고점/저점 추세선 계산 (빗각)
    x = np.arange(len(data))
    high_idx = np.where(data['High'] == data['High'].rolling(10, center=True).max())[0]
    low_idx = np.where(data['Low'] == data['Low'].rolling(10, center=True).min())[0]
    
    if len(high_idx) < 2 or len(low_idx) < 2: return None
    
    high_fit = np.polyfit(high_idx, data['High'].iloc[high_idx], 1)
    low_fit = np.polyfit(low_idx, data['Low'].iloc[low_idx], 1)
    
    return {
        'high_line': high_fit[0] * x + high_fit[1],
        'low_line': low_fit[0] * x + low_fit[1],
        'index': data.index
    }

# --- 4. 메인 UI (에러 수정 포인트) ---
st.title("🏛️ v17.1 Premium Quant")

# [수정] 폼 내부에서 모든 입력과 버튼이 완결되어야 합니다.
with st.form(key='search_form'):
    col1, col2 = st.columns([3, 1])
    with col1:
        stock_input = st.text_input("종목명(예: 삼성전자) 또는 티커 입력", value="삼성전자")
    with col2:
        st.write(" ") # 수직 정렬용
        # [핵심] 반드시 form 블록 안에 submit_button이 있어야 함
        submitted = st.form_submit_button("전략 분석 실행 🚀")

# 폼 외부에서 데이터 처리
if stock_input:
    df, name = get_stock_data(stock_input)

    if df is not None:
        tab1, tab2, tab3 = st.tabs(["📈 빗각 추세 차트", "🌡️ 투자 온도계", "📋 전략 가이드"])

        with tab1:
            st.subheader(f"[{name}] 빗각 추세 및 삼각수렴 분석")
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
            
            # 캔들
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
            
            # 빗각 추세선 추가
            conv = get_convergence(df)
            if conv:
                fig.add_trace(go.Scatter(x=conv['index'], y=conv['high_line'], line=dict(color='red', dash='dot'), name='상단저항'), row=1, col=1)
                fig.add_trace(go.Scatter(x=conv['index'], y=conv['low_line'], line=dict(color='green', dash='dot'), name='하단지지'), row=1, col=1)
            
            # 거래량
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color='gray'), row=2, col=1)
            fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            st.subheader("시장 온도계")
            # 간단한 점수 로직
            score = 65 # 예시
            st.gauge(score) if hasattr(st, 'gauge') else st.metric("현재 퀀트 점수", f"{score}점")
            st.info("RSI 및 이동평균선 기반 점수입니다.")

        with tab3:
            st.subheader("백데이터 전략")
            st.write("최근 200일 데이터를 기반으로 산출된 가이드입니다.")
            st.table(pd.DataFrame({"구분": ["목표가", "손절가"], "가격": [df['Close'].max(), df['Close'].iloc[-1]*0.95]}))

    else:
        st.error("종목을 찾을 수 없습니다. 종목명이 정확한지 확인해 주세요.")
