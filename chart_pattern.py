import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO
from bs4 import BeautifulSoup

# --- 1. [VIP 터미널 디자인] (가시성 & 무지개 테마) ---
st.set_page_config(layout="wide", page_title="Aegis Oracle Chroma v120.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;900&display=swap');
    body, .stApp { background-color: #030303; font-family: 'Pretendard'; color: #e0e0e0; }
    .stMetric { background-color: #0f0f0f; padding: 25px; border-radius: 18px; border: 1px solid #1e1e1e; }
    .profit-card { background: linear-gradient(135deg, #0055ff, #00aaff); padding: 30px; border-radius: 24px; color: white; text-align: center; margin-bottom: 25px; }
    .verdict-box { background-color: #0e1621; border: 2px solid #00f2ff; padding: 20px; border-radius: 15px; margin-bottom: 20px; }
    /* 알림 스타일 (v119.0 유지) */
    .alert-box { background: linear-gradient(90deg, #ffcc00, #ff9900); color: black; padding: 15px; border-radius: 10px; font-weight: 900; text-align: center; margin-bottom: 20px; font-size: 1.2rem; }
    /* 가이드 박스 (v109.0 유지) */
    .guide-box { background-color: #0a0f1e; border: 1px dashed #00f2ff; padding: 20px; border-radius: 15px; margin-top: 20px; }
    .guide-title { color: #00f2ff; font-weight: 900; font-size: 1.2rem; margin-bottom: 10px; }
    .highlight { color: #00f2ff; font-weight: 800; }
    .recommend-box { background: #111; padding: 15px; border-radius: 12px; border: 1px solid #333; margin-bottom: 10px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [엔진] 무적의 로더 & 무지개 분석 엔진 ---
@st.cache_data(ttl=60)
def get_chroma_imperial_data(symbol):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        is_kr = symbol.isdigit() and len(symbol) == 6
        if is_kr:
            # 국장 데이터 로드 (v103.0 무적 엔진)
            df_list = []
            for p in range(1, 10):
                url = f"https://finance.naver.com/item/sise_day.naver?code={symbol}&page={p}"
                res = requests.get(url, headers=headers)
                df_list.append(pd.read_html(StringIO(res.text))[0].dropna())
            df = pd.concat(df_list).reset_index(drop=True)
            df.columns = ['Date', 'Close', 'Net', 'Open', 'High', 'Low', 'Volume']
            df['Date'] = pd.to_datetime(df['Date'])
            m_type = "KR"
            n_res = requests.get(f"https://finance.naver.com/item/main.naver?code={symbol}", headers=headers)
            soup = BeautifulSoup(n_res.text, 'html.parser')
            s_name = soup.select_one('.wrap_company h2 a').text.strip() if soup.select_one('.wrap_company h2 a') else symbol
        else:
            # 미장 데이터 로드
            df = yf.download(symbol.upper(), period="2y", progress=False).reset_index()
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df.columns = [str(c).capitalize() for c in df.columns]
            s_name = symbol.upper()
            m_type = "US"

        df = df.sort_values('Date').reset_index(drop=True)
        
        # 지표 연산 (v107.0 복원)
        for ma in [5, 20, 60, 120]: df[f'MA{ma}'] = df['Close'].rolling(ma).mean()
        std = df['Close'].rolling(20).std()
        df['BB_U'], df['BB_L'] = df['MA20'] + (std * 2), df['MA20'] - (std * 2)
        
        # RSI
        delta = df['Close'].diff(); gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))

        # 몬테카를로 (5,000회 및 raw data sims 추가 반환)
        ret = df['Close'].pct_change().dropna()
        sims = np.random.normal(ret.mean(), ret.std() if ret.std() > 0 else 0.01, 5000)
        win_rate = (sims > 0).sum() / 5000 * 100
        avg_profit = sims.mean() * 100

        # 알림 로직 (v119.0)
        alerts = []
        last = df.iloc[-1]; prev = df.iloc[-2]
        if 'MA20' in df.columns and last['MA5'] > last['MA20'] and prev['MA5'] <= prev['MA20']: alerts.append("🎯 [매수 신호] 골든크로스 발생 (5선 > 20선)")
        if 'RSI' in df.columns and last['RSI'] <= 30: alerts.append("⚠️ [과매도] RSI 30 이하! 기술적 반등 임박")
        if 'BB_L' in df.columns and last['Close'] <= df['BB_L'].iloc[-1]: alerts.append("🛡️ [침체선 터치] 확률적 저점 도달! 매수 찬스")

        return df, s_name, win_rate, avg_profit, m_type, sims, alerts
    except Exception as e:
        return None, str(e), 0, 0, "Error", [], []

# --- 3. [메인 화면 구성] ---
s_input = st.sidebar.text_input("📊 종목코드", value="053000") # 우리금융지주
invest_amt = st.sidebar.number_input("💰 투자금", value=10000000)

df, s_name, win_rate, avg_profit, m_type, sims, alerts = get_chroma_imperial_data(s_input)

if df is not None and not df.empty:
    curr_p = float(df['Close'].iloc[-1]); unit = "원" if m_type == "KR" else "$"
    
    st.markdown(f"## {s_name} ({s_input})")
    
    # [1] 실시간 매수 알림 표시 (v119.0 유지)
    if alerts:
        for alert in alerts:
            st.markdown(f'<div class="alert-box">{alert}</div>', unsafe_allow_html=True)
    
    # [2] AI 최종 종합 판정
    action = "🔥 적극 매수" if win_rate > 60 else "⚖️ 관망/보유"
    st.markdown(f"""<div class="verdict-box">
        <div style="color:#00f2ff; font-weight:800; margin-bottom:5px;">🤖 Oracle's Chroma Synthesis</div>
        <div style="font-size:1.6rem; font-weight:900;">{action}</div>
        <div>과거 데이터를 기반으로 무지개색 레인지와 5,000회 시뮬레이션을 종합 분석했습니다.</div>
    </div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1: st.markdown(f'<div class="profit-card"><h3>내일 기대수익</h3><h1>{avg_profit:+.2f}%</h1><p>예상 손익: {invest_amt*(avg_profit/100):+,.0f}{unit}</p></div>', unsafe_allow_html=True)
    with c2: st.metric("현재가", f"{curr_p:,.0f}{unit}"); st.metric("AI 승률", f"{win_rate:.1f}%")
    with c3: st.metric("목표가(+15%)", f"{curr_p*1.15:,.0f}{unit}"); st.metric("손절가(-6%)", f"{curr_p*0.94:,.0f}{unit}")

    tab1, tab2, tab3, tab4 = st.tabs(["📉 전문가 차트 분석", "🧪 지능형 무지개 온도계", "📰 재무/실시간 뉴스", "🚀 AI 엄선 테마"])

    with tab1: # 1P: 정밀 차트 (v107.0 복원 및 v109.0 볼린저 밴드 통합)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.05)
        # 캔들
        fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='시세'), row=1, col=1)
        # 이평선
        colors = {'MA5':'yellow', 'MA20':'magenta', 'MA60':'cyan', 'MA120':'white'}
        for ma, clr in colors.items():
            if f'MA{ma}' in df.columns: fig.add_trace(go.Scatter(x=df['Date'], y=df[ma], line=dict(color=clr, width=1.5), name=f'{ma}선'), row=1, col=1)
        # 예측 밴드 (v109.0)
        if 'BB_U' in df.columns:
            fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_U'], line=dict(color='rgba(255,55,175,0.3)', dash='dash'), name='과열선'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_L'], line=dict(color='rgba(0,170,255,0.3)', dash='dash'), fill='tonexty', fillcolor='rgba(0,170,255,0.03)', name='침체선'), row=1, col=1)
        # 거래량
        v_colors = ['#ff37af' if df['Close'].iloc[i] > df['Open'].iloc[i] else '#00aaff' for i in range(len(df))]
        fig.add_trace(go.Bar(x=df['Date'], y=df['Volume'], marker_color=v_colors, name='거래량'), row=2, col=1)
        fig.update_layout(height=650, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(t=0, b=0, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)
        # 전문가 조언 가이드 (v109.0 유지)
        st.markdown('<div class="guide-box"><div class="guide-title">🔍 전문가 조언: 차트 읽는 법</div>파란 침체선에 주가가 닿으면 매수, 빨간 과열선을 뚫으면 익절 타점으로 봅니다. 60일선(청록색) 지지 여부가 중요합니다.</div>', unsafe_allow_html=True)

    with tab2: # 2P: [핵심 업그레이드] 무지개 온도계 & 크로마 분포표
        st.markdown(f"#### 🧪 과거 데이터 기반 무지개 퀀트 분석")
        col1, col2 = st.columns([1, 1.2])
        with col1:
            # [기능 통합] Gauge에 무지개색 레인지 적용 (빨강 -> 파랑)
            fig_g = go.Figure(go.Indicator(mode="gauge+number", value=win_rate, domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': "AI 매수 온도 (Temperature)", 'font': {'size': 20, 'color': '#00f2ff'}},
                gauge = {
                    'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "#444"},
                    'bar': {'color': "#0055ff"}, # 게이지 바 색상
                    'bgcolor': "rgba(0,0,0,0)",
                    'borderwidth': 2, 'bordercolor': "#333",
                    'steps': [
                        {'range': [0, 20], 'color': '#1a0000'},   # 빨강 (위험)
                        {'range': [20, 40], 'color': '#1a0d00'},  # 주황
                        {'range': [40, 60], 'color': '#1a1a00'},  # 노랑 (중립)
                        {'range': [60, 80], 'color': '#001a0d'},  # 초록
                        {'range': [80, 100], 'color': '#00001a'}  # 파랑 (강력)
                    ],
                    'threshold': {'line': {'color': "white", 'width': 4}, 'thickness': 0.75, 'value': win_rate}
                }
            ))
            fig_g.update_layout(height=450, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_g, use_container_width=True)
        with col2:
            # [기능 통합] 수익률 분포 히스토그램에 크로마(그라데이션) 적용
            fig_h = go.Figure()
            # sims 데이터를 백분율로 변환
            sims_pct = sims * 100
            # 수익률 빈도 계산 (히스토그램의 데이터 소스)
            counts, bins = np.histogram(sims_pct, bins=50)
            bins_center = (bins[:-1] + bins[1:]) / 2
            
            # [핵심] 수익률 구간에 따라 무지개색 매핑 (빨강 <-> 파랑)
            # -10% 미만: 빨강, 0% 근처: 노랑, 10% 이상: 파랑
            colors = ['#ff37af' if b < -5 else '#ffaa00' if b < 0 else '#ffd60a' if b < 5 else '#00ffaa' if b < 10 else '#007AFF' for b in bins_center]
            
            fig_h.add_trace(go.Bar(x=bins_center, y=counts, marker_color=colors, name='시나리오 빈도', opacity=0.8, marker_line_width=0.5))
            
            # [복원] 0% 기준선
            fig_h.add_vline(x=0, line_width=2, line_dash="dash", line_color="white")
            fig_h.update_layout(title_text='5,000회 시뮬레이션 수익률 분포 (Chroma Histogram)', template='plotly_dark', xaxis_title='예상 수익률 (%)', yaxis_title='시나리오 빈도', height=450, bargap=0.01, paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_h, use_container_width=True)

        # 전문가 조언 가이드 (v109.0 유지 및 색상 설명 추가)
        st.markdown(f"""
        <div class="guide-box">
            <div class="guide-title">🧪 전문가 조언: 무지개 온도계 & 크로마 분포표 해석</div>
            1. <b>AI 승률 온도:</b> 온도가 <span style="color:#00ffaa;">초록색</span>을 넘어 <span style="color:#007AFF;">파란색</span> 구간에 진입했다면 과거 패턴상 <span class="highlight">승률이 압도적으로 높은 자리</span>입니다.<br>
            2. <b>크로마 분포표(오른쪽 그래프):</b> 수익률 막대가 <span style="color:#ff37af;">빨간색(하락)</span>보다 <span style="color:#007AFF;">파란색(상승)</span> 영역에 많고 넓게 분포할수록 <span class="highlight">대박 수익</span>의 기회가 열려 있다는 뜻입니다.<br>
            3. <b>결론:</b> 온도가 파랗게 타오르고, 오른쪽 그래프가 파란색 영역에 집중될 때가 가장 완벽한 매수 타이밍입니다.
        </div>
        """, unsafe_allow_html=True)

    with tab3: # 3P: 실시간 뉴스 룸 (v105.0 특징주 뉴스 통합)
        st.markdown(f"#### 📰 실시간 특징주 뉴스 룸")
        try:
            n_res = requests.get(f"https://search.naver.com/search.naver?where=news&query={s_name} 특징주", headers={'User-Agent': 'Mozilla/5.0'})
            n_soup = BeautifulSoup(n_res.text, 'html.parser')
            for item in n_soup.select('.news_area')[:10]: # 뉴스 10개 표시
                title = item.select_one('.news_tit').text
                link = item.select_one('.news_tit')['href']
                st.markdown(f"📍 [{title}]({link})")
        except: st.write("뉴스를 불러올 수 없습니다.")

    with tab4: # 4P: AI 엄선 초급등 테마 (v105.0 💎 등급제 통합)
        st.markdown("### 🚀 AI 선정 초급등 예상 핵심 섹터")
        themes = {
            "🤖 AI/반도체 (대장주)": ["NVDA 💎💎💎", "SK하이닉스 💎💎", "삼성전자 💎"],
            "💰 금융/저PBR (고수익)": ["우리금융지주 💎💎💎", "KB금융 💎💎"],
            "🛡️ K-방산/우주 (수주랠리)": ["한화에어로스페이스 💎💎💎", "LIG넥스원 💎💎"]
        }
        cols = st.columns(3)
        for i, (t, s) in enumerate(themes.items()):
            with cols[i]:
                st.markdown(f"<div class='cate-title'>{t}</div>", unsafe_allow_html=True)
                for stock in s: st.markdown(f"<div class='recommend-box'>🚀 {stock}</div>", unsafe_allow_html=True)
else:
    st.error("데이터 로드 실패. 잠시 후 새로고침해 주세요.")
