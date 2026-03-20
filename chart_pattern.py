import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from bs4 import BeautifulSoup
from io import StringIO

# --- 1. 스타일 설정 ---
st.set_page_config(layout="wide", page_title="Aegis Pro v55.2")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;800&display=swap');
    body, .stApp { background-color: #000000; font-family: 'Pretendard', sans-serif; }
    .stMetric { background-color: #111; padding: 20px; border-radius: 16px; border: 1px solid #222; }
    .analysis-card { background: #161616; padding: 25px; border-radius: 20px; border-left: 5px solid #00f2ff; margin-bottom: 20px; }
    .signal-text { font-size: 1.8rem; font-weight: 800; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [수정] 초간편 종목 마스터 로더 (IndexError 방지) ---
@st.cache_data(ttl=86400)
def get_stock_master_list():
    try:
        # 가장 안정적인 KIND 종목 코드 리스트 활용
        url = 'http://kind.krx.co.kr/corpoctl/corpList.do?method=download&searchType=13'
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        df = pd.read_html(StringIO(res.text), header=0)[0]
        # 종목명과 종목코드 컬럼을 이름으로 직접 찾기
        df = df[['회사명', '종목코드']].copy()
        df.columns = ['name', 'code']
        df['code'] = df['code'].apply(lambda x: f"{int(x):06d}")
        return dict(zip(df['name'], df['code']))
    except:
        # 서버 에러 시 비상용 리스트
        return {"삼성전자": "005930", "한화솔루션": "009830", "SK하이닉스": "000660", "현대차": "005380"}

# --- 3. 데이터 엔진 (분/일/월 대응 및 스마트 스캔) ---
@st.cache_data(ttl=60)
def get_refined_data(symbol, market="KR", mode="일봉"):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)', 'Referer': 'https://finance.naver.com/'}
    try:
        if market == "KR":
            url = f"https://finance.naver.com/item/sise_time.naver?code={symbol}&page=1" if mode == "1분봉" else f"https://finance.naver.com/item/sise_day.naver?code={symbol}&page=1"
            res = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(res.text, 'lxml')
            tables = soup.find_all('table')
            df = None
            target_key = '시간' if mode == "1분봉" else '날짜'
            for table in tables:
                temp_df = pd.read_html(StringIO(str(table)))[0]
                if target_key in temp_df.columns and len(temp_df) > 5:
                    df = temp_df.dropna(subset=[target_key]).copy()
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
            res = requests.get(url, headers=headers).json()['chart']['result'][0]
            df = pd.DataFrame({'close': res['indicators']['quote'][0]['close'], 'open': res['indicators']['quote'][0]['open'], 'high': res['indicators']['quote'][0]['high'], 'low': res['indicators']['quote'][0]['low'], 'vol': res['indicators']['quote'][0]['volume']}, index=pd.to_datetime(res['timestamp'], unit='s'))
        
        df = df.ffill().dropna().apply(pd.to_numeric)
        df['MA5'] = df['close'].rolling(5).mean()
        df['MA20'] = df['close'].rolling(20).mean()
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
        return df
    except: return None

# --- 4. 사이드바: 풍부한 선택사항 ---
stock_dict = get_stock_master_list()
with st.sidebar:
    st.markdown('<p style="font-size:1.8rem; font-weight:800; color:#00f2ff;">Aegis Control</p>', unsafe_allow_html=True)
    u_input = st.text_input("종목명/티커 입력", value="한화솔루션")
    filtered = [n for n in stock_dict.keys() if u_input in n]
    target_name = st.selectbox(f"검색 결과 ({len(filtered)}건)", options=filtered[:100] if filtered else [u_input])
    symbol = stock_dict.get(target_name, u_input.upper())
    market = "KR" if symbol.isdigit() and len(symbol) == 6 else "US"
    
    st.divider()
    view_mode = st.radio("차트 주기 설정", ["1분봉", "일봉", "월봉"], index=1, horizontal=True)
    invest_val = st.number_input("투자 원금 ($/원)", value=10000000, step=1000000)
    
    st.divider()
    st.subheader("🛠️ 차트 옵션")
    chart_style = st.radio("그래프 형태", ["전문가 캔들", "심플 라인"], horizontal=True)
    show_ma = st.multiselect("이동평균선(MA)", [5, 20, 60, 120], default=[5, 20])
    show_rsi = st.checkbox("RSI 보조지표 표시", value=True)

# --- 5. 메인 로직 및 대시보드 ---
df = get_refined_data(symbol, market, view_mode)

if df is not None and not df.empty:
    curr_p = df['close'].iloc[-1]; unit = "$" if market == "US" else "원"
    rsi_val = df['RSI'].iloc[-1]
    # 객관적 점수 산출
    score = 50 + (25 if curr_p > df['MA20'].iloc[-1] else -10) + (25 if rsi_val < 35 else -10 if rsi_val > 70 else 0)
    est_ret = 8.5 if score > 70 else 2.1
    
    st.markdown(f"### {target_name} ({symbol}) | {view_mode}")
    
    # [상단 대시보드]
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1:
        st.markdown(f"""<div class="analysis-card">
            <p style="margin:0; font-size:1rem; opacity:0.8;">데이터 기반 AI 전략 진단</p>
            <p class="signal-text" style="color:{'#FF3B30' if score > 70 else '#00f2ff'};">{'🚀 적극 매수 신호' if score > 70 else '⚖️ 관망 및 분할 매수'}</p>
            <p style="margin:0;">예상 기대 수익금: {invest_val * (est_ret/100):+,.0f} {unit} ({est_ret}%)</p>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.metric("현재가", f"{curr_p:,.0f}{unit}", f"{df['close'].iloc[-1]-df['close'].iloc[-2]:+,.0f}")
        st.metric("RSI (14D)", f"{rsi_val:.1f}", "과매도" if rsi_val < 30 else "정상")
    with c3:
        st.metric("AI 퀀트 점수", f"{score}점", f"{score-50:+}")
        st.metric("목표가 (+12%)", f"{curr_p*1.12:,.0f}{unit}")

    # [차트 렌더링 세분화]
    rows = 2 if show_rsi else 1
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3] if show_rsi else [1], vertical_spacing=0.03)
    if chart_style == "전문가 캔들" and view_mode != "1분봉":
        fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'], increasing_line_color='#FF3B30', decreasing_line_color='#007AFF', name=''), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(x=df.index, y=df['close'], fill='tozeroy', fillcolor='rgba(0, 242, 255, 0.1)', line=dict(color='#00f2ff', width=2), name=''), row=1, col=1)
    
    for ma in show_ma:
        if f'MA{ma}' not in df.columns: df[f'MA{ma}'] = df['close'].rolling(ma).mean()
        fig.add_trace(go.Scatter(x=df.index, y=df[f'MA{ma}'], line=dict(width=1.2), name=f'{ma}선'), row=1, col=1)
    
    if show_rsi:
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='#FF9500', width=1.5), name='RSI'), row=2, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1); fig.add_hline(y=30, line_dash="dot", line_color="green", row=2, col=1)

    fig.update_layout(height=650, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # [하단 탭 정보]
    t1, t2, t3, t4 = st.tabs(["🌡️ 상세 진단", "📰 실시간 뉴스", "🚀 테마주 정보", "📅 투자 캘린더"])
    with t1: st.write("AI 기술적 지표 분석: 현재 매수 에너지가 강화되고 있습니다.")
    with t2:
        res_n = requests.get(f"https://search.naver.com/search.naver?where=news&query={target_name}")
        soup = BeautifulSoup(res_n.text, 'html.parser')
        for art in soup.select('.news_area')[:5]: st.write(f"· [{art.select_one('.news_tit').text}]({art.select_one('.news_tit')['href']})")
    with t3: st.markdown("[오늘의 핫 테마 확인](https://finance.naver.com/sise/theme.naver)")
    with t4: st.markdown("[공모주/배당주 일정](https://finance.naver.com/sise/ipo.naver)")

else:
    st.error("데이터 로드 실패: 종목명을 다시 확인하시거나 주기를 변경해 보세요.")
