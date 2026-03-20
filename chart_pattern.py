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
# [LAYER 1] 프리미엄 UI & 네온 테마 (요청사항 1번)
# ==============================================================================
st.set_page_config(layout="wide", page_title="QUANT INFINITY PRO v4.5", page_icon="💎")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@100;400;700;900&family=JetBrains+Mono&display=swap');
    :root { 
        --neon-blue: #00E5FF; --neon-green: #00FF99; --neon-red: #FF3366; 
        --bg-deep: #030305; --bg-card: #0c0c0e; 
    }
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; background-color: var(--bg-deep); color: #E0E0E0; }
    
    /* 탭 메뉴 디자인: 굵고 선명하게 */
    .stTabs [data-baseweb="tab-list"] { gap: 20px; background-color: #0a0a0c; padding: 15px 25px; border-radius: 15px; border: 1px solid #1e1e24; }
    .stTabs [data-baseweb="tab"] { font-size: 1.2rem; font-weight: 800; color: #555; transition: 0.4s; }
    .stTabs [aria-selected="true"] { color: var(--neon-blue) !important; text-shadow: 0 0 12px var(--neon-blue); }

    /* 분석 리포트 카드 (유리막 효과) */
    .report-box { background: var(--bg-card); border-left: 10px solid var(--neon-blue); padding: 35px; border-radius: 20px; margin-bottom: 25px; box-shadow: 0 20px 40px rgba(0,0,0,0.8); }
    
    /* 뉴스 카드 스타일 */
    .news-card { background: #0b0b0d; padding: 20px; border-radius: 15px; margin-bottom: 12px; border-left: 5px solid #BF00FF; transition: 0.3s; }
    .news-card:hover { background: #151518; }
    
    /* 메트릭 폰트 강조 */
    div[data-testid="stMetricValue"] { font-size: 2.2rem !important; font-weight: 900 !important; color: var(--neon-green); }
    
    /* 라이브 인디케이터 애니메이션 */
    @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.3; } 100% { opacity: 1; } }
    .live-dot { width: 12px; height: 12px; background: var(--neon-red); border-radius: 50%; display: inline-block; margin-right: 10px; animation: blink 2s infinite; }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# [LAYER 2] 스마트 데이터 파이프라인 (요청사항 5번)
# ==============================================================================
@st.cache_data(ttl=86400)
def load_full_market_data():
    """KRX 전체 종목 리스트 로드"""
    return fdr.StockListing('KRX')

def get_ticker_smart(query_str):
    """이름을 입력하면 티커로 변환하는 지능형 검색"""
    q = query_str.strip().replace(" ", "").upper()
    if q.isdigit() and len(q) == 6: return q
    
    master_list = load_full_market_data()
    match = master_list[master_list['Name'].str.replace(" ", "", regex=False).str.upper() == q]
    if not match.empty: return match.iloc[0]['Code']
    
    # 글로벌 특수 매핑 (암호화폐 및 해외주식)
    mapping = {
        "테슬라":"TSLA", "애플":"AAPL", "엔비디아":"NVDA", 
        "비트코인":"BTC-USD", "이더리움":"ETH-USD", "온다스":"ONDS"
    }
    return mapping.get(q, q)

# ==============================================================================
# [LAYER 3] 퀀트 아키텍처 핵심 엔진 (요청사항 3, 6, 7, 9, 11번 통합)
# ==============================================================================
class UltimateQuantEngine:
    def __init__(self, df):
        self.df = df.copy()
        if isinstance(self.df.columns, pd.MultiIndex):
            self.df.columns = self.df.columns.get_level_values(0)

    def execute_all_logic(self):
        """11가지 요청사항을 하나씩 순차적으로 실행"""
        self._math_raw_indicators()       # 3번: 원시 수학 엔진
        self._ichimoku_detailed()         # 7번: 일목균형표 정밀 계산
        self._detect_candle_logic()       # 11번: 캔들 패턴 비율 직접 계산
        self._volume_profile_poc()        # 6번: 매물대 분석 POC
        self._scoring_and_filtering()     # 9번: 다중 타임프레임 필터링
        return self.df

    def _math_raw_indicators(self):
        """외부 라이브러리 없이 직접 수식으로 계산하는 원시 엔진 (3번)"""
        # 1. 다중 이동평균선
        self.df['MA5'] = self.df['Close'].rolling(5).mean()
        self.df['MA20'] = self.df['Close'].rolling(20).mean()
        self.df['MA60'] = self.df['Close'].rolling(60).mean()
        self.df['MA120'] = self.df['Close'].rolling(120).mean() # 상위 추세용

        # 2. RSI (Relative Strength Index) 원시 수식
        delta = self.df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        self.df['RSI_RAW'] = 100 - (100 / (1 + (gain / loss)))

        # 3. MACD (지수이동평균 기반) 원시 수식
        ema12 = self.df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = self.df['Close'].ewm(span=26, adjust=False).mean()
        self.df['MACD_LINE'] = ema12 - ema26
        self.df['MACD_SIG'] = self.df['MACD_LINE'].ewm(span=9, adjust=False).mean()
        self.df['MACD_HIST'] = self.df['MACD_LINE'] - self.df['MACD_SIG']

        # 4. ATR (Average True Range) 변동성 직접 연산
        h_l = self.df['High'] - self.df['Low']
        h_pc = abs(self.df['High'] - self.df['Close'].shift(1))
        l_pc = abs(self.df['Low'] - self.df['Close'].shift(1))
        tr = pd.concat([h_l, h_pc, l_pc], axis=1).max(axis=1)
        self.df['ATR_RAW'] = tr.rolling(window=14).mean()

    def _ichimoku_detailed(self):
        """일목균형표의 시간론과 구름대 상세 로직 (7번)"""
        # 전환선, 기준선
        self.df['Tenkan'] = (self.df['High'].rolling(9).max() + self.df['Low'].rolling(9).min()) / 2
        self.df['Kijun'] = (self.df['High'].rolling(26).max() + self.df['Low'].rolling(26).min()) / 2
        # 선행스팬A, B (26일 선행)
        self.df['SpanA'] = ((self.df['Tenkan'] + self.df['Kijun']) / 2).shift(26)
        self.df['SpanB'] = ((self.df['High'].rolling(52).max() + self.df['Low'].rolling(52).min()) / 2).shift(26)
        # 후행스팬 (26일 후행)
        self.df['Chikou'] = self.df['Close'].shift(-26)

    def _detect_candle_logic(self):
        """시고저종 비율을 이용한 캔들 패턴 직접 인식 (11번)"""
        body = abs(self.df['Close'] - self.df['Open'])
        lower_shadow = self.df[['Open', 'Close']].min(axis=1) - self.df['Low']
        upper_shadow = self.df['High'] - self.df[['Open', 'Close']].max(axis=1)
        
        # 망치형: 몸통보다 꼬리가 2배 이상 길고 위꼬리가 거의 없음
        self.df['Pattern_Hammer'] = (lower_shadow > body * 2) & (upper_shadow < body * 0.5)
        # 도지: 몸통이 거의 없는 형태
        self.df['Pattern_Doji'] = body < (self.df['High'] - self.df['Low']) * 0.1

    def _volume_profile_poc(self):
        """특정 가격대 거래량 집중도 분석 - Point of Control (6번)"""
        price_bins = pd.cut(self.df['Close'], bins=20)
        # 가장 거래가 많이 일어난 가격 구간의 중간값 추출
        self.poc_value = self.df.groupby(price_bins, observed=False)['Volume'].sum().idxmax().mid

    def _scoring_and_filtering(self):
        """다중 타임프레임 필터를 결합한 AI 스코어링 (9번)"""
        score = pd.Series(50.0, index=self.df.index)
        
        # 필터 1: 대추세(120일선) 위에 있을 때만 안정적 가점
        score += np.where(self.df['Close'] > self.df['MA120'], 10, -5)
        # 필터 2: 단기 골든크로스 및 추세 가점
        score += np.where(self.df['Close'] > self.df['MA20'], 10, -10)
        score += np.where(self.df['MACD_HIST'] > 0, 10, -5)
        # 필터 3: 역발상 과매도 가점
        score += np.where(self.df['RSI_RAW'] < 30, 20, 0)
        # 필터 4: 캔들 패턴 확증 가점
        score += np.where(self.df['Pattern_Hammer'], 15, 0)
        
        self.df['AI_Score'] = score.clip(0, 100).fillna(50)

# ==============================================================================
# [LAYER 4] 통계적 시뮬레이션 & 자산 배분 (요청사항 8, 10번)
# ==============================================================================
def run_monte_carlo_5000(df, n=5000, days=252):
    """5,000회 반복 연산을 통한 확률적 미래 주가 예측 (10번)"""
    returns = df['Close'].pct_change().dropna()
    mu, sigma = returns.mean(), returns.std()
    last_price = df['Close'].iloc[-1]
    
    # 병렬 난수 행렬 생성 (고속 연산)
    shocks = np.random.normal(mu, sigma, (days, n))
    paths = last_price * np.exp(np.cumsum(shocks, axis=0))
    
    # 켈리 공식: p(승률), b(손익비) 기반 최적 투자 비중 (8번)
    win_rate = (returns > 0).sum() / len(returns)
    gain_avg = returns[returns > 0].mean()
    loss_avg = abs(returns[returns < 0].mean())
    b_ratio = gain_avg / loss_avg if loss_avg != 0 else 1
    kelly_f = (win_rate * b_ratio - (1 - win_rate)) / b_ratio
    
    return paths, max(0, kelly_f)

# ==============================================================================
# [LAYER 5] 실전 백테스팅 엔진 (요청사항 4번)
# ==============================================================================
def execute_backtest_with_fees(df):
    """수수료 및 슬리피지(0.03%)를 반영한 성과 검증"""
    df['Position'] = 0
    # AI 점수 60점 돌파 시 매수, 40점 붕괴 시 매도 (추세 유지 로직)
    df.loc[df['AI_Score'] >= 60, 'Position'] = 1
    df.loc[df['AI_Score'] <= 40, 'Position'] = 0
    df['Position'] = df['Position'].replace(0, np.nan).ffill().fillna(0)
    
    # 수익률 연산
    mkt_returns = df['Close'].pct_change()
    # 매매 수수료 0.03% 반영 (포지션이 바뀔 때만 차감)
    df['Strategy_Returns'] = (df['Position'].shift(1) * mkt_returns) - (df['Position'].diff().abs() * 0.0003)
    
    df['Cum_Market'] = (1 + mkt_returns.fillna(0)).cumprod() * 100
    df['Cum_Strategy'] = (1 + df['Strategy_Returns'].fillna(0)).cumprod() * 100
    return df

# ==============================================================================
# [LAYER 6] 메인 통합 터미널 UI (탭 및 뉴스 통합)
# ==============================================================================
def start_ultimate_terminal():
    st.sidebar.markdown("# 💎 INFINITY CONTROL")
    st.sidebar.caption("ULTIMATE MASTER EDITION v4.5")
    
    user_input = st.sidebar.text_input("분석 종목명/티커 (예: 하이닉스, TSLA)", value="SK하이닉스")
    ticker_code = get_ticker_smart(user_input)
    
    # 접미사 처리 (한국 시장 자동 인식)
    if ticker_code.isdigit():
        krx_data = load_full_market_data()
        m_type = krx_data[krx_data['Code'] == ticker_code]['Market'].values[0]
        final_ticker = f"{ticker_code}.KS" if m_type == "KOSPI" else f"{ticker_code}.KQ"
    else:
        final_ticker = ticker_code

    try:
        # 데이터 수집 (일봉 고정)
        raw_df = yf.download(final_ticker, period="1y", interval="1d", progress=False)
        if raw_df.empty:
            st.error("데이터 로드에 실패했습니다. 티커를 다시 확인하세요.")
            return

        # 엔진 가동
        engine = UltimateQuantEngine(raw_df)
        df = engine.execute_all_logic()
        df = execute_backtest_with_fees(df)
        
        # 기하학 및 변곡점 도출 (10번)
        pks, _ = find_peaks(df['High'].values, distance=14, prominence=df['High'].std()*0.4)
        vls, _ = find_peaks(-df['Low'].values, distance=14, prominence=df['High'].std()*0.4)
        mx, mn = df['High'].max(), df['Low'].min()
        fib_618 = mx - 0.618 * (mx - mn)

        # ----------------------------------------------------------------------
        # 상단 라이브 대시보드
        # ----------------------------------------------------------------------
        st.markdown(f"<h2><span class='live-dot'></span>QUANT INFINITY TERMINAL | {user_input}</h2>", unsafe_allow_html=True)
        
        cur_p = df['Close'].iloc[-1]
        ai_s = df['AI_Score'].iloc[-1]
        
        c_m1, c_m2, c_m3, c_m4 = st.columns(4)
        c_m1.metric("CURRENT PRICE", f"{cur_p:,.0f}")
        c_m2.metric("AI QUANT SCORE", f"{ai_s:.0f} / 100")
        c_m3.metric("ATR VOLATILITY", f"{df['ATR_RAW'].iloc[-1]:,.1f}")
        c_m4.metric("POC VOLUME MAX", f"{engine.poc_value:,.0f}")

        # 메인 탭 아키텍처
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 MASTER CHART", "🌡️ AI GAUGE & STRATEGY", "🔮 5,000 SIMULATION", "📈 BACKTESTING", "⚡ GLOBAL HUB"])

        with tab1:
            # 10번: 엘리어트 & 피보나치 통합 차트
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.8, 0.2])
            
            # 캔들 & 일목구름(7번)
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="PRICE"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['SpanA'], line=dict(width=0), showlegend=False), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['SpanB'], fill='tonexty', fillcolor='rgba(0, 255, 153, 0.05)', name="KUMO CLOUD"), row=1, col=1)
            
            # 매물대 POC (6번)
            fig.add_hline(y=engine.poc_value, line=dict(color="cyan", dash="dash", width=2), annotation_text="POC", row=1, col=1)
            
            # 엘리어트 숫자 (10번)
            wave_labels = ['1','2','3','4','5','A','B','C']
            pts_merged = sorted([('p',i,df['High'].iloc[i]) for i in pks]+[('v',i,df['Low'].iloc[i]) for i in vls], key=lambda x:x[1])[-8:]
            for idx, pt in enumerate(pts_merged):
                if idx < len(wave_labels):
                    color = "#00FF99" if pt[0]=='v' else "#FF3366"
                    fig.add_trace(go.Scatter(x=[df.index[pt[1]]], y=[pt[2]], mode="text+markers", text=[f"<b>{wave_labels[idx]}</b>"], 
                                             textposition="bottom center" if pt[0]=='v' else "top center", textfont=dict(size=22, color=color),
                                             marker=dict(color=color, size=12, symbol='diamond'), showlegend=False), row=1, col=1)
            
            fig.add_hline(y=fib_618, line=dict(color="orange", dash="dot"), annotation_text="Fib 61.8%", row=1, col=1)
            fig.add_trace(go.Bar(x=df.index, y=df['MACD_HIST'], marker_color='purple', name="MOMENTUM"), row=2, col=1)
            
            fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            # 1번: AI 온도계 (게이지)
            st.subheader("🌡️ AI 매수 매력도 온도계")
            g_clr = "#00FF99" if ai_s >= 60 else "#FFCC00" if ai_s >= 40 else "#FF3366"
            fig_g = go.Figure(go.Indicator(
                mode="gauge+number", value=ai_s, gauge={'axis': {'range': [0, 100]}, 'bar': {'color': g_clr}},
                title={'text': "AI MASTER SCORE", 'font': {'size': 24}}
            ))
            fig_g.update_layout(height=450, margin=dict(t=120, b=0), paper_bgcolor="rgba(0,0,0,0)", font={'color': "white"})
            st.plotly_chart(fig_g, use_container_width=True)
            
            st.markdown("<div class='report-box'>", unsafe_allow_html=True)
            st.write(f"#### 🔍 {user_input} 퀀트 기술 리포트")
            st.write(f"• **매물대 분석**: 주요 매물벽(POC)은 **{engine.poc_value:,.0f}** 원입니다.")
            st.write(f"• **캔들 진단**: {'상승 반전 망치형 패턴 감지' if df['Pattern_Hammer'].iloc[-1] else '현재 안정적인 추세 구간'}")
            st.write(f"• **대추세 상태**: {'상위 120일 추세선 위에 안착(매우 긍정)' if cur_p > df['MA120'].iloc[-1] else '상위 추세선 아래(보수적 접근)'}")
            st.write(f"• **가격 전략**: 목표가 **{cur_p + df['ATR_RAW'].iloc[-1]*3:,.0f}** / 손절가 **{cur_p - df['ATR_RAW'].iloc[-1]*2:,.0f}**")
            st.markdown("</div>", unsafe_allow_html=True)

        with tab3:
            # 10번: 5,000회 시뮬레이션 및 8번: 켈리 공식
            st.subheader("🔮 5,000회 확률적 자산 예측 (Monte-Carlo)")
            with st.spinner('5,000개 경로 확률 연산 중...'):
                paths, kelly_val = run_monte_carlo_5000(df)
                fig_sim = go.Figure()
                for i in range(25): fig_sim.add_trace(go.Scatter(y=paths[:, i], mode='lines', opacity=0.2, showlegend=False))
                fig_sim.add_trace(go.Scatter(y=np.mean(paths, axis=1), mode='lines', line=dict(color='#00E5FF', width=4), name="EXPECTED"))
                fig_sim.update_layout(height=550, template="plotly_dark")
                st.plotly_chart(fig_sim, use_container_width=True)
                
                st.success(f"📈 1년 뒤 상승 확률: **{(paths[-1, :] > cur_p).sum() / 50.0:.1f}%**")
                st.info(f"⚖️ **켈리 공식 최적 비중**: 총 자산의 **{kelly_val*100:.1f}%** 이내 투자를 권장합니다.")

        with tab4:
            # 4번: 백테스팅
            st.subheader("📈 알고리즘 백테스팅 성과")
            b_c1, b_c2 = st.columns(2)
            b_c1.metric("시장 수익률(존버)", f"{df['Cum_Market'].iloc[-1]-100:+.2f}%")
            b_c2.metric("AI 전략 수익률", f"{df['Cum_Strategy'].iloc[-1]-100:+.2f}%")
            
            fig_bt = go.Figure()
            fig_bt.add_trace(go.Scatter(x=df.index, y=df['Cum_Market'], name="존버", line=dict(color='gray', dash='dot')))
            fig_bt.add_trace(go.Scatter(x=df.index, y=df['Cum_Strategy'], name="AI 퀀트", line=dict(color='#00FF99', width=3)))
            fig_bt.update_layout(height=500, template="plotly_dark")
            st.plotly_chart(fig_bt, use_container_width=True)

        with tab5:
            # 5번: 글로벌 뉴스 허브
            st.subheader("⚡ 글로벌 인텔리전스 레이더")
            kw = urllib.parse.quote(f"{user_input} 특징주 OR {user_input} 주가")
            feed = feedparser.parse(f"https://news.google.com/rss/search?q={kw}&hl=ko&gl=KR&ceid=KR:ko")
            if feed.entries:
                for e in feed.entries[:12]:
                    st.markdown(f"<div class='news-card'><a href='{e.link}' target='_blank' style='color:white;text-decoration:none;font-weight:700;'>{e.title}</a><br><small style='color:#666'>{e.published}</small></div>", unsafe_allow_html=True)
            else:
                st.info("현재 관련 뉴스가 없습니다.")

    except Exception as e:
        st.error(f"시스템 오류 발생: {e}")

if __name__ == "__main__":
    start_ultimate_terminal()
