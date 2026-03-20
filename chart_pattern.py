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
st.set_page_config(layout="wide", page_title="Aegis Master v39.0")
st.markdown("""
    <style>
    .stApp { background-color: #000000; }
    .stMetric { border: 1.5px solid #00f2ff; background-color: #080808; color: #ffffff !important; padding: 18px; border-radius: 12px; }
    .main-title { font-size: 2.2rem; font-weight: 800; color: #ffdf00; text-align: center; margin-bottom: 25px; text-shadow: 0 0 10px rgba(255,223,0,0.5); }
    .status-text { font-size: 1.5rem; font-weight: 700; text-align: center; padding: 10px; border-radius: 8px; border: 2px solid #00ff41; color: #00ff41; margin: 10px 0; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [핵심] 전 종목 마스터 데이터 엔진 ---
@st.cache_data(ttl=86400)  # 하루에 한 번 갱신
def get_all_stock_master():
    try:
        # KRX 상장법인목록 다운로드
        url = 'http://kind.krx.co.kr/corpoctl/corpList.do?method=download&searchType=13'
        df_stocks = pd.read_html(url, header=0)[0]
        df_stocks['종목코드'] = df_stocks['종목코드'].apply(lambda x: f"{x:06d}")
        return dict(zip(df_stocks['종목명'], df_stocks['종목코드']))
    except:
        # 실패 시 비상용 리스트
        return {"삼성전자": "005930", "현대차": "005380", "한화에어로스페이스": "012450"}

# --- 3. 방탄 데이터 로더 (분봉/일봉 에러 완벽 차단) ---
@st.cache_data(ttl=60)
def get_integrated_data(code, mode="일봉"):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page=1" if mode != "1분봉" else f"https://finance.naver.com/item/sise_time.naver?code={code}&page=1"
        res = requests.get(url, headers=headers, timeout=10)
        dfs = pd.read_html(StringIO(res.text), flavor='lxml')
        
        df = None
        for temp_df in dfs:
            target_col = '시간' if mode == "1분봉" else '날짜'
            if target_col in temp_df.columns:
                df = temp_df.dropna(subset=[target_col]).copy()
                break
        
        if df is None or len(df) < 5: return None, "데이터 부족"

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
        # 지표 계산
        df['MA5'] = df['종가'].rolling(window=5).mean()
        df['MA20'] = df['종가'].rolling(window=20).mean()
        df['GC'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1))
        df['DC'] = (df['MA5'] < df['MA20']) & (df['MA5'].shift(1) >= df['MA20'].shift(1))
        
        return df, "성공"
    except Exception as e:
        return None, str(e)

# --- 4. 메인 컨트롤 타워 ---
st.markdown('<p class="main-title">Aegis Master Control v39.0</p>', unsafe_allow_html=True)

# 데이터 준비
all_stocks = get_all_stock_master()
stock_names = list(all_stocks.keys())

with st.sidebar:
    st.subheader("🔍 실시간 종목 필터링")
    user_input = st.text_input("종목명 입력 (예: 삼성, 한화)", value="삼성전자")
    
    # [핵심] 실시간 필터링 로직
    filtered_list = [name for name in stock_names if user_input in name]
    if not filtered_list:
        target_name = st.selectbox("검색 결과 없음", [user_input])
    else:
        target_name = st.selectbox(f"검색 결과 ({len(filtered_list)}건)", options=filtered_list[:100])
    
    target_code = all_stocks.get(target_name, "005930")
    view_mode = st.radio("차트 주기", ["1분봉", "일봉", "월봉"], index=1)
    
    st.divider()
    st.subheader("🛠️ 분석 레이어")
    opt_cross = st.checkbox("골든/데드크로스 신호", value=True)
    opt_wave = st.checkbox("엘리어트 파동 가이드", value=True)
    
    st.caption(f"분석 중: {target_name} ({target_code})")

# 데이터 처리 및 렌더링
df, msg = get_integrated_data(target_code, view_mode)

if df is not None and not df.empty:
    curr_p = df['종가'].iloc[-1]
    tab1, tab2 = st.tabs(["📈 분석 차트", "🌡️ AI 온도계"])

    with tab1:
        c1, c2, c3 = st.columns(3)
        c1.metric("🔥 권장 매수", f"{curr_p * 0.99:,.0f}원")
        c2.metric("🚀 목표가", f"{curr_p * 1.12:,.0f}원")
        c3.metric("⚠️ 손절가", f"{curr_p * 0.94:,.0f}원")

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.05)
        fig.add_trace(go.Candlestick(x=df.index, open=df['시가'], high=df['고가'], low=df['저가'], close=df['종가'],
                                     increasing_line_color='#00ff41', decreasing_line_color='#ff0055', name='시세'), row=1, col=1)
        
        # 신호 복구 (GC/DC)
        if opt_cross:
            gc_df = df[df['GC']]
            dc_df = df[df['DC']]
            if not gc_df.empty:
                fig.add_trace(go.Scatter(x=gc_df.index, y=gc_df['종가'], mode='markers', marker=dict(symbol='triangle-up', size=12, color='#ffdf00'), name='골든크로스'), row=1, col=1)
            if not dc_df.empty:
                fig.add_trace(go.Scatter(x=dc_df.index, y=dc_df['종가'], mode='markers', marker=dict(symbol='triangle-down', size=12, color='#ff4b4b'), name='데드크로스'), row=1, col=1)

        fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False, showlegend=False)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with tab2:
        score = 50 + (25 if df['GC'].tail(15).any() else 0) + (25 if curr_p > df['MA20'].iloc[-1] else 0)
        status = "🚀 강력 매수" if score >= 80 else "⚖️ 관망"
        st.markdown(f'<div class="status-text">{target_name}: {status} ({score}점)</div>', unsafe_allow_html=True)
        fig_g = go.Figure(go.Indicator(mode="gauge+number", value=score, gauge={'bar':{'color':"#00ff41"}}))
        fig_g.update_layout(height=350, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_g, use_container_width=True)
else:
    st.error(f"데이터 로드 실패: {msg}")
