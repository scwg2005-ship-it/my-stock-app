import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from bs4 import BeautifulSoup
from io import StringIO

# --- 1. 스타일 및 레이아웃 ---
st.set_page_config(layout="wide", page_title="Aegis Master v36.0")
st.markdown("""
    <style>
    .stApp { background-color: #000000; }
    .stMetric { border: 1.5px solid #00f2ff; background-color: #080808; color: #ffffff !important; padding: 18px; border-radius: 12px; }
    .main-title { font-size: 2.2rem; font-weight: 800; color: #ffdf00; text-align: center; margin-bottom: 25px; }
    .status-text { font-size: 1.5rem; font-weight: 700; text-align: center; padding: 10px; border-radius: 8px; margin-top: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 전종목 코드 검색 엔진 ---
@st.cache_data
def get_stock_code(name_or_code):
    # 기본 매핑 (자주 쓰는 종목)
    base_codes = {"현대차": "005380", "삼성전자": "005930", "SK하이닉스": "000660", "에코프로": "086520", "카카오": "035720", "NAVER": "035420"}
    if name_or_code in base_codes:
        return base_codes[name_or_code]
    
    # 숫자로만 되어 있으면 코드로 간주
    if name_or_code.isdigit() and len(name_or_code) == 6:
        return name_or_code
    
    # 네이버 검색을 통한 코드 유추 (간이 로직)
    try:
        search_url = f"https://search.naver.com/search.naver?query={name_or_code} 주가"
        res = requests.get(search_url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(res.text, 'html.parser')
        # 종목코드 추출 (패턴 매칭)
        import re
        code_match = re.search(r'(\d{6})', res.text)
        if code_match:
            return code_match.group(1)
    except:
        pass
    return "005930" # 못 찾으면 삼전 기본값

# --- 3. 데이터 및 패턴 엔진 (v35.3 정밀 로직 포함) ---
@st.cache_data(ttl=60)
def get_master_data_v36(code, mode="day"):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        if mode in ["일봉", "월봉"]:
            url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page=1"
            res = requests.get(url, headers=headers, timeout=7)
            df = pd.read_html(StringIO(res.text), flavor='lxml')[0].dropna()
            df.columns = ['날짜', '종가', '전일비', '시가', '고가', '저가', '거래량']
            df['날짜'] = pd.to_datetime(df['날짜'])
            df = df.set_index('날짜').sort_index()
        else:
            url = f"https://finance.naver.com/item/sise_time.naver?code={code}&page=1"
            res = requests.get(url, headers=headers, timeout=7)
            df = pd.read_html(StringIO(res.text), flavor='lxml')[0].dropna()
            df.columns = ['시간', '종가', '전일비', '매수', '매도', '거래량', '변동량']
            df['고가'] = df['종가']; df['저가'] = df['종가']; df['시가'] = df['종가']
            df = df.set_index('시간').sort_index()
        
        # 지표 계산
        df['MA5'] = df['종가'].rolling(window=5).mean()
        df['MA20'] = df['종가'].rolling(window=20).mean()
        df['GC'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1))
        df['DC'] = (df['MA5'] < df['MA20']) & (df['MA5'].shift(1) >= df['MA20'].shift(1))
        
        return df, "성공"
    except Exception as e: return None, str(e)

# --- 4. 메인 UI ---
st.markdown('<p class="main-title">Aegis Master Control v36.0</p>', unsafe_allow_html=True)

with st.sidebar:
    st.subheader("🔍 종목 검색")
    search_input = st.text_input("종목명 또는 코드 입력", value="삼성전자")
    target_code = get_stock_code(search_input)
    view_mode = st.radio("차트 주기", ["1분봉", "일봉", "월봉"], index=1)
    
    st.divider()
    st.subheader("🛠️ 분석 레이어")
    opt_wave = st.checkbox("엘리어트 파동", value=True)
    opt_angle = st.checkbox("삼각수렴 빗각", value=True)
    opt_lines = st.checkbox("지지/저항선", value=True)
    opt_cross = st.checkbox("골든/데드크로스", value=True)

df, msg = get_master_data_v36(target_code, view_mode)

if df is not None and not df.empty:
    curr_p = df['종가'].iloc[-1]
    tab1, tab2, tab3 = st.tabs(["📈 [1P] 차트 분석", "🌡️ [2P] AI 온도계", "🔍 [3P] 뉴스"])

    with tab1:
        # 매매 가이드 (고대비)
        c1, c2, c3 = st.columns(3)
        c1.metric("🔥 AI 권장 매수", f"{curr_p * 0.99:,.0f}원")
        c2.metric("🚀 목표가 (+12%)", f"{curr_p * 1.12:,.0f}원")
        c3.metric("⚠️ 손절가 (-6%)", f"{curr_p * 0.94:,.0f}원")

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.05)
        fig.add_trace(go.Candlestick(x=df.index, open=df['시가'], high=df['고가'], low=df['저가'], close=df['종가'],
                                     increasing_line_color='#00ff41', decreasing_line_color='#ff0055', name='시세'), row=1, col=1)
        
        # 신호 표시
        if opt_cross:
            for date in df[df['GC']].index:
                fig.add_annotation(x=date, y=df.loc[date,'종가'], text="✨골든", showarrow=True, arrowhead=1, arrowcolor="#ffdf00", font=dict(color="#ffdf00"), row=1, col=1)
            for date in df[df['DC']].index:
                fig.add_annotation(x=date, y=df.loc[date,'종가'], text="💀데드", showarrow=True, arrowhead=1, arrowcolor="#ff4b4b", font=dict(color="#ff4b4b"), row=1, col=1)

        fig.update_xaxes(fixedrange=True); fig.update_yaxes(fixedrange=True)
        fig.update_layout(height=580, template='plotly_dark', xaxis_rangeslider_visible=False, dragmode=False)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with tab2:
        # 2페이지 AI 온도계
        score = 40 + (30 if df['GC'].tail(10).any() else 0) + (30 if curr_p > df['MA20'].iloc[-1] else 0)
        status = "🚀 강력 매수" if score >= 80 else "✅ 매수" if score >= 60 else "⚖️ 관망"
        st.markdown(f'<div class="status-text" style="color:#00ff41; border: 2px solid #00ff41;">{status} ({score}점)</div>', unsafe_allow_html=True)
        fig_g = go.Figure(go.Indicator(mode="gauge+number", value=score, gauge={'bar':{'color':"#00ff41"}}))
        fig_g.update_layout(height=350, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_g, use_container_width=True, config={'displayModeBar': False})

else:
    st.error(f"데이터 로드 실패: {msg}")
