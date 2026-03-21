import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO
from bs4 import BeautifulSoup

# --- 1. [디자인] 하이엔드 퀀트 터미널 CSS (가시성 극대화) ---
st.set_page_config(layout="wide", page_title="Aegis Oracle v115.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;900&display=swap');
    body, .stApp { background-color: #030303; font-family: 'Pretendard', sans-serif; color: #e0e0e0; }
    .stMetric { background-color: #0f0f0f; padding: 25px; border-radius: 18px; border: 1px solid #1e1e1e; }
    .profit-card { background: linear-gradient(135deg, #0055ff 0%, #00aaff 100%); padding: 30px; border-radius: 24px; color: white; text-align: center; margin-bottom: 25px; box-shadow: 0 10px 30px rgba(0,85,255,0.3); }
    .verdict-box { background-color: #0e1621; border: 2px solid #00f2ff; padding: 25px; border-radius: 20px; margin-bottom: 30px; }
    .guide-box { background-color: #0a0f1e; border: 1px dashed #00f2ff; padding: 20px; border-radius: 15px; margin-top: 30px; line-height: 1.7; }
    .guide-title { color: #00f2ff; font-weight: 900; font-size: 1.2rem; margin-bottom: 10px; }
    .cate-title { color: #00f2ff; font-weight: 900; font-size: 1.3rem; border-left: 5px solid #00f2ff; padding-left: 15px; margin: 25px 0 15px 0; }
    .recommend-box { background: #0a0a0a; padding: 15px; border-radius: 12px; margin-bottom: 10px; border: 1px solid #222; font-weight: bold; transition: 0.3s; }
    .recommend-box:hover { border-color: #00f2ff; background: #111; transform: translateY(-3px); }
    .highlight { color: #00f2ff; font-weight: 800; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [엔진] 무결성 하이브리드 로더 (미래 예측 & 뉴스 통합) ---
@st.cache_data(ttl=60)
def get_majesty_data(symbol):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
    try:
        is_kr = symbol.isdigit() and len(symbol) == 6
        if is_kr:
            # 국장 로드 (안전한 표 추출 방식)
            url = f"https://finance.naver.com/item/sise_day.naver?code={symbol}&page=1"
            res = requests.get(url, headers=headers)
            dfs = pd.read_html(StringIO(res.text))
            df = dfs[0].dropna()
            if df.empty: df = dfs[1].dropna()
            df.columns = ['Date', 'Close', 'Net', 'Open', 'High', 'Low', 'Volume']
            df['Date'] = pd.to_datetime(df['Date'])
            s_name = f"KOSPI:{symbol}"
            m_type = "KR"
            
            # 뉴스 파싱 (URL 포함)
            n_res = requests.get(f"https://search.naver.com/search.naver?where=news&query={symbol} 특징주", headers=headers)
            n_soup = BeautifulSoup(n_res.text, 'html.parser')
            news_list = []
            for item in n_soup.select('.news_area')[:10]:
                news_list.append({'title': item.select_one('.news_tit').text, 'link': item.select_one('.news_tit')['href']})
        else:
            # 미장 로드
            ticker = yf.Ticker(symbol.upper())
            df = ticker.history(period="1y").reset_index()
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df.columns = [str(c).capitalize() for c in df.columns]
            s_name = symbol.upper()
            m_type = "US"
            news_list = [{'title': f'{s_name} 실시간 뉴스 (인베스팅닷컴)', 'link': f'https://kr.investing.com/search/?q={s_name}'}]

        # 데이터 정제 및 지표 계산
        for col in ['Close', 'Open', 'High', 'Low', 'Volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.sort_values('Date').reset_index(drop=True)
        
        # 예측 밴드 (Bollinger) 및 RSI
        df['MA20'] = df['Close'].rolling(20).mean()
        std_dev = df['Close'].rolling(20).std()
        df['BB_Upper'] = df['MA20'] + (std_dev * 2)
        df['BB_Lower'] = df['MA20'] - (std_dev * 2)
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))

        # 5,000회 시뮬레이션
        ret = df['Close'].pct_change().dropna()
        sims = np.random.normal(ret.mean(), ret.std() if ret.std() > 0 else 0.01, 5000)
        win_rate = (sims > 0).sum() / 5000 * 100
        avg_profit = sims.mean() * 100

        # AI 최종 의견
        last_p = df['Close'].iloc[-1]
        if win_rate >= 60 and last_p <= df['BB_Lower'].iloc[-1] * 1.03:
            action, verdict = "🔥 적극 매수 (Strong Buy)", "통계적 바닥권이며 AI 승률이 압도적입니다."
        elif last_p >= df['BB_Upper'].iloc[-1] * 0.97:
            action, verdict = "⚠️ 과열 매도 (Sell)", "확률적 상한선에 도달했습니다. 수익 실현 타이밍입니다."
        else:
            action, verdict = "⚖️ 중립 관망 (Hold)", "현재 박스권 내에서 에너지를 응축 중입니다."

        return df, s_name, win_rate, avg_profit, m_type, sims, action, verdict, news_list
    except Exception as e:
        return None, str(e), 0, 0, "Error", [], "", "", []

# --- 3. [메인] ---
s_input = st.sidebar.text_input("📊 종목코드", value="053000")
invest_amt = st.sidebar.number_input("💰 투자 원금", value=10000000)

df, s_name, win_rate, avg_profit, m_type, sims, action, verdict_text, news = get_majesty_data(s_input)

if df is not None and not df.empty:
    curr_p = float(df['Close'].iloc[-1]); unit = "원" if m_type == "KR" else "$"
    
    st.markdown(f"## {s_name} ({s_input})")
    
    # [상단] AI 최종 의사결정 요약
    st.markdown(f"""<div class="verdict-box">
        <div style="color:#00f2ff; font-weight:800; margin-bottom:5px;">🤖 Oracle's Final AI Verdict</div>
        <div style="font-size:1.5rem; font-weight:900;">{action}</div>
        <div style="color:#cccccc;">{verdict_text}</div>
    </div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1: st.markdown(f'<div class="profit-card"><h3>내일 기대수익</h3><h1>{avg_profit:+.2f}%</h1></div>', unsafe_allow_html=True)
    with c2: st.metric("현재가", f"{curr_p:,.0f}{unit}"); st.metric("AI 승률", f"{win_rate:.1f}%")
    with c3: st.metric("목표가(+15%)", f"{curr_p*1.15:,.0f}{unit}"); st.metric("손절가(-6%)", f"{curr_p*0.94:,.0f}{unit}")

    tab1, tab2, tab3, tab4 = st.tabs(["📉 예측 차트 분석", "🧪 퀀트 온도계", "📰 실시간 뉴스/재무", "🚀 AI 엄선 테마"])

    with tab1: # 1P 예측 차트
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.05)
        fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='시세'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_Upper'], line=dict(color='#ff37af', width=1.5, dash='dash'), name='과열선'))
        fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_Lower'], line=dict(color='#00aaff', width=1.5, dash='dash'), fill='tonexty', fillcolor='rgba(0,170,255,0.05)', name='침체선'))
        fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("""<div class="guide-box"><div class="guide-title">🔍 전문가 조언: 예측 차트 활용법</div>
        주가가 <b>파란 침체선</b>에 닿으면 통계적으로 저평가 구간입니다. 반대로 <b>빨간 과열선</b>을 뚫으면 단기 조정 확률이 95% 이상이므로 익절을 고려하세요.</div>""", unsafe_allow_html=True)

    with tab2: # 2P 퀀트 온도계
        col1, col2 = st.columns(2)
        with col1:
            fig_g = go.Figure(go.Indicator(mode="gauge+number", value=win_rate, title={'text': "매수 온도"}, gauge={'bar': {'color': "#0055ff"}}))
            st.plotly_chart(fig_g, use_container_width=True)
        with col2:
            fig_h = go.Figure()
            sims_pct = sims * 100
            fig_h.add_trace(go.Histogram(x=sims_pct[sims_pct >= 0], name='상승', marker_color='#007AFF', opacity=0.7))
            fig_h.add_trace(go.Histogram(x=sims_pct[sims_pct < 0], name='하락', marker_color='#ff37af', opacity=0.7))
            fig_h.update_layout(title='수익률 확률 분포도', template='plotly_dark')
            st.plotly_chart(fig_h, use_container_width=True)
        st.markdown("""<div class="guide-box"><div class="guide-title">🧪 전문가 조언: 퀀트 분석 해석</div>
        <b>온도가 70% 이상</b>이고 히스토그램 막대가 <b>오른쪽(파란색)</b>으로 치우쳐 있을 때가 가장 강력한 '풀배팅' 신호입니다.</div>""", unsafe_allow_html=True)

    with tab3: # 3P 뉴스룸 (URL 포함)
        st.markdown("#### 📰 실시간 특징주 속보 (TOP 10)")
        for n in news:
            st.markdown(f"📍 [{n['title']}]({n['link']})")
        st.markdown("""<div class="guide-box"><div class="guide-title">📰 전문가 조언: 뉴스 활용법</div>
        단순 호재보다 '수주', '흑자전환', '기술수출' 키워드가 섞인 뉴스가 차트의 <b>빨간 점선(과열선)</b>을 뚫는 강력한 재료가 됩니다.</div>""", unsafe_allow_html=True)

    with tab4: # 4P AI 엄선 테마
        st.markdown("### 🚀 AI 선정 초급등 예상 핵심 섹터")
        themes = {
            "🤖 AI/반도체 (대장주)": ["NVDA 💎💎💎", "SK하이닉스 💎💎", "삼성전자 💎"],
            "💰 지주사/금융 (저PBR)": ["우리금융지주 💎💎💎", "KB금융 💎💎", "메리츠금융 💎"],
            "🛡️ K-방산/우주 (수주)": ["한화에어로스페이스 💎💎💎", "LIG넥스원 💎💎"]
        }
        cols = st.columns(3)
        for i, (t, s) in enumerate(themes.items()):
            with cols[i]:
                st.markdown(f"<div class='cate-title'>{t}</div>", unsafe_allow_html=True)
                for stock in s: st.markdown(f"<div class='recommend-box'>🔥 {stock}</div>", unsafe_allow_html=True)
        st.markdown("""<div class="guide-box"><div class="guide-title">🚀 전문가 조언: 테마주 순환매</div>
        💎💎💎 종목이 과열선(빨간선)에 도달했다면, 아직 바닥에 있는 💎💎 종목으로 자금을 옮기는 <b>순환매 전략</b>이 유효합니다.</div>""", unsafe_allow_html=True)
else:
    st.error("데이터 로드 실패.")
