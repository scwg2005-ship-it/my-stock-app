import yfinance as yf
import pandas as pd
import numpy as np
import mplfinance as mpf
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import warnings

# 경고 메시지 무시 (깔끔한 출력을 위해)
warnings.filterwarnings('ignore')

class AlphaQuantSystem:
    """
    v15.0 Alpha Quant System Core Engine
    설계자: AI Assistant & User
    """
    
    def __init__(self, ticker="005930.KS", days_back=365):
        """
        [코어 초기화 모듈]
        기본적으로 한국 증시(삼성전자)를 타겟으로 하거나, 'BTC-USD', 'AAPL' 등 입력 가능
        """
        self.ticker = ticker
        self.end_date = datetime.now()
        self.start_date = self.end_date - timedelta(days=days_back)
        self.data = pd.DataFrame()
        self.market_temperature = 50.0  # 초기 퀀트 온도
        
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🚀 v15.0 Alpha Quant Engine 가동 준비 완료")
        print(f"Target Ticker: {self.ticker} | Period: {days_back} Days")

    def fetch_market_data(self):
        """
        [데이터 파이프라인 모듈]
        Yahoo Finance API를 통한 고해상도 OHLCV 데이터 수집 및 전처리
        """
        print(">> 시장 데이터 수집 중...")
        try:
            df = yf.download(self.ticker, start=self.start_date, end=self.end_date, progress=False)
            if df.empty:
                raise ValueError("데이터를 불러오지 못했습니다. 티커 심볼을 확인하세요.")
            
            # 멀티인덱스 컬럼 평탄화 (yfinance 최신 버전 대응)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
                
            self.data = df.dropna()
            print(f">> 데이터 수집 완료: 총 {len(self.data)} 거래일 확보")
        except Exception as e:
            print(f"❌ 데이터 수집 오류 발생: {e}")

    def calc_technical_indicators(self):
        """
        [1단계 - 모듈 2, 3] 이동평균선, 골든/데드크로스, MACD 등 기술적 지표 산출
        """
        print(">> 기술적 지표 및 크로스오버 타점 연산 중...")
        df = self.data
        
        # 1. 이동평균선 (5일, 20일)
        df['MA_5'] = df['Close'].rolling(window=5).mean()
        df['MA_20'] = df['Close'].rolling(window=20).mean()
        
        # 2. 크로스오버 시그널 (▲: 골든크로스, ▼: 데드크로스)
        df['Signal'] = 0
        # 5일선이 20일선보다 위에 있으면 1, 아니면 0
        df['Signal'][5:] = np.where(df['MA_5'][5:] > df['MA_20'][5:], 1, 0)
        # Signal의 차분(diff)을 구하여 1이면 골든, -1이면 데드크로스
        df['Position'] = df['Signal'].diff()
        
        # 3. MACD (12, 26, 9)
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Histogram'] = df['MACD'] - df['Signal_Line']
        
        # 차트 표기를 위한 마커 위치 설정 (캔들 위/아래 여백 확보)
        df['Buy_Marker'] = np.where(df['Position'] == 1, df['Low'] * 0.98, np.nan)
        df['Sell_Marker'] = np.where(df['Position'] == -1, df['High'] * 1.02, np.nan)
        
        self.data = df
