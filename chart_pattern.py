import streamlit as st
import pandas as pd
import FinanceDataReader as fdr  # 국장 전용 (네이버/KRX 직결)
import yfinance as yf           # 미장 전용 (야후 파이낸스)
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO
from bs4 import BeautifulSoup

# --- 1. [디자인] 증권사 프리미엄 터미널 UI ---
st.set_page_config(layout="wide", page_title="Aegis Oracle v94.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;800&display=swap');
    body, .stApp { background-color: #050505; font-family: 'Pretendard', sans-serif; color: #ffffff; }
    .stMetric { background-color: #111; padding: 20px; border-radius: 16px; border: 1px solid #222; }
    .profit-card { background: linear-gradient(135deg, #007AFF 0%, #5856D6 100%); padding: 25px; border-radius: 20px; color: white; text-align: center; margin-bottom: 20px; }
    .info-card { background-color: #161616; padding: 18px; border-radius: 14px; margin-bottom: 12px; border: 1px solid #222; }
    .status-tag { padding: 4px 12px; border-radius: 6px; font-weight: 800; font-size: 0.85rem; color: white; margin-left: 10px; }
    .news-link { color: #00f2ff; text-decoration: none; font-weight: 600; font-size: 0.9rem; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [연결 엔진] 하이브리드 데이터 로더 (검증 완료) ---
@st.cache_data(ttl=3600)
def find_symbol_intelligent(query):
    # 고정 매핑 (프로세스 안정성 확보)
    mapping = {"우리금융지주": ("053000", "KR"), "삼성전자": ("005930", "KR"), "엔비디아": ("NVDA", "US"), "테슬라": ("TSLA", "US")}
    if query in mapping: return mapping[query][0], query, mapping[query][1]
    
    try: # 국장(KRX) 검색 시도
        url = 'http://kind.krx.co.kr/corpoctl/corpList.do?method=download'
        res = requests.get(url, timeout=5)
        df_krx = pd.read_html(StringIO(res.text), header=0)[0]
        match = df_krx[df_krx['회사명'].str.contains(query, na=False, case=False)]
        if not match.empty: return f"{match.iloc[0]['종목코드']:06d}", match.iloc[0]['회사명'], "KR"
    except: pass
    return query.upper(), query, "US"

@st.cache_data(ttl=60)
def get_hybrid_data(symbol, market_type):
    try:
        if market_type == "KR":
            # [국장 최강] FinanceDataReader는 네이버 금융 데이터를 긁어와 가장 안정적임
            df = fdr.DataReader(symbol, period="1y")
            df.columns = [str(c).capitalize() for c in df.columns]
        else:
            # [미장 최강] yfinance는 미국 주식 데이터의 표준임
            # MultiIndex 방지를 위해 2024년 최신 옵션 및 평탄화 적용
            raw = yf.download(symbol, period="1y", progress=False)
            df = raw.copy()
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df.columns = [str(c).capitalize() for c in df.columns]

        if df.empty: return None
        df.index = pd.to_datetime(df.index).date
        
        # [정밀 분석] 기술적 지표 및 배열 판독
        for ma in [5, 20, 60, 120]: df[f'MA{ma}'] = df['Close'].rolling(ma).mean()
        
        last = df.iloc[-1]
        if last['MA5'] > last['MA20'] > last['MA60'] > last['MA120']: df['State'] = "정배열 (상승)"
        elif last['MA5'] < last['MA20'] < last['MA60'] < last['MA120']: df['State'] = "역배열 (하락)"
        else: df['State'] = "혼조세"
        
        # RSI & 변동성
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
        return df
    except: return None

# --- 3. [메인 화면 구성] ---
with st.sidebar:
    st.markdown('<p style="font-size:1.8rem; font-weight:800; color:#00f2ff;">Oracle Master</p>', unsafe_allow_html=True)
    u_input = st.text_input("분석 종목 (국장/미장 자동판별)", value="우리금융지주")
    symbol, target_name, m_type = find_symbol_intelligent(u_input)
    st.info(f"Connected: {target_name} ({symbol}) | Market: {m_type}")
    invest_val = st.number_input("투자 원금 설정", value=10000000)

df = get_hybrid_data(symbol, m_type)

if df is not None:
    # --- [프로세스] 시뮬레이션 및 데이터 추출 ---
    curr_p = float(df['Close'].iloc[-1]); unit = "원" if m_type == "KR" else "$"
    state = df['State'].iloc[-1]; state_clr = "#00f2ff" if "정배열" in state else "#ff37af" if "역배열" in state else "#888"
    returns = df['Close'].pct_change().dropna()
    sim_results = np.random.normal(returns.mean(), returns.std(), 5000)
    win_rate = (sim_results > 0).sum() / 5000 * 100
    avg_profit = sim_results.mean() * 100

    # 헤더
    st.markdown(f"### {target_name} <span class='status-tag' style='background:{state_clr};'>{state}</span>", unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1:
        st.markdown(f'<div class="profit-card"><h1>{avg_profit:+.2f}%</h1><p>5,000회 몬테카를로 기대수익</p></div>', unsafe_allow_html=True)
    with c2: st.metric("현재가", f"{curr_p:,.0f}{unit}"); st.metric("AI 매수 승률", f"{win_rate:.1f}%")
    with c3: st.metric("목표가(+12%)", f"{curr_p*1.12:,.0f}"); st.metric("손절가(-6%)", f"{curr_p*0.94:,.0f}")

    tab1, tab2, tab3, tab4 = st.tabs(["📉 분석 차트", "🧪 정밀 기술 온도계", "📰 실시간 뉴스/테마", "🚀 글로벌 테마 리스트"])

    with tab1: # 1페이지: 고정 차트
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='시세'), row=1, col=1)
        for ma, clr in zip([5, 20, 60, 120], ['#FFD60A', '#FF37AF', '#00F2FF', '#FFFFFF']):
            fig.add_trace(go.Scatter(x=df.index, y=df[f'MA{ma}'], line=dict(color=clr, width=1.2), name=f'{ma}선'), row=1, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color='#333', name='거래량'), row=2, col=1)
        fig.update_layout(height=650, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with tab2: # 2페이지: 정밀 온도계
        cl1, cl2 = st.columns([1.2, 1])
        with cl1:
            fig_g = go.Figure(go.Indicator(
                mode = "gauge+number", value = win_rate, title = {'text': "AI 매수 온도 (승률 %)"},
                gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "#007AFF"},
                        'steps': [{'range': [0, 40], 'color': "#333"}, {'range': [70, 100], 'color': "#222"}]}
            ))
            fig_g.update_layout(height=400, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)'); st.plotly_chart(fig_g, use_container_width=True)
        with cl2:
            st.markdown(f'<div class="info-card"><b>🔍 정밀 기술 지표</b><br>RSI: {df["RSI"].iloc[-1]:.1f}<br>이평선: {state}<br>배열 상태: {"안정" if "정배열" in state else "주의"}</div>', unsafe_allow_html=True)

    with tab3: # 3페이지: 뉴스 URL 통합
        c_news, c_url = st.columns(2)
        with c_news:
            st.markdown("#### 📰 실시간 뉴스")
            try:
                res_n = requests.get(f"https://search.naver.com/search.naver?where=news&query={target_name} 특징주", headers={'User-Agent': 'Mozilla/5.0'})
                soup = BeautifulSoup(res_n.text, 'html.parser')
                for art in soup.select('.news_area')[:6]:
                    st.markdown(f"📍 <a href='{art.select_one('.news_tit')['href']}' class='news-link' target='_blank'>{art.select_one('.news_tit').text}</a>", unsafe_allow_html=True)
            except: st.write("뉴스 연동 중...")
        with c_url:
            st.markdown("#### ⚡ 급등 테마/섹터 분석")
            st.markdown("- [📊 네이버 증권 테마별 시세](https://finance.naver.com/sise/theme.naver)")
            st.markdown("- [🔍 인베스팅닷컴 글로벌 속보](https://kr.investing.com/news/stock-market-news)")
            st.markdown("- [🛡️ 한국경제 종목 정밀진단](https://eureca.hankyung.com/)")

    with tab4: # 4페이지: 글로벌 테마 종목 확장
        st.write("### 🚀 AI 글로벌 핵심 테마 9대 섹터")
        themes = {
            "🤖 AI/반도체": ["NVDA", "ASML", "SK하이닉스", "TSM", "AVGO", "AMD"],
            "🛡️ K-방산/우주": ["한화에어로스페이스", "LIG넥스원", "현대로템", "KAI", "RTX", "LMT"],
            "💰 금융/비트코인": ["우리금융지주", "KB금융", "JPM", "GS", "COIN", "MSTR"],
            "💊 바이오": ["알테오젠", "LLY", "NVO", "삼성바이오로직스", "AMGN", "VRTX"],
            "🔋 2차전지/EV": ["TSLA", "LG에너지솔루션", "에코프로", "BYD", "CATL", "삼성SDI"],
            "🏗️ 에너지/원자력": ["CEG", "SMR", "두산에너빌리티", "VST", "한전산업", "XOM"]
        }
        cols = st.columns(3)
        for i, (t_name, stocks) in enumerate(themes.items()):
            with cols[i % 3]:
                st.markdown(f'<p style="color:#00f2ff; font-weight:bold; border-bottom:1px solid #333;">{t_name}</p>', unsafe_allow_html=True)
                for s in stocks: st.markdown(f'<div class="info-card" style="padding:8px; margin-bottom:4px;"><b>{s}</b></div>', unsafe_allow_html=True)

else: st.error("데이터 로드 실패: 티커를 확인하세요.")
