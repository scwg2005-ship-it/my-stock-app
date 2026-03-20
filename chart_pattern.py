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

# ==========================================
# 1. UI/UX: 최상위 프리미엄 다크 테마 & 반응형 CSS
# ==========================================
st.set_page_config(layout="wide", page_title="AI 프리미엄 퀀트 v5.0", page_icon="👑")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;700;900&display=swap');
    html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif; background-color: #0E1117; color: #FFFFFF; }
    
    /* 탭 메뉴 디자인 */
    .stTabs [data-baseweb="tab-list"] { gap: 12px; border-bottom: 1px solid #333; }
    .stTabs [data-baseweb="tab"] { font-size: 1.1rem; font-weight: 700; color: #888; padding: 10px 20px; transition: 0.3s; }
    .stTabs [aria-selected="true"] { color: #00FF00 !important; border-bottom: 2px solid #00FF00 !important; }
    
    /* 카드 및 리포트 섹션 */
    .ai-report { background: linear-gradient(145deg, #1e1e26, #14141b); padding: 30px; border-radius: 15px; border-left: 6px solid #00FF00; margin-bottom: 30px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); line-height: 1.8; }
    .price-card { background: #1a1c24; border-radius: 12px; padding: 20px; text-align: center; border: 1px solid #333; transition: 0.3s; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }
    .price-card:hover { border-color: #00FF00; transform: translateY(-5px); }
    .price-label { color: #999; font-size: 0.95rem; font-weight: 500; margin-bottom: 8px; }
    .price-val { font-size: 1.8rem; font-weight: 900; }
    
    /* 뉴스 섹션 */
    .news-box { background: #16181d; padding: 18px; border-radius: 10px; margin-bottom: 12px; border-left: 4px solid #00BFFF; transition: 0.2s; }
    .news-box:hover { background: #1f2229; }
    .news-title { font-size: 1.05rem; font-weight: 700; color: #ffffff; text-decoration: none; display: block; margin-bottom: 6px; }
    .news-title:hover { color: #00FF00; }
    .news-meta { font-size: 0.85rem; color: #777; }
    
    /* 메트릭 폰트 최적화 */
    div[data-testid="stMetricValue"] { font-size: 1.8rem !important; font-weight: 900; color: #00FF00; }
    
    /* 모바일 최적화 */
    @media (max-width: 768px) {
        .stTabs [data-baseweb="tab"] { font-size: 0.9rem; padding: 8px 10px; }
        .price-val { font-size: 1.4rem; }
        div[data-testid="stMetricValue"] { font-size: 1.4rem !important; }
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 엔진: 데이터 수집 & 스마트 검색 (FDR + YF)
# ==========================================
@st.cache_data(ttl=86400)
def load_full_krx():
    return fdr.StockListing('KRX')

full_krx = load_full_krx()

def get_smart_ticker(query):
    query = query.strip().replace(" ", "").upper()
    if query.isdigit() and len(query) == 6: return query
    match = full_krx[full_krx['Name'].str.replace(" ", "", regex=False).str.upper() == query]
    if not match.empty: return match.iloc[0]['Code']
    mapping = {"테슬라":"TSLA", "애플":"AAPL", "엔비디아":"NVDA", "마이크로소프트":"MSFT", "하이닉스":"000660", "삼전":"005930"}
    return mapping.get(query, query.upper())

@st.cache_data(ttl=60)
def fetch_master_data(symbol, p_val, i_val):
    try:
        # 1. 티커 변환 로직
        if symbol.isdigit():
            m_info = full_krx[full_krx['Code'] == symbol]
            m_type = m_info['Market'].values[0] if not m_info.empty else "KOSPI"
            yf_ticker = f"{symbol}.KS" if m_type == 'KOSPI' else f"{symbol}.KQ"
        else: yf_ticker = symbol

        # 2. 데이터 다운로드 (일봉 vs 분봉)
        if "분봉" in i_val:
            m_map = {"5분봉": "5m", "15분봉": "15m", "60분봉": "60m"}
            df = yf.download(yf_ticker, period="1mo", interval=m_map.get(i_val, "60m"), progress=False)
        else:
            d_map = {"3mo": "3mo", "6mo": "6mo", "1y": "1y", "2y": "2y"}
            df = yf.download(yf_ticker, period=d_map.get(p_val, "6mo"), interval="1d", progress=False)
            
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        # 3. 고도화된 퀀트 지표 연산
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # MACD
        df['MACD'] = df['Close'].ewm(span=12, adjust=False).mean() - df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD_S'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_H'] = df['MACD'] - df['MACD_S']
        
        # Stochastic
        df['L14'] = df['Low'].rolling(window=14).min()
        df['H14'] = df['High'].rolling(window=14).max()
        df['Stoch_K'] = 100 * ((df['Close'] - df['L14']) / (df['H14'] - df['L14']))
        
        # 크로스 신호
        df['GC'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1))
        df['DC'] = (df['MA5'] < df['MA20']) & (df['MA5'].shift(1) >= df['MA20'].shift(1))
        
        # 4. 공격적 AI 스코어링 로직 (민감도 상향)
        df['AI_Score'] = 50.0
        # 추세 가점
        df.loc[df['Close'] > df['MA20'], 'AI_Score'] += 15
        df.loc[df['MA5'] > df['MA20'], 'AI_Score'] += 15
        # 모멘텀 가점
        df.loc[df['MACD_H'] > 0, 'AI_Score'] += 10
        df.loc[df['GC'], 'AI_Score'] += 15
        # 바닥권 가점
        df.loc[df['Stoch_K'] < 30, 'AI_Score'] += 10
        df.loc[df['RSI'] < 40, 'AI_Score'] += 10
        
        # 위험 감점
        df.loc[df['Close'] < df['MA20'], 'AI_Score'] -= 15
        df.loc[df['Close'] < df['MA60'], 'AI_Score'] -= 20
        df.loc[df['DC'], 'AI_Score'] -= 20
        
        df['AI_Score'] = df['AI_Score'].clip(0, 100)
        
        # 5. 백테스팅 엔진 (진입 60, 탈출 40)
        df['Pos'] = np.nan
        df.loc[df['AI_Score'] >= 60, 'Pos'] = 1
        df.loc[df['AI_Score'] <= 40, 'Pos'] = 0
        df['Pos'] = df['Pos'].ffill().fillna(0)
        
        df['Daily_Ret'] = df['Close'].pct_change()
        df['Strat_Ret'] = df['Pos'].shift(1) * df['Daily_Ret']
        df['Cum_Mkt'] = (1 + df['Daily_Ret'].fillna(0)).cumprod() * 100
        df['Cum_Strat'] = (1 + df['Strat_Ret'].fillna(0)).cumprod() * 100
        
        # 6. 엘리어트 변곡점 탐지
        pks, _ = find_peaks(df['High'].values, distance=7, prominence=df['High'].std()*0.2)
        vls, _ = find_peaks(-df['Low'].values, distance=7, prominence=df['Low'].std()*0.2)
        
        return df, pks, vls
    except Exception as e:
        st.error(f"데이터 엔진 오류: {e}")
        return None

@st.cache_data(ttl=300)
def fetch_global_news(query=None):
    kw = "증시 특징주" if query is None else f"{query} 특징주 OR {query} 주가"
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(kw)}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        feed = feedparser.parse(url)
        return [{"title": e.title, "link": e.link, "date": e.published[:-4] if hasattr(e, 'published') else "방금 전"} for e in feed.entries[:7]]
    except: return []

# ==========================================
# 3. 사이드바 제어판
# ==========================================
st.sidebar.title("👑 MASTER 제어판")
user_q = st.sidebar.text_input("종목명/티커 입력", value="SK하이닉스")
symbol = get_smart_ticker(user_q)
chart_int = st.sidebar.selectbox("타임프레임(주기)", ["일봉", "60분봉", "15분봉", "5분봉"])
chart_per = st.sidebar.select_slider("백테스팅 데이터 범위", options=["3mo", "6mo", "1y", "2y"], value="1y")

# ==========================================
# 4. 메인 대시보드 출력
# ==========================================
data_res = fetch_master_data(symbol, chart_per, chart_int)

if data_res:
    df, pks, vls = data_res
    curr_p = float(df['Close'].iloc[-1])
    prev_p = float(df['Close'].iloc[-2])
    change_pct = ((curr_p - prev_p) / prev_p) * 100
    ai_score = float(df['AI_Score'].iloc[-1])
    
    # [NaN 방어] 지지/저항가 계산
    target_p = df['High'].iloc[pks[-1]] if len(pks) > 0 else curr_p * 1.15
    stop_p = df['Low'].iloc[vls[-1]] if len(vls) > 0 else curr_p * 0.92
    if stop_p >= curr_p: stop_p = curr_p * 0.94
    if target_p <= curr_p: target_p = curr_p * 1.08

    st.title(f"👑 {user_q} 프리미엄 퀀트 인텔리전스")
    
    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("실시간 현재가", f"{curr_p:,.0f}" if curr_p > 100 else f"{curr_p:,.2f}", f"{change_pct:+.2f}%")
    col_m2.metric("AI 퀀트 점수", f"{ai_score:.0f}점", "공격적 매수구간" if ai_score >= 60 else "관망/대피구간")
    col_m3.metric("하락 방어력(ATR)", f"{(df['High']-df['Low']).rolling(14).mean().iloc[-1]:,.0f}")

    t1, t2, t3, t4 = st.tabs(["📊 엘리어트 마스터 차트", "🧠 AI 리포트 & 가격전략", "📉 백테스팅 심층검증", "⚡ 실시간 특징주 뉴스"])

    # [TAB 1] 엘리어트 마스터 차트
    with t1:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="캔들"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name="20일선", line=dict(color='gold', width=1.5)), row=1, col=1)
        
        # 엘리어트 숫자 표기 (22pt 굵게)
        labels = ['1','2','3','4','5','A','B','C']
        all_pts = sorted([('p', p, df['High'].iloc[p]) for p in pks] + [('v', v, df['Low'].iloc[v]) for v in vls], key=lambda x: x[1])[-8:]
        for i, pt in enumerate(all_pts):
            if i < len(labels):
                color = "#00FF00" if pt[0] == 'v' else "#FF4B4B"
                fig.add_trace(go.Scatter(x=[df.index[pt[1]]], y=[pt[2]], mode="text+markers", text=[f"<b>{labels[i]}</b>"],
                                         textposition="bottom center" if pt[0]=='v' else "top center",
                                         textfont=dict(size=22, color=color), marker=dict(color=color, size=12, symbol='diamond'),
                                         showlegend=False), row=1, col=1)
        
        # 골든/데드크로스 화살표
        fig.add_trace(go.Scatter(x=df[df['GC']].index, y=df[df['GC']]['Low']*0.96, mode='markers', marker=dict(symbol='triangle-up', size=15, color='lime'), name="골든크로스"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df[df['DC']].index, y=df[df['DC']]['High']*1.04, mode='markers', marker=dict(symbol='triangle-down', size=15, color='red'), name="데드크로스"), row=1, col=1)
        
        fig.add_hline(y=target_p, line_dash="dash", line_color="#00FF00", annotation_text="목표가", row=1, col=1)
        fig.add_hline(y=stop_p, line_dash="dash", line_color="#FF4B4B", annotation_text="손절가", row=1, col=1)

        fig.add_trace(go.Bar(x=df.index, y=df['MACD_H'], marker_color=['red' if x<0 else 'green' for x in df['MACD_H']], name="MACD"), row=2, col=1)
        fig.update_layout(height=750, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

    # [TAB 2] AI 리포트 & 가격전략
    with t2:
        if ai_score >= 70: status_txt, g_col = "🟢 강력 매수 (상승 파동 진입)", "#00FF00"
        elif ai_score >= 45: status_txt, g_col = "🟡 중립 유지 (관망/분할 매수)", "#FFD700"
        else: status_txt, g_col = "🔴 위험 대피 (리스크 관리 강화)", "#FF4B4B"
        
        fig_g = go.Figure(go.Indicator(
            mode = "gauge+number", value = ai_score, domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': f"AI 퀀트 매력도 점수<br><span style='font-size:0.75em;color:{g_col}'>{status_txt}</span>", 'font': {'size': 28, 'color': 'white'}},
            gauge = {
                'axis': {'range': [0, 100], 'tickcolor': "white"},
                'bar': {'color': g_col},
                'steps': [{'range': [0, 45], 'color': "rgba(255,75,75,0.2)"}, {'range': [70, 100], 'color': "rgba(0,255,0,0.2)"}],
                'threshold': {'line': {'color': "white", 'width': 4}, 'thickness': 0.75, 'value': ai_score}
            }
        ))
        fig_g.update_layout(height=450, margin=dict(l=30, r=30, t=180, b=30), paper_bgcolor="#0E1117", font={'color': 'white'})
        st.plotly_chart(fig_g, use_container_width=True)

        pc_col1, pc_col2, pc_col3 = st.columns(3)
        pc_col1.markdown(f"<div class='price-card'><div class='price-label'>🔵 추세 지지선</div><div class='price-val' style='color:#00BFFF;'>{df['MA20'].iloc[-1]:,.0f}</div></div>", unsafe_allow_html=True)
        pc_col2.markdown(f"<div class='price-card'><div class='price-label'>🟢 목표 매도가</div><div class='price-val' style='color:#00FF00;'>{target_p:,.0f}</div></div>", unsafe_allow_html=True)
        pc_col3.markdown(f"<div class='price-card'><div class='price-label'>🔴 손절 커트라인</div><div class='price-val' style='color:#FF4B4B;'>{stop_p:,.0f}</div></div>", unsafe_allow_html=True)

        st.markdown("<div class='ai-report'>", unsafe_allow_html=True)
        st.subheader("🧐 퀀트 심층 리포트")
        if len(all_pts) > 0:
            last_w = labels[len(all_pts)-1]
            st.markdown(f"#### 📐 파동 진단: **엘리어트 {last_w}파** 진행 중")
            if last_w == '3': st.success("🔥 **핵심 분석**: 가장 강력한 추세인 상승 3파 구간입니다. 추세 추종 전략을 통해 수익을 극대화해야 합니다.")
            elif last_w == '5': st.warning("⚠️ **핵심 분석**: 상승 파동의 막바지입니다. 과열 지표(RSI)를 주시하며 분할 익절을 고려하세요.")
            elif last_w in ['A', 'C']: st.error("🚨 **핵심 분석**: 하락 조정 구간입니다. 성급한 매수보다는 지지선 확인이 최우선입니다.")
        
        st.write(f"• **단기 모멘텀**: {'MACD 히스토그램이 양수로 반전되어 매수 우위 시장입니다.' if df['MACD_H'].iloc[-1] > 0 else '단기 매도 압력이 우세한 국면입니다.'}")
        st.write(f"• **과매수도 지표**: {'RSI 수치가 낮아 기술적 반등 가능성이 높습니다.' if df['RSI'].iloc[-1] < 40 else '지표상 중립 혹은 과열권에 진입하고 있습니다.'}")
        st.markdown("</div>", unsafe_allow_html=True)

    # [TAB 3] 백테스팅 심층검증 (평행선 문제 완전 해결)
    with t3:
        st.subheader("📉 AI 퀀트 전략 백테스팅")
        m_r, s_r = df['Cum_Mkt'].iloc[-1]-100, df['Cum_Strat'].iloc[-1]-100
        bt_col1, bt_col2 = st.columns(2)
        bt_col1.metric("시장 수익률(존버)", f"{m_r:+.2f}%")
        bt_col2.metric("AI 전략 수익률", f"{s_r:+.2f}%", f"{s_r-m_r:+.2f}%p")

        fig_bt = go.Figure()
        fig_bt.add_trace(go.Scatter(x=df.index, y=df['Cum_Mkt'], name="시장 수익률(존버)", line=dict(color='rgba(255,255,255,0.3)', width=2)))
        fig_bt.add_trace(go.Scatter(x=df.index, y=df['Cum_Strat'], name="AI 퀀트 전략", line=dict(color='#00FF00', width=3)))
        # 점수 히스토리 통합
        fig_bt.add_trace(go.Scatter(x=df.index, y=df['AI_Score'], name="AI 점수 추이", yaxis="y2", line=dict(color='yellow', width=1, dash='dot')))
        
        fig_bt.update_layout(height=500, template="plotly_dark", 
                             yaxis2=dict(overlaying="y", side="right", range=[0, 100], title="AI Score", showgrid=False),
                             margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_bt, use_container_width=True)
        st.info("💡 **전략 메커니즘**: AI 점수 60점 이상 시 매수, 40점 이하 시 전량 매도 관망 전략입니다.")

    # [TAB 4] 실시간 뉴스
    with t4:
        st.subheader("🚨 실시간 마켓 레이더")
        n_c1, n_c2 = st.columns(2)
        with n_c1:
            st.markdown("#### 🌐 증시 전체 이슈")
            for n in fetch_global_news():
                st.markdown(f"<div class='news-box'><a href='{n['link']}' target='_blank' class='news-title'>{n['title']}</a><div class='news-meta'>🕒 {n['date']}</div></div>", unsafe_allow_html=True)
        with n_c2:
            st.markdown(f"#### 🎯 {user_q} 관련 뉴스")
            for n in fetch_global_news(user_q):
                st.markdown(f"<div class='news-box'><a href='{n['link']}' target='_blank' class='news-title'>{n['title']}</a><div class='news-meta'>🕒 {n['date']}</div></div>", unsafe_allow_html=True)
else:
    st.error("데이터 로드 실패. 종목명과 주기를 확인해주세요.")
