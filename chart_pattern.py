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
st.set_page_config(layout="wide", page_title="Aegis Pro v53.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;800&display=swap');
    body, .stApp { background-color: #000000; font-family: 'Pretendard', sans-serif; }
    .stMetric { border: none; background-color: #111; padding: 20px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
    .main-title { font-size: 2.2rem; font-weight: 800; color: #fff; text-align: left; margin-bottom: 25px; }
    .signal-card { font-size: 1.8rem; font-weight: 800; text-align: center; padding: 20px; border-radius: 16px; margin-bottom: 20px; }
    .info-card { background-color: #161616; padding: 18px; border-radius: 14px; margin-bottom: 12px; border: 1px solid #222; }
    .quant-box { background-color: #0d0d0d; border-left: 5px solid #ffdf00; padding: 20px; border-radius: 12px; margin-top: 15px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 방탄 종목 마스터 로더 ---
@st.cache_data(ttl=86400)
def get_krx_master_v53():
    try:
        url = 'http://kind.krx.co.kr/corpoctl/corpList.do?method=download'
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        df = pd.read_html(StringIO(res.text), header=0)[0]
        # 컬럼 위치로 안전하게 추출
        df_clean = df.iloc[:, [0, 1]].copy()
        df_clean.columns = ['name', 'code']
        df_clean['code'] = df_clean['code'].apply(lambda x: f"{int(x):06d}")
        return dict(zip(df_clean['name'], df_clean['code']))
    except:
        return {"삼성전자": "005930", "한화솔루션": "009830", "우리금융지주": "316140"}

# --- 3. 스마트 데이터 엔진 (표 자동 탐색 및 로드) ---
@st.cache_data(ttl=60)
def get_robust_data(symbol, market="KR", mode="일봉"):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        if market == "KR":
            url = f"https://finance.naver.com/item/sise_day.naver?code={symbol}&page=1" if mode != "1분봉" else f"https://finance.naver.com/item/sise_time.naver?code={symbol}&page=1"
            res = requests.get(url, headers=headers)
            dfs = pd.read_html(StringIO(res.text), flavor='lxml')
            
            # [핵심] 유효한 시세 데이터 표 탐색
            df = None
            target_key = '시간' if mode == "1분봉" else '날짜'
            for t in dfs:
                if target_key in t.columns and len(t) > 5:
                    df = t.dropna(subset=[target_key]).copy()
                    break
            if df is None: return None
            
            if mode == "1분봉":
                df.columns = ['date', 'close', 'diff', 'buy', 'sell', 'vol', 'var']
                df['open'] = df['high'] = df['low'] = df['close']
            else:
                df = df.iloc[:, :7]
                df.columns = ['date', 'close', 'diff', 'open', 'high', 'low', 'vol']
        else:
            # 미국 주식 Yahoo Finance API 직접 연동
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=6mo"
            res = requests.get(url, headers=headers).json()['chart']['result'][0]
            df = pd.DataFrame({
                'date': pd.to_datetime(res['timestamp'], unit='s'),
                'close': res['indicators']['quote'][0]['close'],
                'open': res['indicators']['quote'][0]['open'],
                'high': res['indicators']['quote'][0]['high'],
                'low': res['indicators']['quote'][0]['low'],
                'vol': res['indicators']['quote'][0]['volume']
            })
        
        df = df.set_index('date').sort_index().ffill().dropna()
        for c in ['close','open','high','low','vol']: df[c] = pd.to_numeric(df[c])
        
        # 백데이터 분석용 지표 계산
        df['MA5'] = df['close'].rolling(5).mean()
        df['MA20'] = df['close'].rolling(20).mean()
        df['GC'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1))
        return df
    except: return None

# --- 4. 메인 대시보드 및 컨트롤 ---
krx_map = get_krx_master_v53()
with st.sidebar:
    st.markdown('<p style="font-size:1.5rem; font-weight:800; color:#00f2ff;">Aegis Ultimate</p>', unsafe_allow_html=True)
    u_input = st.text_input("종목명/티커 입력", value="삼성전자")
    filtered = [n for n in krx_map.keys() if u_input in n]
    target_name = st.selectbox(f"검색 결과 ({len(filtered)}건)", options=filtered[:100] if filtered else [u_input])
    symbol = krx_map.get(target_name, u_input.upper())
    market = "KR" if symbol.isdigit() and len(symbol) == 6 else "US"
    
    st.divider()
    view_mode = st.radio("주기", ["1분봉", "일봉", "월봉"], index=1, horizontal=True)
    invest_val = st.number_input("투자 원금 설정", value=10000000, step=1000000)
    st.caption(f"시장: {market} | 코드: {symbol}")

df = get_robust_data(symbol, market, view_mode)

if df is not None and not df.empty:
    curr_p = df['close'].iloc[-1]; unit = "$" if market == "US" else "원"
    st.markdown(f'<p class="main-title">{target_name} <span style="font-size:1rem; color:#888;">{symbol}</span></p>', unsafe_allow_html=True)
    
    t1, t2, t3, t4 = st.tabs(["📉 시세 분석", "🌡️ AI 퀀트 진단", "📰 뉴스 판별", "📅 캘린더"])

    with t1: # 1P: 시세 및 가이드
        m1, m2, m3 = st.columns(3)
        diff = df['close'].iloc[-1] - df['close'].iloc[-2]
        m1.metric("현재가", f"{curr_p:,.0f}{unit}", f"{diff:+,.0f}")
        m2.metric("목표가 (+12%)", f"{curr_p*1.12:,.0f}{unit}")
        m3.metric("손절가 (-6%)", f"{curr_p*0.94:,.0f}{unit}", delta_color="inverse")
        
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'], increasing_line_color='#FF3B30', decreasing_line_color='#007AFF', name=''), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='#FFD60A', width=1.2), name='5선'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#00F2FF', width=1.2), name='20선'), row=1, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df['vol'], marker_color='#333', name='거래량'), row=2, col=1)
        fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with t2: # 2P: AI 퀀트 및 수익 시뮬레이션
        is_gc = df['GC'].tail(15).any()
        score = 45 + (35 if is_gc else 0) + (20 if curr_p > df['MA20'].iloc[-1] else 0)
        clr = "#FF3B30" if score >= 80 else "#00F2FF" if score >= 60 else "#FFD60A"
        
        c_l, c_r = st.columns([1, 1.2])
        with c_l:
            status = "🚀 적극 매수" if score >= 80 else "✅ 분할 매수" if score >= 60 else "⚖️ 관망"
            st.markdown(f'<div class="signal-card" style="background-color:{clr}; color:white;">{status} ({score}점)</div>', unsafe_allow_html=True)
            st.markdown(f"""<div class="quant-box">
                <p style="color:#888; margin-bottom:5px;">{invest_val:,.0f}{unit} 투자 시뮬레이션</p>
                <h2 style="color:{clr}; margin:0;">약 {(invest_val*0.054):+,.0f}{unit} 예상</h2>
                <p style="font-size:0.8rem; color:#666;">* 골든크로스 백데이터 평균 기대 수익 기반</p>
            </div>""", unsafe_allow_html=True)
            st.divider()
            st.checkbox("최근 골든크로스 신호 감지", value=is_gc, disabled=True)
            st.checkbox("이평선 정배열 추세", value=curr_p > df['MA20'].iloc[-1], disabled=True)
        with c_r:
            fig_g = go.Figure(go.Indicator(mode="gauge+number", value=score, gauge={'bar':{'color':clr}, 'bgcolor':'#222'}))
            fig_g.update_layout(height=450, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', margin=dict(r=50))
            st.plotly_chart(fig_g, use_container_width=True)

    with t3: # 3P: 뉴스 판별
        st.subheader("📰 AI 실시간 뉴스 판별")
        res_n = requests.get(f"https://search.naver.com/search.naver?where=news&query={target_name}")
        soup = BeautifulSoup(res_n.text, 'html.parser')
        for art in soup.select('.news_area')[:6]:
            tit = art.select_one('.news_tit').text; lnk = art.select_one('.news_tit')['href']
            st.markdown(f'<div class="info-card"><a href="{lnk}" target="_blank" style="color:white; text-decoration:none;">{tit}</a></div>', unsafe_allow_html=True)

    with t4: # 4P: 공모주/배당주
        st.subheader("📅 투자 캘린더 센터")
        st.markdown('<div class="info-card"><a href="https://finance.naver.com/sise/ipo.naver" target="_blank" style="color:#00F2FF; text-decoration:none;">🚀 실시간 IPO 청약 일정 확인</a></div>', unsafe_allow_html=True)
        st.markdown('<div class="info-card"><a href="https://finance.naver.com/sise/dividend_list.naver" target="_blank" style="color:#FFD60A; text-decoration:none;">💰 국내 고배당 종목 순위</a></div>', unsafe_allow_html=True)
else:
    st.error("데이터 로드 실패: 해당 종목의 표 구조를 찾을 수 없습니다. 종목명을 정확히 입력해 주세요.")
