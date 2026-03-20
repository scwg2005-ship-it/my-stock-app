import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from bs4 import BeautifulSoup
from io import StringIO
import re

# --- 1. 스타일 설정 ---
st.set_page_config(layout="wide", page_title="Aegis Pro v53.1")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;800&display=swap');
    body, .stApp { background-color: #000000; font-family: 'Pretendard', sans-serif; }
    .stMetric { border: none; background-color: #111; padding: 20px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
    .main-title { font-size: 2.2rem; font-weight: 800; color: #fff; text-align: left; margin-bottom: 25px; }
    .signal-card { font-size: 1.8rem; font-weight: 800; text-align: center; padding: 20px; border-radius: 16px; margin-bottom: 20px; }
    .info-card { background-color: #161616; padding: 18px; border-radius: 14px; margin-bottom: 12px; border: 1px solid #222; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 방탄 종목 마스터 로더 ---
@st.cache_data(ttl=86400)
def get_krx_master_v53_1():
    try:
        url = 'http://kind.krx.co.kr/corpoctl/corpList.do?method=download'
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        df = pd.read_html(StringIO(res.text), header=0)[0]
        df_clean = df.iloc[:, [0, 1]].copy()
        df_clean.columns = ['name', 'code']
        df_clean['code'] = df_clean['code'].apply(lambda x: f"{int(x):06d}")
        return dict(zip(df_clean['name'], df_clean['code']))
    except:
        return {"삼성전자": "005930", "한화솔루션": "009830", "우리금융지주": "316140"}

# --- 3. [핵심수정] 주기별 데이터 분리 로더 ---
@st.cache_data(ttl=60)
def get_time_separated_data(symbol, market="KR", mode="일봉"):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        if market == "KR":
            # [주소 분리] 모드에 따라 네이버 금융 소스가 완전히 달라짐
            if mode == "1분봉":
                url = f"https://finance.naver.com/item/sise_time.naver?code={symbol}&page=1"
            else:
                url = f"https://finance.naver.com/item/sise_day.naver?code={symbol}&page=1"
            
            res = requests.get(url, headers=headers)
            dfs = pd.read_html(StringIO(res.text), flavor='lxml')
            
            # 유효한 표 찾기
            df = None
            target_key = '시간' if mode == "1분봉" else '날짜'
            for t in dfs:
                if target_key in t.columns and len(t) > 5:
                    df = t.dropna(subset=[target_key]).copy()
                    break
            
            if df is None: return None
            
            if mode == "1분봉":
                # 분봉 데이터 구조 (시간, 종가, 전일비, 매수, 매도, 거래량)
                df.columns = ['time', 'close', 'diff', 'buy', 'sell', 'vol', 'var']
                # 분봉은 시가/고가/저가가 없으므로 종가로 대체하여 선형 그래프 구성
                df['open'] = df['high'] = df['low'] = df['close']
                df = df.set_index('time').sort_index()
            else:
                # 일봉/월봉 데이터 구조 (날짜, 종가, 전일비, 시가, 고가, 저가, 거래량)
                df = df.iloc[:, :7]
                df.columns = ['date', 'close', 'diff', 'open', 'high', 'low', 'vol']
                df['date'] = pd.to_datetime(df['date'])
                df = df.set_index('date').sort_index()
        else:
            # 미국 주식 Yahoo Finance (모드별 간격 조정)
            intervals = {"1분봉": "1m", "일봉": "1d", "월봉": "1mo"}
            ranges = {"1분봉": "1d", "일봉": "6mo", "월봉": "max"}
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={intervals[mode]}&range={ranges[mode]}"
            res = requests.get(url, headers=headers).json()['chart']['result'][0]
            df = pd.DataFrame({
                'date': pd.to_datetime(res['timestamp'], unit='s'),
                'close': res['indicators']['quote'][0]['close'],
                'open': res['indicators']['quote'][0]['open'],
                'high': res['indicators']['quote'][0]['high'],
                'low': res['indicators']['quote'][0]['low'],
                'vol': res['indicators']['quote'][0]['volume']
            }).set_index('date').sort_index()
        
        df = df.ffill().dropna()
        for c in ['close','open','high','low','vol']: df[c] = pd.to_numeric(df[c])
        df['MA5'] = df['close'].rolling(5).mean()
        df['MA20'] = df['close'].rolling(20).mean()
        df['GC'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1))
        return df
    except: return None

# --- 4. 메인 UI ---
krx_map = get_krx_master_v53_1()
with st.sidebar:
    st.markdown('<p style="font-size:1.5rem; font-weight:800; color:#00f2ff;">Aegis Ultimate</p>', unsafe_allow_html=True)
    u_input = st.text_input("종목명/티커 입력", value="삼성전자")
    filtered = [n for n in krx_map.keys() if u_input in n]
    target_name = st.selectbox(f"검색 결과 ({len(filtered)}건)", options=filtered[:100] if filtered else [u_input])
    symbol = krx_map.get(target_name, u_input.upper())
    market = "KR" if symbol.isdigit() and len(symbol) == 6 else "US"
    
    st.divider()
    # [수정] 라디오 버튼 선택 시 데이터 리로드 강제
    view_mode = st.radio("차트 주기 선택", ["1분봉", "일봉", "월봉"], index=1, horizontal=True)
    invest_val = st.number_input("투자 원금 설정", value=10000000)

df = get_time_separated_data(symbol, market, view_mode)

if df is not None and not df.empty:
    curr_p = df['close'].iloc[-1]; unit = "$" if market == "US" else "원"
    st.markdown(f'<p class="main-title">{target_name} <span style="font-size:1rem; color:#888;">{symbol} / {view_mode}</span></p>', unsafe_allow_html=True)
    
    t1, t2, t3 = st.tabs(["📈 시세 차트", "🌡️ AI 퀀트 진단", "📰 실시간 뉴스"])

    with t1:
        # 상단 가이드
        m1, m2, m3 = st.columns(3)
        m1.metric("현재가", f"{curr_p:,.0f}{unit}")
        m2.metric("목표가", f"{curr_p*1.12:,.0f}{unit}")
        m3.metric("손절가", f"{curr_p*0.94:,.0f}{unit}", delta_color="inverse")
        
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.03)
        
        # [수정] 1분봉일 때는 라인 차트로, 일봉/월봉은 캔들로 시각화 최적화
        if view_mode == "1분봉":
            fig.add_trace(go.Scatter(x=df.index, y=df['close'], line=dict(color='#00f2ff', width=2), fill='tozeroy', fillcolor='rgba(0, 242, 255, 0.1)', name='시세'), row=1, col=1)
        else:
            fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'], increasing_line_color='#FF3B30', decreasing_line_color='#007AFF', name='캔들'), row=1, col=1)
        
        fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='#FFD60A', width=1), name='5선'), row=1, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df['vol'], marker_color='#333', name='거래량'), row=2, col=1)
        fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False, showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with t2: # AI 퀀트 (오른쪽 배치)
        is_gc = df['GC'].tail(15).any()
        score = 45 + (35 if is_gc else 0) + (20 if curr_p > df['MA20'].iloc[-1] else 0)
        clr = "#FF3B30" if score >= 80 else "#00F2FF" if score >= 60 else "#FFD60A"
        c_l, c_r = st.columns([1, 1.2])
        with c_l:
            st.markdown(f'<div class="signal-card" style="background-color:{clr}; color:white;">AI 점수: {score}점</div>', unsafe_allow_html=True)
            st.write(f"#### 💰 {invest_val:,.0f}{unit} 투자 시 예상 수익: **{(invest_val*0.052):+,.0f}{unit}**")
        with c_r:
            fig_g = go.Figure(go.Indicator(mode="gauge+number", value=score, gauge={'bar':{'color':clr}, 'bgcolor':'#222'}))
            fig_g.update_layout(height=400, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_g, use_container_width=True)

    with t3: # 뉴스
        st.subheader("📰 실시간 주요 뉴스")
        res_n = requests.get(f"https://search.naver.com/search.naver?where=news&query={target_name}")
        soup = BeautifulSoup(res_n.text, 'html.parser')
        for art in soup.select('.news_area')[:6]:
            t, l = art.select_one('.news_tit').text, art.select_one('.news_tit')['href']
            st.markdown(f'<div class="info-card"><a href="{l}" target="_blank" style="color:white; text-decoration:none;">{t}</a></div>', unsafe_allow_html=True)
else:
    st.error("데이터 로드 실패. 주기를 변경하거나 종목명을 다시 확인하세요.")
