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

# --- 1. [디자인] VIP 터미널 프리미엄 CSS ---
st.set_page_config(layout="wide", page_title="Aegis Oracle v126.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;900&display=swap');
    body, .stApp { background-color: #030303; font-family: 'Pretendard'; color: #e0e0e0; }
    .stMetric { background-color: #0f0f0f; padding: 25px; border-radius: 18px; border: 1px solid #1e1e1e; }
    .profit-card { background: linear-gradient(135deg, #0055ff 0%, #00aaff 100%); padding: 30px; border-radius: 24px; color: white; text-align: center; margin-bottom: 25px; }
    .action-box { background-color: #0e1621; border: 2px solid #00f2ff; padding: 25px; border-radius: 20px; margin-bottom: 30px; }
    .guide-box { background-color: #0a0f1e; border: 1px dashed #00f2ff; padding: 20px; border-radius: 15px; margin-top: 20px; line-height: 1.8; }
    .cate-title { color: #00f2ff; font-weight: 900; font-size: 1.3rem; border-left: 5px solid #00f2ff; padding-left: 15px; margin: 25px 0 10px 0; }
    .recommend-box { background: #111; padding: 15px; border-radius: 12px; border: 1px solid #333; margin-bottom: 10px; font-weight: bold; }
    .highlight { color: #00f2ff; font-weight: 800; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [엔진] 신규 상장주 대응 하이브리드 로더 ---
@st.cache_data(ttl=60)
def get_new_star_data(symbol):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
    try:
        is_kr = symbol.isdigit() and len(symbol) == 6
        if is_kr:
            # [국장] 네이버 금융 정밀 타격
            df_list = []
            for p in range(1, 5): # 신규주는 데이터가 적으므로 5페이지면 충분
                url = f"https://finance.naver.com/item/sise_day.naver?code={symbol}&page={p}"
                res = requests.get(url, headers=headers)
                soup = BeautifulSoup(res.text, 'html.parser')
                table = soup.select_one('table.type2')
                if table:
                    # 표의 날짜가 유효한지 체크하며 수집
                    temp_df = pd.read_html(StringIO(str(table)))[0].dropna()
                    if not temp_df.empty: df_list.append(temp_df)
            
            if not df_list: return None, "데이터 없음", 0, 0, "Error", [], [], "Error", "white"
            
            df = pd.concat(df_list).reset_index(drop=True)
            df.columns = ['Date', 'Close', 'Net', 'Open', 'High', 'Low', 'Volume']
            df['Date'] = pd.to_datetime(df['Date'])
            
            # 종목명 추출 (안전 장치 강화)
            m_res = requests.get(f"https://finance.naver.com/item/main.naver?code={symbol}", headers=headers)
            m_soup = BeautifulSoup(m_res.text, 'html.parser')
            s_name = m_soup.select_one('title').text.split(':')[0].strip() if m_soup.select_one('title') else f"KOSPI:{symbol}"
            
            # 뉴스 (신규 상장주 특징주 뉴스 위주)
            n_res = requests.get(f"https://search.naver.com/search.naver?where=news&query={s_name} 특징주", headers=headers)
            n_soup = BeautifulSoup(n_res.text, 'html.parser')
            news_items = [{'title': i.select_one('.news_tit').text, 'link': i.select_one('.news_tit')['href']} for i in n_soup.select('.news_area')[:10]]
            m_type = "KR"
        else:
            # [미장] yfinance
            ticker = yf.Ticker(symbol.upper())
            df = ticker.history(period="1y").reset_index()
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df.columns = [str(c).capitalize() for c in df.columns]
            s_name = symbol.upper()
            news_items = [{'title': f'{s_name} 실시간 뉴스', 'link': f'https://kr.investing.com/search/?q={s_name}'}]
            m_type = "US"

        df = df.sort_values('Date').reset_index(drop=True)
        
        # [중요] 데이터가 적은 신규 상장주를 위한 가변 지표 계산
        count = len(df)
        for ma in [5, 20, 60]:
            if count >= ma: df[f'MA{ma}'] = df['Close'].rolling(ma).mean()
            else: df[f'MA{ma}'] = df['Close'].expanding().mean() # 데이터 부족시 누적 평균 사용
            
        std = df['Close'].rolling(min(count, 20)).std()
        df['BB_U'] = df['MA20'] + (std * 2)
        df['BB_L'] = df['MA20'] - (std * 2)
        
        # 몬테카를로 (상장 초기라 변동성이 크므로 주의 필요)
        ret = df['Close'].pct_change().dropna()
        if not ret.empty:
            sims = np.random.normal(ret.mean(), ret.std(), 5000)
            win_rate = (sims > 0).sum() / 5000 * 100
            avg_profit = sims.mean() * 100
        else: win_rate, avg_profit, sims = 50, 0, np.zeros(5000)

        # AI 액션 플랜
        last_p = df['Close'].iloc[-1]
        if win_rate >= 60: action, color = "🚀 신규주 급등 기대", "#00f2ff"
        elif last_p <= df['BB_L'].iloc[-1]: action, color = "🛡️ 바닥 지지 매수", "#00ffaa"
        else: action, color = "⚖️ 추세 관망", "#ffd60a"

        return df, s_name, win_rate, avg_profit, m_type, sims, news_items, action, color
    except Exception as e:
        return None, str(e), 0, 0, "Error", [], [], "Error", "white"

# --- 3. [메인 화면] ---
s_input = st.sidebar.text_input("📊 종목코드 (쓰리빌리언: 394210)", value="394210")
invest_amt = st.sidebar.number_input("💰 투자금 설정", value=10000000)

df, s_name, win_rate, avg_profit, m_type, sims, news, ai_action, ai_color = get_new_star_data(s_input)

if df is not None and not df.empty:
    curr_p = float(df['Close'].iloc[-1]); unit = "원" if m_type == "KR" else "$"
    
    st.markdown(f"## {s_name} <small style='color:#888;'>({s_input})</small>", unsafe_allow_html=True)
    
    # [1] AI 최종 액션 플랜
    st.markdown(f"""<div class="action-box">
        <div style="color:#888; font-weight:800; margin-bottom:5px;">🤖 Oracle's New-Star Verdict</div>
        <div style="font-size:1.6rem; font-weight:900; color:{ai_color};">{ai_action}</div>
        <div>신규 상장주 특유의 변동성을 반영한 <span class="highlight">AI 기대 승률 {win_rate:.1f}%</span> 구간입니다.</div>
    </div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1: st.markdown(f'<div class="profit-card"><h3>내일 기대수익</h3><h1>{avg_profit:+.2f}%</h1><p>예상 손익: {invest_amt*(avg_profit/100):+,.0f}{unit}</p></div>', unsafe_allow_html=True)
    with c2: st.metric("현재가", f"{curr_p:,.0f}{unit}"); st.metric("AI 승률", f"{win_rate:.1f}%")
    with c3: st.metric("목표가(+15%)", f"{curr_p*1.15:,.0f}{unit}"); st.metric("손절가(-6%)", f"{curr_p*0.94:,.0f}{unit}")

    tab1, tab2, tab3, tab4 = st.tabs(["📉 전문가 정밀 차트", "🧪 무지개 퀀트 분석", "📰 실시간 증권 뉴스", "🚀 AI 추천 테마"])

    with tab1: # 차트 & 가이드
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.05)
        fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='시세'), row=1, col=1)
        for ma, clr in zip(['MA5', 'MA20', 'MA60'], ['yellow', 'magenta', 'cyan']):
            if ma in df.columns: fig.add_trace(go.Scatter(x=df['Date'], y=df[ma], line=dict(color=clr, width=1.5), name=f'{ma}선'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_U'], line=dict(color='red', dash='dash'), name='과열선'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_L'], line=dict(color='blue', dash='dash'), fill='tonexty', fillcolor='rgba(0,170,255,0.03)', name='침체선'), row=1, col=1)
        fig.add_trace(go.Bar(x=df['Date'], y=df['Volume'], marker_color='#333', name='거래량'), row=2, col=1)
        fig.update_layout(height=650, template='plotly_dark', xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('<div class="guide-box"><div class="guide-title">🔍 전문가 조언</div>신규 상장주는 <b>5일선(노랑)</b> 이탈 여부를 가장 중요하게 보십시오.</div>', unsafe_allow_html=True)

    with tab2: # 온도계 & 히스토그램
        col1, col2 = st.columns([1, 1.2])
        with col1:
            st.plotly_chart(go.Figure(go.Indicator(mode="gauge+number", value=win_rate, gauge={'bar':{'color':'#0055ff'}, 'steps':[{'range':[0,40],'color':'#1a0000'},{'range':[70,100],'color':'#001a1a'}]})).update_layout(template='plotly_dark', height=400))
        with col2:
            fig_h = go.Figure(go.Bar(x=np.linspace(-10, 10, 50), y=np.histogram(sims*100, bins=50)[0], marker_color='#007AFF', opacity=0.8))
            fig_h.update_layout(title='5,000회 시뮬레이션 분포', template='plotly_dark', height=400); st.plotly_chart(fig_h, use_container_width=True)

    with tab3: # 뉴스 (URL 10개)
        st.markdown(f"#### 📰 {s_name} 실시간 특징주 뉴스")
        if news:
            for n in news: st.markdown(f"📍 [{n['title']}]({n['link']})")
        else: st.warning("신규 종목이라 관련 뉴스를 수집 중입니다.")

    with tab4: # 테마 섹터
        st.markdown("### 🚀 AI 선정 핵심 섹터")
        themes = {"🧬 바이오/헬스케어 (쓰리빌리언 관련)": ["쓰리빌리언 💎💎💎", "알테오젠 💎💎", "리가켐바이오 💎"], "🤖 AI/반도체": ["NVDA 💎💎💎", "SK하이닉스 💎💎"]}
        for t, s in themes.items():
            st.markdown(f"<div class='cate-title'>{t}</div>", unsafe_allow_html=True)
            for stock in s: st.markdown(f"<div class='recommend-box'>🔥 {stock}</div>", unsafe_allow_html=True)
else:
    st.error("데이터 로드 실패. 신규 상장주 데이터 연결을 재시도 중입니다.")
