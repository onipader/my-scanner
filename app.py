import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
import time
import requests
from datetime import datetime
import io

# 페이지 설정
st.set_page_config(page_title="글로벌 우량주 스캐너", page_icon="💰", layout="wide")

st.title("💰 실시간 글로벌 우량주 & 저PER 스캐너")
st.markdown("전 세계 주식과 코인을 분석합니다. **데이터가 안 나온다면 필터(PER, RSI)를 완화해 보세요.**")

# --- 세션 상태 초기화 ---
if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# 사이드바 설정
with st.sidebar:
    st.header("🔍 검색 설정")
    market = st.selectbox("대상 선택", ["국내주식 (KOSPI/KOSDAQ)", "미국주식 (NASDAQ/NYSE)", "업비트 코인 (원화마켓)"])
    timeframe = st.selectbox("타임프레임", ["5분봉", "1시간봉", "4시간봉", "일봉", "주봉", "월봉"])
    
    st.divider()
    st.subheader("⚙️ 필터 세부 조절")
    top_n = st.number_input("스캔할 종목 수 (시총순)", min_value=1, max_value=2000, value=100)
    
    use_per = st.checkbox("PER 필터 사용 (국내 전용)", value=True)
    per_limit = st.number_input("PER 기준 (이하)", min_value=0.0, max_value=100.0, value=15.0)
    
    rsi_threshold = st.slider("RSI 과매도 기준", 10, 70, 35)
    use_ma200 = st.checkbox("MA200 위에서만 찾기 (매우 보수적)", value=False)
    
    start_button = st.button("🚀 스캔 시작", use_container_width=True)

# --- 시간 매핑 설정 ---
upbit_time_map = {"5분봉": "5", "1시간봉": "60", "4시간봉": "240", "일봉": "days", "주봉": "weeks", "월봉": "months"}
yf_time_map = {
    "5분봉": ("5m", "1d"), "1시간봉": ("60m", "1w"), "4시간봉": ("4h", "1mo"),
    "일봉": ("1d", "2y"), "주봉": ("1wk", "5y"), "월봉": ("1mo", "max")
}

def calculate_rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0); down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=period-1, adjust=False).mean()
    ema_down = down.ewm(com=period-1, adjust=False).mean()
    rs = ema_up / (ema_down + 1e-10)
    return 100 - (100 / (1 + rs))

def check_signal(df):
    if df is None or len(df) < 20: return None
    close = df['Close']
    
    basis = close.rolling(window=20).mean()
    std = close.rolling(window=20).std()
    lower_band = basis - (std * 2)
    rsi = calculate_rsi(close)
    
    curr_p, prev_p = close.iloc[-1], close.iloc[-2]
    curr_low, curr_rsi = lower_band.iloc[-1], rsi.iloc[-1]
    
    # 볼린저 밴드 하단 돌파/터치 조건
    is_bb_hit = (prev_p < curr_low) or (curr_p < curr_low)
    is_rsi_ok = curr_rsi <= rsi_threshold
    
    # MA200 필터
    if use_ma200:
        if len(df) < 200: return None
        ma200 = close.rolling(200).mean().iloc[-1]
        if curr_p < ma200: return None
    
    if is_bb_hit and is_rsi_ok:
        return {"price": curr_p, "rsi": curr_rsi}
    return None

# --- 분석 로직 ---
if start_button:
    st.session_state.found_data = []
    progress_bar = st.progress(0); status_text = st.empty()
    
    try:
        # 1. 종목 리스트 확보
        with st.spinner("종목 리스트를 불러오는 중..."):
            if "국내" in market:
                df_list = fdr.StockListing('KRX')
                cap_col = next((c for c in ['MarCap', '시가총액'] if c in df_list.columns), None)
                df_list[cap_col] = pd.to_numeric(df_list[cap_col], errors='coerce')
                
                if use_per and 'PER' in df_list.columns:
                    df_list['PER'] = pd.to_numeric(df_list['PER'], errors='coerce')
                    df_list = df_list[(df_list['PER'] > 0) & (df_list['PER'] <= per_limit)]
                
                df_list = df_list.sort_values(cap_col, ascending=False).head(int(top_n))
                tickers = [(row['Code'] + ('.KS' if row['Market'] == 'KOSPI' else '.KQ'), row['Name'], row.get('PER', 'N/A')) for _, row in df_list.iterrows()]
            
            elif "미국" in market:
                df_list = fdr.StockListing('NASDAQ').head(int(top_n))
                tickers = [(row['Symbol'], row['Symbol'], 'N/A') for _, row in df_list.iterrows()]
            
            else: # 업비트
                res = requests.get("https://api.upbit.com/v1/market/all").json()
                raw_coins = [m for m in res if m['market'].startswith('KRW-')]
                tickers = [(m['market'], m['korean_name'], 'N/A') for m in raw_coins[:int(top_n)]]

        if not tickers:
            st.warning("스캔할 종목이 없습니다. 필터(PER 등)를 완화해 보세요.")
        else:
            # 2. 개별 종목 분석
            for i, (symbol, name, per_val) in enumerate(tickers):
                progress_bar.progress((i + 1) / len(tickers))
                status_text.text(f"분석 중: {name} ({i+1}/{len(tickers)})")
                
                try:
                    if "업비트" in market:
                        unit = upbit_time_map[timeframe]
                        url = f"https://api.upbit.com/v1/candles/{'minutes/' if unit.isdigit() else ''}{unit[:-1] if not unit.isdigit() else unit}?market={symbol}&count=200"
                        df = pd.DataFrame(requests.get(url).json()).sort_values('timestamp').rename(columns={'trade_price': 'Close'})
                    else:
                        inter, per_str = yf_time_map[timeframe]
                        raw_data = yf.download(symbol, interval=inter, period=per_str, progress=False)
                        if raw_data.empty: continue
                        
                        df = pd.DataFrame()
                        # Multi-index 대응
                        target_col = 'Close'
                        if isinstance(raw_data.columns, pd.MultiIndex):
                            df['Close'] = raw_data[target_col][symbol]
                        else:
                            df['Close'] = raw_data[target_col]
                    
                    sig = check_signal(df)
                    if sig:
                        st.success(f"✅ **{name}** 포착! (RSI: {sig['rsi']:.1f})")
                        st.session_state.found_data.append({
                            "시간": datetime.now().strftime('%H:%M'),
                            "종목": name, "현재가": sig['price'],
                            "RSI": round(sig['rsi'], 1), "PER": per_val
                        })
                except Exception as e:
                    continue # 개별 종목 오류는 무시하고 진행
            
            status_text.text(f"✅ {timeframe} 스캔 완료! 총 {len(st.session_state.found_data)}개 발견")

    except Exception as e:
        st.error(f"오류 발생: {e}")

# 결과 출력
if st.session_state.found_data:
    st.divider()
    res_df = pd.DataFrame(st.session_state.found_data)
    st.dataframe(res_df, use_container_width=True)
elif start_button:
    st.info("조건에 맞는 종목이 발견되지 않았습니다. 필터를 조정해 보세요.")
