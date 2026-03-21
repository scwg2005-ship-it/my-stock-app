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

# --- 1. [디자인] 증권사 프리미엄 VIP 터미널 CSS ---
st.set_page_config(layout="wide", page_title="Aegis Oracle Sovereign v101.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;900&display=swap');
    body, .stApp { background-color: #030303; font-family: 'Pretendard', sans-serif; color: #e0e0e0; }
    .stMetric { background-color: #0f0f0f; padding: 25px; border-radius: 18px; border: 1px solid #1e1e1e; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
    .profit-card { background: linear-gradient(135deg, #0055ff 0%, #00aaff 100%); padding: 30px; border-radius: 24px; color: white; text-align: center; margin-bottom: 25px; box-shadow: 0 10px 30px rgba(0,85,255,0.3); }
    .info-card { background-color: #121212; padding: 20px; border-radius: 16px; margin-bottom: 15px; border: 1px solid #252525; }
    .status-tag { padding: 6px 14px; border-radius: 8px; font-weight: 900; font-size: 0.9rem; color: white; text-transform: uppercase; letter-spacing: 1px; }
    .cate-title { color: #00f2ff; font-weight: 900; font-size: 1.2rem; border-left: 5px solid #00f2ff; padding-left: 15px; margin: 25px 0 15px 0; }
    .recommend-box { background: #0a0a0a; padding: 12px; border-radius: 10px; margin-bottom: 8px; border: 1px solid #222; }
    /* 알림 스타일 */
    .alert-box { background-color: #1e1e00; border: 2px solid #ffcc00; color: #ffcc00; padding: 15px; border-radius: 10px; font-weight: bold; margin-bottom: 20px; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [엔진] 하이브리드 데이터 로더 & 분석 (v101.0 최적화) ---
@st.cache_data(ttl=60)
def get_sovereign_data(symbol, invest_amt):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
        market_type = "KR" if symbol.isdigit() and len(symbol) == 6 else "US"
        
        # [데이터 통합 로드]
        if market_type == "KR":
            # 한국 주식 파싱 엔진 (稳定性 확보)
            ticker = symbol
            name_res = requests.get(f"https://finance.naver.com/item/main.naver?code={ticker}", headers=headers)
            name_soup = BeautifulSoup(name_res.text, 'html.parser')
            s_name = name_soup.select_one('.wrap_company h2 a').text.strip()
            
            df_list = []
            for p in range(1, 10): # 데이터 축적을 위해 10페이지 수집
                res = requests.get(f"https://finance.naver.com/item/sise_day.naver?code={ticker}&page={p}", headers=headers)
                dfs = pd.read_html(StringIO(res.text))
                df_list.append(dfs[0].dropna())
            df = pd.concat(df_list).reset_index(drop=True)
            df.columns = ['Date', 'Close', 'Net', 'Open', 'High', 'Low', 'Volume']
            df['Date'] = pd.to_datetime(df['Date'])
            
            # [기능 2] 국장 배당/재무 파싱 (연결 안정성 고려)
            try:
                fin_url = f"https://finance.naver.com/item/coinfo.naver?code={ticker}"
                fin_res = requests.get(fin_url, headers=headers)
                fin_soup = BeautifulSoup(fin_res.text, 'html.parser')
                
                # 배당수익률 (최근 결산)
                div_yield_tag = fin_soup.select_one('.tb_type1.tb_num strong:-contains("배당수익률") + span')
                if div_yield_tag: div_yield = div_yield_tag.text.strip() + "%"
                else: div_yield = "정보 없음"
                
                # 재무 요약 (간단 매출/영업이익)
                fin_table = pd.read_html(StringIO(str(fin_soup.select_one('.tb_type1.tb_num'))))[0]
                fin_summary = f"매출(억원): {fin_table.iloc[0, 1]}, 영업이익(억원): {fin_table.iloc[1, 1]}"
                
            except:
                div_yield = "연결 실패"
                fin_summary = "재무 연결 실패"

        else:
            # [기능 4] 미장 통합 로드 엔진 (Stable yfinance)
            ticker = symbol.upper()
            raw = yf.download(ticker, period="2y", interval="1d", progress=False)
            df = raw.copy()
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df.columns = [str(c).capitalize() for c in df.columns]
            df.index = pd.to_datetime(df.index).tz_localize(None)
            df = df.apply(pd.to_numeric, errors='coerce').dropna(subset=['Close'])
            df = df.sort_index().reset_index()
            df.rename(columns={'index': 'Date'}, inplace=True)
            
            # 미장 재무/배당 (yfinance 사용)
            ticker_obj = yf.Ticker(ticker)
            info = ticker_obj.info
            s_name = info.get('longName', ticker)
            
            # 배당수익률
            div_yield_val = info.get('dividendYield', 0)
            div_yield = f"{div_yield_val*100:.2f}%" if div_yield_val > 0 else "무배당"
            
            # 재무 요약
            fin_summary = f"매출(억$): {info.get('totalRevenue', 0)/1e8:.2f}, 영업이익(억$): {info.get('operatingCashflow', 0)/1e8:.2f}"

        # --- [퀀트 분석 공통 프로세스] ---
        # 기술 지표
        for ma in [5, 20, 60, 120]:
            if len(df) >= ma: df[f'MA{ma}'] = df['Close'].rolling(ma).mean()
        
        # 배열 판독
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        if 'MA120' in df.columns:
            if last['MA5'] > last['MA20'] > last['MA60'] > last['MA120']: state = "🔥 강력 정배열"
            elif last['MA5'] < last['MA20'] < last['MA60'] < last['MA120']: state = "🧊 강력 역배열"
            else: state = "⚖️ 추세 혼조"
        else: state = "데이터 축적중"
        
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
        
        # --- [기능 1] 자동 알림(Alert) 로직 ---
        alerts = []
        # 골든크로스 (5일선이 20일선 돌파)
        if last['MA5'] > last['MA20'] and prev['MA5'] <= prev['MA20']:
            alerts.append("🔔 골든크로스 발생 (5선 > 20선)")
        # 과매도 신호 (RSI 30 이하)
        if last['RSI'] <= 30:
            alerts.append("⚠️ 과매도 구간 진입 (RSI 30 이하)")
        
        # 몬테카를로 시뮬레이션
        daily_ret = df['Close'].pct_change().dropna()
        sims = np.random.normal(daily_ret.mean(), daily_ret.std() if daily_ret.std() > 0 else 0.01, 5000)
        win_rate = (sims > 0).sum() / 5000 * 100
        expected_profit = sims.mean() * 100

        return df, s_name, state, alerts, expected_profit, win_rate, div_yield, fin_summary, market_type

    except: return None, "Error", "Error", [], 0, 0, "N/A", "N/A", "Error"

# --- 3. [사이드바] 전문가 제어판 ---
with st.sidebar:
    st.markdown('<h1 style="color:#00f2ff; font-weight:900;">AEGIS ORACLE</h1>', unsafe_allow_html=True)
    st.markdown("---")
    s_symbol = st.text_input("📊 종목코드 (국장 6자리 / 미장 티커)", value="053000") # 우리금융지주
    invest_amt = st.number_input("💰 투자 원금 설정", value=10000000)
    st.info("💡 국장: 053000(우리), 005930(삼성) / 미장: NVDA(엔비디아), TSLA(테슬라)")
    st.markdown("---")
    st.caption("v101.0 Sovereign Edition | Stable Engine")

# --- 4. [메인] 분석 프로세스 가동 ---
df, s_name, state, alerts, exp_profit, win_rate, div_yield, fin_sum, m_type = get_sovereign_data(s_symbol, invest_amt)

if df is not None and not df.empty:
    curr_p = float(df['Close'].iloc[-1])
    unit = "원" if m_type == "KR" else "$"
    state_clr = "#00f2ff" if "정배열" in state else "#ff37af" if "역배열" in state else "#ffaa00"

    # 상단 요약 브리핑
    st.markdown(f"## {s_name} ({s_symbol}) <span class='status-tag' style='background:{state_clr};'>{state}</span>", unsafe_allow_html=True)
    
    # [기능 1] 알림 영역 (Alert Area)
    if alerts:
        st.markdown(f'<div class="alert-box">{" | ".join(alerts)}</div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns([1.5, 1, 1, 1])
    with c1:
        st.markdown(f'<div class="profit-card"><h3>내일의 기대수익</h3><h1>{exp_profit:+.2f}%</h1><p>투자 시 예상 손익: {invest_amt * (exp_profit/100):+,.0f}{unit}</p></div>', unsafe_allow_html=True)
    with c2: st.metric("현재가", f"{curr_p:,.0f}{unit}"); st.metric("승률", f"{win_rate:.1f}%")
    with c3: st.metric("배당수익률", div_yield); st.metric("퀀트 분석 구간", state)
    with c4: st.metric("목표가(+12%)", f"{curr_p*1.12:,.0f}{unit}"); st.metric("손절가(-6%)", f"{curr_p*0.94:,.0f}{unit}")

    tab1, tab2, tab3, tab4 = st.tabs(["📉 전문가 분석 차트", "🧪 정밀 퀀트 온도계", "📊 재무/뉴스 브리핑", "🚀 글로벌 테마 포트폴리오"])

    with tab1: # 1P: 기술 분석
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.05)
        fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='시세'), row=1, col=1)
        for ma, clr in zip(['MA5', 'MA20', 'MA60', 'MA120'], ['#FFD60A', '#FF37AF', '#00F2FF', '#FFFFFF']):
            if ma in df.columns: fig.add_trace(go.Scatter(x=df['Date'], y=df[ma], line=dict(color=clr, width=1.2), name=ma), row=1, col=1)
        fig.add_trace(go.Bar(x=df['Date'], y=df['Volume'], marker_color='#333'), row=2, col=1)
        fig.update_layout(height=650, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig, use_container_width=True)

    with tab2: # 2P: 정밀 온도계
        cl1, cl2 = st.columns([1.2, 1])
        with cl1:
            # 전문가용 Gauge 차트
            fig_g = go.Figure(go.Indicator(mode="gauge+number", value=win_rate, domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': "AI 매수 온도 (Temperature)", 'font': {'size': 20, 'color': '#00f2ff'}},
                gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "#0055ff"}, 'bgcolor': "rgba(0,0,0,0)",
                        'steps': [{'range': [0, 40], 'color': '#1a0000'}, {'range': [70, 100], 'color': '#001a1a'}]}))
            fig_g.update_layout(height=450, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)'); st.plotly_chart(fig_g, use_container_width=True)
        with cl2:
            # RSI 온도계
            curr_rsi = df['RSI'].iloc[-1]
            fig_rsi = go.Figure(go.Indicator(mode = "gauge+number", value = curr_rsi, domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': "RSI 심리 강도"}, gauge = {'axis': {'range': [0, 100]},
                    'bar': {'color': "#FF37AF" if curr_rsi > 70 or curr_rsi < 30 else "#FFFFFF"},
                    'steps': [{'range': [0, 30], 'color': '#001a00'}, {'range': [70, 100], 'color': '#1a0000'}]}))
            fig_rsi.update_layout(height=250, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)'); st.plotly_chart(fig_rsi, use_container_width=True)

    with tab3: # 3P: 재무 및 뉴스
        st.markdown(f"#### 📊 {s_name} 재무/배당 브리핑")
        st.markdown(f'<div class="info-card"><b>배당수익률:</b> {div_yield}<br><b>최근 재무 요약:</b> {fin_sum}</div>', unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown(f"#### 📰 실시간 특징주 뉴스")
        if m_type == "KR":
            try:
                n_res = requests.get(f"https://search.naver.com/search.naver?where=news&query={s_name} 특징주", headers=headers)
                n_soup = BeautifulSoup(n_res.text, 'html.parser')
                for item in n_soup.select('.news_area')[:8]:
                    st.markdown(f"📍 [{item.select_one('.news_tit').text}]({item.select_one('.news_tit')['href']})")
            except: st.write("뉴스를 불러올 수 없습니다.")
        else:
            st.write("미국 주식 뉴스는 인베스팅닷컴 등 외부 링크를 활용하세요.")
            st.markdown(f"- [{s_name} 인베스팅닷컴 뉴스 보기](https://kr.investing.com/search/?q={s_name})")

    with tab4: # 4P: 글로벌 테마 포트폴리오
        st.write("### 🚀 글로벌 핵심 테마 포트폴리오 (Hybird Picker)")
        themes = {
            "🤖 AI/반도체": ["NVDA(US)", "SK하이닉스(KR)", "TSM(US)", "ASML(US)", "005930(KR)"],
            "💰 금융/비트코인": ["우리금융지주(KR)", "KB금융(KR)", "JPM(US)", "COIN(US)", "MSTR(US)"],
            "🛡️ K-방산/우주": ["한화에어로스페이스(KR)", "LIG넥스원(KR)", "RTX(US)", "LMT(US)"]
        }
        cols = st.columns(3)
        for i, (t_name, stocks) in enumerate(themes.items()):
            with cols[i]:
                st.markdown(f"<div class='cate-title'>{t_name}</div>", unsafe_allow_html=True)
                for s in stocks:
                    st.markdown(f"<div class='recommend-box'>💎 {s}</div>", unsafe_allow_html=True)

else:
    st.error("❌ 데이터를 불러올 수 없습니다. 종목코드를 확인하세요. (국장: 053000 / 미장: AAPL)")
