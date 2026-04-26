import streamlit as st
import yfinance as yf
import pandas as pd
import time
import requests
from datetime import datetime

# 페이지 설정
st.set_page_config(page_title="글로벌 자산 스캐너", layout="wide")
st.title("💰 글로벌 주식 & 코인 매수신호 스캐너")

if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# 사이드바 설정
with st.sidebar:
    st.header("🔍 검색 설정")
    market = st.selectbox("대상 선택", ["국내주식 (KOSPI/KOSDAQ)", "업비트 코인 (원화마켓)", "미국주식 (S&P500)"])
    
    # 시총 순위 범위 (국내 주식 전체 대응)
    top_n = st.slider("시총 순위 범위 설정 (상위 N개)", min_value=10, max_value=2000, value=100, step=50)
    
    # 🔹 타임프레임 옵션 확장
    tf_display = ["5분봉", "1시간봉", "4시간봉", "일봉", "주봉", "월봉"]
    tf_choice = st.selectbox("타임프레임", tf_display)
    
    start_button = st.button("🚀 분석 시작", use_container_width=True)

# 🔹 타임프레임 매핑 (yfinance용 / 업비트용)
yf_tf_map = {
    "5분봉": ("5m", "1d"), "1시간봉": ("60m", "1w"), "4시간봉": ("90m", "2w"), # 4시간봉은 yf에서 90m나 1h 조합 필요
    "일봉": ("1d", "1y"), "주봉": ("1wk", "2y"), "월봉": ("1mo", "5y")
}
upbit_tf_map = {
    "5분봉": "5", "1시간봉": "60", "4시간봉": "240", "일봉": "days", "주봉": "weeks", "월봉": "months"
}

def get_upbit_candles(market, tf_choice):
    unit = upbit_tf_map[tf_choice]
    if tf_choice in ["일봉", "주봉", "월봉"]:
        url = f"https://api.upbit.com/v1/candles/{unit}?market={market}&count=100"
    else:
        url = f"https://api.upbit.com/v1/candles/minutes/{unit}?market={market}&count=100"
    res = requests.get(url).json()
    return pd.DataFrame(res).sort_values('timestamp')['trade_price']

def check_signal(prices):
    if len(prices) < 20: return None
    ma20 = prices.rolling(window=20).mean()
    std = prices.rolling(window=20).std()
    lower_band = ma20 - (std * 2)
    
    curr, prev = prices.iloc[-1], prices.iloc[-2]
    if prev < lower_band.iloc[-2] and curr > lower_band.iloc[-1]: # 하단 돌파 후 회복 신호
        return curr
    elif curr <= lower_band.iloc[-1] * 1.005: # 혹은 하단선 초밀착
        return curr
    return None

if start_button:
    st.session_state.found_data = []
    status_area = st.empty() 
    progress_bar = st.progress(0)
    results_container = st.container()
    
    # 🔹 종목 리스트 구성
    if "국내" in market:
        # FinanceDataReader 대신 안정적인 리스트 구성 (실제 운영 시 CSV/JSON 관리 권장)
        # yfinance를 위해 .KS(코스피), .KQ(코스닥) 접미사가 필요합니다.
        # 시총 순위 데이터가 외부 API로 확보되지 않을 시 주요 종목 위주로 자동 생성
        status_area.warning("국내 주식 데이터를 구성 중입니다...")
        # 임시 가이드: 주요 종목 코드 생성 (실제 시총 데이터는 서버 부하로 조절 필요)
        tickers = ["005930.KS", "000660.KS", "035420.KS", "035720.KS", "005380.KS", "068270.KS", "000270.KS", "005490.KS", "051910.KS", "105560.KS"] # ... 상위 종목 확장 가능
        tickers = tickers[:top_n]
    elif "업비트" in market:
        tickers = [m for m in requests.get("https://api.upbit.com/v1/market/all").json() if m['market'].startswith('KRW-')][:top_n]
    else:
        tickers = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL", "AMZN", "META"][:top_n]

    for i, t in enumerate(tickers):
        prog = (i + 1) / len(tickers)
        progress_bar.progress(prog)
        t_name = t['korean_name'] if isinstance(t, dict) else t
        status_area.markdown(f"🔍 **분석 중:** `{t_name}` ({tf_choice})")
        
        try:
            if "업비트" in market:
                prices = get_upbit_candles(t['market'], tf_choice)
            else:
                itv, per = yf_tf_map[tf_choice]
                data = yf.download(t, interval=itv, period=per, progress=False)
                if data.empty: continue
                prices = data['Close'].iloc[:, 0] if isinstance(data['Close'], pd.DataFrame) else data['Close']
            
            price = check_signal(prices)
            if price:
                with results_container:
                    st.success(f"✅ **{t_name}** 신호 포착! ({price:,.0f}원/$)")
                st.session_state.found_data.append({"시간": datetime.now().strftime('%H:%M'), "종목": t_name, "현재가": price})
            time.sleep(0.05)
        except: continue
    
    status_area.info("✅ 분석 완료!")

if st.session_state.found_data:
    st.table(pd.DataFrame(st.session_state.found_data))
