import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Real Signal Finder", layout="wide")
st.title("🎯 차트 'BUY' 글자 일치 검색기")

with st.sidebar:
    st.header("⚙️ 검색 설정")
    market = st.selectbox("시장", ["업비트 코인", "국내주식", "미국주식"])
    tf_choice = st.selectbox("타임프레임", ["월봉", "주봉", "일봉", "4시간봉"])
    top_n = st.number_input("스캔 범위 (상위 N개)", min_value=50, max_value=500, value=100, step=50)
    
    tf_map = {"월봉": "1M", "주봉": "1W", "일봉": "", "4시간봉": "240"}
    st.info("차트 상단에 'BUY'가 선명하게 뜬 종목만 찾아냅니다.")
    start_btn = st.button("🚀 진짜 신호 종목 리스트업", use_container_width=True)

def get_accurate_signal(m_name, itv, limit):
    url_map = {"업비트 코인": "crypto", "국내주식": "korea", "미국주식": "america"}
    api_url = f"https://scanner.tradingview.com/{url_map[m_name]}/scan"
    
    sig_col = f"Recommend.All|{itv}" if itv else "Recommend.All"
    cols = [sig_col, "close", "BB.lower", "description", "name"]

    payload = {
        "filter": [
            # 🔹 기준을 0.25로 강화 (비트코인 캐시 같은 '뉴트럴' 차단용)
            {"left": sig_col, "operation": "greater", "right": 0.25}
        ],
        "markets": [url_map[m_name]],
        "columns": cols,
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
    raw = get_accurate_signal(market, tf_map[tf_choice], top_n)
    
    if not raw:
        st.warning("현재 확실한 'BUY' 신호가 확인된 종목이 없습니다.")
    else:
        results = []
        for item in raw:
            d = item.get('d', [])
            results.append({
                "종목명": d[3],
                "신호 강도": "Strong Buy" if d[0] > 0.5 else "Buy",
                "현재가": f"{d[1]:,.1f}",
                "볼밴 하단": f"{d[2]:,.1f}" if d[2] else "N/A"
            })

        if results:
            # 신호 강도순으로 정렬하여 출력
            df = pd.DataFrame(results)
            st.table(df)
            st.success(f"차트의 'BUY' 글자와 일치하는 {len(results)}개 종목을 찾았습니다.")
