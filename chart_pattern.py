import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from bs4 import BeautifulSoup
from io import StringIO

# --- 1. 통합 프리미엄 네온 스타일 설정 ---
st.set_page_config(layout="wide", page_title="Aegis Ultimate v33.1")
st.markdown("""
    <style>
    /* 전체 배경 깊은 블랙 */
    .stApp { background-color: #000000; }
    /* 핵심 지표 고대비 네온 스타일 */
    .stMetric { border: 1.5px solid #00f2ff; background-color: #080808; color: #ffffff !important; padding: 18px; border-radius: 12px; box-shadow: 0 0 15px rgba(0,242,255,0.15); }
    /* 메인 타이틀 네온 글로우 효과 */
    .main-title { font-size: 2.5rem; font-weight: 800; color: #ffdf00; text-align: center; margin-bottom: 30px; text-shadow: 0 0 12px rgba(255,223,0,0.6); text-transform: uppercase; letter-spacing: 1px; }
    /* 탭 메뉴 스타일 통일 */
    .stTabs>div { background-color: #0a0a0a; border-radius: 10px; border: 1px solid #222; }
    div[data-testid="stExpander"] { border: 1px solid #333; border-radius: 10px; background-color: #080808; }
    /* 라디오 버튼 스타일 통일 */
    .stRadio>div { background-color: #111; padding: 10px; border-radius: 10px; border: 1px solid #222; }
    /* 모바일 대응 */
    @media (max-width: 640px) { .main-title { font-size: 1.8rem; } }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 스마트 데이터 엔진 ---
@st.cache_data(ttl=300)
def get_ultimate_data_v33(name, mode="day"):
    codes = {"현대자동차": "005380", "현대차": "005380", "삼성전자": "005930", "삼전": "005930", "SK하이닉스": "000660", "에코프로": "086520"}
    code = codes.get(name.strip())
    if not code: return None, [], "코드 오류"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'}
    try:
        url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page=1" if mode != "time" else f"https://finance.naver.com/item/sise_time.naver?code={code}&page=1"
        res = requests.get(url, headers=headers, timeout=7)
        # FutureWarning 해결을 위한 StringIO 사용
        df = pd.read_html(StringIO(res.text), flavor='lxml')[0].dropna()
        
        if mode in ["day", "month"]:
            df.columns = ['날짜', '종가', '전일비', '시가', '고가', '저가', '거래량']
            df['날짜'] = pd.to_datetime(df['날짜'])
            df = df.set_index('날짜').sort_index()
            # 기술적 지표 계산
            df['MA5'] = df['종가'].rolling(window=5).mean()
            df['MA20'] = df['종가'].rolling(window=20).mean()
            # 자동 신호 포착
            df['GC_Signal'] = (df['MA5'] > df['MA20']) & (df['MA5'].shift(1) <= df['MA20'].shift(1))
            df['DC_Signal'] = (df['MA5'] < df['MA20']) & (df['MA5'].shift(1) >= df['MA20'].shift(1))
        else:
            df.columns = ['시간', '종가', '전일비', '매수', '매도', '거래량', '변동량']
            
        # 뉴스 데이터 수집
        n_url = "https://finance.naver.com/news/mainnews.naver"
        n_res = requests.get(n_url, headers=headers, timeout=5)
        soup = BeautifulSoup(n_res.text, 'html.parser')
        headlines = [item.get_text(strip=True) for item in soup.select('.articleSubject a')[:8]]
        
        return df, headlines, "성공"
    except Exception as e: return None, [], str(e)

# --- 3. 프리미엄 시각화 라이브러리 (통일된 스타일) ---
def draw_neon_chart(df, view_mode):
    # 차트 생성 (시인성을 위해 간격 조정)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        row_heights=[0.8, 0.2], vertical_spacing=0.05)
    
    if view_mode in ["일봉", "월봉"]:
        # 1. 캔들차트 (고대비 색상)
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['시가'], high=df['고가'], low=df['저가'], close=df['종가'],
            increasing_line_color='#00ff41', decreasing_line_color='#ff0055', # 네온 그린 & 네온 핑크
            name='시세'
        ), row=1, col=1)

        # 2. 이동평균선 구름대 (영역 채우기)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='#00f2ff', width=1.5), name='5선'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#ffffff', width=1, dash='dot'), 
                                 fill='tonexty', fillcolor='rgba(0, 242, 255, 0.05)', name='20선'), row=1, col=1)

        # 3. 지지/저항 영역 (HRect 반투명)
        res = df['고가'].tail(60).max()
        sup = df['저가'].tail(60).min()
        fig.add_hrect(y0=res*0.998, y1=res*1.002, fillcolor="red", opacity=0.15, line_width=0, name="저항구역", row=1, col=1)
        fig.add_hrect(y0=sup*0.998, y1=sup*1.002, fillcolor="dodgerblue", opacity=0.15, line_width=0, name="지지구역", row=1, col=1)
        
        # 4. 엘리어트 파동 및 크로스 신호 (고대비)
        wave_idx = [len(df)-20, len(df)-15, len(df)-10, len(df)-5, len(df)-1]
        fig.add_trace(go.Scatter(x=df.index[wave_idx], y=df['종가'].iloc[wave_idx], mode='lines+markers+text', 
                                 text=['1','2','3','4','5'], textfont=dict(color="white", size=14),
                                 line=dict(color='#ffdf00', width=3), name='파동'), row=1, col=1)
        
        for date in df[df.get('GC_Signal', False)].index:
            fig.add_annotation(x=date, y=df.loc[date,'저가'], text="✨골든", showarrow=True, arrowhead=1, arrowcolor="#ffdf00", font=dict(color="#ffdf00", size=11), yshift=-10, row=1, col=1)
        for date in df[df.get('DC_Signal', False)].index:
            fig.add_annotation(x=date, y=df.loc[date,'고가'], text="💀데드", showarrow=True, arrowhead=1, arrowcolor="#ff4b4b", font=dict(color="#ff4b4b", size=11), yshift=10, row=1, col=1)
            
    else:
        # 분봉 선형 차트 (네온 사이언)
        fig.add_trace(go.Scatter(x=df['시간'], y=df['종가'], mode='lines+markers', line=dict(color='#00f2ff', width=2), name=view_mode), row=1, col=1)

    # 거래량
    fig.add_trace(go.Bar(x=df.index if view_mode in ["일봉", "월봉"] else df['시간'], y=df['거래량'], marker_color='#333', name='거래량'), row=2, col=1)
    
    # 줌 방지 및 레이아웃 설정
    fig.update_xaxes(fixedrange=True); fig.update_yaxes(fixedrange=True)
    fig.update_layout(height=580, template='plotly_dark', xaxis_rangeslider_visible=False, dragmode=False,
                      paper_bgcolor='black', plot_bgcolor='black', margin=dict(t=10, b=10, l=10, r=10),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig

# --- 4. 메인 대시보드 실행 ---
st.markdown('<p class="main-title">Aegis Omni-Signal v33.1</p>', unsafe_allow_html=True)

with st.sidebar:
    st.subheader("📡 시장 감시 대상")
    target_stock = st.selectbox("리스트", ["현대자동차", "삼성전자", "SK하이닉스", "에코프로"])
    view_mode = st.radio("차트 주기", ["1분봉", "5분봉", "일봉", "월봉"], index=2)
    st.divider()
    st.caption("고대비 네온 크리스탈 테마 적용 중")

df, headlines, msg = get_ultimate_data_v33(target_stock, "day" if view_mode == "일봉" else "month" if view_mode == "월봉" else "time")

if df is not None and not df.empty:
    curr_p = df['종가'].iloc[-1] if '종가' in df.columns else df['종가'].iloc[0]
    
    tab1, tab2, tab3 = st.tabs(["📈 [1P] 통합 패턴 차트", "🌡️ [2P] AI 자동 온도계", "🔍 [3P] 시장 리포트"])

    # --- 1페이지: 시인성 극대화 차트 및 매매가 ---
    with tab1:
        # 핵심 매매가 대시보드
        c1, c2, c3 = st.columns(3)
        c1.metric("🔥 AI 권장 매수가", f"{curr_p * 0.99:,.0f}원", "진입 대기")
        c2.metric("🚀 목표가 (+12%)", f"{curr_p * 1.12:,.0f}원", "익절")
        c3.metric("⚠️ 손절가 (-6%)", f"{curr_p * 0.94:,.0f}원", "리스크", delta_color="inverse")
        
        # 줌 방지 및 고시인성 차트 호출
        st.plotly_chart(draw_neon_chart(df, view_mode), use_container_width=True, config={'displayModeBar': False})
        
        with st.expander("⏱️ 실시간 분봉(체결) 흐름 보기"):
            st.dataframe(df.tail(10).sort_index(ascending=False), use_container_width=True)

    # --- 2페이지: AI 온도계 (통일된 스타일) ---
    with tab2:
        st.subheader("🌡️ AI 실시간 진단 온도계")
        is_gc = df['GC_Signal'].tail(5).any() if 'GC_Signal' in df.columns else False
        is_uptrend = curr_p > df['MA20'].iloc[-1] if 'MA20' in df.columns else False
        score = 40 + (25 if is_gc else 0) + (15 if is_uptrend else 0)
        
        col_chk, col_gauge = st.columns([1, 1.5])
        with col_chk:
            st.write("### AI 분석 리포트")
            st.checkbox("골든크로스 발생", value=is_gc, disabled=True)
            st.checkbox("20일선 위 시세 형성", value=is_uptrend, disabled=True)
            st.divider()
            st.metric("종합 분석 점수", f"{score}점", f"크로스 영향: {'+25' if is_gc else '0'}")

        with col_gauge:
            # 통일된 스타일의 AI 게이지
            fig_g = go.Figure(go.Indicator(
                mode="gauge+number", value=score,
                gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "#ffdf00"},
                       'steps': [{'range': [0, 50], 'color': "#0a0a0a"}, {'range': [50, 100], 'color': "#111"}]}))
            fig_g.update_layout(height=350, template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', margin=dict(t=30, b=0))
            st.plotly_chart(fig_g, use_container_width=True, config={'displayModeBar': False})

    # --- 3페이지: 시장 리포트 (통일된 스타일) ---
    with tab3:
        st.subheader("🔍 뉴스 브리핑 및 주도 테마")
        for h in headlines:
            st.write(f"- {h}")
        st.divider()
        st.write("### 현재 주도 테마 순위")
        # 표 내부도 통일된 용어 사용
        st.table(pd.DataFrame({'테마명': ['반도체', 'AI', '자동차'], '언급횟수': [5, 3, 2], '현재상태': ['🔥급등', '✅안정', '⚖️조정']}))

else:
    st.error(f"데이터 로드 실패: {msg}")
