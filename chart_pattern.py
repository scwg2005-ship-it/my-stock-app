import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. 설정 및 스타일 ---
st.set_page_config(layout="wide", page_title="Aegis Terminus v25.6")
st.markdown("""
    <style>
    .stMetric { background-color: #0a0a0a; border: 1px solid #222; padding: 10px; border-radius: 8px; }
    .main-title { font-size: 2.2rem; font-weight: 700; color: #00e5ff; text-align: center; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 데이터 수집 엔진 (데이터 양 확대) ---
@st.cache_data(ttl=600)
def get_naver_data(name):
    codes = {"현대자동차": "005380", "현대차": "005380", "삼성전자": "005930", "삼전": "005930", "SK하이닉스": "000660", "에코프로": "086520"}
    code = codes.get(name.strip())
    if not code: return None
    headers = {'User-Agent': 'Mozilla/5.0'}
    all_dfs = []
    try:
        # 에러 방지를 위해 충분한 데이터(3페이지분량)를 가져옴
        for p in range(1, 4):
            url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page={p}"
            res = requests.get(url, headers=headers)
            dfs = pd.read_html(res.text, flavor='lxml')
            if dfs: all_dfs.append(dfs[0].dropna())
        
        df = pd.concat(all_dfs)
        df.columns = ['Date', 'Close', 'Diff', 'Open', 'High', 'Low', 'Volume']
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.set_index('Date').sort_index()
        for col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    except: return None

# --- 3. 패턴 분석 로직 (데이터 개수 체크 추가) ---
def analyze_v25_6(df):
    data_len = len(df)
    indices = np.arange(data_len)
    
    # 엘리어트 파동 포인트 (데이터가 25개 이상일 때만 작동)
    wave_data = None
    if data_len >= 25:
        wave_idx = [data_len-25, data_len-20, data_len-15, data_len-10, data_len-1]
        wave_data = {'x': df.index[wave_idx], 'y': df['Close'].iloc[wave_idx]}

    # 삼각수렴 빗각 (최근 15일로 축소하여 안정성 확보)
    fit_len = min(data_len, 15)
    h_fit = np.polyfit(indices[-fit_len:], df['High'].iloc[-fit_len:], 1)
    l_fit = np.polyfit(indices[-fit_len:], df['Low'].iloc[-fit_len:], 1)
    
    # 지지/저항 (최근 40일)
    res_l = df['High'].tail(40).max()
    sup_l = df['Low'].tail(40).min()
    
    return {
        'wave': wave_data,
        'h_line': h_fit[0] * indices[-fit_len:] + h_fit[1],
        'l_line': l_fit[0] * indices[-fit_len:] + l_fit[1],
        'res': res_l, 'sup': sup_l, 'fit_idx': df.index[-fit_len:]
    }

# --- 4. 메인 화면 ---
st.markdown('<p class="main-title">Aegis Terminus v25.6</p>', unsafe_allow_html=True)

with st.sidebar:
    target_stock = st.selectbox("종목 선택", ["현대자동차", "삼성전자", "SK하이닉스", "에코프로"])
    btn = st.button("분석 실행")

df = get_naver_data(target_stock)

if df is not None and len(df) > 10:
    res = analyze_v25_6(df)
    tab1, tab2, tab3 = st.tabs(["📈 [1P] 통합 차트", "🌡️ [2P] AI 점수 연동", "🔍 [3P] 뉴스"])

    with tab1:
        # 차트 수치 대시보드
        m1, m2, m3 = st.columns(3)
        m1.metric("현재가", f"{df['Close'].iloc[-1]:,.0f}원")
        m2.metric("목표가", f"{df['Close'].iloc[-1]*1.12:,.0f}원")
        m3.metric("손절가", f"{df['Close'].iloc[-1]*0.94:,.0f}원")

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='시세'), row=1, col=1)
        
        # 엘리어트 파동 (데이터 있을 때만)
        if res['wave']:
            fig.add_trace(go.Scatter(x=res['wave']['x'], y=res['wave']['y'], mode='lines+markers+text', 
                                     text=['1','2','3','4','5'], textposition='top center',
                                     line=dict(color='yellow', width=2), name='Wave'), row=1, col=1)
        
        # 빗각 및 지지저항
        fig.add_trace(go.Scatter(x=res['fit_idx'], y=res['h_line'], line=dict(color='cyan', dash='dash'), name='저항빗각'), row=1, col=1)
        fig.add_trace(go.Scatter(x=res['fit_idx'], y=res['l_line'], line=dict(color='magenta', dash='dash'), name='지지빗각'), row=1, col=1)
        fig.add_hline(y=res['res'], line_dash="solid", line_color="red", row=1, col=1)
        fig.add_hline(y=res['sup'], line_dash="solid", line_color="dodgerblue", row=1, col=1)
        
        fig.update_xaxes(fixedrange=True); fig.update_yaxes(fixedrange=True)
        fig.update_layout(height=550, template='plotly_dark', xaxis_rangeslider_visible=False, dragmode=False)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with tab2:
        # 2페이지 체크박스 및 점수 연동
        st.subheader("🤖 AI 점수 연동")
        score = 50
        c1 = st.checkbox("POC 지지 확인 (+10)")
        c2 = st.checkbox("수렴 돌파 시도 (+15)")
        if c1: score += 10
        if c2: score += 15
        st.metric("최종 점수", f"{score}점")
        
    with tab3:
        st.write("실시간 뉴스 데이터 준비 중...")

else:
    st.warning("데이터가 부족하거나 불러올 수 없습니다.")
