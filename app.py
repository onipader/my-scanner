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

# --- 세션 상태 초기화 (데이터 유지용) ---
if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# 사이드바 설정
with st.sidebar:
    st.header("🔍 검색 설정")
    market = st.selectbox("대상 선택", ["국내주식 (KOSPI/KOSDAQ)", "미국주식 (NASDAQ/NYSE)", "업비트 코인 (원화마켓)"])
    timeframe = st.selectbox("타임프레임", ["5분봉", "1시간봉", "4시간봉", "일봉", "주봉", "월봉"])
    start_button = st.button("🚀 분석 시작", use_container_width=True)

# --- 시간 매핑 설정 (수정된 부분) ---
time_map = {
    "5분봉": "5", 
    "1시간봉": "60", 
    "4시간봉": "240", 
    "일봉": "day", 
    "주봉": "week", 
    "월봉": "month"
}

# yf_time_map의 중복을 제거하고 4시간봉을 추가했습니다.
yf_time_map = {
    "5분봉": ("5m", "1d"), 
    "1시간봉": ("1h", "2y"), 
    "4시간봉": ("1h", "2y"), # yf는 4h를 공식지원하지 않는 경우가 많아 1h로 가져온 뒤 리샘플링하거나 긴 기간을 확보합니다.
    "일봉": ("1d", "2y"), 
    "주봉": ("1wk", "max"), 
    "월봉": ("1mo", "max")
}

def get_upbit_candles(market, unit):
    """업비트 전용 데이터 수집 함수"""
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
    """공통 매수 신호 계산기 (볼린저 밴드 하단 돌파 후 회복)"""
    if len(close_series) < 20: return None
    
    # 볼린저 밴드 계산
    basis = close_series.rolling(window=20).mean()
    std = close_series.rolling(window=20).std()
    lower_band = basis - (std * 2)
    
    # 신호 포착 로직 (종가가 밴드 하단을 아래에서 위로 돌파할 때)
    curr, prev = close_series.iloc[-1], close_series.iloc[-2]
    lower = lower_band.iloc[-1]
    
    if prev < lower and curr > lower:
        return curr
    return None

# --- 분석 로직 시작 ---
if start_button:
    st.session_state.found_data = [] # 새로운 분석 시 기존 데이터 초기화
    
    if "업비트" in market:
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
                        st.success(f"✅ **{m['korean_name']}** ({m['market']}) 포착! : {price:,.0f}원")
                    st.session_state.found_data.append({"시간": datetime.now().strftime('%H:%M'), "종목": m['korean_name'], "현재가": price})
                time.sleep(0.05) # Rate Limit 방지
            except: continue
            
    else:
        is_kr = "국내" in market
        if is_kr:
            df = fdr.StockListing('KRX')
            tickers = [row['Code'] + ('.KS' if row['Market'] == 'KOSPI' else '.KQ') for _, row in df.iterrows()]
        else:
            # 미국 주식의 경우 데이터량이 방대하므로 샘플링하거나 상위 종목 위주로 구성하는 것이 좋으나 원본 유지
            df_nasdaq = fdr.StockListing('NASDAQ')
            df_nyse = fdr.StockListing('NYSE')
            df = pd.concat([df_nasdaq, df_nyse])
            tickers = [t for t in df['Symbol'].dropna().unique().tolist() if str(t).isalpha()]

        # KeyError 방지를 위해 .get() 사용
        inter, per = yf_time_map.get(timeframe, ("1d", "1y"))
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        results_container = st.container()

        # 분석 속도를 위해 전체 티커 중 일부만 예시로 수행하거나 루프 최적화 필요 (여기선 원본 로직 유지)
        for i, t in enumerate(tickers[:500]): # 속도 문제로 상위 500개 우선 분석 예시
            prog = (i + 1) / 500
            progress_bar.progress(prog)
            status_text.text(f"주식 분석 중: {i+1}/500 ({t})")
            try:
                data = yf.download(t, interval=inter, period=per, progress=False)
                if data.empty or len(data) < 20: continue
                
                # Multi-index 및 다양한 데이터 구조 대응
                if isinstance(data.columns, pd.MultiIndex):
                    close = data['Close'][t]
                else:
                    close = data['Close']
                
                # 4시간봉의 경우 1시간봉 데이터를 합쳐서 계산 (옵션)
                if timeframe == "4시간봉":
                    close = close.resample('4H').last().dropna()

                price = check_signal(close)
                if price:
                    with results_container:
                        st.success(f"✅ **{t}** 신호 발생! : {price:,.2f}")
                    st.session_state.found_data.append({"시간": datetime.now().strftime('%H:%M'), "종목": t, "현재가": price})
            except: continue

# --- 결과 출력 및 다운로드 영역 ---
if st.session_state.found_data:
    st.divider()
    st.subheader("📊 분석 결과 요약")
    result_df = pd.DataFrame(st.session_state.found_data)
    st.table(result_df)
    
    # 엑셀 다운로드
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        result_df.to_excel(writer, index=False, sheet_name='Scan_Results')
    processed_data = output.getvalue()
    
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="📥 엑셀 파일로 저장 (.xlsx)",
            data=processed_data,
            file_name=f"scanner_{datetime.now().strftime('%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    with col2:
        csv_data = result_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 CSV 파일로 저장 (.csv)",
            data=csv_data,
            file_name=f"scanner_{datetime.now().strftime('%m%d_%H%M')}.csv",
            mime="text/csv"
        )
elif start_button:
    st.warning("신호가 발견되지 않았습니다.")
