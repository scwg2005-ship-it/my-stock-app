import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO

# --- 1. [디자인] 전문가용 다크 터미널 ---
st.set_page_config(layout="wide", page_title="Aegis Oracle v103.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;900&display=swap');
    body, .stApp { background-color: #050505; font-family: 'Pretendard', sans-serif; color: #e0e0e0; }
    .stMetric { background-color: #111; padding: 20px; border-radius: 15px; border: 1px solid #222; }
    .profit-card { background: linear-gradient(135deg, #0055ff 0%, #00aaff 100%); padding: 25px; border-radius: 20px; color: white; text-align: center; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [엔진] 무적의 데이터 로더 (Pandas 전용) ---
@st.cache_data(ttl=60)
def get_core_data(code):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
    try:
        # 1. 일별 시세 페이지 (모바일 주소 사용 - 보안이 더 낮음)
        url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page=1"
        res = requests.get(url, headers=headers)
        
        # [해결책] read_html을 사용하여 표를 통째로 가져옴 (NoneType 에러 방지)
        dfs = pd.read_html(StringIO(res.text))
        df = dfs[0].dropna()
        
        if df.empty or len(df.columns) < 7:
            df = dfs[1].dropna()

        # 컬럼명 강제 재정의
        df.columns = ['Date', 'Close', 'Net', 'Open', 'High', 'Low', 'Volume']
        
        # 데이터 정제
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.dropna(subset=['Date'])
        
        for col in ['Close', 'Open', 'High', 'Low', 'Volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        df = df.sort_values('Date').reset_index(drop=True)

        # 기술 지표 계산
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        
        # 몬테카를로 승률 계산
        returns = df['Close'].pct_change().dropna()
        sims = np.random.normal(returns.mean(), returns.std() if returns.std() > 0 else 0.01, 5000)
        win_rate = (sims > 0).sum() / 5000 * 100
        
        return df, win_rate
    except Exception as e:
        return None, str(e)

# --- 3. [사이드바] 제어 센터 ---
with st.sidebar:
    st.markdown('<h2 style="color:#00f2ff;">Oracle Master</h2>', unsafe_allow_html=True)
    s_code = st.text_input("📊 종목코드 (6자리)", value="053000") # 우리금융지주
    invest_amt = st.number_input("💰 투자 원금 (원)", value=10000000)

# --- 4. [메인] 분석 프로세스 ---
df, result = get_core_data(s_code)

if df is not None and not df.empty:
    curr_p = float(df['Close'].iloc[-1])
    win_rate = result
    
    st.markdown(f"### 종목코드: {s_code}")
    
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1:
        st.markdown(f'<div class="profit-card"><h1>{curr_p:,.0f}원</h1><p>현재가 분석 리포트</p></div>', unsafe_allow_html=True)
    with c2: st.metric("AI 승률", f"{win_rate:.1f}%"); st.metric("목표가", f"{curr_p*1.12:,.0f}")
    with c3: st.metric("손절가", f"{curr_p*0.94:,.0f}"); st.metric("20일평균", f"{df['MA20'].iloc[-1]:,.0f}")

    tab1, tab2, tab3 = st.tabs(["📉 분석 차트", "🧪 정밀 온도계", "📰 실시간 뉴스"])

    with tab1:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.05)
        fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='시세'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['MA20'], line=dict(color='#FF37AF', width=1.5), name='20일선'), row=1, col=1)
        fig.update_layout(height=550, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        fig_g = go.Figure(go.Indicator(mode="gauge+number", value=win_rate, title={'text': "매수 온도"}, gauge={'bar': {'color': "#007AFF"}}))
        fig_g.update_layout(height=350, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)'); st.plotly_chart(fig_g, use_container_width=True)

    with tab3:
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            n_res = requests.get(f"https://search.naver.com/search.naver?where=news&query={s_code} 특징주", headers=headers)
            # 뉴스 파싱 부분도 최대한 단순화하여 에러 방지
            st.write(f"[{s_code}] 관련 최신 뉴스는 네이버에서 실시간으로 확인하실 수 있습니다.")
            st.markdown(f"- [네이버 뉴스 바로가기](https://search.naver.com/search.naver?where=news&query={s_code}%20특징주)")
        except: st.write("뉴스 연결 실패")

else:
    st.error(f"❌ 데이터 로드 실패. (에러내용: {result})")
