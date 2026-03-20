import FinanceDataReader as fdr
import pandas as pd
import numpy as np

def get_stock_code(name):
    """종목명으로 티커/코드 찾기 (한국/미국 통합)"""
    df_krx = fdr.StockListing('KRX') # 한국 시장
    df_nasdaq = fdr.StockListing('NASDAQ') # 나스닥
    
    # 한국 종목명 검색
    target = df_krx[df_krx['Name'] == name]
    if not target.empty:
        return target.iloc[0]['Code']
    
    # 미국 종목명/티커 검색
    target = df_nasdaq[df_nasdaq['Symbol'] == name.upper()]
    if not target.empty:
        return target.iloc[0]['Symbol']
    
    return name # 찾지 못하면 입력값 그대로 반환

def analyze_elliott_wave(symbol_name):
    # 1. 종목 코드 변환 및 데이터 로드
    symbol = get_stock_code(symbol_name)
    df = fdr.DataReader(symbol).tail(100) # 최근 100일 데이터
    
    # 2. 엘리어트 1파(고점) 및 저점 확인
    low_price = df['Low'].min()
    high_price = df['High'].max()
    current_price = df['Close'].iloc[-1]
    
    # 피보나치 되돌림 계산 (2파 눌림목 타점)
    # 보통 1파 상승분의 0.5 ~ 0.618 지점이 강력한 매수 타점
    fib_618 = high_price - (high_price - low_price) * 0.618
    fib_500 = high_price - (high_price - low_price) * 0.5
    
    # 3. 알림 로직 (엘리어트 2파 진행 중 매수 구간 진입 여부)
    status = "관망"
    alert = False
    
    # 현재가가 고점 대비 조정 중이며, 0.5~0.618 구간에 들어왔을 때
    if fib_618 <= current_price <= fib_500:
        status = "⭐ 엘리어트 2파 눌림목 (매수 적기)"
        alert = True
    elif current_price < fib_618:
        status = "과조정 (손절선 확인 필요)"
    elif current_price > fib_500:
        status = "1파 상승 후 조정 진행 중"

    # 4. 결과 리포트
    print(f"--- [{symbol_name} / {symbol}] 분석 결과 ---")
    print(f"현재가: {current_price}")
    print(f"1파 고점: {high_price} | 최근 저점: {low_price}")
    print(f"피보나치 0.618 타점: {fib_618:.2f}")
    print(f"현재 상태: {status}")
    
    if alert:
        send_telegram_alert(symbol_name, current_price, status)

def send_telegram_alert(name, price, msg):
    """자동 알림 시뮬레이션 (실제 텔레그램 봇 API 연결 가능)"""
    print(f"\n🔔 [자동 알림] {name} 종목이 타점에 진입했습니다!")
    print(f"가격: {price} | 상태: {msg}")

# 실행 예시 (한국어 종목명 또는 티커 입력 가능)
analyze_elliott_wave("ONDS")      # 미국 주식
# analyze_elliott_wave("삼성전자") # 한국 주식도 가능
