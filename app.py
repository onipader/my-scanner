import streamlit as st
import yfinance as yf
import pandas as pd
import time
import requests
from datetime import datetime

# 페이지 설정
st.set_page_config(page_title="글로벌 자산 스캐너", layout="wide")
st.title("💰 글로벌 주식 & 코인 매수신호 스캐너")

# --- 세션 상태 초기화 ---
if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# --- 국내 주식 시총 순위 리스트 가져오기 (고급 최적화) ---
@st.cache_data(ttl=3600)
def get_krx_market_cap_list():
    # FinanceDataReader가 관리하는 전체 종목 리스트 (시총 포함)
    url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/krx_tickers.csv"
    try:
        df = pd.read_csv(url)
        # 시가총액(Marcap) 기준 내림차순 정렬 (이게 핵심!)
        df = df.sort_values(by='Marcap', ascending=False)
        
        # yfinance 티커 형식 생성
        def make_ticker(row):
            code = str(row['Symbol']).zfill(6)
            return code + ('.KS' if row['Market'] == 'KOSPI' else '.KQ')
            
        df['Ticker'] = df.apply(make_ticker, axis=1)
        return df[['Ticker', 'Name', 'Marcap']] 
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return pd.DataFrame([["005930.KS", "삼성전자", 0]], columns=['Ticker', 'Name', 'Marcap'])

# 사이드바 설정
with st.sidebar:
    st.header("🔍 검색 설정")
    market_choice = st.selectbox("대상 선택", ["국내주식 (KOSPI/KOSDAQ)", "업비트 코인 (원화마켓)"])
    top_n = st.slider("시총 순위 범위 (상위 N개)", 10, 2000, 100, 50)
    
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
    # 최신 yfinance MultiIndex 대응
    try:
        close = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
    except:
        close = df['Close']
        
    ma20 = close.rolling(window=20).mean()
    std = close.rolling(window=20).std()
    lower_band = ma20 - (std * 2)
    
    curr = close.iloc[-1]
    # 신호 포착 기준: 현재가가 하단 밴드 근처(1% 이내)
    if curr <= lower_band.iloc[-1] * 1.01:
        return curr
    return None

if start_button:
    st.session_state.found_data = []
    status_area = st.empty()
    progress_bar = st.progress(0)
    results_container = st.container()

    # 1. 대상 리스트 확보
    if "국내" in market_choice:
        full_list = get_krx_market_cap_list()
        target_list = full_list.head(top_n).values.tolist() # [[티커, 이름, 시총], ...]
    else:
        upbit_res = requests.get("https://api.upbit.com/v1/market/all").json()
        target_list = [[m['market'], m['korean_name'], 0] for m in upbit_res if m['market'].startswith('KRW-')][:top_n]

    # 2. 분석 루프
    count = len(target_list)
    for i, (ticker, name, _) in enumerate(target_list):
        progress_bar.progress((i + 1) / count)
        status_area.markdown(f"🔍 **분석 중 ({i+1}/{count}):** `{name}` ({ticker})")
        
        try:
            if "국내" in market_choice:
                itv, per = yf_tf_map[tf_choice]
                # auto_adjust=True로 데이터 정합성 강화
                data = yf.download(ticker, interval=itv, period=per, progress=False, show_errors=False)
                if data.empty: continue
                price = check_signal(data)
            else:
                # 업비트용 별도 API 호출 로직 (생략 시 yfinance로 코인도 가능하나 API 권장)
                data = yf.download(ticker.replace("KRW-", "") + "-KRW", period="1y", progress=False)
                price = check_signal(data)
                
            if price:
                with results_container:
                    st.success(f"✅ **{name}** 신호 포착! 현재가: {price:,.0f}")
                st.session_state.found_data.append({"시간": datetime.now().strftime('%H:%M'), "종목": name, "코드": ticker, "현재가": price})
            
            # 🔹 너무 빠르면 야후에서 차단하므로 속도 조절
            time.sleep(0.3) 
        except:
            continue

    status_area.info(f"✅ 상위 {top_n}개 종목 분석 완료!")

if st.session_state.found_data:
    st.divider()
    st.subheader("📊 스캔 결과 리스트")
    st.table(pd.DataFrame(st.session_state.found_data))
