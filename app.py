import streamlit as st
import pandas as pd
import requests
import FinanceDataReader as fdr
import yfinance as yf
import time

st.set_page_config(page_title="Double BB Scanner PRO", layout="wide")

st.title("📈 Double Bollinger Bands 스캐너 (통합버전)")
st.markdown("코인 / 국내 / 미국 전부 지원 + 현재 캔들 BUY(crossover) 탐지")

# ---------------- 설정 ----------------
with st.sidebar:
    st.header("🔍 설정")

    market = st.selectbox("시장 선택", [
        "업비트 코인",
        "국내 주식",
        "미국 주식"
    ])

    tf = st.selectbox("타임프레임", [
        "일봉", "주봉", "월봉"
    ])

    interval_map = {
        "일봉": "day",
        "주봉": "week",
        "월봉": "month"
    }

    std_dev = st.number_input("표준편차", value=1.0)

    limit = st.slider("스캔 개수", 10, 200, 100)

    start = st.button("🚀 스캔 시작")

# ---------------- 데이터 함수 ----------------
def get_upbit(symbol, tf):
    url = f"https://api.upbit.com/v1/candles/{tf}"
    params = {"market": f"KRW-{symbol}", "count": 50}
    res = requests.get(url, params=params).json()
    df = pd.DataFrame(res)
    df = df.rename(columns={"trade_price": "close"})
    df = df[::-1]
    return df

def get_krx(symbol):
    df = fdr.DataReader(symbol)
    df = df.tail(100)
    return df.rename(columns={"Close": "close"})

def get_us(symbol):
    df = yf.download(symbol, period="6mo", interval="1d", progress=False)
    return df.rename(columns={"Close": "close"})

# ---------------- 리샘플 ----------------
def resample_df(df, tf):
    if tf == "일봉":
        return df

    rule = "W" if tf == "주봉" else "M"

    return df.resample(rule).agg({
        "close": "last"
    }).dropna()

# ---------------- BB 계산 ----------------
def check_buy(df):
    if len(df) < 25:
        return False

    df['sma'] = df['close'].rolling(20).mean()
    df['std'] = df['close'].rolling(20).std()
    df['lower'] = df['sma'] - df['std'] * std_dev

    prev = df.iloc[-2]
    now = df.iloc[-1]

    return (prev['close'] <= prev['lower']) and (now['close'] > now['lower'])

# ---------------- 실행 ----------------
if start:
    found = []

    if market == "업비트 코인":
        markets = requests.get("https://api.upbit.com/v1/market/all").json()
        tickers = [m['market'].replace("KRW-", "") for m in markets if m['market'].startswith("KRW-")]

        for i, sym in enumerate(tickers[:limit]):
            try:
                df = get_upbit(sym, interval_map[tf])
                if check_buy(df):
                    st.success(f"🎯 {sym} BUY")
                    found.append({"종목": sym, "가격": df.iloc[-1]['close']})
            except:
                pass

    elif market == "국내 주식":
        listing = fdr.StockListing('KRX').head(limit)

        for i, row in listing.iterrows():
            try:
                df = get_krx(row['Code'])
                df = resample_df(df, tf)

                if check_buy(df):
                    st.success(f"🎯 {row['Name']} BUY")
                    found.append({"종목": row['Name'], "가격": df.iloc[-1]['close']})
            except:
                pass

    else:
        listing = fdr.StockListing('NASDAQ').head(limit)

        for i, row in listing.iterrows():
            try:
                df = get_us(row['Symbol'])
                df = resample_df(df, tf)

                if check_buy(df):
                    st.success(f"🎯 {row['Symbol']} BUY")
                    found.append({"종목": row['Symbol'], "가격": df.iloc[-1]['close']})
            except:
                pass

    st.write(f"총 {len(found)}개 발견")

    if found:
        st.dataframe(pd.DataFrame(found))
    else:
        st.warning("현재 BUY 신호 없음")
