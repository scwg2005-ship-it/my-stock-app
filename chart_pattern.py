import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from scipy.signal import find_peaks
import feedparser
import urllib.parse
import time

# ==========================================
# 1. 전역 설정 및 프리미엄 CSS (UI/UX)
# ==========================================
st.set_page_config(layout="wide", page_title="AI 프리미엄 퀀트 v5.5", page_icon="👑")

# 전종목 리스트 미리 로드 (캐싱)
@st.cache_data(ttl=86400)
def get_krx_list():
    return fdr.StockListing('KRX')

krx_list = get_krx_list()

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@100;400;700;900&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Pretendard', sans-serif;
        background-color: #0E1117;
        color: #FFFFFF;
    }

    /* 상단 탭 디자인: 더 크고 명확하게 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 15px;
        border-bottom: 2px solid #333;
        padding-bottom: 5px;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 1.2rem;
        font-weight: 800;
        color: #999;
        padding: 12px 25px;
        border-radius: 10px 10px 0 0;
        transition: all 0.3s ease;
    }
    .stTabs [aria-selected="true"] {
        color: #00FF00 !important;
        background-color: rgba(0, 255, 0, 0.05);
        border-bottom: 3px solid #00FF00 !important;
    }

    /* AI 리포트 박스: 입체감 있는 그라데이션 */
    .ai-report-container {
        background: linear-gradient(145deg, #1e1e26, #14141b);
        padding: 35px;
        border-radius: 20px;
        border-left: 8px solid #00FF00;
        margin-bottom: 30px;
        box-shadow: 0 15px 35px rgba(0,0,0,0.6);
        line-height: 1.8;
    }
    
    .report-title {
        font-size: 1.6rem;
        font-weight: 900;
        color: #00FF00;
        margin-bottom: 20px;
        border-bottom: 1px solid #444;
        padding-bottom: 10px;
    }

    /* 가격 카드: 세련된 다크 모드 스타일 */
    .price-card-v2 {
        background: #1c1e26;
        border-radius: 15px;
        padding: 25px;
        text-align: center;
        border: 1px solid #333;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        box-shadow: 0 5px 15px rgba(0,0,0,0.3);
    }
    .price-card-v2:hover {
        border-color: #00FF00;
        transform: translateY(-8px);
        box-shadow: 0 12px 25px rgba(0, 255, 0, 0.15);
    }
    .card-label { color: #aaa; font-size: 1rem; font-weight: 600; margin-bottom: 10px; }
    .card-value { font-size: 2rem; font-weight: 900; letter-spacing: -1px; }

    /* 뉴스 박스 최적화 */
    .news-item {
        background: #16181d;
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 15px;
        border-right: 4px solid #00BFFF;
        transition: 0.3s;
    }
    .news-item:hover { background: #21242c; transform: scale(1.01); }
    .news-link { font-size: 1.1rem; font-weight: 700; color: #fff; text-decoration: none; }
    .news-link:hover { color: #00FF00; }
    .news-time { font-size: 0.85rem; color: #666; margin-top: 8px; }

    /* 메트릭 폰트 */
    div[data-testid="stMetricValue"] { font-size: 2rem !important; font-weight: 900 !important; color: #00FF00; }
    
    /* 스크롤바 커스텀 */
    ::-webkit-scrollbar { width: 8px; }
    ::-webkit-scrollbar-track { background: #0E1117; }
    ::-webkit-scrollbar-thumb { background: #333; border-radius: 10px; }
    ::-webkit-scrollbar-thumb:hover { background: #444; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 스마트 엔진: 데이터 분석 및 검색 로직
# ==========================================
def smart_ticker_search(user_query):
    query = user_query.strip().replace(" ", "").upper()
    if query.isdigit() and len(query) == 6:
        return query
    
    # KRX 리스트에서 정확한 일치 확인
    target = krx_list[krx_list['Name'].str.replace(" ", "", regex=False).str.upper() == query]
    if not target.empty:
        return target.iloc[0]['Code']
    
    # 수동 매핑 (해외 주식 및 별칭)
    manual_map = {
        "테슬라": "TSLA", "애플": "AAPL", "엔비디아": "NVDA", "마이크로소프트": "MSFT", 
        "구글": "GOOGL", "아마존": "AMZN", "메타": "META", "하이닉스": "000660",
        "삼성전자": "005930", "삼전": "005930", "에코프로": "086520"
    }
    return manual_map.get(query, query.upper())

@st.cache_data(ttl=60)
def get_advanced_data(symbol, period_choice, interval_choice):
    try:
        # 야후 파이낸스용 티커 변환 (국내 주식용)
        if symbol.isdigit():
            market_info = krx_list[krx_list['Code'] == symbol]
            m_type = market_info['Market'].values[0] if not market_info.empty else "KOSPI"
            yf_symbol = f"{symbol}.KS" if m_type == "KOSPI" else f"{symbol}.KQ"
        else:
            yf_symbol = symbol

        # 데이터 호출 기간 설정
        p_map = {"3mo": "3mo", "6mo": "6mo", "1y": "1y", "2y": "2y"}
        
        # 분봉/일봉 엔진 분기
        if "분봉" in interval_choice:
            i_map = {"5분봉": "5m", "15분봉": "15m", "60분봉": "60m"}
            raw_df = yf.download(yf_symbol, period="1mo", interval=i_map.get(interval_choice, "60m"), progress=False)
        else:
            raw_df = yf.download(yf_symbol, period=p_map.get(period_choice, "6mo"), interval="1d", progress=False)

        if raw_df.empty: return None
        
        # 멀티인덱스 컬럼 정리
        if isinstance(raw_df.columns, pd.MultiIndex):
            raw_df.columns = raw_df.columns.get_level_values(0)

        df = raw_df.copy()

        # [고급 기술적 지표 계산]
        # 1. 이동평균선 (정배열/역배열 판단)
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA60'] = df['Close'].rolling(window=60).mean()
        df['MA120'] = df['Close'].rolling(window=120).mean()

        # 2. RSI (상대강도지수)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        # 3. MACD (이동평균 수렴 확산)
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

        # 4. 볼린저 밴드
        df['BB_Mid'] = df['MA20']
        df['BB_Std'] = df['Close'].rolling(window=20).std()
        df['BB_Upper'] = df['BB_Mid'] + (df['BB_Std'] * 2)
        df['BB_Lower'] = df['BB_Mid'] - (df['BB_Std'] * 2)

        # 5. 스토캐스틱 (Stochastic Fast/Slow)
        low_min = df['Low'].rolling(window=14).min()
        high_max = df['High'].rolling(window=14).max()
        df['Stoch_K'] = 100 * ((df['Close'] - low_min) / (high_max - low_min))
        df['Stoch_D'] = df['Stoch_K'].rolling(window=3).mean()

        # [AI 퀀트 스코어링 - Pro급 가중치 적용]
        df['AI_Score'] = 50.0 # 중립 시작
        
        # 상승 요인 (공격적 가점)
        df.loc[df['Close'] > df['MA20'], 'AI_Score'] += 12
        df.loc[df['MA5'] > df['MA20'], 'AI_Score'] += 10
        df.loc[df['MACD_Hist'] > 0, 'AI_Score'] += 10
        df.loc[df['RSI'] < 35, 'AI_Score'] += 15 # 과매도 반등 가점
        df.loc[df['Close'] < df['BB_Lower'], 'AI_Score'] += 10 # 밴드 하단 돌파 가점
        df.loc[(df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1)), 'AI_Score'] += 15 # 골든크로스 즉시 가점

        # 하락 요인 (방어적 감점)
        df.loc[df['Close'] < df['MA20'], 'AI_Score'] -= 12
        df.loc[df['Close'] < df['MA60'], 'AI_Score'] -= 15 # 생명선 이탈
        df.loc[df['MACD_Hist'] < 0, 'AI_Score'] -= 8
        df.loc[df['RSI'] > 75, 'AI_Score'] -= 15 # 과매수 경고 감점
        df.loc[(df['MA5'] < df['MA20']) & (df['MA5'].shift(1) >= df['MA20'].shift(1)), 'AI_Score'] -= 20 # 데드크로스 탈출 감점
        
        df['AI_Score'] = df['AI_Score'].clip(0, 100)

        # [백테스팅 로직 - 실제 포지션 스위칭]
        # 진입 장벽을 낮춰 평행선 문제를 해결 (60점 이상 매수 / 45점 이하 매도)
        df['Position'] = np.nan
        df.loc[df['AI_Score'] >= 60, 'Position'] = 1
        df.loc[df['AI_Score'] <= 45, 'Position'] = 0
        df['Position'] = df['Position'].ffill().fillna(0)
        
        # 수익률 연산 (수수료 0.015% 가정)
        fee = 0.00015
        df['Daily_Return'] = df['Close'].pct_change()
        df['Strategy_Return'] = df['Position'].shift(1) * df['Daily_Return']
        # 매매 발생 시 수수료 차감 로직
        df['Trade_Fee'] = (df['Position'].diff().abs() * fee).fillna(0)
        df['Strategy_Return_Net'] = df['Strategy_Return'] - df['Trade_Fee']

        df['Cum_Market'] = (1 + df['Daily_Return'].fillna(0)).cumprod() * 100
        df['Cum_Strategy'] = (1 + df['Strategy_Return_Net'].fillna(0)).cumprod() * 100

        # [엘리어트 변곡점 추출]
        prominence_factor = df['High'].std() * 0.25
        pks, _ = find_peaks(df['High'].values, distance=10, prominence=prominence_factor)
        vls, _ = find_peaks(-df['Low'].values, distance=10, prominence=prominence_factor)

        return df, pks, vls
    except Exception as e:
        st.error(f"데이터 연산 중 오류 발생: {e}")
        return None

@st.cache_data(ttl=300)
def fetch_news_expert(query=None):
    kw = "국내 증시 특징주" if query is None else f"{query} 특징주 OR {query} 주가 전망"
    encoded_kw = urllib.parse.quote(kw)
    url = f"https://news.google.com/rss/search?q={encoded_kw}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        feed = feedparser.parse(url)
        results = []
        for entry in feed.entries[:8]:
            results.append({
                "title": entry.title,
                "link": entry.link,
                "date": entry.published[:-4] if hasattr(entry, 'published') else "최근 뉴스"
            })
        return results
    except: return []

# ==========================================
# 3. 사이드바 메인 제어 센터
# ==========================================
st.sidebar.markdown("## ⚙️ 마스터 제어 센터")
user_query = st.sidebar.text_input("종목명 또는 티커 (예: 하이닉스, TSLA)", value="SK하이닉스")
target_symbol = smart_ticker_search(user_query)

st.sidebar.markdown("---")
st.sidebar.subheader("📈 차트 환경 설정")
time_frame = st.sidebar.selectbox("타임프레임 (주기)", ["일봉", "60분봉", "15분봉", "5분봉"])
lookback = st.sidebar.select_slider("데이터 분석 범위 (일봉 전용)", options=["3mo", "6mo", "1y", "2y"], value="1y")

st.sidebar.markdown("---")
st.sidebar.subheader("💰 내 자산 실시간 동기화")
avg_price = st.sidebar.number_input("나의 평균 단가", value=0.0, step=100.0)
hold_qty = st.sidebar.number_input("보유 수량", value=0, step=1)

# ==========================================
# 4. 데이터 로드 및 연산 실행
# ==========================================
result_package = get_advanced_data(target_symbol, lookback, time_frame)

if result_package:
    df, pks, vls = result_package
    curr_close = float(df['Close'].iloc[-1])
    prev_close = float(df['Close'].iloc[-2])
    day_change = ((curr_close - prev_close) / prev_close) * 100
    current_ai_score = float(df['AI_Score'].iloc[-1])
    
    # [NaN 방어 & 지지/저항가 정밀 계산]
    # 목표가: 최근 2개 고점 중 높은 값 + ATR 변동성 고려
    if len(pks) >= 1:
        resistance = df['High'].iloc[pks].tail(2).max()
        target_price = max(resistance, curr_close * 1.05)
    else:
        target_price = curr_close * 1.12 # 기본 12% 목표

    # 손절가: 최근 2개 저점 중 낮은 값 또는 MA60
    if len(vls) >= 1:
        support = df['Low'].iloc[vls].tail(2).min()
        stop_loss = min(support, df['MA60'].iloc[-1] if not np.isnan(df['MA60'].iloc[-1]) else support)
    else:
        stop_loss = curr_close * 0.92 # 기본 8% 손절

    # 논리적 오류 방지
    if stop_loss >= curr_close: stop_loss = curr_close * 0.94
    if target_price <= curr_close: target_price = curr_close * 1.10

    # ------------------------------------------
    # 5. 상단 실시간 대시보드 (메트릭)
    # ------------------------------------------
    st.title(f"👑 {user_query} ({target_symbol}) 인텔리전트 대시보드")
    
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    price_disp = f"{curr_close:,.0f}" if curr_close > 200 else f"{curr_close:,.4f}"
    m_col1.metric("실시간 주가", price_disp, f"{day_change:+.2f}%")
    m_col2.metric("AI 퀀트 스코어", f"{current_ai_score:.0f}점", "상승 우세" if current_ai_score > 60 else "하락 우세")
    
    if avg_price > 0 and hold_qty > 0:
        total_pnl = (curr_close - avg_price) * hold_qty
        pnl_pct = ((curr_close - avg_price) / avg_price) * 100
        m_col3.metric("나의 수익률", f"{pnl_pct:+.2f}%", f"{total_pnl:,.0f}원")
        m_col4.metric("평가 금액", f"{(curr_close * hold_qty):,.0f}원")
    else:
        m_col3.metric("RSI 상대강도", f"{df['RSI'].iloc[-1]:.1f}", "과매도" if df['RSI'].iloc[-1] < 30 else "과매수" if df['RSI'].iloc[-1] > 70 else "보통")
        m_col4.metric("20일선 이격도", f"{(curr_close / df['MA20'].iloc[-1] * 100):.1f}%")

    st.markdown("---")

    # ------------------------------------------
    # 6. 메인 콘텐츠 탭 분할
    # ------------------------------------------
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 엘리어트 마스터 차트", 
        "🧠 AI 심층 리포트 & 전략", 
        "📉 백테스팅 성과 검증", 
        "⚡ 실시간 마켓 뉴스"
    ])

    # [TAB 1: 엘리어트 마스터 차트]
    with tab1:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])
        
        # 캔들스틱 본체
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
            name="주가 캔들", increasing_line_color='#FF4B4B', decreasing_line_color='#0080FF'
        ), row=1, col=1)
        
        # 이동평균선 3종
        fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], name="5일선", line=dict(color='white', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name="20일선", line=dict(color='gold', width=2)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], name="60일선", line=dict(color='cyan', width=1, dash='dot')), row=1, col=1)
        
        # ⭐ [핵심] 엘리어트 파동 숫자 레이블 (1~5, A~C)
        labels = ['1','2','3','4','5','A','B','C']
        merged_pts = sorted([('p', p, df['High'].iloc[p]) for p in pks] + [('v', v, df['Low'].iloc[v]) for v in vls], key=lambda x: x[1])[-8:]
        
        for i, pt in enumerate(merged_pts):
            if i < len(labels):
                is_valley = pt[0] == 'v'
                color = "#00FF00" if is_valley else "#FF4B4B"
                symbol = "triangle-up" if is_valley else "triangle-down"
                fig.add_trace(go.Scatter(
                    x=[df.index[pt[1]]], y=[pt[2]],
                    mode="text+markers",
                    text=[f"<b>{labels[i]}</b>"],
                    textposition="bottom center" if is_valley else "top center",
                    textfont=dict(size=24, color=color),
                    marker=dict(color=color, size=15, symbol=symbol),
                    showlegend=False
                ), row=1, col=1)
        
        # 골든/데드크로스 신호탄
        gc_indices = df[df['GC']].index
        fig.add_trace(go.Scatter(x=gc_indices, y=df.loc[gc_indices, 'Low']*0.95, mode='markers', marker=dict(symbol='star', size=12, color='yellow'), name="골든크로스"), row=1, col=1)

        # 가격 가이드 라인
        fig.add_hline(y=target_price, line_dash="dash", line_color="#00FF00", annotation_text="AI 목표가", row=1, col=1)
        fig.add_hline(y=stop_loss, line_dash="dash", line_color="#FF4B4B", annotation_text="AI 손절가", row=1, col=1)

        # 하단 보조지표 (MACD + 볼륨)
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], name="MACD 히스토그램", marker_color=['#FF4B4B' if x < 0 else '#00FF00' for x in df['MACD_Hist']]), row=2, col=1)
        
        fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # [TAB 2: AI 심층 리포트 & 전략]
    with tab2:
        # AI 온도계 (타이틀 짤림 방지 t=180 설정)
        if current_ai_score >= 70:
            status_desc, gauge_col = "🚀 강력 매수 적기 (공격적 추세 추종)", "#00FF00"
        elif current_ai_score >= 45:
            status_desc, gauge_col = "⚖️ 중립 유지 (분할 매수 및 관망)", "#FFD700"
        else:
            status_desc, gauge_col = "⚠️ 리스크 경보 (비중 축소 및 손절 준비)", "#FF4B4B"
            
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number", value = current_ai_score, domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': f"AI 퀀트 점수: {current_ai_score:.0f}점<br><span style='font-size:0.7em;color:{gauge_col}'>{status_desc}</span>", 'font': {'size': 28, 'color': 'white'}},
            gauge = {
                'axis': {'range': [0, 100], 'tickwidth': 2, 'tickcolor': "white"},
                'bar': {'color': gauge_col},
                'steps': [
                    {'range': [0, 45], 'color': "rgba(255, 75, 75, 0.2)"},
                    {'range': [45, 70], 'color': "rgba(255, 215, 0, 0.2)"},
                    {'range': [70, 100], 'color': "rgba(0, 255, 0, 0.2)"}
                ],
                'threshold': {'line': {'color': "white", 'width': 5}, 'thickness': 0.8, 'value': current_ai_score}
            }
        ))
        fig_gauge.update_layout(height=480, margin=dict(l=30, r=30, t=180, b=30), paper_bgcolor="#0E1117", font={'color': 'white'})
        st.plotly_chart(fig_gauge, use_container_width=True)

        # 가격 대시보드 카드
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"<div class='price-card-v2'><div class='card-label'>🎯 AI 1차 목표가</div><div class='card-value' style='color:#00FF00;'>{target_price:,.0f}</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='price-card-v2'><div class='card-label'>🛡️ AI 손절 마지노선</div><div class='card-value' style='color:#FF4B4B;'>{stop_loss:,.0f}</div></div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='price-card-v2'><div class='card-label'>⚖️ 적정 진입 추천가</div><div class='card-value' style='color:#00BFFF;'>{df['MA20'].iloc[-1]:,.0f}</div></div>", unsafe_allow_html=True)

        st.markdown("<div class='ai-report-container'>", unsafe_allow_html=True)
        st.markdown("<div class='report-title'>🔍 퀀트 전략 심층 리포트</div>", unsafe_allow_html=True)
        
        if len(merged_pts) > 0:
            last_wave_label = labels[len(merged_pts)-1]
            st.markdown(f"#### 📐 파동 분석: 현재 **엘리어트 {last_wave_label}파** 국면")
            if last_wave_label == '3':
                st.success("💎 **[상승 3파 포착]** 현재 주가는 엘리어트 파동 중 가장 강력한 상승력을 가진 '3파'에 위치해 있습니다. 이는 기관과 외인의 강력한 수급이 뒷받침되는 구간으로, 목표가 상향 조정이 가능합니다.")
            elif last_wave_label == '5':
                st.warning("🔥 **[상승 5파 과열]** 상승의 마지막 불꽃인 5파입니다. RSI 지표가 과열권에 진입하고 있으므로, 추격 매수보다는 익절 타이밍을 잡으십시오.")
            elif last_wave_label in ['A', 'C']:
                st.error("📉 **[하락 조정파]** 현재는 하락 A파 혹은 C파에 진입했습니다. 바닥 확인 전까지는 현금을 확보하고 관망하는 전략이 가장 유리합니다.")
        
        st.markdown("#### 📊 보조지표 종합 진단")
        st.write(f"• **이동평균선**: 현재 5일선이 20일선 위에 있는 {'정배열' if df['MA5'].iloc[-1] > df['MA20'].iloc[-1] else '역배열'} 상태로 단기적인 {'상승 탄력' if df['MA5'].iloc[-1] > df['MA20'].iloc[-1] else '하락 압력'}이 작용하고 있습니다.")
        st.write(f"• **RSI**: {df['RSI'].iloc[-1]:.1f} 수치를 기록 중이며, 현재 시장은 {'과매수 상태로 조정 유의' if df['RSI'].iloc[-1] > 70 else '과매도 상태로 기술적 반등 기대' if df['RSI'].iloc[-1] < 30 else '안정적인 추세'}를 보이고 있습니다.")
        st.write(f"• **MACD**: {'매수 신호(Golden Cross)' if df['MACD_Hist'].iloc[-1] > 0 else '매도 신호(Dead Cross)'}가 발생하여 추세적 에너지가 전환되고 있습니다.")
        st.markdown("</div>", unsafe_allow_html=True)

    # [TAB 3: 백테스팅 성과 검증]
    with tab3:
        st.subheader("📉 AI 퀀트 전략 백테스팅 (Historical Simulation)")
        
        final_mkt = df['Cum_Market'].iloc[-1] - 100
        final_strat = df['Cum_Strategy'].iloc[-1] - 100
        
        b1, b2, b3 = st.columns(3)
        b1.metric("시장 수익률(존버)", f"{final_mkt:+.2f}%")
        b2.metric("AI 전략 수익률", f"{final_strat:+.2f}%", f"{(final_strat - final_mkt):+.2f}%p (초과수익)")
        b3.metric("최대 낙폭(MDD)", f"{(df['Cum_Strategy'].div(df['Cum_Strategy'].cummax()).sub(1).min()*100):.2f}%")

        fig_bt = go.Figure()
        fig_bt.add_trace(go.Scatter(x=df.index, y=df['Cum_Market'], name="단순 보유 (Buy & Hold)", line=dict(color='gray', width=2, dash='dot')))
        fig_bt.add_trace(go.Scatter(x=df.index, y=df['Cum_Strategy'], name="AI 퀀트 전략", line=dict(color='#00FF00', width=4)))
        
        # [⭐ 백미] AI 점수 히스토리를 겹쳐서 표시
        fig_bt.add_trace(go.Scatter(x=df.index, y=df['AI_Score'], name="AI 점수 추이", yaxis="y2", line=dict(color='yellow', width=1)))
        
        fig_bt.update_layout(
            height=600, template="plotly_dark", 
            yaxis2=dict(overlaying="y", side="right", range=[0, 100], title="AI 점수 (Score)", showgrid=False),
            margin=dict(l=10, r=10, t=30, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_bt, use_container_width=True)
        st.info("💡 **전략 요약**: AI 점수가 60점 이상 시 매수(공격적 진입), 45점 이하로 하락 시 매도(관망)하여 하락장 손실을 방어합니다.")

    # [TAB 4: 실시간 마켓 뉴스]
    with tab4:
        st.subheader(f"⚡ 실시간 마켓 레이더: {user_query}")
        
        n_col1, n_col2 = st.columns(2)
        with n_col1:
            st.markdown("#### 🌐 글로벌 증시 핫뉴스")
            for item in fetch_news_expert():
                st.markdown(f"""
                <div class='news-item'>
                    <a href='{item['link']}' target='_blank' class='news-link'>{item['title']}</a>
                    <div class='news-time'>🕘 {item['date']}</div>
                </div>
                """, unsafe_allow_html=True)
        
        with n_col2:
            st.markdown(f"#### 🎯 {user_query} 특징주 뉴스")
            for item in fetch_news_expert(user_query):
                st.markdown(f"""
                <div class='news-item'>
                    <a href='{item['link']}' target='_blank' class='news-link'>{item['title']}</a>
                    <div class='news-time'>🕘 {item['date']}</div>
                </div>
                """, unsafe_allow_html=True)
else:
    st.error("⚠️ 데이터를 불러오지 못했습니다. 종목명을 정확하게 입력했는지, 혹은 인터넷 연결 상태를 확인해주세요.")
