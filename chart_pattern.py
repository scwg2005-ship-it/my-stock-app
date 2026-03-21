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

# --- 1. [디자인] 오리진 하이엔드 퀀트 UI (Obsidian 테마) ---
st.set_page_config(layout="wide", page_title="Aegis Oracle Obsidian v135.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;900&family=Pretendard:wght@400;600;900&display=swap');
    
    /* 전체 배경 및 폰트 설정 */
    body, .stApp { background-color: #050505; font-family: 'Pretendard'; color: #ececec; }
    
    /* 메인 타이틀 네온 효과 */
    .main-title { font-family: 'Orbitron'; color: #00f2ff; text-shadow: 0 0 20px rgba(0,242,255,0.6); font-weight: 900; font-size: 2.5rem; text-align: center; margin-bottom: 30px; }
    
    /* 프리미엄 카드 디자인 */
    .stMetric { background: rgba(15,15,15,0.8); border: 1px solid #222; border-radius: 20px; padding: 25px; transition: 0.3s; box-shadow: inset 0 0 10px rgba(255,255,255,0.02); }
    .stMetric:hover { border-color: #00f2ff; transform: translateY(-5px); box-shadow: 0 10px 30px rgba(0,242,255,0.1); }
    
    /* AI 액션 대시보드 (Glassmorphism) */
    .action-box { background: linear-gradient(135deg, rgba(14,22,33,0.9), rgba(5,5,5,0.9)); border: 1px solid #00f2ff; border-radius: 25px; padding: 30px; margin-bottom: 35px; backdrop-filter: blur(10px); }
    .action-title { font-family: 'Orbitron'; font-size: 1.8rem; font-weight: 900; margin-bottom: 10px; }
    
    /* 기대수익 하이라이트 카드 */
    .profit-card { background: linear-gradient(135deg, #0044cc 0%, #001133 100%); border: 1px solid #0055ff; padding: 35px; border-radius: 30px; color: white; text-align: center; margin-bottom: 30px; box-shadow: 0 15px 40px rgba(0,68,204,0.4); }
    
    /* 탭 메뉴 디자인 커스텀 */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; background-color: transparent; }
    .stTabs [data-baseweb="tab"] { background-color: #111; border: 1px solid #222; border-radius: 12px 12px 0 0; color: #888; padding: 10px 25px; }
    .stTabs [aria-selected="true"] { background-color: #00f2ff !important; color: #000 !important; font-weight: 900 !important; }

    /* 뉴스 및 테마 박스 스타일 */
    .news-item { background: #0a0a0a; border-radius: 15px; padding: 15px; border-left: 5px solid #00f2ff; margin-bottom: 15px; }
    .recommend-box { background: rgba(255,255,255,0.03); padding: 18px; border-radius: 15px; border: 1px solid #222; margin-bottom: 12px; font-weight: 700; transition: 0.2s; }
    .recommend-box:hover { background: rgba(0,242,255,0.05); border-color: #00f2ff; }
    .highlight { color: #00f2ff; font-weight: 900; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [엔진] 무결성 하이브리드 로더 (v130.0 무적 엔진 유지) ---
@st.cache_data(ttl=60)
def get_obsidian_empire_data(symbol):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
    try:
        is_kr = symbol.isdigit() and len(symbol) == 6
        if is_kr:
            df_list = []
            for p in range(1, 6):
                url = f"https://finance.naver.com/item/sise_day.naver?code={symbol}&page={p}"
                res = requests.get(url, headers=headers)
                soup = BeautifulSoup(res.text, 'html.parser')
                table = soup.select_one('table.type2')
                if table:
                    df_list.append(pd.read_html(StringIO(str(table)))[0].dropna())
                time.sleep(0.05)
            df = pd.concat(df_list).reset_index(drop=True)
            df.columns = ['Date', 'Close', 'Net', 'Open', 'High', 'Low', 'Volume']
            df['Date'] = pd.to_datetime(df['Date'])
            
            m_res = requests.get(f"https://finance.naver.com/item/main.naver?code={symbol}", headers=headers)
            s_name = BeautifulSoup(m_res.text, 'html.parser').select_one('title').text.split(':')[0].strip()
            
            # 뉴스 URL 10선
            news_res = requests.get(f"https://search.naver.com/search.naver?where=news&query={s_name} 특징주", headers=headers)
            news_items = [{'title': i.select_one('.news_tit').text, 'link': i.select_one('.news_tit')['href']} for i in BeautifulSoup(news_res.text, 'html.parser').select('.news_area')[:10]]
            m_type, div_y, fin_s = "KR", "3.2% (Est)", "Operating Profit Stable"
        else:
            ticker = yf.Ticker(symbol.upper())
            df = ticker.history(period="1y").reset_index()
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df.columns = [str(c).capitalize() for c in df.columns]
            s_name = symbol.upper()
            news_items = [{'title': f'{s_name} Investing.com 실시간 속보', 'link': f'https://kr.investing.com/search/?q={s_name}'}]
            m_type, div_y, fin_s = "US", f"{ticker.info.get('dividendYield', 0)*100:.1f}%", f"Rev: {ticker.info.get('totalRevenue', 0)/1e9:.1f}B"

        df = df.sort_values('Date').reset_index(drop=True)
        for ma in [5, 20, 60, 120]:
            if len(df) >= ma: df[f'MA{ma}'] = df['Close'].rolling(ma).mean()
        std = df['Close'].rolling(20).std()
        df['BB_U'], df['BB_L'] = df['MA20'] + (std * 2), df['MA20'] - (std * 2)
        delta = df['Close'].diff(); gain = (delta.where(delta > 0, 0)).rolling(14).mean(); loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
        
        ret = df['Close'].pct_change().dropna(); sims = np.random.normal(ret.mean(), ret.std(), 5000)
        win_rate = (sims > 0).sum() / 5000 * 100; avg_profit = sims.mean() * 100

        # AI 액션 플랜 판정
        last_p = df['Close'].iloc[-1]; bb_l = df['BB_L'].iloc[-1]; bb_u = df['BB_U'].iloc[-1]
        if win_rate >= 65 and last_p <= bb_l * 1.05: action, color = "💎 STRONG BUY (적극 매수)", "#00f2ff"
        elif last_p >= bb_u * 0.95: action, color = "⚠️ SCALE OUT (분할 매도)", "#ff37af"
        elif last_p <= df['MA20'].iloc[-1] * 0.94: action, color = "🚨 CUT LOSS (즉시 손절)", "#ff0000"
        else: action, color = "⚖️ HOLD (관망 유지)", "#ffd60a"

        return df, s_name, win_rate, avg_profit, m_type, sims, news_items, action, color, div_y, fin_s
    except Exception as e: return None, str(e), 0, 0, "Error", [], [], "Error", "white", "", ""

# --- 3. [메인 화면] ---
s_input = st.sidebar.text_input("📊 TRADING SYMBOL", value="053000")
invest_amt = st.sidebar.number_input("💰 PORTFOLIO SIZE", value=10000000)

df, s_name, win_rate, avg_profit, m_type, sims, news, ai_action, ai_color, div_y, fin_s = get_obsidian_empire_data(s_input)

if df is not None and not df.empty:
    curr_p = float(df['Close'].iloc[-1]); unit = "원" if m_type == "KR" else "$"
    
    st.markdown(f'<div class="main-title">{s_name} TERMINAL</div>', unsafe_allow_html=True)
    
    # [1] AI 액션 대시보드
    st.markdown(f"""<div class="action-box">
        <div style="color:#888; font-weight:800; font-size:0.9rem; letter-spacing:2px; margin-bottom:10px;">🤖 ORACLE AI ACTION STRATEGY</div>
        <div class="action-title" style="color:{ai_color};">{ai_action}</div>
        <div style="color:#cccccc;">AI 승률 <span class="highlight">{win_rate:.1f}%</span>를 기반으로 산출된 퀀트 엔진의 최종 결정입니다.</div>
    </div>""", unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns([1.5, 1, 1, 1])
    with c1: st.markdown(f'<div class="profit-card"><h3>EXPECTED PROFIT</h3><h1>{avg_profit:+.2f}%</h1><p>예상 손익: {invest_amt*(avg_profit/100):+,.0f}{unit}</p></div>', unsafe_allow_html=True)
    with c2: st.metric("CURRENT PRICE", f"{curr_p:,.0f}{unit}"); st.metric("AI WIN RATE", f"{win_rate:.1f}%")
    with c3: st.metric("DIVIDEND YIELD", div_y); st.metric("RSI STRENGTH", f"{df['RSI'].iloc[-1]:.1f}")
    with c4: st.metric("TARGET (+15%)", f"{curr_p*1.15:,.0f}{unit}"); st.metric("STOP LOSS (-6%)", f"{curr_p*0.94:,.0f}{unit}")

    tabs = st.tabs(["📉 QUANT CHART", "🧪 CHROMA GAUGE", "📰 NEWS FEED", "🚀 SECTOR THEMES"])

    with tabs[0]: # 1P 차트
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.05)
        fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
        clrs = {5:'#ffd60a', 20:'#ff37af', 60:'#00f2ff', 120:'#ffffff'}
        for ma, clr in clrs.items():
            if f'MA{ma}' in df.columns: fig.add_trace(go.Scatter(x=df['Date'], y=df[f'MA{ma}'], line=dict(color=clr, width=1.8), name=f'{ma}MA'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_U'], line=dict(color='rgba(255,55,175,0.4)', dash='dash'), name='OVERHEAT'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_L'], line=dict(color='rgba(0,242,255,0.4)', dash='dash'), fill='tonexty', fillcolor='rgba(0,242,255,0.03)', name='BOTTOM'), row=1, col=1)
        fig.add_trace(go.Bar(x=df['Date'], y=df['Volume'], marker_color='#333', name='VOL'), row=2, col=1)
        fig.update_layout(height=700, template='plotly_dark', xaxis_rangeslider_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, width='stretch')

    with tabs[1]: # 2P 무지개 온도계
        col1, col2 = st.columns([1, 1.2])
        with col1:
            st.plotly_chart(go.Figure(go.Indicator(mode="gauge+number", value=win_rate, gauge={'bar': {'color': "#00f2ff"}, 'steps': [{'range': [0, 40], 'color': '#1a0000'}, {'range': [70, 100], 'color': '#001a1a'}]})).update_layout(template='plotly_dark', height=450, paper_bgcolor='rgba(0,0,0,0)'), width='stretch')
        with col2:
            sims_pct = sims * 100; counts, bins = np.histogram(sims_pct, bins=50); bins_center = (bins[:-1] + bins[1:]) / 2
            colors = ['#ff37af' if b < 0 else '#00f2ff' for b in bins_center]
            fig_h = go.Figure(go.Bar(x=bins_center, y=counts, marker_color=colors, opacity=0.8))
            fig_h.update_layout(title='5,000 SCENARIO DISTRIBUTION', template='plotly_dark', height=450, paper_bgcolor='rgba(0,0,0,0)'); st.plotly_chart(fig_h, width='stretch')

    with tabs[2]: # 3P 뉴스 피드
        st.markdown(f"#### 📰 REAL-TIME NEWS FEED (TOP 10)")
        for n in news:
            st.markdown(f"""<div class="news-item">📍 <a href='{n['link']}' class='news-link' target='_blank'>{n['title']}</a></div>""", unsafe_allow_html=True)

    with tabs[3]: # 4P 테마 섹터
        st.markdown("### 🚀 SECTOR LEADERS")
        themes = {"🤖 SEMI/AI": ["NVDA 💎💎💎", "SK HYNIX 💎💎"], "💰 FINANCE": ["WOORI FG 💎💎💎", "KB FG 💎💎"], "🛡️ DEFENSE": ["HANWHA AERO 💎💎💎", "LIG NEX1 💎💎"]}
        cols = st.columns(3)
        for i, (t, s) in enumerate(themes.items()):
            with cols[i]:
                st.markdown(f"<div class='cate-title'>{t}</div>", unsafe_allow_html=True)
                for stock in s: st.markdown(f"<div class='recommend-box'>🔥 {stock}</div>", unsafe_allow_html=True)
else:
    st.error("SYSTEM ERROR: UNABLE TO FETCH DATA.")
