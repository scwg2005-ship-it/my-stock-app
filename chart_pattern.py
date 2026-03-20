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
st.set_page_config(layout="wide", page_title="Aegis Master v37.1")
st.markdown("""
    <style>
    .stApp { background-color: #000000; }
    .stMetric { border: 1.5px solid #00f2ff; background-color: #080808; color: #ffffff !important; padding: 18px; border-radius: 12px; }
    .main-title { font-size: 2.2rem; font-weight: 800; color: #ffdf00; text-align: center; margin-bottom: 25px; }
    .status-text { font-size: 1.5rem; font-weight: 700; text-align: center; padding: 10px; border-radius: 8px; border: 2px solid #00ff41; color: #00ff41; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 스마트 종목 코드 검색 (강화 버전) ---
@st.cache_data
def get_precise_code(query):
    if query.isdigit() and len(query) == 6: return query
    try:
        # 네이버 검색 결과에서 종목 코드를 정확히 추출
        url = f"https://search.naver.com/search.naver?query={query} 종목코드"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=5)
        # 종목코드 6자리 숫자 패턴 탐색
        codes = re.findall(r'(\d{6})', res.text)
        if codes: return codes[0]
    except: pass
    return "005930"

# --- 3. 방탄 데이터 로더 (모든 종목 대응) ---
@st.cache_data(ttl=60)
def get_bulletproof_data(code, mode="일봉"):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        if mode == "1분봉":
            url = f"https://finance.naver.com/item/sise_time.naver?code={code}&page=1"
        else:
            url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page=1"
        
        res = requests.get(url, headers=headers, timeout=10)
        # 표 추출 시 lxml 엔진 강제 및 인덱스 정밀 조정
        dfs = pd.read_html(StringIO(res.text), flavor='lxml')
        
        # 데이터 유효성 검사
        if not dfs or len(dfs[0]) < 2:
            return None, "해당 종목의 데이터를 찾을 수 없습니다."
            
        df = dfs[0].copy()
        
        if mode == "1분봉":
            df.columns = ['시간', '종가', '전일비', '매수', '매도', '거래량', '변동량']
            df = df.dropna(subset=['시간'])
            df['시가'] = df['종가']; df['고가'] = df['종가']; df['저가'] = df['종가']
            df = df.set_index('시간').sort_index()
        else:
            # 일봉/월봉 컬럼명 강제 할당 (구조가 다른 경우 대비)
            if len(df.columns) >= 7:
                df = df.iloc[:, [0, 1, 2, 3, 4, 5, 6]]
                df.columns = ['날짜', '종가', '전일비', '시가', '고가', '저가', '거래량']
            df = df.dropna(subset=['날짜'])
            df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
            df = df.dropna(subset=['날짜'])
            df = df.set_index('날짜').sort_index()
            
        # 수치형 변환 (콤마 제거 등)
        for col in ['종가', '시가', '고가', '저가', '거래량']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df = df.ffill().dropna() # 결측치 처리
        
        if len(df) < 5: return None, "데이터 개수가 부족합니다."
        
        # 기술적 지표 계산
        df['MA5'] = df['종가'].rolling(window=5).mean()
        df['MA20'] = df['종가'].rolling(window=20).mean()
        df['GC'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1))
        df['DC'] = (df['MA5'] < df['MA20']) & (df['MA5'].shift(1) >= df['MA20'].shift(1))
        
        return df, "성공"
    except Exception as e:
        return None, f"연결 오류: {str(e)}"

# --- 4. 메인 UI ---
st.markdown('<p class="main-title">Aegis Master Control v37.1</p>', unsafe_allow_html=True)

with st.sidebar:
    st.subheader("🔍 스마트 종목 검색")
    search_q = st.text_input("종목명 입력 (예: 한화에어로)", value="한화에어로스페이스")
    
    # 자동완성 후보군
    candidates = ["삼성전자", "현대차", "한화", "한화솔루션", "한화에어로스페이스", "한화오션", "쓰리빌리언", "에코프로"]
    filtered = [c for c in candidates if search_q in c]
    if not filtered: filtered = [search_q]
    
    target_name = st.selectbox("종목 선택", options=filtered)
    target_code = get_precise_code(target_name)
    view_mode = st.radio("차트 주기", ["1분봉", "일봉", "월봉"], index=1)
    st.divider()
    st.caption(f"분석 중인 코드: {target_code}")

# 데이터 로드
df, msg = get_bulletproof_data(target_code, view_mode)

if df is not None and not df.empty:
    curr_p = df['종가'].iloc[-1]
    tab1, tab2, tab3 = st.tabs(["📈 패턴 차트", "🌡️ AI 온도계", "🔍 리포트"])

    with tab1:
        # 매매 가이드 (고대비)
        c1, c2, c3 = st.columns(3)
        c1.metric("🔥 AI 권장 매수", f"{curr_p * 0.99:,.0f}원")
        c2.metric("🚀 목표 익절", f"{curr_p * 1.12:,.0f}원")
        c3.metric("⚠️ 위험 손절", f"{curr_p * 0.94:,.0f}원")

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.05)
        fig.add_trace(go.Candlestick(x=df.index, open=df['시가'], high=df['고가'], low=df['저가'], close=df['종가'],
                                     increasing_line_color='#00ff41', decreasing_line_color='#ff0055', name='시세'), row=1, col=1)
        
        # 골든크로스 표시
        gc_points = df[df['GC']]
        if not gc_points.empty:
            fig.add_trace(go.Scatter(x=gc_points.index, y=gc_points['종가'], mode='markers', marker=dict(symbol='star', size=10, color='#ffdf00'), name='신호'), row=1, col=1)

        fig.update_xaxes(fixedrange=True); fig.update_yaxes(fixedrange=True)
        fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False, dragmode=False)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with tab2:
        score = 50 + (25 if df['GC'].tail(10).any() else 0) + (25 if curr_p > df['MA20'].iloc[-1] else 0)
        st.markdown(f'<div class="status-text">AI 종합 판정: {score}점</div>', unsafe_allow_html=True)
        fig_g = go.Figure(go.Indicator(mode="gauge+number", value=score, gauge={'bar':{'color':"#00ff41"}, 'axis':{'range':[0,100]}}))
        fig_g.update_layout(height=350, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_g, use_container_width=True, config={'displayModeBar': False})
else:
    st.error(f"데이터 로드 실패: {msg}")
