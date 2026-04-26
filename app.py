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
st.markdown("시가총액 상위 종목 중 **저평가(PER)** 및 **과매도(BB/RSI)** 종목을 분석합니다.")

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
    top_n = st.number_input("스캔할 종목 수 (시총순)", min_value=1, max_value=2000, value=100)
    
    # --- PER 필터 추가 ---
    use_per = st.checkbox("PER 필터 사용 (국내주식 전용)", value=False)
    per_limit = st.number_input("PER 기준 (이하)", min_value=0.0, max_value=100.0, value=15.0)
    
    rsi_threshold = st.slider("RSI 과매도 기준", 10, 70, 32)
    use_ma200 = st.checkbox("MA200 위에서만 찾기 (매우 보수적)", value=False)
    
    start_button = st.button("🚀 스캔 시작", use_container_width=True)

# 시간 매핑 및 RSI 계산 함수 등은 동일
time_map = {"1시간봉": "60", "4시간봉": "240", "일봉": "day", "주봉": "week"}
yf_time_map = {"1시간봉": ("60m", "1w"), "4시간봉": ("4h", "1mo"), "일봉": ("1d", "2y"), "주봉": ("1wk", "2y")}

def calculate_rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0); down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=period-1, adjust=False).mean()
    ema_down = down.ewm(com=period-1, adjust=False).mean()
    return 100 - (100 / (1 + (ema_up / (ema_down + 1e-10))))

def check_signal(df):
    if len(df) < 20: return None
    close = df['Close']
    lower_band = close.rolling(20).mean() - (close.rolling(20).std() * 2)
    rsi = calculate_rsi(close)
    
    curr_p, prev_p = close.iloc[-1], close.iloc[-2]
    curr_low, curr_rsi = lower_band.iloc[-1], rsi.iloc[-1]
    
    is_bb_hit = (prev_p < curr_low) or (curr_p < curr_low)
    is_rsi_ok = curr_rsi <= rsi_threshold
    
    if is_bb_hit and is_rsi_ok:
        return {"price": curr_p, "rsi": curr_rsi}
    return None

if start_button:
    st.session_state.found_data = []
    progress_bar = st.progress(0); status_text = st.empty()
    
    try:
        tickers = []
        if "국내" in market:
            df_list = fdr.StockListing('KRX')
            
            # 1. PER 필터 적용 (있을 경우만)
            if use_per and 'PER' in df_list.columns:
                df_list['PER'] = pd.to_numeric(df_list['PER'], errors='coerce')
                # PER이 0보다 크고 설정값보다 작은 종목만 필터링
                df_list = df_list[(df_list['PER'] > 0) & (df_list['PER'] <= per_limit)]
            
            # 2. 시총순 정렬 및 개수 제한
            cap_col = 'MarCap' if 'MarCap' in df_list.columns else '시가총액'
            df_list[cap_col] = pd.to_numeric(df_list[cap_col], errors='coerce')
            df_list = df_list.sort_values(cap_col, ascending=False).head(int(top_n))
            
            tickers = [(row['Code'] + ('.KS' if row['Market'] == 'KOSPI' else '.KQ'), row['Name'], row.get('PER', 'N/A')) for _, row in df_list.iterrows()]
        
        elif "미국" in market:
            df_list = fdr.StockListing('NASDAQ').head(int(top_n))
            tickers = [(row['Symbol'], row['Symbol'], 'N/A') for _, row in df_list.iterrows()]
        else: # 코인
            res = requests.get("https://api.upbit.com/v1/market/all").json()
            tickers = [(m['market'], m['korean_name'], 'N/A') for m in res if m['market'].startswith('KRW-')][:int(top_n)]

        # 2. 분석 실행
        for i, (symbol, name, per_val) in enumerate(tickers):
            progress_bar.progress((i + 1) / len(tickers))
            status_text.text(f"분석 중: {name} (PER: {per_val}) - {i+1}/{len(tickers)}")
            
            try:
                if "업비트" in market:
                    unit = time_map[timeframe]
                    url = f"https://api.upbit.com/v1/candles/{'minutes/' if unit.isdigit() else ''}{unit}{'s' if not unit.isdigit() else ''}?market={symbol}&count=200"
                    data = pd.DataFrame(requests.get(url).json()).sort_values('timestamp').rename(columns={'trade_price': 'Close'})
                else:
                    inter, per_str = yf_time_map[timeframe]
                    raw_data = yf.download(symbol, interval=inter, period=per_str, progress=False)
                    data = pd.DataFrame()
                    data['Close'] = raw_data['Close'][symbol] if isinstance(raw_data.columns, pd.MultiIndex) else raw_data['Close']

                sig = check_signal(data)
                if sig:
                    st.success(f"✅ **{name}** 포착! PER: {per_val} / 현재가: {sig['price']:,.0f}")
                    st.session_state.found_data.append({
                        "시간": datetime.now().strftime('%H:%M'),
                        "종목": name,
                        "현재가": sig['price'],
                        "RSI": round(sig['rsi'], 1),
                        "PER": per_val
                    })
            except: continue
            
        status_text.text(f"✅ 분석 완료! ({len(tickers)}개 종목 스캔)")

    except Exception as e:
        st.error(f"오류 발생: {e}")

# 결과 출력
if st.session_state.found_data:
    st.divider()
    res_df = pd.DataFrame(st.session_state.found_data)
    st.dataframe(res_df, use_container_width=True)
    st.download_button("📥 결과 저장", res_df.to_csv(index=False).encode('utf-8-sig'), "signals.csv", "text/csv")
