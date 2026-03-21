import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from bs4 import BeautifulSoup
from io import StringIO

# --- 1. [디자인] VIP 전용 다크 터미널 UI ---
st.set_page_config(layout="wide", page_title="Aegis Oracle v99.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;900&display=swap');
    body, .stApp { background-color: #030303; font-family: 'Pretendard', sans-serif; color: #e0e0e0; }
    .stMetric { background-color: #0f0f0f; padding: 20px; border-radius: 15px; border: 1px solid #222; }
    .profit-card { background: linear-gradient(135deg, #0055ff 0%, #00aaff 100%); padding: 25px; border-radius: 20px; color: white; text-align: center; margin-bottom: 20px; }
    .info-card { background-color: #121212; padding: 15px; border-radius: 12px; margin-bottom: 10px; border: 1px solid #252525; }
    .status-tag { padding: 4px 12px; border-radius: 6px; font-weight: 800; font-size: 0.85rem; color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [엔진] 네이버 금융 보안 우회 정밀 파싱 ---
@st.cache_data(ttl=60)
def get_safe_naver_data(code, count=100):
    try:
        url = f"https://finance.naver.com/item/sise_day.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        
        all_data = []
        for page in range(1, 6): # 최근 5페이지(50거래일) 데이터 수집
            res = requests.get(f"{url}&page={page}", headers=headers)
            soup = BeautifulSoup(res.text, 'html.parser')
            table = soup.select_one('table.type2')
            
            if not table: continue
            
            rows = table.select('tr')
            for row in rows:
                cols = row.select('td')
                if len(cols) < 7 or not cols[0].text.strip(): continue
                
                date = cols[0].text.strip().replace('.', '-')
                close = cols[1].text.strip().replace(',', '')
                open_p = cols[3].text.strip().replace(',', '')
                high = cols[4].text.strip().replace(',', '')
                low = cols[5].text.strip().replace(',', '')
                vol = cols[6].text.strip().replace(',', '')
                
                all_data.append([date, open_p, high, low, close, vol])
        
        df = pd.DataFrame(all_data, columns=['Date', 'Open', 'High', 'Low', 'Close', 'Volume'])
        df['Date'] = pd.to_datetime(df['Date'])
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            df[col] = pd.to_numeric(df[col])
        
        df = df.sort_values('Date').reset_index(drop=True)
        
        # 이동평균선 계산 (데이터가 적을 경우를 대비해 유연하게 처리)
        for ma in [5, 20]:
            if len(df) >= ma:
                df[f'MA{ma}'] = df['Close'].rolling(ma).mean()
        
        # 종목명 가져오기
        name_res = requests.get(f"https://finance.naver.com/item/main.naver?code={code}", headers=headers)
        name_soup = BeautifulSoup(name_res.text, 'html.parser')
        s_name = name_soup.select_one('.wrap_company h2 a').text
        
        return df, s_name
    except Exception as e:
        return None, str(e)

# --- 3. [사이드바] 제어 센터 ---
with st.sidebar:
    st.markdown('<h2 style="color:#00f2ff;">Oracle Master</h2>', unsafe_allow_html=True)
    s_code = st.text_input("📊 종목코드 (6자리)", value="053000")
    invest_amt = st.number_input("💰 투자 원금 (원)", value=10000000)
    chart_style = st.radio("📈 차트", ["전문가 캔들", "심플 라인"], horizontal=True)

# --- 4. [메인] 정밀 프로세스 가동 ---
df, s_name = get_safe_naver_data(s_code)

if df is not None and not df.empty:
    curr_p = float(df['Close'].iloc[-1])
    
    # [프로세스] 5,000회 몬테카를로 시뮬레이션
    daily_ret = df['Close'].pct_change().dropna()
    sims = np.random.normal(daily_ret.mean(), daily_ret.std() if daily_ret.std() > 0 else 0.01, 5000)
    win_rate = (sims > 0).sum() / 5000 * 100
    expected_profit = sims.mean() * 100

    # 헤더
    st.markdown(f"## {s_name} ({s_code})")
    
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1:
        st.markdown(f'<div class="profit-card"><h3>내일의 기대수익</h3><h1>{expected_profit:+.2f}%</h1><p>예상 손익: {invest_amt * (expected_profit/100):+,.0f}원</p></div>', unsafe_allow_html=True)
    with c2: st.metric("현재가", f"{curr_p:,.0f}원"); st.metric("AI 승률", f"{win_rate:.1f}%")
    with c3: st.metric("목표가(+12%)", f"{curr_p*1.12:,.0f}원"); st.metric("손절가(-6%)", f"{curr_p*0.94:,.0f}원")

    tab1, tab2, tab3, tab4 = st.tabs(["📊 분석 차트", "🧪 정밀 온도계", "📰 실시간 뉴스", "🚀 글로벌 테마"])

    with tab1: # 1P: 기술 차트
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.05)
        if chart_style == "전문가 캔들":
            fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='시세'), row=1, col=1)
        else:
            fig.add_trace(go.Scatter(x=df['Date'], y=df['Close'], line=dict(color='#00f2ff', width=2), fill='tozeroy', name='시세'), row=1, col=1)
        
        if 'MA20' in df.columns:
            fig.add_trace(go.Scatter(x=df['Date'], y=df['MA20'], line=dict(color='#FF37AF', width=1.5), name='20일선'), row=1, col=1)
            
        fig.add_trace(go.Bar(x=df['Date'], y=df['Volume'], marker_color='#333', name='거래량'), row=2, col=1)
        fig.update_layout(height=550, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig, use_container_width=True)

    with tab2: # 2P: 매수 온도계
        cl1, cl2 = st.columns([1.2, 1])
        with cl1:
            fig_g = go.Figure(go.Indicator(mode="gauge+number", value=win_rate, title={'text': "AI 매수 온도 (%)"}, gauge={'bar': {'color': "#007AFF"}}))
            fig_g.update_layout(height=350, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)'); st.plotly_chart(fig_g, use_container_width=True)
        with cl2: st.markdown(f'<div class="info-card"><b>🎯 퀀트 가이드</b><br>현재 승률 {win_rate:.1f}% 구간입니다.<br>단기 추세에 따른 분할 매수를 추천합니다.</div>', unsafe_allow_html=True)

    with tab3: # 3P: 실시간 뉴스
        try:
            n_res = requests.get(f"https://search.naver.com/search.naver?where=news&query={s_name} 특징주", headers=headers)
            n_soup = BeautifulSoup(n_res.text, 'html.parser')
            for item in n_soup.select('.news_area')[:6]:
                st.markdown(f"📍 [{item.select_one('.news_tit').text}]({item.select_one('.news_tit')['href']})")
        except: st.write("뉴스 로딩 중...")

    with tab4: # 4P: 글로벌 테마
        st.write("### 🚀 AI 글로벌 포트폴리오")
        themes = {"🤖 AI": ["삼성전자", "SK하이닉스"], "🛡️ 방산": ["LIG넥스원", "현대로템"], "💰 금융": ["우리금융지주", "KB금융"]}
        for t, stocks in themes.items():
            st.markdown(f"**{t}**: {', '.join(stocks)}")

else:
    st.error(f"❌ 데이터 로드 실패: {s_name if s_name else '알 수 없는 오류'}. 종목코드를 확인하세요.")
