import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
import requests

# 페이지 설정
st.set_page_config(page_title="글로벌 자산 스캐너", layout="wide")
st.title("💰 글로벌 주식 & 코인 매수신호 스캐너")

# --- 사이드바 설정 ---
st.sidebar.header("🔍 필터 설정")
market = st.sidebar.selectbox("대상 시장", ["국내 코스피/코스닥", "미국 나스닥 100", "업비트 코인"])
interval = st.sidebar.selectbox("타임프레임", ["1d", "4h", "1h"], index=0) # 타임프레임 부활!
start_btn = st.sidebar.button("분석 시작")

# --- 분석 함수 ---
def analyze_asset(ticker, name, is_kr=False):
    try:
        # 타임프레임에 따라 데이터 가져오기
        period = "200d" if interval == "1d" else "10d"
        df = yf.download(ticker, period=period, interval=interval, progress=False)
        
        if len(df) < 30: return None

        # 지표 계산
        ma20 = df['Close'].rolling(window=20).mean()
        std = df['Close'].rolling(window=20).std()
        df['lower_band'] = ma20 - (std * 2)
        df['ema200'] = df['Close'].ewm(span=200, adjust=False).mean()

        curr = df.iloc[-1]
        close = float(curr['Close'])
        lower = float(curr['lower_band'])
        ema200 = float(curr['ema200'])

        # 매수 조건 (이평선 조건은 일단 제외하고 하단 돌파만 체크)
        if close < lower:
            # if close > ema200: # 나중에 이평선 조건 다시 쓰려면 이 줄의 #만 지우세요!
            return {
                "종목명": name, "티커": ticker, 
                "현재가": f"{close:,.0f}" if is_kr else f"{close:,.2f}",
                "밴드하단": f"{lower:,.0f}" if is_kr else f"{lower:,.2f}",
                "200일선": f"{ema200:,.0f}" if is_kr else f"{ema200:,.2f}"
            }
    except:
        return None
    return None

# --- 메인 로직 ---
if start_btn:
    results = []
    status = st.empty()

    if "코인" in market:
        # 업비트 전체 원화 코인 리스트 가져오기
        url = "https://api.upbit.com/v1/market/all"
        coins = requests.get(url).json()
        krw_coins = [c for c in coins if c['market'].startswith('KRW-')]
        
        for c in krw_coins:
            status.text(f"코인 분석 중: {c['korean_name']}")
            res = analyze_asset(f"{c['market'].split('-')[1]}-USD", c['korean_name'])
            if res: results.append(res)

    elif "국내" in market:
        df_krx = fdr.StockListing('KRX').head(300) # 일단 상위 300개 테스트
        for _, row in df_krx.iterrows():
            status.text(f"국내주식 분석 중: {row['Name']}")
            t = row['Code'] + (".KS" if row['Market'] == 'KOSPI' else ".KQ")
            res = analyze_asset(t, row['Name'], is_kr=True)
            if res: results.append(res)

    status.text("✅ 분석 완료!")
    if results:
        st.table(pd.DataFrame(results))
    else:
        st.info("조건에 맞는 종목이 없습니다. 타임프레임을 바꿔보세요!")
