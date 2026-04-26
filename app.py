import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Official Signal Sync", layout="wide")
st.title("🎯 트레이딩뷰 '신호 일치' 정밀 검색기")

with st.sidebar:
    st.header("⚙️ 검색 설정")
    market = st.selectbox("시장", ["업비트 코인", "국내주식", "미국주식"])
    tf_choice = st.selectbox("타임프레임", ["월봉", "주봉", "일봉", "4시간봉"])
    top_n = st.number_input("스캔 범위 (상위 N개)", min_value=50, max_value=500, value=100, step=50)
    
    tf_map = {"월봉": "1M", "주봉": "1W", "일봉": "", "4시간봉": "240"}
    st.info("차트 바늘이 'BUY' 이상인 종목만 정밀 필터링합니다.")
    start_btn = st.button("🚀 신호 검색 시작", use_container_width=True)

def get_synced_data(m_name, itv, limit):
    url_map = {"업비트 코인": "crypto", "국내주식": "korea", "미국주식": "america"}
    api_url = f"https://scanner.tradingview.com/{url_map[m_name]}/scan"
    
    cols = ["Recommend.All", "close", "BB.lower", "description", "name", "exchange"]
    actual_cols = [f"{c}|{itv}" if itv and c not in ["description", "name", "exchange"] else c for c in cols]

    payload = {
        "filter": [],
        "markets": [url_map[m_name]],
        "columns": actual_cols,
        "sort": {"column": "market_cap_basic", "direction": "desc"},
        "range": [0, limit]
    }
    
    if m_name == "업비트 코인":
        payload["filter"].append({"left": "name", "operation": "match", "right": "KRW"})
        payload["filter"].append({"left": "exchange", "operation": "equal", "right": "UPBIT"})

    try:
        res = requests.post(api_url, json=payload, timeout=10).json()
        return res.get('data', [])
    except: return []

if start_btn:
    raw = get_synced_data(market, interval := tf_map[tf_choice], top_n)
    results = []
    
    for item in raw:
        d = item['d']
        if None in d[:3]: continue
        
        score = d[0]
        
        # 🔹 핵심: 차트 바늘이 'Neutral'을 완전히 벗어나는 0.15 이상만 추출
        # 이제 비트코인 캐시(BCH)는 이 필터를 통과하지 못합니다.
        if score >= 0.15: 
            status = "Strong Buy" if score > 0.5 else "Buy"
            results.append({
                "종목명": d[3],
                "현재 상태": status,
                "현재가": f"{d[1]:,.0f}" if d[1] > 100 else f"{d[1]:,.2f}",
                "하단선": f"{d[2]:,.0f}"
            })

    if results:
        st.table(pd.DataFrame(results))
        st.success(f"차트와 일치하는 {len(results)}개 종목을 찾았습니다.")
    else:
        st.warning("현재 차트 바늘이 'BUY'를 가리키는 종목이 없습니다.")
