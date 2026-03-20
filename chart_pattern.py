import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from scipy.signal import find_peaks
import feedparser
import urllib.parse

# ==========================================
# 1. UI/UX: 프리미엄 다크 테마 & 모바일 최적화
# ==========================================
st.set_page_config(layout="wide", page_title="AI 프리미엄 퀀트", page_icon="👑")

st.markdown("""
    <style>
    .main { background-color: #0E1117; color: #FFFFFF; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { font-size: 1.1rem; font-weight: bold; color: #888; }
    .stTabs [aria-selected="true"] { color: #00FF00 !important; border-bottom-color: #00FF00 !important; }
    .ai-report { background: #1E1E1E; padding: 20px; border-radius: 10px; border-left: 5px solid #00FF00; margin-bottom: 20px; line-height: 1.6;}
    
    /* 가격 안내 박스 스타일 */
    .price-card {
        background: #262730;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        border: 1px solid #444;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .price-label { color: #999; font-size: 0.9rem; margin-bottom: 5px; }
    .price-value { font-size: 1.6rem; font-weight: 800; }
    
    div[data-testid="stMetricValue"] { font-size: 1.6rem !important; font-weight: 800; color: #00FF00; }
    
    @media (max-width: 768px) {
        .price-value { font-size: 1.2rem; }
        .stTabs [data-baseweb="tab"] { font-size: 0.9rem; }
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 스마트 검색 엔진 (대소문자/공백 무시)
# ==========================================
@st.cache_data(ttl=86400)
def load_krx_listing():
    return fdr.StockListing('KRX')

krx_df = load_krx_listing()

def get_ticker_from_name(query):
    query = query.strip()
    if query.isdigit() and len(query) == 6: return query
    query_clean = query.replace(" ", "").upper()
    match = krx_df[krx_df['Name'].str.replace(" ", "", regex=False).str.upper() == query_clean]
    if not match.empty: return match.iloc[0]['Code']
    us_map = {"테슬라": "TSLA", "애플": "AAPL", "엔비디아": "NVDA"}
    return us_map.get(query, query.upper())

# ==========================================
# 3. 퀀트 데이터 & 지표 연산 코어
# ==========================================
@st.cache_data(ttl=60)
def load_and_calc_data(symbol, p):
    try:
        today = datetime.today()
        days_map = {"3mo": 90, "6mo": 180, "1y": 365, "2y": 730}
        start_date = today - timedelta(days=days_map.get(p, 180))
        df = fdr.DataReader(symbol, start_date)
        if df.empty or len(df) < 30: return None
        
        # 지표 계산
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MACD'] = df['Close'].ewm(span=12).mean() - df['Close'].ewm(span=26).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD'].ewm(span=9).mean()
        low_min, high_max = df['Low'].rolling(14).min(), df['High'].rolling(14).max()
        df['Stoch_K'] = 100 * ((df['Close'] - low_min) / (high_max - low_min))
        
        # 파동 탐지
        peaks, _ = find_peaks(df['High'].values, distance=10, prominence=df['High'].std()*0.3)
        valleys, _ = find_peaks(-df['Low'].values, distance=10, prominence=df['Low'].std()*0.3)
        
        # AI 점수 및 백테스팅 포지션
        df['AI_Score'] = 50
        df.loc[df['Stoch_K'] < 20, 'AI_Score'] += 20
        df.loc[df['Stoch_K'] > 80, 'AI_Score'] -= 20
        df.loc[df['Close'] > df['MA20'], 'AI_Score'] += 15
        df.loc[df['Close'] <= df['MA20'], 'AI_Score'] -= 10
        df.loc[df['MACD_Hist'] > 0, 'AI_Score'] += 15
        df.loc[df['MACD_Hist'] <= 0, 'AI_Score'] -= 10
        df['AI_Score'] = df['AI_Score'].clip(0, 100)
        
        df['Position'] = np.nan
        df.loc[df['AI_Score'] >= 70, 'Position'] = 1
        df.loc[df['AI_Score'] <= 40, 'Position'] = 0
        df['Position'] = df['Position'].ffill().fillna(0)
        
        df['Daily_Return'] = df['Close'].pct_change()
        df['Strategy_Return'] = df['Position'].shift(1) * df['Daily_Return']
        df['Cum_Market'] = (1 + df['Daily_Return']).cumprod() * 100
        df['Cum_Strategy'] = (1 + df['Strategy_Return']).cumprod() * 100
        
        return df, peaks, valleys
    except: return None

# ==========================================
# 4. 메인 대시보드 출력
# ==========================================
st.sidebar.title("⚙️ 시스템 설정")
user_input = st.sidebar.text_input("종목명 검색", value="SK하이닉스")
ticker = get_ticker_from_name(user_input)
period = st.sidebar.select_slider("조회 기간", options=["3mo", "6mo", "1y", "2y"], value="6mo")

result = load_and_calc_data(ticker, period)

if result:
    df, peaks, valleys = result
    curr_p = df['Close'].iloc[-1]
    
    # --- [핵심] 매수/매도/손절가 가이드 계산 ---
    # 1. 매수가 가이드: 현재가 혹은 최근 20일선 부근 진입 추천
    buy_guide = df['MA20'].iloc[-1] 
    
    # 2. 목표가(매도가): 최근 고점 파동의 저항선
    target_p = df['High'].iloc[peaks[-1]] if len(peaks) > 0 else curr_p * 1.15
    
    # 3. 손절가: 최근 저점 파동의 지지선
    stop_p = df['Low'].iloc[valleys[-1]] if len(valleys) > 0 else curr_p * 0.92
    
    # UI 상단 요약
    st.metric(f"{user_input} 현재가", f"{curr_p:,.0f} 원", f"{((curr_p - df['Close'].iloc[-2])/df['Close'].iloc[-2]*100):+.2f}%")

    tab1, tab2, tab3 = st.tabs(["📊 프리미엄 차트", "🧠 AI 리포트 & 가격전략", "📈 백테스팅 검증"])

    with tab1:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.75, 0.25])
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="주가"), row=1, col=1)
        
        # 차트 위에 가이드 라인 표시
        fig.add_hline(y=target_p, line_dash="dash", line_color="#00FF00", annotation_text="목표가(익절)", row=1, col=1)
        fig.add_hline(y=stop_p, line_dash="dash", line_color="#FF4B4B", annotation_text="손절가", row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name="20일선(매수기준)", line=dict(color='orange', width=1)), row=1, col=1)

        colors = ['red' if val < 0 else 'green' for val in df['MACD_Hist']]
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], name="MACD", marker_color=colors), row=2, col=1)
        fig.update_layout(height=550, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        # --- 가이드 가격 박스 ---
        st.subheader("🎯 AI 퀀트 매매 전략")
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown(f"<div class='price-card'><div class='price-label'>🔵 권장 매수가</div><div class='price-value' style='color:#00BFFF;'>{buy_guide:,.0f}</div></div>", unsafe_allow_html=True)
        with c2: st.markdown(f"<div class='price-card'><div class='price-label'>🟢 1차 목표가</div><div class='price-value' style='color:#00FF00;'>{target_p:,.0f}</div></div>", unsafe_allow_html=True)
        with c3: st.markdown(f"<div class='price-card'><div class='price-label'>🔴 필수 손절가</div><div class='price-value' style='color:#FF4B4B;'>{stop_p:,.0f}</div></div>", unsafe_allow_html=True)
        
        # AI 온도계
        ai_score = df['AI_Score'].iloc[-1]
        st.write("")
        st.subheader(f"🌡️ AI 매수 매력도 점수: {ai_score:.0f}점")
        st.progress(ai_score/100)
        
        st.markdown("<div class='ai-report'>", unsafe_allow_html=True)
        st.markdown(f"#### 🔍 {user_input} 분석 결과")
        if ai_score >= 70: st.success("✅ **[강력 매수 신호]** 모든 지표가 우상향을 가리키고 있습니다. 목표가까지 홀딩을 권장합니다.")
        elif ai_score >= 40: st.info("🟡 **[관망 및 중립]** 현재 구간은 지지선을 확인하며 분할 매수할 타이밍입니다.")
        else: st.error("🚨 **[위험 및 매도]** 지표가 과열되었거나 지지선이 무너졌습니다. 손절가를 반드시 준수하세요.")
        st.markdown("</div>", unsafe_allow_html=True)

    with tab3:
        st.subheader("📉 과거 전략 검증 (백테스팅)")
        m_ret, s_ret = df['Cum_Market'].iloc[-1]-100, df['Cum_Strategy'].iloc[-1]-100
        st.write(f"과거 {period}간 **단순보유: {m_ret:+.2f}%** | **AI전략: {s_ret:+.2f}%**")
        
        fig_bt = go.Figure()
        fig_bt.add_trace(go.Scatter(x=df.index, y=df['Cum_Market'], name="단순 보유", line=dict(color='gray')))
        fig_bt.add_trace(go.Scatter(x=df.index, y=df['Cum_Strategy'], name="AI 퀀트", line=dict(color='#00FF00')))
        
        # AI 점수 변화도 함께 표시
        fig_bt.add_trace(go.Scatter(x=df.index, y=df['AI_Score'], name="AI 점수", yaxis="y2", line=dict(color='yellow', width=1, dash='dot')))
        fig_bt.update_layout(height=400, template="plotly_dark", yaxis2=dict(title="AI Score", overlaying="y", side="right", range=[0, 100]))
        st.plotly_chart(fig_bt, use_container_width=True)

else: st.error("데이터 로드 실패!")
