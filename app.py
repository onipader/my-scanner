import streamlit as st
import yfinance as yf
import pandas as pd
import time
import requests
from datetime import datetime
import io

# FinanceDataReader 설치 오류 방지를 위한 안전한 임포트
try:
    import FinanceDataReader as fdr
except ImportError:
    st.error("FinanceDataReader 설치 중입니다. 잠시만 기다려주세요.")

st.set_page_config(page_title="글로벌 자산 스캐너", page_icon="💰", layout="wide")
st.title("💰 글로벌 주식 & 코인 매수신호 스캐너")

# 세션 초기화
if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# 사이드바
with st.sidebar:
    st.header("🔍 검색 설정")
    market = st.selectbox("대상 선택", ["국내주식 (KOSPI/KOSDAQ)", "미국주식 (NASDAQ/NYSE)", "업비트 코인 (원화마켓)"])
    timeframe = st.selectbox("타임프레임", ["5분봉", "1시간봉", "일봉", "주봉", "월봉"])
    # 🔹 사용자님이 원하는 '전체' 스캔을 위해 범위를 크게 잡았습니다.
    top_n = st.slider("시총 순위 범위 (상위 N개)", 10, 2000, 200) 
    start_button = st.button("🚀 분석 시작", use_container_width=True)

# 시간 매핑
time_map = {"5분봉":"5", "1시간봉":"60", "일봉":"day", "주봉":"week", "월봉":"month"}
yf_time_map = {"5분봉":("5m","1d"), "1시간봉":("60m","1w"), "일봉":("1d","1y"), "주봉":("1wk","2y"), "월봉":("1mo","5y")}

def check_signal(close_series):
    if len(close_series) < 20: return None
    basis = close_series.rolling(window=20).mean()
    std = close_series.rolling(window=20).std()
    lower_band = basis - (std * 2)
    curr, prev = close_series.iloc[-1], close_series.iloc[-2]
    # 🔹 사용자님 원본 로직 유지
    if prev < lower_band.iloc[-2] and curr > lower_band.iloc[-1]:
        return curr
    return None

if start_button:
    st.session_state.found_data = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    if "업비트" in market:
        markets = [m for m in requests.get("https://api.upbit.com/v1/market/all").json() if m['market'].startswith('KRW-')]
        markets = markets[:top_n]
        for i, m in enumerate(markets):
            progress_bar.progress((i + 1) / len(markets))
            status_text.text(f"분석 중: {m['korean_name']}")
            try:
                # 업비트 API 호출
                unit = time_map[timeframe]
                url = f"https://api.upbit.com/v1/candles/{'minutes/' if unit.isdigit() else ''}{unit}{'s' if not unit.isdigit() else ''}?market={m['market']}&count=100"
                res = requests.get(url).json()
                prices = pd.DataFrame(res).sort_values('timestamp')['trade_price']
                price = check_signal(prices)
                if price:
                    st.success(f"✅ {m['korean_name']} 포착!")
                    st.session_state.found_data.append({"시간": datetime.now().strftime('%H:%M'), "종목": m['korean_name'], "현재가": price})
                time.sleep(0.05)
            except: continue
    else:
        # 주식 스캔
        if "국내" in market:
            df_list = fdr.StockListing('KRX').sort_values('Marcap', ascending=False).head(top_n)
            tickers = [(str(row['Code']).zfill(6) + ('.KS' if row['Market'] == 'KOSPI' else '.KQ'), row['Name']) for _, row in df_list.iterrows()]
        else:
            df_list = fdr.StockListing('NASDAQ').head(top_n)
            tickers = [(row['Symbol'], row['Symbol']) for _, row in df_list.iterrows()]

        inter, per = yf_time_map[timeframe]
        for i, (t, name) in enumerate(tickers):
            progress_bar.progress((i + 1) / len(tickers))
            status_text.text(f"분석 중: {name}")
            try:
                data = yf.download(t, interval=inter, period=per, progress=False, show_errors=False)
                if data.empty: continue
                close = data['Close'].iloc[:, 0] if isinstance(data['Close'], pd.DataFrame) else data['Close']
                price = check_signal(close)
                if price:
                    st.success(f"✅ {name} 포착!")
                    st.session_state.found_data.append({"시간": datetime.now().strftime('%H:%M'), "종목": name, "현재가": price})
                time.sleep(0.05)
            except: continue

if st.session_state.found_data:
    st.table(pd.DataFrame(st.session_state.found_data))
