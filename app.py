import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Signal Sync Scanner", layout="wide")
st.title("🎯 트레이딩뷰 '신호 일치' 스캐너")

with st.sidebar:
    st.header("⚙️ 필터 설정")
    market = st.selectbox("시장", ["업비트 코인", "국내주식", "미국주식"])
    tf_choice = st.selectbox("타임프레임", ["월봉", "주봉", "일봉", "4시간봉"])
    
    # 시가총액 상위 범위
    top_n = st.slider("스캔 범위 (상위 N개)", 50, 500, 100, step=50)
    
    tf_map = {"월봉": "1M", "주봉": "1W", "일봉": "", "4시간봉": "240"}
    st.info("선택한 타임프레임에서 '매수' 신호가 있는 종목을 찾습니다.")
    
    start_btn = st.button("🚀 스캔 시작", use_container_width=True)

def get_tradingview_data(m_name, itv, limit):
    url_map = {"업비트 코인": "crypto", "국내주식": "korea", "미국주식": "america"}
    api_url = f"https://scanner.tradingview.com/{url_map[m_name]}/scan"
    
    # 기본 지표 데이터 요청
    cols = ["Recommend.All", "close", "BB.lower", "description", "name"]
    actual_cols = [f"{c}|{itv}" if itv and c not in ["description", "name"] else c for c in cols]

    payload = {
        "filter": [],
        "markets": [url_map[m_name]],
        "columns": actual_cols,
        "sort": {"column": "market_cap_basic", "direction": "desc"},
        "range": [0, limit]
    }
    
    # 업비트 종목만 필터링
    if m_name == "업비트 코인":
        payload["filter"].append({"left": "name", "operation": "match", "right": "KRW"})

    try:
        res = requests.post(api_url, json=payload, timeout=10).json()
        return res.get('data', [])
    except:
        return []

if start_btn:
    raw = get_tradingview_data(market, interval := tf_map[tf_choice], top_n)
    results = []
    
    for item in raw:
        d = item['d']
        if None in d[:3]: continue
        
        # 추천 점수가 0보다 크면(매수권) 리스트에 추가
        if d[0] > 0:
            results.append({
                "종목명": d[3],
                "신호 강도": "Strong Buy" if d[0] > 0.5 else "Buy",
                "현재가": f"{d[1]:,.0f}" if d[1] > 100 else f"{d[1]:,.2f}",
                "볼밴 하단": f"{d[2]:,.0f}" if d[2] else "N/A"
            })

    if results:
        df = pd.DataFrame(results)
        st.table(df)
        st.success(f"조건에 맞는 종목 {len(results)}개를 찾았습니다.")
    else:
        st.warning("현재 매수 신호가 있는 종목이 없습니다.")
