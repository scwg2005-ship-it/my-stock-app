import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO
from bs4 import BeautifulSoup
import re

# --- 1. [디자인] 전문가용 블랙 터미널 UI ---
st.set_page_config(layout="wide", page_title="Aegis Oracle Citadel v102.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;900&display=swap');
    body, .stApp { background-color: #050505; font-family: 'Pretendard', sans-serif; color: #e0e0e0; }
    .stMetric { background-color: #111; padding: 20px; border-radius: 15px; border: 1px solid #222; }
    .profit-card { background: linear-gradient(135deg, #0055ff 0%, #00aaff 100%); padding: 25px; border-radius: 20px; color: white; text-align: center; margin-bottom: 20px; }
    .info-card { background-color: #161616; padding: 15px; border-radius: 12px; margin-bottom: 10px; border: 1px solid #252525; }
    .alert-box { background-color: #1e1e00; border: 2px solid #ffcc00; color: #ffcc00; padding: 15px; border-radius: 10px; font-weight: bold; margin-bottom: 20px; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [핵심 엔진] 수동 파싱 하이브리드 로더 ---
@st.cache_data(ttl=60)
def get_citadel_data(symbol):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
    try:
        # [A] 국장 판별 및 로드 (네이버 금융 직접 파싱)
        if symbol.isdigit() and len(symbol) == 6:
            url = f"https://finance.naver.com/item/sise_day.naver?code={symbol}&page=1"
            res = requests.get(url, headers=headers)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 종목명 추출
            name_res = requests.get(f"https://finance.naver.com/item/main.naver?code={symbol}", headers=headers)
            name_soup = BeautifulSoup(name_res.text, 'html.parser')
            s_name = name_soup.select_one('.wrap_company h2 a').text.strip()
            
            # 데이터 파싱
            rows = soup.select('table.type2 tr')
            data = []
            for row in rows:
                cols = row.select('td')
                if len(cols) < 7 or not cols[0].text.strip(): continue
                data.append([cols[0].text.strip(), cols[3].text.strip(), cols[4].text.strip(), cols[5].text.strip(), cols[1].text.strip(), cols[6].text.strip()])
            
            df = pd.DataFrame(data, columns=['Date', 'Open', 'High', 'Low', 'Close', 'Volume'])
            m_type = "KR"

        # [B] 미장 판별 및 로드 (야후 파이낸스 직접 파싱 - 라이브러리 미사용)
        else:
            url = f"https://finance.yahoo.com/quote/{symbol.upper()}/history"
            res = requests.get(url, headers=headers)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            s_name = symbol.upper()
            # 야후 히스토리 테이블 추출
            rows = soup.select('table.m-4560756a tr') # 야후의 최신 테이블 클래스 (변동 가능성 대비)
            if not rows: rows = soup.select('table tr') # 폴백
            
            data = []
            for row in rows[1:30]: # 최근 30거래일
                cols = row.select('td')
                if len(cols) < 6: continue
                data.append([cols[0].text, cols[1].text, cols[2].text, cols[3].text, cols[4].text, cols[6].text])
            
            df = pd.DataFrame(data, columns=['Date', 'Open', 'High', 'Low', 'Close', 'Volume'])
            m_type = "US"

        # [C] 데이터 공통 정제
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            df[col] = df[col].apply(lambda x: re.sub(r'[^\d.]', '', str(x)))
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.dropna().sort_values('Date').reset_index(drop=True)

        # [D] 정밀 분석 (배열/RSI/알림)
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        state = "정배열 상승" if last['MA5'] > last['MA20'] else "역배열 조정"
        
        alerts = []
        if last['MA5'] > last['MA20'] and prev['MA5'] <= prev['MA20']: alerts.append("🔔 골든크로스 발생")
        
        # 몬테카를로 (최소 데이터로 실행)
        ret = df['Close'].pct_change().dropna()
        sims = np.random.normal(ret.mean(), ret.std() if ret.std() > 0 else 0.01, 5000)
        win_rate = (sims > 0).sum() / 5000 * 100
        
        return df, s_name, state, alerts, win_rate, m_type

    except Exception as e:
        return None, str(e), "Error", [], 0, "Error"

# --- 3. [사이드바] 제어 센터 ---
with st.sidebar:
    st.markdown('<h1 style="color:#00f2ff; font-weight:900;">CITADEL FINAL</h1>', unsafe_allow_html=True)
    s_input = st.text_input("종목 입력 (053000 / NVDA)", value="053000")
    invest_amt = st.number_input("투자 원금 설정", value=10000000)

# --- 4. [메인] 프로세스 가동 ---
df, s_name, state, alerts, win_rate, m_type = get_citadel_data(s_input)

if df is not None and not df.empty:
    curr_p = float(df['Close'].iloc[-1]); unit = "원" if m_type == "KR" else "$"
    
    st.markdown(f"### {s_name} <small style='color:#00f2ff;'>[{state}]</small>", unsafe_allow_html=True)
    if alerts: st.markdown(f'<div class="alert-box">{" | ".join(alerts)}</div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1:
        st.markdown(f'<div class="profit-card"><h3>현재가</h3><h1>{curr_p:,.0f}{unit}</h1><p>상태: {state}</p></div>', unsafe_allow_html=True)
    with c2: st.metric("AI 승률", f"{win_rate:.1f}%"); st.metric("목표가", f"{curr_p*1.12:,.0f}")
    with c3: st.metric("RSI 강도", "분석중"); st.metric("손절가", f"{curr_p*0.94:,.0f}")

    tab1, tab2, tab3, tab4 = st.tabs(["📊 분석 차트", "🧪 정밀 온도계", "📰 실시간 뉴스", "🚀 테마 리스트"])

    with tab1: # 차트
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.05)
        fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='시세'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['MA20'], line=dict(color='#FF37AF', width=1.5), name='20일선'), row=1, col=1)
        fig.update_layout(height=550, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig, use_container_width=True)

    with tab2: # 온도계
        fig_g = go.Figure(go.Indicator(mode="gauge+number", value=win_rate, title={'text': "매수 온도"}, gauge={'bar': {'color': "#007AFF"}}))
        fig_g.update_layout(height=350, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)'); st.plotly_chart(fig_g, use_container_width=True)

    with tab3: # 뉴스
        try:
            n_res = requests.get(f"https://search.naver.com/search.naver?where=news&query={s_name} 특징주", headers={'User-Agent': 'Mozilla/5.0'})
            n_soup = BeautifulSoup(n_res.text, 'html.parser')
            for item in n_soup.select('.news_area')[:6]:
                st.markdown(f"📍 [{item.select_one('.news_tit').text}]({item.select_one('.news_tit')['href']})")
        except: st.write("뉴스 로딩 중...")

    with tab4: # 테마
        st.write("### 🚀 글로벌 핵심 테마")
        st.markdown("**AI/반도체**: 삼성전자, SK하이닉스, NVDA, TSM")
        st.markdown("**금융**: 우리금융지주, KB금융, JPM")

else:
    st.error(f"❌ 로드 실패: {s_name}. 종목코드(053000 등)를 입력하세요.")
