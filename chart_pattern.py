@st.cache_data(ttl=3600, show_spinner="데이터 오라클 접속 중...")
def get_oracle_data(symbol, market_type):
    try:
        if market_type == "KR":
            # [수정] 한국 주식은 무조건 FinanceDataReader만 사용 (야후 차단 회피)
            df = fdr.DataReader(symbol)
            if df is None or df.empty:
                # 혹시 모르니 종목코드 뒤에 .KS나 .KQ를 붙여서 재시도
                df = fdr.DataReader(f"{symbol}") 
        else:
            # [수정] 미국 주식은 yfinance 사용하되, 차단 방지용 라이브러리 설정 추가
            ticker = yf.Ticker(symbol)
            # 데이터 호출 전 아주 짧은 대기 (연속 호출 방지)
            time.sleep(0.5)
            df = ticker.history(period="1y")
            
        if df is None or df.empty:
            return None
            
        # 컬럼명 표준화
        df.columns = [str(c).capitalize() for c in df.columns]
        
        # 인덱스가 Datetime인지 확인 및 정렬
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        
        df = df.apply(pd.to_numeric, errors='coerce').dropna()
        
        # 보조지표 계산 (데이터 개수가 충분할 때만)
        if len(df) > 120:
            for ma in [5, 20, 60, 120]:
                df[f'MA{ma}'] = df['Close'].rolling(ma).mean()
            
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
            df['High_Max'] = df['High'].rolling(20).max()
            df['Low_Min'] = df['Low'].rolling(20).min()
            return df
        else:
            return df # 데이터가 적어도 일단 반환
            
    except Exception as e:
        st.error(f"데이터 엔진 오류: {e}")
        return None
