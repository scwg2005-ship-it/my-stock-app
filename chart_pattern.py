import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import locale

# --- 1. 설정 및 한글 폰트 설정 ---
st.set_page_config(layout="wide", page_title="v17.0 Premium Quant")

# 천단위 콤마 설정을 위한 로케일
try:
    locale.setlocale(locale.LC_ALL, 'ko_KR.UTF-8')
except:
    pass # 윈도우 환경 등 로케일 설정 실패 시 패스

# --- 2. 안정적인 한국어 데이터 로드 함수 ---
@st.cache_data(ttl=1800) # 30분 캐시
def load_korean_data(symbol, interval='D'):
    try:
        # FinanceDataReader는 내부적으로 Naver, Daum, Krx 등을 지원합니다.
        # 한국 종목명으로 코드를 찾아 데이터를 가져옵니다.
        df = fdr.DataReader(symbol, exchange='KRX') 
        if df is not None and not df.empty:
            return df.tail(200) # 최근 200일 데이터
        return None
    except Exception as e:
        st.error(f"데이터 로드 오류: {e}")
        return None

# --- 3. 삼각수렴 패턴 계산 함수 ---
def find_convergence_lines(df):
    try:
        if len(df) < 60: return None # 최소 데이터 부족

        # 최근 60일 데이터로 패턴 분석
        data = df.tail(60).copy()
        
        # 고점들과 저점들의 인덱스 찾기 (단순화된 방식)
        highs = data['High'].rolling(7).max()
        lows = data['Low'].rolling(7).min()
        
        high_points = data[data['High'] == highs].dropna()
        low_points = data[data['Low'] == lows].dropna()
        
        if len(high_points) < 3 or len(low_points) < 3: return None

        # 고점들 간의 하락 추세선 (Resistance Line) - 빗각
        high_times = np.array(high_points.index.view(np.int64))
        high_vals = np.array(high_points['High'])
        high_coeffs = np.polyfit(high_times, high_vals, 1) # 1차 정사
        high_line = high_coeffs[0] * np.array(data.index.view(np.int64)) + high_coeffs[1]
        
        # 저점들 간의 상승 추세선 (Support Line) - 빗각
        low_times = np.array(low_points.index.view(np.int64))
        low_vals = np.array(low_points['Low'])
        low_coeffs = np.polyfit(low_times, low_vals, 1) # 1차 근사
        low_line = low_coeffs[0] * np.array(data.index.view(np.int64)) + low_coeffs[1]
        
        # 추세선 데이터 정리
        convergence_data = pd.DataFrame(index=data.index)
        convergence_data['HighLine'] = high_line
        convergence_data['LowLine'] = low_line
        
        # 수렴 여부 판단 (단순)
        start_diff = high_line[0] - low_line[0]
        end_diff = high_line[-1] - low_line[-1]
        is_converging = end_diff < start_diff * 0.7 # 30% 이상 수렴

        return convergence_data, high_points, low_points, is_converging
    except:
        return None

# --- 4. 메인 UI ---
st.title("🏛️ v17.0 Premium Quant (Korean Focus)")

with st.form(key='premium_control'):
    col1, col2 = st.columns([3, 1])
    with col1:
        # 한국어 검색 도입
        stock_
