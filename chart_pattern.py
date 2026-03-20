import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. 설정 ---
st.set_page_config(layout="wide", page_title="v19.3 Alpha Quant")

# --- 2. 데이터 수집 (안정화된 Scraper) ---
@st.cache_data(ttl=3600)
def get_naver_data(name):
    codes = {"현대자동차": "005380", "현대차": "005380", "삼성전자": "005930", "삼전": "005930", "SK하이닉스": "000660"}
    code = codes.get(name.strip())
    if not code: return None
    all_dfs = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        for p in range(1, 5): # 데이터 양을 늘려 지지/저항 신뢰도 확보
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

# --- 3. 분석 알고리즘 (수평 지지/저항 추가) ---
def analyze_sr_levels(df):
    # 최근 60일 데이터 기준
    recent_df = df.tail(60)
    resistance = recent_df['High'].max() # 최고점 저항
    support = recent_df['Low'].min()    # 최저점 지지
    
    # 빗각 추세 (최근 15일)
    x = np.arange(len(df))
    h_fit = np.polyfit(x[-15:], df['High'].iloc[-15:], 1)
    l_fit = np.polyfit(x[-15:], df['Low'].iloc[-15:], 1)
    
    # 온도계 점수 계산 (RSI 기반)
    delta = df['Close'].diff()
    up = delta.clip(lower=0).rolling(14).mean()
    down = -1 * delta.clip(upper=0).rolling(14).mean()
    rsi = 100 - (100 / (1 + (up / down)))
    
    return {
        'res_level': resistance,
        'sup_level': support,
        'h_line': h_fit[0] * x[-15:] + h_fit[1],
        'l_line': l_fit[0] * x[-15:] + l_fit[1],
        'rsi': rsi.iloc[-1],
        'score': rsi.iloc[-1] # 단순화된 점수
    }

# --- 4. 메인 UI ---
st.title("🏛️ v19.3 Alpha Quant (Support & Resistance)")

with st.form(key='sr_form'):
    col1, col2 = st.columns([3, 1])
    with col1:
        stock_input = st.text_input("종목명 입력", value="현대자동차")
    with col2:
        st.write(" ")
        submitted = st.form_submit_button("전략 분석 실행 🚀")

if submitted or stock_input:
    df = get_naver_data(stock_input)
    if df is not None and len(df) > 20:
        res = analyze_sr_levels(df)
        tab1, tab2, tab3 = st.tabs(["📈 지지/저항 차트", "🌡️ 투자 온도계", "📋 매매 전략"])
        
        with tab1:
            st.subheader(f"[{stock_input}] 일봉 지지 및 저항선")
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
            
            # 캔들차트
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='시세'), row=1, col=1)
            
            # 1. 수평 저항선 (최근 고점 - 빨간 실선)
            fig.add_hline(y=res['res_level'], line_dash="solid", line_color="red", line_width=2, 
                          annotation_text=f"강력 저항: {res['res_level']:,.0f}", row=1, col=1)
            
            # 2. 수평 지지선 (최근 저점 - 파란 실선)
            fig.add_hline(y=res['sup_level'], line_dash="solid", line_color="dodgerblue", line_width=2, 
                          annotation_text=f"강력 지지: {res['sup_level']:,.0f}", row=1, col=1)
            
            # 3. 빗각 추세선 (수렴 확인용 점선)
            fig.add_trace(go.Scatter(x=df.index[-15:], y=res['h_line'], line=dict(color='orange', dash='dot'), name='하락 빗각'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index[-15:], y=res['l_line'], line=dict(color='springgreen', dash='dot'), name='상승 빗각'), row=1, col=1)
            
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='거래량', marker_color='gray'), row=2, col=1)
            fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
            
        with tab2:
            st.metric("현재 투자 온도", f"{res['score']:.1f}°C")
        with tab3:
            st.write(f"현재가는 저항선 대비 {((res['res_level'] - df['Close'].iloc[-1]) / res['res_level'] * 100):.1f}% 아래에 있습니다.")
    else:
        st.error("데이터 로드 실패!")
