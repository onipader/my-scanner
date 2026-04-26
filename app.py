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

st.title("💰 실시간 글로벌 우량주 스캐너")
st.markdown("시가총액 상위 종목을 분석합니다. 신호가 안 나온다면 **RSI 기준**을 높여보세요.")

# --- 세션 상태 초기화 ---
if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# 사이드바 설정
with st.sidebar:
    st.header("🔍 검색 설정")
    market = st.selectbox("대상 선택", ["국내주식 (KOSPI/KOSDAQ)", "미국주식 (NASDAQ/NYSE)", "업비트 코인 (원화마켓)"])
    timeframe = st.selectbox("타임프레임", ["일봉", "주봉", "4시간봉", "1시간봉"])
    
    st.divider()
    st.subheader("⚙️ 필터 세부 조절")
    top_n = st.number_input("스캔할 종목 수 (시총순)", min_value=10, max_value=2000, value=200)
    rsi_threshold = st.slider("RSI 과매도 기준", 10, 70, 32)
    use_ma200 = st.checkbox("MA200 위에서만 찾기 (매우 보수적)", value=False)
    
    start_button = st.button("🚀 스캔 시작", use_container_width=True)

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
    rs = ema_up / (ema_down + 1e-10) # 0 나누기 방지
    return 100 - (100 / (1 + rs))

def check_signal(df, symbol_name):
    if len(df) < 20: return None
    
    close = df['Close']
    # 볼린저 밴드
    basis = close.rolling(window=20).mean()
    std = close.rolling(window=20).std()
    lower_band = basis - (std * 2)
    
    # RSI & MA200
    rsi = calculate_rsi(close)
    ma200 = close.rolling(window=200).mean()
    
    curr_p, prev_p = close.iloc[-1], close.iloc[-2]
    curr_low = lower_band.iloc[-1]
    curr_rsi = rsi.iloc[-1]
    
    # 조건 검증
    is_bb_hit = prev_p < curr_low or curr_p < curr_low # 하단 돌파 혹은 터치
    is_rsi_ok = curr_rsi <= rsi_threshold
    is_ma_ok = curr_p > ma200.iloc[-1] if use_ma200 and len(df) >= 200 else True
    
    if is_bb_hit and is_rsi_ok and is_ma_ok:
        return {"price": curr_p, "rsi": curr_rsi}
    return None

if start_button:
    st.session_state.found_data = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        # 1. 종목 리스트 확보 (오류 수정 핵심 구간)
        if "국내" in market:
            df_list = fdr.StockListing('KRX')
            # 컬럼명 유연하게 대응 (MarCap 또는 시가총액)
            cap_col = 'MarCap' if 'MarCap' in df_list.columns else '시가총액'
            if cap_col in df_list.columns:
                df_list = df_list.sort_values(cap_col, ascending=False).head(top_n)
            tickers = [(row['Code'] + ('.KS' if row['Market'] == 'KOSPI' else '.KQ'), row['Name']) for _, row in df_list.iterrows()]
        
        elif "미국" in market:
            df_list = fdr.StockListing('NASDAQ') # 기본적으로 나스닥 상위
            tickers = [(row['Symbol'], row['Symbol']) for _, row in df_list.head(top_n).iterrows()]
            
        else: # 코인
            res = requests.get("https://api.upbit.com/v1/market/all").json()
            tickers = [(m['market'], m['korean_name']) for m in res if m['market'].startswith('KRW-')][:top_n]

        # 2. 개별 종목 스캔
        for i, (symbol, name) in enumerate(tickers):
            progress_bar.progress((i + 1) / len(tickers))
            status_text.text(f"분석 중: {name} ({i+1}/{len(tickers)})")
            
            try:
                if "업비트" in market:
                    unit = time_map[timeframe]
                    url = f"https://api.upbit.com/v1/candles/{'minutes/' if unit.isdigit() else ''}{unit}{'s' if not unit.isdigit() else ''}?market={symbol}&count=200"
                    data = pd.DataFrame(requests.get(url).json()).sort_values('timestamp')
                    data = data.rename(columns={'trade_price': 'Close'})
                else:
                    inter, per = yf_time_map[timeframe]
                    raw_data = yf.download(symbol, interval=inter, period=per, progress=False)
                    if raw_data.empty: continue
                    data = pd.DataFrame()
                    data['Close'] = raw_data['Close'][symbol] if isinstance(raw_data.columns, pd.MultiIndex) else raw_data['Close']

                sig = check_signal(data, name)
                if sig:
                    st.success(f"✅ **{name}** 포착! 현재가: {sig['price']:,.0f} / RSI: {sig['rsi']:.1f}")
                    st.session_state.found_data.append({"시간": datetime.now().strftime('%H:%M'), "종목": name, "현재가": sig['price'], "RSI": round(sig['rsi'],1)})
            except: continue
            
        status_text.text(f"✅ 분석 완료! 총 {len(st.session_state.found_data)}개의 종목을 찾았습니다.")

    except Exception as e:
        st.error(f"리스트 확보 실패: {e}")

# 결과 출력
if st.session_state.found_data:
    st.divider()
    res_df = pd.DataFrame(st.session_state.found_data)
    st.dataframe(res_df, use_container_width=True)
    csv = res_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 CSV 결과 저장", csv, "signals.csv", "text/csv")
