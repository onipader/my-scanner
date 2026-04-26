import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Real Chart Signal Scanner", layout="wide")
st.title("🎯 실시간 차트 'Buy' 신호 종목 검색기")

with st.sidebar:
    st.header("⚙️ 검색 설정")
    market = st.selectbox("시장 선택", ["업비트 코인", "국내주식", "미국주식"])
    tf_choice = st.selectbox("타임프레임 (차트와 맞추세요)", ["월봉", "주봉", "일봉", "4시간봉"])
    top_n = st.number_input("스캔 범위 (시총 상위 N개)", min_value=50, max_value=500, value=100, step=50)
    
    tf_map = {"월봉": "1M", "주봉": "1W", "일봉": "", "4시간봉": "240"}
    st.info("차트의 'Technicals' 바늘이 BUY 이상인 종목만 추출합니다.")
    start_btn = st.button("🚀 진짜 신호 종목 찾기", use_container_width=True)

def get_real_signal(m_name, itv, limit):
    url_map = {"업비트 코인": "crypto", "국내주식": "korea", "미국주식": "america"}
    api_url = f"https://scanner.tradingview.com/{url_map[m_name]}/scan"
    
    # 🔹 핵심: 'recommendation' 필드를 직접 가져옵니다. (Buy, Neutral, Sell 등 문자열값)
    signal_col = f"recommendation|{itv}" if itv else "recommendation"
    cols = [signal_col, "close", "BB.lower", "description", "name"]

    payload = {
        "filter": [
            # 🔹 차트 바늘이 'BUY'나 'STRONG_BUY'인 것만 서버 단계에서 필터링
            {"left": signal_col, "operation": "in_range", "right": [1, 2]} 
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
    raw = get_real_signal(market, tf_map[tf_choice], top_n)
    results = []
    
    # 트레이딩뷰의 문자열 신호 매핑
    status_map = {2: "Strong Buy", 1: "Buy", 0: "Neutral", -1: "Sell", -2: "Strong Sell"}
    
    for item in raw:
        d = item['d']
        results.append({
            "종목명": d[3],
            "현재 신호": status_map.get(int(d[0]), "Unknown"),
            "현재가": f"{d[1]:,.0f}" if d[1] > 100 else f"{d[1]:,.2f}",
            "볼밴 하단": f"{d[2]:,.0f}" if d[2] else "N/A"
        })

    if results:
        st.table(pd.DataFrame(results))
        st.success(f"현재 차트에서 'Buy' 신호가 확인된 {len(results)}개 종목입니다.")
    else:
        st.warning("현재 선택하신 타임프레임에서 'Buy' 신호가 뜬 종목이 없습니다.")
