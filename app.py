import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
import time

# 페이지 설정
st.set_page_config(page_title="Double BB Scanner", page_icon="📈", layout="wide")

st.title("📈 사용자 전략 동기화: 실시간 상태 포착 스캐너")
st.markdown("차트의 BUY 신호와 동기화하기 위해 **'이번 달 하단 터치 후 복귀'** 여부를 체크합니다.")

# 사이드바 설정
with st.sidebar:
    st.header("🔍 전략 설정")
    market = st.selectbox("대상 선택", ["업비트 코인", "국내주식 (KRX)"])
    tf_choice = st.selectbox("타임프레임", ["월봉", "주봉", "일봉", "4시간봉", "1시간봉"])
    interval_map = {"1시간봉": "60", "4시간봉": "240", "일봉": "", "주봉": "1W", "월봉": "1M"}
    
    st.divider()
    top_n = st.number_input("스캔 대상 개수", value=250, min_value=10)
    sd1 = st.number_input("Standard Deviation 1", value=1.00)
    
    start_button = st.button("🚀 실시간 신호 스캔 시작", use_container_width=True)

def get_realtime_signal(symbol, screener, exchange, interval):
    try:
        url = f"https://scanner.tradingview.com/{screener}/scan"
        payload = {
            "symbols": {"tickers": [f"{exchange}:{symbol}"], "query": {"types": []}},
            "columns": ["close", "low", "sma[20]", "StdDev.20", "open", "close[1]"]
        }
        res = requests.post(url, json=payload, timeout=7).json()
        if 'data' not in res or not res['data']: return None
        
        d = res['data'][0]['d']
        curr_c, curr_l, curr_ma, curr_sd, curr_o, prev_c = d[0], d[1], d[2], d[3], d[4], d[5]

        # 1번 하단선 계산
        l1 = curr_ma - (curr_sd * sd1)
        
        # 🔹 [핵심 로직] 이번 봉(4월) 내에서 1.0 하단선을 건드렸거나 아래였고, 현재는 위인 경우
        # ta.crossover보다 훨씬 유연하게 차트 신호를 잡아냅니다.
        was_below = (curr_l <= l1) or (curr_o <= l1) or (prev_c <= l1)
        is_above = curr_c > l1

        if was_below and is_above:
            return {"price": curr_c, "l1": l1, "low": curr_l}
        return None
    except:
        return None

if start_button:
    found_list = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    if "업비트" in market:
        res = requests.get("https://api.upbit.com/v1/market/all").json()
        tickers = [("BTC", "비트코인", "UPBIT", "crypto")]
        for m in res:
            if m['market'].startswith('KRW-') and m['market'] != 'KRW-BTC':
                tickers.append((m['market'].split('-')[1], m['korean_name'], "UPBIT", "crypto"))
    else:
        df = fdr.StockListing('KRX')
        tickers = [(row['Code'], row['Name'], "KRX", "korea") for _, row in df.head(top_n).iterrows()]

    for i, (sym, name, exch, scr) in enumerate(tickers[:top_n]):
        progress_bar.progress((i + 1) / len(tickers[:top_n]))
        status_text.text(f"분석 중: {name}")
        
        res = get_realtime_signal(sym, scr, exch, interval_map[tf_choice])
        if res:
            st.success(f"🎯 **{name}({sym})** 포착!")
            found_list.append({"종목": name, "심볼": sym, "가격": f"{res['price']:,.0f}", "하단선": f"{res['l1']:,.0f}"})
        time.sleep(0.01)

    status_text.text("✅ 스캔 완료!")
    if found_list:
        st.divider()
        st.table(pd.DataFrame(found_list))
    else:
        st.warning("조건을 만족하는 종목이 없습니다. (하단선과 저가 수치를 다시 확인해 주세요)")
