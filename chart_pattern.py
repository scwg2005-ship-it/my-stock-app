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

# ==========================================
# [LAYER 1] 프리미엄 UI & 네온 스타일 (1번)
# ==========================================
st.set_page_config(layout="wide", page_title="QUANT INFINITY v4.0", page_icon="💎")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@100;400;700;900&family=JetBrains+Mono&display=swap');
    :root { --neon-blue: #00E5FF; --neon-green: #00FF99; --neon-red: #FF3366; --bg-card: #0c0c0e; }
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; background-color: #030305; color: #E0E0E0; }
    .report-box { background: var(--bg-card); border-left: 10px solid var(--neon-blue); padding: 25px; border-radius: 20px; margin-bottom: 20px; box-shadow: 0 15px 35px rgba(0,0,0,0.7); }
    .news-card { background: #0b0b0d; padding: 20px; border-radius: 12px; margin-bottom: 12px; border-left: 4px solid #BF00FF; }
    div[data-testid="stMetricValue"] { font-size: 2rem !important; font-weight: 900 !important; color: var(--neon-green); }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# [LAYER 2-11] 핵심 퀀트 인피니티 엔진
# ==========================================
class UltimateQuantEngine:
    def __init__(self, df, symbol):
        self.df = df.copy()
        self.symbol = symbol
        if isinstance(self.df.columns, pd.MultiIndex): self.df.columns = self.df.columns.get_level_values(0)

    def run_all_layers(self):
        self._layer_3_raw_indicators()     # 3번: 원시 수학 엔진
        self._layer_7_ichimoku()          # 7번: 일목균형표 상세
        self._layer_11_candle_patterns()  # 11번: 캔들 패턴 직접 계산
        self._layer_4_backtest()          # 4번: 백테스팅
        self._layer_6_volume_profile()    # 6번: 매물대 POC
        self._layer_10_geometry()         # 10번: 피보나치 & 엘리어트
        self._scoring_system()            # AI 스코어링 결합
        return self.df

    def _layer_3_raw_indicators(self):
        """라이브러리 없이 직접 계산하는 원시 지표"""
        # 이평선
        self.df['MA20'] = self.df['Close'].rolling(20).mean()
        self.df['MA60'] = self.df['Close'].rolling(60).mean()
        self.df['MA120'] = self.df['Close'].rolling(120).mean()
        # RSI
        diff = self.df['Close'].diff()
        u, d = diff.copy(), diff.copy()
        u[u < 0], d[d > 0] = 0, 0
        self.df['RSI'] = 100 - (100 / (1 + (u.rolling(14).mean() / d.abs().rolling(14).mean())))
        # MACD
        e12, e26 = self.df['Close'].ewm(span=12).mean(), self.df['Close'].ewm(span=26).mean()
        self.df['MACD_H'] = (e12 - e26) - (e12 - e26).ewm(span=9).mean()
        # ATR
        tr = pd.concat([self.df['High']-self.df['Low'], abs(self.df['High']-self.df['Close'].shift()), abs(self.df['Low']-self.df['Close'].shift())], axis=1).max(axis=1)
        self.df['ATR'] = tr.rolling(14).mean()

    def _layer_7_ichimoku(self):
        """일목균형표 5대 지표 및 후행스팬"""
        h9, l9 = self.df['High'].rolling(9).max(), self.df['Low'].rolling(9).min()
        h26, l26 = self.df['High'].rolling(26).max(), self.df['Low'].rolling(26).min()
        self.df['Tenkan'] = (h9 + l9) / 2
        self.df['Kijun'] = (h26 + l26) / 2
        self.df['SpanA'] = ((self.df['Tenkan'] + self.df['Kijun']) / 2).shift(26)
        self.df['SpanB'] = ((self.df['High'].rolling(52).max() + self.df['Low'].rolling(52).min()) / 2).shift(26)
        self.df['Chikou'] = self.df['Close'].shift(-26) # 후행스팬

    def _layer_11_candle_patterns(self):
        """캔들 시고저종 비율을 이용한 패턴 인식"""
        body = abs(self.df['Close'] - self.df['Open'])
        lower_s = self.df[['Open','Close']].min(axis=1) - self.df['Low']
        upper_s = self.df['High'] - self.df[['Open','Close']].max(axis=1)
        self.df['Hammer'] = (lower_s > body * 2) & (upper_s < body * 0.5)
        self.df['Doji'] = body < (self.df['High'] - self.df['Low']) * 0.1

    def _layer_6_volume_profile(self):
        """매물대 분석 및 POC 도출"""
        price_bins = pd.cut(self.df['Close'], bins=20)
        self.poc_price = self.df.groupby(price_bins, observed=False)['Volume'].sum().idxmax().mid

    def _layer_10_geometry(self):
        """피보나치 되돌림 및 엘리어트 변곡점"""
        mx, mn = self.df['High'].max(), self.df['Low'].min()
        diff = mx - mn
        self.fib = {'L618': mx - 0.618 * diff, 'L382': mx - 0.382 * diff}
        self.pks, _ = find_peaks(self.df['High'].values, distance=14, prominence=self.df['High'].std()*0.4)
        self.vls, _ = find_peaks(-self.df['Low'].values, distance=14, prominence=self.df['Low'].std()*0.4)

    def _scoring_system(self):
        """9번: 다중 타임프레임 필터 포함 스코어링"""
        score = pd.Series(50.0, index=self.df.index)
        score += np.where(self.df['Close'] > self.df['MA20'], 10, -10)
        score += np.where(self.df['Close'] > self.df['MA120'], 10, -5) # 대추세 필터
        score += np.where(self.df['MACD_H'] > 0, 10, -5)
        score += np.where(self.df['Hammer'], 15, 0)
        score += np.where(self.df['RSI'] < 30, 20, 0)
        self.df['Score'] = score.clip(0, 100)

    def _layer_4_backtest(self):
        """수수료 반영 백테스팅"""
        self.df['Signal'] = (self.df['Score'].shift(1) > 60).astype(int)
        ret = self.df['Close'].pct_change()
        self.df['Strat_Ret'] = (self.df['Signal'] * ret) - (self.df['Signal'].diff().abs() * 0.0003)
        self.df['Cum_Mkt'] = (1 + ret.fillna(0)).cumprod() * 100
        self.df['Cum_Strat'] = (1 + self.df['Strat_Ret'].fillna(0)).cumprod() * 100

# ==========================================
# [MODULE] 데이터 호출 및 검색 (5번)
# ==========================================
@st.cache_data(ttl=86400)
def load_master(): return fdr.StockListing('KRX')

def get_ticker(name):
    name = name.strip().replace(" ", "").upper()
    if name.isdigit() and len(name) == 6: return name
    master = load_master()
    match = master[master['Name'].str.upper() == name]
    return match.iloc[0]['Code'] if not match.empty else name

# ==========================================
# [MODULE] 5,000회 몬테카를로 & 켈리 공식 (8,10번)
# ==========================================
def run_simulation_pro(df):
    returns = df['Close'].pct_change().dropna()
    mu, sigma = returns.mean(), returns.std()
    # 5,000회 벡터화 연산 (최적화)
    shocks = np.random.normal(mu, sigma, (252, 5000))
    paths = df['Close'].iloc[-1] * np.exp(np.cumsum(shocks, axis=0))
    
    # 켈리 공식: f = (p*b - q) / b (p:승률, b:손익비)
    win_rate = (returns > 0).sum() / len(returns)
    profit_factor = returns[returns>0].mean() / abs(returns[returns<0].mean())
    kelly = (win_rate * profit_factor - (1 - win_rate)) / profit_factor
    return paths, max(0, kelly)

# ==========================================
# [MAIN] 시스템 실행
# ==========================================
st.sidebar.title("💎 INFINITY v4.0")
target = st.sidebar.text_input("종목명/티커", value="SK하이닉스")
code = get_ticker(target)

if code.isdigit():
    m_info = load_master()[load_master()['Code']==code]['Market'].iloc[0]
    ticker = f"{code}.KS" if m_info == "KOSPI" else f"{code}.KQ"
else: ticker = code

try:
    raw = yf.download(ticker, period="1y", interval="1d", progress=False)
    if not raw.empty:
        # 엔진 가동
        engine = UltimateQuantEngine(raw, target)
        df = engine.run_all_layers()
        cp, score = df['Close'].iloc[-1], df['Score'].iloc[-1]

        # UI 헤더
        st.markdown(f"<h2><span style='color:red'>●</span> QUANT TERMINAL | {target}</h2>", unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("현재가", f"{cp:,.0f}", f"{((cp/df['Close'].iloc[-2]-1)*100):+.2f}%")
        m2.metric("AI 점수", f"{score:.0f}")
        m3.metric("RSI(14)", f"{df['RSI'].iloc[-1]:.1f}")
        m4.metric("매물대(POC)", f"{engine.poc_price:,.0f}")

        tabs = st.tabs(["📊 마스터 차트", "🌡️ AI 온도계 & 전략", "🔮 5,000회 예측", "⚖️ 백테스팅", "⚡ 뉴스 허브"])

        with tabs[0]:
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.8, 0.2])
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="캔들"), row=1, col=1)
            # 일목 구름 & 매물대
            fig.add_trace(go.Scatter(x=df.index, y=df['SpanA'], line=dict(width=0), showlegend=False), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['SpanB'], fill='tonexty', fillcolor='rgba(0, 255, 153, 0.05)', name="구름대"), row=1, col=1)
            fig.add_hline(y=engine.poc_price, line=dict(color="cyan", dash="dash", width=2), annotation_text="POC", row=1, col=1)
            # 엘리어트 숫자
            lbls = ['1','2','3','4','5','A','B','C']
            merged = sorted([('p',i,df['High'].iloc[i]) for i in engine.pks]+[('v',i,df['Low'].iloc[i]) for i in engine.vls], key=lambda x:x[1])[-8:]
            for i, pt in enumerate(merged):
                if i < len(lbls):
                    clr = "#00FF99" if pt[0]=='v' else "#FF3366"
                    fig.add_trace(go.Scatter(x=[df.index[pt[1]]], y=[pt[2]], mode="text+markers", text=[f"<b>{lbls[i]}</b>"], 
                                             textposition="bottom center" if pt[0]=='v' else "top center", textfont=dict(size=22, color=clr),
                                             marker=dict(color=clr, size=14, symbol='diamond'), showlegend=False), row=1, col=1)
            fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

        with tabs[1]:
            # 1번: 온도계
            st.subheader("🌡️ AI 매수 매력도")
            g_clr = "#00FF99" if score >= 60 else "#FFCC00" if score >= 40 else "#FF3366"
            fig_g = go.Figure(go.Indicator(
                mode="gauge+number", value=score, gauge={'axis': {'range': [0, 100]}, 'bar': {'color': g_clr}},
                title={'text': "AI SCORE", 'font': {'size': 24}}
            ))
            fig_g.update_layout(height=400, margin=dict(t=100, b=0), paper_bgcolor="rgba(0,0,0,0)", font={'color': "white"})
            st.plotly_chart(fig_g, use_container_width=True)
            
            st.markdown("<div class='report-box'>", unsafe_allow_html=True)
            st.write(f"#### 🔍 {target} 전략 리포트")
            st.write(f"• **피보나치 61.8% 지지선**: {engine.fib['L618']:,.0f} 원")
            st.write(f"• **캔들 패턴 진단**: {'강력한 망치형 반등 포착' if df['Hammer'].iloc[-1] else '특이 패턴 없음'}")
            st.write(f"• **목표가 (ATR 3x)**: {cp + df['ATR'].iloc[-1]*3:,.0f} 원")
            st.markdown("</div>", unsafe_allow_html=True)

        with tabs[2]:
            st.subheader("🔮 5,000회 확률적 자산 예측")
            paths, kelly = run_simulation_pro(df)
            fig_sim = go.Figure()
            for i in range(25): fig_sim.add_trace(go.Scatter(y=paths[:, i], mode='lines', opacity=0.2, showlegend=False))
            fig_sim.add_trace(go.Scatter(y=np.mean(paths, axis=1), mode='lines', line=dict(color='#00E5FF', width=4), name="평균 경로"))
            fig_sim.update_layout(height=550, template="plotly_dark")
            st.plotly_chart(fig_sim, use_container_width=True)
            
            st.success(f"📈 1년 뒤 상승 확률: **{(paths[-1, :] > cp).sum() / 50.0:.1f}%**")
            st.info(f"⚖️ **켈리 공식 추천 비중**: 전체 자산의 **{kelly*100:.1f}%** 투자 권장")

        with tabs[3]:
            st.subheader("📉 알고리즘 백테스팅 성과")
            c1, c2 = st.columns(2)
            c1.metric("시장 수익률(존버)", f"{df['Cum_Mkt'].iloc[-1]-100:+.2f}%")
            c2.metric("AI 전략 수익률", f"{df['Cum_Strat'].iloc[-1]-100:+.2f}%")
            fig_bt = go.Figure()
            fig_bt.add_trace(go.Scatter(x=df.index, y=df['Cum_Mkt'], name="MARKET", line=dict(color='gray', dash='dot')))
            fig_bt.add_trace(go.Scatter(x=df.index, y=df['Cum_Strat'], name="AI QUANT", line=dict(color='#00FF99', width=3)))
            fig_bt.update_layout(height=500, template="plotly_dark")
            st.plotly_chart(fig_bt, use_container_width=True)

        with tabs[4]:
            # 5번: 뉴스 허브
            st.subheader("⚡ 글로벌 인텔리전스")
            kw = urllib.parse.quote(f"{target} 특징주 OR {target} 주가")
            feed = feedparser.parse(f"https://news.google.com/rss/search?q={kw}&hl=ko&gl=KR&ceid=KR:ko")
            for e in feed.entries[:10]:
                st.markdown(f"<div class='news-card'><a href='{e.link}' target='_blank' style='color:white;text-decoration:none;font-weight:700;'>{e.title}</a></div>", unsafe_allow_html=True)

except Exception as e: st.error(f"시스템 중단: {e}")
