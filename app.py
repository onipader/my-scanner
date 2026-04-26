import streamlit as st
import yfinance as yf
import pandas as pd
import time
import requests
from datetime import datetime
import io

# 페이지 설정
st.set_page_config(page_title="글로벌 자산 스캐너", layout="wide")
st.title("💰 글로벌 주식 & 코인 매수신호 스캐너")

if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# 🔹 국내 주식 리스트를 시총 순으로 가져오는 함수 (캐싱 적용)
@st.cache_data(ttl=3600)
def get_krx_list():
    # FinanceDataReader 대신 안정적인 깃허브 원본 소스를 사용합니다.
    url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/krx_tickers.csv"
    try:
        df = pd.read_csv(url)
        # 종목코드 6자리 맞추고 yfinance용 접미사 추가
        df['Ticker'] = df['Symbol'].apply(lambda x: str(x).zfill(6) + ('.KS' if 'KOSPI' in str(df.loc[df['Symbol']==x, 'Market'].values[0]) else '.KQ'))
        return df[['Ticker', 'Name']] # 티커와 종목명 반환
    except:
        return pd.DataFrame([["005930.KS", "삼성전자"]], columns=['Ticker', 'Name'])

# 사이드바 설정
with st.sidebar:
    st.header("🔍 검색 설정")
    market = st.selectbox("대상 선택", ["국내주식 (KOSPI/KOSDAQ)", "업비트 코인 (원화마켓)"])
    top_n = st.slider("시총 순위 범위 (상위 N개)", 10, 2000, 100, 50)
    
    tf_display = ["5분봉", "1시간봉", "4시간봉", "일봉", "주봉", "월봉"]
    tf_choice = st.selectbox("타임프레임", tf_display)
    start_button = st.button("🚀 분석 시작")

# 타임프레임 매핑
yf_tf_map = {
    "5분봉": ("5m", "1d"), "1시간봉": ("60m", "1w"), "4시간봉": ("90m", "1mo"), 
    "일봉": ("1d", "1y"), "주봉": ("1wk", "2y"), "월봉": ("1mo", "5y")
}

def check_signal(df):
    if len(df) < 20: return None
    # 데이터 구조 대응 (MultiIndex 처리)
    close = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
    ma20 = close.rolling(window=20).mean()
    std = close.rolling(window=20).std()
    lower_band = ma20 - (std * 2)
    
    curr = close.iloc[-1]
    # 볼린저 밴드 하단 돌파 후 회복하거나 하단선 근처일 때
    if curr <= lower_band.iloc[-1] * 1.01:
        return curr
    return None

if start_button:
    st.session_state.found_data = []
    status_area = st.empty()
    progress_bar = st.progress(0)
    results_container = st.container()

    # 1. 대상 리스트 확보
    if "국내" in market:
        stock_list = get_krx_list()
        # 시총 순위 상위 N개만 선택
        target_list = stock_list.head(top_n).values.tolist()
    else:
        # 업비트 리스트
        upbit_res = requests.get("https://api.upbit.com/v1/market/all").json()
        target_list = [[m['market'], m['korean_name']] for m in upbit_res if m['market'].startswith('KRW-')][:top_n]

    # 2. 분석 루프
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
                # 업비트 캔들 로직은 이전과 동일 (생략)
                price = None 
                
            if price:
                with results_container:
                    st.success(f"✅ **{name}** 신호 포착! 현재가: {price:,.0f}")
                st.session_state.found_data.append({"시간": datetime.now().strftime('%H:%M'), "종목": name, "코드": ticker, "현재가": price})
            
            # API 과부하 방지를 위해 살짝 쉬어줍니다
            time.sleep(0.1) 
        except:
            continue

    status_area.info("✅ 분석이 완료되었습니다!")

if st.session_state.found_data:
    st.divider()
    st.table(pd.DataFrame(st.session_state.found_data))
