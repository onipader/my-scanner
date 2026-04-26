import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import time
from datetime import datetime

# 1. 초기 설정
st.set_page_config(page_title="코인/주식 스캐너", layout="wide")
st.title("💰 실시간 매수 신호 스캐너")

if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# 2. 사이드바 - 가장 단순하고 확실한 설정
with st.sidebar:
    st.header("🔍 검색 설정")
    market = st.selectbox("대상 선택", ["업비트 코인 (전체)", "미국 대형주 (TOP 20)", "국내 대형주 (TOP 20)"])
    timeframe = st.selectbox("타임프레임", ["일봉", "주봉", "월봉", "1시간봉", "5분봉"])
    start_btn = st.button("🚀 분석 시작", use_container_width=True)

# 3. 데이터 매핑
yf_tf = {"5분봉": "5m", "1시간봉": "60m", "일봉": "1d", "주봉": "1wk", "월봉": "1mo"}
yf_pd = {"5분봉": "1d", "1시간봉": "1w", "일봉": "1y", "주봉": "2y", "월봉": "5y"}

def check_signal(df):
    """기본 볼린저 밴드 하단 돌파 로직"""
    if df is None or len(df) < 20: return None
    close = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
    
    ma20 = close.rolling(window=20).mean()
    std = close.rolling(window=20).std()
    lower_band = ma20 - (std * 2)
    
    curr = close.iloc[-1]
    if curr <= lower_band.iloc[-1] * 1.01: # 하단선 1% 이내
        return curr
    return None

# 4. 분석 시작
if start_btn:
    st.session_state.found_data = []
    status = st.empty()
    prog = st.progress(0)
    
    # 종목 리스트 구성
    if "업비트" in market:
        res = requests.get("https://api.upbit.com/v1/market/all").json()
        tickers = [m['market'].replace("KRW-", "") + "-KRW" for m in res if m['market'].startswith("KRW-")]
        names = [m['korean_name'] for m in res if m['market'].startswith("KRW-")]
    elif "미국" in market:
        tickers = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL", "AMZN", "META", "BRK-B", "UNH", "V", "JPM", "JNJ", "WMT", "MA", "PG", "AVGO", "HD", "ORCL", "COST", "CVX"]
        names = tickers
    else:
        tickers = ["005930.KS", "000660.KS", "373220.KS", "207940.KS", "005380.KS", "068270.KS", "000270.KS", "005490.KS", "035420.KS", "006400.KS", "051910.KS", "035720.KS", "012330.KS", "105560.KS", "055550.KS", "066570.KS", "000810.KS", "032830.KS", "086790.KS", "015760.KS"]
        names = ["삼성전자", "SK하이닉스", "LG엔솔", "삼바", "현대차", "셀트리온", "기아", "POSCO홀딩스", "네이버", "삼성SDI", "LG화학", "카카오", "현대모비스", "KB금융", "신한지주", "LG전자", "삼성화재", "삼성생명", "하나금융", "한국전력"]

    # 루프
    for i, t in enumerate(tickers):
        prog.progress((i + 1) / len(tickers))
        status.markdown(f"🔍 **분석 중:** `{names[i]}`")
        
        try:
            data = yf.download(t, interval=yf_tf[timeframe], period=yf_pd[timeframe], progress=False)
            if data.empty: continue
            
            price = check_signal(data)
            if price:
                st.success(f"✅ **{names[i]}** 신호 포착!")
                st.session_state.found_data.append({"시간": datetime.now().strftime('%H:%M'), "종목": names[i], "코드": t, "현재가": f"{price:,.0f}"})
            time.sleep(0.1)
        except: continue

    status.info("✅ 분석 완료!")

# 5. 결과 표시
if st.session_state.found_data:
    st.table(pd.DataFrame(st.session_state.found_data))
elif start_btn:
    st.warning("현재 신호가 잡힌 종목이 없습니다.")
