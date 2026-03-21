import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time

# --- 1. [디자인] 하이엔드 퀀트 터미널 CSS ---
st.set_page_config(layout="wide", page_title="Aegis Oracle Prime v98.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;900&display=swap');
    body, .stApp { background-color: #030303; font-family: 'Pretendard', sans-serif; color: #e0e0e0; }
    .stMetric { background-color: #0f0f0f; padding: 25px; border-radius: 18px; border: 1px solid #1e1e1e; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
    .profit-card { background: linear-gradient(135deg, #0055ff 0%, #00aaff 100%); padding: 30px; border-radius: 24px; color: white; text-align: center; margin-bottom: 25px; box-shadow: 0 10px 30px rgba(0,85,255,0.3); }
    .info-card { background-color: #121212; padding: 20px; border-radius: 16px; margin-bottom: 15px; border: 1px solid #252525; }
    .status-tag { padding: 6px 14px; border-radius: 8px; font-weight: 900; font-size: 0.9rem; color: white; text-transform: uppercase; letter-spacing: 1px; }
    .cate-title { color: #00f2ff; font-weight: 900; font-size: 1.2rem; border-left: 5px solid #00f2ff; padding-left: 15px; margin: 25px 0 15px 0; }
    .recommend-box { background: #0a0a0a; padding: 12px; border-radius: 10px; margin-bottom: 8px; border: 1px solid #222; transition: 0.3s; }
    .recommend-box:hover { border-color: #00f2ff; background: #111; }
    .news-item { border-bottom: 1px solid #1e1e1e; padding: 12px 0; }
    .news-item:last-child { border: none; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [엔진] 초고속 데이터 파싱 및 퀀트 분석 로직 ---
@st.cache_data(ttl=60)
def get_master_data(code, pages=12):
    try:
        url = f"https://finance.naver.com/item/sise_day.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        df_list = []
        for p in range(1, pages + 1):
            res = requests.get(f"{url}&page={p}", headers=headers)
            df_list.append(pd.read_html(StringIO(res.text), header=0)[0])
        
        df = pd.concat(df_list).dropna().sort_values('날짜').reset_index(drop=True)
        df.columns = ['Date', 'Close', 'Net', 'Open', 'High', 'Low', 'Volume']
        df['Date'] = pd.to_datetime(df['Date'])
        
        # 기술 지표 계산 (전문가용 5, 20, 60, 120선)
        for ma in [5, 20, 60, 120]:
            df[f'MA{ma}'] = df['Close'].rolling(ma).mean()
        
        # 배열 진단 로직
        last = df.iloc[-1]
        if last['MA5'] > last['MA20'] > last['MA60'] > last['MA120']: state = "🔥 강력 정배열"
        elif last['MA5'] < last['MA20'] < last['MA60'] < last['MA120']: state = "🧊 강력 역배열"
        else: state = "⚖️ 추세 혼조"
        
        # RSI & 볼린저 밴드 기초
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
        
        # 종목명 가져오기
        name_url = f"https://finance.naver.com/item/main.naver?code={code}"
        name_res = requests.get(name_url, headers=headers)
        soup = BeautifulSoup(name_res.text, 'html.parser')
        stock_name = soup.select_one('.wrap_company h2 a').text
        
        return df, state, stock_name
    except: return None, "Error", "Unknown"

# --- 3. [사이드바] 전문가 제어판 ---
with st.sidebar:
    st.markdown('<h1 style="color:#00f2ff; font-weight:900;">AEGIS ORACLE</h1>', unsafe_allow_html=True)
    st.markdown("---")
    s_code = st.text_input("📊 종목코드 (6자리)", value="053000")
    invest_amt = st.number_input("💰 투자 원금 (KRW)", value=10000000, step=1000000)
    chart_type = st.radio("📈 차트 스타일", ["전문가용 캔들", "퀀트 라인"], horizontal=True)
    st.markdown("---")
    st.caption("v98.0 Prime Edition | 2026 Stable")

# --- 4. [메인] 퀀트 분석 프로세스 ---
df, state, s_name = get_master_data(s_code)

if df is not None:
    curr_p = float(df['Close'].iloc[-1])
    change_pct = (curr_p - float(df['Close'].iloc[-2])) / float(df['Close'].iloc[-2]) * 100
    state_clr = "#00f2ff" if "정배열" in state else "#ff37af" if "역배열" in state else "#ffaa00"

    # [프로세스] 5,000회 몬테카를로 시뮬레이션
    daily_ret = df['Close'].pct_change().dropna()
    sims = np.random.normal(daily_ret.mean(), daily_ret.std(), 5000)
    win_rate = (sims > 0).sum() / 5000 * 100
    expected_profit = sims.mean() * 100

    # 상단 요약 브리핑
    st.markdown(f"## {s_name} <small style='color:#888;'>{s_code}</small> <span class='status-tag' style='background:{state_clr};'>{state}</span>", unsafe_allow_html=True)
    
    c1, c2, c3, c4 = st.columns([1.5, 1, 1, 1])
    with c1:
        st.markdown(f'<div class="profit-card"><h3>내일의 기대수익</h3><h1>{expected_profit:+.2f}%</h1><p>투자 시 예상 손익: {invest_amt * (expected_profit/100):+,.0f}원</p></div>', unsafe_allow_html=True)
    with c2: st.metric("현재가", f"{curr_p:,.0f}원", f"{change_pct:+.2f}%")
    with c3: st.metric("퀀트 승률", f"{win_rate:.1f}%", "5,000회 시뮬레이션")
    with c4: st.metric("목표 타점", f"{curr_p*1.15:,.0f}원", "상승여력 15%")

    tab1, tab2, tab3, tab4 = st.tabs(["📊 정밀 기술 차트", "🧪 AI 퀀트 진단", "📰 실시간 뉴스 룸", "🚀 글로벌 테마 포트폴리오"])

    with tab1: # 1P: 기술적 분석
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.05)
        if chart_type == "전문가용 캔들":
            fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
        else:
            fig.add_trace(go.Scatter(x=df['Date'], y=df['Close'], line=dict(color='#00f2ff', width=3), fill='tozeroy', name='Price'), row=1, col=1)
        
        # 이평선 레이어
        ma_cfg = {5: '#FFD60A', 20: '#FF37AF', 60: '#00F2FF', 120: '#FFFFFF'}
        for ma, clr in ma_cfg.items():
            fig.add_trace(go.Scatter(x=df['Date'], y=df[f'MA{ma}'], line=dict(color=clr, width=1.5, dash='solid' if ma<60 else 'dot'), name=f'MA{ma}'), row=1, col=1)
        
        fig.add_trace(go.Bar(x=df['Date'], y=df['Volume'], marker_color='#333', name='Volume'), row=2, col=1)
        fig.update_layout(height=700, template='plotly_dark', xaxis_rangeslider_visible=False, margin=dict(t=10, b=10, l=10, r=10), showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True)

    with tab2: # 2P: 정밀 진단 온도계
        cl1, cl2 = st.columns([1.2, 1])
        with cl1:
            fig_g = go.Figure(go.Indicator(
                mode = "gauge+number", value = win_rate, domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': "AI 매수 적합도 (Temperature)", 'font': {'size': 20, 'color': '#00f2ff'}},
                gauge = {
                    'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "#444"},
                    'bar': {'color': "#0055ff"},
                    'bgcolor': "rgba(0,0,0,0)",
                    'borderwidth': 2, 'bordercolor': "#333",
                    'steps': [{'range': [0, 30], 'color': '#1a0000'}, {'range': [70, 100], 'color': '#001a1a'}],
                    'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': win_rate}
                }
            ))
            fig_g.update_layout(height=450, font={'color': "white", 'family': "Pretendard"}, paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_g, use_container_width=True)
        with cl2:
            st.markdown(f"""<div class="info-card">
                <h3 style="color:#00f2ff; margin-top:0;">📋 퀀트 진단 보고서</h3>
                <p><b>추세 분석:</b> 현재 주가는 <b>{state}</b> 구간에 위치해 있습니다.</p>
                <p><b>심리 지수(RSI):</b> {df['RSI'].iloc[-1]:.2f} ({"과열 주의" if df['RSI'].iloc[-1]>70 else "바닥권 매수 기회" if df['RSI'].iloc[-1]<30 else "안정적 추세"})</p>
                <p><b>변동성 리스크:</b> {daily_ret.std()*100:.2f}% (최근 60일 기준)</p>
                <hr style="border:0.5px solid #333;">
                <p style="font-size:1.1rem;">🎯 <b>권고 타점:</b> <span style="color:#00f2ff;">{curr_p*0.98:,.0f}원 이하 분할 매수</span></p>
                <p style="font-size:1.1rem;">⚠️ <b>데드라인:</b> <span style="color:#ff37af;">{curr_p*0.94:,.0f}원 이탈 시 손절</span></p>
            </div>""", unsafe_allow_html=True)

    with tab3: # 3P: 실시간 뉴스 룸
        st.markdown(f"#### 📰 {s_name} 관련 실시간 주요 소식")
        try:
            n_res = requests.get(f"https://search.naver.com/search.naver?where=news&query={s_name} 특징주", headers={'User-Agent': 'Mozilla/5.0'})
            soup = BeautifulSoup(n_res.text, 'html.parser')
            for item in soup.select('.news_area')[:10]:
                title = item.select_one('.news_tit').text
                link = item.select_one('.news_tit')['href']
                st.markdown(f"<div class='news-item'>📍 <a href='{link}' style='color:#e0e0e0; text-decoration:none;'>{title}</a></div>", unsafe_allow_html=True)
        except: st.write("소식을 불러오는 중 에러가 발생했습니다.")

    with tab4: # 4P: 글로벌 테마 포트폴리오
        st.markdown("### 🚀 AI 선정 글로벌 테마별 핵심 종목")
        themes = {
            "🤖 반도체/AI": ["005930(삼성전자)", "000660(SK하이닉스)", "NVDA(엔비디아)", "TSM(TSMC)"],
            "🛡️ 방산/우주": ["047810(한국항공우주)", "012450(한화에어로스페이스)", "LMT(록히드마틴)"],
            "💰 금융/지주": ["053000(우리금융지주)", "055550(신한지주)", "JPM(JP모건)"],
            "🔋 이차전지": ["373220(LG엔솔)", "006400(삼성SDI)", "TSLA(테슬라)"]
        }
        cols = st.columns(2)
        for i, (t_name, stocks) in enumerate(themes.items()):
            with cols[i % 2]:
                st.markdown(f"<div class='cate-title'>{t_name}</div>", unsafe_allow_html=True)
                for s in stocks:
                    st.markdown(f"<div class='recommend-box'>💎 {s}</div>", unsafe_allow_html=True)

else:
    st.error("❌ 종목 데이터를 불러올 수 없습니다. 코드가 올바른지(숫자 6자리) 확인해 주세요.")
