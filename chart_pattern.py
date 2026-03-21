import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO
from bs4 import BeautifulSoup
import time

# --- 1. [VIP 터미널 디자인] ---
st.set_page_config(layout="wide", page_title="Aegis Oracle v123.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;900&display=swap');
    body, .stApp { background-color: #030303; font-family: 'Pretendard'; color: #e0e0e0; }
    .stMetric { background-color: #0f0f0f; padding: 25px; border-radius: 18px; border: 1px solid #1e1e1e; }
    .profit-card { background: linear-gradient(135deg, #0055ff 0%, #00aaff 100%); padding: 30px; border-radius: 24px; color: white; text-align: center; margin-bottom: 25px; }
    .action-box { background-color: #0e1621; border: 2px solid #00f2ff; padding: 25px; border-radius: 20px; margin-bottom: 30px; box-shadow: 0 0 15px rgba(0,242,255,0.2); }
    .guide-box { background-color: #0a0f1e; border: 1px dashed #00f2ff; padding: 20px; border-radius: 15px; margin-top: 20px; line-height: 1.8; }
    .highlight { color: #00f2ff; font-weight: 800; }
    .news-link { color: #00aaff; text-decoration: none; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [엔진] 고성능 정밀 파싱 로더 (안정성 200% 강화) ---
@st.cache_data(ttl=60)
def get_absolute_integrity_data(symbol):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
    try:
        is_kr = symbol.isdigit() and len(symbol) == 6
        if is_kr:
            # [국장] BeautifulSoup 정밀 파싱 (read_html 대체)
            df_list = []
            for p in range(1, 6):
                url = f"https://finance.naver.com/item/sise_day.naver?code={symbol}&page={p}"
                res = requests.get(url, headers=headers)
                soup = BeautifulSoup(res.text, 'html.parser')
                table = soup.select_one('table.type2')
                if table:
                    temp_df = pd.read_html(StringIO(str(table)))[0].dropna()
                    df_list.append(temp_df)
                time.sleep(0.1) # 서버 부하 방지
            
            df = pd.concat(df_list).reset_index(drop=True)
            df.columns = ['Date', 'Close', 'Net', 'Open', 'High', 'Low', 'Volume']
            df['Date'] = pd.to_datetime(df['Date'])
            
            # 종목명 및 뉴스 추출 (안전 모드)
            m_res = requests.get(f"https://finance.naver.com/item/main.naver?code={symbol}", headers=headers)
            m_soup = BeautifulSoup(m_res.text, 'html.parser')
            s_name = m_soup.select_one('title').text.split(':')[0].strip() if m_soup.select_one('title') else symbol
            
            # 뉴스 URL 10개 추출
            news_res = requests.get(f"https://search.naver.com/search.naver?where=news&query={s_name} 특징주", headers=headers)
            n_soup = BeautifulSoup(news_res.text, 'html.parser')
            news_items = [{'title': i.select_one('.news_tit').text, 'link': i.select_one('.news_tit')['href']} for i in n_soup.select('.news_area')[:10]]
            m_type = "KR"
        else:
            # [미장] yfinance 로드
            ticker = yf.Ticker(symbol.upper())
            df = ticker.history(period="1y").reset_index()
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df.columns = [str(c).capitalize() for c in df.columns]
            s_name = symbol.upper()
            news_items = [{'title': f'{s_name} Investing.com 실시간 뉴스', 'link': f'https://kr.investing.com/search/?q={s_name}'}]
            m_type = "US"

        # 지표 계산
        df = df.sort_values('Date').reset_index(drop=True)
        for ma in [5, 20, 60, 120]: df[f'MA{ma}'] = df['Close'].rolling(ma).mean()
        std = df['Close'].rolling(20).std()
        df['BB_U'], df['BB_L'] = df['MA20'] + (std * 2), df['MA20'] - (std * 2)
        
        # RSI & 몬테카를로
        delta = df['Close'].diff(); gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
        
        ret = df['Close'].pct_change().dropna()
        sims = np.random.normal(ret.mean(), ret.std(), 5000)
        win_rate = (sims > 0).sum() / 5000 * 100
        avg_profit = sims.mean() * 100

        # AI 액션 플랜 판정
        last_p = df['Close'].iloc[-1]
        if win_rate >= 65 and last_p <= df['BB_L'].iloc[-1] * 1.05: action, color = "💎 강력 매수", "#00f2ff"
        elif last_p >= df['BB_U'].iloc[-1] * 0.95: action, color = "⚠️ 분할 매도", "#ff37af"
        elif last_p <= df['MA20'].iloc[-1] * 0.94: action, color = "🚨 즉시 손절", "#ff0000"
        else: action, color = "⚖️ 관망/홀딩", "#ffd60a"

        return df, s_name, win_rate, avg_profit, m_type, sims, news_items, action, color
    except Exception as e:
        return None, str(e), 0, 0, "Error", [], [], "Error", "white"

# --- 3. [메인 프로세스] ---
s_input = st.sidebar.text_input("📊 종목코드", value="053000")
invest_amt = st.sidebar.number_input("💰 투자금", value=10000000)

df, s_name, win_rate, avg_profit, m_type, sims, news, ai_action, ai_color = get_absolute_integrity_data(s_input)

if df is not None and not df.empty:
    curr_p = float(df['Close'].iloc[-1]); unit = "원" if m_type == "KR" else "$"
    
    st.markdown(f"## {s_name} ({s_input})")
    
    # [1] AI 최종 액션 플랜 (매수/매도/손절)
    st.markdown(f"""<div class="action-box">
        <div style="color:#888; font-weight:800; margin-bottom:5px;">🤖 Oracle's Final Action Plan</div>
        <div style="font-size:1.6rem; font-weight:900; color:{ai_color};">{ai_action}</div>
        <div>AI 승률 <span class="highlight">{win_rate:.1f}%</span>를 기반으로 산출된 최종 의사결정입니다.</div>
    </div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1: st.markdown(f'<div class="profit-card"><h3>내일 기대수익</h3><h1>{avg_profit:+.2f}%</h1><p>예상 손익: {invest_amt*(avg_profit/100):+,.0f}{unit}</p></div>', unsafe_allow_html=True)
    with c2: st.metric("현재가", f"{curr_p:,.0f}{unit}"); st.metric("AI 승률", f"{win_rate:.1f}%")
    with c3: st.metric("목표가(+15%)", f"{curr_p*1.15:,.0f}{unit}"); st.metric("손절가(-6%)", f"{curr_p*0.94:,.0f}{unit}")

    tab1, tab2, tab3, tab4 = st.tabs(["📉 전문가 정밀 차트", "🧪 무지개 퀀트 분석", "📰 재무/실시간 뉴스", "🚀 AI 엄선 테마"])

    with tab1: # 1P: 정밀 차트 복원
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.05)
        fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='시세'), row=1, col=1)
        ma_cfg = {5:'yellow', 20:'magenta', 60:'cyan', 120:'white'}
        for ma, clr in ma_cfg.items():
            if f'MA{ma}' in df.columns: fig.add_trace(go.Scatter(x=df['Date'], y=df[f'MA{ma}'], line=dict(color=clr, width=1.5), name=f'{ma}선'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_U'], line=dict(color='red', dash='dash'), name='과열선'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_L'], line=dict(color='blue', dash='dash'), fill='tonexty', fillcolor='rgba(0,170,255,0.03)', name='침체선'), row=1, col=1)
        fig.add_trace(go.Bar(x=df['Date'], y=df['Volume'], marker_color='#333', name='거래량'), row=2, col=1)
        fig.update_layout(height=650, template='plotly_dark', xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('<div class="guide-box"><div class="guide-title">🔍 전문가 조언</div>파란 침체선 터치 시 <b>강력 매수</b>, 빨간 과열선 돌파 시 <b>분할 매도</b>하십시오.</div>', unsafe_allow_html=True)

    with tab2: # 2P: 무지개 온도계 & 히스토그램
        col1, col2 = st.columns([1, 1.2])
        with col1:
            fig_g = go.Figure(go.Indicator(mode="gauge+number", value=win_rate, gauge={
                'bar': {'color': "#0055ff"}, 'steps': [{'range': [0, 40], 'color': '#1a0000'}, {'range': [70, 100], 'color': '#001a1a'}]}))
            st.plotly_chart(fig_g, use_container_width=True)
        with col2:
            sims_pct = sims * 100; counts, bins = np.histogram(sims_pct, bins=50); bins_center = (bins[:-1] + bins[1:]) / 2
            colors = ['#ff37af' if b < 0 else '#007AFF' for b in bins_center]
            fig_h = go.Figure(go.Bar(x=bins_center, y=counts, marker_color=colors, opacity=0.8))
            fig_h.update_layout(title='5,000회 크로마 수익률 분포', template='plotly_dark', height=400); st.plotly_chart(fig_h, use_container_width=True)
        st.markdown('<div class="guide-box"><div class="guide-title">🧪 퀀트 가이드</div>히스토그램의 파란색 막대가 우측으로 쏠려 있을 때 수익 확률이 높습니다.</div>', unsafe_allow_html=True)

    with tab3: # 3P: 실시간 뉴스 URL 직결
        st.markdown("#### 📰 실시간 증권가 소식 (TOP 10)")
        for n in news: st.markdown(f"📍 [{n['title']}]({n['link']})")

    with tab4: # 4P: 테마
        themes = {"🤖 AI/반도체": ["NVDA 💎💎💎", "SK하이닉스 💎💎"], "💰 금융/저PBR": ["우리금융지주 💎💎💎", "KB금융 💎💎"]}
        for t, s in themes.items():
            st.markdown(f"**{t}**: {', '.join(s)}")
else:
    st.error(f"❌ 데이터 로드 실패. (사유: {s_name}) 1분 후 다시 시도해 주세요.")
