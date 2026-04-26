import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
import time
import requests
from datetime import datetime

# 페이지 설정
st.set_page_config(page_title="글로벌 우량주 스캐너", page_icon="💰", layout="wide")

st.title("💰 글로벌 우량주 매수신호 스캐너")
st.markdown("시가총액 상위 종목 중 **볼린저 밴드 하단 돌파 + RSI 과매도** 종목을 찾습니다.")

# --- 세션 상태 초기화 ---
if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# 사이드바 설정
with st.sidebar:
    st.header("🔍 검색 설정")
    market = st.selectbox("대상 선택", ["국내주식 (KOSPI/KOSDAQ)", "미국주식 (S&P 500 등)", "업비트 코인 (원화마켓)"])
    timeframe = st.selectbox("타임프레임", ["일봉", "주봉", "4시간봉", "1시간봉"])
    
    st.divider()
    st.subheader("⚙️ 필터 옵션")
    top_n = st.slider("시가총액 순위 제한", 100, 500, 300)
    use_rsi = st.checkbox("RSI 과매도 필터 (35 이하)", value=True)
    use_ma200 = st.checkbox("MA200 추세 필터 (우상향)", value=False)
    
    start_button = st.button("🚀 분석 시작", use_container_width=True)

# 시간 매핑
time_map = {"1시간봉": "60", "4시간봉": "240", "일봉": "day", "주봉": "week"}
yf_time_map = {
    "1시간봉": ("60m", "1w"), "4시간봉": ("4h", "1mo"),
    "일봉": ("1d", "2y"), "주봉": ("1wk", "2y")
}

def calculate_rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=period-1, adjust=False).mean()
    ema_down = down.ewm(com=period-1, adjust=False).mean()
    rs = ema_up / ema_down
    return 100 - (100 / (1 + rs))

def check_signal(df):
    if df is None or len(df) < 20: return None
    
    # 데이터 구조 정규화
    if isinstance(df.columns, pd.MultiIndex):
        close = df['Close'].iloc[:, 0]
    else:
        close = df['Close']
    
    close = close.dropna()
    if len(close) < 20: return None

    # 지표 계산
    basis = close.rolling(window=20).mean()
    std = close.rolling(window=20).std()
    lower_band = basis - (std * 2)
    rsi = calculate_rsi(close)
    ma200 = close.rolling(window=200).mean() if len(close) >= 200 else None
    
    curr_price = float(close.iloc[-1])
    prev_price = float(close.iloc[-2])
    curr_lower = float(lower_band.iloc[-1])
    curr_rsi = float(rsi.iloc[-1])
    
    # 조건 검증
    is_bb_low = prev_price < curr_lower and curr_price > curr_lower
    is_rsi_low = curr_rsi < 35 if use_rsi else True
    is_trend_up = (curr_price > ma200.iloc[-1]) if (use_ma200 and ma200 is not None) else True

    if is_bb_low and is_rsi_low and is_trend_up:
        return {"price": curr_price, "rsi": curr_rsi}
    return None

# --- 분석 로직 ---
if start_button:
    st.session_state.found_data = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    if "업비트" in market:
        # 업비트는 시가총액 순 정보를 제공하지 않으므로 거래대금 상위 위주로 스캔 가능 (여기선 전체 KRW 마켓)
        markets = requests.get("https://api.upbit.com/v1/market/all").json()
        krw_markets = [m for m in markets if m['market'].startswith('KRW-')]
        
        for i, m in enumerate(krw_markets):
            progress_bar.progress((i + 1) / len(krw_markets))
            status_text.text(f"코인 분석 중: {m['korean_name']}")
            try:
                unit = time_map[timeframe]
                url = f"https://api.upbit.com/v1/candles/{'minutes/' if timeframe in ['1시간봉','4시간봉'] else ''}{unit}{'s' if timeframe in ['일봉','주봉'] else ''}?market={m['market']}&count=200"
                res = requests.get(url).json()
                temp_df = pd.DataFrame(res).sort_values('timestamp').rename(columns={'trade_price': 'Close'})
                
                res_signal = check_signal(temp_df)
                if res_signal:
                    st.session_state.found_data.append({"종목": m['korean_name'], "가격": res_signal['price'], "RSI": round(res_signal['rsi'], 2)})
                time.sleep(0.05)
            except: continue
            
    else:
        # 주식 시장별 우량주 필터링
        try:
            if "국내" in market:
                # KOSPI/KOSDAQ 종목 리스트를 가져와 시가총액 순으로 정렬
                df_krx = fdr.StockListing('KRX')
                # 시가총액(MarCap) 기준 내림차순 정렬 후 상위 N개 선택
                df_krx = df_krx.sort_values(by='MarCap', ascending=False).head(top_n)
                tickers_raw = [[row['Code'], row['Market'], row['Name']] for _, row in df_krx.iterrows()]
            else:
                # 미국 시장은 S&P 500 종목 리스트 사용 (우량주 집합)
                df_sp500 = fdr.StockListing('S&P500')
                tickers_raw = [[row['Symbol'], 'US', row['Name']] for _, row in df_sp500.head(top_n).iterrows()]
        except:
            st.error("종목 리스트를 가져오는 데 실패했습니다.")
            tickers_raw = []

        inter, per = yf_time_map[timeframe]
        for i, (code, mkt, name) in enumerate(tickers_raw):
            progress_bar.progress((i + 1) / len(tickers_raw))
            status_text.text(f"분석 중: {name}")
            try:
                symbol = (code + ('.KS' if mkt == 'KOSPI' else '.KQ')) if "국내" in market else code
                data = yf.download(symbol, interval=inter, period=per, progress=False)
                
                if data.empty: continue
                
                # 동전주 필터 (국내 1000원 미만, 미국 1달러 미만 제외)
                last_p = data['Close'].iloc[-1]
                if ("국내" in market and last_p < 1000) or ("미국" in market and last_p < 1): continue

                res_signal = check_signal(data)
                if res_signal:
                    st.success(f"✅ **{name}** 포착!")
                    st.session_state.found_data.append({"종목": f"{name}({symbol})", "가격": res_signal['price'], "RSI": round(res_signal['rsi'], 2)})
            except: continue

# --- 결과 출력 ---
if st.session_state.found_data:
    st.divider()
    st.subheader(f"📊 분석 완료 (포착: {len(st.session_state.found_data)}개)")
    st.table(pd.DataFrame(st.session_state.found_data))
elif start_button:
    st.warning("조건에 맞는 우량주가 없습니다.")
