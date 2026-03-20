import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import yfinance as yf
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO
from bs4 import BeautifulSoup
import time

# --- 1. [디자인] 설정 (반드시 import 다음에 위치) ---
st.set_page_config(layout="wide", page_title="Aegis Oracle v86.0")

# (중략: st.markdown 스타일 부분은 그대로 두세요)

# --- 2. [데이터] 함수 정의 ---

@st.cache_data(ttl=3600)
def find_symbol_intelligent(query):
    # (기존 코드 내용)
    try:
        url_krx = 'http://kind.krx.co.kr/corpoctl/corpList.do?method=download'
        res = requests.get(url_krx, timeout=5)
        df_krx = pd.read_html(StringIO(res.text), header=0)[0]
        clean_query = query.replace(" ", "")
        match = df_krx[df_krx['회사명'].str.replace(" ", "").str.contains(clean_query, na=False, case=False)]
        if not match.empty:
            return f"{match.iloc[0]['종목코드']:06d}", match.iloc[0]['회사명'], "KR"
    except: pass
    return query.upper(), query, "US"

# ✅ 이 부분이 핵심입니다! @st.cache_data와 def 사이에 빈 줄이 없어야 합니다.
@st.cache_data(ttl=3600, show_spinner="데이터 오라클 접속 중...")
def get_oracle_data(symbol, market_type):
    try:
        if market_type == "KR":
            # 한국 주식 (FinanceDataReader 우선 사용)
            df = fdr.DataReader(symbol)
        else:
            # 미국 주식 (yfinance)
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="1y")
            
        if df is None or df.empty: return None
        
        # 데이터 전처리 로직 (이전 답변과 동일)
        df.columns = [str(c).capitalize() for c in df.columns]
        df = df.apply(pd.to_numeric, errors='coerce').dropna()
        # ... 이하 생략 ...
        return df
    except Exception as e:
        return None

# --- 이후 메인 로직 실행 ---
