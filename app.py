import streamlit as st
import yfinance as yf
import pandas as pd
import datetime

st.set_page_config(page_title="Bollinger Band Scanner", layout="wide")
st.title("📊 야후 파이낸스 기반 볼밴 하단 스캐너")

with st.sidebar:
    st.header("⚙️ 설정")
    target_market = st.selectbox("대상 시장", ["코인 (BTC/ETH 등)", "미국 주식"])
    period = st.selectbox("데이터 기간", ["1y", "2y", "5y"])
    interval = st.selectbox("봉 단위 (타임프레임)", ["1mo", "1wk", "1d"])
    
    st.info("야후 파이낸스 데이터를 직접 계산하여 하단 돌파 종목을 찾습니다.")
    start_btn = st.button("🚀 스캔 시작")

# 코인 리스트 (야후 파이낸스 티커 기준)
COIN_TICKERS = [
    "BTC-USD", "ETH-USD", "BCH-USD", "SOL-USD", "XRP-USD", 
    "ADA-USD", "DOGE-USD", "DOT-USD", "MATIC-USD", "TRX-USD",
    "AVAX-USD", "SHIB-USD", "LINK-USD", "NEAR-USD", "UNI-USD"
]

# 미국 주식 리스트 (시총 상위 예시)
STOCK_TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "BRK-B", "UNH", "V"]

def calculate_bb(ticker, p, i):
    try:
        df = yf.download(ticker, period=p, interval=i, progress=False)
        if df.empty: return None
        
        # 볼린저 밴드 계산 (20일 표준)
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['STD'] = df['Close'].rolling(window=20).std()
        df['Upper'] = df['MA20'] + (df['STD'] * 2)
        df['Lower'] = df['MA20'] - (df['STD'] * 2)
        
        last_row = df.iloc[-1]
        return {
            "Symbol": ticker,
            "Price": round(float(last_row['Close']), 2),
            "Lower": round(float(last_row['Lower']), 2),
            "Status": "하단 돌파" if last_row['Close'] <= last_row['Lower'] else "근접"
        }
    except:
        return None

if start_btn:
    tickers = COIN_TICKERS if target_market == "코인 (BTC/ETH 등)" else STOCK_TICKERS
    results = []
    
    with st.spinner("데이터 분석 중..."):
        for t in tickers:
            res = calculate_bb(t, period, interval)
            if res:
                results.append(res)
    
    if results:
        df_res = pd.DataFrame(results)
        st.table(df_res)
        st.success("스캔이 완료되었습니다.")
    else:
        st.error("데이터를 가져오지 못했습니다.")
