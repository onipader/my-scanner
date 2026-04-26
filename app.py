import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Signal Sync Scanner", layout="wide")
st.title("🎯 트레이딩뷰 '신호 일치' 스캐너")

with st.sidebar:
    st.header("⚙️ 필터 설정")
    market = st.selectbox("시장", ["업비트 코인", "국내주식", "미국주식"])
    tf_choice = st.selectbox("타임프레임", ["월봉", "주봉", "일봉", "4시간봉"])
    
    # 시가총액 범위 설정
    top_n = st.slider("시가총액 상위 몇 위까지 스캔할까요?", 50, 500, 100, step=50)
    
    tf_map = {"월봉": "1M", "주봉": "1W", "일봉": "", "4시간봉": "240"}
    st.info(f"시가총액 상위 {top_n}개 중 '매수' 신호가 뜬 종목을 찾습니다.")
    
    start_btn = st.button("🚀 신호 동기화 스캔 시작", use_container_width=True)

def get_synced_data(m_name, itv, limit):
    url_map = {"업비트 코인": "crypto", "국내주식": "korea", "미국주식": "america"}
    api_url = f"https://scanner.tradingview.com/{url_map[m_name]}/scan"
    
    # 🔹 exchange(거래소) 컬럼을 추가해서 필터링에 사용합니다.
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
        # 🔹 필터 강화: 이름에 'KRW'가 있고 거래소가 'UPBIT'인 것만!
        payload["filter"].append({"left": "name", "operation": "match", "right": "KRW"})
        payload["filter"].append({"left": "exchange", "operation": "equal", "right": "UPBIT"})
    elif m_name == "미국주식":
        payload["filter"].append({"left": "type", "operation": "in_range", "right": ["stock", "dr", "fund"]})

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
        if score > 0.1:
            results.append({
                "종목명": d[3], # 더 읽기 쉬운 description 사용
                "신호": "Strong Buy" if score > 0.5 else "Buy",
                "현재가": f"{d[1]:,.0f}" if d[1] > 100 else f"{d[1]:,.2f}",
                "하단선": f"{d[2]:,.0f}" if d[2] else "N/A"
            })

    if results:
        st.table(pd.DataFrame(results))
        st.success(f"상위 {top_n}개 중 {len(results)}개 종목 포착!")
    else:
        st.warning(f"상위 {top_n}개 중 현재 'BUY' 신호가 뜬 종목이 없습니다.")
