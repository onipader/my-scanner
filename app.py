import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
from datetime import datetime
import time

# 페이지 설정
st.set_page_config(page_title="Double BB Scanner", page_icon="📈", layout="wide")

st.title("📈 전략 일치형: Double BB + 365 EMA 스캐너")
st.markdown("트레이딩뷰의 **StdDev 1.0 & 2.0** 설정을 모두 반영하여 신호를 추적합니다.")

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
    # 트레이딩뷰 설정과 동일하게 두 개의 표준편차 입력
    std_dev_1 = st.number_input("Standard Deviation 1", value=1.00, step=0.1)
    std_dev_2 = st.number_input("Standard Deviation 2", value=2.00, step=0.1)
    
    st.divider()
    use_per = st.checkbox("저PER 필터 사용 (국내 전용)", value=False)
    per_limit = st.number_input("PER 기준 (이하)", value=15.0)
    
    start_button = st.button("🚀 지표 완벽 동기화 스캔 시작", use_container_width=True)

# 트레이딩뷰 지표 계산 함수 (Double BB 로직 적용)
def get_tv_double_bb_signal(symbol, screener, exchange, interval):
    try:
        url = f"https://scanner.tradingview.com/{screener}/scan"
        payload = {
            "symbols": {"tickers": [f"{exchange}:{symbol}"], "query": {"types": []}},
            "columns": ["close", "sma[20]", "StdDev.20", "close[1]", "low", "EMA365"]
        }
        res = requests.post(url, json=payload, timeout=7).json()
        if 'data' not in res or not res['data']: return None
        
        d = res['data'][0]['d']
        curr_price, basis, stddev, prev_price, curr_low, ema365 = d[0], d[1], d[2], d[3], d[4], d[5]
        
        if None in [curr_price, basis, stddev]: return None
        
        # 지표 설정값에 따른 하단선 두 개 계산
        lower_1 = basis - (stddev * std_dev_1)
        lower_2 = basis - (stddev * std_dev_2)
        
        # [신호 판정] 
        # 보통 Double BB 전략에서 BUY는 가격이 Lower 1과 Lower 2 사이에 있거나, 
        # Lower 1을 상향 돌파할 때 발생합니다.
        
        # 1. 현재가가 하단 1선 근처이거나 아래에 있음 (Buy Zone)
        is_in_zone = curr_price <= lower_1 * 1.01 # 1% 오차 허용
        
        # 2. 직전 봉에서 하단선을 터치하고 올라오는 중 (Crossover)
        is_crossover = (prev_price is not None) and (prev_price <= lower_1 and curr_price > lower_1)
        
        # 3. 캔들 저가가 하단 1선 아래로 내려갔었음 (꼬리 터치)
        is_low_hit = curr_low <= lower_1
        
        if is_in_zone or is_crossover or is_low_hit:
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
        else: # 코인 (비트코인 포함)
            res = requests.get("https://api.upbit.com/v1/market/all").json()
            raw_tickers = [m for m in res if m['market'].startswith('KRW-')]
            tickers = [("BTC", "비트코인", "UPBIT", "crypto", "N/A")]
            for m in raw_tickers:
                sym = m['market'].split('-')[1]
                if sym != "BTC": tickers.append((sym, m['korean_name'], "UPBIT", "crypto", "N/A"))
            tickers = tickers[:top_n]

        # 2. 분석 실행
        total = len(tickers)
        for i, (symbol, name, exch, scr, per_val) in enumerate(tickers):
            progress_bar.progress((i + 1) / total)
            status_text.text(f"지표 분석 중: {name}")
            
            res = get_tv_double_bb_signal(symbol, scr, exch, interval_map[tf_choice])
            
            if res:
                st.success(f"🎯 **{name}({symbol})** 신호 포착!")
                st.session_state.found_data.append({
                    "종목": name, "심볼": symbol, "현재가": res['price'], "하단1(1.0)": round(res['lower_1'], 2), "하단2(2.0)": round(res['lower_2'], 2)
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
        st.warning("신호를 찾지 못했습니다. 트레이딩뷰 지표의 파라미터가 1.00, 2.00이 맞는지 다시 확인해 주세요.")
