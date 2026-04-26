import streamlit as st
import FinanceDataReader as fdr
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
    market = st.selectbox("대상 선택", ["국내주식 (KOSPI/KOSDAQ)", "미국주식 (NASDAQ/NYSE)", "업비트 코인 (원화마켓)"])
    timeframe = st.selectbox("타임프레임", ["5분봉", "1시간봉", "일봉", "주봉", "월봉"])
    # 🔹 너무 많은 종목은 차단될 수 있어 범위를 조절할 수 있게 추가했습니다.
    top_n = st.slider("스캔 종목 수", 10, 2000, 200) 
    start_button = st.button("🚀 분석 시작", use_container_width=True)

# 시간 매핑
time_map = {"5분봉":"5", "1시간봉":"60", "일봉":"day", "주봉":"week", "월봉":"month"}
yf_time_map = {"5분봉":("5m","1d"), "1시간봉":("60m","1w"), "일봉":("1d","1y"), "주봉":("1wk","2y"), "월봉":("1mo","5y")}

def get_upbit_candles(market, unit):
    if unit in ['month', 'week', 'day']:
        url = f"https://api.upbit.com/v1/candles/{unit}s?market={market}&count=200"
    else:
        url = f"https://api.upbit.com/v1/candles/minutes/{unit}?market={market}&count=200"
    res = requests.get(url).json()
    df = pd.DataFrame(res).sort_values('timestamp')
    return df['trade_price']

def check_signal(close_series):
    """사용자님 원본 로직 유지"""
    if len(close_series) < 20: return None
    basis = close_series.rolling(window=20).mean()
    std = close_series.rolling(window=20).std()
    lower_band = basis - (std * 2)
    
    curr, prev = close_series.iloc[-1], close_series.iloc[-2]
    lower, prev_lower = lower_band.iloc[-1], lower_band.iloc[-2]
    
    # 🔹 하단 돌파 후 회복 신호 (사용자님 로직)
    if prev < prev_lower and curr > lower:
        return curr
    return None

# --- 분석 로직 시작 ---
if start_button:
    st.session_state.found_data = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    results_container = st.container()

    if "업비트" in market:
        markets = [m for m in requests.get("https://api.upbit.com/v1/market/all").json() if m['market'].startswith('KRW-')]
        markets = markets[:top_n]
        for i, m in enumerate(markets):
            progress_bar.progress((i + 1) / len(markets))
            status_text.text(f"코인 분석 중: {i+1}/{len(markets)} ({m['korean_name']})")
            try:
                prices = get_upbit_candles(m['market'], time_map[timeframe])
                price = check_signal(prices)
                if price:
                    with results_container:
                        st.success(f"✅ **{m['korean_name']}** 포착! : {price:,.0f}원")
                    st.session_state.found_data.append({"시간": datetime.now().strftime('%H:%M'), "종목": m['korean_name'], "현재가": price})
                time.sleep(0.05)
            except: continue
    else:
        # 주식 로직 (사용자님 방식)
        if "국내" in market:
            df_list = fdr.StockListing('KRX')
            # 🔹 티커 생성 방식 수정 (종목 코드 6자리 보장)
            tickers = [(str(row['Code']).zfill(6) + ('.KS' if row['Market'] == 'KOSPI' else '.KQ'), row['Name']) for _, row in df_list.iterrows()]
        else:
            df_list = pd.concat([fdr.StockListing('NASDAQ'), fdr.StockListing('NYSE')])
            tickers = [(t, t) for t in df_list['Symbol'].dropna().unique().tolist() if str(t).isalpha()]

        tickers = tickers[:top_n] # 설정한 개수만큼
        inter, per = yf_time_map[timeframe]

        for i, (t, name) in enumerate(tickers):
            progress_bar.progress((i + 1) / len(tickers))
            status_text.text(f"주식 분석 중: {i+1}/{len(tickers)} ({name})")
            try:
                data = yf.download(t, interval=inter, period=per, progress=False, show_errors=False)
                if data.empty or len(data) < 20: continue
                
                # 🔹 데이터 구조 대응 (가장 중요한 수정 포인트)
                if isinstance(data.columns, pd.MultiIndex):
                    close = data['Close'].iloc[:, 0]
                else:
                    close = data['Close']
                
                price = check_signal(close)
                if price:
                    with results_container:
                        st.success(f"✅ **{name}** ({t}) 신호 발생! : {price:,.2f}")
                    st.session_state.found_data.append({"시간": datetime.now().strftime('%H:%M'), "종목": name, "현재가": price})
                time.sleep(0.05)
            except: continue

# --- 결과 출력 (사용자님 UI 유지) ---
if st.session_state.found_data:
    st.divider()
    result_df = pd.DataFrame(st.session_state.found_data)
    st.table(result_df)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        result_df.to_excel(writer, index=False, sheet_name='Scan_Results')
    
    processed_data = output.getvalue()
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("📥 엑셀 저장", data=processed_data, file_name="scanner.xlsx")
    with col2:
        st.download_button("📥 CSV 저장", data=result_df.to_csv(index=False).encode('utf-8-sig'), file_name="scanner.csv")
elif start_button:
    st.warning("신호가 발견되지 않았습니다.")
