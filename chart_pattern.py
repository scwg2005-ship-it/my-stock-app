import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO
from bs4 import BeautifulSoup

# --- 1. [디자인] 증권사 프리미엄 터미널 UI ---
st.set_page_config(layout="wide", page_title="Aegis Oracle v64.3")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;800&display=swap');
    body, .stApp { background-color: #050505; font-family: 'Pretendard', sans-serif; color: #ffffff; }
    .stMetric { background-color: #111; padding: 20px; border-radius: 16px; border: 1px solid #222; }
    .profit-card { background: linear-gradient(135deg, #007AFF 0%, #5856D6 100%); padding: 25px; border-radius: 20px; color: white; text-align: center; margin-bottom: 20px; }
    .info-card { background-color: #161616; padding: 18px; border-radius: 14px; margin-bottom: 12px; border: 1px solid #222; }
    .price-guide { border-left: 5px solid #FF3B30; padding-left: 15px; margin-top: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [데이터] 글로벌 멀티 데이터 엔진 ---
@st.cache_data(ttl=86400)
def get_krx_dict_v64():
    try:
        url = 'http://kind.krx.co.kr/corpoctl/corpList.do?method=download'
        df = pd.read_html(StringIO(requests.get(url).text), header=0)[0]
        df = df[['회사명', '종목코드']].copy()
        df['ticker'] = df['종목코드'].apply(lambda x: f"{x:06d}.KS")
        return dict(zip(df['회사명'], df['ticker']))
    except: return {"삼성전자": "005930.KS", "한화솔루션": "009830.KS"}

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
        df['MA5'] = df['Close'].rolling(5).mean(); df['MA20'] = df['Close'].rolling(20).mean()
        delta = df['Close'].diff(); gain = (delta.where(delta > 0, 0)).rolling(14).mean(); loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
        df['High_Max'] = df['High'].rolling(20).max(); df['Low_Min'] = df['Low'].rolling(20).min()
        return df
    except: return None

# --- 3. [사이드바] 풍부한 선택사항 ---
krx_map = get_krx_dict_v64()
with st.sidebar:
    st.markdown('<p style="font-size:1.8rem; font-weight:800; color:#00f2ff;">Oracle Control</p>', unsafe_allow_html=True)
    u_input = st.text_input("종목명/티커 입력", value="한화솔루션")
    filtered = [n for n in krx_map.keys() if u_input in n]
    target_name = st.selectbox(f"검색 결과 ({len(filtered)}건)", options=filtered[:100] if filtered else [u_input])
    ticker = krx_map.get(target_name, u_input.upper())
    
    st.divider()
    view_mode = st.radio("분석 주기", ["1분봉", "일봉", "월봉"], index=1, horizontal=True)
    invest_val = st.number_input("투자 원금 설정", value=10000000)
    
    st.divider()
    st.subheader("🛠️ 차트 레이어 커스텀")
    chart_style = st.radio("그래프 형태", ["전문가 캔들", "심플 라인"], horizontal=True)
    show_ma = st.multiselect("이평선 표시", [5, 20, 60], default=[5, 20])
    show_wave = st.checkbox("엘리어트 파동/빗각 레이어", value=True)
    fit_candle = st.checkbox("추세선 종가(Close) 기준 정렬", value=True)
    show_rsi = st.checkbox("RSI/거래량 표시", value=True)

# --- 4. [메인] 분석 및 시뮬레이션 ---
df = get_oracle_data(ticker, view_mode)

if df is not None:
    curr_p = float(df['Close'].iloc[-1])
    unit = "$" if ".KS" not in ticker and ".KQ" not in ticker else "원"
    
    # [5,000회 몬테카를로 엔진]
    returns = df['Close'].pct_change().dropna()
    sim_runs = 5000
    sim_results = np.random.normal(returns.mean(), returns.std(), sim_runs)
    win_rate = (sim_results > 0).sum() / sim_runs * 100
    avg_sim_profit_pct = sim_results.mean() * 100
    
    # 퀀트 점수 & 수익금
    score = 50 + (25 if curr_p > float(df['MA20'].iloc[-1]) else -10) + (25 if float(df['RSI'].iloc[-1]) < 40 else 0)
    est_profit = invest_val * (avg_sim_profit_pct / 100)

    # 상단 대시보드
    st.markdown(f"### {target_name} ({ticker})")
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1:
        st.markdown(f"""<div class="profit-card">
            <p style="margin:0; font-size:0.9rem; opacity:0.8;">5,000회 시뮬레이션 기대 수익</p>
            <h1 style="margin:0; font-size:3.2rem;">{avg_sim_profit_pct:+.2f}%</h1>
            <p style="margin:0; font-weight:bold;">수익금: {est_profit:+,.0f} {unit} (승률: {win_rate:.1f}%)</p>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.metric("현재가", f"{curr_p:,.0f}{unit}")
        st.metric("AI 퀀트 점수", f"{score}점", f"승률 {win_rate:.1f}%")
    with c3:
        st.metric("목표가 (+12%)", f"{curr_p*1.12:,.0f}{unit}")
        st.metric("손절가 (-6%)", f"{curr_p*0.94:,.0f}{unit}")

    tab1, tab2, tab3 = st.tabs(["📉 시세 분석", "🧪 AI 정밀 진단 (타점 가이드)", "📰 실시간 뉴스"])

    with tab1:
        rows = 2 if show_rsi else 1
        fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2] if show_rsi else [1], vertical_spacing=0.03)
        if chart_style == "전문가 캔들" and view_mode != "1분봉":
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], increasing_line_color='#FF3B30', decreasing_line_color='#007AFF', name=''), row=1, col=1)
        else:
            fig.add_trace(go.Scatter(x=df.index, y=df['Close'], line=dict(color='#00f2ff', width=2), fill='tozeroy', name=''), row=1, col=1)
        for ma in show_ma: fig.add_trace(go.Scatter(x=df.index, y=df[f'MA{ma}'], line=dict(width=1.2), name=f'{ma}선'), row=1, col=1)
        if show_wave:
            fig.add_trace(go.Scatter(x=df.index, y=df['High_Max'], line=dict(color='#888', width=1, dash='dot'), name='저항'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['Low_Min'], line=dict(color='#888', width=1, dash='dot'), name='지지'), row=1, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color='#333', name='거래량'), row=rows, col=1)
        fig.update_layout(height=650, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with tab2: # 2페이지: 온도계 및 가격 가이드 복구
        st.write("### AI 정밀 분석 및 타점 가이드")
        cl1, cl2 = st.columns([1.2, 1])
        with cl1:
            # AI 온도계 (승률 기반)
            fig_g = go.Figure(go.Indicator(mode="gauge+number", value=win_rate, title={'text': "AI 매수 승률 (%)"}, gauge={'bar': {'color': "#007AFF" if win_rate > 50 else "#FF3B30"}, 'bgcolor': '#222', 'axis': {'range': [0, 100]}}))
            fig_g.update_layout(height=400, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_g, use_container_width=True)
        with cl2:
            st.markdown(f"""
                <div class="info-card">
                    <b style="font-size:1.2rem; color:#00f2ff;">🎯 실시간 타점 가이드</b><br>
                    <div class="price-guide">
                        적극 매수가: <b style="color:#00C7BE;">{curr_p*0.98:,.0f}{unit}</b> (현재가 대비 -2%)<br>
                        <b>목표가 (1차): {curr_p*1.12:,.0f}{unit}</b> (+12%)<br>
                        <b style="color:#FF3B30;">손절가 (Stop): {curr_p*0.94:,.0f}{unit}</b> (-6%)
                    </div><br>
                    <b>AI 분석 의견</b><br>
                    5,000회 시뮬레이션 결과 평균 기대 수익률은 <b>{avg_sim_profit_pct:.2f}%</b>이며, 
                    현재 RSI {df['RSI'].iloc[-1]:.1f} 수준으로 보조지표 상 {'과매수' if df['RSI'].iloc[-1] > 70 else '과매도' if df['RSI'].iloc[-1] < 30 else '중립'} 구간입니다.
                </div>
            """, unsafe_allow_html=True)

    with tab3: # 뉴스
        res_n = requests.get(f"https://search.naver.com/search.naver?where=news&query={target_name}+특징주")
        soup = BeautifulSoup(res_n.text, 'html.parser')
        for art in soup.select('.news_area')[:6]:
            st.write(f"· [{art.select_one('.news_tit').text}]({art.select_one('.news_tit')['href']})")
        st.divider()
        st.markdown("[🚀 실시간 테마주 확인](https://finance.naver.com/sise/theme.naver)")

else:
    st.error("데이터 로드 실패")