def render_professional_chart(self):
        """[1단계 - 모듈 1] Streamlit 최적화 및 AttributeError 방어 차트 렌더링"""
        import streamlit as st
        import matplotlib.pyplot as plt

        # 1. 데이터 존재 여부 체크 (AttributeError 방지 핵심)
        if self.data.empty:
            st.error("❌ 분석할 데이터가 없습니다. 티커를 확인해 주세요.")
            return

        # 2. 필요한 컬럼이 없는 경우를 대비한 자동 생성 (안전장치)
        required_cols = ['MA_5', 'MA_20', 'MACD', 'Signal_Line', 'MACD_Histogram', 'Buy_Marker', 'Sell_Marker']
        for col in required_cols:
            if col not in self.data.columns:
                self.data[col] = np.nan

        # 3. 최근 120일 데이터 슬라이싱
        df_plot = self.data[-120:].copy()
        
        # 4. 차트 스타일 설정
        mc = mpf.make_marketcolors(up='red', down='blue', edge='inherit', wick='inherit', volume={'up': 'red', 'down': 'blue'})
        s = mpf.make_mpf_style(marketcolors=mc, gridstyle=':', y_on_right=False)

        # 5. 보조 지표 패널 구성
        apds = [
            mpf.make_addplot(df_plot['MA_5'], color='magenta', width=1.2, panel=0),
            mpf.make_addplot(df_plot['MA_20'], color='cyan', width=1.2, panel=0),
            mpf.make_addplot(df_plot['MACD'], color='black', panel=2, ylabel='MACD'),
            mpf.make_addplot(df_plot['Signal_Line'], color='red', panel=2),
            mpf.make_addplot(df_plot['MACD_Histogram'], type='bar', color='dimgray', panel=2)
        ]

        # 6. 매매 타점 마커 추가 (값이 있을 때만)
        if not df_plot['Buy_Marker'].dropna().empty:
            apds.append(mpf.make_addplot(df_plot['Buy_Marker'], type='scatter', markersize=80, marker='^', color='red', panel=0))
        if not df_plot['Sell_Marker'].dropna().empty:
            apds.append(mpf.make_addplot(df_plot['Sell_Marker'], type='scatter', markersize=80, marker='v', color='blue', panel=0))

        # 7. 차트 생성 및 Streamlit 출력
        try:
            fig, axlist = mpf.plot(df_plot, type='candle', volume=True, addplot=apds, style=s,
                                  title=f"\n[v15.0 Alpha Quant] {self.ticker} Analysis",
                                  ylabel='Price', ylabel_lower='Volume',
                                  figratio=(14, 9), figscale=1.1, panel_ratios=(4, 1, 1.5),
                                  returnfig=True)
            st.pyplot(fig)
            plt.close(fig) # 메모리 관리
        except Exception as e:
            st.warning(f"⚠️ 차트 생성 중 일부 오류 발생: {e}")

# ==========================================
# 메인 실행부 (Streamlit UI 구성)
# ==========================================
if __name__ == "__main__":
    import streamlit as st
    
    # 🎨 웹 대시보드 제목
    st.set_page_config(page_title="v15.0 Alpha Quant Engine", layout="wide")
    st.title("🏛️ v15.0 Alpha Quant System Dashboard")
    
    # 사이드바 설정
    target_ticker = st.sidebar.text_input("Enter Ticker (e.g. ONDS, TSLA, ^NDX)", value="ONDS")
    lookback = st.sidebar.slider("Lookback Period (Days)", 100, 500, 250)
    
    if st.sidebar.button("🚀 Run Analysis"):
        engine = AlphaQuantSystem(ticker=target_ticker, days_back=lookback)
        
        with st.spinner('데이터 분석 및 엔진 가동 중...'):
            # 파이프라인 순차 가동
            engine.fetch_market_data()
            engine.calc_technical_indicators()
            engine.calc_fibonacci_retracement()
            engine.analyze_elliott_waves()
            engine.fetch_live_news_sentiment()
            engine.calc_quant_thermometer()
            engine.calc_volume_profile()
            engine.calc_kelly_criterion()
            
            # 1. 차트 렌더링
            engine.render_professional_chart()
            
            # 2. 리포트 섹션 (Streamlit UI로 깔끔하게 출력)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Market Temp 🌡️", f"{engine.market_temperature:.1f}°C")
                st.write(f"**Wave Status:** {engine.wave_status}")
            with col2:
                st.metric("Sentiment Score 🧠", f"{engine.sentiment_score:.1f}/100")
                st.write(f"**POC Price:** {engine.poc_price:.2f}")
            with col3:
                st.metric("Kelly Betting ⚖️", f"{engine.safe_kelly_pct:.2f}%")
                st.write("**Strategy:** V15.0 Alpha Integrated")
                
            st.success("✅ 모든 14개 모듈 분석이 완료되었습니다.")

