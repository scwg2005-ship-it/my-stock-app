import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from scipy.signal import find_peaks
from scipy.stats import norm
import feedparser
import urllib.parse
import os

# ==============================================================================
# [요구사항 1] UI 설정 및 모바일 반응형 스타일
# ==============================================================================
st.set_page_config(layout="wide", page_title="퀀트 인피니티 v9.5", page_icon="💎")

def apply_mobile_optimized_style():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@100;400;700;900&family=JetBrains+Mono&display=swap');
        :root {
            --neon-blue: #00E5FF; --neon-green: #00FF99; --neon-red: #FF3366;
            --bg-deep: #030305; --bg-card: #0c0c0e;
        }
        html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; background-color: var(--bg-deep); color: #E0E0E0; }
        
        /* 모바일 탭 가독성 향상 */
        .stTabs [data-baseweb="tab-list"] { 
            gap: 10px; background-color: #0a0a0f; padding: 10px; border-radius: 15px; 
            display: flex; overflow-x: auto; 
        }
        .stTabs [data-baseweb="tab"] { font-size: 1rem; font-weight: 700; white-space: nowrap; }
        
        /* 리포트 카드 디자인 */
        .report-card { background: var(--bg-card); border-left: 8px solid var(--neon-blue); padding: 25px; border-radius: 15px; margin-bottom: 20px; }
        
        /* 메트릭 폰트 모바일 최적화 */
        div[data-testid="stMetricValue"] { font-size: 1.8rem !important; font-weight: 900 !important; color: var(--neon-green); }
        </style>
    """, unsafe_allow_html=True)

apply_mobile_optimized_style()

# ==============================================================================
# [요구사항 2, 5] 데이터 엔진 (분봉/일봉 및 스마트 검색)
# ==============================================================================
st.sidebar.title("💎 인피니티 마스터 v9.5")
user_input = st.sidebar.text_input("종목명 또는 티커", value="SK하이닉스")
t_frame = st.sidebar.selectbox("차트 주기", ["일봉", "60분봉", "15분봉", "5분봉"])
d_range = st.sidebar.select_slider("데이터 범위", options=["1개월", "3개월", "6개월", "1년", "2년"], value="1년")

@st.cache_data(ttl=86400)
def load_krx_db(): return fdr.StockListing('KRX')

def get_ticker_v95(query):
    query = query.strip().replace(" ", "").upper()
    if query.isdigit() and len(query) == 6: return query
    db = load_krx_db()
    match = db[db['Name'].str.upper() == query]
    if not match.empty: return match.iloc[0]['Code']
    mapping = {"비트코인":"BTC-USD", "테슬라":"TSLA", "엔비디아":"NVDA", "애플":"AAPL", "온다스":"ONDS"}
    return mapping.get(query, query)

target_ticker = get_ticker_v95(user_input)
if target_ticker.isdigit():
    krx = load_krx_db()
    m_type = krx[krx['Code']==target_ticker]['Market'].iloc[0]
    yf_ticker = f"{target_ticker}.KS" if m_type == "KOSPI" else f"{target_ticker}.KQ"
else: yf_ticker = target_ticker

# ==============================================================================
# [요구사항 3, 6, 7, 9, 11] 핵심 퀀트 엔진 (원시 수식 풀 버전 - 생략 없음)
# ==============================================================================
class UnabridgedEngineV95:
    def __init__(self, df):
        self.df = df.copy()
        if isinstance(self.df.columns, pd.MultiIndex): self.df.columns = self.df.columns.get_level_values(0)

    def calculate_all(self):
        # [3번] 원시 이동평균
        self.df['MA20'] = self.df['Close'].rolling(20).mean()
        self.df['MA120'] = self.df['Close'].rolling(120).mean()

        # [3번] RSI 수동 연산
        delta = self.df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        self.df['RSI'] = 100 - (100 / (1 + (gain/loss)))

        # [3번] MACD 수동 연산
        e12 = self.df['Close'].ewm(span=12, adjust=False).mean()
        e26 = self.df['Close'].ewm(span=26, adjust=False).mean()
        self.df['MACD_H'] = (e12 - e26) - (e12 - e26).ewm(span=9, adjust=False).mean()

        # [7번] 일목균형표 상세
        h9, l9 = self.df['High'].rolling(9).max(), self.df['Low'].rolling(9).min()
        h26, l26 = self.df['High'].rolling(26).max(), self.df['Low'].rolling(26).min()
        self.df['선행1'] = ((h9 + l9 + h26 + l26) / 4).shift(26)
        self.df['선행2'] = ((self.df['High'].rolling(52).max() + self.df['Low'].rolling(52).min()) / 2).shift(26)

        # [3번] 변동성 ATR
        tr = pd.concat([self.df['High']-self.df['Low'], abs(self.df['High']-self.df['Close'].shift()), abs(self.df['Low']-self.df['Close'].shift())], axis=1).max(axis=1)
        self.df['ATR'] = tr.rolling(14).mean()

        # [6번] 매물대 POC
        bins = pd.cut(self.df['Close'], bins=20)
        self.poc = self.df.groupby(bins, observed=False)['Volume'].sum().idxmax().mid

        # [11번] 캔들 패턴 (망치형)
        body = abs(self.df['Close'] - self.df['Open'])
        ls = self.df[['Open','Close']].min(axis=1) - self.df['Low']
        self.df['Hammer'] = (ls > body * 2.2)

        # [9번] AI 스코어링 (다중 필터)
        score = pd.Series(50.0, index=self.df.index)
        score += np.where(self.df['Close'] > self.df['MA120'], 15, -10)
        score += np.where(self.df['Close'] > self.df['MA20'], 10, -10)
        score += np.where(self.df['MACD_H'] > 0, 10, -5)
        score += np.where(self.df['Hammer'], 15, 0)
        self.df['AI_Score'] = score.clip(0, 100).fillna(50)

        # [10번] 변곡점 (엘리어트/피보나치)
        self.pks, _ = find_peaks(self.df['High'].values, distance=14, prominence=self.df['High'].std()*0.4)
        self.vls, _ = find_peaks(-self.df['Low'].values, distance=14, prominence=self.df['High'].std()*0.4)
        mx, mn = self.df['High'].max(), self.df['Low'].min()
        self.fib618 = mx - 0.618 * (mx - mn)

        return self.df

# ==============================================================================
# [요구사항 4, 8, 10] 백테스팅 및 화살표 가격 (생략 없음)
# ==============================================================================
def run_visual_backtest(df):
    df['Pos'] = 0
    df.loc[df['AI_Score'] >= 62, 'Pos'] = 1
    df.loc[df['AI_Score'] <= 42, 'Pos'] = 0
    df['Pos'] = df['Pos'].replace(0, np.nan).ffill().fillna(0)
    
    mkt_ret = df['Close'].pct_change()
    strat_ret = (df['Pos'].shift(1) * mkt_ret) - (df['Pos'].diff().abs() * 0.00035)
    df['Cum_Mkt'] = (1 + mkt_ret.fillna(0)).cumprod() * 100
    df['Cum_Strat'] = (1 + strat_ret.fillna(0)).cumprod() * 100
    
    # 화살표 및 가격 레이블 생성
    df['Buy_Sig'] = np.where((df['Pos'] == 1) & (df['Pos'].shift(1) == 0), df['Low'] * 0.97, np.nan)
    df['Sell_Sig'] = np.where((df['Pos'] == 0) & (df['Pos'].shift(1) == 1), df['High'] * 1.03, np.nan)
    df['Buy_Txt'] = np.where(~df['Buy_Sig'].isna(), df['Close'].apply(lambda x: f"{x:,.0f}"), "")
    df['Sell_Txt'] = np.where(~df['Sell_Sig'].isna(), df['Close'].apply(lambda x: f"{x:,.0f}"), "")
    
    return df

# ==============================================================================
# 메인 대시보드 및 시각화 (모바일 터치 최적화 적용)
# ==============================================================================
try:
    tf_map = {"일봉":"1d", "60분봉":"60m", "15분봉":"15m", "5분봉":"5m"}
    rg_map = {"1개월":"1mo", "3개월":"3mo", "6개월":"6mo", "1년":"1y", "2년":"2y"}
    raw = yf.download(yf_ticker, period="1mo" if "분" in t_frame else rg_map[d_range], interval=tf_map[t_frame], progress=False)
    
    if not raw.empty:
        df = UnabridgedEngineV95(raw).calculate_all()
        df = run_visual_backtest(df)
        
        # 10. 5,000회 시뮬레이션
        rets = df['Close'].pct_change().dropna()
        shocks = np.random.normal(rets.mean(), rets.std(), (252, 5000))
        paths = df['Close'].iloc[-1] * np.exp(np.cumsum(shocks, axis=0))

        st.markdown(f"## 💎 {user_input} 터미널 | v9.5")
        cp, score = df['Close'].iloc[-1], df['AI_Score'].iloc[-1]
        
        # 핵심 지표
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("현재가", f"{cp:,.0f}")
        c2.metric("AI 점수", f"{score:.0f}")
        c3.metric("최종 수익률", f"{df['Cum_Strat'].iloc[-1]-100:+.2f}%")
        c4.metric("매물대 POC", f"{df.poc:,.0f}")

        tabs = st.tabs(["📊 매매신호 차트", "🌡️ AI 온도계", "🔮 5,000회 예측", "⚡ 뉴스"])

        with tabs[0]:
            # [중요] 모바일 스크롤 간섭 해결을 위한 차트 설정
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])
            
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="캔들"), row=1, col=1)
            
            # 매수/매도 화살표 및 가격
            fig.add_trace(go.Scatter(x=df.index, y=df['Buy_Sig'], mode='markers+text', marker=dict(symbol='triangle-up', size=15, color='#00FF99'),
                                     text=df['Buy_Txt'], textposition="bottom center", name="매수"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['Sell_Sig'], mode='markers+text', marker=dict(symbol='triangle-down', size=15, color='#FF3366'),
                                     text=df['Sell_Txt'], textposition="top center", name="매도"), row=1, col=1)

            # 일목구름 & 피보나치
            fig.add_trace(go.Scatter(x=df.index, y=df['선행1'], line=dict(width=0), showlegend=False), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['선행2'], fill='tonexty', fillcolor='rgba(0, 255, 153, 0.05)', name="일목구름"), row=1, col=1)
            fig.add_hline(y=df.fib618, line=dict(color="orange", dash="dot"), annotation_text="피보 61.8%", row=1, col=1)

            # 하단 수익률 그래프
            fig.add_trace(go.Scatter(x=df.index, y=df['Cum_Strat'], line=dict(color='#00E5FF', width=3), name="AI수익"), row=2, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['Cum_Mkt'], line=dict(color='gray', width=1, dash='dot'), name="시장"), row=2, col=1)
            
            # [모바일 최적화 레이아웃 핵심]
            fig.update_layout(
                height=700, template="plotly_dark", xaxis_rangeslider_visible=False,
                dragmode=False, # 차트 내 드래그(줌)를 기본적으로 비활성화하여 페이지 스크롤 허용
                hovermode='x unified',
                margin=dict(l=10, r=10, t=30, b=10)
            )
            # 모바일에서 차트 터치 시 스크롤이 막히지 않도록 config 설정
            st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': False, 'displayModeBar': False})
            st.info("💡 모바일 팁: 차트 내부 드래그를 끄고 페이지 스크롤이 원활하도록 설정했습니다.")

        with tabs[1]:
            st.subheader("🌡️ AI 매수 매력도 온도계")
            g_clr = "#00FF99" if score >= 60 else "#FFCC00" if score >= 40 else "#FF3366"
            fig_g = go.Figure(go.Indicator(mode="gauge+number", value=score, gauge={'axis': {'range': [0, 100]}, 'bar': {'color': g_clr}}))
            fig_g.update_layout(height=350, template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_g, use_container_width=True, config={'displayModeBar': False})
            
            st.markdown(f"""
            <div class='report-card'>
                <h4>📝 실전 대응 전략</h4>
                <p>• <b>목표가</b>: {cp + df['ATR'].iloc[-1]*3:,.0f} 원</p>
                <p>• <b>손절가</b>: {cp - df['ATR'].iloc[-1]*2:,.0f} 원</p>
                <p>• <b>매물대</b>: {df.poc:,.0f} 원</p>
            </div>
            """, unsafe_allow_html=True)

        with tabs[2]:
            st.subheader("🔮 5,000회 확률 예측")
            fig_sim = go.Figure()
            for i in range(25): fig_sim.add_trace(go.Scatter(y=paths[:, i], mode='lines', opacity=0.15, showlegend=False))
            fig_sim.add_trace(go.Scatter(y=np.mean(paths, axis=1), mode='lines', line=dict(color='#00E5FF', width=3), name="평균"))
            fig_sim.update_layout(height=450, template="plotly_dark")
            st.plotly_chart(fig_sim, use_container_width=True, config={'scrollZoom': False})
            st.success(f"📈 1년 뒤 상승 확률: **{(paths[-1, :] > cp).sum() / 50.0:.1f}%**")

        with tabs[3]:
            kw = urllib.parse.quote(f"{user_input} 특징주")
            feed = feedparser.parse(f"https://news.google.com/rss/search?q={kw}&hl=ko&gl=KR&ceid=KR:ko")
            for e in feed.entries[:8]:
                st.markdown(f"• <a href='{e.link}' target='_blank' style='color:white;'>{e.title}</a>", unsafe_allow_html=True)

except Exception as e: st.error(f"오류 발생: {e}")
