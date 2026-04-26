import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
import time
import requests
from datetime import datetime

# 페이지 설정
st.set_page_config(page_title="글로벌 우량주 스캐너", page_icon="💰", layout="wide")

st.title("💰 실시간 글로벌 우량주 스캐너")
st.markdown("시가총액 상위 종목을 실시간으로 분석합니다. 신호가 안 나온다면 **RSI 기준**을 높여보세요.")

# --- 세션 상태 초기화 ---
if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# 사이드바 설정
with st.sidebar:
    st.header("🔍 검색 설정")
    market = st.selectbox("대상 선택", ["국내주식 (KOSPI/KOSDAQ)", "미국주식 (S&P 500)", "업비트 코인"])
    timeframe = st.selectbox("타임프레임", ["일봉", "주봉", "4시간봉", "1시간봉"], index=0)
    
    st.divider()
    st.subheader("⚙️ 필터 세부 조절")
    top_n = st.number_input("스캔할 종목 수 (시총순)", 50, 500, 200)
    rsi_threshold = st.slider("RSI 과매도 기준", 20, 50, 40)
    use_ma200 = st.checkbox("MA200 위에서만 찾기 (매우 보수적)", value=False)
    
    start_button = st.button("🚀 스캔 시작", use_container_width=True)

# 시간 매핑
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
    if df is None or len(df) < 25: return None
    
    # 데이터 정리
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
    
    curr_price = float(close.iloc[-1])
    prev_price = float(close.iloc[-2])
    curr_lower = float(lower_band.iloc[-1])
    curr_rsi = float(rsi.iloc[-1])
    
    # 핵심 조건 (볼린저 하단 근처 혹은 돌파)
    # 1. 현재가가 볼린저 하단보다 낮거나, 막 상향돌파 시도 중일 때
    is_bb_low = curr_price <= curr_lower * 1.01  # 하단 터치 포함 (1% 오차범위)
    
    # 2. RSI 필터
    is_rsi_low = curr_rsi <= rsi_threshold
    
    # 3. MA200 (선택)
    is_trend_up = True
    if use_ma200 and len(close) >= 200:
        ma200 = close.rolling(window=200).mean().iloc[-1]
        is_trend_up = curr_price > ma200

    if is_bb_low and is_rsi_low and is_trend_up:
        return {"price": curr_price, "rsi": curr_rsi, "bb_lower": curr_lower}
    return None

# --- 분석 로직 ---
if start_button:
    st.session_state.found_data = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    log_text = st.empty() # 현재 작업 로그 표시용
    
    # 1. 종목 리스트 확보
    with st.spinner("종목 리스트를 불러오는 중..."):
        try:
            if "국내" in market:
                df_krx = fdr.StockListing('KRX')
                # 시총 기준 정렬 (MarCap 컬럼명 확인 필수)
                target_list = df_krx.sort_values('MarCap', ascending=False).head(top_n)
                tickers = [[row['Code'], row['Market'], row['Name']] for _, row in target_list.iterrows()]
            elif "미국" in market:
                df_sp500 = fdr.StockListing('S&P500')
                target_list = df_sp500.head(top_n)
                tickers = [[row['Symbol'], 'US', row['Name']] for _, row in target_list.iterrows()]
            else: # 업비트
                coins = requests.get("https://api.upbit.com/v1/market/all").json()
                tickers = [[c['market'], 'KRW', c['korean_name']] for c in coins if c['market'].startswith('KRW-')]
                tickers = tickers[:top_n]
        except Exception as e:
            st.error(f"리스트 확보 실패: {e}")
            tickers = []

    # 2. 개별 종목 분석
    found_count = 0
    for i, (code, mkt, name) in enumerate(tickers):
        progress_bar.progress((i + 1) / len(tickers))
        log_text.write(f"🔍 분석 중: **{name}** ({code})")
        
        try:
            if "업비트" in market:
                unit = "days" if timeframe == "일봉" else "weeks" if timeframe == "주봉" else "minutes/240" if timeframe == "4시간봉" else "minutes/60"
                url = f"https://api.upbit.com/v1/candles/{unit}?market={code}&count=200"
                res = requests.get(url).json()
                data = pd.DataFrame(res).sort_values('timestamp').rename(columns={'trade_price': 'Close'})
            else:
                symbol = (code + ('.KS' if mkt == 'KOSPI' else '.KQ')) if "국내" in market else code
                inter, per = yf_time_map[timeframe]
                data = yf.download(symbol, interval=inter, period=per, progress=False)
            
            signal = check_signal(data)
            if signal:
                found_count += 1
                st.toast(f"📍 {name} 포착!", icon="✅")
                st.session_state.found_data.append({
                    "종목명": name,
                    "현재가": f"{signal['price']:,.0f}" if "국내" in market or "업비트" in market else f"{signal['price']:.2f}",
                    "RSI": round(signal['rsi'], 1),
                    "BB하단": round(signal['bb_lower'], 1)
                })
            
            # API 과부하 방지 (매우 중요)
            if i % 10 == 0: time.sleep(0.1)
            
        except:
            continue

    status_text.success(f"✅ 분석 완료! 총 {found_count}개의 종목을 찾았습니다.")
    log_text.empty()

# --- 결과 출력 ---
if st.session_state.found_data:
    st.divider()
    df_res = pd.DataFrame(st.session_state.found_data)
    st.dataframe(df_res, use_container_width=True)
    
    csv = df_res.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 결과 다운로드 (CSV)", csv, "signals.csv", "text/csv")
elif start_button:
    st.warning("선택하신 조건(RSI, MA200 등)을 만족하는 우량주가 현재 시장에 없습니다. 사이드바에서 RSI 기준을 높여보세요.")
