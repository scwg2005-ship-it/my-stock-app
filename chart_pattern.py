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
st.set_page_config(layout="wide", page_title="AI 엘리어트 퀀트 v3", page_icon="🚀")

st.markdown("""
    <style>
    .main { background-color: #0E1117; color: #FFFFFF; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { font-size: 1rem; font-weight: bold; color: #888; }
    .stTabs [aria-selected="true"] { color: #00FF00 !important; border-bottom-color: #00FF00 !important; }
    .ai-report { background: #1E1E1E; padding: 20px; border-radius: 10px; border-left: 5px solid #00FF00; margin-bottom: 20px; line-height: 1.6; }
    .price-card { background: #262730; border-radius: 10px; padding: 15px; text-align: center; border: 1px solid #444; margin-bottom: 10px; }
    .news-box { background: #1a1c24; padding: 12px; border-radius: 8px; margin-bottom: 8px; border-left: 3px solid #00FF00; }
    div[data-testid="stMetricValue"] { font-size: 1.5rem !important; font-weight: 800; color: #00FF00; }
    @media (max-width: 768px) {
        div[data-testid="stMetricValue"] { font-size: 1.2rem !important; }
        .stTabs [data-baseweb="tab"] { font-size: 0.85rem; padding: 0 5px; }
        .price-card h2 { font-size: 1.2rem !important; }
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 엔진: 스마트 검색 & 실시간 뉴스
# ==========================================
@st.cache_data(ttl=86400)
def load_krx(): return fdr.StockListing('KRX')

krx_df = load_krx()

def get_ticker(query):
    query = query.strip().replace(" ", "").upper()
    if query.isdigit() and len(query) == 6: return query
    match = krx_df[krx_df['Name'].str.replace(" ", "", regex=False).str.upper() == query]
    if not match.empty: return match.iloc[0]['Code']
    us_map = {"테슬라": "TSLA", "애플": "AAPL", "엔비디아": "NVDA", "하이닉스": "000660"}
    return us_map.get(query, query.upper())

@st.cache_data(ttl=300)
def fetch_news(query=None):
    kw = "증시 특징주 OR 주식 마감" if query is None else f"{query} 특징주 OR {query} 실적"
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
    pts = sorted(pts, key=lambda x: x[1])[-8:] # 최근 8개 변곡점
    
    labels = ['1', '2', '3', '4', '5', 'A', 'B', 'C']
    wave_data = []
    ratios = []
    
    for i, pt in enumerate(pts):
        if i < len(labels):
            wave_data.append({'type': pt[0], 'idx': pt[1], 'val': pt[2], 'label': labels[i]})
            
    if len(pts) >= 4:
        try:
            w1 = abs(pts[1][2] - pts[0][2])
            w3 = abs(pts[3][2] - pts[2][2])
            if w1 > 0: ratios.append(f"3파/1파 비율: {w3/w1:.2f}x")
        except: pass
    return wave_data, ratios

@st.cache_data(ttl=60)
def analyze_data(symbol, p):
    try:
        days = {"3mo": 90, "6mo": 180, "1y": 365, "2y": 730}
        df = fdr.DataReader(symbol, datetime.today() - timedelta(days=days.get(p, 180)))
        if df.empty or len(df) < 40: return None
        
        # 지표 계산
        df['MA5'], df['MA20'], df['MA60'] = df['Close'].rolling(5).mean(), df['Close'].rolling(20).mean(), df['Close'].rolling(60).mean()
        df['MACD_H'] = df['Close'].ewm(span=12).mean() - df['Close'].ewm(span=26).mean()
        df['Stoch_K'] = 100 * ((df['Close'] - df['Low'].rolling(14).min()) / (df['High'].rolling(14).max() - df['Low'].rolling(14).min()))
        
        # 시그널 포착
        df['GC'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1))
        df['DC'] = (df['MA5'] < df['MA20']) & (df['MA5'].shift(1) >= df['MA20'].shift(1))
        
        # 파동 분석
        pks, _ = find_peaks(df['High'].values, distance=8, prominence=df['High'].std()*0.3)
        vls, _ = find_peaks(-df['Low'].values, distance=8, prominence=df['Low'].std()*0.3)
        waves, ratios = calc_elliott_waves(df, pks, vls)
        
        # --- 🚀 공격적 & 방어적 AI 스코어링 ---
        df['AI_Score'] = 50
        if df['MA5'].iloc[-1] > df['MA20'].iloc[-1]: df['AI_Score'] += 20 # 상승추세
        if df['GC'].iloc[-1]: df['AI_Score'] += 15 # 골든크로스
        if df['MACD_H'].iloc[-1] > 0: df['AI_Score'] += 15 # 모멘텀
        if df['Close'].iloc[-1] < df['MA60'].iloc[-1]: df['AI_Score'] -= 30 # 하락장 방어(급소)
        if df['DC'].iloc[-1]: df['AI_Score'] -= 20 # 데드크로스 대피
        df['AI_Score'] = df['AI_Score'].clip(0, 100)
        
        # 백테스팅 포지션
        df['Pos'] = np.nan
        df.loc[df['AI_Score'] >= 65, 'Pos'] = 1
        df.loc[df['AI_Score'] <= 45, 'Pos'] = 0
        df['Pos'] = df['Pos'].ffill().fillna(0)
        df['Strat_Ret'] = df['Pos'].shift(1) * df['Close'].pct_change()
        df['Cum_Mkt'] = (1 + df['Close'].pct_change()).cumprod() * 100
        df['Cum_Strat'] = (1 + df['Strat_Ret']).cumprod() * 100
        
        return df, waves, ratios
    except: return None

# ==========================================
# 4. 메인 대시보드 구현
# ==========================================
st.sidebar.title("🚀 엘리어트 퀀트 v3")
input_name = st.sidebar.text_input("종목명 검색", value="SK하이닉스")
ticker = get_ticker(input_name)
period = st.sidebar.select_slider("조회 기간", options=["3mo", "6mo", "1y", "2y"], value="6mo")

res = analyze_data(ticker, period)

if res:
    df, waves, wave_ratios = res
    curr_p = df['Close'].iloc[-1]
    ai_score = df['AI_Score'].iloc[-1]
    
    # 헤더 메트릭
    c1, c2, c3 = st.columns(3)
    c1.metric(f"{input_name}", f"{curr_p:,.0f}원", f"{((curr_p/df['Close'].iloc[-2]-1)*100):+.2f}%")
    c2.metric("AI 퀀트 점수", f"{ai_score:.0f}점")
    gc_status = "✨ 골든크로스!" if df['GC'].iloc[-1] else "추세 관찰 중"
    c3.markdown(f"<div class='price-card'><small>현재 상태</small><br><b style='color:#FFD700'>{gc_status}</b></div>", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["📊 엘리어트 차트", "🧠 파동 전략 & 가격", "📉 하락장 방어 검증", "⚡ 실시간 뉴스"])

    with tab1:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.75, 0.25])
        # 캔들스틱 & 이평선
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="주가"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name="20일선", line=dict(color='gold', width=1.5)), row=1, col=1)
        
        # ⭐ 엘리어트 파동 숫자 표기 ⭐
        for w in waves:
            color = "#00FF00" if w['type'] == 'valley' else "#FF4B4B"
            y_pos = w['val'] * 0.97 if w['type'] == 'valley' else w['val'] * 1.03
            fig.add_trace(go.Scatter(x=[df.index[w['idx']]], y=[y_pos], mode="text+markers",
                                     text=[f"<b>{w['label']}</b>"], textposition="top center" if w['type']=='peak' else "bottom center",
                                     textfont=dict(size=18, color=color), marker=dict(color=color, size=10, symbol='diamond'),
                                     showlegend=False), row=1, col=1)
        
        # 골든/데드크로스 마커
        fig.add_trace(go.Scatter(x=df[df['GC']].index, y=df[df['GC']]['Low']*0.95, mode='markers', marker=dict(symbol='triangle-up', size=12, color='lime'), name="GC"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df[df['DC']].index, y=df[df['DC']]['High']*1.05, mode='markers', marker=dict(symbol='triangle-down', size=12, color='red'), name="DC"), row=1, col=1)

        fig.add_trace(go.Bar(x=df.index, y=df['MACD_H'], marker_color=['red' if v<0 else 'green' for v in df['MACD_H']], name="MACD"), row=2, col=1)
        fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with tab2:
        # 목표가/손절가
        target_p = df['High'].tail(20).max()
        stop_p = df['MA60'].iloc[-1]
        
        st.subheader("📐 엘리어트 파동 전략 가이드")
        pc1, pc2 = st.columns(2)
        pc1.markdown(f"<div class='price-card'><h4>🎯 목표가(익절)</h4><h2 style='color:#00FF00;'>{target_p:,.0f}</h2></div>", unsafe_allow_html=True)
        pc2.markdown(f"<div class='price-card'><h4>🛡️ 손절가(대피)</h4><h2 style='color:#FF4B4B;'>{stop_p:,.0f}</h2></div>", unsafe_allow_html=True)
        
        st.markdown("<div class='ai-report'>", unsafe_allow_html=True)
        if waves:
            last_w = waves[-1]['label']
            st.markdown(f"#### 현재 추정: **{last_w}파** 구간")
            if last_w == '3': st.success("🔥 **[강력 상승 3파]** 가장 큰 수익이 기대되는 구간입니다. 공격적 대응을 추천합니다.")
            elif last_w == '5': st.warning("⚠️ **[과열 5파]** 상승의 마지막 단계입니다. 목표가 도달 시 익절을 고려하세요.")
            elif last_w in ['A', 'C']: st.error("🚨 **[조정 파동]** 하락 압력이 강합니다. 지지선 확인 전까지 관망하세요.")
            if wave_ratios: st.write(f"📊 피보나치 분석: {wave_ratios[0]}")
        st.markdown("</div>", unsafe_allow_html=True)

    with tab3:
        st.subheader("📉 전략 수익률 및 하락장 방어 검증")
        m_r, s_r = df['Cum_Mkt'].iloc[-1]-100, df['Cum_Strat'].iloc[-1]-100
        br1, br2 = st.columns(2)
        br1.metric("그냥 보유(존버)", f"{m_r:+.2f}%")
        br2.metric("AI 전략 매매", f"{s_r:+.2f}%", f"{s_r-m_r:+.2f}%p")
        
        fig_bt = go.Figure()
        fig_bt.add_trace(go.Scatter(x=df.index, y=df['Cum_Mkt'], name="존버", line=dict(color='gray')))
        fig_bt.add_trace(go.Scatter(x=df.index, y=df['Cum_Strat'], name="AI 퀀트", line=dict(color='#00FF00', width=2)))
        fig_bt.add_trace(go.Scatter(x=df.index, y=df['AI_Score'], name="AI 점수", yaxis="y2", line=dict(color='yellow', width=1, dash='dot')))
        fig_bt.update_layout(height=400, template="plotly_dark", yaxis2=dict(overlaying="y", side="right", range=[0, 100]), margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_bt, use_container_width=True)

    with tab4:
        st.subheader("⚡ 실시간 마켓 뉴스")
        n1, n2 = st.columns(2)
        with n1:
            st.markdown("#### 🌐 증시 핫이슈")
            for n in fetch_news(): st.markdown(f"<div class='news-box'><a href='{n['link']}' target='_blank' style='color:white; text-decoration:none;'>{n['title']}</a><br><small>{n['date']}</small></div>", unsafe_allow_html=True)
        with n2:
            st.markdown(f"#### 🎯 {input_name} 뉴스")
            for n in fetch_news(input_name): st.markdown(f"<div class='news-box'><a href='{n['link']}' target='_blank' style='color:white; text-decoration:none;'>{n['title']}</a><br><small>{n['date']}</small></div>", unsafe_allow_html=True)

else: st.error("데이터 로드 실패. 종목명과 인터넷 연결을 확인해주세요.")
