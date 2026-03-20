import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import trendln  # 추세선 및 삼각수렴 자동 계산
from sklearn.cluster import KMeans # 매물대 분석

# --- 전역 설정 ---
st.set_page_config(layout="wide", page_title="v15.0 Alpha Quant System")

# --- 종목 코드 변환 함수 (이전 코드 유지) ---
def get_stock_code(name):
    """종목명으로 티커/코드 찾기 (한국/미국 통합)"""
    # 💡 더 빠른 성능을 위해 세션 상태에 데이터베이스 캐싱
    if 'krx_list' not in st.session_state:
        st.session_state['krx_list'] = fdr.StockListing('KRX')
    if 'nasdaq_list' not in st.session_state:
        st.session_state['nasdaq_list'] = fdr.StockListing('NASDAQ')

    df_krx = st.session_state['krx_list']
    df_nasdaq = st.session_state['nasdaq_list']
    
    # 1. 한국 종목명 검색
    target = df_krx[df_krx['Name'] == name]
    if not target.empty:
        return target.iloc[0]['Code']
    
    # 2. 미국 티커 검색 (이미 티커인 경우)
    target = df_nasdaq[df_nasdaq['Symbol'] == name.upper()]
    if not target.empty:
        return target.iloc[0]['Symbol']
    
    # 3. 미국 종목명 검색 (예: Apple -> AAPL)
    # yfinance를 사용하여 대략적인 검색 시도 (검색 품질은 yfinance에 의존)
    return name.upper() 

# --- 핵심 분석 로직 (기능 통합 및 고도화) ---
@st.cache_data(ttl=3600) # 데이터를 1시간 동안 캐싱하여 성능 향상
def analyze_advanced(symbol, period_days=250):
    start_date = (datetime.now() - timedelta(days=period_days)).strftime('%Y-%m-%d')
    end_date = datetime.now().strftime('%Y-%m-%d')
    
    try:
        df = fdr.DataReader(symbol, start=start_date, end=end_date)
    except Exception as e:
        return None, f"데이터 로드 실패: {str(e)}"

    if df.empty or len(df) < 50:
        return None, "데이터가 충분하지 않습니다 (최소 50일 필요)."

    # 1. 기본 지표 계산 (MA, RSI, BB)
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA50'] = df['Close'].rolling(window=50).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # 볼린저 밴드
    df['BB_Mid'] = df['Close'].rolling(window=20).mean()
    std = df['Close'].rolling(window=20).std()
    df['BB_Upper'] = df['BB_Mid'] + (std * 2)
    df['BB_Lower'] = df['BB_Mid'] - (std * 2)

    # 2. 엘리어트 & 스마트 신호 로직 (우리가 만들었던 로직 유지)
    current_price = df['Close'].iloc[-1]
    low_price = df['Low'].min()
    high_price = df['High'].max()
    
    fib_618 = high_price - (high_price - low_price) * 0.618
    fib_500 = high_price - (high_price - low_price) * 0.5
    
    # 스마트 매수 신호 (기존 로직)
    is_smart_buy = (df['RSI'].iloc[-1] < 35) and (df['Close'].iloc[-1] <= df['BB_Lower'].iloc[-1]) and (df['Volume'].iloc[-1] > df['Volume'].shift(1).iloc[-1])
    is_elliott_buy = fib_618 <= current_price <= fib_500
    
    df['Smart_Buy_Signal'] = 1 if is_smart_buy else 0
    df['Elliott_2_Wait'] = 1 if is_elliott_buy else 0

    # 3. 빗각 & 삼각수렴 자동 계산 (trendln 라이브러리 활용)
    # 주요 추세선 찾기 (고점들과 저점들)
    h_lines = trendln.get_lines(df['High'].values, extmethod=trendln.METHOD_NAIVE)
    l_lines = trendln.get_lines(df['Low'].values, extmethod=trendln.METHOD_NAIVE)
    
    # 가장 최근의 주요 상단/하단 추세선 하나씩만 가져옴
    top_line = h_lines[0] if h_lines else None
    bot_line = l_lines[0] if l_lines else None
    
    # 삼각수렴 확인: 상단선은 하향, 하단선은 상향이며, 두 선이 만날 때
    pattern = "추세 진행 중"
    if top_line and bot_line:
        if top_line[1] < 0 and bot_line[1] > 0: # 기울기 확인
            pattern = "⭐ 삼각수렴 진행 중"

    # 4. AI 기반 매물대 및 가격 구간 분석 (K-Means Clustering)
    # 최근 100일간 가장 많이 거래된 가격대(POC)를 AI로 찾음
    df_vol_price = df.tail(100)[['Close', 'Volume']]
    kmeans = KMeans(n_clusters=5, random_state=42).fit(df_vol_price[['Close']])
    pocs = kmeans.cluster_centers_.flatten()
    
    # 가장 거래량이 많은 가격대 클러스터 찾기
    cluster_volumes = df_vol_price.groupby(kmeans.labels_)['Volume'].sum()
    poc_main = pocs[cluster_volumes.idxmax()]
    
    # 매수/매도/손절 구간 설정 (POC 및 피보나치 기반)
    analysis_repo = {
        'POC': poc_main,
        'Buy_Zone': [fib_618 * 0.98, fib_500 * 1.02], # 2파 눌림목 주변 구간
        'Sell_Zone': [high_price * 0.95, high_price * 1.05], # 전고점 주변 구간
        'StopLoss': low_price * 0.95 # 전저점 아래
    }

    return df, analysis_repo, top_line, bot_line, pattern

