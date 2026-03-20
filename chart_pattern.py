import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO
from bs4 import BeautifulSoup

# --- 1. [디자인] 증권사 VIP 전용 터미널 UI ---
st.set_page_config(layout="wide", page_title="Aegis Oracle v80.0")
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

# --- 2. [강력 수정] 위치 기반 데이터 강제 추출 엔진 ---
@st.cache_data(ttl=3600)
def find_ticker_ultimate(query):
    try:
        url_krx = 'http://kind.krx.co.kr/corpoctl/corpList.do?method=download'
        res = requests.get(url_krx, timeout=5)
        df_krx = pd.read_html(StringIO(res.text), header=0)[0]
        match = df_krx[df_krx['회사명'].str.contains(query, na=False, case=False)]
        if not match.empty:
            return f"{match.iloc[0]['종목코드']:06d}.KS", match.iloc[0]['회사명']
    except: pass
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}&quotesCount=1"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).json()
        if res.get('quotes'): return res['quotes'][0]['symbol'], res['quotes'][0].get('shortname', query)
    except: pass
    return f"{query.upper()}.KS", query

@st.cache_data(ttl=60)
def get_oracle_data(ticker, mode="일봉"):
    interval_map = {"1분봉": "1m", "일봉": "1d", "월봉": "1mo"}
    period_map = {"1분봉": "1d", "일봉": "1y", "월봉": "max"}
    try:
        # 1. 원본 데이터 다운로드
        data = yf.download(ticker, period=period_map[mode], interval=interval_map[mode], progress=False)
        if data.empty and ".KS" in ticker:
            data = yf.download(ticker.replace(".KS", ".KQ"), period=period_map[mode], interval=interval_map[mode], progress=False)
        if data.empty: return None

        # 2. [필살기] 모든 인덱스와 컬럼 구조를 강제로 평탄화
        df = data.copy()
        # MultiIndex 해제
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        # 컬럼 이름 재설정 (yfinance가 어떤 이름을 주든 위치로 고정)
        # 보통 순서는 Open, High, Low, Close, Adj Close, Volume 입니다.
        temp_cols = [c.capitalize() for c in df.columns]
        df.columns = temp_cols

        # 3. 데이터가 여전히 MultiIndex 문제로 꼬여있을 경우를 대비해 위치 기반으로 재정의
        # 이 부분이 이번 버전의 핵심입니다.
        valid_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        final_df = pd.DataFrame(index=df.index)
        for col in valid_cols:
            if col in df.columns:
                # 동일한 이름이 여러개인 경우 첫 번째 것만 가져옴
                col_data = df[col]
                if isinstance(col_data, pd.DataFrame):
                    final_df[col] = col_data.iloc[:, 0]
                else:
                    final_df[col] = col_data
        
        if final_df.empty or 'Close' not in final_df.columns: return None

        # 4. 보조지표 계산
        for ma in [5, 20, 60, 120]:
            final_df[f'MA{ma}'] = final_df['Close'].rolling(ma).mean()
        
        delta = final_df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        final_df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
        final_df['High_Max'] = final_df['High'].rolling(20).max()
        final_df['Low_Min'] = final_df['Low'].rolling(20).min()
        
        return final_df
    except:
        return None

# --- 3. [사이드바] 제어 센터 ---
with st.sidebar:
    st.markdown('<p style="font-size:1.8rem; font-weight:800; color:#00f2ff;">Oracle Control</p>', unsafe_allow_html=True)
    u_input = st.text_input("종목명 입력 (예: 삼성전자, 우리금융지주)", value="삼성전자")
    ticker, target_name = find_ticker_ultimate(u_input)
    st.success(f"매칭: **{target_name} ({ticker})**")
    
    st.divider()
    view_mode = st.radio("분석 주기", ["1분봉", "일봉", "월봉"], index=1, horizontal=True)
    invest_val = st.number_input("투자 원금 설정", value=10000000)
    
    st.divider()
    chart_style = st.radio("그래프 형태", ["전문가 캔들", "심플 라인"], horizontal=True)
    show_ma = st.multiselect("이평선 표시", [5, 20, 60, 120], default=[5, 20, 60, 120])
    show_wave = st.checkbox("파동/빗각/수렴 레이어", value=True)
    show_rsi = st.checkbox("RSI/거래량 표시", value=True)

# --- 4. [메인] 분석 실행 ---
df = get_oracle_data(ticker, view_mode)

