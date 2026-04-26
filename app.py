import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
import time

st.set_page_config(page_title="Double BB Scanner", layout="wide")

st.title("📈 Double BB (Pine 완전복제 버전)")

if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# ---------------- 설정 ----------------
with st.sidebar:
    tf_choice = st.selectbox("타임프레임", ["월봉", "주봉", "일봉"])

    interval_map = {
        "일봉": "",
        "주봉": "1W",
        "월봉": "1M"
    }

    lookback = st.slider("최근 몇 개 봉까지 추적", 1, 50, 12)

    start_button = st.button("🚀 스캔 시작")

# ---------------- 핵심 함수 ----------------
def get_tv_pine_signal(symbol, screener, exchange, interval):
    try:
        url = f"https://scanner.tradingview.com/{screener}/scan"

        columns = []
        for i in range(lookback + 1):
            columns.extend([
                f"close[{i}]",
                f"sma[20][{i}]",
                f"StdDev.20[{i}]"
            ])

        payload = {
            "symbols": {
                "tickers": [f"{exchange}:{symbol}"],
                "query": {"types": []}
            },
            "columns": columns,
            "interval": interval
        }

        res = requests.post(url, json=payload, timeout=10).json()

        if 'data' not in res or not res['data']:
            return None

        d = res['data'][0]['d']

        # -------- Pine Script crossover 복제 --------
        for i in range(lookback):
            close_now = d[i*3]
            ma = d[i*3+1]
            sd = d[i*3+2]

            close_prev = d[(i+1)*3]

            if None in [close_now, ma, sd, close_prev]:
                continue

            lower = ma - sd * 1.0

            # Pine Script crossover 동일
            if close_prev <= lower and close_now > lower:
                return {
                    "price": d[0],
                    "signal": f"{i}봉 전 BUY 발생"
                }

        return None

    except:
        return None

# ---------------- 실행 ----------------
if start_button:
    st.session_state.found_data = []

    res = requests.get("https://api.upbit.com/v1/market/all").json()
    raw = [m for m in res if m['market'].startswith('KRW-')]

    tickers = [("BTCKRW", "비트코인", "UPBIT", "crypto")]

    for m in raw:
        sym = m['market'].replace("KRW-", "")
        if sym != "BTC":
            tickers.append((f"{sym}KRW", m['korean_name'], "UPBIT", "crypto"))

    total = len(tickers)

    for i, (symbol, name, exch, scr) in enumerate(tickers):
        result = get_tv_pine_signal(
            symbol,
            scr,
            exch,
            interval_map[tf_choice]
        )

        if result:
            st.success(f"🎯 {name} → {result['signal']}")

            st.session_state.found_data.append({
                "종목": name,
                "가격": result['price'],
                "신호": result['signal']
            })

        time.sleep(0.01)

    st.write(f"총 {len(st.session_state.found_data)}개 발견")

# ---------------- 결과 ----------------
if st.session_state.found_data:
    st.dataframe(pd.DataFrame(st.session_state.found_data))
