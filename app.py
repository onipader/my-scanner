import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime
import io
import time

# 1. 페이지 설정
st.set_page_config(page_title="Global Signal Scanner", layout="wide")
st.title("💰 실시간 매수 신호 스캐너 (복구 버전)")

# 2. 세션 상태 초기화
if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# 3. 사이드바 설정
with st.sidebar:
    st.header("🔍 검색 설정")
    market_type = st.selectbox("대상 선택", ["업비트 원화코인", "미국 대형주"])
    tf_choice = st.selectbox("타임프레임", ["월봉", "주봉", "일봉"])
    start_btn = st.button("🚀 분석 시작", use_container_width=True)

# 야후 파이낸스용 타임프레임 매핑
tf_map = {"월봉": "1mo", "주봉": "1wk", "일봉": "1d"}
period_map = {"월봉": "5y", "주봉": "2y", "일봉": "1y"}

def check_bb_signal(df):
    """볼린저 밴드 하단 돌파 여부 계산"""
    if len(df) < 20: return None
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['STD'] = df['Close'].rolling(window=20).std()
    df['Lower'] = df['MA20'] - (df['STD'] * 2)
    
    curr = df['Close'].iloc[-1]
    lower = df['Lower'].iloc[-1]
    
    # 🔹 현재가가 하단선 근처(2% 이내)거나 아래에 있으면 포착
    if curr <= lower * 1.02:
        return curr
    return None

# 4. 분석 로직
if start_btn:
    st.session_state.found_data = []
    
    # 분석 대상 리스트 구성 (에러 유발 요인 제거)
    if market_type == "업비트 원화코인":
        # 사용자님이 차트에서 보신 주요 종목 (야후 티커)
        tickers = ["BTC-USD", "ETH-USD", "NEAR-USD", "SOL-USD", "BCH-USD", "TRX-USD", "ADA-USD"]
    else:
        tickers = ["AAPL", "MSFT", "TSLA", "NVDA", "GOOGL"]

    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, t in enumerate(tickers):
        progress_bar.progress((i + 1) / len(tickers))
        status_text.text(f"분석 중: {t}")
        try:
            # yfinance로 데이터 직접 수집 (안정성 최우선)
            data = yf.download(t, interval=tf_map[tf_choice], period=period_map[tf_choice], progress=False)
            if data.empty: continue
            
            price = check_bb_signal(data)
            if price:
                st.success(f"✅ **{t}** 신호 포착! 현재가: ${price:,.2f}")
                st.session_state.found_data.append({
                    "시간": datetime.now().strftime('%H:%M'),
                    "종목": t,
                    "현재가": round(float(price), 2)
                })
            time.sleep(0.2) # API 제한 방지
        except: continue
    status_text.text("분석 완료!")

# 5. 결과 테이블 출력
if st.session_state.found_data:
    st.divider()
    st.subheader("📊 포착된 종목 리스트")
    st.table(pd.DataFrame(st.session_state.found_data))
