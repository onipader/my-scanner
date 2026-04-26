import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
import time

# ---------------- 기본 설정 ----------------
st.set_page_config(page_title="Double BB Scanner", page_icon="📈", layout="wide")

st.title("📈 Double BB + EMA365 스캐너 (확장 버전)")
st.markdown("현재 BUY 상태 + 과거 BUY 신호 모두 탐지")

if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# ---------------- 사이드바 ----------------
with st.sidebar:
    st.header("🔍 설정")

    market = st.selectbox("시장", [
        "업비트 코인",
        "국내주식",
        "미국주식"
    ])

    tf_choice = st.selectbox("타임프레임", [
        "월봉", "주봉", "일봉", "4시간봉", "1시간봉", "5분봉"
    ])

    interval_map = {
        "5분봉": "5",
        "1시간봉": "60",
        "4시간봉": "240",
        "일봉": "",
        "주봉": "1W",
        "월봉": "1M"
    }

    mode = st.selectbox("현재 신호 방식", [
        "현재 BUY 상태",
        "최근 교차"
    ])

    st.divider()

    lookback = st.slider("과거 몇 봉까지 추적", 1, 50, 12)
    use_history = st.checkbox("과거 BUY 신호 포함", value=True)

    st.divider()

    std_dev_1 = st.number_input("BB 1σ", value=1.0)
    std_dev_2 = st.number_input("BB 2σ", value=2.0)

    use_strong = st.checkbox("2σ만 사용", value=False)
    use_ema = st.checkbox("EMA365 필터", value=False)

    st.divider()

    top_n = st.slider("스캔 개수", 10, 500, 150)

    start_button = st.button("🚀 스캔 시작", use_container_width=True)

# ---------------- 현재 상태 탐지 ----------------
def get_tv_signal(symbol, screener, exchange, interval):
    try:
        url = f"https://scanner.tradingview.com/{screener}/scan"

        columns = [
            "close",
            "sma[20]",
            "StdDev.20",
            "EMA365",
            "close[1]"
        ]

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

        close = d[0]
        ma = d[1]
        sd = d[2]
        ema365 = d[3]
        prev_close = d[4]

        if None in [close, ma, sd]:
            return None

        l1 = ma - (sd * std_dev_1)
        l2 = ma - (sd * std_dev_2)

        tolerance = 1.02

        if use_strong:
            buy_now = close <= l2 * tolerance
        else:
            buy_now = close <= l1 * tolerance

        if use_ema and ema365:
            if close < ema365:
                buy_now = False

        cross = False
        if prev_close and prev_close <= l1 and close > l1:
            cross = True

        if mode == "현재 BUY 상태":
            if buy_now:
                return {
                    "price": close,
                    "signal": "BUY 유지",
                    "ema": ema365
                }

        elif mode == "최근 교차":
            if cross:
                return {
                    "price": close,
                    "signal": "최근 교차",
                    "ema": ema365
                }

        return None

    except:
        return None

# ---------------- 과거 Pine Script BUY 탐지 ----------------
def get_tv_pine_history(symbol, screener, exchange, interval, lookback):
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

        for i in range(lookback):
            close_now = d[i*3]
            ma = d[i*3+1]
            sd = d[i*3+2]
            close_prev = d[(i+1)*3]

            if None in [close_now, ma, sd, close_prev]:
                continue

            lower = ma - (sd * std_dev_1)

            # Pine Script crossover 그대로 복제
            if close_prev <= lower and close_now > lower:
                return f"{i}봉 전 BUY 발생"

        return None

    except:
        return None

# ---------------- 실행 ----------------
if start_button:
    st.session_state.found_data = []

    progress = st.progress(0)
    status = st.empty()

    try:
        # 종목 리스트
        if "국내" in market:
            df = fdr.StockListing('KRX')
            tickers = [(row['Code'], row['Name'], "KRX", "korea") for _, row in df.head(top_n).iterrows()]

        elif "미국" in market:
            df = fdr.StockListing('NASDAQ').head(top_n)
            tickers = [(row['Symbol'], row['Symbol'], "NASDAQ", "america") for _, row in df.iterrows()]

        else:
            res = requests.get("https://api.upbit.com/v1/market/all").json()
            raw = [m for m in res if m['market'].startswith('KRW-')]

            tickers = [("BTCKRW", "비트코인", "UPBIT", "crypto")]

            for m in raw:
                sym = m['market'].replace("KRW-", "")
                if sym != "BTC":
                    tickers.append((f"{sym}KRW", m['korean_name'], "UPBIT", "crypto"))

            tickers = tickers[:top_n]

        # 분석 루프
        total = len(tickers)

        for i, (symbol, name, exch, scr) in enumerate(tickers):
            progress.progress((i + 1) / total)
            status.text(f"분석중: {name}")

            result = get_tv_signal(symbol, scr, exch, interval_map[tf_choice])

            history_signal = None
            if use_history:
                history_signal = get_tv_pine_history(
                    symbol, scr, exch, interval_map[tf_choice], lookback
                )

            if result:
                signal_text = result['signal']
                price = result['price']
                ema_val = result['ema']

            elif history_signal:
                signal_text = history_signal
                price = "N/A"
                ema_val = None

            else:
                continue

            st.success(f"🎯 {name} → {signal_text}")

            st.session_state.found_data.append({
                "종목": name,
                "가격": price,
                "신호": signal_text,
                "EMA365": round(ema_val, 1) if ema_val else "N/A"
            })

            time.sleep(0.01)

        status.text(f"✅ 완료: {len(st.session_state.found_data)}개 발견")

    except Exception as e:
        st.error(f"에러 발생: {e}")

# ---------------- 결과 ----------------
if st.session_state.found_data:
    st.divider()
    st.dataframe(pd.DataFrame(st.session_state.found_data), use_container_width=True)
else:
    if start_button:
        st.warning("조건에 맞는 종목 없음")
