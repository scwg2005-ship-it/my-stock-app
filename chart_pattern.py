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
st.set_page_config(layout="wide", page_title="Aegis Pro v51.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;800&display=swap');
    body, .stApp { background-color: #000000; font-family: 'Pretendard', sans-serif; }
    .stMetric { border: none; background-color: #111; padding: 20px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
    .main-title { font-size: 2rem; font-weight: 800; color: #fff; text-align: left; margin-bottom: 20px; }
    .signal-card { font-size: 1.8rem; font-weight: 800; text-align: center; padding: 20px; border-radius: 16px; margin-bottom: 20px; }
    .info-card { background-color: #161616; padding: 18px; border-radius: 14px; margin-bottom: 12px; border: 1px solid #222; }
    .news-tag { padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 800; margin-right: 8px; }
    .tag-pos { background-color: #FF3B30; color: white; } /* 호재 */
    .tag-neg { background-color: #007AFF; color: white; } /* 악재 */
    .tag-neu { background-color: #444; color: white; }    /* 중립 */
    </style>
    """, unsafe_allow_html=True)

# --- 2. AI 뉴스 감성 판별 로직 (Keyword-based AI) ---
def analyze_sentiment(title):
    pos_keywords = ['상승', '돌파', '수주', '흑자', '최대', '호재', '급등', '계약', 'M&A', '추천']
    neg_keywords = ['하락', '적자', '급락', '유상증자', '과징금', '조사', '악재', '부진', '손실']
    
    for word in pos_keywords:
        if word in title: return "호재", "tag-pos"
    for word in neg_keywords:
        if word in title: return "악재", "tag-neg"
    return "중립", "tag-neu"

# --- 3. 데이터 로더 (기존 고성능 로직 유지) ---
@st.cache_data(ttl=60)
def get_pro_data_v51(symbol, market="KR"):
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
        df['MA5'] = df['close'].rolling(5).mean(); df['MA20'] = df['close'].rolling(20).mean()
        df['GC'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1))
        return df
    except: return None

# --- 4. 메인 컨트롤 ---
krx_dict = requests.get('http://kind.krx.co.kr/corpoctl/corpList.do?method=download').text
krx_dict = pd.read_html(StringIO(krx_dict), header=0)[0]
krx_dict['종목코드'] = krx_dict['종목코드'].apply(lambda x: f"{x:06d}")
stock_map = dict(zip(krx_dict['종목명'], krx_dict['종목코드']))

with st.sidebar:
    st.title("Aegis v51.0 Pro")
    u_input = st.text_input("종목명/티커", value="삼성전자")
    filtered = [n for n in stock_map.keys() if u_input in n]
    target_name = st.selectbox(f"필터링 ({len(filtered)}건)", options=filtered[:100] if filtered else [u_input])
    symbol = stock_map.get(target_name, u_input.upper())
    market = "KR" if symbol.isdigit() else "US"
    invest_val = st.number_input("원금 설정", value=10000000)

df = get_pro_data_v51(symbol, market)
if df is not None:
    curr_p = df['close'].iloc[-1]; unit = "$" if market == "US" else "원"
    st.markdown(f'<p class="main-title">{target_name} ({symbol})</p>', unsafe_allow_html=True)
    t1, t2, t3, t4 = st.tabs(["📉 분석", "🌡️ 진단", "📰 뉴스판별", "📅 공모/배당"])

    with t1: # 시세 분석
        c1, c2, c3 = st.columns(3)
        c1.metric("현재가", f"{curr_p:,.0f}{unit}")
        c2.metric("목표가", f"{curr_p*1.12:,.0f}{unit}", "+12%")
        c3.metric("손절가", f"{curr_p*0.94:,.0f}{unit}", "-6%", delta_color="inverse")
        fig = make_subplots(rows=1, cols=1)
        fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'], increasing_line_color='#FF3B30', decreasing_line_color='#007AFF'))
        fig.update_layout(height=500, template='plotly_dark', xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

    with t2: # AI 진단
        score = 40 + (35 if df['GC'].tail(15).any() else 0) + (25 if curr_p > df['MA20'].iloc[-1] else 0)
        clr = "#FF3B30" if score >= 80 else "#00F2FF" if score >= 60 else "#FFD60A"
        st.markdown(f'<div class="signal-card" style="background-color:{clr}; color:white;">AI 판정: {score}점</div>', unsafe_allow_html=True)
        st.write(f"### {invest_val:,.0f}{unit} 투자 시 예상 수익: **{(invest_val*0.051):+,.0f}{unit}**")
        fig_g = go.Figure(go.Indicator(mode="gauge+number", value=score, gauge={'bar':{'color':clr}, 'bgcolor':'#222'}))
        fig_g.update_layout(height=350, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_g, use_container_width=True)

    with t3: # AI 뉴스 감성 판별
        st.subheader("📰 AI 실시간 뉴스 감성 분석")
        res_n = requests.get(f"https://search.naver.com/search.naver?where=news&query={target_name}")
        soup = BeautifulSoup(res_n.text, 'html.parser')
        for art in soup.select('.news_area')[:6]:
            tit = art.select_one('.news_tit').text; lnk = art.select_one('.news_tit')['href']
            label, css = analyze_sentiment(tit)
            st.markdown(f"""<div class="info-card">
                <span class="news-tag {css}">{label}</span>
                <a href="{lnk}" target="_blank" style="color:white; text-decoration:none;">{tit}</a>
            </div>""", unsafe_allow_html=True)

    with t4: # 공모주 및 배당주 정보
        st.subheader("📅 공모주 & 고배당주 투자 정보")
        c_ipo, c_div = st.columns(2)
        with c_ipo:
            st.markdown("#### 🚀 따끈따끈 공모주 일정")
            ipo_links = [
                ("IPO 청약 일정 (네이버)", "https://finance.naver.com/sise/ipo.naver"),
                ("신규상장 종목 수익률", "https://finance.naver.com/sise/sise_low_up.naver?sosok=0"),
                ("비상장 주식 시세 (38커뮤니케이션)", "http://www.38.co.kr/")
            ]
            for t, u in ipo_links:
                st.markdown(f'<div class="info-card"><a href="{u}" target="_blank" style="color:#00F2FF; text-decoration:none;">{t}</a></div>', unsafe_allow_html=True)
        with c_div:
            st.markdown("#### 💰 찬바람 불 땐 고배당주")
            div_links = [
                ("배당금 높은 주식 순위", "https://finance.naver.com/sise/dividend_list.naver"),
                ("월배당 ETF 리스트", "https://search.naver.com/search.naver?query=월배당+ETF"),
                ("미국 배당 귀족주 (Dividend Aristocrats)", "https://www.google.com/search?query=US+Dividend+Aristocrats")
            ]
            for t, u in div_links:
                st.markdown(f'<div class="info-card"><a href="{u}" target="_blank" style="color:#FFD60A; text-decoration:none;">{t}</a></div>', unsafe_allow_html=True)

else: st.error("종목 검색 실패. 이름을 정확히 입력해 주세요.")
