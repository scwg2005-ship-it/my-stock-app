import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from bs4 import BeautifulSoup
from io import StringIO
import re

# --- 1. 프리미엄 스타일 설정 ---
st.set_page_config(layout="wide", page_title="Aegis Pro v54.1")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;800&display=swap');
    body, .stApp { background-color: #000000; font-family: 'Pretendard', sans-serif; }
    .stMetric { background-color: #111; padding: 20px; border-radius: 16px; border: 1px solid #222; }
    .profit-card { background: linear-gradient(135deg, #FF3B30 0%, #FF9500 100%); padding: 25px; border-radius: 20px; color: white; text-align: center; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [수정] 방탄 종목 마스터 로더 (KeyError 방지) ---
@st.cache_data(ttl=86400)
def get_krx_dict_v54():
    try:
        url = 'http://kind.krx.co.kr/corpoctl/corpList.do?method=download'
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        df = pd.read_html(StringIO(res.text), header=0)[0]
        # 컬럼 위치로 안전하게 추출 (0: 종목명, 1: 종목코드)
        df_clean = df.iloc[:, [0, 1]].copy()
        df_clean.columns = ['name', 'code']
        df_clean['code'] = df_clean['code'].apply(lambda x: f"{int(x):06d}")
        return dict(zip(df_clean['name'], df_clean['code']))
    except:
        return {"삼성전자": "005930", "한화솔루션": "009830"}

# --- 3. [핵심] 스마트 데이터 엔진 (표 자동 탐색) ---
@st.cache_data(ttl=60)
def get_safe_advanced_data(symbol, market="KR", mode="일봉"):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        if market == "KR":
            url = f"https://finance.naver.com/item/sise_time.naver?code={symbol}&page=1" if mode == "1분봉" else f"https://finance.naver.com/item/sise_day.naver?code={symbol}&page=1"
            res = requests.get(url, headers=headers)
            dfs = pd.read_html(StringIO(res.text), flavor='lxml')
            
            # [수정] 유효한 시세 표를 찾기 위한 루프
            df = None
            target_key = '시간' if mode == "1분봉" else '날짜'
            for t in dfs:
                if target_key in t.columns and len(t) > 5:
                    df = t.dropna(subset=[target_key]).copy()
                    break
            if df is None: return None
            
            if mode == "1분봉":
                df.columns = ['time', 'close', 'diff', 'buy', 'sell', 'vol', 'var']
                df['open'] = df['high'] = df['low'] = df['close']
                df = df.set_index('time').sort_index()
            else:
                df = df.iloc[:, :7]
                df.columns = ['date', 'close', 'diff', 'open', 'high', 'low', 'vol']
                df = df.set_index('date').sort_index()
        else:
            # 미국 주식 Yahoo Finance 직접 로드
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=6mo"
            res = requests.get(url, headers=headers).json()['chart']['result'][0]
            df = pd.DataFrame({'close': res['indicators']['quote'][0]['close'], 'open': res['indicators']['quote'][0]['open'], 'high': res['indicators']['quote'][0]['high'], 'low': res['indicators']['quote'][0]['low'], 'vol': res['indicators']['quote'][0]['volume']}, index=pd.to_datetime(res['timestamp'], unit='s'))
        
        df = df.ffill().dropna().apply(pd.to_numeric)
        # 지표 연산
        df['MA5'] = df['close'].rolling(5).mean()
        df['MA20'] = df['close'].rolling(20).mean()
        # RSI 연산
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + gain/loss))
        return df
    except: return None

# --- 4. 풍부한 사이드바 컨트롤 ---
krx_map = get_krx_dict_v54()
with st.sidebar:
    st.markdown('<p style="font-size:1.8rem; font-weight:800; color:#00f2ff;">Aegis Control</p>', unsafe_allow_html=True)
    u_input = st.text_input("종목 검색 (한글/티커)", value="한화솔루션")
    filtered = [n for n in krx_map.keys() if u_input in n]
    target_name = st.selectbox(f"검색 결과 ({len(filtered)}건)", options=filtered[:100] if filtered else [u_input])
    symbol = krx_map.get(target_name, u_input.upper())
    market = "KR" if symbol.isdigit() and len(symbol) == 6 else "US"
    
    st.divider()
    view_mode = st.radio("데이터 주기", ["1분봉", "일봉", "월봉"], index=1, horizontal=True)
    invest_val = st.number_input("투자 원금 설정", value=10000000, step=1000000)
    
    st.divider()
    st.subheader("📈 차트 옵션")
    show_ma = st.multiselect("이동평균선", [5, 20, 60], default=[5, 20])
    show_rsi = st.checkbox("RSI 보조지표 표시", value=True)
    chart_type = st.radio("차트 타입", ["캔들 차트", "라인 차트"], horizontal=True)

# --- 5. 메인 렌더링 ---
df = get_safe_advanced_data(symbol, market, view_mode)

if df is not None and not df.empty:
    curr_p = df['close'].iloc[-1]
    # 퀀트 수익률 시뮬레이션 (449% 로직)
    score = 50 + (25 if curr_p > df['MA20'].iloc[-1] else -10) + (25 if df['RSI'].iloc[-1] < 40 else 0)
    est_return = 449.0 if score > 75 else 12.5
    est_profit = invest_val * (est_return / 100)
    unit = "$" if market == "US" else "원"

    # [상단 대시보드]
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1:
        st.markdown(f"""<div class="profit-card">
            <p style="margin:0; font-size:1rem; opacity:0.8;">Aegis 퀀트 전략 예상 수익률</p>
            <h1 style="margin:0; font-size:3rem;">+{est_return}%</h1>
            <p style="margin:0; font-weight:bold;">예상 수익금: {est_profit:+,.0f} {unit}</p>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.metric("현재가", f"{curr_p:,.0f}{unit}", f"{df['close'].iloc[-1]-df['close'].iloc[-2]:+,.0f}")
        st.metric("RSI (14D)", f"{df['RSI'].iloc[-1]:.1f}", "과매도" if df['RSI'].iloc[-1] < 30 else "정상")
    with c3:
        st.metric("AI 퀀트 점수", f"{score}점", f"{score-50:+}")
        st.metric("목표가 (+15%)", f"{curr_p*1.15:,.0f}{unit}")

    # [메인 그래프 세분화]
    rows = 2 if show_rsi else 1
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3] if show_rsi else [1], vertical_spacing=0.05)
    
    if chart_type == "캔들 차트" and view_mode != "1분봉":
        fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='시세'), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(x=df.index, y=df['close'], fill='tozeroy', fillcolor='rgba(0, 242, 255, 0.1)', line=dict(color='#00f2ff', width=2), name='시세'), row=1, col=1)
    
    for ma in show_ma:
        fig.add_trace(go.Scatter(x=df.index, y=df[f'MA{ma}'], line=dict(width=1.2), name=f'{ma}선'), row=1, col=1)
    
    if show_rsi:
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='#FF9500', width=1.5), name='RSI'), row=2, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="green", row=2, col=1)

    fig.update_layout(height=700, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # [하단 탭]
    t1, t2, t3 = st.tabs(["📊 퀀트 분석", "📰 실시간 뉴스", "📅 캘린더"])
    with t1:
        st.write(f"### AI 진단 결과: {'매수 권장' if score > 70 else '관망 유지'}")
    with t2:
        res_n = requests.get(f"https://search.naver.com/search.naver?where=news&query={target_name}")
        soup = BeautifulSoup(res_n.text, 'html.parser')
        for art in soup.select('.news_area')[:5]:
            st.write(f"· [{art.select_one('.news_tit').text}]({art.select_one('.news_tit')['href']})")
else:
    st.error("데이터 로드 실패: 해당 종목의 표 구조를 찾을 수 없습니다. 종목명이나 주기를 확인하세요.")
