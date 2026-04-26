import streamlit as st
import yfinance as yf
import pandas as pd
import time
import requests
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="글로벌 자산 스캐너", layout="wide")
st.title("💰 글로벌 주식 & 코인 매수신호 스캐너")

# 2. 국내 주식 전체 리스트 확보 (가장 안정적인 소스 사용)
@st.cache_data(ttl=3600)
def get_total_krx():
    # KRX 종목 리스트를 실시간으로 가져오는 대체 경로
    url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/krx_tickers.csv"
    df = pd.read_csv(url)
    # 시가총액(Marcap) 기준 내림차순 정렬
    df = df.sort_values(by='Marcap', ascending=False)
    # yfinance용 티커 포맷팅
    df['Ticker'] = df.apply(lambda x: str(x['Symbol']).zfill(6) + ('.KS' if x['Market'] == 'KOSPI' else '.KQ'), axis=1)
    return df[['Ticker', 'Name']]

# 3. 사이드바 설정
with st.sidebar:
    st.header("🔍 검색 설정")
    market_choice = st.selectbox("대상 선택", ["국내주식 (KOSPI/KOSDAQ)", "업비트 코인 (원화마켓)"])
    top_n = st.slider("스캔 범위 (상위 N개)", 10, 2500, 300, 50)
    tf_display = ["5분봉", "1시간봉", "4시간봉", "일봉", "주봉", "월봉"]
    tf_choice = st.selectbox("타임프레임", tf_display)
    start_button = st.button("🚀 분석 시작", use_container_width=True)

# 4. 분석 로직
yf_tf_map = {
    "5분봉": ("5m", "1d"), "1시간봉": ("60m", "1w"), "4시간봉": ("90m", "1mo"), 
    "일봉": ("1d", "1y"), "주봉": ("1wk", "2y"), "월봉": ("1mo", "5y")
}

def check_signal(df):
    if df is None or len(df) < 20: return None
    close = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
    ma20 = close.rolling(window=20).mean()
    std = close.rolling(window=20).std()
    lower_band = ma20 - (std * 2)
    curr = close.iloc[-1]
    # 하단 밴드 1.5% 이내 근접 시 포착
    if curr <= lower_band.iloc[-1] * 1.015:
        return curr
    return None

if start_button:
    st.session_state.found_data = []
    status_area = st.empty()
    progress_bar = st.progress(0)
    results_container = st.container()

    # 대상 리스트 준비
    if "국내" in market_choice:
        total_list = get_total_krx()
        target_list = total_list.head(top_n).values.tolist()
    else:
        upbit_res = requests.get("https://api.upbit.com/v1/market/all").json()
        target_list = [[m['market'], m['korean_name']] for m in upbit_res if m['market'].startswith('KRW-')][:top_n]

    # 스캔 시작
    for i, (ticker, name) in enumerate(target_list):
        progress_bar.progress((i + 1) / len(target_list))
        status_area.markdown(f"🔍 **분석 중 ({i+1}/{len(target_list)}):** `{name}`")
        
        try:
            itv, per = yf_tf_map[tf_choice]
            search_ticker = ticker.replace("KRW-", "") + "-KRW" if "업비트" in market_choice else ticker
            data = yf.download(search_ticker, interval=itv, period=per, progress=False, show_errors=False)
            
            if data.empty: continue
            price = check_signal(data)
            
            if price:
                with results_container:
                    st.success(f"✅ **{name}** 포착! ({price:,.0f}원)")
                st.session_state.found_data.append({"시간": datetime.now().strftime('%H:%M'), "종목": name, "코드": ticker, "현재가": f"{price:,.0f}"})
            time.sleep(0.1)
        except: continue

    status_area.info(f"✅ 총 {len(target_list)}개 종목 분석 완료!")

if st.session_state.found_data:
    st.table(pd.DataFrame(st.session_state.found_data))
