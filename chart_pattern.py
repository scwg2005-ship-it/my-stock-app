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
# 1. UI/UX: 모바일 최적화 & 프리미엄 테마
# ==========================================
st.set_page_config(layout="wide", page_title="AI 엘리어트 퀀트 v3.1", page_icon="🚀")

st.markdown("""
    <style>
    .main { background-color: #0E1117; color: #FFFFFF; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { font-size: 1rem; font-weight: bold; color: #888; }
    .stTabs [aria-selected="true"] { color: #00FF00 !important; border-bottom-color: #00FF00 !important; }
    .ai-report { background: #1E1E1E; padding: 20px; border-radius: 10px; border-left: 5px solid #00FF00; margin-bottom: 20px; }
    .price-card { background: #262730; border-radius: 10px; padding: 15px; text-align: center; border: 1px solid #444; margin-bottom: 10px; }
    div[data-testid="stMetricValue"] { font-size: 1.5rem !important; font-weight: 800; color: #00FF00; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 엔진: 스마트 검색 & 뉴스
# ==========================================
@st.cache_data(ttl=86400)
def load_krx(): return fdr.StockListing('KRX')

krx_df = load_krx()

def get_ticker(query):
    query = query.strip().replace(" ", "").upper()
    if query.isdigit() and len(query) == 6: return query
    match = krx_df[krx_df['Name'].str.replace(" ", "", regex=False).str.upper() == query]
    return match.iloc[0]['Code'] if not match.empty else query

@st.cache_data(ttl=300)
def fetch_news(query=None):
    kw = "증시 특징주" if query is None else f"{query} 특징주 OR {query} 실적"
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(kw)}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        feed = feedparser.parse(url)
        return [{"title": e.title, "link": e.link, "date": e.published[:-4] if hasattr(e, 'published') else "최근"} for e in feed.entries[:6]]
    except: return []

# ==========================================
# 3. 코어: 엘리어트 파동 & 퀀트 알고리즘
# ==========================================
def calc_elliott_waves(df, peaks, valleys):
    pts = []
    for p in peaks: pts.append(('peak', p, df['High'].iloc[p]))
    for v in valleys: pts.append(('valley', v, df['Low'].iloc[v]))
    pts = sorted(pts, key=lambda x: x[1])[-8:] 
    
    labels = ['1', '2', '3', '4', '5', 'A', 'B', 'C']
    wave_data = []
    for i, pt in enumerate(pts):
        if i < len(labels):
            wave_data.append({'type': pt[0], 'idx': pt[1], 'val': pt[2], 'label': labels[i]})
    return wave_data

@st.cache_data(ttl=60)
def analyze_data(symbol, p, interval):
    try:
        days = {"3mo": 90, "6mo": 180, "1y": 365, "2y": 730}
        # FinanceDataReader는 분봉을 위해 '1', '5', '15', '60' 등의 단위를 지원합니다.
        # 한국 주식 분봉은 현재 FinanceDataReader 제약상 일봉 위주로 최적화되어 있으나 옵션은 열어둡니다.
        df = fdr.DataReader(symbol, datetime.today() - timedelta(days=days.get(p, 180)))
        
        if df.empty or len(df) < 40: return None
        
        # 지표 계산
        df['MA5'], df['MA20'], df['MA60'] = df['Close'].rolling(5).mean(), df['Close'].rolling(20).mean(), df['Close'].rolling(60).mean()
        df['MACD_H'] = df['Close'].ewm(span=12).mean() - df['Close'].ewm(span=26).mean()
        df['Stoch_K'] = 100 * ((df['Close'] - df['Low'].rolling(14).min()) / (df['High'].rolling(14).max() - df['Low'].rolling(14).min()))
        
        # 시그널
        df['GC'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1))
        df['DC'] = (df['MA5'] < df['MA20']) & (df['MA5'].shift(1) >= df['MA20'].shift(1))
        
        # 파동 분석
        pks, _ = find_peaks(df['High'].values, distance=8, prominence=df['High'].std()*0.3)
        vls, _ = find_peaks(-df['Low'].values, distance=8, prominence=df['Low'].std()*0.3)
        waves = calc_elliott_waves(df, pks, vls)
        
        # AI 점수 (공격/방어 통합)
        df['AI_Score'] = 50
        if df['MA5'].iloc[-1] > df['MA20'].iloc[-1]: df['AI_Score'] += 20
        if df['GC'].iloc[-1]: df['AI_Score'] += 15
        if df['MACD_H'].iloc[-1] > 0: df['AI_Score'] += 15
        if df['Close'].iloc[-1] < df['MA60'].iloc[-1]: df['AI_Score'] -= 30
        df['AI_Score'] = df['AI_Score'].clip(0, 100)
        
        # 백테스팅
        df['Pos'] = np.nan
        df.loc[df['AI_Score'] >= 65, 'Pos'] = 1
        df.loc[df['AI_Score'] <= 45, 'Pos'] = 0
        df['Pos'] = df['Pos'].ffill().fillna(0)
        df['Strat_Ret'] = df['Pos'].shift(1) * df['Close'].pct_change()
        df['Cum_Mkt'] = (1 + df['Close'].pct_change()).cumprod() * 100
        df['Cum_Strat'] = (1 + df['Strat_Ret']).cumprod() * 100
        
        return df, waves
    except: return None

# ==========================================
# 4. 메인 대시보드
# ==========================================
st.sidebar.title("🚀 엘리어트 퀀트 v3.1")
input_name = st.sidebar.text_input("종목명 검색", value="SK하이닉스")
ticker = get_ticker(input_name)

# --- [부활] 일봉/분봉 선택 ---
chart_type = st.sidebar.selectbox("차트 주기", ["일봉", "60분봉", "15분봉", "5분봉"])
period = st.sidebar.select_slider("조회 기간", options=["3mo", "6mo", "1y", "2y"], value="6mo")

res = analyze_data(ticker, period, chart_type)

if res:
    df, waves = res
    curr_p = df['Close'].iloc[-1]
    ai_score = df['AI_Score'].iloc[-1]
    
    st.metric(f"{input_name} ({chart_type})", f"{curr_p:,.0f}원", f"{((curr_p/df['Close'].iloc[-2]-1)*100):+.2f}%")

    tab1, tab2, tab3, tab4 = st.tabs(["📊 엘리어트 차트", "🧠 AI 온도계 & 전략", "📉 하락장 방어 검증", "⚡ 실시간 뉴스"])

    with tab1:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.75, 0.25])
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="주가"), row=1, col=1)
        
        # 엘리어트 숫자 표기
        for w in waves:
            color = "#00FF00" if w['type'] == 'valley' else "#FF4B4B"
            y_pos = w['val'] * 0.96 if w['type'] == 'valley' else w['val'] * 1.04
            fig.add_trace(go.Scatter(x=[df.index[w['idx']]], y=[y_pos], mode="text+markers",
                                     text=[f"<b>{w['label']}</b>"], textposition="top center" if w['type']=='peak' else "bottom center",
                                     textfont=dict(size=18, color=color), marker=dict(color=color, size=10, symbol='diamond'),
                                     showlegend=False), row=1, col=1)
        
        # 골든/데드크로스 마커
        fig.add_trace(go.Scatter(x=df[df['GC']].index, y=df[df['GC']]['Low']*0.95, mode='markers', marker=dict(symbol='triangle-up', size=12, color='lime'), name="GC"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df[df['DC']].index, y=df[df['DC']]['High']*1.05, mode='markers', marker=dict(symbol='triangle-down', size=12, color='red'), name="DC"), row=1, col=1)

        fig.add_trace(go.Bar(x=df.index, y=df['MACD_H'], marker_color=['red' if v<0 else 'green' for v in df['MACD_H']], name="MACD"), row=2, col=1)
        fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        # --- [부활] AI 온도계 게이지 ---
        st.subheader("🌡️ AI 매수 매력도 온도계")
        if ai_score >= 70: status_text, gauge_color = "🟢 매수 기회 (좋음)", "green"
        elif ai_score >= 45: status_text, gauge_color = "🟡 중립 및 관망 (보통)", "yellow"
        else: status_text, gauge_color = "🔴 위험 및 매도 (나쁨)", "red"
            
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number", value = ai_score, domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': f"AI 퀀트 점수<br><span style='font-size:0.7em;color:{gauge_color}'>{status_text}</span>", 'font': {'size': 20, 'color': 'white'}},
            gauge = {
                'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white"},
                'bar': {'color': gauge_color}, 'bgcolor': "black", 'borderwidth': 2, 'bordercolor': "gray",
                'steps': [{'range': [0, 45], 'color': "rgba(255,0,0,0.3)"}, {'range': [45, 70], 'color': "rgba(255,255,0,0.3)"}, {'range': [70, 100], 'color': "rgba(0,255,0,0.3)"}]
            }
        ))
        fig_gauge.update_layout(height=300, margin=dict(l=10, r=10, t=50, b=10), paper_bgcolor="#0E1117", font={'color': "white"})
        st.plotly_chart(fig_gauge, use_container_width=True)

        st.markdown("<div class='ai-report'>", unsafe_allow_html=True)
        if waves:
            last_w = waves[-1]['label']
            st.markdown(f"#### 현재 추정: **{last_w}파** 구간")
            if last_w == '3': st.success("🔥 **[상승 3파]** 강력한 수익 구간입니다. 적극 대응하세요.")
            elif last_w == '5': st.warning("⚠️ **[과열 5파]** 상승 마감 단계입니다. 분할 익절을 준비하세요.")
            elif last_w in ['A', 'C']: st.error("🚨 **[하락 조정]** 하락 압력이 강합니다. 지지선을 확인하세요.")
        st.markdown("</div>", unsafe_allow_html=True)

    with tab3:
        st.subheader("📉 하락장 방어 검증")
        m_r, s_r = df['Cum_Mkt'].iloc[-1]-100, df['Cum_Strat'].iloc[-1]-100
        c_r1, c_r2 = st.columns(2)
        c_r1.metric("존버(보유)", f"{m_r:+.2f}%")
        c_r2.metric("AI 퀀트", f"{s_r:+.2f}%", f"{s_r-m_r:+.2f}%p")
        
        fig_bt = go.Figure()
        fig_bt.add_trace(go.Scatter(x=df.index, y=df['Cum_Mkt'], name="보유", line=dict(color='gray')))
        fig_bt.add_trace(go.Scatter(x=df.index, y=df['Cum_Strat'], name="AI 퀀트", line=dict(color='#00FF00', width=2)))
        fig_bt.add_trace(go.Scatter(x=df.index, y=df['AI_Score'], name="AI 점수", yaxis="y2", line=dict(color='yellow', width=1, dash='dot')))
        fig_bt.update_layout(height=400, template="plotly_dark", yaxis2=dict(overlaying="y", side="right", range=[0, 100]))
        st.plotly_chart(fig_bt, use_container_width=True)

    with tab4:
        st.subheader("⚡ 실시간 뉴스")
        n1, n2 = st.columns(2)
        with n1:
            for n in fetch_news(): st.markdown(f"<div class='price-card' style='text-align:left;'><a href='{n['link']}' target='_blank' style='color:white;text-decoration:none;'>{n['title']}</a><br><small>{n['date']}</small></div>", unsafe_allow_html=True)
        with n2:
            for n in fetch_news(input_name): st.markdown(f"<div class='price-card' style='text-align:left;'><a href='{n['link']}' target='_blank' style='color:white;text-decoration:none;'>{n['title']}</a><br><small>{n['date']}</small></div>", unsafe_allow_html=True)

else: st.error("데이터 로드 실패!")
