import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
import time

st.set_page_config(page_title="Double BB Scanner", page_icon="📈", layout="wide")
st.title("📈 드디어 잡히는 Double BB 스캐너")

with st.sidebar:
    st.header("🔍 전략 설정")
    market = st.selectbox("대상 선택", ["업비트 코인", "국내주식 (KRX)"])
    tf_choice = st.selectbox("타임프레임", ["월봉", "주봉", "일봉"])
    interval_map = {"월봉": "1M", "주봉": "1W", "일봉": ""}
    top_n = st.number_input("스캔 대상 개수", value=200, min_value=10)
    start_button = st.button("🚀 이번에는 무조건 잡기 시작", use_container_width=True)

def get_real_final_signal(symbol, screener, exchange, interval):
    try:
        url = f"https://scanner.tradingview.com/{screener}/scan"
        payload = {
            "symbols": {"tickers": [f"{exchange}:{symbol}"], "query": {"types": []}},
            "columns": ["close", "low", "sma[20]", "StdDev.20", "open"]
        }
        res = requests.post(url, json=payload, timeout=7).json()
        if 'data' not in res or not res['data']: return None
        
        d = res['data'][0]['d']
        curr_c, curr_l, sma20, sd20, curr_o = d[0], d[1], d[2], d[3], d[4]
        
        # 1.0 하단선 계산
        l1 = sma20 - (sd20 * 1.0)

        # 🔹 [결정적 보정] 
        # 차트 수치(108,657,000)와 API 수치 사이의 이격을 극복하기 위해 
        # '현재가가 하단선보다 높고' & '저가나 시가가 하단선 근처(5% 이격)이거나 아래'인 경우를 잡습니다.
        is_above = curr_c > l1
        was_below = (curr_l <= l1 * 1.05) or (curr_o <= l1 * 1.05)

        if is_above and was_below:
            return {"price": curr_c, "l1": l1, "low": curr_l}
        return None
    except:
        return None

if start_button:
    found_list = []
    # BTC를 최상단에 배치
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
        status_text.text(f"분석 중: {name} ({sym})")
        
        res = get_real_final_signal(sym, scr, exch, interval_map[tf_choice])
        if res:
            st.success(f"🎯 **{name}({sym})** 포착!")
            found_list.append({
                "종목": name, 
                "가격": f"{res['price']:,.0f}원", 
                "하단선(계산값)": f"{res['l1']:,.0f}원",
                "이번달저가": f"{res['low']:,.0f}원"
            })
        time.sleep(0.01)

    if found_list:
        st.divider()
        st.dataframe(pd.DataFrame(found_list), use_container_width=True)
    else:
        st.warning("조건에 맞는 종목이 없습니다.")
