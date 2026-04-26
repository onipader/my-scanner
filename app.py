import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Global Market Scanner", layout="wide")
st.title("📊 통합 마켓 스캐너 (Double BB 전략)")

# --- 사이드바 설정 ---
with st.sidebar:
    st.header("⚙️ 스캔 설정")
    # 1. 시장 선택
    market_choice = st.selectbox("대상 시장", ["업비트 코인", "국내주식 (KRX)", "미국주식 (NASDAQ/NYSE)"])
    
    # 2. 타임프레임 (5분 ~ 월)
    tf_map = {"5분봉": "5", "1시간봉": "60", "4시간봉": "240", "일봉": "", "주봉": "1W", "월봉": "1M"}
    selected_tf = st.selectbox("타임프레임", list(tf_map.keys()), index=5)
    interval = tf_map[selected_tf]

    # 3. 시가총액 순위 및 필터
    top_n = st.slider("스캔 대상 (시총 상위 N개)", 50, 500, 100)
    
    per_limit = 100.0
    if "국내주식" in market_choice:
        per_limit = st.number_input("최대 PER (이하만 추출)", value=15.0)

    st.divider()
    start_btn = st.button("🚀 전체 시장 스캔 시작", use_container_width=True)

def get_market_data(market, interval, limit, per_val):
    # 시장별 API 설정
    m_cfg = {
        "업비트 코인": {"url": "https://scanner.tradingview.com/crypto/scan", "m": "crypto"},
        "국내주식 (KRX)": {"url": "https://scanner.tradingview.com/korea/scan", "m": "korea"},
        "미국주식 (NASDAQ/NYSE)": {"url": "https://scanner.tradingview.com/america/scan", "m": "america"}
    }
    cfg = m_cfg[market]
    
    # 기본 컬럼 구성
    cols = ["close", "BB.lower", "low", "market_cap_basic", "description"]
    if "국내주식" in market: cols.append("price_earnings_ttm") # PER 추가

    # 타임프레임 적용 컬럼 생성
    actual_cols = [f"{c}|{interval}" if (interval and c not in ["description", "market_cap_basic", "price_earnings_ttm"]) else c for c in cols]

    payload = {
        "filter": [],
        "options": {"lang": "ko"},
        "markets": [cfg["m"]],
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": actual_cols,
        "sort": {"column": "market_cap_basic", "direction": "desc"}, # 시총 순 정렬
        "range": [0, limit]
    }
    
    if "국내주식" in market:
        payload["filter"].append({"left": "price_earnings_ttm", "operation": "less", "right": per_val})

    try:
        res = requests.post(cfg["url"], json=payload, timeout=15).json()
        return res.get('data', [])
    except:
        return []

if start_btn:
    st.write(f"### 🔎 {market_choice} ({selected_tf}) 분석 결과")
    data = get_market_data(market_choice, interval, top_n, per_limit)
    
    found = []
    for item in data:
        d = item['d']
        if None in d[:3]: continue # 필수 데이터 누락 시 스킵
        
        curr_c, bb_low, curr_l, mcap, desc = d[0], d[1], d[2], d[3], d[4]
        
        # 🎯 전략 판정 (저가 <= 하단선 * 1.02 AND 현재가 > 하단선)
        if curr_c > bb_low and curr_l <= bb_low * 1.02:
            res_dict = {
                "종목명": desc,
                "현재가": f"{curr_c:,.2f}" if curr_c < 1000 else f"{curr_c:,.0f}",
                "1번 하단선": f"{bb_low:,.0f}",
                "시가총액": f"{mcap/100000000:,.0f}억" if mcap else "N/A"
            }
            if "국내주식" in market_choice:
                res_dict["PER"] = round(d[5], 2) if d[5] else "N/A"
            found.append(res_dict)

    if found:
        st.success(f"{len(found)}개 종목 포착!")
        st.table(pd.DataFrame(found))
    else:
        st.warning("조건에 맞는 종목이 없습니다. 설정을 변경해 보세요.")
