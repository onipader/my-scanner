import streamlit as st
import yfinance as yf
import pandas as pd
import time
import requests
from datetime import datetime

# 페이지 설정
st.set_page_config(page_title="글로벌 자산 스캐너", layout="wide")
st.title("💰 글로벌 주식 & 코인 매수신호 스캐너")

# 🔹 국내 주식 시총 순위 리스트 가져오기 함수 (안정적인 API 사용)
@st.cache_data(ttl=3600) # 1시간 동안 리스트 캐싱
def get_krx_stock_list():
    # 시총 순위 데이터를 제공하는 오픈 API나 깃허브 정제 데이터를 활용합니다.
    # 여기서는 가장 범용적인 방식인 정제된 리스트를 사용합니다.
    url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/krx_tickers.csv"
    try:
        df = pd.read_csv(url)
        # 시가총액(Marcap) 순으로 정렬되어 있다고 가정하거나 정렬 로직 추가
        # yfinance용 티커 포맷으로 변경 (코스피 .KS, 코스닥 .KQ)
        df['Ticker'] = df.apply(lambda x: x['Symbol'] + ('.KS' if x['Market'] == 'KOSPI' else '.KQ'), axis=1)
        return df[['Ticker', 'Name']] # 티커와 종목명 반환
    except:
        return pd.DataFrame([["005930.KS", "삼성전자"]], columns=['Ticker', 'Name'])

# 사이드바 설정
with st.sidebar:
    st.header("🔍 검색 설정")
    market = st.selectbox("대상 선택", ["국내주식 (KOSPI/KOSDAQ)", "업비트 코인 (원화마켓)"])
    top_n = st.slider("시총 순위 범위 (상위 N개)", 10, 2000, 100, 50)
    
    # 타임프레임 옵션
    tf_display = ["5분봉", "1시간봉", "4시간봉", "일봉", "주봉", "월봉"]
    tf_choice = st.selectbox("타임프레임", tf_display)
    start_button = st.button("🚀 분석 시작")

# 타임프레임 설정 매핑
yf_tf_map = {
    "5분봉": ("5m", "1d"), "1시간봉": ("60m", "1w"), "4시간봉": ("90m", "1mo"), # 4시간은 90m 대용
    "일봉": ("1d", "1y"), "주봉": ("1wk", "2y"), "월봉": ("1mo", "5y")
}

def check_signal(df):
    if len(df) < 20: return None
    close = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
    ma20 = close.rolling(window=20).mean()
    std = close.rolling(window=20).std()
    lower_band = ma20 - (std * 2)
    curr = close.iloc[-1]
    if curr <= lower_band.iloc[-1] * 1.005: # 하단선 0.5% 이내 근접 시
        return curr
    return None

if start_button:
    st.session_state.found_data = []
    status_area = st.empty()
    progress_bar = st.progress(0)
    results_container = st.container()

    # 1. 대상 리스트 확보
    if "국내" in market:
        stock_df = get_krx_stock_list()
        target_list = stock_df.head(top_n).values.tolist() # [[티커, 이름], ...]
    else:
        # 업비트 리스트
        upbit_list = requests.get("https://api.upbit.com/v1/market/all").json()
        target_list = [[m['market'], m['korean_name']] for m in upbit_list if m['market'].startswith('KRW-')][:top_n]

    # 2. 루프 시작
    for i, (ticker, name) in enumerate(target_list):
        progress_bar.progress((i + 1) / len(target_list))
        status_area.markdown(f"🔍 **분석 중:** `{name}` ({ticker}) - {i+1}/{len(target_list)}")
        
        try:
            if "국내" in market:
                itv, per = yf_tf_map[tf_choice]
                data = yf.download(ticker, interval=itv, period=per, progress=False)
                if data.empty: continue
                price = check_signal(data)
            else:
                # 업비트 캔들 조회 로직 (생략 - 이전과 동일)
                price = None # 예시용
                
            if price:
                with results_container:
                    st.success(f"✅ **{name}** 포착! 현재가: {price:,.0f}")
                st.session_state.found_data.append({"시간": datetime.now().strftime('%H:%M'), "종목": name, "코드": ticker, "현재가": price})
            
            # API 부하 방지를 위한 미세 지연 (필수!)
            time.sleep(0.2) 
        except:
            continue

    status_area.info("✅ 분석이 완료되었습니다!")

if st.session_state.found_data:
    st.write("### 📢 매수 신호 발생 종목")
    st.table(pd.DataFrame(st.session_state.found_data))
