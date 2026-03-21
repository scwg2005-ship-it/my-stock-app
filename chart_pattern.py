import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO
from bs4 import BeautifulSoup
from datetime import datetime

# --- 1. [디자인] 증권사 프리미엄 퀀트 터미널 CSS ---
st.set_page_config(layout="wide", page_title="Aegis Oracle Restoration v116.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;900&display=swap');
    body, .stApp { background-color: #030303; font-family: 'Pretendard', sans-serif; color: #e0e0e0; }
    .stMetric { background-color: #0f0f0f; padding: 25px; border-radius: 18px; border: 1px solid #1e1e1e; }
    .profit-card { background: linear-gradient(135deg, #0055ff 0%, #00aaff 100%); padding: 30px; border-radius: 24px; color: white; text-align: center; margin-bottom: 25px; }
    .verdict-box { background-color: #0e1621; border: 2px solid #00f2ff; padding: 25px; border-radius: 20px; margin-bottom: 30px; }
    .guide-box { background-color: #0a0f1e; border: 1px dashed #00f2ff; padding: 20px; border-radius: 15px; margin-top: 30px; line-height: 1.7; }
    .guide-title { color: #00f2ff; font-weight: 900; font-size: 1.2rem; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [엔진] 무결성 하이브리드 로더 (v115.0 안정성 유지) ---
@st.cache_data(ttl=60)
def get_restored_data(symbol):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
    try:
        is_kr = symbol.isdigit() and len(symbol) == 6
        if is_kr:
            # 국장 로드 (데이터 축적을 위해 10페이지 수집)
            df_list = []
            for p in range(1, 11):
                url = f"https://finance.naver.com/item/sise_day.naver?code={symbol}&page={p}"
                res = requests.get(url, headers=headers)
                dfs = pd.read_html(StringIO(res.text))
                df_list.append(dfs[0].dropna())
            df = pd.concat(df_list).reset_index(drop=True)
            df.columns = ['Date', 'Close', 'Net', 'Open', 'High', 'Low', 'Volume']
            df['Date'] = pd.to_datetime(df['Date'])
            
            n_res = requests.get(f"https://finance.naver.com/item/main.naver?code={symbol}", headers=headers)
            name_soup = BeautifulSoup(n_res.text, 'html.parser')
            # 안정적인 종목명 파싱 (v103.0 방식 폴백 추가)
            name_tag = name_soup.select_one('.wrap_company h2 a')
            s_name = name_tag.text.strip() if name_tag else f"KOSPI:{symbol}"
            m_type = "KR"
            
            # 뉴스 (URL 포함)
            n_res = requests.get(f"https://search.naver.com/search.naver?where=news&query={s_name} 특징주", headers=headers)
            soup = BeautifulSoup(n_res.text, 'html.parser')
            news_list = [{'title': i.select_one('.news_tit').text, 'link': i.select_one('.news_tit')['href']} for i in soup.select('.news_area')[:10]]
        else:
            # 미장 로드
            ticker = yf.Ticker(symbol.upper())
            df = ticker.history(period="2y").reset_index()
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df.columns = [str(c).capitalize() for c in df.columns]
            s_name = symbol.upper()
            m_type = "US"
            news_list = [{'title': f'{s_name} 실시간 뉴스 (Investing.com)', 'link': f'https://kr.investing.com/search/?q={s_name}'}]

        for col in ['Close', 'Open', 'High', 'Low', 'Volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.sort_values('Date').reset_index(drop=True)
        
        # --- [차트 복원] 풍부한 기술 지표 계산 ---
        # 1. 이동평균선 (5, 20, 60, 120일)
        for ma in [5, 20, 60, 120]:
            if len(df) >= ma: df[f'MA{ma}'] = df['Close'].rolling(ma).mean()
        
        # 2. 예측 밴드 (Bollinger)
        if len(df) >= 20:
            std_dev = df['Close'].rolling(20).std()
            df['BB_Upper'] = df['MA20'] + (std_dev * 2)
            df['BB_Lower'] = df['MA20'] - (std_dev * 2)
        
        # 3. RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))

        # 시뮬레이션
        ret = df['Close'].pct_change().dropna()
        sims = np.random.normal(ret.mean(), ret.std() if ret.std() > 0 else 0.01, 5000)
        win_rate = (sims > 0).sum() / 5000 * 100
        avg_profit = sims.mean() * 100

        # AI 최종 의견
        last_p = df['Close'].iloc[-1]
        action = "🔥 적극 매수" if win_rate >= 60 else "⚠️ 과열/관망" if win_rate <= 40 else "⚖️ 보유/중립"
        verdict = f"현재 승률 {win_rate:.1f}% 구간입니다."

        return df, s_name, win_rate, avg_profit, m_type, sims, action, verdict, news_list
    except Exception as e:
        return None, str(e), 0, 0, "Error", [], "", "", []

# --- 3. [메인] ---
s_input = st.sidebar.text_input("📊 종목코드", value="053000") # 우리금융지주
invest_amt = st.sidebar.number_input("💰 투자 원금", value=10000000)

df, s_name, win_rate, avg_profit, m_type, sims, action, verdict_text, news = get_restored_data(s_input)

if df is not None and not df.empty:
    curr_p = float(df['Close'].iloc[-1]); unit = "원" if m_type == "KR" else "$"
    
    st.markdown(f"## {s_name} ({s_input})")
    
    st.markdown(f"""<div class="verdict-box">
        <div style="color:#00f2ff; font-weight:800; margin-bottom:5px;">🤖 AI 최종 매매 의견</div>
        <div style="font-size:1.5rem; font-weight:900;">{action}</div>
        <div style="color:#cccccc;">{verdict_text}</div>
    </div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1: st.markdown(f'<div class="profit-card"><h3>내일 기대수익</h3><h1>{avg_profit:+.2f}%</h1></div>', unsafe_allow_html=True)
    with c2: st.metric("현재가", f"{curr_p:,.0f}{unit}"); st.metric("AI 승률", f"{win_rate:.1f}%")
    with c3: st.metric("목표가", f"{curr_p*1.15:,.0f}{unit}"); st.metric("손절가", f"{curr_p*0.94:,.0f}{unit}")

    tab1, tab2, tab3 = st.tabs(["📉 전문가 정밀 분석 차트", "🧪 퀀트 온도계", "📰 실시간 특징주 뉴스"])

    with tab1: # --- [복원 완료] 전문가용 퀀트 차트 ---
        # 1. 서브플롯 생성 (주가 / 거래량)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.05)
        
        # 2. 캔들차트 (Candlestick)
        fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='시세'), row=1, col=1)
        
        # 3. [복원] 풍부한 이동평균선 레이어
        ma_cfg = {5: '#FFD60A', 20: '#FF37AF', 60: '#00F2FF', 120: '#FFFFFF'}
        for ma, clr in ma_cfg.items():
            if f'MA{ma}' in df.columns:
                fig.add_trace(go.Scatter(x=df['Date'], y=df[f'MA{ma}'], line=dict(color=clr, width=1.5), name=f'{ma}선'), row=1, col=1)
        
        # 4. 예측 밴드 (Bollinger Bands)
        if 'BB_Upper' in df.columns:
            fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_Upper'], line=dict(color='rgba(255,55,175,0.3)', dash='dash'), name='과열선'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_Lower'], line=dict(color='rgba(0,170,255,0.3)', dash='dash'), fill='tonexty', fillcolor='rgba(0,170,255,0.03)', name='침체선'), row=1, col=1)
        
        # 5. [복원] 하단 거래량 차트 (Volume Bar)
        # 당일 시가 대비 종가 상승/하락에 따른 거래량 색상 지정
        colors = ['#ff37af' if df['Close'].iloc[i] > df['Open'].iloc[i] else '#00aaff' for i in range(len(df))]
        fig.add_trace(go.Bar(x=df['Date'], y=df['Volume'], marker_color=colors, name='거래량'), row=2, col=1)
        
        fig.update_layout(height=700, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(t=0, b=0, l=10, r=10), showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("""<div class="guide-box"><div class="guide-title">🔍 전문가 조언: 차트 읽는 법</div>
        차트는 캔들, 이동평균선(5,20,60,120), 거래량, 볼린저 밴드로 구성됩니다. 
        <b>파란 침체선</b>에 주가가 닿거나 <b>60일선(청록색)</b>을 지지할 때 매수 타점으로 잡고, <b>빨간 과열선</b>을 뚫을 때 익절을 고려하세요.</div>""", unsafe_allow_html=True)

    with tab2: # 2P 온도계 (기능 유지)
        col1, col2 = st.columns(2)
        with col1:
            fig_g = go.Figure(go.Indicator(mode="gauge+number", value=win_rate, title={'text': "매수 온도"}, gauge={'bar': {'color': "#0055ff"}}))
            st.plotly_chart(fig_g, use_container_width=True)
        with col2:
            fig_h = go.Figure()
            sims_pct = sims * 100
            fig_h.add_trace(go.Histogram(x=sims_pct[sims_pct >= 0], name='상승', marker_color='#007AFF', opacity=0.7)); fig_h.add_trace(go.Histogram(x=sims_pct[sims_pct < 0], name='하락', marker_color='#ff37af', opacity=0.7))
            fig_h.update_layout(title='수익률 확률 분포도', template='plotly_dark')
            st.plotly_chart(fig_h, use_container_width=True)

    with tab3: # 3P 뉴스룸 (URL 포함, 기능 유지)
        st.markdown("#### 📰 실시간 특징주 속보 (TOP 10)")
        if news:
            for n in news: st.markdown(f"📍 [{n['title']}]({n['link']})")
        else: st.write("소식을 불러오는 중입니다.")

else:
    st.error("데이터 로드 실패.")
