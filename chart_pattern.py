import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO
from bs4 import BeautifulSoup
from datetime import datetime

# --- 1. [디자인] 증권사 VIP 터미널 UI ---
st.set_page_config(layout="wide", page_title="Aegis Oracle v90.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;800&display=swap');
    body, .stApp { background-color: #050505; font-family: 'Pretendard', sans-serif; color: #ffffff; }
    .stMetric { background-color: #111; padding: 20px; border-radius: 16px; border: 1px solid #222; }
    .profit-card { background: linear-gradient(135deg, #007AFF 0%, #5856D6 100%); padding: 25px; border-radius: 20px; color: white; text-align: center; margin-bottom: 20px; }
    .info-card { background-color: #161616; padding: 18px; border-radius: 14px; margin-bottom: 12px; border: 1px solid #222; }
    .status-tag { padding: 4px 10px; border-radius: 6px; font-weight: 800; font-size: 0.8rem; }
    .cate-title { color: #00f2ff; font-weight: 800; font-size: 1.1rem; border-bottom: 2px solid #333; padding-bottom: 5px; margin-top: 15px; }
    .recommend-box { background: #111; padding: 10px; border-radius: 8px; margin-bottom: 6px; border: 1px solid #333; font-size: 0.85rem; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [엔진] 데이터 정형화 및 분석 로직 ---
@st.cache_data(ttl=3600)
def find_ticker_intelligent(query):
    mapping = {"우리금융지주": "053000.KS", "삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "현대차": "005380.KS"}
    if query in mapping: return mapping[query], query
    try:
        url = 'http://kind.krx.co.kr/corpoctl/corpList.do?method=download'
        res = requests.get(url, timeout=5)
        df_krx = pd.read_html(StringIO(res.text), header=0)[0]
        match = df_krx[df_krx['회사명'].str.contains(query, na=False, case=False)]
        if not match.empty: return f"{match.iloc[0]['종목코드']:06d}.KS", match.iloc[0]['회사명']
    except: pass
    return query.upper(), query

@st.cache_data(ttl=60)
def get_oracle_data(ticker):
    try:
        data = yf.download(ticker, period="2y", interval="1d", progress=False)
        if data.empty: return None
        df = data.copy()
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).capitalize() for c in df.columns]
        
        # 날짜 인덱스 처리 (TypeError 방지 핵심)
        df.index = pd.to_datetime(df.index).date
        
        # 지표 계산
        for ma in [5, 20, 60, 120]: df[f'MA{ma}'] = df['Close'].rolling(ma).mean()
        
        # 정배열/역배열 진단 (최근 1일 기준)
        last = df.iloc[-1]
        if last['MA5'] > last['MA20'] > last['MA60'] > last['MA120']: df['Alignment'] = "정배열"
        elif last['MA5'] < last['MA20'] < last['MA60'] < last['MA120']: df['Alignment'] = "역배열"
        else: df['Alignment'] = "혼조세"
        
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
        
        # 파동 지지/저항
        df['High_Max'] = df['High'].rolling(20).max()
        df['Low_Min'] = df['Low'].rolling(20).min()
        return df
    except: return None

# --- 3. [사이드바] 제어 센터 ---
with st.sidebar:
    st.markdown('<p style="font-size:1.8rem; font-weight:800; color:#00f2ff;">Oracle Control</p>', unsafe_allow_html=True)
    u_input = st.text_input("종목명 입력", value="우리금융지주")
    ticker, target_name = find_ticker_intelligent(u_input)
    st.info(f"Target: {target_name} ({ticker})")
    invest_val = st.number_input("투자 원금(원/$)", value=10000000)
    chart_style = st.radio("그래프 형태", ["전문가 캔들", "심플 라인"], horizontal=True)

# --- 4. [메인] 분석 및 결과 ---
df = get_oracle_data(ticker)

if df is not None:
    curr_p = float(df['Close'].iloc[-1]); unit = "원" if ".KS" in ticker else "$"
    align_status = df['Alignment'].iloc[-1]
    align_color = "#00f2ff" if align_status == "정배열" else "#ff37af" if align_status == "역배열" else "#888"

    # 5,000회 몬테카를로 시뮬레이션
    returns = df['Close'].pct_change().dropna()
    sim_results = np.random.normal(returns.mean(), returns.std(), 5000)
    win_rate = (sim_results > 0).sum() / 5000 * 100
    avg_profit_pct = sim_results.mean() * 100

    # 헤더 섹션
    st.markdown(f"### {target_name} <span class='status-tag' style='background:{align_color}; color:white;'>{align_status}</span>", unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1:
        st.markdown(f'<div class="profit-card"><h1>{avg_profit_pct:+.2f}%</h1><p>5,000회 시계열 예측 기대수익</p></div>', unsafe_allow_html=True)
    with c2: st.metric("현재가", f"{curr_p:,.0f}{unit}"); st.metric("승률", f"{win_rate:.1f}%")
    with c3: st.metric("추천 매수가", f"{curr_p*0.98:,.0f}"); st.metric("배열 상태", align_status)

    tab1, tab2, tab3, tab4 = st.tabs(["📉 고정 분석 차트", "🧪 정밀 기술 진단", "📰 실시간 특징주", "🚀 글로벌 테마 리스트"])

    with tab1: # 1페이지 고정 차트
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.03)
        if chart_style == "전문가 캔들":
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='시세'), row=1, col=1)
        else:
            fig.add_trace(go.Scatter(x=df.index, y=df['Close'], line=dict(color='#00f2ff', width=2), fill='tozeroy', name='종가'), row=1, col=1)
        
        for ma, clr in zip([5, 20, 60, 120], ['#FFD60A', '#FF37AF', '#00F2FF', '#FFFFFF']):
            fig.add_trace(go.Scatter(x=df.index, y=df[f'MA{ma}'], line=dict(color=clr, width=1.2), name=f'{ma}선'), row=1, col=1)
        
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color='#333', name='거래량'), row=2, col=1)
        fig.update_layout(height=650, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with tab2: # 2페이지 정밀 진단
        cl1, cl2, cl3 = st.columns(3)
        with cl1:
            st.markdown(f'<div class="info-card"><b>📈 이동평균선 분석</b><br>현재 상태: {align_status}<br>골든크로스: {"발생" if df["MA5"].iloc[-1] > df["MA20"].iloc[-1] else "미발생"}</div>', unsafe_allow_html=True)
        with cl2:
            st.markdown(f'<div class="info-card"><b>⚖️ RSI 강도 분석</b><br>현재 지수: {df["RSI"].iloc[-1]:.1f}<br>상태: {"과매수" if df["RSI"].iloc[-1] > 70 else "과매도" if df["RSI"].iloc[-1] < 30 else "보통"}</div>', unsafe_allow_html=True)
        with cl3:
            st.markdown(f'<div class="info-card"><b>🎯 퀀트 타점</b><br>1차 목표: {curr_p*1.12:,.0f}<br>강력 손절: {curr_p*0.94:,.0f}</div>', unsafe_allow_html=True)
        
        fig_sim = go.Figure(); fig_sim.add_trace(go.Histogram(x=sim_results, nbinsx=50, marker_color='#007AFF'))
        fig_sim.update_layout(title="5,000회 시뮬레이션 수익률 분포", template='plotly_dark', height=300); st.plotly_chart(fig_sim, use_container_width=True)

    with tab3: # 실시간 뉴스
        try:
            res_n = requests.get(f"https://search.naver.com/search.naver?where=news&query={target_name} 특징주", headers={'User-Agent': 'Mozilla/5.0'})
            soup = BeautifulSoup(res_n.text, 'html.parser')
            for art in soup.select('.news_area')[:10]:
                st.markdown(f"📍 [{art.select_one('.news_tit').text}]({art.select_one('.news_tit')['href']})")
        except: st.write("뉴스 로딩 실패")

    with tab4: # 글로벌 테마 확장
        st.write("### 🚀 글로벌 테마별 유망주 (Oracle Pick)")
        themes = {
            "🤖 AI/반도체": ["NVDA", "ASML", "SK하이닉스", "TSM", "ARM", "AVGO"],
            "🛡️ K-방산/우주": ["한화에어로스페이스", "LIG넥스원", "현대로템", "KAI", "LMT", "RTX"],
            "🔋 2차전지": ["TSLA", "LG에너지솔루션", "에코프로머티", "BYD", "CATL", "삼성SDI"],
            "💰 금융/비트코인": ["우리금융지주", "KB금융", "COIN", "MSTR", "JPM", "GS"],
            "💊 바이오/헬스": ["알테오젠", "LLY", "NVO", "삼성바이오로직스", "VRTX", "MRK"],
            "🚢 조선/원자력": ["HD현대중공업", "삼성중공업", "SMR", "CEG", "VST", "한전산업"]
        }
        cols = st.columns(3)
        for i, (t_name, stocks) in enumerate(themes.items()):
            with cols[i % 3]:
                st.markdown(f'<div class="cate-title">{t_name}</div>', unsafe_allow_html=True)
                for s in stocks: st.markdown(f'<div class="recommend-box"><b>{s}</b></div>', unsafe_allow_html=True)

else: st.error("데이터 로드 실패. 티커를 확인하세요.")
