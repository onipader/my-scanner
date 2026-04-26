import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
import time

# 페이지 설정
st.set_page_config(page_title="Double BB Scanner", page_icon="📈", layout="wide")

st.title("📈 Pine Script 동기화: Double BB 스캐너")
st.markdown("""
**차트와 동일한 로직 적용:**
* **BUY:** 직전 봉 종가가 하단1선 이하이고, 현재 종가가 하단1선을 돌파할 때 (`ta.crossover`)
* **지표 기준:** SMA 20, StdDev 1.0 / 2.0, EMA 365
""")

# --- 세션 상태 초기화 ---
if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# 사이드바 설정
with st.sidebar:
    st.header("🔍 전략 설정")
    market = st.selectbox("대상 선택", ["업비트 코인", "국내주식 (KRX)", "미국주식 (NASDAQ/NYSE)"])
    tf_choice = st.selectbox("타임프레임", ["월봉", "주봉", "일봉", "4시간봉", "1시간봉"])
    
    interval_map = {
        "1시간봉": "60", "4시간봉": "240", "일봉": "", "주봉": "1W", "월봉": "1M"
    }

    st.divider()
    top_n = st.number_input("스캔 대상 개수", value=250, min_value=10)
    
    st.subheader("⚙️ 지표 파라미터 (Pine Script 기준)")
    length = 20
    sd1 = st.number_input("Standard Deviation 1", value=1.0)
    sd2 = st.number_input("Standard Deviation 2", value=2.0)
    
    start_button = st.button("🚀 차트 신호 동기화 스캔 시작", use_container_width=True)

# 트레이딩뷰 ta.crossover 로직 구현
def get_pine_signal(symbol, screener, exchange, interval):
    try:
        url = f"https://scanner.tradingview.com/{screener}/scan"
        # 현재 봉(0)과 직전 봉(1) 데이터를 요청
        payload = {
            "symbols": {"tickers": [f"{exchange}:{symbol}"], "query": {"types": []}},
            "columns": [
                "close", "sma[20]", "StdDev.20", "EMA365",       # 현재 봉
                "close[1]", "sma[20][1]", "StdDev.20[1]"        # 직전 봉
            ]
        }
        res = requests.post(url, json=payload, timeout=7).json()
        if 'data' not in res or not res['data']: return None
        
        d = res['data'][0]['d']
        curr_c, curr_ma, curr_sd, ema365 = d[0], d[1], d[2], d[3]
        prev_c, prev_ma, prev_sd = d[4], d[5], d[6]

        if None in [curr_c, curr_ma, curr_sd, prev_c, prev_ma, prev_sd]: return None

        # 밴드 계산 (Pine Script와 동일)
        curr_l1 = curr_ma - (curr_sd * sd1)
        prev_l1 = prev_ma - (prev_sd * sd1)

        # 🔹 ta.crossover(close, lower_band_1) 구현
        # 조건: 이전 봉은 밴드 아래(<=), 현재 봉은 밴드 위(>)
        is_long = (prev_c <= prev_l1) and (curr_c > curr_l1)
        
        if is_long:
            return {
                "price": curr_c,
                "l1": curr_l1,
                "ema": ema365
            }
        return None
    except:
        return None

if start_button:
    st.session_state.found_data = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    # 1. 대상 리스트업
    try:
        if "업비트" in market:
            res = requests.get("https://api.upbit.com/v1/market/all").json()
            tickers = [("BTC", "비트코인", "UPBIT", "crypto")] # BTC 최우선
            for m in res:
                if m['market'].startswith('KRW-') and m['market'] != 'KRW-BTC':
                    tickers.append((m['market'].split('-')[1], m['korean_name'], "UPBIT", "crypto"))
        elif "국내" in market:
            df = fdr.StockListing('KRX')
            tickers = [(row['Code'], row['Name'], "KRX", "korea") for _, row in df.head(top_n).iterrows()]
        else:
            df = fdr.StockListing('NASDAQ')
            tickers = [(row['Symbol'], row['Symbol'], "NASDAQ", "america") for _, row in df.head(top_n).iterrows()]

        # 2. 스캔 실행
        total = len(tickers[:top_n])
        for i, (sym, name, exch, scr) in enumerate(tickers[:top_n]):
            progress_bar.progress((i + 1) / total)
            status_text.text(f"Pine Script 로직 분석 중: {name} ({sym})")
            
            res = get_pine_signal(sym, scr, exch, interval_map[tf_choice])
            if res:
                st.success(f"🎯 **{name}({sym})** BUY 신호 발생!")
                st.session_state.found_data.append({
                    "종목": name, "심볼": sym, "현재가": res['price'], "하단1선": round(res['l1'], 2), "365EMA": round(res['ema'], 1) if res['ema'] else "N/A"
                })
            time.sleep(0.01)

        status_text.text("✅ 스캔 완료!")

    except Exception as e:
        st.error(f"오류: {e}")

if st.session_state.found_data:
    st.divider()
    st.table(pd.DataFrame(st.session_state.found_data))
else:
    if start_button:
        st.warning("현재 캔들에서 ta.crossover 조건이 만족된 종목이 없습니다.")