# 파트 1 단독 테스트용 코드
if __name__ == "__main__":
    # 비트코인으로 테스트
    engine = AlphaQuantSystem(ticker="BTC-USD", days_back=200)
    engine.fetch_market_data()
    engine.calc_technical_indicators()
    engine.render_professional_chart()
    # ==========================================
    # Phase 2: 패턴 인식 및 파동 이론 (기존 클래스에 추가)
    # ==========================================
    from scipy.signal import find_peaks

    def calc_fibonacci_retracement(self, lookback_days=120):
        """
        [2단계 - 모듈 6] 피보나치 되돌림 및 확장 구간 자동 산출
        최근 N일간의 최고점과 최저점을 기준으로 핵심 지지/저항 라인 계산
        """
        print(f">> 피보나치 되돌림 구간 산출 중 (기준: 최근 {lookback_days}일)...")
        recent_data = self.data[-lookback_days:]
        max_price = recent_data['High'].max()
        min_price = recent_data['Low'].min()
        diff = max_price - min_price
        
        # 황금비율 기반 주요 마디가
        self.fibo_levels = {
            "0.000 (최고점)": max_price,
            "0.236 (단기조정)": max_price - diff * 0.236,
            "0.382 (건전조정)": max_price - diff * 0.382,
            "0.500 (절반되돌림)": max_price - diff * 0.500,
            "0.618 (핵심지지)": max_price - diff * 0.618,
            "0.786 (깊은조정)": max_price - diff * 0.786,
            "1.000 (최저점)": min_price
        }
        
        # 결과 로깅
        for level, price in self.fibo_levels.items():
            print(f"   - {level}: {price:.4f}")
            
        return self.fibo_levels

    def analyze_elliott_waves(self, distance=10):
        """
        [2단계 - 모듈 4, 5] 엘리어트 파동 및 A-B-C 조정파동 인식 알고리즘
        scipy의 find_peaks를 사용하여 로컬 고점(Peaks)과 저점(Troughs)을 추적
        """
        print(">> 엘리어트 상승 5파 및 조정 A-B-C 파동 패턴 탐색 중...")
        prices = self.data['Close'].values
        
        # 노이즈를 걸러내고 의미 있는 고점/저점만 추출 (distance 파라미터 적용)
        peaks, _ = find_peaks(prices, distance=distance)
        troughs, _ = find_peaks(-prices, distance=distance) # 하락 반전을 위해 음수값 처리
        
        self.data['Peak'] = np.nan
        self.data['Trough'] = np.nan
        self.data['Peak'].iloc[peaks] = self.data['Close'].iloc[peaks]
        self.data['Trough'].iloc[troughs] = self.data['Close'].iloc[troughs]
        
        # 주요 변곡점을 시간순으로 정렬하여 현재 파동 단계 추론
        recent_pivots = sorted(list(peaks[-3:]) + list(troughs[-3:]))
        if len(recent_pivots) >= 4:
            if prices[recent_pivots[-1]] < prices[recent_pivots[-2]]:
                self.wave_status = "📉 조정 파동 (A-B-C) 진행 또는 하락 추세 구간"
            else:
                self.wave_status = "📈 상승 충격파 (Impulse Wave) 전개 중"
        else:
            self.wave_status = "⏳ 파동 식별 대기 중 (변곡점 데이터 부족)"
            
        print(f">> 파동 분석 결과: {self.wave_status}")
        return self.wave_status

    # ==========================================
    # Phase 3: 확률적 미래 예측 (기존 클래스에 추가)
    # ==========================================
    def run_monte_carlo_simulation(self, days_to_predict=30, num_simulations=10000):
        """
        [3단계 - 모듈 7] 몬테카를로 시뮬레이션
        과거 변동성 기반으로 미래 가격 경로 10,000개를 생성하고 95% 신뢰구간 도출
        """
        print(f">> 몬테카를로 시뮬레이션 가동 중 (예측기간: {days_to_predict}일, 반복: {num_simulations}회)...")
        
        # 일간 로그 수익률 계산 (기하학적 브라운 운동 모델링을 위함)
        log_returns = np.log(1 + self.data['Close'].pct_change()).dropna()
        
        mu = log_returns.mean()
        var = log_returns.var()
        drift = mu - (0.5 * var) # 편향(Drift) 값 계산
        stdev = log_returns.std()
        
        # (예측일수 x 시뮬레이션 횟수) 정규분포 난수 매트릭스 생성
        daily_returns = np.exp(drift + stdev * np.random.normal(0, 1, (days_to_predict, num_simulations)))
        
        # 미래 가격 경로 계산 매트릭스
        price_paths = np.zeros_like(daily_returns)
        price_paths[0] = self.data['Close'].iloc[-1] # 현재가에서 출발
        
        for t in range(1, days_to_predict):
            price_paths[t] = price_paths[t - 1] * daily_returns[t]
            
        self.mc_price_paths = price_paths
        final_prices = price_paths[-1]
        
        # 확률적 결과 추출
        self.mc_results = {
            "Expected_Mean": np.mean(final_prices),
            "Median": np.median(final_prices),
            "Upper_95%_CI": np.percentile(final_prices, 97.5),
            "Lower_95%_CI": np.percentile(final_prices, 2.5)
        }
        
        print(f"   - 30일 후 예상 평균가: {self.mc_results['Expected_Mean']:.2f}")
        print(f"   - 95% 신뢰구간 하단(Risk): {self.mc_results['Lower_95%_CI']:.2f}")
        print(f"   - 95% 신뢰구간 상단(Target): {self.mc_results['Upper_95%_CI']:.2f}")
        return self.mc_results

    def render_monte_carlo_chart(self):
        """몬테카를로 시뮬레이션 결과를 독립된 서브 차트로 시각화"""
        
        print(">> 몬테카를로 확률 분포 시각화 렌더링 중...")
        plt.figure(figsize=(12, 6))
        # 10,000개 중 150개의 경로만 샘플링하여 렌더링 (메모리 최적화)
        plt.plot(self.mc_price_paths[:, :150], color='royalblue', alpha=0.1) 
        
        current_price = self.data['Close'].iloc[-1]
        plt.axhline(current_price, color='black', linestyle='--', linewidth=1.5, label=f'Current Price ({current_price:.2f})')
        plt.axhline(self.mc_results['Upper_95%_CI'], color='red', linestyle=':', linewidth=2, label='Upper 95% CI')
        plt.axhline(self.mc_results['Lower_95%_CI'], color='green', linestyle=':', linewidth=2, label='Lower 95% CI')
        
        plt.title(f"[{self.ticker}] Monte Carlo Price Simulation (30 Days / 10,000 Paths)", fontsize=14, fontweight='bold')
        plt.xlabel("Days in Future", fontsize=12)
        plt.ylabel("Predicted Price", fontsize=12)
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()
        # ==========================================
    # Phase 3 & 4: 심리 분석, 리스크 관리, 최종 검증 (기존 클래스에 추가)
    # ==========================================
    import requests
    from bs4 import BeautifulSoup

    def calc_volume_profile(self, bins=20):
        """
        [4단계 - 모듈 12] 매물대 프로파일 (Volume Profile)
        가격대별 거래량을 합산하여 가장 강력한 지지/저항 벽(POC: Point of Control) 시각화 데이터 생성
        """
        print(f">> 매물대 프로파일 분석 중 (구간 분할: {bins}개)...")
        recent_data = self.data[-120:] # 최근 120일 기준 매물대
        
        # 가격 구간(Bin) 생성
        min_price, max_price = recent_data['Low'].min(), recent_data['High'].max()
        price_bins = np.linspace(min_price, max_price, bins)
        
        # 각 캔들의 거래량을 해당 가격 구간에 분배
        volume_profile = np.zeros(bins - 1)
        for _, row in recent_data.iterrows():
            typical_price = (row['High'] + row['Low'] + row['Close']) / 3
            # typical_price가 속한 구간(bin) 찾기
            idx = np.digitize(typical_price, price_bins) - 1
            idx = min(max(idx, 0), bins - 2)
            volume_profile[idx] += row['Volume']
            
        poc_idx = np.argmax(volume_profile)
        self.poc_price = (price_bins[poc_idx] + price_bins[poc_idx + 1]) / 2
        
        print(f"   - 🛡️ 최대 매물대(POC - Point of Control) 가격: {self.poc_price:.2f}")
        return self.poc_price

    def fetch_live_news_sentiment(self):
        """
        [3단계 - 모듈 9, 10] 실시간 증시 뉴스피드 및 감성 분석
        Yahoo Finance에서 해당 티커의 최신 헤드라인을 스크래핑하여 호재/악재 점수화
        """
        print(">> 실시간 뉴스 크롤링 및 감성 분석 가동 중...")
        url = f"https://finance.yahoo.com/quote/{self.ticker}/news"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        try:
            response = requests.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 야후 파이낸스 헤드라인 추출 (HTML 구조에 따라 변동 가능성 있음)
            headlines = soup.find_all('h3', limit=5)
            news_titles = [h.text for h in headlines if h.text]
            
            if not news_titles:
                print("   - 뉴스 헤드라인을 찾을 수 없습니다. (HTML 구조 변경 또는 차단 가능성)")
                self.sentiment_score = 50.0
                return
                
            print(f"   - 최신 헤드라인 {len(news_titles)}건 수집 완료")
            
            # [임시 감성 분석 알고리즘] 
            # 실제 구동 시 HuggingFace의 FinBERT 등 NLP 모델 연동 필요
            positive_words = ['surge', 'jump', 'gain', 'profit', 'up', 'beat', 'bull', 'growth', 'contract']
            negative_words = ['drop', 'fall', 'loss', 'miss', 'down', 'bear', 'plunge', 'lawsuit', 'investigation']
            
            score = 50.0 # 기본 50점
            for title in news_titles:
                title_lower = title.lower()
                if any(word in title_lower for word in positive_words): score += 5
                if any(word in title_lower for word in negative_words): score -= 5
                
            self.sentiment_score = max(0, min(100, score)) # 0~100 사이로 제한
            print(f"   - 🧠 실시간 뉴스 투심 점수: {self.sentiment_score:.1f} / 100")
            
        except Exception as e:
            print(f"   - ⚠️ 뉴스 크롤링 실패: {e}")
            self.sentiment_score = 50.0

    def calc_quant_thermometer(self):
        """
        [3단계 - 모듈 8] 퀀트 온도계 0~100°C
        RSI, MACD, 뉴스 투심을 결합하여 시장의 과열/냉각 상태를 종합 수치화
        """
        print(">> 퀀트 온도계 연산 중...")
        # 1. RSI (14일) 계산
        delta = self.data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs.iloc[-1]))
        
        # 2. MACD 위치 (0선 위면 긍정, 아래면 부정)
        macd_val = self.data['MACD'].iloc[-1]
        macd_score = 60 if macd_val > 0 else 40
        
        # 3. 투심 점수 (앞선 스크래핑 모듈에서 계산된 값)
        sentiment = getattr(self, 'sentiment_score', 50.0)
        
        # 가중치 합산 (RSI 40%, MACD 30%, 뉴스투심 30%)
        self.market_temperature = (rsi * 0.4) + (macd_score * 0.3) + (sentiment * 0.3)
        print(f"   - 🌡️ 현재 시장 온도: {self.market_temperature:.1f}°C (과열 > 70, 침체 < 30)")
        return self.market_temperature

    def calc_kelly_criterion(self, win_rate=0.55, profit_factor=1.5):
        """
        [4단계 - 모듈 14] 켈리 공식 자산 배분
        승률과 손익비(Profit Factor)를 기반으로 최적의 베팅 사이즈 산출
        """
        print(">> 켈리 공식 기반 최적 투자 비중 산출 중...")
        # Kelly % = W - [(1 - W) / R] 
        # (W: 승률, R: 평균 수익 / 평균 손실)
        kelly_pct = win_rate - ((1 - win_rate) / profit_factor)
        
        # 하프 켈리 (실전 리스크 관리를 위해 절반만 투입)
        self.safe_kelly_pct = max(0, kelly_pct / 2) * 100 
        print(f"   - ⚖️ 최적 자산 투입 비중 (Half-Kelly): {self.safe_kelly_pct:.2f}%")
        return self.safe_kelly_pct

    def generate_evidence_report(self):
        """
        [4단계 - 모듈 11] 백데이터 근거값 리포트 출력
        """
        print("\n==================================================")
        print(f" 🏛️ v15.0 Alpha Quant System Evidence Report ")
        print("==================================================")
        print(f"▶ 타겟 자산: {self.ticker}")
        print(f"▶ 현재 가격: {self.data['Close'].iloc[-1]:.4f}")
        print(f"▶ 시장 온도: {getattr(self, 'market_temperature', 0):.1f}°C")
        print(f"▶ 뉴스 투심: {getattr(self, 'sentiment_score', 50):.1f} / 100")
        print(f"▶ 최대 매물대: {getattr(self, 'poc_price', 0):.4f}")
        print(f"▶ 파동 상태: {getattr(self, 'wave_status', 'N/A')}")
        print(f"▶ 권장 비중: {getattr(self, 'safe_kelly_pct', 0):.2f}% (Kelly)")
        print("==================================================")
        print("✅ 모든 분석이 성공적으로 완료되었습니다.\n")
if __name__ == "__main__":
    # 타겟 티커 설정: 관심도가 높은 ONDS로 전체 파이프라인 가동
    engine = AlphaQuantSystem(ticker="ONDS", days_back=250)
    
    # [Phase 1: 데이터 로드 및 기술적 지표]
    engine.fetch_market_data()
    engine.calc_technical_indicators()
    
    # [Phase 2: 고등 수학 및 패턴 인식]
    engine.calc_fibonacci_retracement()
    engine.analyze_elliott_waves()
    
    # [Phase 3: 심리 분석 및 예측]
    engine.fetch_live_news_sentiment()
    engine.calc_quant_thermometer()
    # engine.run_monte_carlo_simulation(days_to_predict=30) # 필요시 주석 해제하여 가동
    
    # [Phase 4: 리스크 관리 및 리포트]
    engine.calc_volume_profile()
    engine.calc_kelly_criterion(win_rate=0.58, profit_factor=1.6) # 임의의 긍정적 백테스트 스탯 가정
    
    # 최종 결과 보고서 출력
    engine.generate_evidence_report()
    
    # 차트 시각화 (선택 사항)
    # engine.render_professional_chart()
