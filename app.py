import streamlit as st
import requests
import pandas as pd

# 페이지 설정
st.set_page_config(page_title="Ultimate Market Scanner", layout="wide")
st.title("📊 올인원 마켓 스캐너 (오류 수정 완료)")

# --- 사이드바 설정 ---
with st.sidebar:
    st.header("⚙️ 스캔 설정")
    market_choice = st.selectbox("대상 시장", ["업비트 코인", "국내주식 (KRX)", "미국주식 (NASDAQ/NYSE)"])
    
    tf_display = ["5분봉", "1시간봉", "4시간봉", "일봉", "주봉", "월봉"]
    tf_map = {"5분봉": "5", "1시간봉": "60", "4시간봉": "240", "일봉": "", "주봉": "1W", "월봉": "1M"}
    selected_tf = st.selectbox("타임프레임", tf_display, index=5)
    interval = tf_map[selected_tf]

    top_n = st.slider("시가총액 상위 N개 스캔", 50, 500, 100)
    
    per_filter = 100.0
    if "국내주식" in market_choice:
        per_filter = st.number_input("최대 PER (이하만)", value=15.0)

    st.divider()
    start_btn = st.button("🚀 스캔 시작", use_container_width=True)

# --- 핵심 함수 ---
def get_tv_data(market, interval, limit, per_limit):
    config = {
        "업비트 코인": {"url": "https://scanner.tradingview.com/crypto/scan", "m": "crypto"},
        "국내주식 (KRX)": {"url": "https://scanner.tradingview.com/korea/scan", "m": "korea"},
        "미국주식 (NASDAQ/NYSE)": {"url": "https://scanner.tradingview.com/america/scan", "m": "america"}
    }
    
    m_info = config[market]
    # 필터링 및 정렬 조건 (시가총액 순)
    payload = {
        "filter": [],
        "options": {"lang": "ko"},
        "markets": [m_info["m"]],
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": ["close", "BB.lower", "low", "market_cap_basic", "description"],
        "sort": {"column": "market_cap_basic", "direction": "desc"},
        "range": [0, limit]
    }

    # 타임프레임 적용
    if interval:
        payload["columns"] = [f"{c}|{interval}" if c not in ["description", "market_cap_basic"] else c for c in payload["columns"]]
    
    if "국내주식" in market:
        payload["columns"].append("price_earnings_ttm")
        payload["filter"].append({"left": "price_earnings_ttm", "operation": "less", "right": per_limit})

    try:
        res = requests.post(m_info["url"], json=payload, timeout=10).json()
        return res.get('data', [])
    except:
        return []

if start_btn:
    st.write(f"### 🔎 {market_choice} 분석 결과")
    raw_data = get_tv_data(market_choice, interval, top_n, per_filter)
    
    found_list = []
    for item in raw_data:
        d = item['d']
        # 🔹 에러 방지: 데이터가 하나라도 None이면 건너뜁니다.
        if d[0] is None or d[1] is None or d[2] is None:
            continue
            
        curr_c, bb_low, curr_l, mcap, desc = d[0], d[1], d[2], d[3], d[4]
        
        # 🎯 전략 판정 (저가 <= 하단선 AND 현재가 > 하단선)
        if curr_c > bb_low and curr_l <= bb_low * 1.02:
            found_list.append({
                "종목명": desc,
                "현재가": f"{curr_c:,.0f}" if curr_c > 10 else f"{curr_c:,.4f}",
                "하단선": f"{bb_low:,.0f}",
                "시가총액": f"{mcap/100000000:,.0f}억" if mcap else "N/A"
            })

    if found_list:
        st.table(pd.DataFrame(found_list))
    else:
        st.warning("조건에 맞는 종목을 찾지 못했습니다.")
