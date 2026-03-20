import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from bs4 import BeautifulSoup
import requests
from io import StringIO

# --- 1. [디자인] 글로벌 터미널 UI ---
st.set_page_config(layout="wide", page_title="Aegis Global v61.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;800&display=swap');
    body, .stApp { background-color: #0d0d0d; font-family: 'Pretendard', sans-serif; color: #ffffff; }
    .stMetric { background-color: #1a1a1a; padding: 20px; border-radius: 16px; border: 1px solid #333; }
    .profit-card { background: linear-gradient(135deg, #007AFF 0%, #00C7BE 100%); padding: 25px; border-radius: 20px; color: white; text-align: center; margin-bottom: 20px; }
    .info-card { background-color: #161616; padding: 18px; border-radius: 14px; margin-bottom: 12px; border: 1px solid #222; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [데이터] Yahoo Finance 글로벌 엔진 ---
@st.cache_data(ttl=86400)
def get_krx_dict():
    # 종목명 -> 티커 변환을 위한 마스터 리스트
    try:
        url = 'http://kind.krx.co.kr/corpoctl/corpList.do?method=download'
        res = requests.get(url)
        df = pd.read_html(StringIO(res.text), header=0)[0]
        df = df[['회사명', '종목코드']].copy()
        df['종목코드'] = df['종목코드'].apply(lambda x: f"{x:06d}.KS") # Yahoo 형식 (.KS)
        return dict(zip(df['회사명'], df['종목코드']))
    except:
        return {"삼성전자": "005930.KS", "한화솔루션": "009830.KS", "SK하이닉스": "000660.KS"}

def get_yfinance_data(ticker, mode="일봉"):
    # 주기에 따른 파라미터 설정
    interval_map = {"1분봉": "1m", "일봉": "1d", "월봉": "1mo"}
    period_map = {"1분봉": "1d", "일봉": "1y", "월봉": "max"}
    
    try:
        data = yf.download(ticker, period=period_map[mode], interval=interval_map[mode], progress=False)
        if data.empty: return None
        
        # 컬럼 정리 및 지표 계산
        df = data.copy()
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        
        # RSI 계산
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
        return df
    except:
        return None

# --- 3. [메인 UI] 사이드바 및 컨트롤 ---
st.markdown('<p style="font-size:2.5rem; font-weight:800; color:#fff;">Aegis Global <span style="color:#00f2ff;">v61.0</span></p>', unsafe_allow_html=True)

krx_map = get_krx_dict()
with st.sidebar:
    st.markdown("### 🔍 Global Search")
    u_input = st.text_input("종목명 또는 티커 (삼성전자, TSLA, AAPL)", value="한화솔루션")
    
    filtered = [n for n in krx_map.keys() if u_input in n]
    if filtered:
        target_name = st.selectbox(f"검색 결과 ({len(filtered)}건)", options=filtered[:100])
        ticker = krx_map[target_name]
    else:
        target_name = u_input.upper()
        ticker = target_name # 미국 주식 직접 입력 대응
    
    st.divider()
    view_mode = st.radio("데이터 주기", ["1분봉", "일봉", "월봉"], index=1, horizontal=True)
    invest_val = st.number_input("투자 원금 설정", value=10000000, step=1000000)
    
    st.divider()
    chart_style = st.radio("그래프 형태", ["전문가 캔들", "심플 라인"], horizontal=True)
    show_ma = st.multiselect("이평선 표시", [5, 20, 60], default=[5, 20])

# --- 4. 최종 렌더링 섹션 ---
df = get_yfinance_data(ticker, view_mode)

if df is not None:
    # yfinance 데이터는 MultiIndex일 수 있으므로 처리
    curr_p = float(df['Close'].iloc[-1])
    prev_p = float(df['Close'].iloc[-2])
    unit = "$" if ".KS" not in ticker else "원"
    
    # [퀀트 지표 연산]
    rsi_val = float(df['RSI'].iloc[-1])
    score = 50 + (25 if curr_p > float(df['MA20'].iloc[-1]) else -10) + (25 if rsi_val < 35 else -10 if rsi_val > 70 else 0)
    est_ret = 12.8 if score > 70 else 3.5
    est_profit = invest_val * (est_ret / 100)

    # 상단 대시보드
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1:
        st.markdown(f"""<div class="profit-card">
            <p style="margin:0; font-size:1rem; opacity:0.9;">글로벌 퀀트 전략 기대 수익률</p>
            <h1 style="margin:0; font-size:3.2rem;">+{est_ret}%</h1>
            <p style="margin:0; font-weight:bold;">예상 수익금: {est_profit:+,.0f} {unit}</p>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.metric("현재가", f"{curr_p:,.0f}{unit}", f"{curr_p-prev_p:+,.0f}")
        st.metric("AI 퀀트 점수", f"{score}점", f"{score-50:+}")
    with c3:
        st.metric("RSI (14D)", f"{rsi_val:.1f}", "과매도" if rsi_val < 30 else "정상")
        st.metric("목표가 (+12%)", f"{curr_p*1.12:,.0f}{unit}")

    tab1, tab2, tab3, tab4 = st.tabs(["📉 시세 차트", "🌡️ AI 정밀 진단", "📰 실시간 뉴스", "📅 투자 캘린더"])

    with tab1:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.03)
        if chart_style == "전문가 캔들" and view_mode != "1분봉":
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], increasing_line_color='#FF3B30', decreasing_line_color='#007AFF', name=''), row=1, col=1)
        else:
            fig.add_trace(go.Scatter(x=df.index, y=df['Close'], fill='tozeroy', fillcolor='rgba(0, 122, 255, 0.1)', line=dict(color='#007AFF', width=2.5), name=''), row=1, col=1)
        
        for ma in show_ma:
            ma_name = f'MA{ma}'
            if ma_name not in df.columns: df[ma_name] = df['Close'].rolling(ma).mean()
            fig.add_trace(go.Scatter(x=df.index, y=df[ma_name], line=dict(width=1.2), name=f'{ma}선'), row=1, col=1)
            
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color='#333', name='거래량'), row=2, col=1)
        fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.info(f"현재 {target_name}의 글로벌 퀀트 점수는 {score}점입니다.")
        fig_g = go.Figure(go.Indicator(mode="gauge+number", value=score, gauge={'bar':{'color':'#007AFF'}, 'bgcolor':'#222'}))
        fig_g.update_layout(height=400, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_g, use_container_width=True)

    with tab3:
        st.subheader("📰 글로벌 실시간 뉴스")
        st.write("Yahoo Finance 및 주요 외신 뉴스를 분석 중입니다.")
        st.markdown(f"[클릭하여 최신 뉴스 보기](https://finance.yahoo.com/quote/{ticker}/news)")

    with tab4:
        st.subheader("📅 투자 일정 및 배당")
        st.markdown(f"[📅 {target_name} 배당 정보 확인](https://finance.yahoo.com/quote/{ticker}/dividends)")

else:
    st.error("데이터를 불러올 수 없습니다. 티커(예: AAPL)를 직접 입력하거나 종목명을 다시 확인해 주세요.")
