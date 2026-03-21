import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO
from bs4 import BeautifulSoup

# --- 1. [디자인] 프리미엄 다크 터미널 ---
st.set_page_config(layout="wide", page_title="Aegis Oracle v96.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;800&display=swap');
    body, .stApp { background-color: #050505; font-family: 'Pretendard', sans-serif; color: #ffffff; }
    .stMetric { background-color: #111; padding: 20px; border-radius: 16px; border: 1px solid #222; }
    .profit-card { background: linear-gradient(135deg, #007AFF 0%, #5856D6 100%); padding: 25px; border-radius: 20px; color: white; text-align: center; margin-bottom: 20px; }
    .info-card { background-color: #161616; padding: 18px; border-radius: 14px; margin-bottom: 12px; border: 1px solid #222; }
    .status-tag { padding: 4px 12px; border-radius: 6px; font-weight: 800; font-size: 0.85rem; color: white; margin-left: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [데이터] 원시 데이터 강제 추출 로직 (에러 해결 핵심) ---
@st.cache_data(ttl=60)
def get_absolute_data(ticker):
    try:
        # [핵심] yfinance의 모든 에러를 방어하는 최신 옵션 적용
        raw = yf.download(ticker, period="2y", interval="1d", progress=False, auto_adjust=True)
        
        if raw.empty: return None

        # [필살기] 데이터 구조를 완전히 '박살'내고 필요한 것만 새로 조립
        df = pd.DataFrame(index=raw.index)
        
        # MultiIndex(이중 계층)든 뭐든 상관없이 'Close'라는 글자가 들어간 컬럼을 찾아 데이터 추출
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            target_col = [c for c in raw.columns if col in str(c)]
            if target_col:
                # 데이터가 Series면 그대로, DataFrame(중복)이면 첫 열만
                df[col] = raw[target_col[0]].values.flatten()

        # 인덱스 정형화 (타임존 제거)
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df = df.dropna(subset=['Close'])

        # 지표 계산
        for ma in [5, 20, 60, 120]:
            df[f'MA{ma}'] = df['Close'].rolling(ma).mean()
        
        # 정배열/역배열 판독
        last = df.iloc[-1]
        if last['MA5'] > last['MA20'] > last['MA60'] > last['MA120']: df['State'] = "정배열 (상승)"
        elif last['MA5'] < last['MA20'] < last['MA60'] < last['MA120']: df['State'] = "역배열 (하락)"
        else: df['State'] = "혼조세"
        
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
        return df
    except:
        return None

# --- 3. [사이드바] 제어 센터 ---
with st.sidebar:
    st.markdown('<p style="font-size:1.8rem; font-weight:800; color:#00f2ff;">Oracle Control</p>', unsafe_allow_html=True)
    u_input = st.text_input("분석 종목 (예: 005930.KS / NVDA)", value="053000.KS") # 우리금융지주 기본값
    invest_val = st.number_input("투자 원금 설정", value=10000000)
    chart_style = st.radio("그래프 모드", ["전문가 캔들", "심플 라인"], horizontal=True)

# --- 4. [메인] 정밀 프로세스 가동 ---
df = get_absolute_data(u_input)

if df is not None:
    curr_p = float(df['Close'].iloc[-1]); unit = "원" if ".KS" in u_input else "$"
    state = df['State'].iloc[-1]; state_clr = "#00f2ff" if "정배열" in state else "#ff37af" if "역배열" in state else "#888"
    
    # 5,000회 시뮬레이션
    returns = df['Close'].pct_change().dropna()
    sim_results = np.random.normal(returns.mean(), returns.std(), 5000)
    win_rate = (sim_results > 0).sum() / 5000 * 100
    avg_profit = sim_results.mean() * 100

    st.markdown(f"### {u_input} <span class='status-tag' style='background:{state_clr};'>{state}</span>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1.5, 1, 1])
    with col1:
        st.markdown(f'<div class="profit-card"><h1>{avg_profit:+.2f}%</h1><p>5,000회 시계열 예측 기대수익</p></div>', unsafe_allow_html=True)
    with col2: st.metric("현재가", f"{curr_p:,.0f}{unit}"); st.metric("AI 승률", f"{win_rate:.1f}%")
    with col3: st.metric("목표가(+12%)", f"{curr_p*1.12:,.0f}"); st.metric("손절가(-6%)", f"{curr_p*0.94:,.0f}")

    tab1, tab2, tab3, tab4 = st.tabs(["📉 분석 차트", "🧪 정밀 기술 온도계", "📰 실시간 특징주", "🚀 글로벌 테마"])

    with tab1: # 1P: 차트
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.03)
        if chart_style == "전문가 캔들":
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='시세'), row=1, col=1)
        else:
            fig.add_trace(go.Scatter(x=df.index, y=df['Close'], line=dict(color='#00f2ff', width=2), fill='tozeroy', name='시세'), row=1, col=1)
        for ma, clr in zip([5, 20, 60, 120], ['#FFD60A', '#FF37AF', '#00F2FF', '#FFFFFF']):
            fig.add_trace(go.Scatter(x=df.index, y=df[f'MA{ma}'], line=dict(color=clr, width=1.2), name=f'{ma}선'), row=1, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color='#333', name='거래량'), row=2, col=1)
        fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with tab2: # 2P: 온도계
        cl1, cl2 = st.columns([1.2, 1])
        with cl1:
            fig_g = go.Figure(go.Indicator(mode="gauge+number", value=win_rate, title={'text': "AI 매수 온도 (%)"}, gauge={'bar': {'color': "#007AFF"}}))
            fig_g.update_layout(height=400, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)'); st.plotly_chart(fig_g, use_container_width=True)
        with cl2: st.markdown(f'<div class="info-card"><b>🔍 기술 지표</b><br>RSI: {df["RSI"].iloc[-1]:.1f}<br>상태: {state}</div>', unsafe_allow_html=True)

    with tab3: # 3P: 뉴스
        try:
            res_n = requests.get(f"https://search.naver.com/search.naver?where=news&query={u_input} 특징주", headers={'User-Agent': 'Mozilla/5.0'})
            soup = BeautifulSoup(res_n.text, 'html.parser')
            for art in soup.select('.news_area')[:6]:
                st.markdown(f"📍 [{art.select_one('.news_tit').text}]({art.select_one('.news_tit')['href']})")
        except: st.write("뉴스 연동 중...")

    with tab4: # 4P: 테마
        st.write("### 🚀 글로벌 핵심 테마")
        themes = {"🤖 AI": ["NVDA", "SK하이닉스"], "🛡️ 방산": ["한화에어로스페이스", "LIG넥스원"], "💰 금융": ["우리금융지주", "JPM"]}
        cols = st.columns(3)
        for i, (t_name, stocks) in enumerate(themes.items()):
            with cols[i]:
                st.markdown(f'<div class="info-card"><b>{t_name}</b><br>{", ".join(stocks)}</div>', unsafe_allow_html=True)

else:
    st.error("데이터 로드 실패: 티커 형식을 확인하세요. (005930.KS / AAPL 등)")
