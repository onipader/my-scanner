import streamlit as st
import requests
import pandas as pd

# 1. 페이지 설정
st.set_page_config(page_title="통합 마켓 스캐너", layout="wide")
st.title("🚀 통합 마켓 스캐너 (Double BB 전략)")

# 2. 사이드바 설정 (이름을 단순화해서 에러 방지)
with st.sidebar:
    st.header("🔍 스캔 설정")
    market = st.selectbox("시장 선택", ["업비트 코인", "국내주식", "미국주식"])
    
    # 에러 방지를 위해 단순한 이름 사용
    tf_choice = st.selectbox("시간 간격", ["월봉", "주봉", "일봉", "4시간봉", "1시간봉"])
    tf_map = {"월봉": "1M", "주봉": "1W", "일봉": "", "4시간봉": "240", "1시간봉": "60"}
    interval = tf_map[tf_choice]

    per_limit = 15.0
    if market == "국내주식":
        per_limit = st.number_input("최대 PER (저평가 기준)", value=15.0)

    st.divider()
    btn = st.button("🚀 스캔 시작", use_container_width=True)

# 3. 데이터 로직
def get_data(m_name, itv, p_lim):
    urls = {
        "업비트 코인": "https://scanner.tradingview.com/crypto/scan",
        "국내주식": "https://scanner.tradingview.com/korea/scan",
        "미국주식": "https://scanner.tradingview.com/america/scan"
    }
    m_types = {"업비트 코인": "crypto", "국내주식": "korea", "미국주식": "america"}
    
    cols = ["close", "BB.lower", "low", "market_cap_basic", "description"]
    if m_name == "국내주식": cols.append("price_earnings_ttm")

    # 타임프레임 적용
    final_cols = [f"{c}|{itv}" if itv and c not in ["description", "market_cap_basic", "price_earnings_ttm"] else c for c in cols]

    payload = {
        "filter": [],
        "markets": [m_types[m_name]],
        "columns": final_cols,
        "sort": {"column": "market_cap_basic", "direction": "desc"},
        "range": [0, 100]
    }
    
    if m_name == "국내주식":
        payload["filter"].append({"left": "price_earnings_ttm", "operation": "less", "right": p_lim})

    try:
        r = requests.post(urls[m_name], json=payload, timeout=10).json()
        return r.get('data', [])
    except:
        return []

# 4. 결과 출력
if btn:
    st.write(f"### 🎯 {market} ({tf_choice}) 분석 결과")
    raw = get_data(market, interval, per_limit)
    
    found = []
    for item in raw:
        d = item['d']
        if d[0] is None or d[1] is None: continue
        
        # 전략: 현재가 > 하단선 AND 저가 <= 하단선(2% 유격)
        if d[0] > d[1] and d[2] <= d[1] * 1.02:
            res = {
                "종목명": d[4],
                "현재가": f"{d[0]:,.0f}" if d[0] > 100 else f"{d[0]:.2f}",
                "하단선": f"{d[1]:,.0f}",
                "시가총액": f"{d[3]/100000000:,.0f}억" if d[3] else "N/A"
            }
            if market == "국내주식":
                res["PER"] = round(d[5], 1) if d[5] else "N/A"
            found.append(res)

    if found:
        st.table(pd.DataFrame(found))
        st.success(f"조건에 맞는 종목 {len(found)}개를 찾았습니다!")
    else:
        st.warning("조건에 맞는 종목이 없습니다. 시간 간격을 바꿔보세요.")
