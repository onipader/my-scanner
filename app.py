import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime
import io
import time

# 1. 페이지 설정 및 제목
st.set_page_config(page_title="Global Signal Scanner", layout="wide")
st.title("💰 실전 매수 신호 스캐너 (Error-Free)")

# 2. 세션 상태 초기화
if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# 3. 사이드바 설정
with st.sidebar:
    st.header("🔍 검색 설정")
    market_type = st.selectbox("대상 선택", ["업비트 주요코인", "미국 대형주"])
    tf_choice = st.selectbox("타임프레임", ["월봉", "주봉", "일봉"])
    start_btn = st.button("🚀 분석 시작", use_container_width=True)

# 타임프레임 매핑
tf_map = {"월봉": "1mo", "주봉": "1wk", "일봉": "1d"}
period_map = {"월봉": "5y", "주봉": "2y", "일봉": "1y"}

def check_signal(df):
    """볼린저 밴드 하단 돌파 여부 계산"""
    if len(df) < 20: return None
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['STD'] = df['Close'].rolling(window=20).std()
    df['Lower'] = df['MA20'] - (df['STD'] * 2)
    
    curr = df['Close'].iloc[-1]
    lower = df['Lower'].iloc[-1]
    
    # 🔹 현재가가 하단선 근처(2% 이내)이거나 하단에 있으면 포착
    if curr <= lower * 1.02:
        return curr
    return None

# 4. 메인 로직
if start_btn:
    st.session_state.found_data = []
    
    # 분석 대상 리스트
    if market_type == "업비트 주요코인":
        # 사용자님이 확인하신 종목 위주 (야후 티커 방식)
        tickers = ["BTC-USD", "ETH-USD", "NEAR-USD", "SOL-USD", "BCH-USD", "TRX-USD"]
    else:
        tickers = ["AAPL", "MSFT", "TSLA", "NVDA", "META"]

    progress_bar = st.progress(0)
    for i, t in enumerate(tickers):
        progress_bar.progress((i + 1) / len(tickers))
        try:
            # 데이터 수집 (안정적인 yfinance 사용)
            data = yf.download(t, interval=tf_map[tf_choice], period=period_map[tf_choice], progress=False)
            if data.empty: continue
            
            price = check_signal(data)
            if price:
                st.success(f"✅ **{t}** 신호 포착! 현재가: ${price:,.2f}")
                st.session_state.found_data.append({"시간": datetime.now().strftime('%H:%M'), "종목": t, "현재가": price})
            time.sleep(0.2) # API 과부하 방지
        except: continue

# 5. 결과 출력
if st.session_state.found_data:
    st.divider()
    st.subheader("📊 분석 결과")
    st.table(pd.DataFrame(st.session_state.found_data))
