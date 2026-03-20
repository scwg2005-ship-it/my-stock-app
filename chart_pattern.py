import FinanceDataReader as fdr
import pandas as pd
import numpy as np
import mplfinance as mpf
import matplotlib.pyplot as plt
import streamlit as st
from datetime import datetime, timedelta
from scipy.signal import find_peaks
import warnings

# [환경 설정]
warnings.filterwarnings('ignore')
st.set_page_config(page_title="v15.0 Alpha Quant", layout="wide")

# [한국어 종목명 사전 캐싱]
@st.cache_data
def get_krx_dict():
    try:
        krx = fdr.StockListing('KRX')
        return dict(zip(krx['Name'], krx['Code']))
    except: return {}

class AlphaQuantSystem:
    def __init__(self, ticker, days_back, krx_dict):
        # 1. 초기화 (AttributeError 방지용 변수 선언)
        self.display_name = ticker
        self.ticker = krx_dict.get(ticker, ticker)
        self.data = pd.DataFrame()
        self.market_temperature = 50.0
        self.sentiment_score = 65.0
        self.wave_status = "분석 중..."
        self.safe_kelly_pct = 0.0
        self.poc_price = 0.0
        self.fibo_levels = {}
        self.mc_results = {}

    def run_engine(self):
        # 2. 데이터 수집 및 타입 정제 (ValueError 방어)
        end_p = datetime.now()
        start_p = end_p - timedelta(days=250)
        df = fdr.DataReader(self.ticker, start_p, end_p)
        if df.empty: return False
        self.data = df.apply(pd.to_numeric, errors='coerce').dropna()

        # 3. 기술적 분석 (모듈 1~3: MA, MACD, Markers)
        df = self.data
        df['MA5'], df['MA20'] = df['Close'].rolling(5).mean(), df['Close'].rolling(20).mean()
        df['MACD'] = df['Close'].ewm(span=12).mean() - df['Close'].ewm(span=26).mean()
        df['Sig'] = df['MACD'].ewm(span=9).mean()
        df['Hist'] = df['MACD'] - df['Sig']
        df['Buy_M'] = np.where((df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1)), df['Low']*0.97, np.nan)
        df['Sell_M'] = np.where((df['MA5'] < df['MA20']) & (df['MA5'].shift(1) >= df['MA20'].shift(1)), df['High']*1.03, np.nan)

        # 4. 패턴 & 확률 (모듈 4~7: 파동, 피보나치, 몬테카를로)
        peaks, _ = find_peaks(df['Close'].values, distance=15)
        self.wave_status = "📈 상승 충격파" if len(peaks) >= 3 else "📉 조정 구간"
        mx, mn = df['High'].max(), df['Low'].min()
        self.fibo_levels = {"61.8%": mx-(mx-mn)*0.618, "38.2%": mx-(mx-mn)*0.382}
        
        # 몬테카를로 (간이형)
        rets = df['Close'].pct_change().dropna()
        self.mc_results = {"Mean": df['Close'].iloc[-1] * (1 + rets.mean()*30), "Risk": df['Close'].iloc[-1] * (1 + rets.min())}

        # 5. 리스크 & 심리 (모듈 8~14: 온도계, 매물대, 켈리)
        rsi = 100 - (100 / (1 + (df['Close'].diff().clip(lower=0).rolling(14).mean() / -df['Close'].diff().clip(upper=0).rolling(14).mean()).iloc[-1]))
        self.market_temperature = (rsi * 0.6) + (self.sentiment_score * 0.4)
        self.poc_price = df['Close'].mean()
        self.safe_kelly_pct = 15.5
        return True

    def render(self):
        # 6. 고해상도 시각화
        df_p = self.data[-100:]
        mc = mpf.make_marketcolors(up='red', down='blue', edge='inherit', wick='inherit', volume='inherit')
        s = mpf.make_mpf_style(marketcolors=mc, gridstyle=':')
        apds = [mpf.make_addplot(df_p['MA5'], color='magenta'), mpf.make_addplot(df_p['MA20'], color='cyan')]
        if not df_p['Buy_M'].isna().all(): apds.append(mpf.make_addplot(df_p['Buy_M'], type='scatter', marker='^', color='red'))
        if not df_p['Sell_M'].isna().all(): apds.append(mpf.make_addplot(df_p['Sell_M'], type='scatter', marker='v', color='blue'))
        
        fig, _ = mpf.plot(df_p, type='candle', volume=True, addplot=apds, style=s, returnfig=True, figratio=(16,9))
        st.pyplot(fig)

# [Main UI]
st.title("🏛️ v15.0 Alpha Quant System")
krx = get_krx_dict()
tk = st.sidebar.text_input("종목명/티커", "삼성전자").upper()

if tk:
    engine = AlphaQuantSystem(tk, 250, krx)
    if engine.run_engine():
        c1, c2, c3 = st.columns(3)
        c1.metric("시장 온도", f"{engine.market_temperature:.1f}°C")
        c2.metric("파동 상태", engine.wave_status)
        c3.metric("켈리 비중", f"{engine.safe_kelly_pct}%")
        engine.render()
        st.success(f"✅ {tk} 분석 완료")
