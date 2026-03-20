import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. 설정 및 스타일 ---
st.set_page_config(layout="wide", page_title="v20.0 Quantum Alpha")
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #3e425b; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 데이터 수집 엔진 (안정화된 Scraper) ---
@st.cache_data(ttl=3600)
def get_naver_data(name):
    codes = {"현대자동차": "005380", "현대차": "005380", "삼성전자": "005930", "삼전": "005930", "SK하이닉스": "000660", "에코프로": "086520"}
    code = codes.get(name.strip())
    if not code: return None
    all_dfs = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        for p in range(1, 8): # 데이터 8페이지까지 확보 (신뢰도 최상)
            url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page={p}"
            res = requests.get(url, headers=headers)
            df_list = pd.read_html(res.text)
            if df_list: all_dfs.append(df_list[0].dropna())
        df = pd.concat(all_dfs)
        df.columns = ['Date', 'Close', 'Diff', 'Open', 'High', 'Low', 'Volume']
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.set_index('Date').sort_index()
        for col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    except: return None

# --- 3. AI 퀀트 분석 엔진 ---
def analyze_pro(df):
    # POC (매물대 중심)
    price_bins = pd.cut(df['Close'], bins=30)
    poc_range = df.groupby(price_bins, observed=True)['Volume'].sum().idxmax()
    poc_price = (poc_range.left + poc_range.right) / 2
    
    # 삼각수렴 빗각 (최근 25일)
    x = np.arange(len(df))
    h_fit = np.polyfit(x[-25:], df['High'].iloc[-25:], 1)
    l_fit = np.polyfit(x[-25:], df['Low'].iloc[-25:], 1)
    
    # 지표 계산
    delta = df['Close'].diff()
    up = delta.clip(lower=0).rolling(14).mean()
    down = -1 * delta.clip(upper=0).rolling(14).mean()
    rsi = 100 - (100 / (1 + (up / down)))
    
    curr_p = df['Close'].iloc[-1]
    curr_rsi = rsi.iloc[-1]
    
    # AI 스코어 (0-100)
    score = 50
    if curr_rsi < 30: score += 25
    if curr_rsi > 70: score -= 20
    if curr_p > poc_price: score += 15
    else: score -= 10
    
    # 신호 생성
    buy_sigs = rsi[rsi < 35].tail(10).index
    sell_sigs = rsi[rsi > 65].tail(10).index

    return {
        'poc': poc_price, 'h_line': h_fit[0] * x[-25:] + h_fit[1], 'l_line': l_fit[0] * x[-25:] + l_fit[1],
        'rsi': curr_rsi, 'curr_p': curr_p, 'score': min(max(score, 0), 100),
        'buy_sigs': buy_sigs, 'sell_sigs': sell_sigs,
        'target': curr_p * 1.15, 'stop': curr_p * 0.93, 'buy_zone': poc_price * 1.02
    }

# --- 4. 메인 UI ---
st.title("🏛️ v20.0 Quantum Alpha Pro")

with st.sidebar:
    st.header("⚙️ 분석 설정")
    stock_input = st.selectbox("종목 선택", ["현대자동차", "삼성전자", "SK하이닉스", "에코프로"])
    st.write("---")
    st.write("AI 엔진: Lyria 3 Hybrid")
    st.write("데이터: Naver Realtime")

df = get_naver_data(stock_input)

if df is not None and len(df) > 30:
    res = analyze_pro(df)
    
    tab1, tab2 = st.tabs(["📈 1P: 통합 대시보드", "🤖 2P: AI 정밀 진단"])

    # --- 1페이지: 통합 대시보드 (차트 + 핵심수치) ---
    with tab1:
        st.subheader(f"📊 {stock_input} All-in-One 리포트")
        
        # 상단 메트릭스
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("현재가", f"{res['curr_p']:,.0f}원", f"{df['Diff'].iloc[-1]:+,.0f}")
        m2.metric("AI 온도", f"{res['score']:.1f}°C", "공포/탐욕")
        m3.metric("RSI 수치", f"{res['rsi']:.1f}", "상대강도")
        m4.metric("POC 괴리", f"{((res['curr_p']-res['poc'])/res['poc']*100):+.2f}%", "매물대비")

        # 차트 영역
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
        
        # POC & 수렴선
        fig.add_hline(y=res['poc'], line_dash="solid", line_color="gold", line_width=2, row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index[-25:], y=res['h_line'], line=dict(color='cyan', dash='dash'), name='저항선'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index[-25:], y=res['l_line'], line=dict(color='magenta', dash='dash'), name='지지선'), row=1, col=1)
        
        # BUY/SELL 화살표
        for d in res['buy_sigs']:
            fig.add_annotation(x=d, y=df.loc[d, 'Low'], text="🚀BUY", showarrow=False, yshift=-20, font=dict(color="#00ff00", size=12), row=1, col=1)
        for d in res['sell_sigs']:
            fig.add_annotation(x=d, y=df.loc[d, 'High'], text="⚠️SELL", showarrow=False, yshift=20, font=dict(color="#ff4b4b", size=12), row=1, col=1)

        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color='#4e5d6c'), row=2, col=1)
        fig.update_layout(height=650, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)

    # --- 2페이지: AI 정밀 진단 (수치 및 금액 보강) ---
    with tab2:
        st.subheader("🤖 AI 정밀 타점 및 손익 시뮬레이션")
        
        c1, c2 = st.columns([1, 1.2])
        with c1:
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number", value=res['score'],
                gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "#f63366"},
                       'steps': [{'range': [0, 30], 'color': "#1c83e1"}, {'range': [70, 100], 'color': "#ff4b4b"}]},
                title={'text': "AI 신뢰 지수"}
            ))
            fig_gauge.update_layout(height=400, template='plotly_dark')
            st.plotly_chart(fig_gauge, use_container_width=True)

        with c2:
            st.write("### 🎯 AI 산출 정밀 타점")
            st.success(f"**🟢 추천 진입가 (Buy Zone):** {res['buy_zone']:,.0f}원 이하")
            st.info(f"**🎯 AI 목표가 (Take Profit):** {res['target']:,.0f}원 (예상 수익 +15%)")
            st.error(f"**⚠️ AI 손절가 (Stop Loss):** {res['stop']:,.0f}원 (최대 허용 -7%)")
            
            st.write("---")
            st.write("### 💸 1,000만원 투자 시 시뮬레이션")
            col_p1, col_p2 = st.columns(2)
            col_p1.metric("목표 도달 시 이익", f"+1,500,000원", "Target")
            col_p2.metric("손절 발생 시 손실", f"-700,000원", "Risk", delta_color="inverse")

        st.divider()
        st.write("### 📋 AI 전략 체크리스트")
        col_ch1, col_ch2, col_ch3 = st.columns(3)
        with col_ch1:
            st.checkbox("POC 매물대 지지 확인", value=res['curr_p'] > res['poc'])
            st.checkbox("RSI 과매수권 이탈 여부", value=res['rsi'] < 60)
        with col_ch2:
            st.checkbox("삼각수렴 상단 돌파 시도", value=res['h_line'][-1] < res['curr_p'])
            st.checkbox("거래량 급증 징후 포착", value=df['Volume'].iloc[-1] > df['Volume'].mean())
        with col_ch3:
            st.write(f"**현재 전략:** {'적극 매수' if res['score'] < 35 else '분할 매도' if res['score'] > 70 else '관망/보유'}")

else:
    st.info("왼쪽 사이드바에서 종목을 선택하고 분석을 실행하세요!")
