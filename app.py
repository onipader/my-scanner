import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import time

# 1. 페이지 설정 (가장 가볍고 안정적인 설정)
st.set_page_config(page_title="Signal Scanner", layout="wide")
st.title("💰 실시간 매수 신호 스캐너 (복구 버전)")

# 2. 세션 상태 초기화
if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# 3. 사이드바 설정
with st.sidebar:
    st.header("🔍 검색 설정")
    market_type = st.selectbox("대상 선택", ["업비트 주요코인", "미국 대형주"])
    tf_choice = st.selectbox("타임프레임", ["월봉", "주봉", "일봉"])
    start_btn = st.button("🚀 분석 시작", use_container_width=True)

# yfinance용 타임프레임 및 기간 매핑
tf_map = {"월봉": "1mo", "주봉": "1wk", "일봉": "1d"}
period_map = {"월봉": "5y", "주봉": "2y", "일봉": "1y"}

def check_signal(df):
    """볼린저 밴드 하단 돌파 여부 계산"""
    if len(df) < 20: return None
    
    # 데이터 구조 대응 (yfinance 최신 버전 MultiIndex 처리)
    close = df['Close']
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
        
    ma20 = close.rolling(window=20).mean()
    std = close.rolling(window=20).std()
    lower_band = ma20 - (std * 2)
    
    curr = close.iloc[-1]
    lower = lower_band.iloc[-1]
    
    # 🔹 현재가가 하단선 근처(2% 이내)거나 하단 돌파 시 포착
    if curr <= lower * 1.02:
        return curr
    return None

# 4. 메인 분석 로직
if start_btn:
    st.session_state.found_data = []
    
    # 에러 주범인 FinanceDataReader 없이 직접 티커 지정 (안전성 1순위)
    if market_type == "업비트 주요코인":
        # 사용자님이 확인하신 종목들 (야후 티커 방식)
        tickers = ["BTC-USD", "ETH-USD", "NEAR-USD", "SOL-USD", "TRX-USD", "BCH-USD"]
    else:
        tickers = ["AAPL", "MSFT", "TSLA", "NVDA", "GOOGL", "META"]

    progress_bar = st.progress(0)
    for i, t in enumerate(tickers):
        progress_bar.progress((i + 1) / len(tickers))
        try:
            # yfinance는 기본 설치 라이브러리라 절대 튕기지 않습니다.
            data = yf.download(t, interval=tf_map[tf_choice], period=period_map[tf_choice], progress=False)
            if data.empty: continue
            
            price = check_signal(data)
            if price:
                st.success(f"✅ **{t}** 신호 포착! 현재가: ${price:,.2f}")
                st.session_state.found_data.append({"시간": datetime.now().strftime('%H:%M'), "종목": t, "현재가": price})
            time.sleep(0.1) 
        except: continue

# 5. 결과 출력
if st.session_state.found_data:
    st.divider()
    st.subheader("📊 분석 결과 요약")
    st.table(pd.DataFrame(st.session_state.found_data))
elif start_btn:
    st.warning("현재 신호가 발견된 종목이 없습니다.")
