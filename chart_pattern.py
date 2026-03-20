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
st.set_page_config(layout="wide", page_title="Aegis Master v41.0")
st.markdown("""
    <style>
    .stApp { background-color: #000000; }
    .stMetric { border: 1.5px solid #00f2ff; background-color: #080808; color: #ffffff !important; padding: 18px; border-radius: 12px; box-shadow: 0 0 15px rgba(0,242,255,0.15); }
    .main-title { font-size: 2.5rem; font-weight: 800; color: #ffdf00; text-align: center; margin-bottom: 30px; text-shadow: 0 0 12px rgba(255,223,0,0.6); }
    .status-text { font-size: 1.5rem; font-weight: 700; text-align: center; padding: 10px; border-radius: 8px; border: 2px solid #00ff41; color: #00ff41; margin: 10px 0; }
    .stTabs>div { background-color: #0a0a0a; border-radius: 10px; border: 1px solid #222; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [데이터] 대한민국 전 종목 마스터 로더 (실시간 필터링 엔진) ---
@st.cache_data(ttl=86400)
def get_all_krx_master():
    try:
        # KRX 상장법인목록 전체 다운로드
        url = 'http://kind.krx.co.kr/corpoctl/corpList.do?method=download&searchType=13'
        df = pd.read_html(url, header=0)[0]
        # 종목코드 6자리 포맷팅 (005930 등)
        df['종목코드'] = df['종목코드'].apply(lambda x: f"{x:06d}")
        # 이름: 코드 매핑 딕셔너리 생성
        return dict(zip(df['종목명'], df['종목코드']))
    except:
        # 서버 오류 대비 기본 리스트
        return {"삼성전자": "005930", "현대차": "005380", "우리금융지주": "316140"}

# --- 3. [로직] 통합 데이터 엔진 (분봉 오류 수정 및 지표 계산) ---
@st.cache_data(ttl=60)
def get_universal_stock_data(code, mode="일봉"):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page=1" if mode != "1분봉" else f"https://finance.naver.com/item/sise_time.naver?code={code}&page=1"
        res = requests.get(url, headers=headers, timeout=10)
        dfs = pd.read_html(StringIO(res.text), flavor='lxml')
        
        df = None
        target_col = '시간' if mode == "1분봉" else '날짜'
        for temp_df in dfs:
            if target_col in temp_df.columns:
                df = temp_df.dropna(subset=[target_col]).copy()
                break
        
        if df is None or len(df) < 5: return None, "시세 데이터를 찾을 수 없습니다."

        if mode == "1분봉":
            df.columns = ['시간', '종가', '전일비', '매수', '매도', '거래량', '변동량']
            df['시가'] = df['종가']; df['고가'] = df['종가']; df['저가'] = df['종가']
            df = df.set_index('시간').sort_index()
        else:
            df = df.iloc[:, :7]
            df.columns = ['날짜', '종가', '전일비', '시가', '고가', '저가', '거래량']
            df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
            df = df.dropna(subset=['날짜']).set_index('날짜').sort_index()
            
        for col in ['종가', '시가', '고가', '저가', '거래량']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df = df.ffill().dropna()
        # 기술적 지표 (이평선/크로스)
        df['MA5'] = df['종가'].rolling(window=5).mean()
        df['MA20'] = df['종가'].rolling(window=20).mean()
        df['GC'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1))
        df['DC'] = (df['MA5'] < df['MA20']) & (df['MA5'].shift(1) >= df['MA20'].shift(1))
        return df, "성공"
    except Exception as e: return None, str(e)

# --- 4. [메인] 검색 및 제어부 ---
st.markdown('<p class="main-title">Aegis Master Control v41.0</p>', unsafe_allow_html=True)

# KRX 전 종목 데이터 확보
all_stocks = get_all_krx_master()
stock_names = list(all_stocks.keys())

with st.sidebar:
    st.subheader("🔍 전 종목 실시간 필터링")
    u_input = st.text_input("종목명 입력 (예: 우리, 삼성, 한화, 셀트리온)", value="우리금융지주")
    
    # [핵심] 입력어가 포함된 모든 상장사 실시간 필터링
    filtered = [n for n in stock_names if u_input in n]
    if not filtered:
        target_name = st.selectbox("결과 없음 (직접 입력)", options=[u_input])
    else:
        # 필터링 결과가 너무 많을 경우 상위 100개만 표시
        target_name = st.selectbox(f"검색 결과 ({len(filtered)}건)", options=filtered[:100])
    
    target_code = all_stocks.get(target_name, "005930")
    view_mode = st.radio("차트 주기 선택", ["1분봉", "일봉", "월봉"], index=1)
    
    st.divider()
    st.subheader("🛠️ 분석 레이어")
    opt_wave = st.checkbox("엘리어트 파동", value=True)
    opt_cross = st.checkbox("골든/데드크로스 신호", value=True)
    st.caption(f"분석 중: {target_name} ({target_code})")

# 데이터 처리
df, msg = get_universal_stock_data(target_code, view_mode)

if df is not None and not df.empty:
    curr_p = df['종가'].iloc[-1]
    tab1, tab2 = st.tabs(["📈 패턴 분석 차트", "🌡️ AI 자동 온도계"])

    with tab1:
        # 매수/매도/손절 가이드
        c1, c2, c3 = st.columns(3)
        c1.metric("🔥 AI 권장 매수", f"{curr_p * 0.99:,.0f}원")
        c2.metric("🚀 목표 익절 (+12%)", f"{curr_p * 1.12:,.0f}원")
        c3.metric("⚠️ 위험 손절 (-6%)", f"{curr_p * 0.94:,.0f}원")

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.05)
        # 캔들 및 이평선
        fig.add_trace(go.Candlestick(x=df.index, open=df['시가'], high=df['고가'], low=df['저가'], close=df['종가'],
                                     increasing_line_color='#00ff41', decreasing_line_color='#ff0055', name='시세'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='#ffdf00', width=1.5), name='5선'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#ffffff', width=1, dash='dot'), 
                                 fill='tonexty', fillcolor='rgba(0, 242, 255, 0.05)', name='20선'), row=1, col=1)
        
        # 신호 복구
        if opt_cross:
            for d in df[df['GC']].index:
                fig.add_annotation(x=d, y=df.loc[d,'종가'], text="✨골든", showarrow=True, arrowhead=1, arrowcolor="#ffdf00", font=dict(color="#ffdf00"), row=1, col=1)
            for d in df[df['DC']].index:
                fig.add_annotation(x=d, y=df.loc[d,'종가'], text="💀데드", showarrow=True, arrowhead=1, arrowcolor="#ff4b4b", font=dict(color="#ff4b4b"), row=1, col=1)

        fig.update_xaxes(fixedrange=True); fig.update_yaxes(fixedrange=True)
        fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False, dragmode=False)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with tab2:
        # AI 자동 온도계
        is_gc = df['GC'].tail(15).any()
        score = 45 + (35 if is_gc else 0) + (20 if curr_p > df['MA20'].iloc[-1] else 0)
        status = "🚀 강력 매수" if score >= 80 else "✅ 매수" if score >= 60 else "⚖️ 관망"
        
        col_chk, col_gauge = st.columns([1, 1.5])
        with col_chk:
            st.markdown(f'<div class="status-text">{target_name}: {status}</div>', unsafe_allow_html=True)
            st.checkbox("최근 골든크로스 발생", value=is_gc, disabled=True)
            st.checkbox("20일 이평선 상단 유지", value=curr_p > df['MA20'].iloc[-1], disabled=True)
        with col_gauge:
            fig_g = go.Figure(go.Indicator(mode="gauge+number", value=score, gauge={'bar':{'color':"#00ff41"}, 'axis':{'range':[0,100]}}))
            fig_g.update_layout(height=350, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_g, use_container_width=True)
else:
    st.error(f"데이터 로드 실패: {msg}")
