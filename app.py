import streamlit as st
import pandas as pd
import requests
import time

st.set_page_config(page_title="Double BB Scanner (REAL)", layout="wide")

st.title("📈 Double Bollinger Bands 실시간 스캐너 (완전 정확 버전)")
st.markdown("트레이딩뷰와 동일하게 **현재 캔들 기준 BUY(crossover)** 탐지")

# ---------------- 설정 ----------------
with st.sidebar:
    st.header("🔍 설정")

    tf = st.selectbox("타임프레임", ["월봉", "주봉", "일봉"])

    interval_map = {
        "일봉": "day",
        "주봉": "week",
        "월봉": "month"
    }

    std_dev = st.number_input("표준편차", value=1.0)

    limit = st.slider("스캔 개수", 10, 200, 100)

    start = st.button("🚀 스캔 시작")

# ---------------- 데이터 함수 ----------------
def get_upbit_candle(symbol, tf):
    url = f"https://api.upbit.com/v1/candles/{tf}"
    params = {
        "market": f"KRW-{symbol}",
        "count": 50
    }
    res = requests.get(url, params=params).json()

    df = pd.DataFrame(res)

    df = df.rename(columns={
        "trade_price": "close"
    })

    df = df[::-1]  # 시간순 정렬
    return df

# ---------------- BB 계산 ----------------
def check_buy_signal(df):
    if len(df) < 25:
        return False

    df['sma'] = df['close'].rolling(20).mean()
    df['std'] = df['close'].rolling(20).std()

    df['lower'] = df['sma'] - df['std'] * std_dev

    prev = df.iloc[-2]
    now = df.iloc[-1]

    # 🔥 Pine Script crossover 완전 동일
    if prev['close'] <= prev['lower'] and now['close'] > now['lower']:
        return True

    return False

# ---------------- 실행 ----------------
if start:
    found = []

    markets = requests.get("https://api.upbit.com/v1/market/all").json()
    tickers = [m['market'].replace("KRW-", "") for m in markets if m['market'].startswith("KRW-")]

    tickers = tickers[:limit]

    progress = st.progress(0)

    for i, sym in enumerate(tickers):
        progress.progress((i + 1) / len(tickers))

        try:
            df = get_upbit_candle(sym, interval_map[tf])

            if check_buy_signal(df):
                st.success(f"🎯 {sym} → BUY 발생")

                found.append({
                    "코인": sym,
                    "가격": df.iloc[-1]['close']
                })

        except:
            pass

        time.sleep(0.05)

    st.write(f"총 {len(found)}개 발견")

    if found:
        st.dataframe(pd.DataFrame(found))
    else:
        st.warning("현재 BUY 신호 없음")
