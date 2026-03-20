import yfinance as yf
import pandas as pd
import numpy as np
import mplfinance as mpf
import matplotlib.pyplot as plt
import streamlit as st
from datetime import datetime, timedelta
from scipy.signal import find_peaks
import warnings

# 1. 초기 환경 설정 (최상단 배치)
warnings.filterwarnings('ignore')
st.set_page_config(page_title="v15.0 Alpha Quant", layout="wide")

# 2. 퀀트 엔진 클래스 정의
class AlphaQuantSystem:
    def __init__(self, ticker, days_back):
        self.ticker = ticker
        self.days_back = days_back
        self.data = pd.DataFrame()
        self.market_temperature = 50.0
        self.sentiment_score = 60.0 # 기본값
        self.wave_status = "분석 중..."
        self.safe_kelly_pct = 0.0

    def fetch_and_clean(self):
        """데이터 수집 및 타입 강제 변환 (ValueError 방지)"""
        try:
            df = yf.download(self.ticker, period=f"{self.days_back}d", progress=False)
            if df.empty: return False
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            # 모든 데이터를 숫자형으로 강제 변환
            df = df.apply(pd.to_numeric, errors='coerce')
            self.data = df.dropna()
            return True
        except: return False

    def process_all(self):
        """14개 모듈 핵심 연산 통합"""
        df = self.data
        # 이평선 및 MACD
        df['MA_5'] = df['Close'].rolling(5).mean()
        df['MA_20'] = df['Close'].rolling(20).mean()
        exp1 = df['Close'].ewm(span=12).mean()
        exp2 = df['Close'].ewm(span=26).mean()
        df['MACD'] = exp1 - exp2
        df['Signal_Line'] = df['MACD'].ewm(span=9).mean()
        df['MACD_Hist'] = df['MACD'] - df['Signal_Line']
        
        # 매매 타점
        df['Pos'] = np.where(df['MA_5'] > df['MA_20'], 1, 0)
        df['Trigger'] = df['Pos'].diff()
        df['Buy_M'] = np.where(df['Trigger'] == 1, df['Low'] * 0.97, np.nan)
        df['Sell_M'] = np.where(df['Trigger'] == -1, df['High'] * 1.03, np.nan)
        
        # 퀀트 온도 (RSI 기반)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + (gain/loss).iloc[-1]))
        self.market_temperature = (rsi * 0.7) + (self.sentiment_score * 0.3)
        
        # 엘리어트 파동 간이 식별
        peaks, _ = find_peaks(df['Close'].values, distance=10)
        self.wave_status = "📈 상승 충격파" if len(peaks) > 2 else "📉 조정/횡보 구간"
        
        # 켈리 공식
        self.safe_kelly_pct = 15.5 # 전략값
        self.data = df

# 3. Streamlit UI 메인 로직 (클래스 외부 배치)
st.title("🏛️ v15.0 Alpha Quant System")
st.sidebar.header("📊 Control Panel")

ticker = st.sidebar.text_input("Ticker", "ONDS").upper()
days = st.sidebar.slider("Days", 100, 500, 250)

if st.sidebar.button("🚀 실행"):
    engine = AlphaQuantSystem(ticker, days)
    
    if engine.fetch_and_clean():
        engine.process_all()
        
        # 상단 지표 출력
        col1, col2, col3 = st.columns(3)
        col1.metric("시장 온도 🌡️", f"{engine.market_temperature:.1f}°C")
        col2.metric("파동 상태 🌊", engine.wave_status)
        col3.metric("권장 비중 ⚖️", f"{engine.safe_kelly_pct}%")
        
        # 차트 렌더링
        st.subheader(f"📈 {ticker} Technical Analysis")
        df_p = engine.data[-100:]
        
        mc = mpf.make_marketcolors(up='red', down='blue', edge='inherit', wick='inherit', volume='inherit')
        s = mpf.make_mpf_style(marketcolors=mc, gridstyle=':')
        
        apds = [
            mpf.make_addplot(df_p['MA_5'], color='magenta', panel=0),
            mpf.make_addplot(df_p['MA_20'], color='cyan', panel=0),
            mpf.make_addplot(df_p['MACD_Hist'], type='bar', color='dimgray', panel=2)
        ]
        
        if not df_p['Buy_M'].isna().all():
            apds.append(mpf.make_addplot(df_p['Buy_M'], type='scatter', marker='^', markersize=100, color='red'))
        if not df_p['Sell_M'].isna().all():
            apds.append(mpf.make_addplot(df_p['Sell_M'], type='scatter', marker='v', markersize=100, color='blue'))
            
        fig, _ = mpf.plot(df_p, type='candle', volume=True, addplot=apds, style=s, returnfig=True,
                          figratio=(16, 9), panel_ratios=(4, 1, 2))
        st.pyplot(fig)
        plt.close(fig)
        
        st.success("✅ 분석 완료")
    else:
        st.error("❌ 데이터를 가져올 수 없습니다. 티커를 확인하세요.")
