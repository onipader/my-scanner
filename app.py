import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
from datetime import datetime
import requests

# 페이지 설정
st.set_page_config(page_title="글로벌 우량주 스캐너", page_icon="📈", layout="wide")

st.title("📈 실시간 글로벌 우량주 스캐너")
st.markdown("별도 설치 없이 작동하는 안정화 버전입니다.")

# 사이드바 설정
with st.sidebar:
    st.header("🔍 검색 설정")
    market = st.selectbox("대상 선택", ["국내주식 (KOSPI/KOSDAQ)", "미국주식 (NASDAQ/NYSE)", "업비트 코인"])
    timeframe = st.selectbox("타임프레임", ["1d", "1h", "5m"]) # 기본 제공 값으로 단순화
    
    st.divider()
    top_n = st.number_input("스캔할 종목 수", min_value=1, max_value=200, value=50)
    rsi_threshold = st.slider("RSI 기준", 10, 70, 35)
    
    start_button = st.button("🚀 스캔 시작")

# RSI 계산기 (외부 라이브러리 미사용)
def get_rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=period-1, adjust=False).mean()
    ema_down = down.ewm(com=period-1, adjust=False).mean()
    rs = ema_up / (ema_down + 1e-10)
    return 100 - (100 / (1 + rs))

if start_button:
    progress_bar = st.progress(0)
    found_data = []
    
    # 1. 종목 리스트 가져오기
    try:
        if "국내" in market:
            df = fdr.StockListing('KRX').head(top_n)
            tickers = [(row['Code'], row['Name']) for _, row in df.iterrows()]
        elif "미국" in market:
            df = fdr.StockListing('NASDAQ').head(top_n)
            tickers = [(row['Symbol'], row['Symbol']) for _, row in df.iterrows()]
        else:
            res = requests.get("https://api.upbit.com/v1/market/all").json()
            tickers = [(m['market'], m['korean_name']) for m in res if m['market'].startswith('KRW-')][:top_n]

        # 2. 분석
        for i, (code, name) in enumerate(tickers):
            progress_bar.progress((i + 1) / len(tickers))
            try:
                # 데이터 수집 (야후 파이낸스 활용)
                symbol = code if "국내" not in market else (code + ".KS" if "KOSPI" in str(df) else code + ".KQ")
                data = yf.download(symbol, period="1mo", interval=timeframe, progress=False)
                
                if not data.empty:
                    close = data['Close']
                    rsi = get_rsi(close).iloc[-1]
                    
                    # 볼린저 밴드 계산
                    ma20 = close.rolling(20).mean()
                    std20 = close.rolling(20).std()
                    lower_b = ma20 - (std20 * 2)
                    
                    curr_price = close.iloc[-1]
                    
                    if curr_price <= lower_b.iloc[-1] and rsi <= rsi_threshold:
                        st.success(f"✅ {name} 포착!")
                        found_data.append({"종목": name, "가격": round(float(curr_price), 2), "RSI": round(float(rsi), 1)})
            except:
                continue
                
        if found_data:
            st.table(pd.DataFrame(found_data))
        else:
            st.info("조건에 맞는 종목이 없습니다.")
            
    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")
