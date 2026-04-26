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

# --- 세션 상태 초기화 ---
if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# 사이드바 설정
with st.sidebar:
    st.header("🔍 검색 설정")
    # 국내주식은 yfinance 티커(005930.KS 등)로 처리 가능하므로 대상을 명확히 분리
    market = st.selectbox("대상 선택", ["업비트 코인 (원화마켓)", "미국주식 (대형주)", "국내주식 (삼성/SK 등)"])
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
    # 20일 이동평균선 및 표준편차 계산
    ma20 = close_series.rolling(window=20).mean()
    std = close_series.rolling(window=20).std()
    lower_band = ma20 - (std * 2)
    
    curr, prev = close_series.iloc[-1], close_series.iloc[-2]
    lower = lower_band.iloc[-1]
    
    # 🔹 하단 돌파 신호: 전날은 아래에 있다가 오늘 위로 올라오거나 하단선 근처일 때
    if curr <= lower * 1.01: # 하단선 1% 이내 근접 포함
        return curr
    return None

if start_button:
    st.session_state.found_data = []
    results_container = st.container()
    
    if "업비트" in market:
        markets = [m for m in requests.get("https://api.upbit.com/v1/market/all").json() if m['market'].startswith('KRW-')]
        tickers = markets # 업비트 데이터 사용
    elif "미국" in market:
        tickers = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL", "AMZN", "META"] # 대형주 예시
    else:
        tickers = ["005930.KS", "000660.KS", "035420.KS", "035720.KS"] # 국내 대형주 예시

    progress_bar = st.progress(0)
    
    for i, t in enumerate(tickers):
        progress_bar.progress((i + 1) / len(tickers))
        try:
            if "업비트" in market:
                prices = get_upbit_candles(t['market'], time_map[timeframe])
                name = t['korean_name']
            else:
                inter, per = yf_time_map[timeframe]
                data = yf.download(t, interval=inter, period=per, progress=False)
                if data.empty: continue
                # Multi-index 이슈 대응
                prices = data['Close'].iloc[:, 0] if isinstance(data['Close'], pd.DataFrame) else data['Close']
                name = t
            
            price = check_signal(prices)
            if price:
                with results_container:
                    st.success(f"✅ **{name}** 포착! 현재가: {price:,.2f}")
                st.session_state.found_data.append({"시간": datetime.now().strftime('%H:%M'), "종목": name, "현재가": price})
            time.sleep(0.1)
        except: continue

# --- 결과 출력 (생략된 기존 다운로드 로직 동일) ---
if st.session_state.found_data:
    st.table(pd.DataFrame(st.session_state.found_data))
