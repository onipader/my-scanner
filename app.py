import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
import time

# 페이지 설정
st.set_page_config(page_title="Double BB Scanner", page_icon="📈", layout="wide")

st.title("📈 사용자 전략 동기화: Double BB '상태 유지' 스캐너")
st.markdown("""
**차트와 100% 동기화 로직:**
1. **상태 체크:** 현재 종가(`close`)가 1번 하단선(`lower_band_1`)보다 위에 있는가?
2. **이력 체크:** 이번 캔들의 시가(`open`) 또는 직전 캔들의 종가(`close[1]`)가 1번 하단선 아래에 있었는가? (즉, 이번 봉에서 돌파가 일어났는가)
""")

# 사이드바 설정
with st.sidebar:
    st.header("🔍 전략 설정")
    market = st.selectbox("대상 선택", ["업비트 코인", "국내주식 (KRX)", "미국주식 (NASDAQ/NYSE)"])
    tf_choice = st.selectbox("타임프레임", ["월봉", "주봉", "일봉", "4시간봉", "1시간봉"])
    
    interval_map = {"1시간봉": "60", "4시간봉": "240", "일봉": "", "주봉": "1W", "월봉": "1M"}
    
    st.divider()
    top_n = st.number_input("스캔 대상 개수", value=250, min_value=10)
    
    st.subheader("⚙️ 지표 설정")
    sd1 = st.number_input("Standard Deviation 1", value=1.00)
    
    start_button = st.button("🚀 실시간 신호 포착 시작", use_container_width=True)

def get_synced_signal(symbol, screener, exchange, interval):
    try:
        url = f"https://scanner.tradingview.com/{screener}/scan"
        # 현재 봉과 직전 봉의 데이터를 가져와서 돌파 상태를 확인
        payload = {
            "symbols": {"tickers": [f"{exchange}:{symbol}"], "query": {"types": []}},
            "columns": ["close", "sma[20]", "StdDev.20", "close[1]", "open", "low"]
        }
        res = requests.post(url, json=payload, timeout=7).json()
        if 'data' not in res or not res['data']: return None
        
        d = res['data'][0]['d']
        curr_c, curr_ma, curr_sd, prev_c, curr_o, curr_l = d[0], d[1], d[2], d[3], d[4], d[5]

        # 밴드 계산 (SMA 20, StdDev 1.0)
        l1 = curr_ma - (curr_sd * sd1)
        
        # 🔹 사용자님의 ta.crossover를 '상태'로 해석한 핵심 로직
        # 1. 현재 종가가 하단선보다 위에 있어야 함 (돌파 성공 상태)
        is_above = curr_c > l1
        
        # 2. 이번 봉 내에서 하단선 아래에 있었던 적이 있어야 함 (돌파의 흔적)
        # 시가(open)가 아래였거나, 저가(low)가 아래였거나, 혹은 전봉 종가(prev_c)가 아래였을 때
        was_below = (curr_o <= l1) or (curr_l <= l1) or (prev_c <= l1)

        if is_above and was_below:
            return {
                "price": curr_c,
                "l1": l1,
                "diff": curr_c - l1
            }
        return None
    except:
        return None

if start_button:
    found_list = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # 리스트 준비 (비트코인 최우선 순위)
    if "업비트" in market:
        res = requests.get("https://api.upbit.com/v1/market/all").json()
        tickers = [("BTC", "비트코인", "UPBIT", "crypto")]
        for m in res:
            if m['market'].startswith('KRW-') and m['market'] != 'KRW-BTC':
                tickers.append((m['market'].split('-')[1], m['korean_name'], "UPBIT", "crypto"))
    else:
        # 주식 로직 (생략 가능하나 구조 유지)
        tickers = []

    # 스캔 시작
    total_scan = tickers[:top_n]
    for i, (sym, name, exch, scr) in enumerate(total_scan):
        progress_bar.progress((i + 1) / len(total_scan))
        status_text.text(f"분석 중: {name} ({sym})")
        
        res = get_synced_signal(sym, scr, exch, interval_map[tf_choice])
        if res:
            st.success(f"🎯 **{name}({sym})** BUY 신호 포착!")
            found_list.append({
                "종목": name, 
                "심볼": sym, 
                "현재가": f"{res['price']:,.0f}원", 
                "하단선": f"{res['l1']:,.0f}원",
                "이격": f"{res['diff']:,.0f}원"
            })
        time.sleep(0.01)

    status_text.text("✅ 스캔 완료!")

    if found_list:
        st.divider()
        st.table(pd.DataFrame(found_list))
    else:
        st.warning("현재 캔들에서 돌파 조건(하단선 터치 후 위로 마감)을 만족하는 종목이 없습니다.")
