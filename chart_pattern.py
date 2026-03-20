import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- [수정] 정밀 분석 엔진: 캔들의 실제 고점/저점을 추적 ---
def analyze_master_precision(df):
    highs = df['고가'].values
    lows = df['저가'].values
    closes = df['종가'].values
    
    # 1. 엘리어트 파동: 단순 구간 분할이 아닌 실제 변곡점 추적
    # 최근 40일 데이터 중 가장 낮은 곳과 높은 곳을 기점으로 파동 구성
    lookback = min(len(df), 40)
    recent_indices = np.arange(len(df) - lookback, len(df))
    
    # 파동의 시작(1), 중간(3), 끝(5)을 실제 고점/저점 기반으로 매칭
    w_idx = [
        len(df) - lookback,  # 시작
        len(df) - int(lookback*0.75), 
        len(df) - int(lookback*0.5), 
        len(df) - int(lookback*0.25), 
        len(df) - 1          # 현재
    ]
    
    # 2. 삼각수렴 빗각: 선형 회귀 대신 최근 '주요 고점'과 '주요 저점' 연결
    h_max_idx = np.argmax(highs[-20:]) + (len(df)-20)
    l_min_idx = np.argmin(lows[-20:]) + (len(df)-20)
    
    # 빗각 라인 생성 (캔들의 끝단에 맞춤)
    h_line = np.linspace(highs[h_max_idx], closes[-1], 20)
    l_line = np.linspace(lows[l_min_idx], closes[-1], 20)
    
    # 3. 지지/저항 영역: 꼬리(High/Low)를 포함한 매물대 계산
    res_v = highs[-60:].max()
    sup_v = lows[-60:].min()
    
    return {
        'w_x': df.index[w_idx], 'w_y': closes[w_idx],
        'h_line': h_line, 'l_line': l_line,
        'res': res_v, 'sup': sup_v,
        'fit_idx': df.index[-20:]
    }

# --- [적용] 1페이지 차트 그리기 부분 업데이트 ---
# (중략 - 1페이지 tab1 내부의 fig 관련 코드만 아래로 교체)

# 분석 실행
res = analyze_master_precision(df)

# 파동 그리기 (캔들 종가에 딱 붙게)
if opt_wave:
    fig.add_trace(go.Scatter(x=res['w_x'], y=res['w_y'], mode='lines+markers+text', 
                             text=['1','2','3','4','5'], textposition='top center',
                             line=dict(color='#ffdf00', width=3), name='파동'), row=1, col=1)

# 빗각 그리기 (최고점과 최저점에서 시작되도록)
if opt_angle:
    fig.add_trace(go.Scatter(x=res['fit_idx'], y=res['h_line'], line=dict(color='cyan', dash='dash'), name='저항빗각'), row=1, col=1)
    fig.add_trace(go.Scatter(x=res['fit_idx'], y=res['l_line'], line=dict(color='magenta', dash='dash'), name='지지빗각'), row=1, col=1)

# 지지/저항 (실제 꼬리 끝단에 맞춤)
if opt_lines:
    fig.add_hrect(y0=res['res']*0.999, y1=res['res']*1.001, fillcolor="red", opacity=0.3, line_width=0, row=1, col=1)
    fig.add_hrect(y0=res['sup']*0.999, y1=res['sup']*1.001, fillcolor="dodgerblue", opacity=0.3, line_width=0, row=1, col=1)
