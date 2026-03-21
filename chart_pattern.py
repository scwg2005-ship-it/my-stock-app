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
st.set_page_config(layout="wide", page_title="Aegis Oracle v122.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;900&display=swap');
    body, .stApp { background-color: #030303; font-family: 'Pretendard'; color: #e0e0e0; }
    .stMetric { background-color: #0f0f0f; padding: 25px; border-radius: 18px; border: 1px solid #1e1e1e; }
    .profit-card { background: linear-gradient(135deg, #0055ff 0%, #00aaff 100%); padding: 30px; border-radius: 24px; color: white; text-align: center; margin-bottom: 25px; }
    /* AI 액션 플랜 박스 */
    .action-box { background-color: #0e1621; border: 2px solid #00f2ff; padding: 25px; border-radius: 20px; margin-bottom: 30px; box-shadow: 0 0 15px rgba(0,242,255,0.2); }
    .action-title { font-size: 1.6rem; font-weight: 900; margin-bottom: 10px; }
    /* 알림/가이드 스타일 유지 */
    .alert-box { background: linear-gradient(90deg, #ffcc00, #ff9900); color: black; padding: 15px; border-radius: 10px; font-weight: 900; text-align: center; margin-bottom: 20px; font-size: 1.2rem; }
    .guide-box { background-color: #0a0f1e; border: 1px dashed #00f2ff; padding: 20px; border-radius: 15px; margin-top: 20px; }
    .highlight { color: #00f2ff; font-weight: 800; }
    .news-item { border-bottom: 1px solid #222; padding: 12px 0; }
    .news-link { color: #00aaff; text-decoration: none; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [엔진] 무적의 로더 & AI 액션 엔진 ---
@st.cache_data(ttl=60)
def get_imperial_v122_data(symbol):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        is_kr = symbol.isdigit() and len(symbol) == 6
        if is_kr:
            # 국장 데이터 로드 (v103.0 무적 엔진)
            df_list = []
            for p in range(1, 10):
                url = f"https://finance.naver.com/item/sise_day.naver?code={symbol}&page={p}"
                res = requests.get(url, headers=headers)
                df_list.append(pd.read_html(StringIO(res.text))[0].dropna())
            df = pd.concat(df_list).reset_index(drop=True)
            df.columns = ['Date', 'Close', 'Net', 'Open', 'High', 'Low', 'Volume']
            df['Date'] = pd.to_datetime(df['Date'])
            
            # 종목명 및 증권가 뉴스 파싱 (URL 직결)
            n_res = requests.get(f"https://finance.naver.com/item/main.naver?code={symbol}", headers=headers)
            soup = BeautifulSoup(n_res.text, 'html.parser')
            s_name = soup.select_one('.wrap_company h2 a').text.strip()
            
            # 뉴스 로드 (특징주 및 증권사 리포트 뉴스 10개)
            news_res = requests.get(f"https://search.naver.com/search.naver?where=news&query={s_name} 특징주 증권사", headers=headers)
            n_soup = BeautifulSoup(news_res.text, 'html.parser')
            news_list = [{'title': i.select_one('.news_tit').text, 'link': i.select_one('.news_tit')['href'], 'press': i.select_one('.info.press').text if i.select_one('.info.press') else "증권사속보"} for i in n_soup.select('.news_area')[:10]]
            m_type = "KR"
        else:
            # 미장 데이터 로드
            df = yf.download(symbol.upper(), period="2y", progress=False).reset_index()
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df.columns = [str(c).capitalize() for c in df.columns]
            s_name = symbol.upper()
            news_list = [{'title': f'{s_name} 실시간 인베스팅 뉴스', 'link': f'https://kr.investing.com/search/?q={s_name}', 'press': 'Investing.com'}]
            m_type = "US"

        df = df.sort_values('Date').reset_index(drop=True)
        for ma in [5, 20, 60, 120]: df[f'MA{ma}'] = df['Close'].rolling(ma).mean()
        std = df['Close'].rolling(20).std()
        df['BB_U'], df['BB_L'] = df['MA20'] + (std * 2), df['MA20'] - (std * 2)
        
        # 몬테카를로 (5,000회)
        ret = df['Close'].pct_change().dropna()
        sims = np.random.normal(ret.mean(), ret.std(), 5000)
        win_rate = (sims > 0).sum() / 5000 * 100
        avg_profit = sims.mean() * 100

        # --- [신규 기능] AI 최종 액션 플랜 판정 ---
        last_p = df['Close'].iloc[-1]
        bb_u = df['BB_U'].iloc[-1]
        bb_l = df['BB_L'].iloc[-1]
        
        if win_rate >= 70 and last_p <= bb_l * 1.05:
            action, color = "💎 강력 매수 (Strong Buy)", "#00f2ff"
        elif win_rate >= 55 and last_p <= df['MA20'].iloc[-1]:
            action, color = "📈 분할 매수 (Buy)", "#00ffaa"
        elif last_p >= bb_u * 0.95:
            action, color = "⚠️ 분할 매도 (Sell)", "#ff37af"
        elif last_p <= curr_p * 0.94: # 손절가 도달 시
            action, color = "🚨 즉시 손절 (Cut Loss)", "#ff0000"
        else:
            action, color = "⚖️ 관망/홀딩 (Neutral)", "#ffd60a"

        return df, s_name, win_rate, avg_profit, m_type, sims, news_list, action, color
    except Exception as e:
        return None, str(e), 0, 0, "Error", [], [], "Error", "white"

# --- 3. [메인 화면 구성] ---
s_input = st.sidebar.text_input("📊 종목코드", value="053000") # 우리금융지주
invest_amt = st.sidebar.number_input("💰 투자 원금", value=10000000)

df, s_name, win_rate, avg_profit, m_type, sims, news, ai_action, ai_color = get_imperial_v122_data(s_input)

if df is not None and not df.empty:
    curr_p = float(df['Close'].iloc[-1]); unit = "원" if m_type == "KR" else "$"
    
    st.markdown(f"## {s_name} ({s_input})")
    
    # [1] AI 최종 액션 플랜 박스 (매수/매도/손절 신호 통합)
    st.markdown(f"""
    <div class="action-box">
        <div style="color:#888; font-weight:800; margin-bottom:5px;">🤖 Oracle's Final Action Plan</div>
        <div class="action-title" style="color:{ai_color};">{ai_action}</div>
        <div style="color:#cccccc;">AI 승률 {win_rate:.1f}%와 변동성 밴드를 종합 분석한 <span class="highlight">최종 의사결정</span>입니다.</div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1: st.markdown(f'<div class="profit-card"><h3>내일 기대수익</h3><h1>{avg_profit:+.2f}%</h1><p>예상 손익: {invest_amt*(avg_profit/100):+,.0f}{unit}</p></div>', unsafe_allow_html=True)
    with c2: st.metric("현재가", f"{curr_p:,.0f}{unit}"); st.metric("AI 승률", f"{win_rate:.1f}%")
    with c3: st.metric("목표가(+15%)", f"{curr_p*1.15:,.0f}{unit}"); st.metric("손절가(-6%)", f"{curr_p*0.94:,.0f}{unit}")

    tab1, tab2, tab3, tab4 = st.tabs(["📉 전문가 차트 분석", "🧪 무지개 퀀트 분석", "📰 재무/실시간 뉴스룸", "🚀 AI 추천 테마"])

    with tab1: # 1P 차트 & 가이드 (v120.0 유지)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.05)
        fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='시세'), row=1, col=1)
        clrs = {'MA5':'yellow', 'MA20':'magenta', 'MA60':'cyan', 'MA120':'white'}
        for ma, clr in clrs.items(): fig.add_trace(go.Scatter(x=df['Date'], y=df[ma], line=dict(color=clr, width=1.5), name=f'{ma}선'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_U'], line=dict(color='rgba(255,55,175,0.4)', dash='dash'), name='과열선'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_L'], line=dict(color='rgba(0,170,255,0.4)', dash='dash'), fill='tonexty', fillcolor='rgba(0,170,255,0.03)', name='침체선'), row=1, col=1)
        fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('<div class="guide-box"><div class="guide-title">🔍 전문가 조언</div>파란 침체선에 주가가 닿으면 <b>강력 매수</b>, 빨간 과열선을 뚫으면 <b>분할 매도</b>하십시오.</div>', unsafe_allow_html=True)

    with tab2: # 2P 무지개 온도계 & 크로마 분포표 (v120.0 유지)
        col1, col2 = st.columns([1, 1.2])
        with col1:
            st.plotly_chart(go.Figure(go.Indicator(mode="gauge+number", value=win_rate, gauge={
                'bar': {'color': "#0055ff"}, 'steps': [{'range': [0, 20], 'color': '#1a0000'}, {'range': [20, 40], 'color': '#1a0d00'},
                {'range': [40, 60], 'color': '#1a1a00'}, {'range': [60, 80], 'color': '#001a0d'}, {'range': [80, 100], 'color': '#00001a'}]})).update_layout(template='plotly_dark', height=400))
        with col2:
            sims_pct = sims * 100
            counts, bins = np.histogram(sims_pct, bins=50); bins_center = (bins[:-1] + bins[1:]) / 2
            colors = ['#ff37af' if b < -5 else '#ffaa00' if b < 0 else '#ffd60a' if b < 5 else '#00ffaa' if b < 10 else '#007AFF' for b in bins_center]
            fig_h = go.Figure(go.Bar(x=bins_center, y=counts, marker_color=colors, opacity=0.8))
            fig_h.update_layout(title='5,000회 크로마 수익률 분포', template='plotly_dark', height=400); st.plotly_chart(fig_h, use_container_width=True)
        st.markdown('<div class="guide-box"><div class="guide-title">🧪 퀀트 가이드</div>히스토그램이 파랗게 타오를수록(오른쪽) 매수 시 대박 확률이 높습니다.</div>', unsafe_allow_html=True)

    with tab3: # 3P [신규] 실시간 뉴스룸 (URL 10개 직결)
        st.markdown(f"#### 📰 {s_name} 실시간 증권가 소식 (TOP 10)")
        for n in news:
            st.markdown(f"""
            <div class="news-item">
                📍 <a href='{n['link']}' class='news-link' target='_blank'>{n['title']}</a><br>
                <small style='color:#888;'>[{n['press']}] | 실시간 속보</small>
            </div>
            """, unsafe_allow_html=True)

    with tab4: # 4P 테마 (v120.0 유지)
        themes = {"🤖 AI/반도체": ["NVDA 💎💎💎", "SK하이닉스 💎💎"], "💰 금융/저PBR": ["우리금융지주 💎💎💎", "KB금융 💎💎"]}
        for t, s in themes.items():
            st.markdown(f"**{t}**: {', '.join(s)}")
else:
    st.error("데이터 로드 실패.")
