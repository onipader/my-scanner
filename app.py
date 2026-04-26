import streamlit as st
import yfinance as yf
import pandas as pd
import time
import requests
from datetime import datetime
import io

# 페이지 설정
st.set_page_config(page_title="글로벌 자산 스캐너", page_icon="💰", layout="wide")

st.title("💰 글로벌 주식 & 코인 매수신호 스캐너")
st.markdown("전 세계 주식과 업비트 코인을 분석하여 **볼린저 밴드 하단 돌파** 종목을 찾습니다.")

if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# 사이드바 설정
with st.sidebar:
    st.header("🔍 검색 설정")
    market = st.selectbox("대상 선택", ["업비트 코인 (원화마켓)", "미국주식 (대형주)", "국내주식 (삼성/SK 등)"])
    
    # 🔹 시가총액 순위 종목 수 설정 슬라이더 추가
    top_n = st.slider("시총 순위 범위 설정 (상위 N개)", min_value=10, max_value=300, value=100, step=10)
    
    timeframe = st.selectbox("타임프레임", ["일봉", "주봉", "월봉"])
    start_button = st.button("🚀 분석 시작", use_container_width=True)

# 매핑 설정
time_map = {"일봉":"day", "주봉":"week", "월봉":"month"}
yf_time_map = {"일봉":("1d","1y"), "주봉":("1wk","2y"), "월봉":("1mo","5y")}

def get_upbit_candles(market, unit):
    url = f"https://api.upbit.com/v1/candles/{unit}s?market={market}&count=200"
    res = requests.get(url).json()
    df = pd.DataFrame(res).sort_values('timestamp')
    return df['trade_price']

def check_signal(close_series):
    if len(close_series) < 20: return None
    ma20 = close_series.rolling(window=20).mean()
    std = close_series.rolling(window=20).std()
    lower_band = ma20 - (std * 2)
    curr = close_series.iloc[-1]
    lower = lower_band.iloc[-1]
    if curr <= lower * 1.01:
        return curr
    return None

if start_button:
    st.session_state.found_data = []
    status_area = st.empty() 
    progress_bar = st.progress(0)
    results_container = st.container()
    
    if "업비트" in market:
        # 업비트 시총 순위는 기본적으로 상장 순서나 거래 대금 영향이 크므로, 
        # API에서 전체를 가져온 뒤 슬라이더 값만큼 자릅니다.
        all_markets = [m for m in requests.get("https://api.upbit.com/v1/market/all").json() if m['market'].startswith('KRW-')]
        tickers = all_markets[:top_n] # 🔹 설정한 개수만큼 자르기
    elif "미국" in market:
        # 미국주식 예시 리스트 (실제로는 더 많지만 상위 N개 예시)
        us_list = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL", "AMZN", "META", "BRK-B", "UNH", "V", "JPM", "JNJ", "WMT", "MA", "PG"]
        tickers = us_list[:top_n]
    else:
        # 국내주식 예시 리스트
        kr_list = ["005930.KS", "000660.KS", "035420.KS", "035720.KS", "005380.KS", "000270.KS", "068270.KS", "005490.KS", "051910.KS"]
        tickers = kr_list[:top_n]

    for i, t in enumerate(tickers):
        prog = (i + 1) / len(tickers)
        progress_bar.progress(prog)
        
        t_name = t['korean_name'] if isinstance(t, dict) else t
        status_area.markdown(f"🔍 **현재 분석 중:** `{t_name}` ({i+1}/{len(tickers)})")
        
        try:
            if "업비트" in market:
                prices = get_upbit_candles(t['market'], time_map[timeframe])
                name = t['korean_name']
            else:
                inter, per = yf_time_map[timeframe]
                data = yf.download(t, interval=inter, period=per, progress=False)
                if data.empty: continue
                prices = data['Close'].iloc[:, 0] if isinstance(data['Close'], pd.DataFrame) else data['Close']
                name = t
            
            price = check_signal(prices)
            if price:
                with results_container:
                    st.success(f"✅ **{name}** 포착! 현재가: {price:,.2f}")
                st.session_state.found_data.append({"시간": datetime.now().strftime('%H:%M'), "종목": name, "현재가": price})
            
            time.sleep(0.05)
        except: continue
    
    status_area.info(f"✅ 상위 {len(tickers)}개 종목 분석이 완료되었습니다!")

if st.session_state.found_data:
    st.table(pd.DataFrame(st.session_state.found_data))
