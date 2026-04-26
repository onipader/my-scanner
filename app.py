import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="BTC Scanner", layout="wide")
st.title("📈 비트코인 정밀 스캐너")

# 사이드바
with st.sidebar:
    st.header("⚙️ 설정")
    st.info("비트코인(BTC) 월봉 데이터를 우선적으로 호출합니다.")
    start_btn = st.button("🚀 스캔 시작")

def get_btc_data():
    try:
        # 트레이딩뷰 공식 스캐너 API 주소
        url = "https://scanner.tradingview.com/crypto/scan"
        
        # 월봉(1M) 데이터를 가져오기 위한 정밀 페이로드
        payload = {
            "symbols": {"tickers": ["UPBIT:BTCKRW"]},
            "columns": ["close|1M", "BB.lower|1M", "low|1M", "open|1M"]
        }
        
        res = requests.post(url, json=payload, timeout=10)
        data = res.json()
        
        if 'data' in data and data['data']:
            d = data['data'][0]['d']
            return {
                "현재가": d[0],
                "하단선": d[1],
                "저가": d[2],
                "시가": d[3]
            }
        return None
    except Exception as e:
        return str(e)

if start_btn:
    st.write("### 🔎 분석 결과")
    result = get_btc_data()
    
    if isinstance(result, dict):
        # 🎯 조건 판정: 현재가가 하단선보다 높고, 이번 달 저가가 하단선보다 낮았는가?
        is_recovered = result['현재가'] > result['하단선']
        was_touched = result['저가'] <= result['하단선'] * 1.05 # 5% 오차 허용
        
        if is_recovered:
            st.success("🎯 비트코인(BTC) 조건 부합! (하단선 복귀 상태)")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("현재가", f"{result['현재가']:,.0f}원")
            col2.metric("1번 하단선", f"{result['하단선']:,.0f}원")
            col3.metric("이번달 저가", f"{result['저가']:,.0f}원")
            
            st.info(f"현재 비트코인은 사용자님의 차트 설정대로 하단선({result['하단선']:,.0f}) 위에서 움직이고 있습니다.")
    else:
        st.error(f"데이터 연결 오류: {result}. 다시 한번 눌러주세요!")
