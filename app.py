import streamlit as st
import requests
import pandas as pd

# 1. 기본 설정
st.set_page_config(page_title="Ultimate Global Scanner", layout="wide")
st.title("🚀 통합 마켓 스캐너 (Double BB 전략)")

# 2. 사이드바 - 지치셨으니 아주 단순하게 만들었습니다.
with st.sidebar:
    st.header("⚙️ 설정")
    market = st.selectbox("어디를 스캔할까요?", ["업비트 코인", "국내주식", "미국주식"])
    tf_choice = st.selectbox("시간 간격", ["월봉", "주봉", "일봉", "4시간봉", "1시간봉"])
    
    # 내부 변환
    tf_map = {"월봉": "1M", "주봉": "1W", "일봉": "", "4시간봉": "240", "1시간봉": "60"}
    interval = tf_map[tf_choice]
    
    st.divider()
    # 🔹 시총 상위 250개까지 넉넉하게 훑도록 설정
    st.info("시가총액이 큰 종목부터 250개를 분석합니다.")
    start_btn = st.button("🚀 스캔 시작 (한 번만 클릭!)", use_container_width=True)

# 3. 데이터 가져오기 로직
def get_final_data(m_choice, itv):
    url_map = {
        "업비트 코인": "https://scanner.tradingview.com/crypto/scan",
        "국내주식": "https://scanner.tradingview.com/korea/scan",
        "미국주식": "https://scanner.tradingview.com/america/scan"
    }
    m_type = {"업비트 코인": "crypto", "국내주식": "korea", "미국주식": "america"}
    
    # 📌 필수 데이터 컬럼
    cols = ["close", "BB.lower", "low", "market_cap_basic", "description", "name"]
    if m_choice == "국내주식": cols.append("price_earnings_ttm") # PER 추가

    # 타임프레임 적용
    actual_cols = [f"{c}|{itv}" if itv and c not in ["description", "name", "market_cap_basic", "price_earnings_ttm"] else c for c in cols]

    payload = {
        "filter": [],
        "markets": [m_type[m_choice]],
        "columns": actual_cols,
        "sort": {"column": "market_cap_basic", "direction": "desc"}, # 시총 큰 순서
        "range": [0, 250] # 250개 종목 스캔
    }

    # 🔹 불필요한 잡주 제거 필터
    if m_choice == "업비트 코인":
        payload["filter"].append({"left": "name", "operation": "match", "right": "KRW"}) # 원화 마켓만
    elif m_choice == "미국주식":
        payload["filter"].append({"left": "type", "operation": "in_range", "right": ["stock", "dr", "fund"]})

    try:
        res = requests.post(url_map[m_choice], json=payload, timeout=10).json()
        return res.get('data', [])
    except:
        return []

# 4. 화면 출력 부분
if start_btn:
    with st.spinner("시장 데이터를 정밀 분석 중입니다..."):
        raw = get_final_data(market, interval)
        
        final_results = []
        for item in raw:
            d = item['d']
            # 데이터 누락 방지
            if d[0] is None or d[1] is None or d[2] is None: continue
            
            # 🎯 사용자님의 핵심 전략 (현재가 > 하단선 AND 저가 <= 하단선 * 1.05)
            # 비트코인처럼 힘이 좋은 종목을 위해 5%의 여유를 줬습니다.
            if d[0] > d[1] and d[2] <= d[1] * 1.05:
                row = {
                    "종목명": d[4] if d[4] else d[5],
                    "현재가": f"{d[0]:,.0f}" if d[0] > 100 else f"{d[0]:,.2f}",
                    "1번 하단선": f"{d[1]:,.0f}",
                    "시가총액": f"{d[3]/100000000:,.0f}억" if d[3] else "N/A"
                }
                if market == "국내주식":
                    row["PER"] = round(d[6], 1) if d[6] else "N/A"
                final_results.append(row)

        if final_results:
            st.write(f"### 🎯 {market} ({tf_choice}) 포착 종목")
            st.table(pd.DataFrame(final_results))
            st.success(f"조건에 맞는 우량 종목 {len(final_results)}개를 찾았습니다!")
        else:
            st.warning("현재 조건에 맞는 종목이 없습니다. 시간 간격을 바꿔보세요.")
