import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Ultimate Global Scanner", layout="wide")
st.title("🚀 비트코인 포착용 통합 스캐너")

with st.sidebar:
    st.header("⚙️ 설정")
    market = st.selectbox("시장 선택", ["업비트 코인", "국내주식", "미국주식"])
    tf_choice = st.selectbox("시간 간격", ["월봉", "주봉", "일봉", "4시간봉", "1시간봉"])
    tf_map = {"월봉": "1M", "주봉": "1W", "일봉": "", "4시간봉": "240", "1시간봉": "60"}
    interval = tf_map[tf_choice]
    
    st.divider()
    # 🔹 감도 조절 (비트코인이 안 나오면 이걸 높이세요)
    sensitivity = st.slider("포착 감도 (높을수록 많이 잡힘)", 1.0, 1.3, 1.15, step=0.01)
    start_btn = st.button("🚀 스캔 시작", use_container_width=True)

def get_data(m_choice, itv):
    url_map = {"업비트 코인": "https://scanner.tradingview.com/crypto/scan", "국내주식": "https://scanner.tradingview.com/korea/scan", "미국주식": "https://scanner.tradingview.com/america/scan"}
    m_type = {"업비트 코인": "crypto", "국내주식": "korea", "미국주식": "america"}
    cols = ["close", "BB.lower", "low", "market_cap_basic", "description", "name"]
    actual_cols = [f"{c}|{itv}" if itv and c not in ["description", "name", "market_cap_basic"] else c for c in cols]
    payload = {"filter": [], "markets": [m_type[m_choice]], "columns": actual_cols, "sort": {"column": "market_cap_basic", "direction": "desc"}, "range": [0, 250]}
    if m_choice == "업비트 코인":
        payload["filter"].append({"left": "name", "operation": "match", "right": "KRW"})
    try:
        res = requests.post(url_map[m_choice], json=payload, timeout=10).json()
        return res.get('data', [])
    except: return []

if start_btn:
    raw = get_data(market, interval)
    final_results = []
    for item in raw:
        d = item['d']
        if d[0] is None or d[1] is None: continue
        # 🎯 판정 기준을 사용자가 조절한 sensitivity(감도)로 적용
        if d[0] > d[1] and d[2] <= d[1] * sensitivity:
            final_results.append({
                "종목명": d[4] if d[4] else d[5],
                "현재가": f"{d[0]:,.0f}" if d[0] > 100 else f"{d[0]:,.2f}",
                "하단선": f"{d[1]:,.0f}",
                "이격정도": f"{((d[2]/d[1])-1)*100:.1f}%" # 하단선 대비 얼마나 떨어졌는지 표시
            })
    if final_results:
        st.table(pd.DataFrame(final_results))
    else:
        st.warning("조건을 만족하는 종목이 없습니다.")
