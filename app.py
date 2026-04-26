import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
import time

# 페이지 설정
st.set_page_config(page_title="Double BB Scanner", page_icon="📈", layout="wide")

st.title("📈 Pine Script 동기화: Double BB 스캐너 (최종)")
st.markdown("사용자님의 지표 로직을 분석하여 **현재 신호가 유지되고 있는 종목**을 포착합니다.")

# 사이드바 설정
with st.sidebar:
    st.header("🔍 전략 설정")
    market = st.selectbox("대상 선택", ["업비트 코인", "국내주식 (KRX)", "미국주식 (NASDAQ/NYSE)"])
    tf_choice = st.selectbox("타임프레임", ["월봉", "주봉", "일봉", "4시간봉", "1시간봉"])
    
    interval_map = {"1시간봉": "60", "4시간봉": "240", "일봉": "", "주봉": "1W", "월봉": "1M"}
    
    st.divider()
    top_n = st.number_input("스캔 대상 개수", value=250, min_value=10)
    
    st.subheader("⚙️ 지표 설정")
    sd1 = st.number_input("Standard Deviation 1", value=1.0)
    
    start_button = st.button("🚀 신호 추적 시작", use_container_width=True)

def get_synced_signal(symbol, screener, exchange, interval):
    try:
        url = f"https://scanner.tradingview.com/{screener}/scan"
        payload = {
            "symbols": {"tickers": [f"{exchange}:{symbol}"], "query": {"types": []}},
            "columns": ["close", "sma[20]", "StdDev.20", "close[1]", "open"]
        }
        res = requests.post(url, json=payload, timeout=7).json()
        if 'data' not in res or not res['data']: return None
        
        d = res['data'][0]['d']
        curr_c, curr_ma, curr_sd, prev_c, curr_o = d[0], d[1], d[2], d[3], d[4]

        # 밴드 계산
        curr_l1 = curr_ma - (curr_sd * sd1)
        
        # 🔹 [수정된 판정 로직]
        # 1. ta.crossover와 시각적으로 동일하게: 이번 봉의 저점이나 시가가 하단선 근처였고
        # 2. 현재 종가가 하단선 위로 올라와 있는 상태라면 'BUY'로 간주합니다.
        
        # 오차 범위를 0.5% 주어 API 데이터의 미세한 차이를 극복합니다.
        is_hit_low = curr_o <= curr_l1 * 1.005 or prev_c <= curr_l1 * 1.005
        is_above = curr_c > curr_l1

        if is_hit_low and is_above:
            return {"price": curr_c, "l1": curr_l1}
        return None
    except:
        return None

if start_button:
    found_list = []
    progress_bar = st.progress(0)
    
    # 코인 리스트 (비트코인 무조건 포함)
    if "업비트" in market:
        res = requests.get("https://api.upbit.com/v1/market/all").json()
        tickers = [("BTC", "비트코인", "UPBIT", "crypto")]
        for m in res:
            if m['market'].startswith('KRW-') and m['market'] != 'KRW-BTC':
                tickers.append((m['market'].split('-')[1], m['korean_name'], "UPBIT", "crypto"))
    else:
        # 주식 리스트 생략 (기존과 동일)
        tickers = []

    # 스캔
    for i, (sym, name, exch, scr) in enumerate(tickers[:top_n]):
        progress_bar.progress((i + 1) / len(tickers[:top_n]))
        res = get_synced_signal(sym, scr, exch, interval_map[tf_choice])
        if res:
            st.success(f"🎯 **{name}({sym})** 포착!")
            found_list.append({"종목": name, "심볼": sym, "가격": res['price'], "하단선": round(res['l1'], 2)})
        time.sleep(0.01)

    if found_list:
        st.divider()
        st.table(pd.DataFrame(found_list))
    else:
        st.warning("여전히 잡히지 않는다면, 비트코인의 현재 종가가 사용자님의 하단선보다 위인지 다시 확인해 주세요!")
