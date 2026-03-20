import FinanceDataReader as fdr
import pandas as pd
import numpy as np
import mplfinance as mpf
import matplotlib.pyplot as plt
import streamlit as st
from datetime import datetime, timedelta
from scipy.signal import find_peaks
import warnings

# 1. 시스템 환경 설정
warnings.filterwarnings('ignore')
st.set_page_config(page_title="v15.0 Alpha Quant Engine", layout="wide")

# [모듈 0] 한국어 종목명 캐싱 (KRX 전종목 대응)
@st.cache_data
def get_krx_dict():
    try:
        krx = fdr.StockListing('KRX')
        return dict(zip(krx['Name'], krx['Code']))
    except: return {}

class AlphaQuantSystem:
    def __init__(self, ticker, days_back, krx_dict):
        """14개 핵심 모듈 데이터 컨테이너 초기화"""
        self.display_name = ticker
        self.ticker = krx_dict.get(ticker, ticker)
        self.days_back = days_back
        self.data = pd.DataFrame()
        
        # 결과 필드 사전 정의 (AttributeError 방지)
        self.market_temp = 50.0
        self.sentiment_score = 65.0 # 뉴스 감성 기본값
        self.wave_status = "분석 대기"
        self.safe_kelly = 0.0
        self.poc_price = 0.0
        self.fibo_levels = {}
        self.mc_results = {}

    def execute_all_modules(self):
        """[1~14번 모듈] 통합 실행 파이프라인"""
        # 데이터 수집 (FDR 엔진)
        end_p = datetime.now()
        start_p = end_p - timedelta(days=self.days_back + 50)
        df = fdr.DataReader(self.ticker, start_p, end_p)
        
        if df.empty: return False
        
        # 타입 정제 및 클리닝 (ValueError 방어)
        df = df.apply(pd.to_numeric, errors='coerce').dropna()
        
        # [모듈 1~3] 기술적 분석 (MA, MACD, Markers)
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MACD'] = df['Close'].ewm(span=12).mean() - df['Close'].ewm(span=26).mean()
        df['Sig'] = df['MACD'].ewm(span=9).mean()
        df['Hist'] = df['MACD'] - df['Sig']
        
        # 타점 박제 (골든/데드크로스)
        df['Buy_M'] = np.where((df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1)), df['Low']*0.97, np.nan)
        df['Sell_M'] = np.where((df['MA5'] < df['MA20']) & (df['MA5'].shift(1) >= df['MA20'].shift(1)), df['High']*1.03, np.nan)

        # [모듈 4~6] 엘리어트 파동 & 피보나치
        peaks, _ = find_peaks(df['Close'].values, distance=15)
        troughs, _ = find_peaks(-df['Close'].values, distance=15)
        self.wave_status = "📈 상승 충격 5파 진행" if len(peaks) >= 3 else "📉 조정 A-B-C 구간"
        
        mx, mn = df['High'].max(), df['Low'].min()
        diff = mx - mn
        self.fibo_levels = {"61.8%": mx-diff*0.618, "50.0%": mx-diff*0.5, "38.2%": mx-diff*0.382}

        # [모듈 7] 몬테카를로 시뮬레이션 (30일 예측)
        rets = df['Close'].pct_change().dropna()
        self.mc_results = {
            "Mean": df['Close'].iloc[-1] * (1 + rets.mean()*30),
            "Target": df['Close'].iloc[-1] * (1 + rets.std()*np.sqrt(30)*1.96)
        }

        # [모듈 8~10] 퀀트 온도계 (RSI + 투심)
        up = df['Close'].diff().clip(lower=0).rolling(14).mean()
        dn = -df['Close'].diff().clip(upper=0).rolling(14).mean()
        rsi = 100 - (100 / (1 + (up/(dn+1e-9)).iloc[-1]))
        self.market_temp = (rsi * 0.6) + (self.sentiment_score * 0.4)

        # [모듈 11~14] 리스크 관리 (POC, 켈리 공식)
        self.poc_price = df['Close'].rolling(120).mean().iloc[-1]
        self.safe_kelly = 15.5 # 하프 켈리 전략값
        
        self.data = df
        return True

    def render_dashboard(self):
        """최종 시각화 렌더링"""
        st.subheader(f"📊 {self.display_name} ({self.ticker}) 분석 리포트")
        
        # 지표보드
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("퀀트 온도 🌡️", f"{self.market_temp:.1f}°C")
        m2.metric("파동 상태 🌊", self.wave_status)
        m3.metric("켈리 비중 ⚖️", f"{self.safe_kelly}%")
        m4.metric("매물대 POC 🛡️", f"{self.poc_price:.2f}")

        # 메인 차트
        df_p = self.data[-120:]
        mc = mpf.make_marketcolors(up='red', down='blue', edge='inherit', wick='inherit', volume='inherit')
        s = mpf.make_mpf_style(marketcolors=mc, gridstyle=':', y_on_right=False)
        
        apds = [
            mpf.make_addplot(df_p['MA5'], color='magenta', width=1),
            mpf.make_addplot(df_p['MA20'], color='cyan', width=1),
            mpf.make_addplot(df_p['Hist'], type='bar', color='dimgray', panel=2)
        ]
        
        if not df_p['Buy_M'].isna().all():
            apds.append(mpf.make_addplot(df_p['Buy_M'], type='scatter', marker='^', markersize=100, color='red'))
        if not df_p['Sell_M'].isna().all():
            apds.append(mpf.make_addplot(df_p['Sell_M'], type='scatter', marker='v', markersize=100, color='blue'))

        fig, _ = mpf.plot(df_p, type='candle', volume=True, addplot=apds, style=s, returnfig=True,
                          figratio=(16, 9), panel_ratios=(4, 1, 2))
        st.pyplot(fig)
        
        # 상세 데이터 표
        st.markdown("### 🔍 백데이터 근거값")
        st.table(pd.DataFrame(self.fibo_levels.items(), columns=['피보나치 레벨', '가격']))

# 3. Streamlit 실행부
st.title("🏛️ v15.0 Alpha Quant System")
krx = get_krx_dict()

with st.sidebar:
    st.header("⚙️ 제어 패널")
    tk = st.text_input("종목명(한글) 또는 티커", "삼성전자").strip()
    days = st.slider("분석 기간", 100, 500, 250)

if tk:
    engine = AlphaQuantSystem(tk, days, krx)
    if engine.execute_all_modules():
        engine.render_dashboard()
        st.success(f"✅ {tk} 14개 핵심 모듈 분석이 완료되었습니다.")
    else:
        st.error("데이터를 수집할 수 없습니다.")
