import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO

# --- 1. [디자인] 불사조급 안정성 UI ---
st.set_page_config(layout="wide", page_title="Aegis Oracle v118.0")
st.markdown("""
    <style>
    body, .stApp { background-color: #030303; color: #e0e0e0; font-family: 'Pretendard'; }
    .verdict-box { border: 2px solid #00f2ff; padding: 20px; border-radius: 15px; margin-bottom: 20px; }
    .profit-card { background: linear-gradient(135deg, #0055ff, #00aaff); padding: 25px; border-radius: 20px; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [엔진] 무적의 로더 (Error-Proof) ---
@st.cache_data(ttl=30) # 캐시 시간을 줄여 실시간성 확보
def get_ultra_stable_data(symbol):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        if symbol.isdigit() and len(symbol) == 6: # 국장
            url = f"https://finance.naver.com/item/sise_day.naver?code={symbol}&page=1"
            res = requests.get(url, headers=headers)
            # read_html은 BeautifulSoup보다 훨씬 안정적으로 표만 골라냅니다.
            df = pd.read_html(StringIO(res.text))[0].dropna()
            df.columns = ['Date', 'Close', 'Net', 'Open', 'High', 'Low', 'Volume']
            m_type = "KR"
        else: # 미장
            df = yf.download(symbol.upper(), period="1y", progress=False).reset_index()
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df.columns = [str(c).capitalize() for c in df.columns]
            m_type = "US"
        
        # 데이터 정제 및 이동평균선/볼린저밴드 계산
        df = df.sort_values('Date').reset_index(drop=True)
        df['MA20'] = df['Close'].rolling(20).mean()
        std = df['Close'].rolling(20).std()
        df['BB_U'] = df['MA20'] + (std * 2)
        df['BB_L'] = df['MA20'] - (std * 2)
        
        # 몬테카를로 분석 (승률 계산)
        ret = df['Close'].pct_change().dropna()
        sims = np.random.normal(ret.mean(), ret.std(), 5000)
        win_rate = (sims > 0).sum() / 5000 * 100
        
        return df, win_rate, m_type
    except Exception as e:
        return None, 0, str(e)

# --- 3. [실행] ---
s_input = st.sidebar.text_input("📊 종목코드 (053000 등)", value="053000")
df, win_rate, m_type = get_ultra_stable_data(s_input)

if df is not None:
    st.write(f"### 분석 결과: {s_input} ({m_type})")
    
    # AI 의견 요약
    last_p = df['Close'].iloc[-1]
    action = "🔥 매수 적기" if win_rate > 55 else "⚖️ 관망"
    st.markdown(f'<div class="verdict-box"><h4>🤖 AI 의견: {action}</h4>승률 {win_rate:.1f}% 구간입니다.</div>', unsafe_allow_html=True)
    
    # 전문가용 차트
    fig = make_subplots(rows=1, cols=1)
    fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="시세"))
    fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_U'], line=dict(color='red', dash='dash'), name="과열선"))
    fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_L'], line=dict(color='cyan', dash='dash'), name="침체선"))
    fig.update_layout(height=500, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.error(f"⚠️ 데이터 로드 실패. 원인: {m_type}")
    st.info("잠시 후 다시 시도하거나, 종목코드를 다시 확인해 주세요.")
