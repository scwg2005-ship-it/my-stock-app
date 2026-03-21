import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO
from bs4 import BeautifulSoup

# --- 1. [VIP 터미널 디자인] ---
st.set_page_config(layout="wide", page_title="Aegis Oracle v119.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;900&display=swap');
    body, .stApp { background-color: #030303; font-family: 'Pretendard'; color: #e0e0e0; }
    .stMetric { background-color: #0f0f0f; padding: 20px; border-radius: 15px; border: 1px solid #1e1e1e; }
    .profit-card { background: linear-gradient(135deg, #0055ff, #00aaff); padding: 30px; border-radius: 20px; color: white; text-align: center; }
    .verdict-box { background-color: #0e1621; border: 2px solid #00f2ff; padding: 20px; border-radius: 15px; margin-bottom: 20px; }
    .alert-box { background: linear-gradient(90deg, #ffcc00, #ff9900); color: black; padding: 15px; border-radius: 10px; font-weight: 900; text-align: center; margin-bottom: 20px; font-size: 1.2rem; border: 2px solid #fff; }
    .guide-box { background-color: #0a0f1e; border: 1px dashed #00f2ff; padding: 15px; border-radius: 12px; margin-top: 20px; }
    .recommend-box { background: #111; padding: 15px; border-radius: 10px; border: 1px solid #333; margin-bottom: 10px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [무적의 하이브리드 로더 & 알림 엔진] ---
@st.cache_data(ttl=60)
def get_final_empire_data(symbol):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        is_kr = symbol.isdigit() and len(symbol) == 6
        if is_kr:
            # 국장 데이터 (100일치 확보)
            df_list = []
            for p in range(1, 10):
                url = f"https://finance.naver.com/item/sise_day.naver?code={symbol}&page={p}"
                res = requests.get(url, headers=headers)
                df_list.append(pd.read_html(StringIO(res.text))[0].dropna())
            df = pd.concat(df_list).reset_index(drop=True)
            df.columns = ['Date', 'Close', 'Net', 'Open', 'High', 'Low', 'Volume']
            df['Date'] = pd.to_datetime(df['Date'])
            m_type = "KR"
            # 종목명 파싱
            n_res = requests.get(f"https://finance.naver.com/item/main.naver?code={symbol}", headers=headers)
            soup = BeautifulSoup(n_res.text, 'html.parser')
            s_name = soup.select_one('.wrap_company h2 a').text.strip() if soup.select_one('.wrap_company h2 a') else symbol
        else:
            # 미장 데이터
            df = yf.download(symbol.upper(), period="1y", progress=False).reset_index()
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df.columns = [str(c).capitalize() for c in df.columns]
            s_name = symbol.upper()
            m_type = "US"

        df = df.sort_values('Date').reset_index(drop=True)
        
        # 지표 계산 (5, 20, 60, 120일선)
        for ma in [5, 20, 60, 120]: df[f'MA{ma}'] = df['Close'].rolling(ma).mean()
        std = df['Close'].rolling(20).std()
        df['BB_U'] = df['MA20'] + (std * 2)
        df['BB_L'] = df['MA20'] - (std * 2)
        
        # RSI
        delta = df['Close'].diff(); gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))

        # 몬테카를로 (5,000회)
        ret = df['Close'].pct_change().dropna()
        sims = np.random.normal(ret.mean(), ret.std(), 5000)
        win_rate = (sims > 0).sum() / 5000 * 100
        avg_profit = sims.mean() * 100

        # --- [매수 타이밍 알림 로직] ---
        alerts = []
        last = df.iloc[-1]; prev = df.iloc[-2]
        if last['MA5'] > last['MA20'] and prev['MA5'] <= prev['MA20']: alerts.append("🎯 [골든크로스] 단기 추세 반전! 매수 검토")
        if last['RSI'] <= 30: alerts.append("⚓ [과매도] RSI 30 이하! 기술적 반등 임박")
        if last['Close'] <= last['BB_L']: alerts.append("🛡️ [침체선 터치] 확률적 최저점 도달! 풀매수 찬스")
        if win_rate >= 65: alerts.append("🚀 [AI 승률 폭발] 통계적 상승 확률 압도적")

        return df, s_name, win_rate, avg_profit, m_type, sims, alerts
    except Exception as e:
        return None, str(e), 0, 0, "Error", [], []

# --- 3. [메인 화면] ---
s_input = st.sidebar.text_input("📊 종목코드", value="053000")
invest_amt = st.sidebar.number_input("💰 투자금", value=10000000)

df, s_name, win_rate, avg_profit, m_type, sims, alerts = get_final_empire_data(s_input)

if df is not None:
    st.markdown(f"## {s_name} ({s_input})")
    
    # [1] 실시간 매수 타이밍 알림 (있을 때만 표시)
    if alerts:
        for alert in alerts:
            st.markdown(f'<div class="alert-box">{alert}</div>', unsafe_allow_html=True)
    
    # [2] AI 최종 의견
    action = "🔥 적극 매수" if win_rate > 60 else "⚖️ 관망/보유"
    st.markdown(f"""<div class="verdict-box">
        <div style="color:#00f2ff; font-weight:800;">🤖 AI 종합 판정</div>
        <div style="font-size:1.5rem; font-weight:900;">{action}</div>
        <div>현재 시장 데이터 분석 결과, 승률 {win_rate:.1f}% 구간에 위치해 있습니다.</div>
    </div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1: st.markdown(f'<div class="profit-card"><h3>내일 기대수익</h3><h1>{avg_profit:+.2f}%</h1><p>예상 손익: {invest_amt*(avg_profit/100):+,.0f}</p></div>', unsafe_allow_html=True)
    with c2: st.metric("현재가", f"{df['Close'].iloc[-1]:,.0f}"); st.metric("승률", f"{win_rate:.1f}%")
    with c3: st.metric("RSI", f"{df['RSI'].iloc[-1]:.1f}"); st.metric("거래량", f"{df['Volume'].iloc[-1]:,.0f}")

    tab1, tab2, tab3, tab4 = st.tabs(["📉 정밀 차트", "🧪 퀀트 온도계", "📰 뉴스/재무", "🚀 테마"])

    with tab1: # 정밀 분석 차트
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.05)
        fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='시세'), row=1, col=1)
        colors = {'MA5':'yellow', 'MA20':'magenta', 'MA60':'cyan', 'MA120':'white'}
        for ma, clr in colors.items(): fig.add_trace(go.Scatter(x=df['Date'], y=df[ma], line=dict(color=clr, width=1.5), name=ma), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_U'], line=dict(color='red', dash='dash'), name='과열선'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_L'], line=dict(color='blue', dash='dash'), name='침체선'), row=1, col=1)
        # 거래량
        v_colors = ['red' if df['Close'].iloc[i] > df['Open'].iloc[i] else 'blue' for i in range(len(df))]
        fig.add_trace(go.Bar(x=df['Date'], y=df['Volume'], marker_color=v_colors), row=2, col=1)
        fig.update_layout(height=650, template='plotly_dark', xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

    with tab2: # 온도계
        col1, col2 = st.columns(2)
        with col1: st.plotly_chart(go.Figure(go.Indicator(mode="gauge+number", value=win_rate, gauge={'bar':{'color':'#0055ff'}})).update_layout(template='plotly_dark'))
        with col2:
            fig_h = go.Figure()
            fig_h.add_trace(go.Histogram(x=sims*100, marker_color='#00aaff'))
            fig_h.update_layout(title="수익률 분포", template='plotly_dark')
            st.plotly_chart(fig_h, use_container_width=True)

    with tab3: # 뉴스 (URL)
        st.markdown("#### 📰 실시간 주요 뉴스")
        res = requests.get(f"https://search.naver.com/search.naver?where=news&query={s_name} 특징주")
        soup = BeautifulSoup(res.text, 'html.parser')
        for item in soup.select('.news_area')[:8]:
            st.write(f"📍 [{item.select_one('.news_tit').text}]({item.select_one('.news_tit')['href']})")

    with tab4: # 테마
        st.markdown("#### 🚀 AI 선정 주도 테마")
        st.markdown("<div class='recommend-box'>🤖 AI/반도체: NVDA, SK하이닉스 💎💎💎</div>", unsafe_allow_html=True)
        st.markdown("<div class='recommend-box'>💰 금융/저PBR: 우리금융지주, KB금융 💎💎💎</div>", unsafe_allow_html=True)
else:
    st.error("데이터 로드 실패. 잠시 후 새로고침해 주세요.")
