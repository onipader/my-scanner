import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
import time

# ---------------- 기본 설정 ----------------
st.set_page_config(page_title="Double BB Scanner", page_icon="📈", layout="wide")

st.title("📈 Double BB 실시간 BUY 스캐너")
st.markdown("현재 타임프레임 기준 **방금 발생한 BUY 신호(crossover)** 탐지")

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

    std_dev_1 = st.number_input("BB 1σ", value=1.0)

    top_n = st.slider("스캔 개수", 10, 500, 150)

    start_button = st.button("🚀 스캔 시작", use_container_width=True)

# ---------------- 핵심 함수 ----------------
def get_tv_realtime_cross(symbol, screener, exchange, interval):
    try:
        url = f"https://scanner.tradingview.com/{screener}/scan"

        # 🔥 현재 + 이전 봉 데이터 둘 다 요청
        columns = [
            "close",
            "close[1]",
            "sma[20]",
            "sma[20][1]",
            "StdDev.20",
            "StdDev.20[1]"
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

        close_now = d[0]
        close_prev = d[1]

        ma_now = d[2]
        ma_prev = d[3]

        sd_now = d[4]
        sd_prev = d[5]

        if None in [close_now, close_prev, ma_now, ma_prev, sd_now, sd_prev]:
            return None

        # BB 하단 계산
        l1_now = ma_now - sd_now * std_dev_1
        l1_prev = ma_prev - sd_prev * std_dev_1

        # 🔥 Pine Script crossover 그대로 복제
        cross = (close_prev <= l1_prev) and (close_now > l1_now)

        if cross:
            return {
                "price": close_now,
                "signal": "현재 캔들 BUY 발생"
            }

        return None

    except:
        return None

# ---------------- 실행 ----------------
if start_button:
    st.session_state.found_data = []

    progress = st.progress(0)
    status = st.empty()

    try:
        # ---------------- 종목 리스트 ----------------
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

        # ---------------- 분석 ----------------
        total = len(tickers)

        for i, (symbol, name, exch, scr) in enumerate(tickers):
            progress.progress((i + 1) / total)
            status.text(f"분석중: {name}")

            result = get_tv_realtime_cross(
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

        status.text(f"✅ 완료: {len(st.session_state.found_data)}개 발견")

    except Exception as e:
        st.error(f"에러 발생: {e}")

# ---------------- 결과 ----------------
if st.session_state.found_data:
    st.divider()
    st.dataframe(pd.DataFrame(st.session_state.found_data), use_container_width=True)
else:
    if start_button:
        st.warning("현재 캔들 기준 BUY 신호 없음")
