import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. 설정 ---
st.set_page_config(layout="wide", page_title="v19.4 Alpha Quant")

# --- 2. 데이터 수집 (안정화된 Scraper) ---
@st.cache_data(ttl=3600)
def get_naver_data(name):
    codes = {"현대자동차": "005380", "현대차": "005380", "삼성전자": "005930", "삼전": "005930", "SK하이닉스": "000660", "에코프로": "086520"}
    code = codes.get(name.strip())
    if not code: return None
    all_dfs = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        for p in range(1, 6): # 데이터 양을 늘려 POC 신뢰도 확보
            url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page={p}"
            res = requests.get(url, headers=headers)
            df_list = pd.read_html(res.text)
            if df_list: all_dfs.append(df_list[0].dropna())
        df = pd.concat(all_dfs)
        df.columns = ['Date', 'Close', 'Diff', 'Open', 'High', 'Low', 'Volume']
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.set_index('Date').sort_index()
        for col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    except: return None

# --- 3. 분석 알고리즘 (POC & 삼각수렴) ---
def analyze_advanced(df):
    # 1. POC (Point of Control) 계산
    # 최근 데이터에서 거래량이 가장 많이 실린 가격대 추출
    price_bins = pd.cut(df['Close'], bins=20)
    poc_range = df.groupby(price_bins, observed=True)['Volume'].sum().idxmax()
    poc_price = (poc_range.left + poc_range.right) / 2
    
    # 2. 삼각수렴 빗각 (최근 20일)
    x = np.arange(len(df))
    h_fit = np.polyfit(x[-20:], df['High'].iloc[-20:], 1)
    l_fit = np.polyfit(x[-20:], df['Low'].iloc[-20:], 1)
    
    # 3. RSI & 변동성
    delta = df['Close'].diff()
    up = delta.clip(lower=0).rolling(14).mean()
    down = -1 * delta.clip(upper=0).rolling(14).mean()
    rsi = 100 - (100 / (1 + (up / down)))
    
    return {
        'poc': poc_price,
        'h_line': h_fit[0] * x[-20:] + h_fit[1],
        'l_line': l_fit[0] * x[-20:] + l_fit[1],
        'rsi': rsi.iloc[-1],
        'curr_price': df['Close'].iloc[-1]
    }

# --- 4. 메인 UI ---
st.title("🏛️ v19.4 Alpha Quant (POC & Convergence)")

with st.form(key='advanced_form'):
    col1, col2 = st.columns([3, 1])
    with col1:
        stock_input = st.text_input("종목명 입력", value="현대자동차")
    with col2:
        st.write(" ")
        submitted = st.form_submit_button("차트 분석 실행 🚀")

if submitted or stock_input:
    df = get_naver_data(stock_input)
    if df is not None and len(df) > 30:
        res = analyze_advanced(df)
        tab1, tab2, tab3 = st.tabs(["📊 POC & 삼각수렴", "🌡️ 시장 온도", "📑 전략 리포트"])
        
        with tab1:
            st.subheader(f"[{stock_input}] 매물대 POC 및 수렴 패턴")
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
            
            # 캔들
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
            
            # 1. POC 라인 (황금색 실선) - 매물대 중심점
            fig.add_hline(y=res['poc'], line_dash="solid", line_color="gold", line_width=3, 
                          annotation_text=f"POC(중심매물대): {res['poc']:,.0f}", row=1, col=1)
            
            # 2. 현재가 라인 (흰색 점선)
            fig.add_hline(y=res['curr_price'], line_dash="dot", line_color="white", line_width=1, 
                          annotation_text=f"현재가: {res['curr_price']:,.0f}", row=1, col=1)
            
            # 3. 삼각수렴 빗각 (최근 20일)
            fig.add_trace(go.Scatter(x=df.index[-20:], y=res['h_line'], line=dict(color='cyan', dash='dash'), name='수렴 상단'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index[-20:], y=res['l_line'], line=dict(color='magenta', dash='dash'), name='수렴 하단'), row=1, col=1)
            
            # 거래량
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color='gray'), row=2, col=1)
            
            fig.update_layout(height=650, template='plotly_dark', xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
            
        with tab2:
            st.metric("현재 RSI", f"{res['rsi']:.1f}")
            st.write(f"현재 가격이 POC 대비 **{((res['curr_price'] - res['poc']) / res['poc'] * 100):+.2f}%** 위치에 있습니다.")
        with tab3:
            st.success("수렴 끝단에서 방향성 돌파 시 강력한 추세가 예상됩니다.")
    else:
        st.error("데이터 로드 실패!")
