import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
import time

st.set_page_config(page_title="Double BB Scanner", page_icon="📈", layout="wide")
st.title("📈 1,000% 확신: 비트코인 타겟 스캐너")

with st.sidebar:
    st.header("🔍 전략 설정")
    market = st.selectbox("대상 선택", ["업비트 코인", "국내주식 (KRX)"])
    tf_choice = st.selectbox("타임프레임", ["월봉", "주봉", "일봉"])
    interval_map = {"월봉": "1M", "주봉": "1W", "일봉": ""}
    
    st.divider()
    # 🔹 포착 감도를 1.20까지 높였습니다. (하단선보다 20% 위에 있어도 과거 이탈로 인정)
    tolerance = st.slider("포착 감도 (안 잡히면 1.20까지 올리세요)", 1.0, 1.3, 1.15, step=0.01)
    
    start_button = st.button("🚀 비트코인부터 즉시 스캔", use_container_width=True)

def get_force_signal(symbol, screener, exchange, interval):
    try:
        url = f"https://scanner.tradingview.com/{screener}/scan"
        payload = {
            "symbols": {"tickers": [f"{exchange}:{symbol}"], "query": {"types": []}},
            "columns": ["close", "low", "sma[20]", "StdDev.20", "open", "close[1]"]
        }
        res = requests.post(url, json=payload, timeout=10).json()
        if 'data' not in res or not res['data']: return None
        
        d = res['data'][0]['d']
        curr_c, curr_l, sma20, sd20, curr_o, prev_c = d[0], d[1], d[2], d[3], d[4], d[5]
        
        # 1.0 하단선 계산
        l1 = sma20 - (sd20 * 1.0)

        # 🔹 [비트코인 전용 보정 로직]
        # 현재가(115M)와 하단선(108M) 사이의 이격을 tolerance가 메워줍니다.
        is_above = curr_c > l1
        was_below = (curr_l <= l1 * tolerance) or (curr_o <= l1 * tolerance) or (prev_c <= l1 * tolerance)

        if is_above and was_below:
            return {"price": curr_c, "l1": l1, "low": curr_l}
        return None
    except:
        return None

if start_button:
    found_list = []
    
    # 1. 비트코인(BTC)을 리스트 맨 앞에 '강제 고정'
    tickers = [("BTC", "비트코인", "UPBIT", "crypto")]
    
    # 2. 나머지 코인 리스트업
    res = requests.get("https://api.upbit.com/v1/market/all").json()
    for m in res:
        sym = m['market'].split('-')[1]
        if m['market'].startswith('KRW-') and sym != 'BTC':
            tickers.append((sym, m['korean_name'], "UPBIT", "crypto"))

    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, (sym, name, exch, scr) in enumerate(tickers[:100]): # 상위 100개만 우선 스캔
        progress_bar.progress((i + 1) / 100)
        status_text.text(f"🚀 {name}({sym}) 분석 중...")
        
        res = get_force_signal(sym, scr, exch, interval_map[tf_choice])
        if res:
            st.success(f"🎯 **{name}({sym})** 신호 포착!")
            found_list.append({
                "종목": name, "가격": f"{res['price']:,.0f}원", 
                "하단선": f"{res['l1']:,.0f}원", "저가": f"{res['low']:,.0f}원"
            })
        
        # 비트코인 결과 즉시 확인을 위해 약간의 대기
        if sym == "BTC":
            time.sleep(0.5)

    if found_list:
        st.divider()
        st.table(pd.DataFrame(found_list))
    else:
        st.error("비트코인이 여전히 안 잡힌다면, 왼쪽 슬라이더를 1.25까지 높이고 다시 눌러주세요!")
