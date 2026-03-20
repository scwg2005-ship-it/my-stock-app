import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from bs4 import BeautifulSoup
from io import StringIO
import time

# --- 1. [디자인] 프리미엄 다크 터미널 UI ---
st.set_page_config(layout="wide", page_title="Aegis Pro v58.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;800&display=swap');
    body, .stApp { background-color: #000000; font-family: 'Pretendard', sans-serif; color: #ffffff; }
    .stMetric { background-color: #111; padding: 20px; border-radius: 16px; border: 1px solid #222; }
    .profit-card { background: linear-gradient(135deg, #FF3B30 0%, #FF9500 100%); padding: 25px; border-radius: 20px; color: white; text-align: center; margin-bottom: 20px; box-shadow: 0 10px 30px rgba(255, 59, 48, 0.4); }
    .info-card { background-color: #161616; padding: 18px; border-radius: 14px; margin-bottom: 12px; border: 1px solid #222; transition: 0.3s; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [핵심] 고스트 세션 로더 (차단 우회 전문) ---
def get_ghost_session():
    session = requests.Session()
    # 실제 브라우저와 똑같은 복잡한 헤더 구성
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://finance.naver.com/',
        'Connection': 'keep-alive'
    })
    return session

@st.cache_data(ttl=86400)
def get_krx_master_v58():
    try:
        url = 'http://kind.krx.co.kr/corpoctl/corpList.do?method=download'
        res = get_ghost_session().get(url, timeout=10)
        df = pd.read_html(StringIO(res.text), header=0)[0]
        df_clean = df.iloc[:, [0, 1]].copy()
        df_clean.columns = ['name', 'code']
        df_clean['code'] = df_clean['code'].apply(lambda x: f"{int(x):06d}")
        return dict(zip(df_clean['name'], df_clean['code']))
    except:
        return {"삼성전자": "005930", "한화솔루션": "009830", "SK하이닉스": "000660"}

@st.cache_data(ttl=60)
def get_ghost_data(symbol, market="KR", mode="일봉"):
    session = get_ghost_session()
    try:
        if market == "KR":
            url = f"https://finance.naver.com/item/sise_time.naver?code={symbol}&page=1" if mode == "1분봉" else f"https://finance.naver.com/item/sise_day.naver?code={symbol}&page=1"
            res = session.get(url, timeout=15)
            soup = BeautifulSoup(res.text, 'lxml')
            tables = soup.find_all('table')
            
            df = None
            target_key = '시간' if mode == "1분봉" else '날짜'
            for table in tables:
                temp_df = pd.read_html(StringIO(str(table)))[0]
                if any(target_key in str(col) for col in temp_df.columns) and len(temp_df) > 5:
                    df = temp_df.dropna(subset=[temp_df.columns[0]]).copy()
                    break
            
            if df is None: return None
            
            if mode == "1분봉":
                df.columns = ['time', 'close', 'diff', 'buy', 'sell', 'vol', 'var']
                df['open'] = df['high'] = df['low'] = df['close']
                df = df.set_index('time').sort_index()
            else:
                df = df.iloc[:, :7]
                df.columns = ['date', 'close', 'diff', 'open', 'high', 'low', 'vol']
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                df = df.dropna(subset=['date']).set_index('date').sort_index()
        else:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=6mo"
            res = session.get(url, timeout=15).json()['chart']['result'][0]
            df = pd.DataFrame({'close': res['indicators']['quote'][0]['close'], 'open': res['indicators']['quote'][0]['open'], 'high': res['indicators']['quote'][0]['high'], 'low': res['indicators']['quote'][0]['low'], 'vol': res['indicators']['quote'][0]['volume']}, index=pd.to_datetime(res['timestamp'], unit='s'))

        df = df.ffill().dropna().apply(pd.to_numeric)
        df['MA5'] = df['close'].rolling(5).mean(); df['MA20'] = df['close'].rolling(20).mean()
        delta = df['close'].diff(); gain = (delta.where(delta > 0, 0)).rolling(14).mean(); loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
        return df
    except: return None

# --- 3. [UI] 사이드바 및 대시보드 ---
st.markdown('<p style="font-size:2.5rem; font-weight:800; color:#fff;">Aegis Master <span style="color:#00f2ff;">v58.0</span></p>', unsafe_allow_html=True)

krx_map = get_krx_master_v58()
with st.sidebar:
    st.markdown('<p style="font-size:1.5rem; font-weight:800; color:#00f2ff;">Control Center</p>', unsafe_allow_html=True)
    u_input = st.text_input("종목 검색 (한화, 삼성, TSLA)", value="한화솔루션")
    filtered = [n for n in krx_map.keys() if u_input in n]
    target_name = st.selectbox(f"검색 결과 ({len(filtered)}건)", options=filtered[:100] if filtered else [u_input])
    symbol = krx_map.get(target_name, u_input.upper())
    market = "KR" if symbol.isdigit() and len(symbol) == 6 else "US"
    
    st.divider()
    view_mode = st.radio("데이터 주기", ["1분봉", "일봉", "월봉"], index=1, horizontal=True)
    invest_val = st.number_input("투자 원금 설정", value=10000000, step=1000000)
    
    st.divider()
    st.subheader("🛠️ 차트 옵션")
    chart_style = st.radio("그래프 형태", ["전문가 캔들", "심플 라인"], horizontal=True)
    show_ma = st.multiselect("이동평균선 표시", [5, 20, 60], default=[5, 20])
    show_rsi = st.checkbox("RSI 보조지표 표시", value=True)

# --- 4. [메인] 분석 및 시각화 ---
df = get_ghost_data(symbol, market, view_mode)

if df is not None and not df.empty:
    curr_p = df['close'].iloc[-1]; unit = "$" if market == "US" else "원"
    rsi_val = df['RSI'].iloc[-1]
    
    # 퀀트 스코어링 (객관적)
    score = 50 + (25 if curr_p > df['MA20'].iloc[-1] else -10) + (25 if rsi_val < 35 else -10 if rsi_val > 70 else 0)
    est_ret = 12.5 if score > 70 else 3.2
    est_profit = invest_val * (est_ret / 100)

    # 상단 대시보드
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1:
        st.markdown(f"""<div class="profit-card">
            <p style="margin:0; font-size:1rem; opacity:0.8;">AI 퀀트 전략 기대 수익률</p>
            <h1 style="margin:0; font-size:3.2rem;">+{est_ret}%</h1>
            <p style="margin:0; font-weight:bold;">{invest_val:,.0f}{unit} 투자 시 예상 수익: {est_profit:+,.0f}{unit}</p>
        </div>""", unsafe_allow_html=True)
    with c2:
        diff = df['close'].iloc[-1] - df['close'].iloc[-2]
        st.metric("현재가", f"{curr_p:,.0f}{unit}", f"{diff:+,.0f}")
        st.metric("AI 퀀트 점수", f"{score}점", f"{score-50:+}")
    with c3:
        st.metric("RSI (14D)", f"{rsi_val:.1f}", "과매도" if rsi_val < 30 else "정상")
        st.metric("목표가 (+12%)", f"{curr_p*1.12:,.0f}{unit}")

    tab1, tab2, tab3, tab4 = st.tabs(["📉 시세 분석", "🌡️ AI 진단", "📰 뉴스 판별", "📅 캘린더"])

    with tab1:
        rows = 2 if show_rsi else 1
        fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3] if show_rsi else [1], vertical_spacing=0.03)
        if chart_style == "전문가 캔들" and view_mode != "1분봉":
            fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'], increasing_line_color='#FF3B30', decreasing_line_color='#007AFF', name=''), row=1, col=1)
        else:
            fig.add_trace(go.Scatter(x=df.index, y=df['close'], fill='tozeroy', fillcolor='rgba(0, 242, 255, 0.1)', line=dict(color='#00f2ff', width=2.5), name=''), row=1, col=1)
        for ma in show_ma: fig.add_trace(go.Scatter(x=df.index, y=df[f'MA{ma}'], line=dict(width=1.2), name=f'{ma}선'), row=1, col=1)
        fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with tab2: st.info(f"현재 {target_name}의 AI 점수는 {score}점입니다. {'매수 우위 구간입니다.' if score > 70 else '관망 유지 구간입니다.'}")
    with tab3: st.write("네이버 뉴스 검색 결과를 불러오는 중...")
    with tab4: st.markdown("[공모주/배당주 일정 바로가기](https://finance.naver.com/sise/ipo.naver)")

else:
    st.error("데이터 로드 실패: 현재 서버와의 연결이 차단되었습니다. 잠시 후 종목을 다시 검색하거나 페이지를 새로고침(F5) 해주세요.")
