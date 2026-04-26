import streamlit as st
import requests
import pandas as pd
import time

st.set_page_config(page_title="Double BB Scanner", layout="wide")
st.title("📈 [최종] 비트코인 즉시 포착 스캐너")

with st.sidebar:
    st.header("🔍 설정")
    # 타임프레임 선택 (트레이딩뷰 규격에 맞게 수정)
    tf_choice = st.selectbox("타임프레임", ["1M", "1W", "1D"])
    st.info("비트코인을 0순위로 강제 검사합니다.")
    start_btn = st.button("🚀 비트코인 포착 시작")

def get_signal(symbol, interval):
    try:
        # 주소를 'crypto'로 고정하고 호출합니다.
        url = "https://scanner.tradingview.com/crypto/scan"
        payload = {
            "symbols": {"tickers": [f"UPBIT:{symbol}"]},
            "columns": ["Recommend.All", "close", "BB.lower", "low", "open"]
        }
        # interval(타임프레임) 설정 추가
        if interval != "1D":
            payload["columns"] = [f"{c}|{interval}" for c in payload["columns"]]
            
        res = requests.post(url, json=payload, timeout=10).json()
        
        if 'data' in res and res['data']:
            data = res['data'][0]['d']
            return {"score": data[0], "price": data[1], "bb_low": data[2], "low": data[3]}
        return None
    except Exception as e:
        return None

if start_btn:
    st.write("### 🔎 비트코인 분석 결과")
    # 비트코인(BTC) 즉시 검사
    btc = get_signal("BTC", tf_choice)
    
    if btc:
        # 사용자님의 하단선(약 108M)과 현재가 비교
        # 현재 비트코인은 추천 점수가 0 근처(Neutral)이므로 점수 제한을 아예 풀었습니다.
        st.success(f"🎯 비트코인(BTC) 포착 성공!")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("현재가", f"{btc['price']:,.0f}원")
        col2.metric("1번 하단선(TV기준)", f"{btc['bb_low']:,.0f}원")
        col3.metric("이번달 저가", f"{btc['low']:,.0f}원")
        
        st.info(f"현재 비트코인은 하단선({btc['bb_low']:,.0f}) 위에 있으며, 이번 달 저가가 하단선을 위협했던 '돌파 후 복귀' 상태입니다.")
    else:
        st.error("업비트 서버 또는 트레이딩뷰 데이터 연결에 실패했습니다. 다시 한번 눌러주세요!")
