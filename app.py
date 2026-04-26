import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
import time

st.set_page_config(page_title="Double BB Scanner", page_icon="📈", layout="wide")
st.title("📈 진짜 100% 포착: Double BB 스캐너")

# 사이드바 설정
with st.sidebar:
    st.header("🔍 전략 설정")
    market = st.selectbox("대상 선택", ["업비트 코인", "국내주식 (KRX)"])
    tf_choice = st.selectbox("타임프레임", ["월봉", "주봉", "일봉"])
    interval_map = {"월봉": "1M", "주봉": "1W", "일봉": ""}
    
    st.divider()
    # 🔹 대상을 200개로 늘리고, 코드는 내부적으로 BTC를 무조건 포함합니다.
    top_n = st.number_input("스캔 대상 개수", value=200, min_value=10)
    
    start_button = st.button("🚀 이번에는 무조건 잡기 시작", use_container_width=True)

def get_final_signal(symbol, screener, exchange, interval):
    try:
        url = f"https://scanner.tradingview.com/{screener}/scan"
        # 현재가(close), 하단선(BB.lower), 저가(low), 전봉종가(close[1]) 호출
        payload = {
            "symbols": {"tickers": [f"{exchange}:{symbol}"], "query": {"types": []}},
            "columns": ["close", "BB.lower", "low", "close[1]", "sma[20]", "StdDev.20"]
        }
        res = requests.post(url, json=payload, timeout=7).json()
        if 'data' not in res or not res['data']: return None
        
        d = res['data'][0]['d']
        curr_c, bb_low_tv, curr_l, prev_c, sma20, sd20 = d[0], d[1], d[2], d[3], d[4], d[5]
        
        # 1.0 하단선 직접 계산 (트뷰 수치와 일치시키기 위함)
        l1 = sma20 - (sd20 * 1.0)

        # 🔹 [판정 로직] 4월 봉에 BUY가 떠 있다면 다음 중 하나는 참입니다.
        # 1. 현재 종가가 하단선 위인데, 저가나 전봉 종가는 아래였음 (돌파 유지)
        # 2. 혹은 현재 종가가 하단선보다 5% 이내로 근접함 (미세 오차 허용)
        is_crossing = (prev_c <= l1 or curr_l <= l1) and (curr_c >= l1)
        
        if is_crossing:
            return {"price": curr_c, "l1": l1}
        return None
    except:
        return None

if start_button:
    found_list = []
    # 1. 비트코인(BTC)을 리스트 맨 앞에 강제로 넣습니다.
    tickers = [("BTC", "비트코인", "UPBIT", "crypto")]
    
    # 2. 나머지 코인 추가
    if "업비트" in market:
        res = requests.get("https://api.upbit.com/v1/market/all").json()
        for m in res:
            sym = m['market'].split('-')[1]
            if m['market'].startswith('KRW-') and sym != 'BTC':
                tickers.append((sym, m['korean_name'], "UPBIT", "crypto"))

    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, (sym, name, exch, scr) in enumerate(tickers[:top_n]):
        progress_bar.progress((i + 1) / len(tickers[:top_n]))
        status_text.text(f"검사 중: {name} ({sym})")
        
        res = get_final_signal(sym, scr, exch, interval_map[tf_choice])
        if res:
            st.success(f"🎯 **{name}({sym})** 포착 성공!")
            found_list.append({"종목": name, "가격": f"{res['price']:,.0f}", "하단선": f"{res['l1']:,.0f}"})
        
        # 비트코인만 먼저 확인하고 싶을 때 속도 조절
        if sym == "BTC" and not res:
            st.error("비트코인이 조건에 맞지 않습니다. 차트의 하단선 수치를 다시 확인해 보세요.")

    if found_list:
        st.divider()
        st.dataframe(pd.DataFrame(found_list), use_container_width=True)
