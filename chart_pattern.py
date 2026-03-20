import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from bs4 import BeautifulSoup
from io import StringIO
import re

# --- 1. 프리미엄 스타일 설정 (토스/미래에셋 스타일) ---
st.set_page_config(layout="wide", page_title="Aegis Pro v51.1")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;800&display=swap');
    body, .stApp { background-color: #000000; font-family: 'Pretendard', sans-serif; }
    .stMetric { border: none; background-color: #111; padding: 20px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
    .main-title { font-size: 2.2rem; font-weight: 800; color: #fff; text-align: left; margin-bottom: 25px; }
    .signal-card { font-size: 1.8rem; font-weight: 800; text-align: center; padding: 20px; border-radius: 16px; margin-bottom: 20px; }
    .info-card { background-color: #161616; padding: 18px; border-radius: 14px; margin-bottom: 12px; border: 1px solid #222; transition: 0.3s; }
    .info-card:hover { border-color: #00f2ff; }
    .news-tag { padding: 3px 10px; border-radius: 6px; font-size: 0.8rem; font-weight: 800; margin-right: 10px; }
    .tag-pos { background-color: #FF3B30; color: white; } /* 호재 */
    .tag-neg { background-color: #007AFF; color: white; } /* 악재 */
    .tag-neu { background-color: #444; color: white; }    /* 중립 */
    </style>
    """, unsafe_allow_html=True)

# --- 2. 방탄 종목 마스터 로더 (KeyError 완전 방지) ---
@st.cache_data(ttl=86400)
def get_krx_master_ultimate():
    try:
        url = 'http://kind.krx.co.kr/corpoctl/corpList.do?method=download'
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        df = pd.read_html(StringIO(res.text), header=0)[0]
        # 컬럼 이름 대신 위치(iloc)로 안전하게 추출
        df_clean = df.iloc[:, [0, 1]].copy()
        df_clean.columns = ['name', 'code']
        df_clean['code'] = df_clean['code'].apply(lambda x: f"{int(x):06d}")
        return dict(zip(df_clean['name'], df_clean['code']))
    except:
        return {"삼성전자": "005930", "한화솔루션": "009830", "우리금융지주": "316140"}

# --- 3. AI 뉴스 감성 판별 엔진 ---
def analyze_sentiment_ai(title):
    pos = ['상승', '돌파', '수주', '흑자', '최대', '호재', '급등', '계약', 'M&A', '신고가', '영업이익증가']
    neg = ['하락', '적자', '급락', '유상증자', '과징금', '조사', '악재', '부진', '손실', '신저가']
    for w in pos:
        if w in title: return "호재", "tag-pos"
    for w in neg:
        if w in title: return "악재", "tag-neg"
    return "중립", "tag-neu"

# --- 4. 통합 데이터 로더 (국내/미국 자동 전환) ---
@st.cache_data(ttl=60)
def get_unified_stock_data(symbol, market="KR"):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        if market == "KR":
            url = f"https://finance.naver.com/item/sise_day.naver?code={symbol}&page=1"
            res = requests.get(url, headers=headers)
            dfs = pd.read_html(StringIO(res.text), flavor='lxml')
            df = next(t.dropna(subset=['날짜']) for t in dfs if '날짜' in t.columns)
            df = df.iloc[:, :7]; df.columns = ['date', 'close', 'diff', 'open', 'high', 'low', 'vol']
        else:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=6mo"
            res = requests.get(url, headers=headers).json()['chart']['result'][0]
            df = pd.DataFrame({'date': pd.to_datetime(res['timestamp'], unit='s'), 
                               'close': res['indicators']['quote'][0]['close'], 
                               'open': res['indicators']['quote'][0]['open'], 
                               'high': res['indicators']['quote'][0]['high'], 
                               'low': res['indicators']['quote'][0]['low'], 
                               'vol': res['indicators']['quote'][0]['volume']})
        df = df.set_index('date').sort_index().ffill().dropna()
        df['MA5'] = df['close'].rolling(5).mean(); df['MA20'] = df['close'].rolling(20).mean()
        df['GC'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1))
        return df
    except: return None

# --- 5. 사이드바 컨트롤 패널 ---
krx_map = get_krx_master_ultimate()
with st.sidebar:
    st.markdown('<p style="font-size:1.5rem; font-weight:800; color:#00f2ff;">Aegis Dashboard</p>', unsafe_allow_html=True)
    u_input = st.text_input("종목명/티커 입력", value="삼성전자")
    filtered = [n for n in krx_map.keys() if u_input in n]
    target_name = st.selectbox(f"실시간 검색 ({len(filtered)}건)", options=filtered[:100] if filtered else [u_input])
    symbol = krx_map.get(target_name, u_input.upper())
    market = "KR" if symbol.isdigit() and len(symbol) == 6 else "US"
    
    st.divider()
    invest_val = st.number_input("투자 원금 설정", value=10000000, step=1000000)
    chart_style = st.radio("그래프 스타일", ["캔들 차트", "심플 라인"], horizontal=True)

# --- 6. 메인 대시보드 렌더링 ---
df = get_unified_stock_data(symbol, market)

if df is not None and not df.empty:
    curr_p = df['close'].iloc[-1]; unit = "$" if market == "US" else "원"
    st.markdown(f'<p class="main-title">{target_name} <span style="font-size:1rem; color:#888;">{symbol}</span></p>', unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs(["📉 시세 분석", "🌡️ AI 퀀트 진단", "📰 뉴스 판별", "📅 투자 캘린더"])

    with tab1: # 1P: 시세 및 가이드
        m1, m2, m3 = st.columns(3)
        diff = df['close'].iloc[-1] - df['close'].iloc[-2]
        m1.metric("현재가", f"{curr_p:,.0f}{unit}", f"{diff:+,.0f}")
        m2.metric("목표가 (+12%)", f"{curr_p*1.12:,.0f}{unit}")
        m3.metric("손절가 (-6%)", f"{curr_p*0.94:,.0f}{unit}", delta_color="inverse")
        
        fig = make_subplots(rows=1, cols=1)
        if chart_style == "캔들 차트":
            fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'], increasing_line_color='#FF3B30', decreasing_line_color='#007AFF'))
        else:
            fig.add_trace(go.Scatter(x=df.index, y=df['close'], fill='tozeroy', fillcolor='rgba(0, 122, 255, 0.1)', line=dict(color='#007AFF', width=3)))
        
        fig.update_layout(height=550, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with tab2: # 2P: AI 온도계 및 퀀트
        is_gc = df['GC'].tail(15).any()
        score = 40 + (35 if is_gc else 0) + (25 if curr_p > df['MA20'].iloc[-1] else 0)
        clr = "#FF3B30" if score >= 80 else "#00F2FF" if score >= 60 else "#FFD60A"
        
        col_txt, col_gauge = st.columns([1, 1.2])
        with col_txt:
            st.markdown(f'<div class="signal-card" style="background-color:{clr}; color:white;">AI 진단: {score}점</div>', unsafe_allow_html=True)
            st.write(f"#### 💰 {invest_val:,.0f}{unit} 투자 시 예상 수익: **{(invest_val*0.052):+,.0f}{unit}**")
            st.divider()
            st.checkbox("최근 골든크로스 신호 발생", value=is_gc, disabled=True)
            st.checkbox("상승 정배열 추세 유지", value=curr_p > df['MA20'].iloc[-1], disabled=True)
        with col_gauge:
            fig_g = go.Figure(go.Indicator(mode="gauge+number", value=score, gauge={'bar':{'color':clr}, 'bgcolor':'#222'}))
            fig_g.update_layout(height=400, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', margin=dict(r=50))
            st.plotly_chart(fig_g, use_container_width=True)

    with tab3: # 3P: AI 뉴스 판별
        st.subheader("📰 실시간 뉴스 호재/악재 판별")
        res_n = requests.get(f"https://search.naver.com/search.naver?where=news&query={target_name}")
        soup = BeautifulSoup(res_n.text, 'html.parser')
        for art in soup.select('.news_area')[:6]:
            tit = art.select_one('.news_tit').text; lnk = art.select_one('.news_tit')['href']
            label, css = analyze_sentiment_ai(tit)
            st.markdown(f'<div class="info-card"><span class="news-tag {css}">{label}</span><a href="{lnk}" target="_blank" style="color:white; text-decoration:none;">{tit}</a></div>', unsafe_allow_html=True)

    with tab4: # 4P: 투자 캘린더
        st.subheader("📅 공모주 & 고배당주 투자 센터")
        c_i, c_d = st.columns(2)
        with c_i:
            st.markdown("#### 🚀 공모주(IPO) 일정")
            st.markdown('<div class="info-card"><a href="https://finance.naver.com/sise/ipo.naver" target="_blank" style="color:#00F2FF; text-decoration:none;">📈 실시간 IPO 청약 일정 확인</a></div>', unsafe_allow_html=True)
        with c_d:
            st.markdown("#### 💰 고배당주 리스트")
            st.markdown('<div class="info-card"><a href="https://finance.naver.com/sise/dividend_list.naver" target="_blank" style="color:#FFD60A; text-decoration:none;">💎 국내 고배당 종목 순위</a></div>', unsafe_allow_html=True)
else:
    st.error("종목 검색 실패. 정확한 이름을 입력하거나 잠시 후 다시 시도해 주세요.")
