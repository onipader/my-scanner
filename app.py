import streamlit as st
import requests
import pandas as pd

# 1. 페이지 설정
st.set_page_config(page_title="Signal Sync Master", layout="wide")
st.title("🎯 트레이딩뷰 '신호 일치' 스캐너 (마스터 버전)")

# 2. 사이드바 설정
with st.sidebar:
    st.header("⚙️ 필터 설정")
    market = st.selectbox("시장 선택", ["업비트 코인", "국내주식", "미국주식"])
    tf_choice = st.selectbox("타임프레임", ["월봉", "주봉", "일봉", "4시간봉"])
    
    # 기능 1: 시가총액 범위 (50위 ~ 500위)
    top_n = st.slider("시가총액 스캔 범위", 50, 500, 100, step=50)
    
    # 기능 2: 신호 강도 슬라이더 (0.1이면 약한 매수도 포착, 0.3이면 강력 매수만)
    # 🔹 비트코인이 안 나오면 이 값을 0.1 이하로 낮춰보세요!
    sig_strength = st.slider("신호 포착 강도 (낮을수록 많이 잡힘)", 0.0, 0.5, 0.15, step=0.05)
    
    tf_map = {"월봉": "1M", "주봉": "1W", "일봉": "", "4시간봉": "240"}
    st.info(f"신호 점수가 {sig_strength} 이상인 종목만 보여줍니다.")
    
    start_btn = st.button("🚀 설정값으로 스캔 시작", use_container_width=True)

# 3. 데이터 엔진
def get_master_data(m_name, itv, limit):
    url_map = {"업비트 코인": "crypto", "국내주식": "korea", "미국주식": "america"}
    api_url = f"https://scanner.tradingview.com/{url_map[m_name]}/scan"
    
    # 지표 추천 점수, 현재가, 하단선, 이름, 거래소 데이터 요청
    cols = ["Recommend.All", "close", "BB.lower", "description", "name", "exchange"]
    actual_cols = [f"{c}|{itv}" if itv and c not in ["description", "name", "exchange"] else c for c in cols]

    payload = {
        "filter": [],
        "markets": [url_map[m_name]],
        "columns": actual_cols,
        "sort": {"column": "market_cap_basic", "direction": "desc"},
        "range": [0, limit]
    }
    
    # 업비트 원화 마켓만 필터링
    if m_name == "업비트 코인":
        payload["filter"].append({"left": "name", "operation": "match", "right": "KRW"})
        payload["filter"].append({"left": "exchange", "operation": "equal", "right": "UPBIT"})

    try:
        res = requests.post(api_url, json=payload, timeout=10).json()
        return res.get('data', [])
    except:
        return []

# 4. 결과 출력
if start_btn:
    raw = get_master_data(market, interval := tf_map[tf_choice], top_n)
    results = []
    
    for item in raw:
        d = item['d']
        if None in d[:3]: continue # 데이터 누락 시 스킵
        
        score = d[0]
        # 사용자 설정 강도(sig_strength)와 대조
        if score >= sig_strength:
            results.append({
                "종목명": d[3],
                "신호 점수": round(score, 3),
                "신호": "Strong Buy" if score > 0.5 else "Buy",
                "현재가": f"{d[1]:,.0f}" if d[1] > 100 else f"{d[1]:,.2f}",
                "하단선": f"{d[2]:,.0f}" if d[2] else "N/A"
            })

    if results:
        # 점수가 높은 순으로 정렬해서 출력
        df = pd.DataFrame(results).sort_values(by="신호 점수", ascending=False)
        st.table(df)
        st.success(f"조건에 맞는 종목 {len(results)}개를 찾았습니다!")
    else:
        st.warning(f"현재 강도({sig_strength}) 이상의 신호를 가진 종목이 없습니다. 강도를 낮춰보세요.")
