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
# 1. UI/UX: 프리미엄 다크 테마 & 모바일 최적화
# ==========================================
st.set_page_config(layout="wide", page_title="AI 프리미엄 퀀트 v4.2", page_icon="👑")

st.markdown("""
    <style>
    .main { background-color: #0E1117; color: #FFFFFF; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { font-size: 1.1rem; font-weight: bold; color: #888; }
    .stTabs [aria-selected="true"] { color: #00FF00 !important; border-bottom-color: #00FF00 !important; }
    .ai-report { background: #1E1E1E; padding: 25px; border-radius: 12px; border-left: 5px solid #00FF00; margin-bottom: 25px; line-height: 1.7;}
    .price-card { background: #262730; border-radius: 12px; padding: 18px; text-align: center; border: 1px solid #444; margin-bottom: 12px; transition: 0.3s; }
    .price-card:hover { border-color: #00FF00; }
    .news-box { background: #1a1c24; padding: 15px; border-radius: 10px; margin-bottom: 10px; border-left: 4px solid #00FF00; }
    div[data-testid="stMetricValue"] { font-size: 1.7rem !important; font-weight: 800; color: #00FF00; }
    @media (max-width: 768px) {
        div[data-testid="stMetricValue"] { font-size: 1.3rem !important; }
        .stTabs [data-baseweb="tab"] { font-size: 0.85rem; padding: 0 5px; }
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 엔진: 데이터 수집 및 스마트 검색
# ==========================================
@st.cache_data(ttl=86400)
def load_krx(): return fdr.StockListing('KRX')

krx_list = load_krx()

def get_ticker(query):
    query = query.strip().replace(" ", "").upper()
    if query.isdigit() and len(query) == 6: return query
    match = krx_list[krx_list['Name'].str.replace(" ", "", regex=False).str.upper() == query]
    if not match.empty: return match.iloc[0]['Code']
    us_map = {"테슬라": "TSLA", "애플": "AAPL", "엔비디아": "NVDA", "하이닉스": "000660"}
    return us_map.get(query, query.upper())

@st.cache_data(ttl=60)
def get_data(symbol, p_val, i_val):
    try:
        if symbol.isdigit():
            market = krx_list[krx_list['Code'] == symbol]['Market'].values[0]
            yf_ticker = f"{symbol}.KS" if market == 'KOSPI' else f"{symbol}.KQ"
        else: yf_ticker = symbol

        if "분봉" in i_val:
            m_map = {"5분봉": "5m", "15분봉": "15m", "60분봉": "60m"}
            df = yf.download(yf_ticker, period="1mo", interval=m_map.get(i_val, "60m"))
        else:
            d_map = {"3mo": 90, "6mo": 180, "1y": 365, "2y": 730}
            df = fdr.DataReader(symbol, datetime.today() - timedelta(days=d_map.get(p_val, 180)))
            
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        # [지표]
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        df['MACD'] = df['Close'].ewm(span=12).mean() - df['Close'].ewm(span=26).mean()
        df['MACD_Sig'] = df['MACD'].ewm(span=9).mean()
        df['MACD_H'] = df['MACD'] - df['MACD_Sig']
        df['Stoch_K'] = 100 * ((df['Close'] - df['Low'].rolling(14).min()) / (df['High'].rolling(14).max() - df['Low'].rolling(14).min()))
        
        # [시그널]
        df['GC'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1))
        df['DC'] = (df['MA5'] < df['MA20']) & (df['MA5'].shift(1) >= df['MA20'].shift(1))
        
        # [AI 스코어]
        df['AI_Score'] = 50
        if df['MA5'].iloc[-1] > df['MA20'].iloc[-1]: df['AI_Score'] += 20
        if df['GC'].iloc[-1]: df['AI_Score'] += 15
        if df['MACD_H'].iloc[-1] > 0: df['AI_Score'] += 15
        if df['Close'].iloc[-1] < df['MA60'].iloc[-1]: df['AI_Score'] -= 30
        if df['DC'].iloc[-1]: df['AI_Score'] -= 20
        df['AI_Score'] = df['AI_Score'].clip(0, 100)
        
        # [백테스팅]
        df['Pos'] = np.nan
        df.loc[df['AI_Score'] >= 65, 'Pos'] = 1
        df.loc[df['AI_Score'] <= 45, 'Pos'] = 0
        df['Pos'] = df['Pos'].ffill().fillna(0)
        df['Strat_Ret'] = df['Pos'].shift(1) * df['Close'].pct_change()
        df['Cum_Mkt'] = (1 + df['Close'].pct_change()).cumprod() * 100
        df['Cum_Strat'] = (1 + df['Strat_Ret']).cumprod() * 100
        
        # [파동 변곡점]
        pks, _ = find_peaks(df['High'].values, distance=8, prominence=df['High'].std()*0.3)
        vls, _ = find_peaks(-df['Low'].values, distance=8, prominence=df['Low'].std()*0.3)
        
        return df, pks, vls
    except: return None

@st.cache_data(ttl=300)
def get_news(query=None):
    kw = "증시 특징주" if query is None else f"{query} 특징주 OR {query} 실적"
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(kw)}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        feed = feedparser.parse(url)
        return [{"title": e.title, "link": e.link, "date": e.published[:-4] if hasattr(e, 'published') else "최근"} for e in feed.entries[:6]]
    except: return []

# ==========================================
# 4. 화면 구성
# ==========================================
st.sidebar.title("👑 AI 프리미엄 퀀트 v4.2")
user_input = st.sidebar.text_input("종목 검색", value="SK하이닉스")
ticker = get_ticker(user_input)
chart_type = st.sidebar.selectbox("차트 주기", ["일봉", "60분봉", "15분봉", "5분봉"])
period = st.sidebar.select_slider("데이터 범위", options=["3mo", "6mo", "1y", "2y"], value="6mo")

res = get_data(ticker, period, chart_type)

if res:
    df, pks, vls = res
    curr_p = df['Close'].iloc[-1]
    ai_score = df['AI_Score'].iloc[-1]
    
    # --- [⭐ NaN 방어 로직] 목표가/손절가 예외 처리 ---
    # 1. 목표가: 최근 고점 파동 기준, 없으면 현재가 +10%
    if len(pks) > 0:
        target_p = df['High'].iloc[pks[-1]]
    else:
        target_p = curr_p * 1.10
        
    # 2. 손절가: 최근 저점 파동 기준, 없으면 20일선 혹은 현재가 -7%
    if len(vls) > 0:
        stop_p = df['Low'].iloc[vls[-1]]
    else:
        ma20 = df['MA20'].iloc[-1]
        stop_p = ma20 if not np.isnan(ma20) else curr_p * 0.93

    # 현재가보다 높은 손절가 방지
    if stop_p >= curr_p: stop_p = curr_p * 0.95
    # 현재가보다 낮은 목표가 방지
    if target_p <= curr_p: target_p = curr_p * 1.05

    st.metric(f"{user_input} ({chart_type})", f"{curr_p:,.0f}원", f"{((curr_p/df['Close'].iloc[-2]-1)*100):+.2f}%")

    tab1, tab2, tab3, tab4 = st.tabs(["📊 엘리어트 차트", "🧠 AI 리포트 & 온도계", "📉 백테스팅 검증", "⚡ 실시간 뉴스"])

    with tab1:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.75, 0.25])
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="주가"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name="20일선", line=dict(color='gold', width=1.5)), row=1, col=1)
        
        # [엘리어트 숫자]
        labels = ['1','2','3','4','5','A','B','C']
        pts = sorted([('p', p, df['High'].iloc[p]) for p in pks] + [('v', v, df['Low'].iloc[v]) for v in vls], key=lambda x: x[1])[-8:]
        for i, pt in enumerate(pts):
            if i < len(labels):
                color = "#00FF00" if pt[0] == 'v' else "#FF4B4B"
                fig.add_trace(go.Scatter(x=[df.index[pt[1]]], y=[pt[2]], mode="text+markers", text=[f"<b>{labels[i]}</b>"], 
                                         textposition="bottom center" if pt[0]=='v' else "top center", textfont=dict(size=20, color=color), showlegend=False), row=1, col=1)
        
        # [차트 위 가이드선]
        fig.add_hline(y=target_p, line_dash="dash", line_color="#00FF00", annotation_text="목표가", row=1, col=1)
        fig.add_hline(y=stop_p, line_dash="dash", line_color="#FF4B4B", annotation_text="손절가", row=1, col=1)

        fig.add_trace(go.Bar(x=df.index, y=df['MACD_H'], marker_color=['red' if v<0 else 'green' for v in df['MACD_H']], name="MACD"), row=2, col=1)
        fig.update_layout(height=650, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        if ai_score >= 70: status_txt, g_col = "🟢 적극 매수 권장 구간", "green"
        elif ai_score >= 45: status_txt, g_col = "🟡 중립/관망 필요 구간", "yellow"
        else: status_txt, g_col = "🔴 대피/위험 주의 구간", "red"
            
        fig_g = go.Figure(go.Indicator(
            mode = "gauge+number", value = ai_score, domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': f"AI 퀀트 점수<br><span style='font-size:0.7em;color:{g_col}'>{status_txt}</span>", 'font': {'size': 26, 'color': 'white'}},
            gauge = {'axis': {'range': [0, 100], 'tickcolor': "white"}, 'bar': {'color': g_col}, 'steps': [{'range': [0, 45], 'color': "rgba(255,0,0,0.3)"}, {'range': [70, 100], 'color': "rgba(0,255,0,0.3)"}]}
        ))
        fig_g.update_layout(height=380, margin=dict(l=20, r=20, t=140, b=20), paper_bgcolor="#0E1117", font={'color': 'white'})
        st.plotly_chart(fig_g, use_container_width=True)

        pc1, pc2 = st.columns(2)
        pc1.markdown(f"<div class='price-card'><h4>🎯 AI 목표가 (1차 익절)</h4><h2 style='color:#00FF00;'>{target_p:,.0f}원</h2></div>", unsafe_allow_html=True)
        pc2.markdown(f"<div class='price-card'><h4>🛡️ AI 손절가 (최종 수비)</h4><h2 style='color:#FF4B4B;'>{stop_p:,.0f}원</h2></div>", unsafe_allow_html=True)

        st.markdown("<div class='ai-report'>", unsafe_allow_html=True)
        st.subheader("📊 심층 리포트")
        st.write(f"• **상태**: 현재 {user_input}은(는) {status_txt} 상태입니다.")
        st.write(f"• **추세**: {'20일 이동평균선 위에 위치하여 단기 추세가 견조합니다.' if curr_p > df['MA20'].iloc[-1] else '20일 이동평균선 아래로 내려와 단기적인 지지가 필요합니다.'}")
        st.write(f"• **리스크**: {'현재 파동 저점이 명확하지 않아 기술적 지표인 20일선이나 임의 비율(-7%)을 기준으로 손절가가 설정되었습니다.' if len(vls) == 0 else '최근 형성된 파동의 저점을 기준으로 안전하게 손절가가 설정되었습니다.'}")
        st.markdown("</div>", unsafe_allow_html=True)

    with tab3:
        st.subheader("📉 AI 퀀트 전략 백테스팅")
        m_ret, s_ret = df['Cum_Mkt'].iloc[-1]-100, df['Cum_Strat'].iloc[-1]-100
        br1, br2 = st.columns(2)
        br1.metric("단순 보유(존버)", f"{m_ret:+.2f}%")
        br2.metric("AI 퀀트 전략", f"{s_ret:+.2f}%", f"{s_ret-m_ret:+.2f}%p")
        
        fig_bt = go.Figure()
        fig_bt.add_trace(go.Scatter(x=df.index, y=df['Cum_Mkt'], name="시장 수익률", line=dict(color='gray', width=2)))
        fig_bt.add_trace(go.Scatter(x=df.index, y=df['Cum_Strat'], name="전략 수익률", line=dict(color='#00FF00', width=3)))
        fig_bt.add_trace(go.Scatter(x=df.index, y=df['AI_Score'], name="AI 점수 히스토리", yaxis="y2", line=dict(color='yellow', width=1, dash='dot')))
        fig_bt.update_layout(height=450, template="plotly_dark", yaxis2=dict(overlaying="y", side="right", range=[0, 100], title="AI Score"))
        st.plotly_chart(fig_bt, use_container_width=True)

    with tab4:
        st.subheader("⚡ 실시간 뉴스")
        n1, n2 = st.columns(2)
        with n1:
            for n in get_news(): st.markdown(f"<div class='news-box'><a href='{n['link']}' target='_blank' style='color:white;text-decoration:none;'>{n['title']}</a><br><small>{n['date']}</small></div>", unsafe_allow_html=True)
        with n2:
            for n in get_news(user_input): st.markdown(f"<div class='news-box'><a href='{n['link']}' target='_blank' style='color:white;text-decoration:none;'>{n['title']}</a><br><small>{n['date']}</small></div>", unsafe_allow_html=True)
else:
    st.error("데이터 로드 실패")
