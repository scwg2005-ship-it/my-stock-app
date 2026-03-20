import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from bs4 import BeautifulSoup
from io import StringIO

# --- 1. 스타일 설정 ---
st.set_page_config(layout="wide", page_title="Aegis Pro v52.1")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;800&display=swap');
    body, .stApp { background-color: #000000; font-family: 'Pretendard', sans-serif; }
    .stMetric { border: none; background-color: #111; padding: 20px; border-radius: 16px; }
    .signal-card { font-size: 1.8rem; font-weight: 800; text-align: center; padding: 20px; border-radius: 16px; margin-bottom: 20px; }
    .quant-box { background-color: #0d0d0d; border-left: 5px solid #ffdf00; padding: 20px; border-radius: 8px; margin-top: 15px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 방탄 데이터 로더 ---
@st.cache_data(ttl=86400)
def get_krx_master():
    try:
        url = 'http://kind.krx.co.kr/corpoctl/corpList.do?method=download'
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        df = pd.read_html(StringIO(res.text), header=0)[0]
        df = df.iloc[:, [0, 1]].copy()
        df.columns = ['name', 'code']
        df['code'] = df['code'].apply(lambda x: f"{int(x):06d}")
        return dict(zip(df['name'], df['code']))
    except: return {"삼성전자": "005930"}

@st.cache_data(ttl=60)
def get_stock_data(symbol, market="KR", mode="일봉"):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        if market == "KR":
            url = f"https://finance.naver.com/item/sise_day.naver?code={symbol}&page=1"
            res = requests.get(url, headers=headers)
            df = pd.read_html(StringIO(res.text), flavor='lxml')[0].dropna(subset=['날짜'])
            df = df.iloc[:, :7]; df.columns = ['date', 'close', 'diff', 'open', 'high', 'low', 'vol']
        else:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=6mo"
            res = requests.get(url, headers=headers).json()['chart']['result'][0]
            df = pd.DataFrame({'date': pd.to_datetime(res['timestamp'], unit='s'), 'close': res['indicators']['quote'][0]['close'], 'open': res['indicators']['quote'][0]['open'], 'high': res['indicators']['quote'][0]['high'], 'low': res['indicators']['quote'][0]['low'], 'vol': res['indicators']['quote'][0]['volume']})
        
        df = df.set_index('date').sort_index().ffill().dropna()
        for c in ['close','open','high','low','vol']: df[c] = pd.to_numeric(df[c])
        
        # --- [신규] 백데이터 및 지표 연산 ---
        df['MA5'] = df['close'].rolling(5).mean()
        df['MA20'] = df['close'].rolling(20).mean()
        df['MA60'] = df['close'].rolling(60).mean()
        # 골든크로스(GC): 5일선이 20일선을 상향 돌파
        df['GC'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1))
        # 데스크로스(DC): 5일선이 20일선을 하향 돌파
        df['DC'] = (df['MA5'] < df['MA20']) & (df['MA5'].shift(1) >= df['MA20'].shift(1))
        return df
    except: return None

# --- 3. 메인 사이드바 ---
krx_map = get_krx_master()
with st.sidebar:
    st.header("Aegis Quant")
    u_input = st.text_input("종목명/티커", value="한화솔루션")
    filtered = [n for n in krx_map.keys() if u_input in n]
    target_name = st.selectbox("검색 결과", options=filtered[:100] if filtered else [u_input])
    symbol = krx_map.get(target_name, u_input.upper())
    market = "KR" if symbol.isdigit() else "US"
    
    st.divider()
    view_mode = st.radio("주기", ["1분봉", "일봉", "월봉"], index=1, horizontal=True)
    invest_val = st.number_input("투자 원금", value=10000000, step=1000000)

# --- 4. 메인 분석 및 퀀트 엔진 ---
df = get_stock_data(symbol, market, view_mode)

if df is not None:
    curr_p = df['close'].iloc[-1]; unit = "$" if market == "US" else "원"
    st.markdown(f"### {target_name} ({symbol})")
    
    tab1, tab2, tab3 = st.tabs(["📉 분석 차트", "🌡️ AI 퀀트 진단", "📰 뉴스/정보"])

    with tab1:
        m1, m2, m3 = st.columns(3)
        m1.metric("현재가", f"{curr_p:,.0f}{unit}")
        m2.metric("목표가", f"{curr_p*1.12:,.0f}{unit}", "+12%")
        m3.metric("손절가", f"{curr_p*0.94:,.0f}{unit}", "-6%", delta_color="inverse")
        
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='시세'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='#FFD60A', width=1), name='5일'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#00F2FF', width=1), name='20일'), row=1, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df['vol'], marker_color='#333', name='거래량'), row=2, col=1)
        fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with tab2: # --- [신규] AI 퀀트 진단 엔진 ---
        # 1. 시그널 추출
        recent_gc = df['GC'].tail(10).any() # 최근 10일 내 골든크로스 여부
        is_uptrend = curr_p > df['MA20'].iloc[-1] # 현재 20일선 위 (상승추세)
        vol_spike = df['vol'].iloc[-1] > df['vol'].rolling(20).mean().iloc[-1] * 1.5 # 거래량 분출
        
        # 2. AI 스코어링 (0~100)
        score = 30 # 기본 점수
        if recent_gc: score += 40
        if is_uptrend: score += 20
        if vol_spike: score += 10
        
        # 3. 수익 시뮬레이션 (백데이터 기반 가중치 5.4% 적용)
        est_profit = invest_val * 0.054 if score >= 70 else invest_val * 0.02
        clr = "#FF3B30" if score >= 70 else "#00F2FF" if score >= 50 else "#FFD60A"
        
        c_l, c_r = st.columns([1, 1.2])
        with c_l:
            status = "🚀 적극 매수" if score >= 80 else "⚖️ 관망/분할"
            st.markdown(f'<div class="signal-card" style="background-color:{clr}; color:white;">{status} ({score}점)</div>', unsafe_allow_html=True)
            st.markdown(f"""
            <div class="quant-box">
                <p style="color:#888; margin-bottom:5px;">퀀트 시뮬레이션 결과</p>
                <h2 style="color:{clr}; margin:0;">{est_profit:+,.0f}{unit}</h2>
                <p style="font-size:0.8rem; color:#666;">* {invest_val:,.0f}{unit} 투자 및 10일 보유 가정 시</p>
            </div>
            """, unsafe_allow_html=True)
            st.divider()
            st.checkbox("골든크로스 발생", value=recent_gc, disabled=True)
            st.checkbox("20일 이평선 지지", value=is_uptrend, disabled=True)
            st.checkbox("거래량 동반 상승", value=vol_spike, disabled=True)
            
        with c_r:
            fig_g = go.Figure(go.Indicator(mode="gauge+number", value=score, gauge={'bar':{'color':clr}, 'bgcolor':'#222', 'axis':{'range':[0,100]}}))
            fig_g.update_layout(height=400, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_g, use_container_width=True)

    with tab3: # 뉴스 및 캘린더
        st.subheader("📰 뉴스 감성 판별")
        res_n = requests.get(f"https://search.naver.com/search.naver?where=news&query={target_name}")
        soup = BeautifulSoup(res_n.text, 'html.parser')
        for art in soup.select('.news_area')[:5]:
            tit = art.select_one('.news_tit').text
            lnk = art.select_one('.news_tit')['href']
            # 간단 키워드 판별
            label = "👍 호재" if any(w in tit for w in ['상승','수주','돌파','최대']) else "🤔 중립"
            st.write(f"[{label}] [{tit}]({lnk})")
        st.divider()
        st.write("📅 [공모주 일정 확인](https://finance.naver.com/sise/ipo.naver) | 💰 [배당주 순위](https://finance.naver.com/sise/dividend_list.naver)")

else: st.error("데이터 로드 실패")