if df is not None:
    curr_p = float(df['Close'].iloc[-1])
    unit = "$" if ".KS" not in ticker and ".KQ" not in ticker else "원"
    
    # 시뮬레이션
    returns = df['Close'].pct_change().dropna()
    sim_results = np.random.normal(returns.mean(), returns.std(), 5000)
    win_rate = (sim_results > 0).sum() / 5000 * 100
    avg_sim_profit_pct = sim_results.mean() * 100
    score = 50 + (25 if curr_p > float(df['MA20'].iloc[-1]) else -10)

    st.markdown(f"### {target_name} ({ticker})")
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1:
        st.markdown(f"""<div class="profit-card">
            <p style="margin:0; opacity:0.8;">5,000회 시뮬레이션 기대 수익</p>
            <h1 style="margin:0; font-size:3.2rem;">{avg_sim_profit_pct:+.2f}%</h1>
            <p style="margin:0; font-weight:bold;">수익금: {invest_val * (avg_sim_profit_pct/100):+,.0f} {unit}</p>
        </div>""", unsafe_allow_html=True)
    with c2: st.metric("현재가", f"{curr_p:,.0f}{unit}"); st.metric("AI 점수", f"{score}점", f"승률 {win_rate:.1f}%")
    with c3: st.metric("목표가(+12%)", f"{curr_p*1.12:,.0f}{unit}"); st.metric("손절가(-6%)", f"{curr_p*0.94:,.0f}{unit}")

    tab1, tab2, tab3, tab4 = st.tabs(["📉 시세 분석", "🧪 AI 정밀 진단", "📰 실시간 뉴스", "🚀 글로벌 테마 랭킹"])

    with tab1:
        st.markdown(f"""<div class="ma-legend">
            <span style="color:#FFD60A;">● 5일(황)</span> <span style="color:#FF37AF;">● 20일(적)</span> 
            <span style="color:#00F2FF;">● 60일(청)</span> <span style="color:#FFFFFF;">● 120일(백)</span>
        </div>""", unsafe_allow_html=True)
        rows = 2 if show_rsi else 1
        fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2] if show_rsi else [1], vertical_spacing=0.03)
        if chart_style == "전문가 캔들" and view_mode != "1분봉":
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='시세'), row=1, col=1)
        else:
            fig.add_trace(go.Scatter(x=df.index, y=df['Close'], line=dict(color='#00f2ff', width=2), fill='tozeroy', name='시세'), row=1, col=1)
        ma_colors = {5: '#FFD60A', 20: '#FF37AF', 60: '#00F2FF', 120: '#FFFFFF'}
        for ma in show_ma: 
            fig.add_trace(go.Scatter(x=df.index, y=df[f'MA{ma}'], line=dict(color=ma_colors[ma], width=1.3), name=f'{ma}선'), row=1, col=1)
        if show_wave:
            fig.add_trace(go.Scatter(x=df.index, y=df['High_Max'], line=dict(color='#888', dash='dot'), name='저항'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['Low_Min'], line=dict(color='#888', dash='dot'), name='지지'), row=1, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color='#333', name='거래량'), row=rows, col=1)
        fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with tab2: # 2P: AI 진단
        cl1, cl2 = st.columns([1.2, 1])
        with cl1:
            fig_g = go.Figure(go.Indicator(mode="gauge+number", value=win_rate, title={'text': "AI 매수 승률 (%)"}, gauge={'bar': {'color': "#007AFF" if win_rate > 50 else "#FF3B30"}, 'bgcolor': '#222'}))
            fig_g.update_layout(height=400, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)'); st.plotly_chart(fig_g, use_container_width=True)
        with cl2: st.markdown(f"""<div class="info-card"><b>🎯 실시간 타점 가이드</b><br><div style="border-left:5px solid #FF3B30; padding-left:15px; margin-top:10px;">적극 매수가: <b>{curr_p*0.98:,.0f}{unit}</b><br>목표가: <b>{curr_p*1.12:,.0f}{unit}</b><br>손절가: <b>{curr_p*0.94:,.0f}{unit}</b></div><br>분석 결과 현재 승률 <b>{win_rate:.1f}%</b> 구간입니다.</div>""", unsafe_allow_html=True)

    with tab3: # 뉴스
        try:
            res_n = requests.get(f"https://search.naver.com/search.naver?where=news&query={target_name} 특징주", headers={'User-Agent': 'Mozilla/5.0'})
            soup = BeautifulSoup(res_n.text, 'html.parser')
            for art in soup.select('.news_area')[:8]: st.markdown(f"· [{art.select_one('.news_tit').text}]({art.select_one('.news_tit')['href']})")
        except: st.write("뉴스 로드 실패")

    with tab4: # 카테고리
        st.write("### 🚀 글로벌 테마 카
