import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
import time

# 페이지 설정
st.set_page_config(page_title="Double BB Scanner", page_icon="📈", layout="wide")

st.title("📈 Double BB + EMA365 스캐너 (트뷰 호환 개선판)")
st.markdown("트레이딩뷰 기준 **현재 BUY 상태 유지 + 최근 교차 신호** 모두 탐지")

# 세션 상태 초기화
if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# -------------------- 사이드바 --------------------
with st.sidebar:
    st.header("🔍 전략 설정")

    market = st.selectbox("대상 선택", [
        "업비트 코인",
        "국내주식 (KRX)",
        "미국주식 (NASDAQ/NYSE)"
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

    st.divider()

    mode = st.selectbox("신호 탐지 방식", [
        "현재 BUY 상태",
        "최근 교차 발생"
    ])

    top_n = st.slider("스캔 대상 수", 10, 1000, 200)

    st.divider()

    st.subheader("⚙️ Double BB 설정")
    std_dev_1 = st.number_input("표준편차 1 (기본 BUY)", value=1.0, step=0.1)
    std_dev_2 = st.number_input("표준편차 2 (강한 저점)", value=2.0, step=0.1)

    use_strong = st.checkbox("극단 저점만 (2σ)", value=False)
    use_ema = st.checkbox("EMA365 위 종목만", value=False)

    st.divider()

    use_per = st.checkbox("저 PER 필터 (국내)", value=False)
    per_limit = st.number_input("PER 이하", value=15.0)

    start_button = st.button("🚀 스캔 시작", use_container_width=True)


# -------------------- 핵심 함수 --------------------
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
            "columns": columns
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

        # Bollinger
        l1 = ma - (sd * std_dev_1)
        l2 = ma - (sd * std_dev_2)

        # ---------------- 핵심 로직 ----------------
        # 현재 BUY 상태
        if use_strong:
            buy_now = close <= l2
        else:
            buy_now = close <= l1

        # EMA 필터
        if use_ema and ema365:
            if close < ema365:
                buy_now = False

        # 최근 교차 (하단선 돌파)
        cross = False
        if prev_close and prev_close <= l1 and close > l1:
            cross = True

        # 모드 선택
        if mode == "현재 BUY 상태":
            if buy_now:
                return {
                    "price": close,
                    "signal": "BUY 유지",
                    "ema365": ema365
                }

        elif mode == "최근 교차 발생":
            if cross:
                return {
                    "price": close,
                    "signal": "최근 교차",
                    "ema365": ema365
                }

        return None

    except:
        return None


# -------------------- 실행 --------------------
if start_button:
    st.session_state.found_data = []

    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        # 종목 리스트
        if "국내" in market:
            df_list = fdr.StockListing('KRX')

            if use_per:
                df_list['PER'] = pd.to_numeric(df_list.get('PER'), errors='coerce')
                df_list = df_list[
                    (df_list['PER'] > 0) &
                    (df_list['PER'] <= per_limit)
                ]

            tickers = [
                (row['Code'], row['Name'], "KRX", "korea")
                for _, row in df_list.head(top_n).iterrows()
            ]

        elif "미국" in market:
            df_list = fdr.StockListing('NASDAQ').head(top_n)

            tickers = [
                (row['Symbol'], row['Symbol'], "NASDAQ", "america")
                for _, row in df_list.iterrows()
            ]

        else:
            res = requests.get("https://api.upbit.com/v1/market/all").json()
            raw = [m for m in res if m['market'].startswith('KRW-')]

            tickers = [("BTC", "비트코인", "UPBIT", "crypto")]

            for m in raw:
                sym = m['market'].split('-')[1]
                if sym != "BTC":
                    tickers.append((sym, m['korean_name'], "UPBIT", "crypto"))

            tickers = tickers[:top_n]

        # ---------------- 실행 ----------------
        total = len(tickers)

        for i, (symbol, name, exch, scr) in enumerate(tickers):
            progress_bar.progress((i + 1) / total)
            status_text.text(f"분석중: {name}")

            result = get_tv_signal(
                symbol,
                scr,
                exch,
                interval_map[tf_choice]
            )

            if result:
                st.success(f"🎯 {name} ({symbol}) → {result['signal']}")

                st.session_state.found_data.append({
                    "종목": name,
                    "가격": result['price'],
                    "신호": result['signal'],
                    "EMA365": round(result['ema365'], 1) if result['ema365'] else "N/A"
                })

            time.sleep(0.01)

        status_text.text(f"✅ 완료: {len(st.session_state.found_data)}개 발견")

    except Exception as e:
        st.error(f"오류 발생: {e}")


# -------------------- 결과 --------------------
if st.session_state.found_data:
    st.divider()
    st.dataframe(pd.DataFrame(st.session_state.found_data), use_container_width=True)
else:
    if start_button:
        st.warning("조건에 맞는 종목 없음")
