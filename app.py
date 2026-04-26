import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
import time

st.set_page_config(page_title="Double BB Scanner", page_icon="📈", layout="wide")
st.title("📈 사용자 전략 동기화: Double BB 전용 스캐너")
st.markdown("로직: **StdDev 2.0 하단 터치 후 1.0 하단 상향 돌파** 종목 포착")

# 사이드바 설정
with st.sidebar:
    st.header("🔍 전략 설정")
    market = st.selectbox("대상 선택", ["업비트 코인", "국내주식 (KRX)", "미국주식 (NASDAQ/NYSE)"])
    tf_choice = st.selectbox("타임프레임", ["월봉", "주봉", "일봉", "4시간봉", "1시간봉"])
    
    interval_map = {"1시간봉": "60", "4시간봉": "240", "일봉": "", "주봉": "1W", "월봉": "1M"}
    
    st.divider()
    top_n = st.number_input("스캔 대상 개수", value=250, min_value=10)
    
    st.subheader("⚙️ 지표 설정 (사용자 정의)")
    sd1 = st.number_input("Standard Deviation 1", value=1.0)
    sd2 = st.number_input("Standard Deviation 2", value=2.0)
    
    start_button = st.button("🚀 내 전략으로 스캔 시작", use_container_width=True)

def get_custom_strategy_signal(symbol, screener, exchange, interval):
    try:
        url = f"https://scanner.tradingview.com/{screener}/scan"
        # 현재 봉(0)과 직전 봉(1)의 데이터를 모두 가져와서 흐름을 분석
        payload = {
            "symbols": {"tickers": [f"{exchange}:{symbol}"], "query": {"types": []}},
            "columns": [
                "close", "low", "sma[20]", "StdDev.20", "open",
                "close[1]", "low[1]", "sma[20][1]", "StdDev.20[1]"
            ]
        }
        res = requests.post(url, json=payload, timeout=7).json()
        if 'data' not in res or not res['data']: return None
        
        d = res['data'][0]['d']
        # 현재 데이터
        curr_c, curr_l, curr_ma, curr_sd, curr_o = d[0], d[1], d[2], d[3], d[4]
        # 직전 데이터
        prev_c, prev_l, prev_ma, prev_sd = d[5], d[6], d[7], d[8]

        # 밴드 계산
        curr_l1 = curr_ma - (curr_sd * sd1)
        curr_l2 = curr_ma - (curr_sd * sd2)
        prev_l1 = prev_ma - (prev_sd * sd1)
        prev_l2 = prev_ma - (prev_sd * sd2)

        # --- 사용자 로직 구현 ---
        # 조건 1: (현재 혹은 직전 봉에서) 2.0 하단을 터치했거나 그 근처였음
        was_touching_l2 = (curr_l <= curr_l2 * 1.005) or (prev_l <= prev_l2 * 1.005)
        
        # 조건 2: 1.0 하단을 상향 돌파 (현재 종가가 1.0 하단 위, 시가나 직전 종가는 아래)
        is_crossing_l1 = (curr_c > curr_l1) and (prev_c <= prev_l1 or curr_o <= curr_l1)

        # 두 조건이 이번 캔들 범위 안에서 만족되면 BUY
        if was_touching_l2 and is_crossing_l1:
            return {"price": curr_c, "l1": curr_l1, "l2": curr_l2}
        return None
    except:
        return None

if start_button:
    found_list = []
    progress_bar = st.progress(0)
    
    # 리스트 준비
    if "업비트" in market:
        res = requests.get("https://api.upbit.com/v1/market/all").json()
        tickers = [(m['market'].split('-')[1], m['korean_name'], "UPBIT", "crypto") for m in res if m['market'].startswith('KRW-')]
    elif "국내" in market:
        df = fdr.StockListing('KRX')
        tickers = [(row['Code'], row['Name'], "KRX", "korea") for _, row in df.head(top_n).iterrows()]
    else:
        df = fdr.StockListing('NASDAQ')
        tickers = [(row['Symbol'], row['Symbol'], "NASDAQ", "america") for _, row in df.head(top_n).iterrows()]

    # 스캔
    for i, (sym, name, exch, scr) in enumerate(tickers[:top_n]):
        progress_bar.progress((i + 1) / len(tickers[:top_n]))
        res = get_custom_strategy_signal(sym, scr, exch, interval_map[tf_choice])
        if res:
            st.success(f"🎯 **{name}({sym})** 포착!")
            found_list.append({"종목": name, "심볼": sym, "현재가": res['price'], "하단1": round(res['l1'], 2), "하단2": round(res['l2'], 2)})
        time.sleep(0.01)

    if found_list:
        st.divider()
        st.table(pd.DataFrame(found_list))
    else:
        st.warning("조건에 맞는 종목이 없습니다. 로직을 다시 한번 점검해볼까요?")
