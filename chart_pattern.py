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
st.set_page_config(layout="wide", page_title="Aegis Oracle v91.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;800&display=swap');
    body, .stApp { background-color: #050505; font-family: 'Pretendard', sans-serif; color: #ffffff; }
    .stMetric { background-color: #111; padding: 20px; border-radius: 16px; border: 1px solid #222; }
    .profit-card { background: linear-gradient(135deg, #007AFF 0%, #5856D6 100%); padding: 25px; border-radius: 20px; color: white; text-align: center; margin-bottom: 20px; }
    .info-card { background-color: #161616; padding: 18px; border-radius: 14px; margin-bottom: 12px; border: 1px solid #222; }
    .status-tag { padding: 4px 10px; border-radius: 6px; font-weight: 800; font-size: 0.8rem; color: white; }
    .ma-legend { font-size: 0.9rem; font-weight: bold; margin-bottom: 10px; display: flex; gap: 20px; justify-content: flex-end; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [프로세스 1] 데이터 강제 정형화 엔진 (정밀 로드) ---
@st.cache_data(ttl=3600)
def get_fixed_ticker(query):
    # 필수 종목 우선 매핑 (프로세스 테스트용)
    mapping = {"우리금융지주": "053000.KS", "삼성전자": "005930.KS", "엔비디아": "NVDA"}
    if query in mapping: return mapping[query], query
    return query.upper(), query

@st.cache_data(ttl=60)
def get_processed_data(ticker):
    try:
        # 데이터 다운로드 (구조적 결함 방지)
        raw = yf.download(ticker, period="2y", interval="1d", progress=False)
        if raw.empty: return None
        
        df = raw.copy()
        # MultiIndex 강제 해제 (로드 실패의 핵심 원인 제거)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        # 컬럼명 표준화 및 수치 데이터 강제 변환
        df.columns = [str(c).capitalize() for c in df.columns]
        df = df.apply(pd.to_numeric, errors='coerce').dropna(subset=['Close'])
        df.index = pd.to_datetime(df.index).date # 타임존 에러 방지

        # --- [프로세스 2] 기술적 지표 정밀 계산 ---
        for ma in [5, 20, 60, 120]:
            df[f'MA{ma}'] = df['Close'].rolling(ma).mean()
        
        # 정배열/역배열 판독 로직
        last = df.iloc[-1]
        if last['MA5'] > last['MA20'] > last['MA60'] > last['MA120']:
            df['State'] = "정배열 (강력 상승)"
        elif last['MA5'] < last['MA20'] < last['MA60'] < last['MA120']:
            df['State'] = "역배열 (하락 추세)"
        else:
            df['State'] = "혼조세 (방향 탐색)"
            
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
        
        # 파동 지지/저항
        df['Resist'] = df['High'].rolling(20).max()
        df['Support'] = df['Low'].rolling(20).min()
        return df
    except:
        return None

# --- 3. [사이드바] 제어 센터 ---
with st.sidebar:
    st.markdown('<p style="font-size:1.8rem; font-weight:800; color:#00f2ff;">Oracle Control</p>', unsafe_allow_html=True)
    u_input = st.text_input("분석 종목 입력", value="우리금융지주")
    ticker, target_name = get_fixed_ticker(u_input)
    st.info(f"Target: {target_name} ({ticker})")
    invest_val = st.number_input("투자 원금 설정", value=10000000)
    chart_style = st.radio("그래프 모드", ["전문가 캔들", "심플 라인"], horizontal=True)

# --- 4. [메인] 정밀 프로세스 가동 ---
df = get_processed_data(ticker)

if df is not None:
    curr_p = float(df['Close'].iloc[-1]); unit = "원" if ".KS" in ticker else "$"
    state = df['State'].iloc[-1]
    state_clr = "#00f2ff" if "정배열" in state else "#ff37af" if "역배열" in state else "#888"

    # --- [프로세스 3] 5,000회 몬테카를로 시뮬레이션 ---
    returns = df['Close'].pct_change().dropna()
    sim_results = np.random.normal(returns.mean(), returns.std(), 5000)
    win_rate = (sim_results > 0).sum() / 5000 * 100
    avg_profit = sim_results.mean() * 100

    # 헤더 및 배열 상태
    st.markdown(f"### {target_name} <span class='status-tag' style='background:{state_clr};'>{state}</span>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1.5, 1, 1])
    with col1:
        st.markdown(f'<div class="profit-card"><h1>{avg_profit:+.2f}%</h1><p>5,000회 시뮬레이션 기대수익</p></div>', unsafe_allow_html=True)
    with col2: st.metric("현재가", f"{curr_p:,.0f}{unit}"); st.metric("승률", f"{win_rate:.1f}%")
    with col3: st.metric("목표가(+12%)", f"{curr_p*1.12:,.0f}"); st.metric("손절가(-6%)", f"{curr_p*0.94:,.0f}")

    tab1, tab2, tab3, tab4 = st.tabs(["📉 분석 차트", "🧪 정밀 기술 진단", "📰 실시간 뉴스", "🚀 글로벌 테마"])

    with tab1: # 1페이지 고정 차트
        st.markdown('<div class="ma-legend"><span style="color:#FFD60A;">● 5일</span> <span style="color:#FF37AF;">● 20일</span> <span style="color:#00F2FF;">● 60일</span> <span style="color:#FFFFFF;">● 120일</span></div>', unsafe_allow_html=True)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.03)
        if chart_style == "전문가 캔들":
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='시세'), row=1, col=1)
        else:
            fig.add_trace(go.Scatter(x=df.index, y=df['Close'], line=dict(color='#00f2ff', width=2), fill='tozeroy', name='시세'), row=1, col=1)
        
        for ma, clr in zip([5, 20, 60, 120], ['#FFD60A', '#FF37AF', '#00F2FF', '#FFFFFF']):
            fig.add_trace(go.Scatter(x=df.index, y=df[f'MA{ma}'], line=dict(color=clr, width=1.2), name=f'{ma}선'), row=1, col=1)
        
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color='#333', name='거래량'), row=2, col=1)
        fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with tab2: # 2페이지 정밀 진단
        c1, c2 = st.columns([1.2, 1])
        with c1:
            fig_dist = go.Figure(); fig_dist.add_trace(go.Histogram(x=sim_results, nbinsx=50, marker_color='#007AFF'))
            fig_dist.update_layout(title="수익률 분포 시뮬레이션 (5,000회)", template='plotly_dark', height=350); st.plotly_chart(fig_dist, use_container_width=True)
        with c2:
            st.markdown(f"""<div class="info-card">
                <b>🔍 정밀 기술 지표</b><br>
                RSI 강도: {df['RSI'].iloc[-1]:.1f} ({"과매수" if df['RSI'].iloc[-1]>70 else "과매도" if df['RSI'].iloc[-1]<30 else "중립"})<br>
                이평선 배열: {state}<br>
                20일 저항선: {df['Resist'].iloc[-1]:,.0f}<br>
                20일 지지선: {df['Support'].iloc[-1]:,.0f}
            </div>""", unsafe_allow_html=True)

    with tab3: # 실시간 뉴스
        try:
            res_n = requests.get(f"https://search.naver.com/search.naver?where=news&query={target_name} 특징주", headers={'User-Agent': 'Mozilla/5.0'})
            soup = BeautifulSoup(res_n.text, 'html.parser')
            for art in soup.select('.news_area')[:8]:
                st.markdown(f"📍 [{art.select_one('.news_tit').text}]({art.select_one('.news_tit')['href']})")
        except: st.write("뉴스를 불러올 수 없습니다.")

    with tab4: # 글로벌 테마 (종목 최소화)
        st.write("### 🚀 글로벌 테마 섹터 (다음 주 업데이트 예정)")
        themes = {"🛡️ K-방산": ["한화에어로스페이스"], "🤖 AI/반도체": ["NVDA", "SK하이닉스"], "💰 금융": ["우리금융지주"]}
        cols = st.columns(3)
        for i, (t_name, stocks) in enumerate(themes.items()):
            with cols[i]:
                st.markdown(f'<div class="info-card"><b>{t_name}</b><br>{", ".join(stocks)}</div>', unsafe_allow_html=True)

else:
    st.error("데이터 로드 실패: 티커를 확인하세요. (005930.KS 등)")
