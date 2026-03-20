import streamlit as st
import yfinance as yf
import mplfinance as mpf

st.title("🛠️ 시스템 환경 테스트")

# ONDS 최근 3개월 데이터 다운로드
df = yf.download("ONDS", period="3mo", progress=False)

if not df.empty:
    st.success("✅ 데이터 수집 성공!")
    # 가장 기본 캔들 차트 렌더링
    fig, ax = mpf.plot(df, type='candle', returnfig=True)
    st.pyplot(fig)
else:
    st.error("❌ 데이터 수집 실패 (yfinance 오류)")
