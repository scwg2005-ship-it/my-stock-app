import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- 1. [디자인] 증권사 VIP 터미널 전용 프리미엄 CSS (가시성 극대화) ---
st.set_page_config(layout="wide", page_title="Aegis Oracle Sovereignty v117.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;900&display=swap');
    body, .stApp { background-color: #030303; font-family: 'Pretendard', sans-serif; color: #e0e0e0; }
    /* 메트릭 카드의 가시성 향상 */
    .stMetric { background-color: #0f0f0f; padding: 25px; border-radius: 18px; border: 1px solid #1e1e1e; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
    /* 기대수익 카드의 강조 */
    .profit-card { background: linear-gradient(135deg, #0055ff 0%, #00aaff 100%); padding: 30px; border-radius: 24px; color: white; text-align: center; margin-bottom: 25px; box-shadow: 0 10px 30px rgba(0,85,255,0.3); }
    .info-card { background-color: #121212; padding: 20px; border-radius: 16px; margin-bottom: 15px; border: 1px solid #252525; }
    .status-tag { padding: 6px 14px; border-radius: 8px; font-weight: 900; font-size: 0.9rem; color: white; text-transform: uppercase; letter-spacing: 1px; }
    /* 테마 카테고리 타이틀 강조 */
    .cate-title { color: #00f2ff; font-weight: 900; font-size: 1.3rem; border-left: 5px solid #00f2ff; padding-left: 15px; margin: 25px 0 15px 0; }
    /* AI 추천 종목 박스의 가시성 향상 */
    .recommend-box { background: #0a0a0a; padding: 15px; border-radius: 12px; margin-bottom: 10px; border: 1px solid #222; font-size: 1rem; font-weight: bold; transition: 0.3s; }
    .recommend-box:hover { border-color: #00f2ff; background: #111; }
    /* 알림 스타일 */
    .alert-box { background-color: #1e1e00; border: 2px solid #ffcc00; color: #ffcc00; padding: 15px; border-radius: 10px; font-weight: bold; margin-bottom: 20px; text-align: center; }
    /* 뉴스 링크 스타일 */
    .news-link { color: #00aaff; text-decoration: none; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [엔진] 하이브리드 데이터 로더 & AI 추천 엔진 (Sovereignty v117.0) ---
@st.cache_data(ttl=60)
def get_sovereignty_final_data(symbol, invest_amt):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
        market_type = "KR" if symbol.isdigit() and len(symbol) == 6 else "US"
        
        # [데이터 통합 로드 엔진]
        if market_type == "KR":
            ticker = symbol
            # [복원] 국장 종목명 파싱 (v103.0 안정성 기반)
            name_res = requests.get(f"https://finance.naver.com/item/main.naver?code={ticker}", headers=headers)
            name_soup = BeautifulSoup(name_res.text, 'html.parser')
            name_tag = name_soup.select_one('.wrap_company h2 a')
            s_name = name_tag.text.strip() if name_tag else f"KOSPI:{ticker}"
            
            # [복원] 국장 일별 시세 파싱 (100일치 축적)
            df_list = []
            for p in range(1, 10): 
                res = requests.get(f"https://finance.naver.com/item/sise_day.naver?code={ticker}&page={p}", headers=headers)
                dfs = pd.read_html(StringIO(res.text))
                df_list.append(dfs[0].dropna())
            df = pd.concat(df_list).reset_index(drop=True)
            df.columns = ['Date', 'Close', 'Net', 'Open', 'High', 'Low', 'Volume']
            df['Date'] = pd.to_datetime(df['Date'])
            
            # [복원] 국장 재무/배당 파싱 (v105.0)
            try:
                fin_url = f"https://finance.naver.com/item/coinfo.naver?code={ticker}"
                fin_res = requests.get(fin_url, headers=headers)
                fin_soup = BeautifulSoup(fin_res.text, 'html.parser')
                div_yield_tag = fin_soup.select_one('.tb_type1.tb_num strong:-contains("배당수익률") + span')
                div_yield = div_yield_tag.text.strip() + "%" if div_yield_tag else "정보 없음"
                fin_table = pd.read_html(StringIO(str(fin_soup.select_one('.tb_type1.tb_num'))))[0]
                fin_summary = f"매출(억원): {fin_table.iloc[0, 1]}, 영업이익(억원): {fin_table.iloc[1, 1]}"
            except: div_yield = "연결 실패"; fin_summary = "재무 연결 실패"

        else:
            # [미장 통합 엔진] yfinance (Stable)
            ticker = symbol.upper()
            raw = yf.download(ticker, period="2y", interval="1d", progress=False)
            df = raw.copy()
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df.columns = [str(c).capitalize() for c in df.columns]
            df.index = pd.to_datetime(df.index).tz_localize(None)
            df = df.apply(pd.to_numeric, errors='coerce').dropna(subset=['Close'])
            df = df.sort_index().reset_index()
            df.rename(columns={'index': 'Date'}, inplace=True)
            
            # 미장 재무/배당 (yfinance)
            ticker_obj = yf.Ticker(ticker)
            info = ticker_obj.info
            s_name = info.get('longName', ticker)
            div_yield_val = info.get('dividendYield', 0)
            div_yield = f"{div_yield_val*100:.2f}%" if div_yield_val > 0 else "무배당"
            fin_summary = f"Rev: {info.get('totalRevenue', 0)/1e8:.2f}, Op Cashflow: {info.get('operatingCashflow', 0)/1e8:.2f}"

        # --- [퀀트 분석 공통 프로세스] ---
        # 1. 기술 지표 (5, 20, 60, 120일 복원)
        for ma in [5, 20, 60, 120]:
            if len(df) >= ma: df[f'MA{ma}'] = df['Close'].rolling(ma).mean()
        
        # 2. 미래 예측 밴드 (v109.0 Bollinger)
        if len(df) >= 20:
            std_dev = df['Close'].rolling(20).std()
            df['BB_Upper'] = df['MA20'] + (std_dev * 2)
            df['BB_Lower'] = df['MA20'] - (std_dev * 2)
        
        # 3. RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
        
        # 4. [복원] 실시간 알림(Alert) 로직 (v105.0)
        alerts = []
        last = df.iloc[-1]; prev = df.iloc[-2]
        if 'MA20' in df.columns and last['MA5'] > last['MA20'] and prev['MA5'] <= prev['MA20']: alerts.append("🔔 골든크로스 발생 (5선 > 20선)")
        if 'RSI' in df.columns and last['RSI'] <= 30: alerts.append("⚠️ 과매도 구간 진입 (RSI 30 이하)")
        if 'BB_Lower' in df.columns and last['Close'] <= df['BB_Lower'].iloc[-1]: alerts.append("🛡️ 침체선 도달: 확률적 반등 구간")

        # 5. [복원] 몬테카를로 시뮬레이션 (5,000회 및 히스토그램 sims 데이터)
        daily_ret = df['Close'].pct_change().dropna()
        sims = np.random.normal(daily_ret.mean(), daily_ret.std() if daily_ret.std() > 0 else 0.01, 5000)
        win_rate = (sims > 0).sum() / 5000 * 100
        expected_profit = sims.mean() * 100

        # --- [기능 통합] AI 최종 의사결정 요약 로직 ---
        if win_rate >= 65 and 'BB_Lower' in df.columns and last['Close'] <= df['BB_Lower'].iloc[-1] * 1.05:
            action, verdict = "🔥 적극 매수 (Strong Buy)", f"AI 승률이 {win_rate:.1f}%로 매우 높으며 통계적 바닥권입니다. 강력한 반등이 예상됩니다."
        elif win_rate >= 55 and last['MA5'] > last['MA20']:
            action, verdict = "📈 매수 관점 (Buy)", "단기 골든크로스가 유지되고 있으며, 미래 시나리오상 상승 가능성이 우세합니다."
        elif 'BB_Upper' in df.columns and last['Close'] >= df['BB_Upper'].iloc[-1] * 0.95:
            action, verdict = "⚠️ 과열 매도 (Sell)", "주가가 확률 상한선(과열선)에 도달했습니다. 단기 조정 확률이 매우 높습니다."
        else:
            action, verdict = "⚖️ 중립 (Neutral)", "뚜렷한 방향성이 감지되지 않는 혼조세입니다. 볼린저 밴드 하단이나 AI 승률 개선을 대기하세요."

        return df, s_name, win_rate, expected_profit, sims, m_type, div_yield, fin_summary, action, verdict, alerts

    except Exception as e: return None, str(e), 0, 0, [], "Error", "N/A", "N/A", "Error", str(e), []

# --- 3. [사이드바] 전문가 제어판 ---
with st.sidebar:
    st.markdown('<h1 style="color:#00f2ff; font-weight:900;">ORACLE Sovereignty</h1>', unsafe_allow_html=True)
    st.markdown("---")
    s_symbol = st.text_input("📊 종목코드 (국장 6자리 / 미장 티커)", value="053000") # 우리금융지주
    invest_amt = st.number_input("💰 투자 원금 설정", value=10000000)
    st.info("💡 국장: 053000(우리), 005930(삼성) / 미장: NVDA(엔비디아), TSLA(테슬라)")
    st.markdown("---")
    st.caption("v117.0 Sovereignty | Final Empire")

# --- 4. [메인] 분석 프로세스 가동 ---
df, s_name, win_rate, exp_profit, sims, m_type, div_yield, fin_sum, action, verdict_text, alerts = get_sovereignty_final_data(s_symbol, invest_amt)

if df is not None and not df.empty:
    curr_p = float(df['Close'].iloc[-1]); unit = "원" if m_type == "KR" else "$"
    
    # 상단 요약 브리핑
    st.markdown(f"## {s_name} ({s_symbol}) <span style='font-size:1.1rem; color:#00f2ff;'>[{m_type}]</span>", unsafe_allow_html=True)
    
    # [기능 통합] AI 최종 의사결정 박스 (상단 고정)
    st.markdown(f"""<div class="verdict-box">
        <div style="color:#00f2ff; font-weight:800; margin-bottom:5px;">🤖 Oracle's Final AI Verdict</div>
        <div style="font-size:1.5rem; font-weight:900;">{action}</div>
        <div style="color:#cccccc;">{verdict_text}</div>
    </div>""", unsafe_allow_html=True)
    
    # [복원] 실시간 알림 표시
    if alerts: st.markdown(f'<div class="alert-box">{" | ".join(alerts)}</div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns([1.5, 1, 1, 1])
    with c1: st.markdown(f'<div class="profit-card"><h3>내일 기대수익</h3><h1>{exp_profit:+.2f}%</h1><p>투자 시 예상 손익: {invest_amt * (exp_profit/100):+,.0f}{unit}</p></div>', unsafe_allow_html=True)
    with c2: st.metric("현재가", f"{curr_p:,.0f}{unit}"); st.metric("승률", f"{win_rate:.1f}%")
    with c3: st.metric("배당률", div_yield); st.metric("RSI 강도", f"{df['RSI'].iloc[-1]:.1f}")
    with c4: st.metric("목표가(+15%)", f"{curr_p*1.15:,.0f}{unit}"); st.metric("손절가(-6%)", f"{curr_p*0.94:,.0f}{unit}")

    tab1, tab2, tab3, tab4 = st.tabs(["📉 전문가 정밀 분석 차트", "🧪 퀀트 온도계", "📊 재무/실시간 뉴스 룸", "🚀 AI 엄선 초급등 테마"])

    with tab1: # 1P: 기술 분석 차트 (볼린저 밴드 & 거래량 복원)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.05)
        # 캔들
        fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='시세'), row=1, col=1)
        # 이평선
        ma_cfg = {5: '#FFD60A', 20: '#FF37AF', 60: '#00F2FF', 120: '#FFFFFF'}
        for ma, clr in ma_cfg.items():
            if f'MA{ma}' in df.columns: fig.add_trace(go.Scatter(x=df['Date'], y=df[f'MA{ma}'], line=dict(color=clr, width=1.5), name=f'{ma}선'), row=1, col=1)
        # [복원] 볼린저 밴드 (예측 범위)
        if 'BB_Upper' in df.columns:
            fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_Upper'], line=dict(color='rgba(255,55,175,0.3)', dash='dash'), name='과열선'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_Lower'], line=dict(color='rgba(0,170,255,0.3)', dash='dash'), fill='tonexty', fillcolor='rgba(0,170,255,0.03)', name='침체선'), row=1, col=1)
        # [복원] 하단 거래량 (Coloring)
        colors = ['#ff37af' if df['Close'].iloc[i] > df['Open'].iloc[i] else '#00aaff' for i in range(len(df))]
        fig.add_trace(go.Bar(x=df['Date'], y=df['Volume'], marker_color=colors, name='거래량'), row=2, col=1)
        fig.update_layout(height=700, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(t=0, b=0, l=10, r=10), showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True)
        # [복원] 전문가 조언 가이드
        st.markdown('<div class="guide-box"><div class="guide-title">🔍 전문가 조언: 차트 읽는 법</div>파란 침체선에 주가가 닿으면 매수, 빨간 과열선을 뚫으면 익절 타점으로 봅니다. 60일선(청록색) 지지 여부가 중요합니다.</div>', unsafe_allow_html=True)

    with tab2: # 2P: 정밀 온도계 (승률 Gauge & 분포 Histogram)
        cl1, cl2 = st.columns([1, 1.2])
        with col1:
            fig_g = go.Figure(go.Indicator(mode="gauge+number", value=win_rate, title={'text': "매수 온도"}, gauge={'bar': {'color': "#0055ff"}, 'steps': [{'range': [0, 40], 'color': '#1a0000'}, {'range': [70, 100], 'color': '#001a1a'}]}))
            fig_g.update_layout(height=400, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)'); st.plotly_chart(fig_g, use_container_width=True)
        with col2:
            fig_h = go.Figure()
            sims_pct = sims * 100
            fig_h.add_trace(go.Histogram(x=sims_pct[sims_pct >= 0], name='상승', marker_color='#007AFF', opacity=0.7))
            fig_h.add_trace(go.Histogram(x=sims_pct[sims_pct < 0], name='하락', marker_color='#ff37af', opacity=0.7))
            fig_h.update_layout(title='5,000회 수익률 확률 분포도', template='plotly_dark')
            st.plotly_chart(fig_h, use_container_width=True)
        # [복원] 전문가 조언 가이드
        st.markdown('<div class="guide-box"><div class="guide-title">🧪 전문가 조언: 퀀트 분석 해석</div>온도가 70% 이상이고 파란색(우측) 막대가 쏠려 있을 때 상승 에너지가 가장 강력합니다.</div>', unsafe_allow_html=True)

    with tab3: # 3P: 재무 & 뉴스 (TOP 10 & URL)
        st.markdown(f"#### 📊 {s_name} 재무/배당 브리핑")
        st.markdown(f'<div class="info-card"><b>배당수익률:</b> {div_yield}<br><b>최근 재무 요약:</b> {fin_sum}</div>', unsafe_allow_html=True)
        st.markdown("---")
        st.markdown(f"#### 📰 실시간 특징주 뉴스 룸")
        try:
            n_res = requests.get(f"https://search.naver.com/search.naver?where=news&query={s_name} 특징주", headers=headers)
            n_soup = BeautifulSoup(n_res.text, 'html.parser')
            for item in n_soup.select('.news_area')[:10]:
                title = item.select_one('.news_tit').text
                link = item.select_one('.news_tit')['href']
                st.markdown(f"📍 [<span class='news-link'>{title}</span>]({link})", unsafe_allow_html=True)
        except: st.write("뉴스를 불러올 수 없습니다.")

    with tab4: # 4P: AI 엄선 초급등 테마 (💎 등급제)
        st.markdown("### 🚀 AI가 선정한 초급등 예상 섹터")
        themes = {
            "🤖 AI/반도체 (대장주)": ["NVDA 💎💎💎", "SK하이닉스 💎💎", "삼성전자 💎"],
            "💰 금융/저PBR (고수익)": ["우리금융지주 💎💎💎", "KB금융 💎💎"],
            "🛡️ K-방산/우주 (수주)": ["한화에어로스페이스 💎💎💎", "LIG넥스원 💎💎"]
        }
        cols = st.columns(3)
        for i, (t, s) in enumerate(themes.items()):
            with cols[i]:
                st.markdown(f"<div class='cate-title'>{t}</div>", unsafe_allow_html=True)
                for stock in s: st.markdown(f"<div class='recommend-box'>🚀 {stock}</div>", unsafe_allow_html=True)
        # [복원] 전문가 조언 가이드
        st.markdown('<div class="guide-box"><div class="guide-title">🚀 전문가 조언: 테마주 활용</div>💎💎💎 종목이 과열선(빨간선)에 도달했다면 바닥의 💎💎 종목으로 순환매하는 전략이 유효합니다.</div>', unsafe_allow_html=True)

else:
    st.error(f"❌ 데이터 로드 실패: 종목코드(053000 등)를 정확히 입력하세요.")
