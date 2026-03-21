import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# --- 1. [디자인] VIP 전용 다크 터미널 ---
st.set_page_config(layout="wide", page_title="Aegis Oracle v97.0")
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

# --- 2. [재설계 핵심] 네이버 금융 직접 파싱 엔진 (라이브러리 미사용) ---
@st.cache_data(ttl=60)
def get_naver_stock_data(item_code, pages=10):
    try:
        url = f"https://finance.naver.com/item/sise_day.naver?code={item_code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        df_list = []
        
        for page in range(1, pages + 1):
            res = requests.get(f"{url}&page={page}", headers=headers)
            temp_df = pd.read_html(res.text, header=0)[0]
            df_list.append(temp_df.dropna())
            
        df = pd.concat(df_list)
        df.columns = ['Date', 'Close', 'Net', 'Open', 'High', 'Low', 'Volume']
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date').reset_index(drop=True)
        
        # 수치 데이터 강제 변환
        for col in ['Close', 'Open', 'High', 'Low', 'Volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        # [정밀 분석] 이평선 및 배열 판독
        for ma in [5, 20, 60, 120]:
            df[f'MA{ma}'] = df['Close'].rolling(ma).mean()
        
        last = df.iloc[-1]
        if last['MA5'] > last['MA20'] > last['MA60'] > last['MA120']: state = "정배열 (상승)"
        elif last['MA5'] < last['MA20'] < last['MA60'] < last['MA120']: state = "역배열 (하락)"
        else: state = "혼조세"
        
        # RSI 계산
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
        
        return df, state
    except Exception as e:
        return None, str(e)

# --- 3. [사이드바] 제어 센터 ---
with st.sidebar:
    st.markdown('<p style="font-size:1.8rem; font-weight:800; color:#00f2ff;">Oracle Master</p>', unsafe_allow_html=True)
    # 종목 코드 직접 입력 (우리금융지주: 053000, 삼성전자: 005930)
    stock_code = st.text_input("종목코드 6자리 입력", value="053000") 
    invest_val = st.number_input("투자 원금 설정", value=10000000)
    chart_style = st.radio("그래프 모드", ["전문가 캔들", "심플 라인"], horizontal=True)

# --- 4. [메인] 분석 프로세스 ---
df, state = get_naver_stock_data(stock_code)

if df is not None:
    curr_p = float(df['Close'].iloc[-1])
    state_clr = "#00f2ff" if "정배열" in state else "#ff37af" if "역배열" in state else "#888"
    
    # 5,000회 시뮬레이션
    returns = df['Close'].pct_change().dropna()
    sim_results = np.random.normal(returns.mean(), returns.std(), 5000)
    win_rate = (sim_results > 0).sum() / 5000 * 100
    avg_profit = sim_results.mean() * 100

    st.markdown(f"### 종목코드: {stock_code} <span class='status-tag' style='background:{state_clr};'>{state}</span>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1.5, 1, 1])
    with col1:
        st.markdown(f'<div class="profit-card"><h1>{avg_profit:+.2f}%</h1><p>5,000회 시계열 예측 기대수익</p></div>', unsafe_allow_html=True)
    with col2: st.metric("현재가", f"{curr_p:,.0f}원"); st.metric("AI 승률", f"{win_rate:.1f}%")
    with col3: st.metric("목표가(+12%)", f"{curr_p*1.12:,.0f}"); st.metric("손절가(-6%)", f"{curr_p*0.94:,.0f}")

    tab1, tab2, tab3, tab4 = st.tabs(["📉 분석 차트", "🧪 정밀 기술 온도계", "📰 실시간 뉴스", "🚀 글로벌 테마"])

    with tab1: # 1P: 차트
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.03)
        if chart_style == "전문가 캔들":
            fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='시세'), row=1, col=1)
        else:
            fig.add_trace(go.Scatter(x=df['Date'], y=df['Close'], line=dict(color='#00f2ff', width=2), fill='tozeroy', name='시세'), row=1, col=1)
        for ma, clr in zip([5, 20, 60, 120], ['#FFD60A', '#FF37AF', '#00F2FF', '#FFFFFF']):
            fig.add_trace(go.Scatter(x=df['Date'], y=df[f'MA{ma}'], line=dict(color=clr, width=1.2), name=f'{ma}선'), row=1, col=1)
        fig.add_trace(go.Bar(x=df['Date'], y=df['Volume'], marker_color='#333', name='거래량'), row=2, col=1)
        fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with tab2: # 2P: 온도계
        cl1, cl2 = st.columns([1.2, 1])
        with cl1:
            fig_g = go.Figure(go.Indicator(mode="gauge+number", value=win_rate, title={'text': "AI 매수 온도 (%)"}, gauge={'bar': {'color': "#007AFF"}}))
            fig_g.update_layout(height=400, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)'); st.plotly_chart(fig_g, use_container_width=True)
        with cl2: st.markdown(f'<div class="info-card"><b>🔍 지표 분석</b><br>RSI: {df["RSI"].iloc[-1]:.1f}<br>배열: {state}</div>', unsafe_allow_html=True)

    with tab3: # 3P: 뉴스
        try:
            res_n = requests.get(f"https://search.naver.com/search.naver?where=news&query={stock_code} 특징주", headers={'User-Agent': 'Mozilla/5.0'})
            soup = BeautifulSoup(res_n.text, 'html.parser')
            for art in soup.select('.news_area')[:6]:
                st.markdown(f"📍 [{art.select_one('.news_tit').text}]({art.select_one('.news_tit')['href']})")
        except: st.write("뉴스 로딩 중...")

    with tab4: # 4P: 글로벌 테마
        st.write("### 🚀 글로벌 핵심 테마")
        themes = {"🤖 AI": ["삼성전자", "SK하이닉스"], "💰 금융": ["우리금융지주", "KB금융"]}
        for t, s in themes.items():
            st.markdown(f"**{t}**: {', '.join(s)}")

else:
    st.error("데이터 로드 실패: 종목코드를 확인하세요 (예: 삼성전자 005930)")
