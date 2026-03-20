import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from bs4 import BeautifulSoup
from io import StringIO
import re

# --- 1. [디자인] 프리미엄 네온 크리스탈 스타일 ---
st.set_page_config(layout="wide", page_title="Aegis Global v43.1")
st.markdown("""
    <style>
    .stApp { background-color: #000000; }
    .stMetric { border: 1.5px solid #00f2ff; background-color: #080808; color: #ffffff !important; padding: 18px; border-radius: 12px; box-shadow: 0 0 15px rgba(0,242,255,0.15); }
    .main-title { font-size: 2.5rem; font-weight: 800; color: #ffdf00; text-align: center; margin-bottom: 30px; text-shadow: 0 0 12px rgba(255,223,0,0.6); }
    .status-text { font-size: 1.8rem; font-weight: 800; text-align: center; padding: 15px; border-radius: 12px; margin: 10px 0; }
    .news-card { background-color: #111; padding: 15px; border-radius: 10px; border-left: 5px solid #00f2ff; margin-bottom: 12px; }
    .news-title { font-size: 1.15rem; font-weight: 600; color: #fff; text-decoration: none; display: block; margin-bottom: 5px; }
    .news-title:hover { color: #00f2ff; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [검색] 글로벌 2중 검색 엔진 (국내 KRX + 미국 실시간) ---
@st.cache_data(ttl=86400)
def get_krx_master():
    try:
        url = 'http://kind.krx.co.kr/corpoctl/corpList.do?method=download&searchType=13'
        df = pd.read_html(url, header=0)[0]
        df['종목코드'] = df['종목코드'].apply(lambda x: f"{x:06d}")
        return dict(zip(df['종목명'], df['종목코드']))
    except: return {"삼성전자": "005930", "우리금융지주": "316140"}

def fetch_global_symbol(query):
    krx = get_krx_master()
    if query in krx: return krx[query], "KR"
    # 미국 주식 티커 추출 (대문자 1-5자 혹은 네이버 검색 활용)
    if query.isupper() and 1 <= len(query) <= 5: return query, "US"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(f"https://search.naver.com/search.naver?query={query} 주가", headers=headers, timeout=5)
        ticker_match = re.search(r'([A-Z]{1,5})\.O|([A-Z]{1,5})\.N', res.text)
        if ticker_match:
            ticker = ticker_match.group(1) if ticker_match.group(1) else ticker_match.group(2)
            return ticker, "US"
    except: pass
    return query.upper(), "US"

# --- 3. [데이터] 방탄 글로벌 로더 (yfinance 미사용 버전) ---
@st.cache_data(ttl=60)
def get_global_data(symbol, market="KR", mode="일봉"):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        if market == "KR":
            url = f"https://finance.naver.com/item/sise_day.naver?code={symbol}&page=1" if mode != "1분봉" else f"https://finance.naver.com/item/sise_time.naver?code={symbol}&page=1"
            res = requests.get(url, headers=headers)
            dfs = pd.read_html(StringIO(res.text), flavor='lxml')
            df = next(t.dropna(subset=[t.columns[0]]) for t in dfs if '날짜' in t.columns or '시간' in t.columns)
            df = df.iloc[:, :7]
            df.columns = ['date', 'close', 'diff', 'open', 'high', 'low', 'vol']
        else:
            # 미국 주식 Yahoo JSON API 직접 호출 (별도 설치 필요 없음)
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1mo"
            res = requests.get(url, headers=headers)
            res_data = res.json()['chart']['result'][0]
            df = pd.DataFrame({
                'date': pd.to_datetime(res_data['timestamp'], unit='s'),
                'close': res_data['indicators']['quote'][0]['close'],
                'open': res_data['indicators']['quote'][0]['open'],
                'high': res_data['indicators']['quote'][0]['high'],
                'low': res_data['indicators']['quote'][0]['low'],
                'vol': res_data['indicators']['quote'][0]['volume']
            })
        
        df = df.set_index('date').sort_index().ffill().dropna()
        for c in ['close', 'open', 'high', 'low', 'vol']: df[c] = pd.to_numeric(df[c])
        df['MA5'] = df['close'].rolling(window=5).mean()
        df['MA20'] = df['close'].rolling(window=20).mean()
        df['GC'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1))
        return df
    except: return None

# --- 4. [뉴스] 실시간 뉴스 및 URL 링크 ---
@st.cache_data(ttl=300)
def get_realtime_news(query):
    headers = {'User-Agent': 'Mozilla/5.0'}
    news_list = []
    try:
        res = requests.get(f"https://search.naver.com/search.naver?where=news&query={query}+주가", headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        for art in soup.select('.news_area')[:6]:
            news_list.append({
                "title": art.select_one('.news_tit').text,
                "link": art.select_one('.news_tit')['href'],
                "press": art.select_one('.info_group').text.split(' ')[0]
            })
    except: pass
    return news_list

# --- 5. 메인 UI 및 컨트롤 ---
st.markdown('<p class="main-title">Aegis Global Master v43.1</p>', unsafe_allow_html=True)

all_stocks = get_krx_master()
with st.sidebar:
    st.subheader("🔍 실시간 글로벌 필터링")
    u_input = st.text_input("종목명/티커 입력 (예: 솔리드파워, 삼성, TSLA)", value="SLDP")
    
    # 실시간 필터링 (국내주식 리스트 기반)
    filtered = [n for n in all_stocks.keys() if u_input in n]
    if filtered:
        target_name = st.selectbox(f"검색 결과 ({len(filtered)}건)", options=filtered[:50])
    else: target_name = u_input
    
    symbol, market = fetch_global_symbol(target_name)
    view_mode = st.radio("주기", ["일봉", "월봉"], index=0)
    st.divider()
    st.info(f"분석 대상: {target_name} ({symbol}) | 시장: {market}")

df = get_global_data(symbol, market, view_mode)

if df is not None:
    curr_p = df['close'].iloc[-1]
    unit = "$" if market == "US" else "원"
    tab1, tab2, tab3 = st.tabs(["📈 [1P] 통합 차트", "🌡️ [2P] AI 정밀 온도계", "📰 [3P] 실시간 뉴스"])

    # 1P: 통합 차트 분석
    with tab1:
        c1, c2, c3 = st.columns(3)
        c1.metric("🔥 AI 권장 매수", f"{unit}{curr_p * 0.99:,.2f}")
        c2.metric("🚀 목표 익절 (+12%)", f"{unit}{curr_p * 1.12:,.2f}")
        c3.metric("⚠️ 위험 손절 (-6%)", f"{unit}{curr_p * 0.94:,.2f}")
        
        fig = make_subplots(rows=1, cols=1)
        fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'],
                                     increasing_line_color='#00ff41', decreasing_line_color='#ff0055', name='시세'))
        fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False, dragmode=False)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # 2P: 풍부한 AI 온도계 (오른쪽 치우침)
    with tab2:
        is_gc = df['GC'].tail(15).any()
        score = 45 + (30 if is_gc else 0) + (25 if curr_p > df['MA20'].iloc[-1] else 0)
        status, s_color = ("🚀 강력 매수", "#00ff41") if score >= 80 else ("⚖️ 관망 유지", "#ffdf00")
        
        col_info, col_gauge = st.columns([1, 1.2])
        with col_info:
            st.markdown(f'<div class="status-text" style="color:{s_color}; border:2px solid {s_color};">{status}</div>', unsafe_allow_html=True)
            st.write(f"### 🔍 {target_name} AI 리포트")
            st.write(f"현재 종합 에너지 점수는 **{score}점**입니다.")
            st.divider()
            st.checkbox("골든크로스 신호 감지", value=is_gc, disabled=True)
            st.checkbox("이평선 정배열 추세", value=curr_p > df['MA20'].iloc[-1], disabled=True)
        with col_gauge:
            fig_g = go.Figure(go.Indicator(mode="gauge+number", value=score, domain={'x': [0, 1], 'y': [0, 1]},
                gauge={'bar': {'color': s_color}, 'bgcolor': "rgba(0,0,0,0)", 'axis': {'range': [0, 100]}}))
            fig_g.update_layout(height=450, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', margin=dict(r=50))
            st.plotly_chart(fig_g, use_container_width=True)

    # 3P: 실시간 뉴스 URL 링크
    with tab3:
        st.subheader(f"📰 {target_name} 주요 뉴스 (클릭 시 이동)")
        news_data = get_realtime_news(target_name)
        if news_data:
            for n in news_data:
                st.markdown(f'<div class="news-card"><a class="news-title" href="{n["link"]}" target="_blank">{n["title"]}</a><span style="color: #888;">{n["press"]} | 실시간</span></div>', unsafe_allow_html=True)
        else: st.write("뉴스를 불러올 수 없습니다.")

else: st.error("종목을 찾을 수 없습니다. 정확한 티커(예: SLDP, TSLA)를 입력해 주세요.")
