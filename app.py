import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime
import io
import time

# 페이지 설정
st.set_page_config(page_title="Global Asset Scanner", layout="wide")
st.title("📊 볼린저 밴드 하단 돌파 검색기")

# 세션 상태 초기화
if 'found_data' not in st.session_state:
    st.session_state.found_data = []

with st.sidebar:
    st.header("🔍 검색 설정")
    market_type = st.selectbox("대상 선택", ["업비트 코인", "미국 주식"])
    tf_choice = st.selectbox("타임프레임", ["월봉", "주봉", "일봉"])
    start_btn = st.button("🚀 분석 시작", use_container_width=True)

# 야후 파이낸스 타임프레임 매핑
tf_map = {"월봉": "1mo", "주봉": "1wk", "일봉": "1d"}
period_map = {"월봉": "5y", "주봉": "2y", "일봉": "1y"}

def check_bb_signal(df):
    """실제 가격이 볼밴 하단을 뚫고 올라오는지 체크"""
    if len(df) < 20: return None
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['STD'] = df['Close'].rolling(window=20).std()
    df['Lower'] = df['MA20'] - (df['STD'] * 2)
    
    curr_price = df['Close'].iloc[-1]
    lower_band = df['Lower'].iloc[-1]
    
    # 🔹 현재가가 하단선 근처이거나 돌파 시 신호 발생
    if curr_price <= lower_band * 1.02: # 하단선 위 2% 이내 근접 포함
        return curr_price
    return None

if start_btn:
    st.session_state.found_data = []
    results_container = st.container()
    
    if market_type == "업비트 코인":
        # 업비트 주요 코인 티커 (야후 파이낸스 기준)
        tickers = ["BTC-USD", "ETH-USD", "NEAR-USD", "SOL-USD", "XRP-USD", "ADA-USD", "DOGE-USD", "BCH-USD"]
        
        for t in tickers:
            try:
                data = yf.download(t, interval=tf_map[tf_choice], period=period_map[tf_choice], progress=False)
                price = check_bb_signal(data)
                if price:
                    st.success(f"✅ {t} 포착! 현재가: {price:,.2f}")
                    st.session_state.found_data.append({"시간": datetime.now().strftime('%H:%M'), "종목": t, "현재가": price})
            except: continue
    else:
        # 미국 주식 예시
        tickers = ["AAPL", "MSFT", "TSLA", "NVDA", "GOOGL"]
        for t in tickers:
            try:
                data = yf.download(t, interval=tf_map[tf_choice], period=period_map[tf_choice], progress=False)
                price = check_BB_signal(data)
                if price:
                    st.success(f"✅ {t} 포착! 현재가: {price:,.2f}")
                    st.session_state.found_data.append({"시간": datetime.now().strftime('%H:%M'), "종목": t, "현재가": price})
            except: continue

if st.session_state.found_data:
    st.table(pd.DataFrame(st.session_state.found_data))
