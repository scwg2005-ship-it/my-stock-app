import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO
from bs4 import BeautifulSoup
import re

# --- 1. [디자인] 증권사 프리미엄 터미널 UI ---
st.set_page_config(layout="wide", page_title="Aegis Oracle v69.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;800&display=swap');
    body, .stApp { background-color: #050505; font-family: 'Pretendard', sans-serif; color: #ffffff; }
    .stMetric { background-color: #111; padding: 20px; border-radius: 16px; border: 1px solid #222; }
    .profit-card { background: linear-gradient(135deg, #007AFF 0%, #5856D6 100%); padding: 25px; border-radius: 20px; color: white; text-align: center; margin-bottom: 20px; }
    .info-card { background-color: #161616; padding: 18px; border-radius: 14px; margin-bottom: 12px; border: 1px solid #222; }
    .recommend-box { background: #111; padding: 12px; border-radius: 10px; margin-bottom: 8px; border: 1px solid #333; }
    .cate-title { color: #00f2ff; font-weight: 800; font-size: 1.1rem; border-bottom: 2px solid #333; padding-bottom: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [강력 수정] 지능형 종목 검색 엔진 (Search API 연동) ---
@st.cache_data(ttl=3600)
def search_ticker_intelligent(query):
    """사용자가 입력한 이름으로 야후 파이낸스에서 직접 티커를 찾습니다."""
    try:
        # 1. 먼저 KRX 마스터 리스트 확인 (빠른 매칭)
        url_krx = 'http://kind.krx.co.kr/corpoctl/corpList.do?method=download'
        df_krx = pd.read_html(StringIO(requests.get(url_krx).text), header=0)[0]
        match = df_krx[df_krx['회사명'].str.contains(query, na=False, case=False)]
        if not match.empty:
            code = f"{match.iloc[0]['종목코드']:06d}"
            # 코스피/코스닥 구분 시도 (야후는 .KS 또는 .KQ 사용)
            return f"{code}.KS", match.iloc[0]['회사명']
    except: pass

    # 2. KRX에 없거나 검색 실패 시 야후 검색 API 직접 호출 (우리금융지주 등 해결)
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}&quotesCount=5&newsCount=0&country=Korea"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers).json()
        if res.get('quotes'):
            # 한국 시장(.KS, .KQ) 우선순위로 필터링
            quotes = res['quotes']
            for q in quotes:
                if q['symbol'].endswith(('.KS', '.KQ')):
                    return q['symbol'], q.get('shortname', query)
            # 한국 시장 결과가 없으면 첫 번째 결과 반환 (미국 주식 등)
            return quotes[0]['symbol'], quotes[0].get('shortname', query)
    except: pass
    return query.upper(), query

@st.cache_data(ttl=60)
def get_oracle_data(ticker, mode="일봉"):
    interval_map = {"1분봉": "1m", "일봉": "1d", "월봉": "1mo"}
    period_map = {"1분봉": "1d", "일봉": "1y", "월봉": "max"}
    try:
        data = yf.download(ticker, period=period_map[mode], interval=interval_map[mode], progress=False)
        if data.empty and ".KS" in ticker:
            data = yf.download(ticker.replace(".KS", ".KQ"), period=period_map[mode], interval=interval_map[mode], progress=False)
        if data.empty: return None
        df = data.copy()
        # 이평선 계산
        for ma in [5, 20, 60, 120]:
            df[f'MA{ma}'] = df['Close'].rolling(ma).mean()
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
        df['High_Max'] = df['High'].rolling(20).max(); df['Low_Min'] = df['Low'].rolling(20).min()
        return df
    except: return None

# --- 3. [사이드바] 제어 센터 ---
with st.sidebar:
    st.markdown('<p style="font-size:1.8rem; font-weight:800; color:#00f2ff;">Oracle Control</p>', unsafe_allow_html=True)
    u_input = st.text_input("종목명 또는 티커 입력 (예: 우리금융지주, TSLA)", value="우리금융지주")
    
    # 지능형 검색 실행
    ticker, target_name = search_ticker_intelligent(u_input)
    st.info(f"검색 결과: **{target_name} ({ticker})**")
    
    st.divider()
    view_mode = st.radio("분석 주기", ["1분봉", "일봉", "월봉"], index=1, horizontal=True)
    invest_val = st.number_input("투자 원금 설정", value=10000000)
    
    st.divider()
    chart_style = st.radio("그래프", ["전문가 캔들", "심플 라인"], horizontal=True)
    show_ma = st.multiselect("이평선 표시 (범례에서 색상 확인)", [5, 20, 60, 120], default=[5, 20, 60, 120])
    show_wave = st.checkbox("파동/빗각 레이어", value=True)
    show_rsi = st.checkbox("RSI/거래량 표시", value=True)

# --- 4. [메인] 분석 실행 ---
df = get_oracle_data(ticker, view_mode)

if df is not None:
    curr_p = float(df['Close'].iloc[-1]); unit = "$" if ".KS" not in ticker and ".KQ" not in ticker else "원"
    returns = df['Close'].pct_change().dropna()
    sim_runs = 5000
    sim_results = np.random.normal(returns.mean(), returns.std(), sim_runs)
    win_rate = (sim_results > 0).sum() / sim_runs * 100
    avg_sim_profit_pct = sim_results.mean() * 100
    score = 50 + (25 if curr_p > float(df['MA20'].iloc[-1]) else -10) + (25 if float(df['RSI'].iloc[-1]) < 40 else 0)
    est_profit = invest_val * (avg_sim_profit_pct / 100)

    st.markdown(f"### {target_name} ({ticker})")
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1:
        st.markdown(f"""<div class="profit-card">
            <p style="margin:0; font-size:0.9rem; opacity:0.8;">5,000회 시뮬레이션 기대 수익</p>
            <h1 style="margin:0; font-size:3.2rem;">{avg_sim_profit_pct:+.2f}%</h1>
            <p style="margin:0; font-weight:bold;">수익금: {est_profit:+,.0f} {unit} (승률: {win_rate:.1f}%)</p>
        </div>""", unsafe_allow_html=True)
    with c2: st.metric("현재가", f"{curr_p:,.0f}{unit}"); st.metric("AI 점수", f"{score}점", f"승률 {win_rate:.1f}%")
    with c3: st.metric("목표가 (+12%)", f"{curr_p*1.12:,.0f}{unit}"); st.metric("손절가 (-6%)", f"{curr_p*0.94:,.0f}{unit}")

    tab1, tab2, tab3, tab4 = st.tabs(["📉 시세 분석 차트", "🧪 AI 몬테카를로 진단", "📰 실시간 뉴스", "🚀 글로벌 테마 카테고리"])

    with tab1: # 1P: 시세 차트 (이평선 범례 강화)
        rows = 2 if show_rsi else 1
        fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2] if show_rsi else [1], vertical_spacing=0.03)
        if chart_style == "전문가 캔들" and view_mode != "1분봉":
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], increasing_line_color='#FF3B30', decreasing_line_color='#007AFF', name='시세'), row=1, col=1)
        else:
            fig.add_trace(go.Scatter(x=df.index, y=df['Close'], line=dict(color='#00f2ff', width=2), fill='tozeroy', name='종가'), row=1, col=1)
        
        # [범례 표시를 위해 showlegend=True 설정]
        ma_colors = {5: '#FFD60A', 20: '#FF37AF', 60: '#00F2FF', 120: '#FFFFFF'}
        for ma in show_ma: 
            fig.add_trace(go.Scatter(x=df.index, y=df[f'MA{ma}'], line=dict(color=ma_colors.get(ma, '#888'), width=1.5), name=f'이평선 {ma}일'), row=1, col=1)
        
        if show_wave:
            fig.add_trace(go.Scatter(x=df.index, y=df['High_Max'], line=dict(color='#888', width=1, dash='dot'), name='상단저항'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['Low_Min'], line=dict(color='#888', width=1, dash='dot'), name='하단지지'), row=1, col=1)
        
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color='#333', name='거래량'), row=rows, col=1)
        fig.update_layout(height=650, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(t=30, b=0, l=0, r=0), showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True)

    with tab2: # 2P: AI 진단
        cl1, cl2 = st.columns([1.2, 1])
        with cl1:
            fig_g = go.Figure(go.Indicator(mode="gauge+number", value=win_rate, title={'text': "AI 매수 승률 (%)"}, gauge={'bar': {'color': "#007AFF" if win_rate > 50 else "#FF3B30"}, 'bgcolor': '#222', 'axis': {'range': [0, 100]}}))
            fig_g.update_layout(height=400, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)'); st.plotly_chart(fig_g, use_container_width=True)
        with cl2: st.markdown(f"""<div class="info-card"><b style="font-size:1.2rem; color:#00f2ff;">📊 백데이터 분석</b><br><div style="border-left:5px solid #FF3B30; padding-left:15px; margin-top:10px;">적극 매수가: <b>{curr_p*0.98:,.0f}{unit}</b><br>손절가 가이드: <b>{curr_p*0.94:,.0f}{unit}</b><br>기대 수익률: <b>{avg_sim_profit_pct:.2f}%</b></div></div>""", unsafe_allow_html=True)

    with tab3: # 3P: 뉴스
        st.subheader(f"📰 {target_name} 실시간 특징주 뉴스")
        try:
            res_n = requests.get(f"https://search.naver.com/search.naver?where=news&query={target_name} 특징주", headers={'User-Agent': 'Mozilla/5.0'})
            soup = BeautifulSoup(res_n.text, 'html.parser')
            for art in soup.select('.news_area')[:8]: st.markdown(f"· [{art.select_one('.news_tit').text}]({art.select_one('.news_tit')['href']})")
        except: st.write("뉴스 로드 실패")

    with tab4: # 4P: 전 카테고리 집대성
        st.write("### 🚀 AI 글로벌 핵심 테마 랭킹")
        # 테마 데이터 시각화 (생략 방지 및 실시간성 강화)
        themes = ["🛡️ K-방산", "🤖 AI/반도체", "🔋 2차전지", "💊 바이오", "📡 빅테크", "⚡ 에너지", "🚢 조선", "🍔 음식료", "💰 금융"]
        for i in range(0, 9, 3):
            cols = st.columns(3)
            for j in range(3):
                with cols[j]: st.markdown(f'<div class="info-card"><b style="color:#00f2ff;">{themes[i+j]}</b><br>오늘의 유망 종목: 분석 중...</div>', unsafe_allow_html=True)

else: st.error("데이터 로드 실패: 종목명을 정확히 입력하거나 티커(예: 005930.KS)를 직접 입력해 보세요.")
