import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
from datetime import datetime
import time

# 페이지 설정
st.set_page_config(page_title="Double BB Scanner", page_icon="📈", layout="wide")

st.title("📈 전략 일치형: Double BB + 365 EMA 스캐너")
st.markdown("차트에 **BUY** 표시가 있다면 무조건 찾아내도록 **'최근 신호 추적'** 로직을 적용했습니다.")

# --- 세션 상태 초기화 ---
if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# 사이드바 설정
with st.sidebar:
    st.header("🔍 전략 설정")
    market = st.selectbox("대상 선택", ["업비트 코인", "국내주식 (KRX)", "미국주식 (NASDAQ/NYSE)"])
    tf_choice = st.selectbox("타임프레임", ["월봉", "주봉", "일봉", "4시간봉", "1시간봉", "5분봉"])
    
    interval_map = {
        "5분봉": "5m", "1시간봉": "1h", "4시간봉": "4h",
        "일봉": "1d", "주봉": "1w", "월봉": "1M"
    }

    st.divider()
    top_n = st.slider("스캔 대상 (상위 N개)", 10, 1000, 250)
    
    st.divider()
    st.subheader("⚙️ 파라미터")
    std_dev_1 = st.number_input("Standard Deviation 1", value=1.0, step=0.1)
    
    st.divider()
    use_per = st.checkbox("저PER 필터 사용 (국내 전용)", value=False)
    per_limit = st.number_input("PER 기준 (이하)", value=15.0)
    
    start_button = st.button("🚀 전략 스캔 시작", use_container_width=True)

# 트레이딩뷰 지표 계산 함수 (과거 봉 추적 로직 추가)
def get_tv_strategy_data(symbol, screener, exchange, interval):
    try:
        url = f"https://scanner.tradingview.com/{screener}/scan"
        # 현재 봉(0), 직전 봉(1), 전전 봉(2) 데이터를 모두 가져옴
        payload = {
            "symbols": {"tickers": [f"{exchange}:{symbol}"], "query": {"types": []}},
            "columns": [
                "close", "sma[20]", "StdDev.20", # 현재
                "close[1]", "sma[20][1]", "StdDev.20[1]", # 1봉 전
                "close[2]", "sma[20][2]", "StdDev.20[2]", # 2봉 전
                "EMA365"
            ]
        }
        res = requests.post(url, json=payload, timeout=7).json()
        if 'data' not in res or not res['data']: return None
        
        d = res['data'][0]['d']
        
        # 데이터 정리 (현재, 1봉전, 2봉전)
        closes = [d[0], d[3], d[6]]
        basises = [d[1], d[4], d[7]]
        stddevs = [d[2], d[5], d[8]]
        ema365 = d[9]

        # 3개 봉 이내에 crossover(교차)가 있었는지 확인
        is_buy_signal = False
        signal_age = 0 # 0이면 현재봉, 1이면 직전봉...

        for i in range(2): # 0(현재)과 1(직전)을 검사하여 교차 지점 확인
            curr_c = closes[i]
            prev_c = closes[i+1]
            curr_basis = basises[i]
            curr_std = stddevs[i]
            
            if None in [curr_c, prev_c, curr_basis, curr_std]: continue
            
            # 해당 시점의 하단선
            l_band = curr_basis - (curr_std * std_dev_1)
            
            # 교차 발생 여부 (ta.crossover 로직)
            if prev_c <= l_band and curr_c > l_band:
                is_buy_signal = True
                signal_age = i
                break
            
            # 혹은 현재가가 여전히 하단선 아래에 머물러 있는 경우 (Buy Zone)
            if i == 0 and curr_c <= l_band:
                is_buy_signal = True
                signal_age = 99 # 구간 내 머무름 표시
                break

        if is_buy_signal:
            return {
                "price": closes[0],
                "ema365": ema365,
                "age": signal_age
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
        else: # 코인 (비트코인 최우선)
            res = requests.get("https://api.upbit.com/v1/market/all").json()
            raw_tickers = [m for m in res if m['market'].startswith('KRW-')]
            tickers = [("BTC", "비트코인", "UPBIT", "crypto", "N/A")] # BTC 강제 삽입
            for m in raw_tickers:
                sym = m['market'].split('-')[1]
                if sym != "BTC": tickers.append((sym, m['korean_name'], "UPBIT", "crypto", "N/A"))
            tickers = tickers[:top_n]

        # 2. 분석 실행
        total = len(tickers)
        for i, (symbol, name, exch, scr, per_val) in enumerate(tickers):
            progress_bar.progress((i + 1) / total)
            status_text.text(f"신호 추적 중: {name} ({i+1}/{total})")
            
            res = get_tv_strategy_data(symbol, scr, exch, interval_map[tf_choice])
            
            if res:
                age_msg = "현재 봉 발생" if res['age'] == 0 else ("직전 봉 발생" if res['age'] == 1 else "매수 구간 내")
                st.success(f"🎯 **{name}({symbol})** 신호 포착! ({age_msg})")
                st.session_state.found_data.append({
                    "종목": name, "심볼": symbol, "현재가": res['price'], "상태": age_msg, "PER": per_val
                })
            time.sleep(0.01)

        status_text.text(f"✅ 스캔 완료!")

    except Exception as e:
        st.error(f"오류: {e}")

if st.session_state.found_data:
    st.divider()
    st.dataframe(pd.DataFrame(st.session_state.found_data), use_container_width=True)
else:
    if start_button:
        st.warning("신호가 포착되지 않았습니다. 지표의 Standard Deviation 설정을 다시 확인해 주세요.")
