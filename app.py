import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Signal Sync Scanner", layout="wide")
st.title("🎯 트레이딩뷰 '신호 일치' 스캐너")

with st.sidebar:
    st.header("⚙️ 필터 설정")
    market = st.selectbox("시장", ["업비트 코인", "국내주식", "미국주식"])
    tf_choice = st.selectbox("타임프레임", ["월봉", "주봉", "일봉", "4시간봉"])
    tf_map = {"월봉": "1M", "주봉": "1W", "일봉": "", "4시간봉": "240"}
    st.info("차트의 '종합 지표'가 매수(Buy)인 우량주만 찾아냅니다.")
    start_btn = st.button("🚀 신호 동기화 스캔 시작", use_container_width=True)

def get_clean_data(m_name, itv):
    url_map = {"업비트 코인": "crypto", "국내주식": "korea", "미국주식": "america"}
    api_url = f"https://scanner.tradingview.com/{url_map[m_name]}/scan"
    
    cols = ["Recommend.All", "close", "BB.lower", "description", "name"]
    # 타임프레임 적용
    actual_cols = [f"{c}|{itv}" if itv and c not in ["description", "name"] else c for c in cols]

    payload = {
        "filter": [],
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
    raw = get_clean_data(market, interval := tf_map[tf_choice])
    results = []
    for item in raw:
        d = item['d']
        # 🔹 [에러 방지] 데이터가 하나라도 비어있으면 건너뜁니다
        if None in d[:3]: continue
        
        score = d[0]
        # 점수에 따른 신호 분류
        if score > 0.1: # Buy 이상만 포착
            results.append({
                "종목명": d[3] if d[3] else d[4],
                "신호": "Strong Buy" if score > 0.5 else "Buy",
                "현재가": f"{d[1]:,.0f}" if d[1] > 100 else f"{d[1]:,.2f}",
                "하단선": f"{d[2]:,.0f}" if d[2] else "N/A"
            })

    if results:
        st.table(pd.DataFrame(results))
        st.success(f"차트 신호와 일치하는 {len(results)}개 종목 포착!")
    else:
        st.warning("현재 'BUY' 신호가 뜬 우량 종목이 없습니다.")
