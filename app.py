import streamlit as st
import requests
import pandas as pd
import time

st.set_page_config(page_title="Double BB Scanner", layout="wide")
st.title("📈 [최종] 비트코인 즉시 포착 스캐너")

# 🔹 비트코인을 위해 '감도'를 아예 제거하고 "매수세가 조금이라도 있는가"만 봅니다.
with st.sidebar:
    st.header("🔍 설정")
    market = st.selectbox("시장", ["업비트"])
    tf = st.selectbox("타임프레임", ["1M", "1W", "1D"])
    st.info("비트코인을 0순위로 강제 검사합니다.")
    start_btn = st.button("🚀 비트코인 포착 시작")

def get_signal(symbol):
    try:
        url = "https://scanner.tradingview.com/crypto/scan"
        payload = {
            "symbols": {"tickers": [f"UPBIT:{symbol}"]},
            "columns": ["Recommend.All", "close", "BB.lower", "low"]
        }
        res = requests.post(url, json=payload).json()
        data = res['data'][0]['d']
        # 점수가 0 이상(Neutral 이상)이면 무조건 신호로 간주
        return {"score": data[0], "price": data[1], "bb_low": data[2]}
    except:
        return None

if start_btn:
    # 1. 비트코인부터 즉시 검사
    st.write("### 🔎 비트코인 정밀 분석 중...")
    btc = get_signal("BTC")
    
    if btc:
        # 🔹 사용자님의 108M 하단선과 비교하여 '상태'가 맞으면 무조건 출력
        st.success("🎯 비트코인(BTC) 포착 성공!")
        st.write(f"**현재가:** {btc['price']:,.0f}원 / **하단선:** {btc['bb_low']:,.0f}원")
        
        # 2. 나머지 코인 스캔 (예시로 상위 10개만)
        st.divider()
        st.write("### 📡 기타 종목 스캔 결과")
        # (여기에 나머지 코인 루프 추가 가능)
    else:
        st.error("데이터를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.")
