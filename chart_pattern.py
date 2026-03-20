import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
from datetime import datetime, timedelta

# --- 1. [디자인] 고대비 테마 및 스타일 설정 ---
st.set_page_config(layout="wide", page_title="Aegis Global v43.0")
st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: white; }
    .stMetric { border: 1px solid #30363d; background-color: #161b22; color: white !important; padding: 10px; border-radius: 8px; }
    .stRadio>div { background-color: #161b22; padding: 10px; border-radius: 8px; border: 1px solid #30363d;}
    div[data-testid="stExpander"] { border: 1px solid #30363d; border-radius: 8px; background-color: #161b22;}
    </style>
    """, unsafe_allow_html=True)

# --- 2. [데이터] 글로벌 통합 데이터 로더 (미국 주식 최적화) ---
@st.cache_data(ttl=60)
def get_detailed_stock_data(symbol):
    try:
        # 야후 파이낸스 사용 (미국 주식 SLDP 등 최적화)
        ticker = yf.Ticker(symbol)
        # 1년치 일봉 데이터 가져오기
        df = ticker.history(period="1y", interval="1d")
        
        if df.empty or len(df) < 120: return None
        
        df = df.sort_index()
        # image_2.png에 있는 이동평균선 구성 (5, 20, 60, 120)
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA60'] = df['Close'].rolling(window=60).mean()
        df['MA120'] = df['Close'].rolling(window=120).mean()
        
        # 보조지표 MACD 계산 (image_2.png 하단)
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['Hist'] = df['MACD'] - df['Signal']
        
        # 최고/최저점 계산 (image_2.png 텍스트용)
        df['Is_Max'] = df['High'] == df['High'].max()
        df['Is_Min'] = df['Low'] == df['Low'].min()
        
        # 예시용 가상 매매 마킹 (Is_Buy/Is_Sell)
        # 실제로는 사용자님의 매매 내역을 여기에 연동해야 합니다.
        np.random.seed(42)
        df['Is_Buy'] = np.random.choice([True, False], len(df), p=[0.02, 0.98])
        df['Is_Sell'] = np.random.choice([True, False], len(df), p=[0.01, 0.99])

        return df
    except: return None

# --- 3. [시각화] image_2.png 스타일 통합 차트 ---
def draw_detailed_global_chart(df, symbol):
    # 메인 차트와 MACD 보조 지표를 나눔 (shared_xaxes)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        row_heights=[0.8, 0.2], vertical_spacing=0.03,
                        subplot_titles=(f"{symbol} Detailed Chart", "MACD"))

    # (1) 메인 캔들 차트 (image_2.png 색상 반영)
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                                 increasing_line_color='#00c087', decreasing_line_color='#ff3b30', name='시세'), row=1, col=1)
    
    # (2) 이동평균선 레이어 (image_2.png 스타일)
    ma_colors = {'MA5': '#8cfcb2', 'MA20': '#ff4d4d', 'MA60': '#ffb3ba', 'MA120': '#b388ff'}
    for ma, color in ma_colors.items():
        if ma in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df[ma], line=dict(color=color, width=1.5), name=ma), row=1, col=1)

    # (3) [image_2.png 핵심] 최고/최저점 텍스트 마킹
    max_row = df[df['Is_Max']].iloc[0]
    fig.add_annotation(x=max_row.name, y=max_row['High'], text=f"{max_row['High']:.2f}<br>(최고)", showarrow=True, arrowhead=1, arrowcolor="red", font=dict(color="red", size=11), yshift=10, row=1, col=1)
    
    min_row = df[df['Is_Min']].iloc[0]
    fig.add_annotation(x=min_row.name, y=min_row['Low'], text=f"{min_row['Low']:.2f}<br>(최저)", showarrow=True, arrowhead=1, arrowcolor="dodgerblue", font=dict(color="dodgerblue", size=11), yshift=-10, row=1, col=1)

    # (4) [image_2.png 핵심] 매수(B)/매도(S) 가상 마킹
    buy_rows = df[df['Is_Buy']]
    if not buy_rows.empty:
        fig.add_trace(go.Scatter(x=buy_rows.index, y=buy_rows['Low']*0.98, mode='markers+text', text='B', textposition='bottom center', textfont=dict(color="lime", size=10), marker=dict(symbol='triangle-up', size=8, color='lime'), name='매수'), row=1, col=1)
        
    sell_rows = df[df['Is_Sell']]
    if not sell_rows.empty:
        fig.add_trace(go.Scatter(x=sell_rows.index, y=sell_rows['High']*1.02, mode='markers+text', text='S', textposition='top center', textfont=dict(color="red", size=10), marker=dict(symbol='triangle-down', size=8, color='red'), name='매도'), row=1, col=1)

    # (5) [image_2.png 하단] MACD 보조 지표
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='#ff9f43', width=1.5), name='MACD'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Signal'], line=dict(color='#00cfe8', width=1.5), name='Signal'), row=2, col=1)
    
    # MACD 히스토그램 (색상 분리)
    colors_h = ['#ff3b30' if val < 0 else '#00c087' for val in df['Hist']]
    fig.add_trace(go.Bar(x=df.index, y=df['Hist'], marker_color=colors_h, name='Histogram'), row=2, col=1)

    # (6) 레이아웃 설정 (모바일 고정 및 시인성 최적화)
    fig.update_xaxes(fixedrange=True, rangeslider_visible=False, color='#888', gridcolor='#222')
    fig.update_yaxes(fixedrange=True, color='#888', gridcolor='#222')
    fig.update_layout(
        height=700, 
        template='plotly_dark', 
        xaxis_rangeslider_visible=False, 
        dragmode=False, 
        paper_bgcolor='rgba(0,0,0,0)', 
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig

# --- 4. 메인 대시보드 UI 및 제어 ---
st.markdown('<p style="font-size: 2.2rem; font-weight: 800; color: #ffdf00; text-align: center;">Aegis Global v43.0 "Global Detailed Chart"</p>', unsafe_allow_html=True)

with st.sidebar:
    st.subheader("🔍 종목 검색")
    u_input = st.text_input("종목명 입력 (예: 솔리드파워, TSLA, 삼성전자)", value="SLDP")
    # 대문자로 변환 (야후 파이낸스 티커용)
    target_symbol = u_input.upper().strip()
    
    st.divider()
    st.caption(f"분석 중인 티커: {target_symbol}")
    st.caption("v43.0: Detailed Chart & MACD")

# 데이터 로드
df = get_detailed_stock_data(target_symbol)

if df is not None:
    # `image_2.png`와 유사하게 $ 단위로 매매 가이드라인 제공
    curr_p = df['Close'].iloc[-1]
    
    tab1, tab2 = st.tabs(["📈 Detailed Chart", "🌡️ AI 정밀 온도계"])

    # --- tab1: 상세 차트 분석 (image_2.png 스타일) ---
    with tab1:
        # 매매가 가이드 ($ 단위)
        c1, c2, c3 = st.columns(3)
        c1.metric("🔥 AI 권장 매수", f"${curr_p * 0.99:,.2f}")
        c2.metric("🚀 목표 익절 (+12%)", f"${curr_p * 1.12:,.2f}")
        c3.metric("⚠️ 위험 손절 (-6%)", f"{curr_p * 0.94:,.2f}")
        
        # 상세 차트 그리기
        st.plotly_chart(draw_detailed_global_chart(df, target_symbol), use_container_width=True, config={'displayModeBar': False})
        
    # --- tab2: AI 정밀 온도계 (이전과 동일) ---
    with tab2:
        score = 50 + (25 if df['MA5'].iloc[-1] > df['MA120'].iloc[-1] else 0) + (25 if curr_p > df['MA20'].iloc[-1] else 0)
        status = "🚀 강력 매수" if score >= 85 else "✅ 매수" if score >= 65 else "⚖️ 관망"
        st.markdown(f'<p style="font-size: 1.8rem; font-weight: 700; text-align: center; color:#00ff41;">{target_name}: {status}</p>', unsafe_allow_html=True)
        fig_g = go.Figure(go.Indicator(mode="gauge+number", value=score, gauge={'bar':{'color':"#00ff41"}}))
        fig_g.update_layout(height=350, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_g, use_container_width=True, config={'displayModeBar': False})

else:
    st.error("종목을 찾을 수 없거나 데이터 로드 실패입니다. 티커(예: SLDP)를 직접 입력해 보세요.")
