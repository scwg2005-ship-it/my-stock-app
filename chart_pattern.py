import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO
from bs4 import BeautifulSoup

# --- 1. [디자인] 전문가용 프리미엄 터미널 UI ---
st.set_page_config(layout="wide", page_title="Aegis Oracle Imperial v112.0")
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
    </style>
    """, unsafe_allow_html=True)

# --- 2. [엔진] 무결성 데이터 로더 (국장/미장 완전 분리) ---
@st.cache_data(ttl=60)
def get_zero_error_data(symbol):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
    try:
        is_kr = symbol.isdigit() and len(symbol) == 6
        if is_kr:
            # [국장 전용] 네이버 금융 파싱 (v103.0 성공 로직 기반)
            url = f"https://finance.naver.com/item/sise_day.naver?code={symbol}&page=1"
            res = requests.get(url, headers=headers)
            dfs = pd.read_html(StringIO(res.text))
            df = dfs[0].dropna()
            if df.empty: df = dfs[1].dropna()
            df.columns = ['Date', 'Close', 'Net', 'Open', 'High', 'Low', 'Volume']
            df['Date'] = pd.to_datetime(df['Date'])
            
            # 종목명 가져오기
            n_res = requests.get(f"https://finance.naver.com/item/main.naver?code={symbol}", headers=headers)
            s_name = BeautifulSoup(n_res.text, 'html.parser').select_one('.wrap_company h2 a').text.strip()
            m_type = "KR"
        else:
            # [미장 전용] yfinance (최소 기능 호출로 에러 방지)
            ticker = yf.Ticker(symbol.upper())
            df = ticker.history(period="1y").reset_index()
            # Multi-index 방지 평탄화
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.columns = [str(c).capitalize() for c in df.columns]
            s_name = symbol.upper()
            m_type = "US"

        # 공통 정제
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

        # AI 최종 의견 도출
        last_p = df['Close'].iloc[-1]
        bb_low = df['BB_Lower'].iloc[-1]
        bb_high = df['BB_Upper'].iloc[-1]
        
        if win_rate >= 60 and last_p <= bb_low * 1.05:
            action, verdict = "🔥 적극 매수", "승률이 높고 침체선 근처입니다. 강력한 반등이 예상됩니다."
        elif last_p >= bb_high * 0.95:
            action, verdict = "⚠️ 과열/관망", "상한선 도달로 조정 가능성이 큽니다. 신규 진입을 자제하세요."
        else:
            action, verdict = "⚖️ 보유/중립", "현재 뚜렷한 방향성 없이 박스권 내에서 움직이고 있습니다."

        return df, s_name, win_rate, avg_profit, m_type, sims, action, verdict
    except Exception as e:
        return None, str(e), 0, 0, "Error", [], "", ""

# --- 3. [사이드바] ---
with st.sidebar:
    st.markdown('<h1 style="color:#00f2ff;">IMPERIAL Master</h1>', unsafe_allow_html=True)
    s_input = st.text_input("📊 종목코드 (053000 / NVDA)", value="053000")
    invest_amt = st.number_input("💰 투자 원금", value=10000000)

# --- 4. [메인 프로세스] ---
df, s_name, win_rate, avg_profit, m_type, sims, action, verdict_text = get_zero_error_data(s_input)

if df is not None and not df.empty:
    curr_p = float(df['Close'].iloc[-1]); unit = "원" if m_type == "KR" else "$"
    
    st.markdown(f"## {s_name} ({s_input})")
    
    # [AI 최종 의사결정 박스]
    st.markdown(f"""
    <div class="verdict-box">
        <div style="color:#00f2ff; font-weight:800; margin-bottom:5px;">🤖 AI 최종 매매 의견</div>
        <div style="font-size:1.4rem; font-weight:900;">{action}</div>
        <div style="color:#cccccc;">{verdict_text}</div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1: st.markdown(f'<div class="profit-card"><h3>내일 기대수익</h3><h1>{avg_profit:+.2f}%</h1></div>', unsafe_allow_html=True)
    with c2: st.metric("현재가", f"{curr_p:,.0f}{unit}"); st.metric("AI 승률", f"{win_rate:.1f}%")
    with c3: st.metric("목표가", f"{curr_p*1.15:,.0f}{unit}"); st.metric("손절가", f"{curr_p*0.94:,.0f}{unit}")

    tab1, tab2, tab3 = st.tabs(["📉 예측 차트", "🧪 퀀트 온도계", "🚀 추천 테마"])

    with tab1: # 차트 & 가이드
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.05)
        fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='시세'), row=1, col=1)
        if 'BB_Upper' in df.columns:
            fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_Upper'], line=dict(color='#ff37af', width=1.5, dash='dash'), name='과열선'))
            fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_Lower'], line=dict(color='#00aaff', width=1.5, dash='dash'), name='침체선'))
        fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('<div class="guide-box"><div class="guide-title">🔍 전문가 가이드</div>빨간 점선(상한선) 근접 시 매도, 파란 점선(하한선) 근접 시 매수 타점으로 봅니다.</div>', unsafe_allow_html=True)

    with tab2: # 온도계 & 히스토그램
        col1, col2 = st.columns(2)
        with col1:
            fig_g = go.Figure(go.Indicator(mode="gauge+number", value=win_rate, title={'text': "매수 온도"}, gauge={'bar': {'color': "#0055ff"}}))
            st.plotly_chart(fig_g, use_container_width=True)
        with col2:
            fig_h = go.Figure()
            sims_pct = sims * 100
            fig_h.add_trace(go.Histogram(x=sims_pct[sims_pct >= 0], name='상승', marker_color='#007AFF', opacity=0.7))
            fig_h.add_trace(go.Histogram(x=sims_pct[sims_pct < 0], name='하락', marker_color='#ff37af', opacity=0.7))
            fig_h.update_layout(title='수익률 분포도', template='plotly_dark')
            st.plotly_chart(fig_h, use_container_width=True)
        st.markdown('<div class="guide-box"><div class="guide-title">🧪 전문가 가이드</div>히스토그램의 파란색 막대가 우측으로 길게 쏠려 있을 때 상승 에너지가 큽니다.</div>', unsafe_allow_html=True)

    with tab3: # 추천 테마
        st.markdown("### 🚀 AI 엄선 섹터")
        themes = {"🤖 AI/반도체": ["NVDA 💎💎💎", "SK하이닉스 💎💎"], "💰 금융/저PBR": ["우리금융지주 💎💎💎", "KB금융 💎💎"]}
        for t, s in themes.items(): st.markdown(f"**{t}**: {', '.join(s)}")
        st.markdown('<div class="guide-box"><div class="guide-title">🚀 전문가 가이드</div>💎 등급이 높은 종목은 현재 시장의 주도주입니다.</div>', unsafe_allow_html=True)
else:
    st.error(f"❌ 데이터 로드 실패: {s_name}. 종목코드(053000 등)를 정확히 입력하세요.")
