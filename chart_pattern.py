import streamlit as st
import pandas as pd
import FinanceDataReader as fdr  # 한국 주식 특화 엔진
import yfinance as yf
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO
from bs4 import BeautifulSoup

# --- 1. [디자인] 증권사 VIP 전용 터미널 UI ---
st.set_page_config(layout="wide", page_title="Aegis Oracle v83.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;800&display=swap');
    body, .stApp { background-color: #050505; font-family: 'Pretendard', sans-serif; color: #ffffff; }
    .stMetric { background-color: #111; padding: 20px; border-radius: 16px; border: 1px solid #222; }
    .profit-card { background: linear-gradient(135deg, #007AFF 0%, #5856D6 100%); padding: 25px; border-radius: 20px; color: white; text-align: center; margin-bottom: 20px; }
    .info-card { background-color: #161616; padding: 18px; border-radius: 14px; margin-bottom: 12px; border: 1px solid #222; }
    .ma-legend { font-size: 0.9rem; font-weight: bold; margin-bottom: 10px; display: flex; gap: 20px; justify-content: flex-end; }
    .cate-title { color: #00f2ff; font-weight: 800; font-size: 1.1rem; border-bottom: 2px solid #333; padding-bottom: 5px; margin-top: 15px; }
    .recommend-box { background: #111; padding: 12px; border-radius: 10px; margin-bottom: 8px; border: 1px solid #333; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [강력 수정] 듀얼 데이터 엔진 (한국: FDR / 미국: Yahoo) ---
@st.cache_data(ttl=3600)
def find_symbol_intelligent(query):
    # 한국 거래소 마스터 리스트에서 찾기
    try:
        url_krx = 'http://kind.krx.co.kr/corpoctl/corpList.do?method=download'
        res = requests.get(url_krx, timeout=5)
        df_krx = pd.read_html(StringIO(res.text), header=0)[0]
        match = df_krx[df_krx['회사명'].str.contains(query, na=False, case=False)]
        if not match.empty:
            return f"{match.iloc[0]['종목코드']:06d}", match.iloc[0]['회사명'], "KR"
    except: pass
    return query.upper(), query, "US"

@st.cache_data(ttl=60)
def get_oracle_data(symbol, market_type):
    try:
        if market_type == "KR":
            # [FDR 가동] 한국 주식은 야후보다 10배 안정적입니다.
            df = fdr.DataReader(symbol)
            # 컬럼명 통일 (Open, High, Low, Close, Volume)
            df.columns = [str(c).capitalize() for c in df.columns]
        else:
            # 미국 주식은 야후 사용
            df = yf.download(symbol, period="1y", progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.columns = [str(c).capitalize() for c in df.columns]

        if df.empty: return None

        # 데이터 수치화 및 보조지표 계산
        df = df.apply(pd.to_numeric, errors='coerce').dropna()
        for ma in [5, 20, 60, 120]:
            df[f'MA{ma}'] = df['Close'].rolling(ma).mean()
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
        df['High_Max'] = df['High'].rolling(20).max()
        df['Low_Min'] = df['Low'].rolling(20).min()
        return df
    except: return None

# --- 3. [사이드바] 고정 제어판 ---
with st.sidebar:
    st.markdown('<p style="font-size:1.8rem; font-weight:800; color:#00f2ff;">Oracle Control</p>', unsafe_allow_html=True)
    u_input = st.text_input("종목명 입력 (우리금융지주, 삼성전자, NVDA)", value="우리금융지주")
    symbol, target_name, m_type = find_symbol_intelligent(u_input)
    st.success(f"매칭: **{target_name} ({symbol})**")
    
    invest_val = st.number_input("투자 원금 설정", value=10000000)
    chart_style = st.radio("그래프 형태", ["전문가 캔들", "심플 라인"], horizontal=True)
    show_ma = st.multiselect("이평선 표시", [5, 20, 60, 120], default=[5, 20, 60, 120])
    show_wave = st.checkbox("파동/빗각 레이어", value=True)
    show_rsi = st.checkbox("RSI/거래량 표시", value=True)

# --- 4. [메인] 분석 실행 ---
df = get_oracle_data(symbol, m_type)

if df is not None:
    curr_p = float(df['Close'].iloc[-1])
    # 5,000회 시뮬레이션
    returns = df['Close'].pct_change().dropna()
    sim_results = np.random.normal(returns.mean(), returns.std(), 5000)
    win_rate = (sim_results > 0).sum() / 5000 * 100
    avg_sim_profit_pct = sim_results.mean() * 100

    st.markdown(f"### {target_name} 분석 리포트")
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1:
        st.markdown(f'<div class="profit-card"><h1>{avg_sim_profit_pct:+.2f}%</h1><p>예상 수익금: {invest_val * (avg_sim_profit_pct/100):+,.0f}원</p></div>', unsafe_allow_html=True)
    with c2: st.metric("현재가", f"{curr_p:,.0f}원"); st.metric("AI 승률", f"{win_rate:.1f}%")
    with c3: st.metric("목표가(+12%)", f"{curr_p*1.12:,.0f}"); st.metric("손절가(-6%)", f"{curr_p*0.94:,.0f}")

    tab1, tab2, tab3, tab4 = st.tabs(["📉 시세 분석", "🧪 AI 정밀 진단", "📰 실시간 뉴스", "🚀 글로벌 테마"])

    with tab1:
        st.markdown('<div class="ma-legend"><span style="color:#FFD60A;">● 5일</span> <span style="color:#FF37AF;">● 20일</span> <span style="color:#00F2FF;">● 60일</span> <span style="color:#FFFFFF;">● 120일</span></div>', unsafe_allow_html=True)
        fig = make_subplots(rows=2 if show_rsi else 1, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2] if show_rsi else [1], vertical_spacing=0.03)
        if chart_style == "전문가 캔들":
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name=''), row=1, col=1)
        else:
            fig.add_trace(go.Scatter(x=df.index, y=df['Close'], line=dict(color='#00f2ff', width=2), fill='tozeroy', name=''), row=1, col=1)
        
        colors = {5: '#FFD60A', 20: '#FF37AF', 60: '#00F2FF', 120: '#FFFFFF'}
        for ma in show_ma: fig.add_trace(go.Scatter(x=df.index, y=df[f'MA{ma}'], line=dict(color=colors[ma], width=1.3), name=f'{ma}선'), row=1, col=1)
        if show_wave:
            fig.add_trace(go.Scatter(x=df.index, y=df['High_Max'], line=dict(color='#888', dash='dot'), name=''), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['Low_Min'], line=dict(color='#888', dash='dot'), name=''), row=1, col=1)
        if show_rsi: fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color='#333', name=''), row=2, col=1)
        fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with tab2: # 2P 진단 복구
        cl1, cl2 = st.columns([1.2, 1])
        with cl1:
            fig_g = go.Figure(go.Indicator(mode="gauge+number", value=win_rate, title={'text': "승률"}, gauge={'bar': {'color': "#007AFF"}}))
            fig_g.update_layout(height=350, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)'); st.plotly_chart(fig_g, use_container_width=True)
        with cl2: st.markdown(f'<div class="info-card">🎯 <b>타점 가이드</b><br>매수가: <b>{curr_p*0.98:,.0f}</b><br>손절가: <b>{curr_p*0.94:,.0f}</b></div>', unsafe_allow_html=True)

    with tab3: # 뉴스
        res_n = requests.get(f"https://search.naver.com/search.naver?where=news&query={target_name} 특징주", headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(res_n.text, 'html.parser')
        for art in soup.select('.news_area')[:8]: st.markdown(f"· [{art.select_one('.news_tit').text}]({art.select_one('.news_tit')['href']})")

    with tab4: # 테마 추천
        st.write("### 🚀 AI 글로벌 테마")
        themes = {"🛡️ 방산": ["한화에어로스페이스", "LIG넥스원"], "🤖 AI": ["NVDA", "SK하이닉스"], "💰 금융": ["우리금융지주", "KB금융"]}
        cols = st.columns(3)
        for i, (t_name, stocks) in enumerate(themes.items()):
            with cols[i]:
                st.markdown(f'<div class="cate-title">{t_name}</div>', unsafe_allow_html=True)
                for s in stocks: st.markdown(f'<div class="recommend-box"><b>{s}</b></div>', unsafe_allow_html=True)

else: st.error("데이터 로드 실패: FinanceDataReader 라이브러리를 설치했는지 확인하세요.")
