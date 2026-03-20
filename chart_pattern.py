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
st.set_page_config(layout="wide", page_title="Aegis Oracle v71.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;800&display=swap');
    body, .stApp { background-color: #050505; font-family: 'Pretendard', sans-serif; color: #ffffff; }
    .stMetric { background-color: #111; padding: 20px; border-radius: 16px; border: 1px solid #222; }
    .profit-card { background: linear-gradient(135deg, #007AFF 0%, #5856D6 100%); padding: 25px; border-radius: 20px; color: white; text-align: center; margin-bottom: 20px; }
    .info-card { background-color: #161616; padding: 18px; border-radius: 14px; margin-bottom: 12px; border: 1px solid #222; }
    .ma-legend { font-size: 0.9rem; font-weight: bold; margin-bottom: 10px; display: flex; gap: 20px; justify-content: flex-end; }
    .recommend-box { background: #111; padding: 12px; border-radius: 10px; margin-bottom: 8px; border: 1px solid #333; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [데이터] 지능형 검색 및 데이터 구조 강제 고정 (핵심 해결책) ---
@st.cache_data(ttl=3600)
def find_ticker_ultimate(query):
    # 1. KRX 리스트 대조
    try:
        url_krx = 'http://kind.krx.co.kr/corpoctl/corpList.do?method=download'
        df_krx = pd.read_html(StringIO(requests.get(url_krx).text), header=0)[0]
        match = df_krx[df_krx['회사명'].str.contains(query, na=False, case=False)]
        if not match.empty:
            code = f"{match.iloc[0]['종목코드']:06d}"
            return f"{code}.KS", match.iloc[0]['회사명']
    except: pass
    
    # 2. Yahoo Search API 백업
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}&quotesCount=1"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).json()
        if res.get('quotes'):
            return res['quotes'][0]['symbol'], res['quotes'][0].get('shortname', query)
    except: pass
    return query.upper(), query

@st.cache_data(ttl=60)
def get_safe_data(ticker, mode="일봉"):
    interval_map = {"1분봉": "1m", "일봉": "1d", "월봉": "1mo"}
    period_map = {"1분봉": "1d", "일봉": "1y", "월봉": "max"}
    try:
        # 데이터 로드 (yfinance의 최신 구조 대응)
        data = yf.download(ticker, period=period_map[mode], interval=interval_map[mode], progress=False)
        if data.empty and ".KS" in ticker:
            data = yf.download(ticker.replace(".KS", ".KQ"), period=period_map[mode], interval=interval_map[mode], progress=False)
        
        if data.empty: return None
        
        # [수정 핵심] 멀티인덱스 컬럼을 단일 인덱스로 강제 평탄화하고 이름을 고정함
        df = data.copy()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        # 컬럼명이 정확히 대문자로 시작하는지 확인하고 수정
        col_map = {col: col.capitalize() for col in df.columns}
        df.rename(columns=col_map, inplace=True)
        
        # 필요한 지표 계산
        for ma in [5, 20, 60, 120]:
            df[f'MA{ma}'] = df['Close'].rolling(ma).mean()
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
        df['High_Max'] = df['High'].rolling(20).max()
        df['Low_Min'] = df['Low'].rolling(20).min()
        return df
    except Exception:
        return None

# --- 3. [사이드바] 제어 센터 ---
with st.sidebar:
    st.markdown('<p style="font-size:1.8rem; font-weight:800; color:#00f2ff;">Oracle Control</p>', unsafe_allow_html=True)
    u_input = st.text_input("종목명 입력", value="삼성전자")
    ticker, target_name = find_ticker_ultimate(u_input)
    st.success(f"매칭 완료: **{target_name} ({ticker})**")
    
    st.divider()
    view_mode = st.radio("분석 주기", ["1분봉", "일봉", "월봉"], index=1, horizontal=True)
    invest_val = st.number_input("투자 원금", value=10000000)
    
    st.divider()
    chart_style = st.radio("그래프 형태", ["전문가 캔들", "심플 라인"], horizontal=True)
    show_ma = st.multiselect("이평선 표시", [5, 20, 60, 120], default=[5, 20, 60, 120])
    show_wave = st.checkbox("파동/빗각 레이어", value=True)
    show_rsi = st.checkbox("RSI/거래량 표시", value=True)

# --- 4. [메인] 분석 실행 ---
df = get_safe_data(ticker, view_mode)

if df is not None:
    curr_p = float(df['Close'].iloc[-1]); unit = "$" if ".KS" not in ticker and ".KQ" not in ticker else "원"
    
    # 5,000회 몬테카를로 시뮬레이션
    returns = df['Close'].pct_change().dropna()
    sim_results = np.random.normal(returns.mean(), returns.std(), 5000)
    win_rate = (sim_results > 0).sum() / 5000 * 100
    avg_sim_profit_pct = sim_results.mean() * 100
    score = 50 + (25 if curr_p > float(df['MA20'].iloc[-1]) else -10)
    
    # 상단 대시보드
    st.markdown(f"### {target_name} ({ticker})")
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1:
        st.markdown(f"""<div class="profit-card">
            <p style="margin:0; opacity:0.8;">5,000회 시뮬레이션 기대 수익</p>
            <h1 style="margin:0; font-size:3.2rem;">{avg_sim_profit_pct:+.2f}%</h1>
            <p style="margin:0; font-weight:bold;">수익금: {invest_val * (avg_sim_profit_pct/100):+,.0f} {unit} (승률: {win_rate:.1f}%)</p>
        </div>""", unsafe_allow_html=True)
    with c2: st.metric("현재가", f"{curr_p:,.0f}{unit}"); st.metric("AI 승률", f"{win_rate:.1f}%")
    with c3: st.metric("목표가(+12%)", f"{curr_p*1.12:,.0f}{unit}"); st.metric("손절가(-6%)", f"{curr_p*0.94:,.0f}{unit}")

    tab1, tab2, tab3, tab4 = st.tabs(["📉 시세 분석", "🧪 AI 몬테카를로 진단", "📰 실시간 뉴스", "🚀 글로벌 테마 랭킹"])

    with tab1:
        # 이평선 색상 범례
        st.markdown(f"""<div class="ma-legend">
            <span style="color:#FFD60A;">● 5일선</span> <span style="color:#FF37AF;">● 20일선</span> 
            <span style="color:#00F2FF;">● 60일선</span> <span style="color:#FFFFFF;">● 120일선</span>
        </div>""", unsafe_allow_html=True)
        
        rows = 2 if show_rsi else 1
        fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2] if show_rsi else [1], vertical_spacing=0.03)
        if chart_style == "전문가 캔들" and view_mode != "1분봉":
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='시세'), row=1, col=1)
        else:
            fig.add_trace(go.Scatter(x=df.index, y=df['Close'], line=dict(color='#00f2ff', width=2), name='시세'), row=1, col=1)
        
        ma_colors = {5: '#FFD60A', 20: '#FF37AF', 60: '#00F2FF', 120: '#FFFFFF'}
        for ma in show_ma: fig.add_trace(go.Scatter(x=df.index, y=df[f'MA{ma}'], line=dict(color=ma_colors[ma], width=1.3), name=f'{ma}선'), row=1, col=1)
        
        if show_wave:
            fig.add_trace(go.Scatter(x=df.index, y=df['High_Max'], line=dict(color='#888', dash='dot'), name='저항'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['Low_Min'], line=dict(color='#888', dash='dot'), name='지지'), row=1, col=1)
        
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color='#333', name='거래량'), row=rows, col=1)
        fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        cl1, cl2 = st.columns([1.2, 1])
        with cl1:
            fig_g = go.Figure(go.Indicator(mode="gauge+number", value=win_rate, title={'text': "상승 확률 (%)"}, gauge={'bar': {'color': "#007AFF"}}))
            fig_g.update_layout(height=350, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)'); st.plotly_chart(fig_g, use_container_width=True)
        with cl2: st.markdown(f'<div class="info-card"><b>🎯 타점 가이드</b><br>매수가: <b>{curr_p*0.98:,.0f}{unit}</b><br>손절가: <b>{curr_p*0.94:,.0f}{unit}</b><br>기대수익: <b>{avg_sim_profit_pct:.2f}%</b></div>', unsafe_allow_html=True)

    with tab3:
        try:
            res_n = requests.get(f"https://search.naver.com/search.naver?where=news&query={target_name} 특징주", headers={'User-Agent': 'Mozilla/5.0'})
            soup = BeautifulSoup(res_n.text, 'html.parser')
            for art in soup.select('.news_area')[:8]: st.write(f"· [{art.select_one('.news_tit').text}]({art.select_one('.news_tit')['href']})")
        except: st.write("뉴스 로드 실패")

    with tab4:
        st.write("### 🚀 글로벌 테마 카테고리 (AI 퀀트 추천)")
        theme_data = {
            "🛡️ 방산": [{"m": "KR", "n": "한화에어로스페이스", "s": 94}, {"m": "US", "n": "LMT", "s": 85}],
            "🤖 AI/반도체": [{"m": "US", "n": "NVDA", "s": 98}, {"m": "KR", "n": "SK하이닉스", "s": 92}],
            "🔋 2차전지": [{"m": "US", "n": "TSLA", "s": 82}, {"m": "KR", "n": "LG에너지솔루션", "s": 78}],
            "💊 바이오": [{"m": "KR", "n": "알테오젠", "s": 95}, {"m": "US", "n": "LLY", "s": 93}],
            "🚢 조선": [{"m": "KR", "n": "HD현대중공업", "s": 83}, {"m": "KR", "n": "삼성중공업", "s": 79}],
            "💰 금융": [{"m": "KR", "n": "우리금융지주", "s": 89}, {"m": "US", "n": "JPM", "s": 87}]
        }
        cols = st.columns(3)
        for i, (theme, stocks) in enumerate(theme_data.items()):
            with cols[i % 3]:
                st.markdown(f'<div class="cate-title" style="color:#00f2ff; font-weight:bold;">{theme}</div>', unsafe_allow_html=True)
                for s in stocks:
                    st.markdown(f'<div class="info-card">{s["n"]} | AI 점수: {s["s"]}</div>', unsafe_allow_html=True)

else: st.error("데이터 로드 실패: 종목명을 다시 확인하거나 잠시 후 시도하세요.")
