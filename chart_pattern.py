import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from bs4 import BeautifulSoup
from io import StringIO
import re

# --- 1. 프리미엄 스타일 설정 ---
st.set_page_config(layout="wide", page_title="Aegis Master v42.0")
st.markdown("""
    <style>
    .stApp { background-color: #000000; }
    .stMetric { border: 1.5px solid #00f2ff; background-color: #080808; color: #ffffff !important; padding: 18px; border-radius: 12px; box-shadow: 0 0 15px rgba(0,242,255,0.15); }
    .main-title { font-size: 2.5rem; font-weight: 800; color: #ffdf00; text-align: center; margin-bottom: 30px; text-shadow: 0 0 12px rgba(255,223,0,0.6); }
    .status-text { font-size: 1.8rem; font-weight: 800; text-align: center; padding: 15px; border-radius: 12px; margin: 10px 0; }
    .news-card { background-color: #111; padding: 15px; border-radius: 10px; border-left: 5px solid #00f2ff; margin-bottom: 10px; }
    .news-title { font-size: 1.1rem; font-weight: 600; color: #fff; text-decoration: none; }
    .news-title:hover { color: #00f2ff; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 데이터 엔진 (전종목 & 뉴스 수집) ---
@st.cache_data(ttl=86400)
def get_all_krx_master():
    try:
        url = 'http://kind.krx.co.kr/corpoctl/corpList.do?method=download&searchType=13'
        df = pd.read_html(url, header=0)[0]
        df['종목코드'] = df['종목코드'].apply(lambda x: f"{x:06d}")
        return dict(zip(df['종목명'], df['종목코드']))
    except:
        return {"삼성전자": "005930", "우리금융지주": "316140", "현대차": "005380"}

@st.cache_data(ttl=300)
def get_live_news(query):
    headers = {'User-Agent': 'Mozilla/5.0'}
    news_list = []
    try:
        # 네이버 금융 뉴스 검색
        url = f"https://search.naver.com/search.naver?where=news&query={query}"
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        articles = soup.select('.news_area')
        for art in articles[:6]:
            title = art.select_one('.news_tit').text
            link = art.select_one('.news_tit')['href']
            press = art.select_one('.info_group').text.split(' ')[0]
            news_list.append({"title": title, "link": link, "press": press})
    except: pass
    return news_list

@st.cache_data(ttl=60)
def get_rich_stock_data(code, mode="일봉"):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page=1" if mode != "1분봉" else f"https://finance.naver.com/item/sise_time.naver?code={code}&page=1"
        res = requests.get(url, headers=headers)
        dfs = pd.read_html(StringIO(res.text), flavor='lxml')
        df = None
        target_col = '시간' if mode == "1분봉" else '날짜'
        for temp_df in dfs:
            if target_col in temp_df.columns:
                df = temp_df.dropna(subset=[target_col]).copy()
                break
        if df is None: return None
        
        if mode == "1분봉":
            df.columns = ['시간', '종가', '전일비', '매수', '매도', '거래량', '변동량']
            df['시가']=df['고가']=df['저가']=df['종가']
            df = df.set_index('시간').sort_index()
        else:
            df = df.iloc[:, :7]
            df.columns = ['날짜', '종가', '전일비', '시가', '고가', '저가', '거래량']
            df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
            df = df.dropna(subset=['날짜']).set_index('날짜').sort_index()
            
        for col in ['종가', '시가', '고가', '저가', '거래량']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df = df.ffill().dropna()
        df['MA5'] = df['종가'].rolling(window=5).mean()
        df['MA20'] = df['종가'].rolling(window=20).mean()
        df['GC'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1))
        df['DC'] = (df['MA5'] < df['MA20']) & (df['MA5'].shift(1) >= df['MA20'].shift(1))
        # 거래량 증가율
        df['Vol_Ratio'] = df['거래량'] / df['거래량'].rolling(window=5).mean()
        return df
    except: return None

# --- 3. 메인 화면 구성 ---
st.markdown('<p class="main-title">Aegis Master Control v42.0</p>', unsafe_allow_html=True)

all_stocks = get_all_krx_master()
with st.sidebar:
    st.subheader("🔍 실시간 종목 필터링")
    u_input = st.text_input("종목명 입력", value="삼성전자")
    filtered = [n for n in all_stocks.keys() if u_input in n]
    target_name = st.selectbox(f"검색 결과 ({len(filtered)}건)", options=filtered[:100] if filtered else [u_input])
    target_code = all_stocks.get(target_name, "005930")
    view_mode = st.radio("차트 주기", ["1분봉", "일봉", "월봉"], index=1)
    st.divider()
    opt_wave = st.checkbox("엘리어트 파동", value=True)
    opt_cross = st.checkbox("골든/데드크로스", value=True)

df = get_rich_stock_data(target_code, view_mode)

if df is not None:
    curr_p = df['종가'].iloc[-1]
    tab1, tab2, tab3 = st.tabs(["📈 [1P] 통합 차트", "🌡️ [2P] AI 정밀 온도계", "📰 [3P] 실시간 뉴스"])

    # --- [1P] 차트 분석 (고정) ---
    with tab1:
        c1, c2, c3 = st.columns(3)
        c1.metric("🔥 AI 권장 매수", f"{curr_p * 0.99:,.0f}원")
        c2.metric("🚀 목표 익절 (+12%)", f"{curr_p * 1.12:,.0f}원")
        c3.metric("⚠️ 위험 손절 (-6%)", f"{curr_p * 0.94:,.0f}원")

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.05)
        fig.add_trace(go.Candlestick(x=df.index, open=df['시가'], high=df['고가'], low=df['저가'], close=df['종가'],
                                     increasing_line_color='#00ff41', decreasing_line_color='#ff0055', name='시세'), row=1, col=1)
        if opt_cross:
            for d in df[df['GC']].index: fig.add_annotation(x=d, y=df.loc[d,'종가'], text="✨GC", showarrow=True, arrowhead=1, arrowcolor="#ffdf00", font=dict(color="#ffdf00"), row=1, col=1)
            for d in df[df['DC']].index: fig.add_annotation(x=d, y=df.loc[d,'종가'], text="💀DC", showarrow=True, arrowhead=1, arrowcolor="#ff4b4b", font=dict(color="#ff4b4b"), row=1, col=1)
        
        fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False, dragmode=False)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # --- [2P] 풍부해진 AI 온도계 (오른쪽 배치) ---
    with tab2:
        # 정밀 점수 계산
        is_gc = df['GC'].tail(15).any()
        is_uptrend = curr_p > df['MA20'].iloc[-1]
        is_vol_surge = df['Vol_Ratio'].iloc[-1] > 1.5
        
        score = 40 + (25 if is_gc else 0) + (20 if is_uptrend else 0) + (15 if is_vol_surge else 0)
        status, s_color = ("🚀 강력 매수", "#00ff41") if score >= 85 else ("✅ 매수 권장", "#00f2ff") if score >= 65 else ("⚖️ 관망 유지", "#ffdf00")
        
        col_info, col_gauge = st.columns([1, 1.2])
        
        with col_info:
            st.markdown(f'<div class="status-text" style="color:{s_color}; border:2px solid {s_color};">{status}</div>', unsafe_allow_html=True)
            st.write("### 🔍 AI 분석 리포트")
            st.write(f"현재 **{target_name}**의 시장 에너지는 **{score}점**입니다.")
            st.divider()
            st.checkbox("골든크로스 발생 (최근 15봉)", value=is_gc, disabled=True)
            st.checkbox("20일 이평선 정배열 유지", value=is_uptrend, disabled=True)
            st.checkbox("평균 대비 거래량 폭발 (1.5x)", value=is_vol_surge, disabled=True)
            st.info("💡 팁: 점수가 85점 이상일 때 강력한 추세가 형성됩니다.")

        with col_gauge:
            # 오른쪽으로 치우친 게이지 차트
            fig_g = go.Figure(go.Indicator(
                mode="gauge+number", value=score,
                domain={'x': [0, 1], 'y': [0, 1]},
                gauge={
                    'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white"},
                    'bar': {'color': s_color},
                    'bgcolor': "rgba(0,0,0,0)",
                    'steps': [
                        {'range': [0, 40], 'color': "#222"},
                        {'range': [40, 70], 'color': "#333"},
                        {'range': [70, 100], 'color': "#444"}
                    ],
                    'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 90}
                }
            ))
            fig_g.update_layout(height=450, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', margin=dict(t=50, b=0, r=50))
            st.plotly_chart(fig_g, use_container_width=True)

    # --- [3P] 실시간 뉴스 및 URL 연결 ---
    with tab3:
        st.subheader(f"📰 {target_name} 관련 실시간 주요 뉴스")
        news_data = get_live_news(target_name)
        
        if news_data:
            for n in news_data:
                st.markdown(f"""
                <div class="news-card">
                    <a class="news-title" href="{n['link']}" target="_blank">{n['title']}</a><br>
                    <span style="color: #888; font-size: 0.85rem;">{n['press']} | 실시간 업데이트</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.write("관련 뉴스를 불러올 수 없습니다.")
        
        st.divider()
        st.caption("뉴스 제목을 클릭하면 원문 기사 페이지로 이동합니다.")

else:
    st.error("데이터를 불러오는 중 오류가 발생했습니다. 종목명을 다시 확인해 주세요.")
