import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from bs4 import BeautifulSoup
from io import StringIO

# --- 1. 프리미엄 스타일 설정 ---
st.set_page_config(layout="wide", page_title="Aegis Master v37.0")
st.markdown("""
    <style>
    .stApp { background-color: #000000; }
    .stMetric { border: 1.5px solid #00f2ff; background-color: #080808; color: #ffffff !important; padding: 18px; border-radius: 12px; }
    .main-title { font-size: 2.2rem; font-weight: 800; color: #ffdf00; text-align: center; margin-bottom: 25px; text-shadow: 0 0 10px rgba(255,223,0,0.5); }
    .status-text { font-size: 1.5rem; font-weight: 700; text-align: center; padding: 10px; border-radius: 8px; margin: 10px 0; border: 2px solid #00ff41; color: #00ff41; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 전종목 리스트 로더 (자동완성용) ---
@st.cache_data
def get_all_krx_stocks():
    # 한국거래소 종목 리스트를 가져오는 간이 방식 (네이버 인기 종목 + 주요 종목 기반 확장 가능)
    # 실제 운영 시에는 KRX 전체 상장사 CSV를 로드하는 것이 가장 정확합니다.
    url = "https://finance.naver.com/sise/sise_market_sum.naver?page=1"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers)
        df = pd.read_html(StringIO(res.text), flavor='lxml')[1]
        df = df.dropna(subset=['종목명'])
        # 주요 종목 리스트 반환 (이름: 코드 매핑)
        return dict(zip(df['종목명'], df['종목명'].apply(lambda x: "조회필요"))) 
    except:
        return {"삼성전자": "005930", "현대차": "005380", "한화": "000880", "한화솔루션": "009830", "한화에어로스페이스": "012450"}

# --- 3. 종목 코드 정밀 검색 엔진 ---
@st.cache_data
def find_stock_code(query):
    if query.isdigit() and len(query) == 6:
        return query
    try:
        url = f"https://search.naver.com/search.naver?query={query} 종목코드"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        import re
        codes = re.findall(r'(\d{6})', res.text)
        return codes[0] if codes else "005930"
    except:
        return "005930"

# --- 4. 데이터 로더 ---
@st.cache_data(ttl=60)
def get_clean_data(code, mode="일봉"):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page=1" if mode != "1분봉" else f"https://finance.naver.com/item/sise_time.naver?code={code}&page=1"
        res = requests.get(url, headers=headers, timeout=10)
        df = pd.read_html(StringIO(res.text), flavor='lxml')[0].dropna()
        
        if mode == "1분봉":
            df.columns = ['시간', '종가', '전일비', '매수', '매도', '거래량', '변동량']
            df['시가'] = df['종가']; df['고가'] = df['종가']; df['저가'] = df['종가']
            df = df.set_index('시간').sort_index()
        else:
            df.columns = ['날짜', '종가', '전일비', '시가', '고가', '저가', '거래량']
            df['날짜'] = pd.to_datetime(df['날짜'])
            df = df.set_index('날짜').sort_index()
            
        df['MA5'] = df['종가'].rolling(window=5).mean()
        df['MA20'] = df['종가'].rolling(window=20).mean()
        df['GC'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1))
        df['DC'] = (df['MA5'] < df['MA20']) & (df['MA5'].shift(1) >= df['MA20'].shift(1))
        return df, "성공"
    except Exception as e:
        return None, str(e)

# --- 5. 메인 UI ---
st.markdown('<p class="main-title">Aegis Master Control v37.0</p>', unsafe_allow_html=True)

with st.sidebar:
    st.subheader("🔍 스마트 종목 검색")
    # 자동완성을 위한 리스트 (상위 종목 + 사용자 입력 기반 필터링)
    stock_dict = get_all_krx_stocks()
    # [핵심] st.selectbox에 options를 넣고 index를 조절하여 자동완성 효과를 줌
    search_query = st.text_input("종목명을 입력하세요 (예: 한화)", value="한화")
    
    # 입력한 글자가 포함된 종목들만 필터링하여 리스트업
    filtered_stocks = [name for name in ["삼성전자", "현대차", "한화", "한화솔루션", "한화에어로스페이스", "한화오션", "한화시스템", "한화투자증권", "쓰리빌리언", "에코프로"] if search_query in name]
    
    if not filtered_stocks:
        filtered_stocks = [search_query] # 필터링 결과 없으면 입력값 그대로 사용
        
    target_stock = st.selectbox("검색 결과 선택", options=filtered_stocks)
    target_code = find_stock_code(target_stock)
    
    view_mode = st.radio("차트 주기", ["1분봉", "일봉", "월봉"], index=1)
    st.divider()
    st.caption(f"분석 중인 코드: {target_code}")

# 데이터 로드 및 시각화
df, msg = get_clean_data(target_code, view_mode)

if df is not None and not df.empty:
    curr_p = df['종가'].iloc[-1]
    tab1, tab2, tab3 = st.tabs(["📈 패턴 차트", "🌡️ AI 온도계", "🔍 리포트"])

    with tab1:
        # 매매 가이드
        c1, c2, c3 = st.columns(3)
        c1.metric("🔥 AI 권장 매수", f"{curr_p * 0.99:,.0f}원")
        c2.metric("🚀 목표 익절 (+12%)", f"{curr_p * 1.12:,.0f}원")
        c3.metric("⚠️ 위험 손절 (-6%)", f"{curr_p * 0.94:,.0f}원")

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.05)
        fig.add_trace(go.Candlestick(x=df.index, open=df['시가'], high=df['고가'], low=df['저가'], close=df['종가'],
                                     increasing_line_color='#00ff41', decreasing_line_color='#ff0055', name='시세'), row=1, col=1)
        
        # 골든/데드크로스 마킹
        gc_df = df[df['GC']]
        if not gc_df.empty:
            fig.add_trace(go.Scatter(x=gc_df.index, y=gc_df['종가'], mode='markers', marker=dict(symbol='triangle-up', size=12, color='#ffdf00'), name='✨골든'), row=1, col=1)

        fig.update_xaxes(fixedrange=True); fig.update_yaxes(fixedrange=True)
        fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False, dragmode=False)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with tab2:
        score = 50 + (25 if df['GC'].tail(10).any() else 0) + (25 if curr_p > df['MA20'].iloc[-1] else 0)
        status = "🚀 강력 매수" if score >= 80 else "✅ 매수" if score >= 60 else "⚖️ 관망"
        st.markdown(f'<div class="status-text">{status} ({score}점)</div>', unsafe_allow_html=True)
        fig_g = go.Figure(go.Indicator(mode="gauge+number", value=score, gauge={'bar':{'color':"#00ff41"}}))
        fig_g.update_layout(height=350, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_g, use_container_width=True, config={'displayModeBar': False})
else:
    st.error(f"데이터 로드 실패: {msg}")
