import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
import time
import requests
from datetime import datetime
import io

# 1. 페이지 설정
st.set_page_config(page_title="글로벌 자산 스캐너", page_icon="💰", layout="wide")

st.title("💰 글로벌 주식 & 코인 매수신호 스캐너")
st.markdown("전 세계 주식과 업비트 코인을 분석하여 **볼린저 밴드 하단 돌파** 종목을 찾습니다.")

# 2. 세션 상태 초기화
if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# 3. 사이드바 설정
with st.sidebar:
    st.header("🔍 검색 설정")
    market = st.selectbox("대상 선택", ["국내주식 (KOSPI/KOSDAQ)", "미국주식 (NASDAQ/NYSE)", "업비트 코인 (원화마켓)"])
    timeframe = st.selectbox("타임프레임", ["5분봉", "1시간봉", "4시간봉", "일봉", "주봉", "월봉"])
    start_button = st.button("🚀 분석 시작", use_container_width=True)

# 4. 시간 매핑 설정
time_map = {
    "5분봉": "5", "1시간봉": "60", "4시간봉": "240", 
    "일봉": "day", "주봉": "week", "월봉": "month"
}

yf_time_map = {
    "5분봉": ("5m", "1d"), 
    "1시간봉": ("1h", "2y"), 
    "4시간봉": ("1h", "2y"), 
    "일봉": ("1d", "2y"), 
    "주봉": ("1wk", "max"), 
    "월봉": ("1mo", "max")
}

def get_upbit_candles(market, unit):
    try:
        if unit in ['month', 'week', 'day']:
            url = f"https://api.upbit.com/v1/candles/{unit}s?market={market}&count=200"
        else:
            url = f"https://api.upbit.com/v1/candles/minutes/{unit}?market={market}&count=200"
        res = requests.get(url).json()
        df = pd.DataFrame(res).sort_values('timestamp')
        return df['trade_price']
    except:
        return pd.Series()

def check_signal(close_series):
    if len(close_series) < 20: return None
    basis = close_series.rolling(window=20).mean()
    std = close_series.rolling(window=20).std()
    lower_band = basis - (std * 2)
    
    curr, prev = close_series.iloc[-1], close_series.iloc[-2]
    lower = lower_band.iloc[-1]
    
    if prev < lower and curr > lower:
        return curr
    return None

# 5. 분석 로직 시작
if start_button:
    st.session_state.found_data = []
    
    # --- 코인 분석 ---
    if "업비트" in market:
        try:
            markets = [m for m in requests.get("https://api.upbit.com/v1/market/all").json() if m['market'].startswith('KRW-')]
            progress_bar = st.progress(0)
            status_text = st.empty()
            results_container = st.container()

            for i, m in enumerate(markets):
                prog = (i + 1) / len(markets)
                progress_bar.progress(prog)
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
        except Exception as e:
            st.error(f"업비트 데이터를 가져오는데 실패했습니다: {e}")

    # --- 주식 분석 ---
    else:
        is_kr = "국내" in market
        tickers = []
        try:
            if is_kr:
                df = fdr.StockListing('KRX')
                tickers = [row['Code'] + ('.KS' if row['Market'] == 'KOSPI' else '.KQ') for _, row in df.iterrows()]
            else:
                df_nasdaq = fdr.StockListing('NASDAQ')
                df_nyse = fdr.StockListing('NYSE')
                df = pd.concat([df_nasdaq, df_nyse])
                tickers = [t for t in df['Symbol'].dropna().unique().tolist() if str(t).isalpha()]
        except Exception as e:
            st.error(f"거래소 서버 응답 지연으로 데이터를 불러올 수 없습니다. 잠시 후 다시 시도해주세요. (에러: {e})")

        if tickers:
            inter, per = yf_time_map.get(timeframe, ("1d", "1y"))
            progress_bar = st.progress(0)
            status_text = st.empty()
            results_container = st.container()

            # 주식은 종목수가 많아 상위 300개만 우선 스캔 (속도 최적화)
            scan_limit = 300 
            for i, t in enumerate(tickers[:scan_limit]):
                prog = (i + 1) / scan_limit
                progress_bar.progress(prog)
                status_text.text(f"주식 분석 중: {i+1}/{scan_limit} ({t})")
                try:
                    data = yf.download(t, interval=inter, period=per, progress=False)
                    if data.empty or len(data) < 20: continue
                    
                    if isinstance(data.columns, pd.MultiIndex):
                        close = data['Close'][t]
                    else:
                        close = data['Close']
                    
                    if timeframe == "4시간봉":
                        close = close.resample('4H').last().dropna()

                    price = check_signal(close)
                    if price:
                        with results_container:
                            st.success(f"✅ **{t}** 신호 발생! : {price:,.2f}")
                        st.session_state.found_data.append({"시간": datetime.now().strftime('%H:%M'), "종목": t, "현재가": price})
                except: continue

# 6. 결과 출력 및 다운로드
if st.session_state.found_data:
    st.divider()
    st.subheader("📊 분석 결과 요약")
    result_df = pd.DataFrame(st.session_state.found_data)
    st.table(result_df)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        result_df.to_excel(writer, index=False, sheet_name='Scan_Results')
    processed_data = output.getvalue()
    
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(label="📥 엑셀 저장", data=processed_data, file_name="results.xlsx")
    with col2:
        csv_data = result_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(label="📥 CSV 저장", data=csv_data, file_name="results.csv")
elif 'start_button' in locals() and start_button:
    st.warning("신호가 발견되지 않았습니다.")
