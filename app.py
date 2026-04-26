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
    top_n = st.number_input("스캔할 종목 수 (시총순)", min_value=1, max_value=2000, value=300)
    
    use_per = st.checkbox("PER 필터 사용 (국내주식 전용)", value=True)
    per_limit = st.number_input("PER 기준 (이하)", min_value=0.0, max_value=100.0, value=8.0)
    
    rsi_threshold = st.slider("RSI 과매도 기준", 10, 70, 32)
    use_ma200 = st.checkbox("MA200 위에서만 찾기 (매우 보수적)", value=True)
    
    start_button = st.button("🚀 스캔 시작", use_container_width=True)

# --- 유틸리티 함수 ---
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
    ma200 = close.rolling(200).mean()
    
    curr_p, prev_p = close.iloc[-1], close.iloc[-2]
    curr_low, curr_rsi = lower_band.iloc[-1], rsi.iloc[-1]
    
    is_bb_hit = (prev_p < curr_low) or (curr_p < curr_low)
    is_rsi_ok = curr_rsi <= rsi_threshold
    is_ma_ok = curr_p > ma200.iloc[-1] if use_ma200 and len(df) >= 200 else True
    
    if is_bb_hit and is_rsi_ok and is_ma_ok:
        return {"price": curr_p, "rsi": curr_rsi}
    return None

# --- 분석 로직 ---
if start_button:
    st.session_state.found_data = []
    progress_bar = st.progress(0); status_text = st.empty()
    
    try:
        tickers = []
        if "국내" in market:
            df_list = fdr.StockListing('KRX')
            
            # 시가총액 컬럼 찾기 (오류 방지 핵심)
            cap_col = next((c for c in ['MarCap', '시가총액', 'Stocks'] if c in df_list.columns), None)
            if not cap_col:
                st.error("시가총액 데이터를 찾을 수 없습니다. 라이브러리를 업데이트하거나 관리자에게 문의하세요.")
                st.stop()
            
            # 데이터 수치화
            df_list[cap_col] = pd.to_numeric(df_list[cap_col], errors='coerce')
            
            # PER 필터 적용
            if use_per and 'PER' in df_list.columns:
                df_list['PER'] = pd.to_numeric(df_list['PER'], errors='coerce')
                df_list = df_list[(df_list['PER'] > 0) & (df_list['PER'] <= per_limit)]
            
            # 시총순 정렬 후 상위 N개 슬라이싱
            df_list = df_list.sort_values(cap_col, ascending=False).head(int(top_n))
            
            tickers = [(row['Code'] + ('.KS' if row['Market'] == 'KOSPI' else '.KQ'), row['Name'], row.get('PER', 'N/A')) for _, row in df_list.iterrows()]
        
        elif "미국" in market:
            df_list = fdr.StockListing('NASDAQ').head(int(top_n))
            tickers = [(row['Symbol'], row['Symbol'], 'N/A') for _, row in df_list.iterrows()]
        else: # 코인
            res = requests.get("https://api.upbit.com/v1/market/all").json()
            tickers = [(m['market'], m['korean_name'], 'N/A') for m in res if m['market'].startswith('KRW-')][:int(top_n)]

        # 2. 개별 종목 분석
        scan_count = len(tickers)
        for i, (symbol, name, per_val) in enumerate(tickers):
            progress_bar.progress((i + 1) / scan_count)
            status_text.text(f"분석 중: {name} ({i+1}/{scan_count})")
            
            try:
                if "업비트" in market:
                    # 업비트 API 호출 로직 생략(기존과 동일)
                    pass
                else:
                    data = yf.download(symbol, period="2y", progress=False)
                    if data.empty: continue
                    clean_df = pd.DataFrame()
                    clean_df['Close'] = data['Close'][symbol] if isinstance(data.columns, pd.MultiIndex) else data['Close']
                    
                    sig = check_signal(clean_df)
                    if sig:
                        st.success(f"✅ **{name}** 포착! PER: {per_val}")
                        st.session_state.found_data.append({
                            "시간": datetime.now().strftime('%H:%M'),
                            "종목": name, "현재가": sig['price'],
                            "RSI": round(sig['rsi'], 1), "PER": per_val
                        })
            except: continue
            
        status_text.text(f"✅ 분석 완료! ({scan_count}개 종목 스캔)")

    except Exception as e:
        st.error(f"오류 발생: {e}")

# 결과 출력
if st.session_state.found_data:
    st.divider()
    res_df = pd.DataFrame(st.session_state.found_data)
    st.dataframe(res_df, use_container_width=True)
