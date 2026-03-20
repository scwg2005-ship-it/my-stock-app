import yfinance as yf
import pandas as pd
import numpy as np
import mplfinance as mpf
import matplotlib.pyplot as plt
import streamlit as st
from datetime import datetime, timedelta
from scipy.signal import find_peaks
import requests
from bs4 import BeautifulSoup
import warnings

warnings.filterwarnings('ignore')

class AlphaQuantSystem:
    def __init__(self, ticker="ONDS", days_back=250):
        # [핵심] 모든 인스턴스 변수를 미리 None이나 기본값으로 초기화 (AttributeError 방지)
        self.ticker = ticker
        self.days_back = days_back
        self.data = pd.DataFrame()
        self.market_temperature = 50.0
        self.sentiment_score = 50.0
        self.poc_price = 0.0
        self.wave_status = "데이터 분석 전"
        self.safe_kelly_pct = 0.0
        self.fibo_levels = {}
        
        self.end_date = datetime.now()
        self.start_date = self.end_date - timedelta(days=days_back)

    def fetch_market_data(self):
        try:
            df = yf.download(self.ticker, start=self.start_date, end=self.end_date, progress=False)
            if df.empty: return False
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
            self.data = df.dropna()
            return True
        except: return False

    def calc_technical_indicators(self):
        if self.data.empty: return
        df = self.data
        df['MA_5'] = df['Close'].rolling(window=5).mean()
        df['MA_20'] = df['Close'].rolling(window=20).mean()
        
        # MACD
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Histogram'] = df['MACD'] - df['Signal_Line']
        
        # Signal & Markers
        df['Signal'] = np.where(df['MA_5'] > df['MA_20'], 1, 0)
        df['Position'] = df['Signal'].diff()
        df['Buy_Marker'] = np.where(df['Position'] == 1, df['Low'] * 0.98, np.nan)
        df['Sell_Marker'] = np.where(df['Position'] == -1, df['High'] * 1.02, np.nan)
        self.data = df

    def calc_fibonacci_retracement(self):
        if self.data.empty: return
        max_p, min_p = self.data['High'].max(), self.data['Low'].min()
        diff = max_p - min_p
        self.fibo_levels = {"0.618": max_p - diff * 0.618, "0.5": max_p - diff * 0.5}

    def analyze_elliott_waves(self):
        if len(self.data) < 20: return
        prices = self.data['Close'].values
        peaks, _ = find_peaks(prices, distance=10)
        troughs, _ = find_peaks(-prices, distance=10)
        if len(peaks) > len(troughs): self.wave_status = "📈 상승 충격파 진행"
        else: self.wave_status = "📉 조정 A-B-C 구간"

    def fetch_live_news_sentiment(self):
        # Streamlit 서버 차단 방지를 위한 기본값 설정
        self.sentiment_score = 55.0 

    def calc_quant_thermometer(self):
        if self.data.empty: return
        # RSI 간이 계산
        delta = self.data['Close'].diff()
        up = delta.clip(lower=0).rolling(14).mean()
        down = -delta.clip(upper=0).rolling(14).mean()
        rsi = 100 - (100 / (1 + (up/down).iloc[-1]))
        self.market_temperature = (rsi * 0.6) + (self.sentiment_score * 0.4)

    def calc_volume_profile(self):
        if self.data.empty: return
        self.poc_price = self.data['Close'].mean() # 간이 POC

    def calc_kelly_criterion(self):
        self.safe_kelly_pct = 15.5 # 예시 전략 비중

    def render_professional_chart(self):
        """[완전 방어 모듈] 데이터가 없거나 부족해도 에러 없이 차트 출력"""
        if self.data.empty:
            st.error("차트를 그릴 데이터가 부족합니다.")
            return

        df_plot = self.data[-100:].copy()
        
        # 필수 컬럼 체크 및 보정
        cols = ['MA_5', 'MA_20', 'MACD', 'Signal_Line', 'MACD_Histogram', 'Buy_Marker', 'Sell_Marker']
        for c in cols:
            if c not in df_plot.columns: df_plot[c] = np.nan

        mc = mpf.make_marketcolors(up='red', down='blue', edge='inherit', wick='inherit', volume={'up': 'red', 'down': 'blue'})
        s = mpf.make_mpf_style(marketcolors=mc, gridstyle=':', y_on_right=False)

        apds = [
            mpf.make_addplot(df_plot['MA_5'], color='magenta', panel=0),
            mpf.make_addplot(df_plot['MA_20'], color='cyan', panel=0),
            mpf.make_addplot(df_plot['MACD_Histogram'], type='bar', color='dimgray', panel=2)
        ]

        if not df_plot['Buy_Marker'].isna().all():
            apds.append(mpf.make_addplot(df_plot['Buy_Marker'], type='scatter', marker='^', color='red', panel=0))
        
        fig, _ = mpf.plot(df_plot, type='candle', volume=True, addplot=apds, style=s, 
                          title=f"\n{self.ticker} V15.0 Analysis", returnfig=True,
                          figratio=(12, 7), panel_ratios=(4, 1, 1.5))
        st.pyplot(fig)
        plt.close(fig)

# ==========================================
# Streamlit UI
# ==========================================
st.set_page_config(layout="wide")
st.title("🏛️ v15.0 Alpha Quant System")

ticker = st.sidebar.text_input("Ticker", "ONDS")
if st.sidebar.button("Run Engine"):
    engine = AlphaQuantSystem(ticker=ticker)
    if engine.fetch_market_data():
        engine.calc_technical_indicators()
        engine.calc_fibonacci_retracement()
        engine.analyze_elliott_waves()
        engine.calc_quant_thermometer()
        engine.calc_volume_profile()
        engine.calc_kelly_criterion()
        
        # 차트 출력 (여기서 AttributeError 발생 확률 0%로 수렴)
        engine.render_professional_chart()
        
        # 리포트
        c1, c2, c3 = st.columns(3)
        c1.metric("Market Temp", f"{engine.market_temperature:.1f}°C")
        c2.metric("Wave Status", engine.wave_status)
        c3.metric("Kelly Bet", f"{engine.safe_kelly_pct}%")
    else:
        st.error("데이터 로드 실패")
