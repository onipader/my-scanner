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

st.title("💰 글로벌 주식 & 코인 매수신호 스캐너 (업그레이드)")
st.markdown("전 세계 주식과 코인을 분석하여 **볼린저 밴드 하단 + RSI 과매도 + MA200 추세**를 동시에 만족하는 종목을 찾습니다.")

# --- 세션 상태 초기화 ---
if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# 사이드바 설정
with st.sidebar:
    st.header("🔍 검색 설정")
    market = st.selectbox("대상 선택", ["국내주식 (KOSPI/KOSDAQ)", "미국주식 (NASDAQ/NYSE)", "업비트 코인 (원화마켓)"])
    timeframe = st.selectbox("타임프레임", ["5분봉", "1시간봉", "4시간봉", "일봉", "주봉", "월봉"])
    
    st.divider()
    st.subheader("⚙️ 필터 옵션")
    use_rsi = st.checkbox("RSI 과매도 필터 (35 이하)", value=True)
    use_ma200 = st.checkbox("MA200 추세 필터 (장기 우상향)", value=False)
    
    start_button = st.button("🚀 분석 시작", use_container_width=True)

# 시간 매핑
time_map = {"5분봉": "5", "1시간봉": "60", "4시간봉": "240", "일봉": "day", "주봉": "week", "월봉": "month"}
yf_time_map = {
    "5분봉": ("5m", "1d"), "1시간봉": ("60m", "1w"), "4시간봉": ("4h", "1mo"),
    "일봉": ("1d", "2y"), "주봉": ("1wk", "2y"), "월봉": ("1mo", "5y")
}

def calculate_rsi(series, period=14):
    """RSI 계산 함수"""
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=period-1, adjust=False).mean()
    ema_down = down.ewm(com=period-1, adjust=False).mean()
    rs = ema_up / ema_down
    return 100 - (100 / (1 + rs))

def check_signal(df):
    """업그레이드된 매수 신호 계산기"""
    if len(df) < 200: return None # 이평선 계산을 위해 충분한 데이터 필요
    
    close = df['Close']
    
    # 1. 볼린저 밴드 계산
    basis = close.rolling(window=20).mean()
    std = close.rolling(window=20).std()
    lower_band = basis - (std * 2)
    
    # 2. RSI 계산
    rsi = calculate_rsi(close)
    
    # 3. MA200 계산
    ma200 = close.rolling(window=200).mean()
    
    curr_price = close.iloc[-1]
    prev_price = close.iloc[-2]
    curr_lower = lower_band.iloc[-1]
    curr_rsi = rsi.iloc[-1]
    curr_ma200 = ma200.iloc[-1]
    
    # --- 조건 검증 ---
    # 조건 A: 볼린저 하단 돌파 (어제는 하단 아래, 오늘은 위로 복귀 또는 하단 터치)
    is_bb_low = prev_price < curr_lower and curr_price > curr_lower
    
    # 조건 B: RSI 필터 (RSI가 35 이하인 침체 구간인지)
    is_rsi_low = curr_rsi < 35 if use_rsi else True
    
    # 조건 C: 추세 필터 (현재가가 200일선 위에 있는 우상향 종목인지)
    is_trend_up = curr_price > curr_ma200 if use_ma200 else True
    
    if is_bb_low and is_rsi_low and is_trend_up:
        return {"price": curr_price, "rsi": curr_rsi}
    return None

# --- 분석 로직 ---
if start_button:
    st.session_state.found_data = []
    
    if "업비트" in market:
        markets = [m for m in requests.get("https://api.upbit.com/v1/market/all").json() if m['market'].startswith('KRW-')]
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, m in enumerate(markets):
            progress_bar.progress((i + 1) / len(markets))
            status_text.text(f"코인 분석 중: {i+1}/{len(markets)} ({m['korean_name']})")
            try:
                unit = time_map[timeframe]
                if unit in ['month', 'week', 'day']:
                    url = f"https://api.upbit.com/v1/candles/{unit}s?market={m['market']}&count=200"
                else:
                    url = f"https://api.upbit.com/v1/candles/minutes/{unit}?market={m['market']}&count=200"
                
                res = requests.get(url).json()
                temp_df = pd.DataFrame(res).sort_values('timestamp')
                temp_df = temp_df.rename(columns={'trade_price': 'Close'})
                
                res_signal = check_signal(temp_df)
                if res_signal:
                    st.success(f"✅ **{m['korean_name']}** 포착! 가격: {res_signal['price']:,.0f}원 / RSI: {res_signal['rsi']:.1f}")
                    st.session_state.found_data.append({
                        "시간": datetime.now().strftime('%H:%M'),
                        "종목": m['korean_name'],
                        "현재가": res_signal['price'],
                        "RSI": round(res_signal['rsi'], 2)
                    })
                time.sleep(0.05)
            except: continue
            
    else:
        is_kr = "국내" in market
        if is_kr:
           try:
    kospi = fdr.StockListing('KOSPI')
    kosdaq = fdr.StockListing('KOSDAQ')
    stock_list = pd.concat([kospi, kosdaq])
    tickers = [row['Code'] + ('.KS' if row['Market'] == 'KOSPI' else '.KQ') for _, row in stock_list.iterrows()]
except Exception as e:
    st.error(f"종목 리스트를 불러오는 중 오류가 발생했습니다: {e}")
    tickers = [] # 리스트를 비워 다음 단계에서 에러 방지
        else:
            stock_list = pd.concat([fdr.StockListing('NASDAQ'), fdr.StockListing('NYSE')])
            tickers = stock_list['Symbol'].dropna().unique().tolist()

        inter, per = yf_time_map[timeframe]
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, t in enumerate(tickers):
            progress_bar.progress((i + 1) / len(tickers))
            status_text.text(f"주식 분석 중: {i+1}/{len(tickers)} ({t})")
            try:
                data = yf.download(t, interval=inter, period=per, progress=False)
                if len(data) < 20: continue
                
                # Multi-index 처리
                clean_df = pd.DataFrame()
                clean_df['Close'] = data['Close'][t] if isinstance(data.columns, pd.MultiIndex) else data['Close']
                
                res_signal = check_signal(clean_df)
                if res_signal:
                    st.success(f"✅ **{t}** 신호! 가격: {res_signal['price']:,.2f} / RSI: {res_signal['rsi']:.1f}")
                    st.session_state.found_data.append({
                        "시간": datetime.now().strftime('%H:%M'),
                        "종목": t,
                        "현재가": res_signal['price'],
                        "RSI": round(res_signal['rsi'], 2)
                    })
            except: continue

# --- 결과 출력 ---
if st.session_state.found_data:
    st.divider()
    st.subheader("📊 분석 결과 요약")
    result_df = pd.DataFrame(st.session_state.found_data)
    st.dataframe(result_df, use_container_width=True) # table 대신 dataframe 사용 (정렬 가능)
    
    # 다운로드 로직 (엑셀/CSV) 생략 (기존 코드와 동일)
    csv_data = result_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 결과 다운로드 (CSV)", csv_data, f"signal_{datetime.now().strftime('%m%d_%H%M')}.csv", "text/csv")
elif start_button:
    st.warning("신호가 발견되지 않았습니다. 필터 조건을 완화해 보세요.")
