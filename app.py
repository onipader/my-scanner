import streamlit as st
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

if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# --- 🔍 리스트 수집 함수 (안정성 강화) ---
@st.cache_data(ttl=3600)
def get_stock_list(market_type):
    """안정적인 경로를 통해 주식 리스트 확보"""
    try:
        if "국내" in market_type:
            url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/krx_tickers.csv"
            df = pd.read_csv(url)
            df = df.sort_values('Marcap', ascending=False) # 시총순
            df['Symbol'] = df.apply(lambda x: str(x['Symbol']).zfill(6) + ('.KS' if x['Market'] == 'KOSPI' else '.KQ'), axis=1)
            return df[['Symbol', 'Name']].head(300) # 상위 300개로 제한하여 차단 방지
        else:
            # 미국 상위 100개 (안정성을 위해 직접 지정 또는 라이브러리 활용)
            us_top_tickers = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL", "AMZN", "META", "BRK-B", "UNH", "V", "JPM", "JNJ", "WMT", "MA", "PG", "AVGO", "HD", "ORCL", "COST", "CVX"]
            return pd.DataFrame({"Symbol": us_top_tickers, "Name": us_top_tickers})
    except:
        return pd.DataFrame([["005930.KS", "삼성전자"]], columns=['Symbol', 'Name'])

def get_upbit_candles(market, unit):
    if unit in ['month', 'week', 'day']:
        url = f"https://api.upbit.com/v1/candles/{unit}s?market={market}&count=100"
    else:
        url = f"https://api.upbit.com/v1/candles/minutes/{unit}?market={market}&count=100"
    res = requests.get(url).json()
    df = pd.DataFrame(res).sort_values('timestamp')
    return df['trade_price']

def check_signal(close_series):
    if len(close_series) < 20: return None
    basis = close_series.rolling(window=20).mean()
    std = close_series.rolling(window=20).std()
    lower_band = basis - (std * 2)
    
    curr, prev = close_series.iloc[-1], close_series.iloc[-2]
    lower = lower_band.iloc[-1]
    
    # 🔹 사용자님의 로직: 하단 돌파 후 회복 신호
    if prev < lower_band.iloc[-2] and curr > lower:
        return curr
    return None

# --- 사이드바 설정 ---
with st.sidebar:
    st.header("🔍 검색 설정")
    market = st.selectbox("대상 선택", ["국내주식 (KOSPI/KOSDAQ)", "미국주식 (TOP 20)", "업비트 코인 (원화마켓)"])
    timeframe = st.selectbox("타임프레임", ["5분봉", "1시간봉", "일봉", "주봉", "월봉"])
    start_button = st.button("🚀 분석 시작", use_container_width=True)

time_map = {"5분봉":"5", "1시간봉":"60", "일봉":"day", "주봉":"week", "월봉":"month"}
yf_time_map = {"5분봉":("5m","1d"), "1시간봉":("60m","1w"), "일봉":("1d","1y"), "주봉":("1wk","2y"), "월봉":("1mo","5y")}

# --- 분석 로직 시작 ---
if start_button:
    st.session_state.found_data = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    results_container = st.container()

    if "업비트" in market:
        markets = [m for m in requests.get("https://api.upbit.com/v1/market/all").json() if m['market'].startswith('KRW-')]
        for i, m in enumerate(markets):
            progress_bar.progress((i + 1) / len(markets))
            status_text.text(f"코인 스캔 중: {m['korean_name']} ({i+1}/{len(markets)})")
            try:
                prices = get_upbit_candles(m['market'], time_map[timeframe])
                price = check_signal(prices)
                if price:
                    with results_container:
                        st.success(f"✅ **{m['korean_name']}** 포착! : {price:,.0f}원")
                    st.session_state.found_data.append({"시간": datetime.now().strftime('%H:%M'), "종목": m['korean_name'], "현재가": price})
                time.sleep(0.1)
            except: continue
    else:
        # 주식 로직
        df_list = get_stock_list(market)
        tickers = df_list['Symbol'].tolist()
        names = df_list['Name'].tolist()
        inter, per = yf_time_map[timeframe]

        for i, t in enumerate(tickers):
            progress_bar.progress((i + 1) / len(tickers))
            status_text.text(f"주식 스캔 중: {names[i]} ({i+1}/{len(tickers)})")
            try:
                data = yf.download(t, interval=inter, period=per, progress=False, show_errors=False)
                if data.empty: continue
                
                # Multi-index 대응 및 데이터 추출
                if isinstance(data['Close'], pd.DataFrame):
                    close = data['Close'].iloc[:, 0]
                else:
                    close = data['Close']
                
                price = check_signal(close)
                if price:
                    with results_container:
                        st.success(f"✅ **{names[i]}** ({t}) 신호 발생! : {price:,.2f}")
                    st.session_state.found_data.append({"시간": datetime.now().strftime('%H:%M'), "종목": names[i], "현재가": price})
                time.sleep(0.1)
            except: continue

# --- 결과 출력 및 다운로드 ---
if st.session_state.found_data:
    st.divider()
    st.subheader("📊 분석 결과 요약")
    result_df = pd.DataFrame(st.session_state.found_data)
    st.table(result_df)
    
    # 엑셀/CSV 다운로드
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        result_df.to_excel(writer, index=False, sheet_name='Results')
    
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("📥 엑셀 저장", data=output.getvalue(), file_name="scan.xlsx")
    with col2:
        st.download_button("📥 CSV 저장", data=result_df.to_csv(index=False).encode('utf-8-sig'), file_name="scan.csv")
elif start_button:
    st.warning("분석 결과 신호가 발견되지 않았습니다.")
