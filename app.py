import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
import time

st.set_page_config(page_title="Double BB Scanner", page_icon="📈", layout="wide")
st.title("📈 드디어 잡히는 Double BB 스캐너 (최종 보정)")

with st.sidebar:
    st.header("🔍 전략 설정")
    market = st.selectbox("대상 선택", ["업비트 코인", "국내주식 (KRX)"])
    tf_choice = st.selectbox("타임프레임", ["월봉", "주봉", "일봉"])
    interval_map = {"월봉": "1M", "주봉": "1W", "일봉": ""}
    top_n = st.number_input("스캔 대상 개수", value=200, min_value=10)
    
    st.divider()
    # 🔹 포착 감도: 1.05는 하단선보다 5% 위에 있어도 '뚫었던 것'으로 인정합니다.
    tolerance = st.slider("포착 감도 (높을수록 더 잘 잡힘)", 1.0, 1.1, 1.05, step=0.01)
    
    start_button = st.button("🚀 이번에는 무조건 잡기 시작", use_container_width=True)

def get_final_bojung_signal(symbol, screener, exchange, interval):
    try:
        url = f"https://scanner.tradingview.com/{screener}/scan"
        payload = {
            "symbols": {"tickers": [f"{exchange}:{symbol}"], "query": {"types": []}},
            "columns": ["close", "low", "sma[20]", "StdDev.20", "open", "close[1]"]
        }
        res = requests.post(url, json=payload, timeout=7).json()
        if 'data' not in res or not res['data']: return None
        
        d = res['data'][0]['d']
        curr_c, curr_l, sma20, sd20, curr_o, prev_c = d[0], d[1], d[2], d[3], d[4], d[5]
        
        # 하단선 계산
        l1 = sma20 - (sd20 * 1.0)

        # 🔹 [결정적 보정 로직]
        # 1. 현재 종가가 하단선보다 위에 있는가?
        is_above = curr_c > l1
        
        # 2. 이번 달 저가나 시가, 혹은 전봉 종가 중 하나라도 
        #    하단선 근처(설정한 감도 범위)에 있었는가?
        was_below = (curr_l <= l1 * tolerance) or (curr_o <= l1 * tolerance) or (prev_c <= l1 * tolerance)

        if is_above and was_below:
            return {"price": curr_c, "l1": l1, "low": curr_l}
        return None
    except:
        return None

if start_button:
    found_list = []
    # 비트코인(BTC)을 명단 1순위로 강제 삽입
    tickers = [("BTC", "비트코인", "UPBIT", "crypto")]
    
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
        status_text.text(f"분석 중: {name}")
        
        res = get_final_bojung_signal(sym, scr, exch, interval_map[tf_choice])
        if res:
            st.success(f"🎯 **{name}({sym})** 포착!")
            found_list.append({
                "종목": name, "가격": f"{res['price']:,.0f}원", 
                "하단선": f"{res['l1']:,.0f}원", "저가": f"{res['low']:,.0f}원"
            })
        time.sleep(0.01)

    if found_list:
        st.divider()
        st.table(pd.DataFrame(found_list))
    else:
        st.warning("여전히 안 잡힌다면 '포착 감도' 슬라이더를 1.1로 높여보세요!")
