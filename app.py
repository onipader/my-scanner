import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
import time

# 페이지 설정
st.set_page_config(page_title="Double BB Scanner", page_icon="📈", layout="wide")

st.title("📈 사용자 전략 동기화: 1번 하단선 복귀 스캐너")
st.markdown("""
**포착 로직:**
1. **이탈 확인:** 이번 캔들의 **저가(Low)**가 1번 하단선보다 낮았음 (뚫고 내려갔었음)
2. **복귀 확인:** 현재 **종가(Close)**가 1번 하단선보다 위에 있음 (뚫고 올라옴)
*결과적으로 이번 달에 'V'자 반등이나 하단 돌파 신호가 유지되는 종목을 찾습니다.*
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
    
    start_button = st.button("🚀 조건 부합 종목 찾기", use_container_width=True)

def get_recovery_signal(symbol, screener, exchange, interval):
    try:
        url = f"https://scanner.tradingview.com/{screener}/scan"
        # 현재 캔들의 종가, 저가, 시가와 지표 데이터를 가져옴
        payload = {
            "symbols": {"tickers": [f"{exchange}:{symbol}"], "query": {"types": []}},
            "columns": ["close", "low", "sma[20]", "StdDev.20", "open"]
        }
        res = requests.post(url, json=payload, timeout=7).json()
        if 'data' not in res or not res['data']: return None
        
        d = res['data'][0]['d']
        curr_c, curr_l, curr_ma, curr_sd, curr_o = d[0], d[1], d[2], d[3], d[4]

        # 1번 하단선 계산
        l1 = curr_ma - (curr_sd * sd1)
        
        # 🔹 사용자님 맞춤 로직 🔹
        # 조건 1: 이번 캔들에서 1번 하단선 아래로 내려갔던 흔적이 있는가? (저가가 l1보다 낮음)
        was_broken = curr_l < l1
        
        # 조건 2: 현재는 1번 하단선 위로 올라와 있는가? (종가가 l1보다 높음)
        is_recovered = curr_c > l1

        if was_broken and is_recovered:
            return {
                "price": curr_c,
                "l1": l1,
                "low": curr_l,
                "recovery_pct": ((curr_c / l1) - 1) * 100
            }
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
        tickers = [("BTC", "비트코인", "UPBIT", "crypto")] # BTC 우선
        for m in res:
            if m['market'].startswith('KRW-') and m['market'] != 'KRW-BTC':
                tickers.append((m['market'].split('-')[1], m['korean_name'], "UPBIT", "crypto"))
    else:
        df = fdr.StockListing('KRX') if "국내" in market else fdr.StockListing('NASDAQ')
        tickers = [(row['Code' if "국내" in market else 'Symbol'], row['Name' if "국내" in market else 'Symbol'], "KRX" if "국내" in market else "NASDAQ", "korea" if "국내" in market else "america") for _, row in df.head(top_n).iterrows()]

    # 스캔 시작
    total = len(tickers[:top_n])
    for i, (sym, name, exch, scr) in enumerate(tickers[:top_n]):
        progress_bar.progress((i + 1) / total)
        status_text.text(f"분석 중: {name} ({sym})")
        
        res = get_recovery_signal(sym, scr, exch, interval_map[tf_choice])
        if res:
            st.success(f"🎯 **{name}({sym})** 포착! (하단선 돌파 후 복귀)")
            found_list.append({
                "종목": name, 
                "심볼": sym, 
                "현재가": f"{res['price']:,.0f}", 
                "1번하단선": f"{res['l1']:,.0f}",
                "이번달저가": f"{res['low']:,.0f}",
                "복귀율": f"{res['recovery_pct']:.2f}%"
            })
        time.sleep(0.01)

    status_text.text("✅ 스캔 완료!")

    if found_list:
        st.divider()
        st.dataframe(pd.DataFrame(found_list), use_container_width=True)
    else:
        st.warning("조건(하단1선 이탈 후 복귀)을 만족하는 종목이 현재 없습니다.")
