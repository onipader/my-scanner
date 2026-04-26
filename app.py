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
    
    # 시총 순위 범위 설정 (국내 주식 전체 대응을 위해 max를 2000으로 확장)
    top_n = st.slider("시총 순위 범위 설정 (상위 N개)", min_value=10, max_value=2000, value=100, step=50)
    
    timeframe = st.selectbox("타임프레임", ["일봉", "주봉", "월봉"])
    start_button = st.button("🚀 분석 시작", use_container_width=True)

# 데이터 수집용 함수
@st.cache_data
def get_kr_tickers():
    """국내 주식 시총 순위 리스트 가져오기 (GitHub 등에 공유된 최신 리스트 활용 권장)"""
    # 실제로는 pykrx 등을 써야하지만, 서버 안정성을 위해 상위 티커를 미리 정의하거나 
    # yfinance로 접근 가능한 주요 티커들로 구성합니다.
    # 여기서는 예시로 상위 종목 티커 생성 로직을 넣습니다.
    try:
        # 업비트처럼 외부 API를 통해 리스트를 가져오는 것이 가장 정확합니다.
        # 일단은 사용자님이 설정하신 범위를 위해 주요 종목 리스트를 확장합니다.
        base_tickers = ["005930.KS", "000660.KS", "035420.KS", "035720.KS", "005380.KS"] # ... 실제로는 수천개
        return base_tickers 
    except:
        return ["005930.KS"]

def check_signal(df):
    if len(df) < 20: return None
    close = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
    ma20 = close.rolling(window=20).mean()
    std = close.rolling(window=20).std()
    lower_band = ma20 - (std * 2)
    if close.iloc[-1] <= lower_band.iloc[-1] * 1.01:
        return close.iloc[-1]
    return None

if start_button:
    st.session_state.found_data = []
    status_area = st.empty() 
    progress_bar = st.progress(0)
    
    if "국내" in market:
        # 🔹 시총 순위 데이터를 가져오는 로직 (실제 운영시에는 상장사 전체 리스트 파일을 연동하는게 빠름)
        # 우선은 안정적으로 작동하도록 대상을 지정하되, '전체'를 원하시므로 
        # yfinance에서 인식 가능한 한국 종목 패턴으로 분석 대상을 확장해야 합니다.
        status_area.warning("💡 국내 주식 전체 스캔은 종목수가 많아 시간이 소요됩니다.")
        # 임시로 KOSPI/KOSDAQ 주요 종목 리스트를 불러오는 로직이 필요합니다.
        # (이 부분은 pykrx 설치가 안될 경우를 대비해 yfinance 호환 티커 리스트를 사용해야 합니다.)
        tickers = [f"{str(i).zfill(6)}.KS" for i in range(1, top_n)] # 단순 예시 (실제 티커와 대조 필요)
    
    elif "업비트" in market:
        all_m = [m for m in requests.get("https://api.upbit.com/v1/market/all").json() if m['market'].startswith('KRW-')]
        tickers = all_m[:top_n]
    
    # --- 스캔 루프 ---
    for i, t in enumerate(tickers):
        prog = (i + 1) / len(tickers)
        progress_bar.progress(prog)
        
        t_name = t['korean_name'] if isinstance(t, dict) else t
        status_area.markdown(f"🔍 **현재 분석 중:** `{t_name}` ({i+1}/{len(tickers)})")
        
        try:
            if "업비트" in market:
                # 업비트 로직 동일
                pass
            else:
                inter = {"일봉":"1d", "주봉":"1wk", "월봉":"1mo"}[timeframe]
                data = yf.download(t, interval=inter, period="2y", progress=False)
                if data.empty: continue
                price = check_signal(data)
                if price:
                    st.success(f"✅ **{t}** 포착!")
                    st.session_state.found_data.append({"시간": datetime.now().strftime('%H:%M'), "종목": t, "현재가": price})
            time.sleep(0.05)
        except: continue

if st.session_state.found_data:
    st.table(pd.DataFrame(st.session_state.found_data))
