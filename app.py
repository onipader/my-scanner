import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="차트 신호 동기화 스캐너", layout="wide")
st.title("🎯 트레이딩뷰 'BUY 신호' 일치 스캐너")

with st.sidebar:
    st.header("⚙️ 필터 설정")
    market = st.selectbox("시장", ["업비트 코인", "국내주식", "미국주식"])
    tf_choice = st.selectbox("타임프레임", ["월봉", "주봉", "일봉", "4시간봉"])
    tf_map = {"월봉": "1M", "주봉": "1W", "일봉": "", "4시간봉": "240"}
    
    st.divider()
    st.info("차트의 '테크니컬 지표'가 매수(Buy) 이상인 종목만 추출합니다.")
    start_btn = st.button("🚀 신호 동기화 스캔 시작", use_container_width=True)

def get_synced_data(m_name, itv):
    url_map = {"업비트 코인": "crypto", "국내주식": "korea", "미국주식": "america"}
    api_url = f"https://scanner.tradingview.com/{url_map[m_name]}/scan"
    
    # 🔹 핵심: 트레이딩뷰의 종합 추천 점수(Recommend.All)를 가져옵니다.
    cols = ["Recommend.All", "close", "BB.lower", "low", "description", "name"]
    actual_cols = [f"{c}|{itv}" if itv and c not in ["description", "name"] else c for c in cols]

    payload = {
        "filter": [{"left": f"Recommend.All|{itv}" if itv else "Recommend.All", "operation": "greater", "right": 0.1}],
        "markets": [url_map[m_name]],
        "columns": actual_cols,
        "sort": {"column": "market_cap_basic", "direction": "desc"},
        "range": [0, 100]
    }
    
    if m_name == "업비트 코인":
        payload["filter"].append({"left": "name", "operation": "match", "right": "KRW"})

    try:
        res = requests.post(api_url, json=payload, timeout=10).json()
        return res.get('data', [])
    except: return []

if start_btn:
    raw = get_synced_data(market, interval := tf_map[tf_choice])
    results = []
    for item in raw:
        d = item['d']
        # 추천 점수가 '매수(Buy)' 구간인 종목만 필터링
        score = d[0]
        status = "Strong Buy" if score > 0.5 else "Buy" if score > 0.1 else "Neutral"
        
        if status in ["Buy", "Strong Buy"]:
            results.append({
                "종목명": d[4],
                "현재 신호": status,
                "현재가": f"{d[1]:,.0f}" if d[1] > 100 else f"{d[1]:,.2f}",
                "하단선": f"{d[2]:,.0f}"
            })

    if results:
        st.table(pd.DataFrame(results))
        st.success(f"차트 신호와 일치하는 {len(results)}개 종목을 찾았습니다.")
    else:
        st.warning("현재 해당 타임프레임에서 'BUY' 신호가 뜬 우량주가 없습니다.")
