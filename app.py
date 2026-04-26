import streamlit as st
import requests
import pandas as pd

# 1. 화면 구성 (깔끔하게)
st.set_page_config(page_title="왕초보용 필승 스캐너", layout="wide")
st.title("🚀 돈 되는 우량주 스캐너 (Double BB 전략)")

# 2. 왼쪽 메뉴 설정
with st.sidebar:
    st.header("🔍 어디를 찾을까요?")
    market = st.selectbox("시장 선택", ["업비트 코인", "국내주식 (삼성전자 등)", "미국주식 (애플/테슬라)"])
    timeframe = st.selectbox("시간 간격", ["월봉 (길게 보기)", "주봉", "일봉", "4시간봉", "1시간봉", "5분봉"])
    
    # 시간 간격 변환
    tf_map = {"5분봉": "5", "1시간봉": "60", "4시간봉": "240", "일봉": "", "주봉": "1W", "월봉": "1M"}
    interval = tf_map[timeframe]

    # 국내주식일 때만 PER(저평가) 설정 보이기
    per_val = 15.0
    if "국내주식" in market:
        per_val = st.number_input("PER 15 이하만 보기 (저평가 종목)", value=15.0)

    st.divider()
    btn = st.button("🚀 종목 찾아내기!", use_container_width=True)

# 3. 실제 데이터 가져오는 로직 (에러 방지 강화)
def fetch_data(market_name, itv, p_filter):
    url_map = {
        "업비트 코인": "https://scanner.tradingview.com/crypto/scan",
        "국내주식 (삼성전자 등)": "https://scanner.tradingview.com/korea/scan",
        "미국주식 (애플/테슬라)": "https://scanner.tradingview.com/america/scan"
    }
    m_type = {"업비트 코인": "crypto", "국내주식 (삼성전자 등)": "korea", "미국주식 (애플/테슬라)": "america"}
    
    # 가져올 항목들
    cols = ["close", "BB.lower", "low", "market_cap_basic", "description", "name"]
    if "국내주식" in market_name: cols.append("price_earnings_ttm")

    # 타임프레임 적용
    final_cols = [f"{c}|{itv}" if itv and c not in ["description", "name", "market_cap_basic", "price_earnings_ttm"] else c for c in cols]

    payload = {
        "filter": [],
        "markets": [m_type[market_name]],
        "columns": final_cols,
        "sort": {"column": "market_cap_basic", "direction": "desc"}, # 큰 회사부터
        "range": [0, 100] # 상위 100개 검사
    }
    
    if "국내주식" in market_name:
        payload["filter"].append({"left": "price_earnings_ttm", "operation": "less", "right": p_filter})

    try:
        r = requests.post(url_map[market_name], json=payload).json()
        return r.get('data', [])
    except:
        return []

# 4. 화면 출력
if btn:
    st.write(f"### 🎯 {market}에서 찾아낸 대박 후보")
    raw = fetch_data(market, interval, per_val)
    
    results = []
    for item in raw:
        d = item['d']
        if d[0] is None or d[1] is None: continue # 데이터 없으면 패스
        
        # 현재가 > 하단선 이고 저가 < 하단선(2% 유격) 인 것만!
        if d[0] > d[1] and d[2] <= d[1] * 1.02:
            row = {
                "이름": d[4] if d[4] else d[5],
                "현재가격": f"{d[0]:,.0f}원" if d[0] > 100 else f"{d[0]:.2f}$",
                "하단선": f"{d[1]:,.0f}",
                "시가총액": f"{d[3]/100000000:,.0f}억" if d[3] else "정보없음"
            }
            if "국내주식" in market:
                row["PER(저평가)"] = round(d[6], 1) if d[6] else "N/A"
            results.append(row)

    if results:
        st.table(pd.DataFrame(results))
        st.success(f"현재 조건에 딱 맞는 종목 {len(results)}개를 찾았습니다!")
    else:
        st.warning("지금은 조건에 맞는 종목이 없네요. 시간 간격을 '일봉'이나 '주봉'으로 바꿔보세요!")
