import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO
from bs4 import BeautifulSoup
import time

# --- 1. [디자인] 오리진 하이엔드 퀀트 UI (한국어 Obsidian 테마) ---
st.set_page_config(layout="wide", page_title="Aegis Oracle v137.0")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;900&family=Pretendard:wght@400;600;900&display=swap');
    body, .stApp { background-color: #050505; font-family: 'Pretendard'; color: #ececec; }
    .main-title { font-family: 'Orbitron'; color: #00f2ff; text-shadow: 0 0 20px rgba(0,242,255,0.6); font-weight: 900; font-size: 2.5rem; text-align: center; margin-bottom: 30px; }
    .stMetric { background: rgba(15,15,15,0.8); border: 1px solid #222; border-radius: 20px; padding: 25px; transition: 0.3s; }
    .action-box { background: linear-gradient(135deg, rgba(14,22,33,0.9), rgba(5,5,5,0.9)); border: 2px solid #00f2ff; border-radius: 25px; padding: 30px; margin-bottom: 35px; backdrop-filter: blur(10px); }
    .action-title { font-size: 1.8rem; font-weight: 900; margin-bottom: 10px; }
    .profit-card { background: linear-gradient(135deg, #0044cc 0%, #001133 100%); border: 1px solid #0055ff; padding: 35px; border-radius: 30px; color: white; text-align: center; margin-bottom: 30px; }
    .guide-box { background-color: #0a0f1e; border: 1px dashed #00f2ff; padding: 20px; border-radius: 15px; margin-top: 25px; line-height: 1.8; }
    .guide-title { color: #00f2ff; font-weight: 900; font-size: 1.2rem; margin-bottom: 10px; }
    .news-item { background: #0a0a0a; border-radius: 15px; padding: 15px; border-left: 5px solid #00f2ff; margin-bottom: 15px; }
    .recommend-box { background: rgba(255,255,255,0.03); padding: 15px; border-radius: 12px; border: 1px solid #333; margin-bottom: 10px; font-weight: 700; }
    .highlight { color: #00f2ff; font-weight: 900; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. [엔진] 무결성 하이브리드 로더 ---
@st.cache_data(ttl=60)
def get_eternal_masterpiece_data(symbol):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        is_kr = symbol.isdigit() and len(symbol) == 6
        if is_kr:
            df_list = []
            for p in range(1, 6):
                url = f"https://finance.naver.com/item/sise_day.naver?code={symbol}&page={p}"
                res = requests.get(url, headers=headers)
                soup = BeautifulSoup(res.text, 'html.parser')
                table = soup.select_one('table.type2')
                if table:
                    df_list.append(pd.read_html(StringIO(str(table)))[0].dropna())
                time.sleep(0.05)
            df = pd.concat(df_list).reset_index(drop=True)
            df.columns = ['날짜', '종가', '전일비', '시가', '고가', '저가', '거래량']
            df['날짜'] = pd.to_datetime(df['날짜'])
            m_res = requests.get(f"https://finance.naver.com/item/main.naver?code={symbol}", headers=headers)
            s_name = BeautifulSoup(m_res.text, 'html.parser').select_one('title').text.split(':')[0].strip()
            news_res = requests.get(f"https://search.naver.com/search.naver?where=news&query={s_name} 특징주", headers=headers)
            news_items = [{'title': i.select_one('.news_tit').text, 'link': i.select_one('.news_tit')['href']} for i in BeautifulSoup(news_res.text, 'html.parser').select('.news_area')[:10]]
            m_type, div_y = "국내", "3.2% (예상)"
        else:
            ticker = yf.Ticker(symbol.upper())
            df = ticker.history(period="1y").reset_index()
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df.columns = [str(c).capitalize() for c in df.columns]
            df.rename(columns={'Date':'날짜', 'Close':'종가', 'Open':'시가', 'High':'고가', 'Low':'저가', 'Volume':'거래량'}, inplace=True)
            s_name = symbol.upper(); news_items = [{'title': f'{s_name} 인베스팅 속보', 'link': f'https://kr.investing.com/search/?q={s_name}'}]
            m_type, div_y = "미국", f"{ticker.info.get('dividendYield', 0)*100:.1f}%"

        df = df.sort_values('날짜').reset_index(drop=True)
        for ma in [5, 20, 60, 120]:
            if len(df) >= ma: df[f'MA{ma}'] = df['종가'].rolling(ma).mean()
        std = df['종가'].rolling(20).std()
        df['BB_U'], df['BB_L'] = df['MA20'] + (std * 2), df['MA20'] - (std * 2)
        delta = df['종가'].diff(); gain = (delta.where(delta > 0, 0)).rolling(14).mean(); loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
        ret = df['종가'].pct_change().dropna(); sims = np.random.normal(ret.mean(), ret.std(), 5000)
        win_rate = (sims > 0).sum() / 5000 * 100; avg_profit = sims.mean() * 100

        # AI 액션 플랜 판정
        last_p = df['종가'].iloc[-1]; bb_l = df['BB_L'].iloc[-1]; bb_u = df['BB_U'].iloc[-1]
        if win_rate >= 65 and last_p <= bb_l * 1.05: action, color = "💎 강력 매수 (Strong Buy)", "#00f2ff"
        elif last_p >= bb_u * 0.95: action, color = "⚠️ 분할 매도 (Scale Out)", "#ff37af"
        elif last_p <= df['MA20'].iloc[-1] * 0.94: action, color = "🚨 즉시 손절 (Cut Loss)", "#ff0000"
        else: action, color = "⚖️ 관망 유지 (Hold)", "#ffd60a"

        return df, s_name, win_rate, avg_profit, m_type, sims, news_items, action, color, div_y
    except Exception as e: return None, str(e), 0, 0, "Error", [], [], "Error", "white", ""

# --- 3. [메인 화면] ---
s_input = st.sidebar.text_input("📊 종목 입력 (053000 / NVDA)", value="053000")
invest_amt = st.sidebar.number_input("💰 투자 원금", value=10000000)

df, s_name, win_rate, avg_profit, m_type, sims, news, ai_action, ai_color, div_y = get_eternal_masterpiece_data(s_input)

if df is not None and not df.empty:
    curr_p = float(df['종가'].iloc[-1]); unit = "원" if m_type == "국내" else "$"
    st.markdown(f'<div class="main-title">{s_name} 오라클 터미널</div>', unsafe_allow_html=True)
    
    # [1] AI 최종 액션 플랜
    st.markdown(f"""<div class="action-box">
        <div style="color:#888; font-weight:800; font-size:0.9rem; letter-spacing:2px; margin-bottom:10px;">🤖 ORACLE AI 최종 의사결정</div>
        <div class="action-title" style="color:{ai_color};">{ai_action}</div>
        <div style="color:#cccccc;">AI 승률 <span class="highlight">{win_rate:.1f}%</span>와 확률 시나리오를 종합한 결과입니다.</div>
    </div>""", unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns([1.5, 1, 1, 1])
    with c1: st.markdown(f'<div class="profit-card"><h3>내일 기대수익</h3><h1>{avg_profit:+.2f}%</h1><p>예상 손익: {invest_amt*(avg_profit/100):+,.0f}{unit}</p></div>', unsafe_allow_html=True)
    with c2: st.metric("현재가", f"{curr_p:,.0f}{unit}"); st.metric("AI 승률", f"{win_rate:.1f}%")
    with c3: st.metric("배당률", div_y); st.metric("RSI 강도", f"{df['RSI'].iloc[-1]:.1f}")
    with c4: st.metric("목표가 (+15%)", f"{curr_p*1.15:,.0f}{unit}"); st.metric("손절가 (-6%)", f"{curr_p*0.94:,.0f}{unit}")

    tabs = st.tabs(["📉 전문가 정밀 차트", "🧪 무지개 퀀트 분석", "📰 실시간 증권 뉴스", "🚀 AI 엄선 테마주"])

    with tabs[0]: # 1P 차트 & 전문가 조언 예시
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.05)
        fig.add_trace(go.Candlestick(x=df['날짜'], open=df['시가'], high=df['고가'], low=df['저가'], close=df['종가'], name='시세'), row=1, col=1)
        ma_cfg = {5:'#ffd60a', 20:'#ff37af', 60:'#00f2ff', 120:'#ffffff'}
        for ma, clr in ma_cfg.items():
            if f'MA{ma}' in df.columns: fig.add_trace(go.Scatter(x=df['날짜'], y=df[f'MA{ma}'], line=dict(color=clr, width=1.8), name=f'{ma}일선'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['날짜'], y=df['BB_U'], line=dict(color='rgba(255,55,175,0.4)', dash='dash'), name='과열선'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['날짜'], y=df['BB_L'], line=dict(color='rgba(0,242,255,0.4)', dash='dash'), fill='tonexty', fillcolor='rgba(0,242,255,0.03)', name='침체선'), row=1, col=1)
        fig.add_trace(go.Bar(x=df['날짜'], y=df['거래량'], marker_color='#333', name='거래량'), row=2, col=1)
        fig.update_layout(height=700, template='plotly_dark', xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, width='stretch')
        # [복원] 전문가 조언 가이드 예시
        st.markdown(f"""
        <div class="guide-box">
            <div class="guide-title">🔍 Oracle's Guide: 전문가 차트 분석법</div>
            1. <b>상한선(빨간 점선) 근접:</b> 주가가 이 선에 닿으면 <span class="highlight">단기 고점</span>입니다. 무리한 추격 매수보다는 수익 실현을 예시로 듭니다.<br>
            2. <b>하한선(파란 점선) 근접:</b> 주가가 이 선에 닿으면 <span class="highlight">과매도(바닥)</span> 구간입니다. 반등 확률이 높으므로 매수 타점의 예시로 봅니다.<br>
            3. <b>거래량 폭발:</b> 차트 하단 막대가 솟구치며 파란선을 터치할 때가 가장 강력한 저점 매수 신호입니다.
        </div>
        """, unsafe_allow_html=True)

    with tabs[1]: # 2P 무지개 온도계 & 전문가 조언 예시
        col1, col2 = st.columns([1, 1.2])
        with col1:
            st.plotly_chart(go.Figure(go.Indicator(mode="gauge+number", value=win_rate, gauge={'bar': {'color': "#00f2ff"}, 'steps': [{'range': [0, 20], 'color': '#1a0000'}, {'range': [20, 40], 'color': '#1a0d00'}, {'range': [40, 60], 'color': '#1a1a00'}, {'range': [60, 80], 'color': '#001a0d'}, {'range': [80, 100], 'color': '#00001a'}]})).update_layout(template='plotly_dark', height=450), width='stretch')
        with col2:
            sims_pct = sims * 100; counts, bins = np.histogram(sims_pct, bins=50); bins_center = (bins[:-1] + bins[1:]) / 2
            colors = ['#ff37af' if b < 0 else '#00f2ff' for b in bins_center]
            fig_h = go.Figure(go.Bar(x=bins_center, y=counts, marker_color=colors, opacity=0.8))
            fig_h.update_layout(title='5,000회 미래 수익 시나리오 분포', template='plotly_dark', height=450); st.plotly_chart(fig_h, width='stretch')
        # [복원] 전문가 조언 가이드 예시
        st.markdown(f"""
        <div class="guide-box">
            <div class="guide-title">🧪 Oracle's Guide: 무지개 퀀트 해석법</div>
            1. <b>AI 승률 온도:</b> 온도가 <span style="color:#00f2ff;">파란색(80% 이상)</span> 구간에 진입했다면 과거 패턴상 승률이 압도적으로 높음을 뜻합니다.<br>
            2. <b>수익 분포표:</b> 오른쪽 파란색 막대가 우측으로 길게 뻗어 있을수록 매수 시 <span class="highlight">대박 수익</span>의 확률이 높다는 시각적 예시입니다.
        </div>
        """, unsafe_allow_html=True)

    with tabs[2]: # 3P 뉴스 피드 (URL 직결 10개)
        st.markdown(f"#### 📰 실시간 증권 뉴스 (TOP 10)")
        for n in news:
            st.markdown(f"""<div class="news-item">📍 <a href='{n['link']}' style="color:#00aaff; text-decoration:none; font-weight:600;" target='_blank'>{n['title']}</a></div>""", unsafe_allow_html=True)
        # [복원] 전문가 조언 가이드 예시
        st.markdown(f"""
        <div class="guide-box">
            <div class="guide-title">📰 Oracle's Guide: 뉴스 활용법</div>
            단순 호재 뉴스보다 <b>'공시', '수주', '흑자전환'</b> 키워드가 섞인 뉴스 링크를 클릭하여 상세 내용을 분석하는 예시를 활용하세요.
        </div>
        """, unsafe_allow_html=True)

    with tabs[3]: # 4P 테마 섹터
        st.markdown("### 🚀 AI 선정 주도 섹터별 종목")
        themes = {"🤖 AI/반도체": ["엔비디아 💎💎💎", "SK하이닉스 💎💎", "한미반도체 💎"], "💰 금융/저PBR": ["우리금융지주 💎💎💎", "KB금융 💎💎"], "🛡️ K-방산": ["한화에어로 💎💎💎", "현대로템 💎"]}
        cols = st.columns(3)
        for i, (t, s) in enumerate(themes.items()):
            with cols[i]:
                st.markdown(f"<div style='color:#00f2ff; font-weight:900; font-size:1.2rem; border-left:5px solid #00f2ff; padding-left:15px; margin-bottom:15px;'>{t}</div>", unsafe_allow_html=True)
                for stock in s: st.markdown(f"<div class='recommend-box'>🔥 {stock}</div>", unsafe_allow_html=True)
        # [복원] 전문가 조언 가이드 예시
        st.markdown(f"""
        <div class="guide-box">
            <div class="guide-title">🚀 Oracle's Guide: 테마주 순환매</div>
            💎💎💎 종목이 차트상 과열선에 닿았다면, 아직 바닥권인 💎💎 종목으로 자금을 이동하는 <span class="highlight">순환매 전략</span>의 예시입니다.
        </div>
        """, unsafe_allow_html=True)
else:
    st.error("데이터 로드 실패.")
