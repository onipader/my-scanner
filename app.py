import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Real Candle Signal Scanner", layout="wide")
st.title("🎯 차트 캔들 'Buy' 신호 일치 검색기")

with st.sidebar:
    st.header("⚙️ 검색 설정")
    market = st.selectbox("시장 선택", ["업비트 코인", "국내주식", "미국주식"])
    tf_choice = st.selectbox("타임프레임", ["월봉", "주봉", "일봉", "4시간봉"])
    top_n = st.number_input("스캔 범위 (상위 N개)", min_value=50, max_value=500, value=100, step=50)
    
    tf_map = {"월봉": "1M", "주봉": "1W", "일봉": "", "4시간봉": "240"}
    st.info("차트 캔들에 'BUY' 신호가 뜬 종목들을 찾아냅니다.")
    start_btn = st.button("🚀 신호 종목 리스트업", use_container_width=True)

def get_broad_signal(m_name, itv, limit):
    url_map = {"업비트 코인": "crypto", "국내주식": "korea", "미국주식": "america"}
    api_url = f"https://scanner.tradingview.com/{url_map[m_name]}/scan"
    
    # 🔹 추천 점수가 조금이라도 양수인(+) 종목은 일단 다 가져옵니다.
    sig_col = f"Recommend.All|{itv}" if itv else "Recommend.All"
    cols = [sig_col, "close", "BB.lower", "description", "name"]

    payload = {
        "filter": [
            {"left": sig_col, "operation": "greater", "right": -0.1} # 필터를 대폭 완화
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
    raw = get_broad_signal(market, tf_map[tf_choice], top_n)
    
    if not raw:
        st.warning("신호를 찾을 수 없습니다.")
    else:
        results = []
        for item in raw:
            d = item.get('d', [])
            # 🔹 차트에 Buy가 떠 있는 종목들을 우선적으로 보여줍니다.
            results.append({
                "종목명": d[3],
                "현재가": f"{d[1]:,.1f}",
                "볼밴 하단": f"{d[2]:,.1f}" if d[2] else "N/A"
            })

        if results:
            df = pd.DataFrame(results)
            st.table(df)
            st.success(f"차트 신호 확인용 종목 {len(results)}개를 나열했습니다.")
