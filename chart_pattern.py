import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from scipy.signal import find_peaks

# ==========================================
# 1. UI/UX 전면 개편 & 모바일 최적화 레이아웃
# ==========================================
st.set_page_config(layout="wide", page_title="AI 프리미엄 퀀트", page_icon="👑")
st.markdown("""
    <style>
    .main { background-color: #0E1117; color: #FFFFFF; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { font-size: 1.1rem; font-weight: bold; color: #888; }
    .stTabs [aria-selected="true"] { color: #00FF00 !important; border-bottom-color: #00FF00 !important; }
    .ai-report { background: #1E1E1E; padding: 20px; border-radius: 10px; border-left: 5px solid #00FF00; margin-bottom: 20px; line-height: 1.6;}
    div[data-testid="stMetricValue"] { font-size: 1.6rem !important; font-weight: 800; color: #00FF00; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 스마트 검색 엔진 (FinanceDataReader 기반 전종목 커버)
# ==========================================
@st.cache_data(ttl=86400) # 하루 단위로 상장 목록 캐싱
def load_krx_listing():
    return fdr.StockListing('KRX')

krx_df = load_krx_listing()

def get_ticker_from_name(query):
    query = query.strip()
    # 1. 숫자 6자리 코드 처리
    if query.isdigit() and len(query) == 6: 
        return query
    # 2. 한국 종목 한글 검색
    match = krx_df[krx_df['Name'] == query]
    if not match.empty: 
        return match.iloc[0]['Code']
    # 3. 주요 해외 주식 매핑
    us_map = {"테슬라": "TSLA", "애플": "AAPL", "엔비디아": "NVDA", "마이크로소프트": "MSFT"}
    return us_map.get(query, query.upper())

# ==========================================
# 3. 사이드바: 설정 및 포트폴리오
# ==========================================
st.sidebar.title("⚙️ 시스템 설정")

quick_tickers = ["직접 입력...", "삼성전자", "풍산", "한화솔루션", "테슬라", "애플", "엔비디아"]
selected_quick = st.sidebar.selectbox("⭐ 관심 종목 퀵뷰", quick_tickers)
default_input = "풍산" if selected_quick == "직접 입력..." else selected_quick
user_input = st.sidebar.text_input("종목명/코드 검색", value=default_input)

ticker = get_ticker_from_name(user_input)
st.sidebar.caption(f"🔍 자동 변환된 코드: **{ticker}**")
period = st.sidebar.select_slider("조회 기간", options=["3mo", "6mo", "1y", "2y"], value="6mo")

st.sidebar.markdown("---")
st.sidebar.subheader("🧮 포트폴리오 시뮬레이터")
buy_p = st.sidebar.number_input("평균 단가", value=0.0, step=0.1)
qty = st.sidebar.number_input("보유 수량", value=0, step=1)

# ==========================================
# 4. 데이터 엔진 & 퀀트 코어 로직
# ==========================================
@st.cache_data(ttl=60)
def load_and_calc_data(symbol, p):
    try:
        # 날짜 범위 설정
        today = datetime.today()
        days_map = {"3mo": 90, "6mo": 180, "1y": 365, "2y": 730}
        start_date = today - timedelta(days=days_map.get(p, 180))
        
        # 주가 데이터 로드
        df = fdr.DataReader(symbol, start_date)
        if df.empty or len(df) < 30: return None
        
        # 1. 추세 지표 (이동평균선)
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        
        # 2. 모멘텀 지표 (MACD)
        df['MACD'] = df['Close'].ewm(span=12).mean() - df['Close'].ewm(span=26).mean()
        df['Signal'] = df['MACD'].ewm(span=9).mean()
        df['MACD_Hist'] = df['MACD'] - df['Signal']
        
        # 3. 과매수/과매도 지표 (Stochastic)
        low_min = df['Low'].rolling(window=14).min()
        high_max = df['High'].rolling(window=14).max()
        df['Stoch_K'] = 100 * ((df['Close'] - low_min) / (high_max - low_min))
        df['Stoch_D'] = df['Stoch_K'].rolling(window=3).mean()
        
        # 4. 캔들 패턴 데이터
        df['Body'] = abs(df['Close'] - df['Open'])
        df['Upper_Shadow'] = df['High'] - df[['Close', 'Open']].max(axis=1)
        df['Lower_Shadow'] = df[['Close', 'Open']].min(axis=1) - df['Low']
        
        # 5. 엘리어트 파동(고점/저점) 탐지 로직
        # prominence 값을 동적으로 설정하여 의미 있는 파동만 추출
        prominence_high = df['High'].std() * 0.3
        prominence_low = df['Low'].std() * 0.3
        
        peaks, _ = find_peaks(df['High'].values, distance=10, prominence=prominence_high)
        valleys, _ = find_peaks(-df['Low'].values, distance=10, prominence=prominence_low)
        
        return df, peaks, valleys
    except Exception as e:
        return None

# ==========================================
# 5. 메인 대시보드 시각화 & AI 리포트
# ==========================================
result = load_and_calc_data(ticker, period)

if result is not None:
    df, peaks, valleys = result
    
    # --- 상단 메트릭 요약 ---
    curr_p = df['Close'].iloc[-1]
    prev_p = df['Close'].iloc[-2]
    change = ((curr_p - prev_p) / prev_p) * 100

    col1, col2, col3 = st.columns(3)
    price_format = f"{curr_p:,.0f}" if curr_p > 1000 else f"{curr_p:,.2f}"
    col1.metric(f"{user_input} 현재가", price_format, f"{change:+.2f}%")
    
    if buy_p > 0 and qty > 0:
        profit = ((curr_p - buy_p) / buy_p) * 100
        total_val = curr_p * qty
        col2.metric("보유 수익률", f"{profit:+.2f}%")
        col3.metric("평가 금액", f"{total_val:,.0f}")

    # --- 탭 구성 ---
    tab1, tab2 = st.tabs(["📊 프리미엄 차트 (패턴/추세)", "🧠 AI 심층 분석 리포트"])

    with tab1:
        # Plotly 서브플롯 (주가+추세선 영역 / MACD 영역)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.75, 0.25])

        # 1. 캔들스틱 차트
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="주가"), row=1, col=1)
        
        # 2. 이동평균선
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name="20일선", line=dict(color='orange', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], name="60일선", line=dict(color='cyan', width=1)), row=1, col=1)
        
        # 3. 파동 꼭짓점 시각화 (엘리어트)
        if len(peaks) > 0:
            fig.add_trace(go.Scatter(x=df.index[peaks], y=df['High'].iloc[peaks], mode='markers', 
                                     marker=dict(color='red', size=8, symbol='triangle-down'), name="고점 파동"), row=1, col=1)
        if len(valleys) > 0:
            fig.add_trace(go.Scatter(x=df.index[valleys], y=df['Low'].iloc[valleys], mode='markers', 
                                     marker=dict(color='lime', size=8, symbol='triangle-up'), name="저점 파동"), row=1, col=1)

        # 4. 삼각수렴 / 빗각 추세선 그리기
        if len(peaks) >= 2:
            recent_peaks = peaks[-2:]
            fig.add_trace(go.Scatter(x=df.index[recent_peaks], y=df['High'].iloc[recent_peaks], mode='lines', 
                                     line=dict(color='pink', width=2, dash='dot'), name="상단 저항선(빗각)"), row=1, col=1)
        if len(valleys) >= 2:
            recent_valleys = valleys[-2:]
            fig.add_trace(go.Scatter(x=df.index[recent_valleys], y=df['Low'].iloc[recent_valleys], mode='lines', 
                                     line=dict(color='lightgreen', width=2, dash='dot'), name="하단 지지선(빗각)"), row=1, col=1)

        # 5. 하단 보조지표 (MACD)
        colors = ['red' if val < 0 else 'green' for val in df['MACD_Hist']]
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], name="MACD 히스토그램", marker_color=colors), row=2, col=1)

        fig.update_layout(height=700, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.markdown("<div class='ai-report'>", unsafe_allow_html=True)
        st.subheader(f"💡 {user_input} 종합 퀀트 분석 리포트")
        
        # A. 패턴 및 추세 분석 (삼각수렴, 엘리어트 파동)
        st.markdown("#### 📐 추세 및 파동 (엘리어트 & 빗각)")
        if len(peaks) >= 2 and len(valleys) >= 2:
            peak_slope = df['High'].iloc[peaks[-1]] - df['High'].iloc[peaks[-2]]
            valley_slope = df['Low'].iloc[valleys[-1]] - df['Low'].iloc[valleys[-2]]
            
            if peak_slope < 0 and valley_slope > 0:
                st.warning("⚠️ **[대칭 삼각수렴]** 고점은 낮아지고 저점은 높아지는 패턴입니다. 에너지가 응축되고 있으며, 조만간 상/하방 중 한 곳으로 큰 방향성이 터질 확률이 높습니다.")
            elif peak_slope > 0 and valley_slope > 0:
                st.success("✅ **[상승 채널/파동]** 고점과 저점을 지속적으로 높여가는 전형적인 상승 엘리어트 파동 국면입니다.")
            elif peak_slope < 0 and valley_slope < 0:
                st.error("🚨 **[하락 채널/파동]** 고점과 저점이 모두 낮아지고 있습니다. 섣부른 물타기를 자제하고, 상단 저항선(빗각) 돌파를 확인해야 합니다.")
            else:
                st.write("현재 명확한 채널 방향성보다는 박스권 혹은 확장형 패턴을 보이고 있습니다.")
        else:
            st.write("파동을 분석하기에 데이터 변동성이 충분하지 않습니다.")

        # B. 캔들 패턴 분석
        st.markdown("#### 🕯️ 최근 캔들 패턴 (프라이스 액션)")
        recent_candle = df.iloc[-1]
        body_size = recent_candle['Body']
        
        if recent_candle['Lower_Shadow'] > body_size * 2 and recent_candle['Upper_Shadow'] < body_size:
            st.write("🔨 **[망치형 캔들 포착]** 마지막 거래일에 아래꼬리가 긴 망치형 캔들이 발생했습니다. 바닥권이라면 강한 매수세가 유입되었다는 반등 신호입니다.")
        elif body_size < (recent_candle['High'] - recent_candle['Low']) * 0.1:
            st.write("➕ **[도지형 캔들 포착]** 매수세와 매도세가 팽팽하게 맞서는 도지(Doji) 캔들이 떴습니다. 단기적인 추세 전환점이 될 수 있습니다.")
        else:
            st.write("현재 특이한 반전 캔들 패턴(망치형, 도지형 등)은 관찰되지 않고 일반적인 흐름을 보이고 있습니다.")

        # C. 보조지표 분석 (스토캐스틱, MACD, 이동평균선)
        st.markdown("#### 📊 보조지표 시그널")
        last_k = df['Stoch_K'].iloc[-1]
        
        # 스토캐스틱
        if last_k > 80:
            st.warning(f"• **스토캐스틱**: {last_k:.1f}로 80을 초과한 **과매수 구간**입니다. 단기 조정에 유의하세요.")
        elif last_k < 20:
            st.success(f"• **스토캐스틱**: {last_k:.1f}로 20 미만인 **과매도 구간**입니다. 기술적 반등 가능성이 높습니다.")
        else:
            st.write(f"• **스토캐스틱**: {last_k:.1f}로 중립 구간에 위치해 있습니다.")
            
        # MACD
        if df['MACD_Hist'].iloc[-1] > 0 and df['MACD_Hist'].iloc[-2] < 0:
            st.success("• **MACD**: 히스토그램이 양(+)으로 전환되며 **골든크로스 매수 신호**가 발생했습니다.")
        elif df['MACD_Hist'].iloc[-1] < 0 and df['MACD_Hist'].iloc[-2] > 0:
            st.error("• **MACD**: 히스토그램이 음(-)으로 전환되며 **데드크로스 매도 신호**가 발생했습니다.")
        
        # 이동평균선 추세
        if curr_p > df['MA20'].iloc[-1]:
            st.write("• **이동평균선**: 주가가 20일선 위에 있어 **단기 상승 흐름**이 유효합니다.")
        else:
            st.write("• **이동평균선**: 주가가 20일선 아래에 머물러 있어 **단기 하방 압력**을 받고 있습니다.")

        st.markdown("</div>", unsafe_allow_html=True)

else:
    st.error("데이터를 불러오지 못했습니다. 종목이 존재하지 않거나 상장된 지 30일이 지나지 않았을 수 있습니다.")
