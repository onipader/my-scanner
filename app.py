import streamlit as st
import pandas as pd
import requests
import FinanceDataReader as fdr
import yfinance as yf

st.set_page_config(layout="wide")
st.title("📈 Double BB Scanner (완전 통합버전)")

# ---------------- 설정 ----------------
market = st.selectbox("시장", ["코인", "국내주식", "미국주식"])

tf = st.selectbox("타임프레임", [
    "5분봉", "1시간봉", "4시간봉",
    "일봉", "주봉", "월봉"
])

limit = st.slider("스캔 개수", 10, 100, 30)
start = st.button("🚀 시작")

# ---------------- 리샘플 ----------------
def resample(df, tf):
    df.index = pd.to_datetime(df.index)

    if tf == "일봉":
        return df

    rule_map = {
        "주봉": "W",
        "월봉": "M",
        "1시간봉": "1H",
        "4시간봉": "4H"
    }

    if tf in rule_map:
        return df.resample(rule_map[tf]).last().dropna()

    return df

# ---------------- BB 계산 ----------------
def check(df):
    if len(df) < 25:
        return False

    df["sma"] = df["close"].rolling(20).mean()
    df["std"] = df["close"].rolling(20).std()
    df["lower"] = df["sma"] - df["std"]

    prev = df.iloc[-2]
    now = df.iloc[-1]

    return prev["close"] <= prev["lower"] and now["close"] > now["lower"]

# ---------------- 업비트 데이터 ----------------
def get_upbit(market_code):
    if tf == "5분봉":
        url = "https://api.upbit.com/v1/candles/minutes/5"
    elif tf == "1시간봉":
        url = "https://api.upbit.com/v1/candles/minutes/60"
    elif tf == "4시간봉":
        url = "https://api.upbit.com/v1/candles/minutes/240"
    else:
        url = "https://api.upbit.com/v1/candles/days"

    res = requests.get(url, params={"market": market_code, "count": 200}).json()
    df = pd.DataFrame(res)

    df["close"] = df["trade_price"]
    df = df[::-1]
    df.index = pd.to_datetime(df["candle_date_time_kst"])

    if tf in ["주봉", "월봉"]:
        df = resample(df, tf)

    return df

# ---------------- 국내주식 ----------------
def get_krx(code):
    df = fdr.DataReader(code)
    df = df.rename(columns={"Close": "close"})
    return resample(df, tf)

# ---------------- 미국주식 ----------------
def get_us(symbol):
    df = yf.download(symbol, period="2y", interval="1d", progress=False)
    df = df.rename(columns={"Close": "close"})
    return resample(df, tf)

# ---------------- 실행 ----------------
if start:
    found = []

    progress = st.progress(0)

    if market == "코인":
        markets = requests.get("https://api.upbit.com/v1/market/all").json()
        tickers = [m["market"] for m in markets if m["market"].startswith("KRW-")][:limit]

        for i, t in enumerate(tickers):
            progress.progress((i+1)/len(tickers))

            try:
                df = get_upbit(t)

                if check(df):
                    st.success(f"🎯 {t} BUY")
                    found.append(t)
            except:
                pass

    elif market == "국내주식":
        listing = fdr.StockListing("KRX").head(limit)

        for i, row in listing.iterrows():
            progress.progress((i+1)/limit)

            try:
                df = get_krx(row["Code"])

                if check(df):
                    st.success(f"🎯 {row['Name']} BUY")
                    found.append(row["Name"])
            except:
                pass

    else:
        listing = fdr.StockListing("NASDAQ").head(limit)

        for i, row in listing.iterrows():
            progress.progress((i+1)/limit)

            try:
                df = get_us(row["Symbol"])

                if check(df):
                    st.success(f"🎯 {row['Symbol']} BUY")
                    found.append(row["Symbol"])
            except:
                pass

    st.write("총 발견:", len(found))

    if len(found) == 0:
        st.warning("현재 조건에서 BUY 없음")
