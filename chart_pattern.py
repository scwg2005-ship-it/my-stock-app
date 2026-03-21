import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO
from bs4 import BeautifulSoup

# --- 1. [디자인] 전문가용 블랙 터미널 ---
st.set_page_config(layout="wide", page_title="Aegis Oracle v100.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;900&display=swap');
    body, .stApp { background-color: #050505; font-family: 'Pretendard', sans-serif; color: #e0e0e0; }
    .stMetric { background-color: #111; padding: 20px; border-radius: 15px; border: 1px solid #222; }
    .profit-card { background: linear-gradient(135deg, #0055ff 0%, #00aaff 100%); padding: 25px; border-radius: 20px; color: white; text-align: center; margin-bottom: 20px; }
    .info-card { background-color: #161616; padding: 15px; border-radius: 12px; margin-bottom: 10px; border: 1px solid #252525; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [엔진] 무적의 데이터 로더 (네이버 금융 모바일/PC 하이브리드) ---
@st.cache_data(ttl=60)
def get_master_data_v100(code):
    try:
        # 1. 종목명 먼저 가져오기 (가장 확실한 경로)
        name_url = f"https://finance.naver.com/item/main.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
        name_res = requests.get(name_url, headers=headers)
        soup = BeautifulSoup(name_res.text, 'html.parser')
        
        # 종목명 추출 (여러 경로 시도)
        name_tag = soup.select_one('.wrap_company h2 a')
        if not name_tag: name_tag = soup.select_one('title')
        s_name = name_tag.text.replace(' : 네이버 페이 증권', '').strip()

        # 2. 일별 시세 가져오기 (read_html + StringIO 조합으로 보안 우회)
        url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page=1"
        res = requests.get(url, headers=headers)
        
        # 표 데이터 강제 추출
        dfs = pd.read_html(StringIO(res.text))
        df = dfs[0].dropna() # 첫 번째 표가 보통 시세 데이터임
        
        if df.empty or len(df.columns) < 7:
            # 실패 시 두 번째 표 시도
            df = dfs[1].dropna()

        # 컬럼명 통일
        df.columns = ['Date', 'Close', 'Net', 'Open', 'High', 'Low', 'Volume']
        
        # 데이터 정제 (날짜 형식이 2026.03.21 등으로 들어오므로 변환)
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.dropna(subset=['Date'])
        
        for col in ['Close', 'Open', 'High', 'Low', 'Volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        df = df.sort_values('Date').reset_index(drop=True)

        # 3. 기술 지표 (이평선 5, 20)
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        
        # 배열 판독
        last = df.iloc[-1]
        state = "상승 정배열" if last['MA5'] > last['MA20'] else "조정 역배열"
        
        return df, s_name, state
    except Exception as e:
        return None, str(e), "Error"

# --- 3. [사이드바] 제어 센터 ---
with st.sidebar:
    st.markdown('<h2 style="color:#00f2ff;">Oracle Master</h2>', unsafe_allow_html=True)
    s_code = st.text_input("📊 종목코드 (6자리)", value="053000") # 우리금융지주
    invest_amt = st.number_input("💰 투자 원금 (원)", value=10000000)

# --- 4. [메인] 분석 프로세스 가동 ---
df, s_name, state = get_master_data_v100(s_code)

if df is not None and not df.empty:
    curr_p = float(df['Close'].iloc[-1])
    
    # [프로세스] 5,000회 몬테카를로 시뮬레이션
    daily_ret = df['Close'].pct_change().dropna()
    sims = np.random.normal(daily_ret.mean(), daily_ret.std() if daily_ret.std() > 0 else 0.01, 5000)
    win_rate = (sims > 0).sum() / 5000 * 100
    expected_profit = sims.mean() * 100

    st.markdown(f"### {s_name} ({s_code}) <small style='color:#00f2ff;'>[{state}]</small>", unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1:
        st.markdown(f'<div class="profit-card"><h3>내일의 기대수익</h3><h1>{expected_profit:+.2f}%</h1><p>예상 손익: {invest_amt * (expected_profit/100):+,.0f}원</p></div>', unsafe_allow_html=True)
    with c2: st.metric("현재가", f"{curr_p:,.0f}원"); st.metric("AI 승률", f"{win_rate:.1f}%")
    with c3: st.metric("목표가(+12%)", f"{curr_p*1.12:,.0f}원"); st.metric("손절가(-6%)", f"{curr_p*0.94:,.0f}원")

    tab1, tab2, tab3, tab4 = st.tabs(["📊 분석 차트", "🧪 정밀 온도계", "📰 실시간 뉴스", "🚀 글로벌 테마"])

    with tab1: # 1P: 기술 차트
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.05)
        fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='시세'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['MA20'], line=dict(color='#FF37AF', width=1.5), name='20일선'), row=1, col=1)
        fig.add_trace(go.Bar(x=df['Date'], y=df['Volume'], marker_color='#333', name='거래량'), row=2, col=1)
        fig.update_layout(height=550, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig, use_container_width=True)

    with tab2: # 2P: 매수 온도계
        cl1, cl2 = st.columns([1.2, 1])
        with cl1:
            fig_g = go.Figure(go.Indicator(mode="gauge+number", value=win_rate, title={'text': "AI 매수 온도 (%)"}, gauge={'bar': {'color': "#007AFF"}}))
            fig_g.update_layout(height=350, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)'); st.plotly_chart(fig_g, use_container_width=True)
        with cl2: st.markdown(f'<div class="info-card"><b>🎯 퀀트 가이드</b><br>현재 승률 {win_rate:.1f}% 구간입니다.<br>기술적 지표 {state} 상태입니다.</div>', unsafe_allow_html=True)

    with tab3: # 3P: 실시간 뉴스
        try:
            n_res = requests.get(f"https://search.naver.com/search.naver?where=news&query={s_name} 특징주", headers=headers)
            n_soup = BeautifulSoup(n_res.text, 'html.parser')
            for item in n_soup.select('.news_area')[:6]:
                st.markdown(f"📍 [{item.select_one('.news_tit').text}]({item.select_one('.news_tit')['href']})")
        except: st.write("뉴스 로딩 중...")

    with tab4: # 4P: 글로벌 테마
        st.write("### 🚀 AI 글로벌 포트폴리오")
        themes = {"🤖 AI": ["삼성전자", "SK하이닉스"], "💰 금융": ["우리금융지주", "KB금융"]}
        for t, stocks in themes.items():
            st.markdown(f"**{t}**: {', '.join(stocks)}")

else:
    st.error(f"❌ 데이터 로드 실패: {s_name}. 종목코드(053000 등)를 정확히 입력하세요.")
