import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
import time

st.set_page_config(page_title="Double BB Scanner", page_icon="📈", layout="wide")
st.title("📈 사용자 전략 동기화: Double BB '상태 유지' 스캐너")
st.markdown("""
**포착 조건:**
1. 현재 캔들의 **저가(Low)**가 2번 하단선을 터치했거나 그 근처였음
2. 현재 캔들의 **종가(Close)**가 1번 하단선보다 **위에 있음** (돌파 유지)
""")

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
    
    start_button = st.button("🚀 실시간 신호 추적 시작", use_container_width=True)

def get_state_signal(symbol, screener, exchange, interval):
    try:
        url = f"https://scanner.tradingview.com/{screener}/scan"
        # 현재 캔들의 실시간 데이터를 가져옴
        payload = {
            "symbols": {"tickers": [f"{exchange}:{symbol}"], "query": {"types": []}},
            "columns": ["close", "low", "sma[20]", "StdDev.20"]
        }
        res = requests.post(url, json=payload, timeout=7).json()
        if 'data' not in res or not res['data']: return None
        
        d = res['data'][0]['d']
        curr_c, curr_l, curr_ma, curr_sd = d[0], d[1], d[2], d[3]

        if None in [curr_c, curr_l, curr_ma, curr_sd]: return None

        # 밴드 값 계산
        l1 = curr_ma - (curr_sd * sd1)
        l2 = curr_ma - (curr_sd * sd2)

        # --- 사용자님의 '상태 유지' 로직 ---
        # 1. 이번 봉에서 2번 하단을 터치했었는가? (저가 기준)
        #    * 약간의 오차를 감안해 0.5% 범위를 둡니다.
        has_touched_l2 = curr_l <= l2 * 1.005 
        
        # 2. 현재 종가가 1번 하단 위에 있는가?
        is_above_l1 = curr_c > l1

        # 두 조건이 모두 참이면 'BUY' 상태 유지
        if has_touched_l2 and is_above_l1:
            return {"price": curr_c, "l1": l1, "l2": l2}
        return None
    except:
        return None

if start_button:
    found_list = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
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

    # 스캔 시작
    total = len(tickers[:top_n])
    for i, (sym, name, exch, scr) in enumerate(tickers[:top_n]):
        progress_bar.progress((i + 1) / total)
        status_text.text(f"분석 중: {name} ({sym})")
        
        res = get_state_signal(sym, scr, exch, interval_map[tf_choice])
        if res:
            st.success(f"🎯 **{name}({sym})** BUY 신호 유지 중!")
            found_list.append({
                "종목": name, "심볼": sym, "현재가": res['price'], 
                "1번하단(뚫음)": round(res['l1'], 2), "2번하단(터치)": round(res['l2'], 2)
            })
        time.sleep(0.01)

    status_text.text("✅ 스캔 완료!")

    if found_list:
        st.divider()
        st.table(pd.DataFrame(found_list))
    else:
        st.warning("조건을 만족하는 종목이 없습니다. 차트의 저가가 2번 하단에 닿았는지 확인해 보세요!")