# --- 대시보드 UI ---

# 1. 사이드바 (제어 패널)
st.sidebar.markdown("# ⚙️ 제어 패널")
stock_input = st.sidebar.text_input("종목명(한글) 또는 티커", value="ONDS")
period_days = st.sidebar.slider("분석 기간", min_value=100, max_value=1000, value=250, step=50)

if st.sidebar.button("분석 실행"):
    st.experimental_set_query_params(symbol=stock_input, period=period_days)
    st.experimental_rerun()

# URL 쿼리 파라미터에서 종목 가져오기 (실행 버튼 누르지 않아도 초기 로딩되도록)
query_params = st.experimental_get_query_params()
symbol_to_analyze = query_params.get("symbol", [stock_input])[0]
period_to_analyze = int(query_params.get("period", [period_days])[0])

# 2. 메인 화면
with st.spinner(f"[{symbol_to_analyze}] 분석 중..."):
    code = get_stock_code(symbol_to_analyze)
    df, repo, top_line, bot_line, pattern = analyze_advanced(code, period_to_analyze)

    if df is not None:
        # 타이틀
        st.markdown(f"# 🏛️ v15.0 Alpha Quant System")
        st.markdown(f"## 📊 {symbol_to_analyze} ({code}) 분석 리포트")

    # --- 핵심 지표 요약 (이미지 형태처럼 구성) ---
        col1, col2, col3, col4 = st.columns(4)
        
        # 퀀트 온도계 (RSI 기반 시각화)
        current_rsi = df['RSI'].iloc[-1]
        temp_color = "red" if current_rsi > 70 else ("blue" if current_rsi < 30 else "black")
        col1.metric("퀀트 온도 🌡️", f"{current_rsi:.1f}°C", help="RSI 기반 과매수/과매도 온도")
        
        # 패턴 상태
        pattern_icon = "📈" if "수렴" not in pattern else "⏳"
        col2.metric("파동 및 패턴 상태 🌊", pattern, icon=pattern_icon)
        
        # 매물대 POC
        col3.metric("주요 매물대(POC) 🛡️", f"{repo['POC']:.2f}")

        # 추천 가격 구간
        col4.markdown(f"**추천 매수 구간:** \n**{repo['Buy_Zone'][0]:.2f} ~ {repo['Buy_Zone'][1]:.2f}**")
        col4.markdown(f"**추천 매도 구간:** \n**{repo['Sell_Zone'][0]:.2f} ~ {repo['Sell_Zone'][1]:.2f}**")
        col4.error(f"⚠️ **손절가:** {repo['StopLoss']:.2f}")


    # --- 메인 차트 (Plotly로 고도화) ---
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.03, subplot_titles=('Price', 'Volume/RSI'), 
                            row_width=[0.3, 0.7])

        # 1. 캔들차트
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Market'), row=1, col1)
        
        # 2. 볼린저 밴드
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_Upper'], line=dict(color='gray', width=1, dash='dash'), name='BB Upper'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_Lower'], line=dict(color='gray', width=1, dash='dash'), fill='tonexty', fillcolor='rgba(128, 128, 128, 0.1)', name='BB Lower'), row=1, col=1)

        # 3. 빗각 추세선 및 삼각수렴 시각화
        if top_line and bot_line:
            # trendln이 반환한 데이터로 추세선 x, y값 계산
            x_top = np.array([df.index[top_line[0][0]], df.index[top_line[0][-1]]])
            y_top = np.array([top_line[2][0], top_line[2][-1]])
            fig.add_trace(go.Scatter(x=x_top, y=y_top, mode='lines', line=dict(color='red', width=2), name='상단 추세선'), row=1, col=1)

            x_bot = np.array([df.index[bot_line[0][0]], df.index[bot_line[0][-1]]])
            y_bot = np.array([bot_line[2][0], bot_line[2][-1]])
            fig.add_trace(go.Scatter(x=x_bot, y=y_bot, mode='lines', line=dict(color='blue', width=2), name='하단 추세선'), row=1, col=1)

        # 4. 스마트 매수 신호 표시 (우리가 만들었던 로직)
        buy_signals = df[df['Smart_Buy_Signal'] == 1]
        fig.add_trace(go.Scatter(x=buy_signals.index, y=buy_signals['Close'] * 0.97, mode='markers', marker=dict(symbol='triangle-up', size=12, color='green'), name='스마트 매수 신호'), row=1, col=1)

        # 5. 거래량 및 RSI
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color='blue'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI', line=dict(color='purple')), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=[70]*len(df), mode='lines', line=dict(color='red', width=1, dash='dot'), showlegend=False), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=[30]*len(df), mode='lines', line=dict(color='green', width=1, dash='dot'), showlegend=False), row=2, col=1)

        fig.update_layout(xaxis_rangeslider_visible=False, height=800, template='plotly_dark')
        st.plotly_chart(fig, use_container_width=True)

    # --- 백데이터 근거값 (이미지처럼 하단에 구성) ---
        st.markdown(f"## 🔍 백데이터 근거값 및 실시간 알림")
        
        # 실시간 스마트 알림
        col_msg1, col_msg2 = st.columns(2)
        if is_smart_buy:
            col_msg1.success(f"🔔 [실시간 스마트 알림] {symbol_to_analyze} ({code}): RSI 과매도 + BB 하단 + 거래량 동반 매수 신호 포착!")
        if is_elliott_buy:
            col_msg2.info(f"🔔 [엘리어트 파동 알림] {symbol_to_analyze} ({code}): 엘리어트 2파 눌림목 매수 구간 진입!")

        # 상세 백데이터 테이블
        detail_data = {
            '지표명': ['RSI (14일)', '볼린저밴드 상단', '볼린저밴드 하단', '주요 매물대(POC)', '추천 매수 하한가', '추천 매수 상한가', '손절가'],
            '현재값/구간': [f"{current_rsi:.1f}", f"{df['BB_Upper'].iloc[-1]:.2f}", f"{df['BB_Lower'].iloc[-1]:.2f}", f"{repo['POC']:.2f}", f"{repo['Buy_Zone'][0]:.2f}", f"{repo['Buy_Zone'][1]:.2f}", f"{repo['StopLoss']:.2f}"]
        }
        st.table(pd.DataFrame(detail_data).set_index('지표명'))

    else:
        st.error(st.session_state['error_msg'] if 'error_msg' in st.session_state else "데이터를 불러오는 데 실패했습니다.")
