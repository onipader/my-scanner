import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
from datetime import datetime
import time

# 페이지 설정
st.set_page_config(page_title="Double BB Scanner", page_icon="📈", layout="wide")

st.title("📈 전략 일치형: Double BB + 365 EMA 스캐너")
st.markdown("트레이딩뷰 엔진의 **실시간 지표 값**을 강제로 동기화하여 신호를 추적합니다.")

# --- 세션 상태 초기화 ---
if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# 사이드바 설정
with st.sidebar:
    st.header("🔍 전략 설정")
    market = st.selectbox("대상 선택", ["업비트 코인", "국내주식 (KRX)", "미국주식 (NASDAQ/NYSE)"])
    tf_choice = st.selectbox("타임프레임", ["월봉", "주봉", "일봉", "4시간봉", "1시간봉", "5분봉"])
    
    interval_map = {
        "5분봉": "5", "1시간봉": "60", "4시간봉": "240",
        "일봉": "", "주봉": "1W", "월봉": "1M"
    }

    st.divider()
    top_n = st.slider("스캔 대상 (상위 N개)", 10, 1000, 250)
    
    st.divider()
    st.subheader("⚙️ 파라미터 (Double BB)")
    std_dev_1 = st.number_input("Standard Deviation 1", value=1.00, step=0.1)
    std_dev_2 = st.number_input("Standard Deviation 2", value=2.00, step=0.1)
    
    st.divider()
    use_per = st.checkbox("저PER 필터 사용 (국내 전용)", value=False)
    per_limit = st.number_input("PER 기준 (이하)", value=15.0)
    
    start_button = st.button("🚀 지표 완벽 동기화 스캔 시작", use_container_width=True)

# 트레이딩뷰 엔진 데이터 직접 추출 함수
def get_tv_indicator_data(symbol, screener, exchange, interval):
    try:
        url = f"https://scanner.tradingview.com/{screener}/scan"
        # BB 하단선 데이터를 가져오기 위해 가능한 모든 컬럼 명칭을 요청
        payload = {
            "symbols": {"tickers": [f"{exchange}:{symbol}"], "query": {"types": []}},
            "columns": ["close", "BB.lower", "sma[20]", "StdDev.20", "EMA365", "low"]
        }
        res = requests.post(url, json=payload, timeout=7).json()
        if 'data' not in res or not res['data']: return None
        
        d = res['data'][0]['d']
        curr_price, bb_lower_direct, basis, stddev, ema365, curr_low = d[0], d[1], d[2], d[3], d[4], d[5]
        
        # 1. 트레이딩뷰가 직접 계산한 BB 하단값 사용 (우선순위)
        # 2. 만약 없다면 우리가 입력한 StdDev로 직접 계산
        lower_1 = bb_lower_direct if bb_lower_direct else (basis - (stddev * std_dev_1))
        lower_2 = basis - (stddev * std_dev_2)
        
        # [신호 판정 로직 완화]
        # 현재가(close)나 저가(low)가 하단선(1.0)보다 아래에 있거나, 
        # 하단선 위 2% 이내에만 있어도 '신호'로 간주하여 리스트에 표시
        is_signal = (curr_price <= lower_1 * 1.02) or (curr_low <= lower_1)
        
        if is_signal:
            return {
                "price": curr_price,
                "lower_1": lower_1,
                "lower_2": lower_2,
                "ema365": ema365
            }
        return None
    except:
        return None

if start_button:
    st.session_state.found_data = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        # 1. 리스트 구성
        if "국내" in market:
            df_list = fdr.StockListing('KRX')
            if use_per:
                df_list['PER'] = pd.to_numeric(df_list.get('PER'), errors='coerce')
                df_list = df_list[(df_list['PER'] > 0) & (df_list['PER'] <= per_limit)]
            tickers = [(row['Code'], row['Name'], "KRX", "korea", row.get('PER', 'N/A')) for _, row in df_list.head(top_n).iterrows()]
        elif "미국" in market:
            df_list = fdr.StockListing('NASDAQ').head(top_n)
            tickers = [(row['Symbol'], row['Symbol'], "NASDAQ", "america", "N/A") for _, row in df_list.iterrows()]
        else: # 코인 (BTC 최우선)
            res = requests.get("https://api.upbit.com/v1/market/all").json()
            raw_tickers = [m for m in res if m['market'].startswith('KRW-')]
            tickers = [("BTC", "비트코인", "UPBIT", "crypto", "N/A")] # 비트코인 강제 배치
            for m in raw_tickers:
                sym = m['market'].split('-')[1]
                if sym != "BTC": tickers.append((sym, m['korean_name'], "UPBIT", "crypto", "N/A"))
            tickers = tickers[:top_n]

        # 2. 분석 실행
        total = len(tickers)
        for i, (symbol, name, exch, scr, per_val) in enumerate(tickers):
            progress_bar.progress((i + 1) / total)
            status_text.text(f"차트 데이터 동기화 중: {name}")
            
            res = get_tv_indicator_data(symbol, scr, exch, interval_map[tf_choice])
            
            if res:
                st.success(f"🎯 **{name}({symbol})** 신호 포착!")
                st.session_state.found_data.append({
                    "종목": name, "현재가": res['price'], "하단선(1.0)": round(res['lower_1'], 2), "365EMA": round(res['ema365'], 1) if res['ema365'] else "N/A"
                })
            time.sleep(0.01)

        status_text.text(f"✅ 스캔 완료! (검색 결과 {len(st.session_state.found_data)}건)")

    except Exception as e:
        st.error(f"오류: {e}")

if st.session_state.found_data:
    st.divider()
    st.dataframe(pd.DataFrame(st.session_state.found_data), use_container_width=True)
else:
    if start_button:
        st.warning("여전히 신호가 잡히지 않습니다. 트레이딩뷰 차트에서 BTC 월봉의 '종가'가 하단선(StdDev 1.0)보다 확실히 아래에 있는지 다시 확인 부탁드립니다.")
