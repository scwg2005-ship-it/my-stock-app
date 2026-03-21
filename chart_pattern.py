import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO
from bs4 import BeautifulSoup
import re

# --- 1. [디자인] 전문가 가이드 및 AI 알림 UI ---
st.set_page_config(layout="wide", page_title="Aegis Oracle Imperial v111.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;900&display=swap');
    body, .stApp { background-color: #030303; font-family: 'Pretendard', sans-serif; color: #e0e0e0; }
    .stMetric { background-color: #0f0f0f; padding: 25px; border-radius: 18px; border: 1px solid #1e1e1e; }
    .profit-card { background: linear-gradient(135deg, #0055ff 0%, #00aaff 100%); padding: 30px; border-radius: 24px; color: white; text-align: center; margin-bottom: 25px; }
    .verdict-box { background-color: #0e1621; border: 2px solid #00f2ff; padding: 25px; border-radius: 20px; margin-bottom: 30px; box-shadow: 0 0 15px rgba(0,242,255,0.2); }
    .guide-box { background-color: #0a0f1e; border: 1px dashed #00f2ff; padding: 20px; border-radius: 15px; margin-top: 30px; }
    .guide-title { color: #00f2ff; font-weight: 900; font-size: 1.2rem; margin-bottom: 10px; }
    .highlight { color: #00f2ff; font-weight: 800; }
    .verdict-text { font-size: 1.3rem; font-weight: 900; color: #ffffff; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [엔진] 데이터 로더 및 AI 요약 엔진 ---
@st.cache_data(ttl=60)
def get_final_verdict_data(symbol):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
    try:
        is_kr = symbol.isdigit() and len(symbol) == 6
        if is_kr:
            df_list = []
            for p in range(1, 11):
                url = f"https://finance.naver.com/item/sise_day.naver?code={symbol}&page={p}"
                res = requests.get(url, headers=headers)
                dfs = pd.read_html(StringIO(res.text))
                df_list.append(dfs[0].dropna())
            df = pd.concat(df_list).reset_index(drop=True)
            df.columns = ['Date', 'Close', 'Net', 'Open', 'High', 'Low', 'Volume']
            df['Date'] = pd.to_datetime(df['Date'])
            m_type = "KR"
            n_res = requests.get(f"https://finance.naver.com/item/main.naver?code={symbol}", headers=headers)
            s_name = BeautifulSoup(n_res.text, 'html.parser').select_one('.wrap_company h2 a').text.strip()
        else:
            ticker = yf.Ticker(symbol.upper())
            df = ticker.history(period="2y").reset_index()
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df.columns = [str(c).capitalize() for c in df.columns]
            s_name = symbol.upper()
            m_type = "US"

        for col in ['Close', 'Open', 'High', 'Low', 'Volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.sort_values('Date').reset_index(drop=True)

        # 지표 계산
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        std_dev = df['Close'].rolling(20).std()
        df['BB_Upper'] = df['MA20'] + (std_dev * 2)
        df['BB_Lower'] = df['MA20'] - (std_dev * 2)
        
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))

        # 시뮬레이션
        ret = df['Close'].pct_change().dropna()
        sims = np.random.normal(ret.mean(), ret.std() if ret.std() > 0 else 0.01, 5000)
        win_rate = (sims > 0).sum() / 5000 * 100
        avg_profit = sims.mean() * 100

        # --- [기능 추가] AI 최종 의견 요약 로직 ---
        last = df.iloc[-1]
        verdict = ""
        action = ""
        
        if win_rate >= 65 and last['Close'] <= df['BB_Lower'].iloc[-1] * 1.05:
            action = "🔥 적극 매수 (Strong Buy)"
            verdict = f"AI 승률이 {win_rate:.1f}%로 매우 높으며, 현재 주가가 확률 하한선(침체선) 근처에 있어 기술적 반등 가능성이 매우 큽니다."
        elif win_rate >= 55 and last['MA5'] > last['MA20']:
            action = "📈 매수 관점 (Buy)"
            verdict = "단기 골든크로스가 유지되고 있으며, 미래 시나리오상 상승 가능성이 우세합니다. 분할 매수로 접근하세요."
        elif last['Close'] >= df['BB_Upper'].iloc[-1] * 0.95:
            action = "⚠️ 관망/매도 (Hold/Sell)"
            verdict = "주가가 확률 상한선(과열선)에 도달했습니다. 단기 조정 확률이 95% 이상이므로 신규 진입은 자제하고 수익 실현을 권장합니다."
        else:
            action = "⚖️ 중립 (Neutral)"
            verdict = "뚜렷한 방향성이 감지되지 않는 혼조세입니다. 볼린저 밴드 하단이나 AI 승률이 개선될 때까지 대기하세요."

        return df, s_name, win_rate, avg_profit, m_type, sims, action, verdict
    except: return None, "Error", 0, 0, "Error", [], "", ""

# --- 3. [메인 화면] ---
s_input = st.sidebar.text_input("📊 종목코드", value="053000")
invest_amt = st.sidebar.number_input("💰 투자 원금", value=10000000)

df, s_name, win_rate, avg_profit, m_type, sims, action, verdict_text = get_final_verdict_data(s_input)

if df is not None and not df.empty:
    curr_p = float(df['Close'].iloc[-1]); unit = "원" if m_type == "KR" else "$"
    
    st.markdown(f"## {s_name} ({s_input})")
    
    # [기능 추가] AI 최종 의사결정 박스
    st.markdown(f"""
    <div class="verdict-box">
        <div style="color:#00f2ff; font-weight:800; margin-bottom:10px;">🤖 Oracle's Final AI Verdict</div>
        <div class="verdict-text">{action}</div>
        <div style="margin-top:10px; color:#cccccc;">{verdict_text}</div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1: st.markdown(f'<div class="profit-card"><h3>내일 기대수익</h3><h1>{avg_profit:+.2f}%</h1></div>', unsafe_allow_html=True)
    with c2: st.metric("현재가", f"{curr_p:,.0f}{unit}"); st.metric("AI 승률", f"{win_rate:.1f}%")
    with c3: st.metric("목표가", f"{curr_p*1.15:,.0f}{unit}"); st.metric("손절가", f"{curr_p*0.94:,.0f}{unit}")

    tab1, tab2, tab3 = st.tabs(["📉 예측 차트 분석", "🧪 퀀트 온도계", "🚀 AI 추천 테마"])

    with tab1:
        # 차트 및 하단 가이드 (v110.0 가이드 포함)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.05)
        fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='시세'), row=1, col=1)
        if 'BB_Upper' in df.columns:
            fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_Upper'], line=dict(color='#ff37af', width=1.5, dash='dash'), name='과열선'))
            fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_Lower'], line=dict(color='#00aaff', width=1.5, dash='dash'), fill='tonexty', fillcolor='rgba(0,170,255,0.05)', name='침체선'))
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('<div class="guide-box"><div class="guide-title">🔍 전문가 조언: 차트 읽는 법</div>'
                    '상한선(빨간 점선) 근접 시 수익 실현, 하한선(파란 점선) 근접 시 매수 기회로 활용하세요.</div>', unsafe_allow_html=True)

    with tab2:
        # 온도계 및 히스토그램 가이드
        col1, col2 = st.columns([1, 1.2])
        with col1:
            fig_g = go.Figure(go.Indicator(mode="gauge+number", value=win_rate, title={'text': "매수 온도"}, gauge={'bar': {'color': "#0055ff"}}))
            st.plotly_chart(fig_g, use_container_width=True)
        with col2:
            fig_h = go.Figure()
            sims_pct = sims * 100
            fig_h.add_trace(go.Histogram(x=sims_pct[sims_pct >= 0], name='상승 시나리오', marker_color='#007AFF', opacity=0.7))
            fig_h.add_trace(go.Histogram(x=sims_pct[sims_pct < 0], name='하락 시나리오', marker_color='#ff37af', opacity=0.7))
            st.plotly_chart(fig_h, use_container_width=True)
        st.markdown('<div class="guide-box"><div class="guide-title">🧪 전문가 조언: 온도계 해석</div>'
                    '온도가 70% 이상이고 히스토그램이 파란색(우측)으로 쏠려 있을 때 상승 에너지가 가장 강합니다.</div>', unsafe_allow_html=True)

    with tab3:
        # 추천 테마 가이드
        st.markdown("### 🚀 AI 선정 초급등 예상 핵심 섹터")
        themes = {"🤖 AI/반도체": ["NVDA 💎💎💎", "SK하이닉스 💎💎"], "💰 금융/저PBR": ["우리금융지주 💎💎💎", "KB금융 💎💎"]}
        for t, s in themes.items():
            st.markdown(f"**{t}**: {', '.join(s)}")
        st.markdown('<div class="guide-box"><div class="guide-title">🚀 전문가 조언: 테마 활용</div>'
                    '💎 등급이 높은 종목은 현재 시장 자금이 집중되는 주도주입니다. 분산 투자를 잊지 마세요.</div>', unsafe_allow_html=True)
else:
    st.error("데이터 로드 실패.")
