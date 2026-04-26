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

# --- 🔹 국내 주식 전 종목 리스트 가져오기 (가장 안정적인 소스) ---
@st.cache_data(ttl=3600)
def get_total_krx_list():
    # 한국거래소 전종목 리스트 (상장사 전체 포함된 경로)
    url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/krx_tickers.csv"
    try:
        df = pd.read_csv(url)
        # 시총(Marcap) 기준 내림차순 정렬
        df = df.sort_values(by='Marcap', ascending=False)
        # 티커 포맷팅 (005930.KS 등)
        df['Ticker'] = df.apply(lambda x: str(x['Symbol']).zfill(6) + ('.KS' if x['Market'] == 'KOSPI' else '.KQ'), axis=1)
        return df[['Ticker', 'Name']]
    except:
        # 실패 시 비상용 리스트
        return pd.DataFrame([["005930.KS", "삼성전자"]], columns=['Ticker', 'Name'])

# 사이드바 설정
with st.sidebar:
    st.header("🔍 검색 설정")
    market_choice = st.selectbox("대상 선택", ["국내주식 (KOSPI/KOSDAQ)", "업비트 코인 (원화마켓)"])
    top_n = st.slider("시총 순위 범위 (상위 N개)", 10, 2000, 300, 50)
    
    tf_display = ["5분봉", "1시간봉", "4시간봉", "일봉", "주봉", "월봉"]
    tf_choice = st.selectbox("타임프레임", tf_display)
    start_button = st.button("🚀 분석 시작", use_container_width=True)

# 타임프레임 매핑
yf_tf_map = {
    "5분봉": ("5m", "1d"), "1시간봉": ("60m", "1w"), "4시간봉": ("90m", "1mo"), 
    "일봉": ("1d", "1y"), "주봉": ("1wk", "2y"), "월봉": ("1mo", "5y")
}

def check_signal(df):
    if df is None or len(df) < 20: return None
    try:
        close = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
    except:
        close = df['Close']
    
    ma20 = close.rolling(window=20).mean()
    std = close.rolling(window=20).std()
    lower_band = ma20 - (std * 2)
    
    curr = close.iloc[-1]
    # 신호 민감도 조절: 하단선에 닿거나 1.5% 이내일 때 (더 잘 나오게 수정)
    if curr <= lower_band.iloc[-1] * 1.015:
        return curr
    return None

if start_button:
    st.session_state.found_data = []
    status_area = st.empty()
    progress_bar = st.progress(0)
    results_container = st.container()

    # 1. 전 종목 리스트에서 상위 N개 추출
    if "국내" in market_choice:
        total_list = get_total_krx_list()
        target_list = total_list.head(top_n).values.tolist()
    else:
        upbit_res = requests.get("https://api.upbit.com/v1/market/all").json()
        target_list = [[m['market'], m['korean_name']] for m in upbit_res if m['market'].startswith('KRW-')][:top_n]

    # 2. 분석 루프
    count = len(target_list)
    for i, (ticker, name) in enumerate(target_list):
        progress_bar.progress((i + 1) / count)
        status_area.markdown(f"🔍 **분석 중 ({i+1}/{count}):** `{name}` ({ticker})")
        
        try:
            itv, per = yf_tf_map[tf_choice]
            # 코인인 경우 티커 변환
            search_ticker = ticker.replace("KRW-", "") + "-KRW" if "업비트" in market_choice else ticker
            
            data = yf.download(search_ticker, interval=itv, period=per, progress=False, show_errors=False)
            if data.empty: continue
            
            price = check_signal(data)
            if price:
                with results_container:
                    st.success(f"✅ **{name}** 포착! ({tf_choice})")
                st.session_state.found_data.append({"시간": datetime.now().strftime('%H:%M'), "종목": name, "코드": ticker, "현재가": f"{price:,.0f}"})
            
            time.sleep(0.1) # 속도 개선
        except:
            continue

    status_area.info(f"✅ 총 {count}개 종목 스캔 완료!")

if st.session_state.found_data:
    st.table(pd.DataFrame(st.session_state.found_data))
else:
    if start_button:
        st.warning(f"현재 {tf_choice} 기준 하단 돌파 신호가 있는 종목이 없습니다. 범위를 늘려보세요!")
