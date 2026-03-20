import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO
from bs4 import BeautifulSoup

# --- 1. [디자인] 증권사 터미널급 프리미엄 UI ---
st.set_page_config(layout="wide", page_title="Aegis Oracle v92.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;800&display=swap');
    body, .stApp { background-color: #050505; font-family: 'Pretendard', sans-serif; color: #ffffff; }
    .stMetric { background-color: #111; padding: 20px; border-radius: 16px; border: 1px solid #222; }
    .profit-card { background: linear-gradient(135deg, #007AFF 0%, #5856D6 100%); padding: 25px; border-radius: 20px; color: white; text-align: center; margin-bottom: 20px; }
    .info-card { background-color: #161616; padding: 18px; border-radius: 14px; margin-bottom: 12px; border: 1px solid #222; }
    .status-tag { padding: 4px 12px; border-radius: 6px; font-weight: 800; font-size: 0.85rem; color: white; margin-left: 10px; }
    .cate-title { color: #00f2ff; font-weight: 800; font-size: 1.1rem; border-bottom: 2px solid #333; padding-bottom: 5px; margin-top: 15px; }
    .recommend-box { background: #111; padding: 10px; border-radius: 8px; margin-bottom: 6px; border: 1px solid #333; font-size: 0.85rem; }
    .news-link { color: #00f2ff; text-decoration: none; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [프로세스] 데이터 정형화 및 정밀 분석 엔진 ---
@st.cache_data(ttl=3600)
def find_ticker_intelligent(query):
    mapping = {"우리금융지주": "053000.KS", "삼성전자": "005930.KS", "SK하이닉스": "000660.KS"}
    if query in mapping: return mapping[query], query
    try:
        url = 'http://kind.krx.co.kr/corpoctl/corpList.do?method=download'
        res = requests.get(url, timeout=5)
        df_krx = pd.read_html(StringIO(res.text), header=0)[0]
        match = df_krx[df_krx['회사명'].str.contains(query, na=False, case=False)]
        if not match.empty: return f"{match.iloc[0]['종목코드']:06d}.KS", match.iloc[0]['회사명']
    except: pass
    return query.upper(), query

@st.cache_data(ttl=60)
def get_oracle_data(ticker):
    try:
        raw = yf.download(ticker, period="2y", interval="1d", progress=False)
        if raw.empty: return None
        df = raw.copy()
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).capitalize() for c in df.columns]
        df.index = pd.to_datetime(df.index).date
        
        # 기술적 지표 계산
        for ma in [5, 20, 60, 120]: df[f'MA{ma}'] = df['Close'].rolling(ma).mean()
        
        # 정배열/역배열 판독
        last = df.iloc[-1]
        if last['MA5'] > last['MA20'] > last['MA60'] > last['MA120']: df['State'] = "정배열 (상승)"
        elif last['MA5'] < last['MA20'] < last['MA60'] < last['MA120']: df['State'] = "역배열 (하락)"
        else: df['State'] = "혼조세"
        
        # RSI & 변동성
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
        df['Vol_Score'] = df['Close'].pct_change().rolling(20).std() * 100
        return df
    except: return None

# --- 3. [사이드바] 제어 센터 ---
with st.sidebar:
    st.markdown('<p style="font-size:1.8rem; font-weight:800; color:#00f2ff;">Oracle Control</p>', unsafe_allow_html=True)
    u_input = st.text_input("종목명 입력", value="우리금융지주")
    ticker, target_name = find_ticker_intelligent(u_input)
    st.info(f"Target: {target_name} ({ticker})")
    invest_val = st.number_input("투자 원금 설정", value=10000000)
    chart_style = st.radio("그래프 모드", ["전문가 캔들", "심플 라인"], horizontal=True)

# --- 4. [메인] 정밀 분석 로직 가동 ---
df = get_oracle_data(ticker)

if df is not None:
    curr_p = float(df['Close'].iloc[-1]); unit = "원" if ".KS" in ticker else "$"
    state = df['State'].iloc[-1]; state_clr = "#00f2ff" if "정배열" in state else "#ff37af" if "역배열" in state else "#888"
    
    # 5,000회 시뮬레이션
    returns = df['Close'].pct_change().dropna()
    sim_results = np.random.normal(returns.mean(), returns.std(), 5000)
    win_rate = (sim_results > 0).sum() / 5000 * 100
    avg_profit = sim_results.mean() * 100

    # 헤더 섹션
    st.markdown(f"### {target_name} <span class='status-tag' style='background:{state_clr};'>{state}</span>", unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1:
        st.markdown(f'<div class="profit-card"><h1>{avg_profit:+.2f}%</h1><p>5,000회 시뮬레이션 기대수익</p></div>', unsafe_allow_html=True)
    with c2: st.metric("현재가", f"{curr_p:,.0f}{unit}"); st.metric("승률", f"{win_rate:.1f}%")
    with c3: st.metric("목표가(+12%)", f"{curr_p*1.12:,.0f}"); st.metric("손절가(-6%)", f"{curr_p*0.94:,.0f}")

    tab1, tab2, tab3, tab4 = st.tabs(["📉 분석 차트", "🧪 정밀 기술 온도계", "📰 실시간 뉴스/테마", "🚀 글로벌 테마 리스트"])

    with tab1: # 1페이지: 고정 분석 차트
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

    with tab2: # 2페이지: 정밀 온도계 및 분석
        cl1, cl2 = st.columns([1.2, 1])
        with cl1:
            # 투자 매수 온도계 (Gauge)
            fig_g = go.Figure(go.Indicator(
                mode = "gauge+number", value = win_rate, title = {'text': "AI 매수 온도 (승률 %)"},
                gauge = {
                    'axis': {'range': [0, 100]},
                    'bar': {'color': "#007AFF"},
                    'steps': [{'range': [0, 40], 'color': "#333"}, {'range': [40, 70], 'color': "#555"}, {'range': [70, 100], 'color': "#222"}],
                    'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 80}
                }
            ))
            fig_g.update_layout(height=400, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)'); st.plotly_chart(fig_g, use_container_width=True)
        with cl2:
            st.markdown(f"""<div class="info-card">
                <b>🔍 상세 기술 분석 보고서</b><br><br>
                - <b>추세 상태:</b> {state}<br>
                - <b>심리 강도(RSI):</b> {df['RSI'].iloc[-1]:.1f} ({"과열" if df['RSI'].iloc[-1]>70 else "침체" if df['RSI'].iloc[-1]<30 else "안정"})<br>
                - <b>변동성 지수:</b> {df['Vol_Score'].iloc[-1]:.2f}%<br>
                - <b>퀀트 점수:</b> {int(win_rate * 0.8 + (20 if "정배열" in state else 0))} / 100
            </div>""", unsafe_allow_html=True)

    with tab3: # 3페이지: 뉴스 및 급등 테마 URL
        c_news, c_theme = st.columns(2)
        with c_news:
            st.markdown("#### 📰 종목 실시간 뉴스")
            try:
                res_n = requests.get(f"https://search.naver.com/search.naver?where=news&query={target_name} 특징주", headers={'User-Agent': 'Mozilla/5.0'})
                soup = BeautifulSoup(res_n.text, 'html.parser')
                for art in soup.select('.news_area')[:6]:
                    st.markdown(f"📍 [{art.select_one('.news_tit').text}]({art.select_one('.news_tit')['href']})")
            except: st.write("뉴스 연동 중...")
        with c_theme:
            st.markdown("#### ⚡ 급등 테마 중요 사이트")
            st.markdown("- [네이버 증권 테마별 시세](https://finance.naver.com/sise/theme.naver)")
            st.markdown("- [한경 유레카 (종목진단)](https://eureca.hankyung.com/)")
            st.markdown("- [인베스팅닷컴 글로벌 뉴스](https://kr.investing.com/news/stock-market-news)")

    with tab4: # 4페이지: 확장된 글로벌 테마
        st.write("### 🚀 글로벌 핵심 테마 9대 섹터 (Next Gen)")
        themes = {
            "🤖 AI/반도체": ["NVDA", "ASML", "SK하이닉스", "TSM", "ARM"],
            "🛡️ K-방산/우주": ["한화에어로스페이스", "LIG넥스원", "KAI", "현대로템"],
            "💰 금융/지주": ["우리금융지주", "KB금융", "JPM", "GS", "MS"],
            "💊 바이오": ["알테오젠", "삼성바이오로직스", "LLY", "NVO"],
            "🔋 2차전지": ["TSLA", "LG에너지솔루션", "에코프로", "삼성SDI"],
            "🏗️ 원자력/에너지": ["CEG", "SMR", "한전산업", "두산에너빌리티"]
        }
        cols = st.columns(3)
        for i, (t_name, stocks) in enumerate(themes.items()):
            with cols[i % 3]:
                st.markdown(f'<div class="cate-title">{t_name}</div>', unsafe_allow_html=True)
                for s in stocks: st.markdown(f'<div class="recommend-box"><b>{s}</b></div>', unsafe_allow_html=True)

else:
    st.error("데이터 로드 실패: 티커 형식을 확인하세요. (예: 005930.KS)")
