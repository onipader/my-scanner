import streamlit as st
import requests
import pandas as pd
import time

# 페이지 설정
st.set_page_config(page_title="Ultimate Market Scanner", layout="wide")

st.title("📊 올인원 마켓 스캐너 (Double BB 전략)")
st.markdown("사용자님의 **'하단선 이탈 후 복귀'** 로직을 국내/미국 주식 및 코인 전체에 적용합니다.")

# --- 사이드바 설정 ---
with st.sidebar:
    st.header("⚙️ 스캔 설정")
    
    # 1. 시장 선택
    market_choice = st.selectbox("대상 시장", ["업비트 코인", "국내주식 (KRX)", "미국주식 (NASDAQ/NYSE)"])
    
    # 2. 타임프레임 선택
    tf_display = ["5분봉", "1시간봉", "4시간봉", "일봉", "주봉", "월봉"]
    tf_map = {"5분봉": "5", "1시간봉": "60", "4시간봉": "240", "일봉": "", "주봉": "1W", "월봉": "1M"}
    selected_tf = st.selectbox("타임프레임", tf_display, index=5) # 기본 월봉
    interval = tf_map[selected_tf]

    # 3. 필터 및 정렬
    top_n = st.slider("시가총액 상위 N개 스캔", 50, 500, 100)
    
    # 국내주식 전용 저PER 필터
    per_filter = 100.0
    if "국내주식" in market_choice:
        per_filter = st.number_input("최대 PER (이하만 추출)", value=15.0)

    st.divider()
    start_btn = st.button("🚀 전체 시장 스캔 시작", use_container_width=True)

# --- 기능 함수 ---
def get_tradingview_data(market, interval, limit, per_limit):
    # 시장별 스캐너 주소 및 설정
    config = {
        "업비트 코인": {"url": "https://scanner.tradingview.com/crypto/scan", "screener": "crypto", "exchange": "UPBIT"},
        "국내주식 (KRX)": {"url": "https://scanner.tradingview.com/korea/scan", "screener": "korea", "exchange": "KRX"},
        "미국주식 (NASDAQ/NYSE)": {"url": "https://scanner.tradingview.com/america/scan", "screener": "america", "exchange": ""}
    }
    
    m_info = config[market]
    
    # 기본 컬럼 (현재가, 하단선, 저가, 시가총액)
    cols = ["close", "BB.lower", "low", "market_cap_basic", "name", "description"]
    if "국내주식" in market:
        cols.append("price_earnings_ttm") # PER 추가

    # 타임프레임 적용
    if interval != "":
        actual_cols = [f"{c}|{interval}" if c not in ["name", "description", "market_cap_basic", "price_earnings_ttm"] else c for c in cols]
    else:
        actual_cols = cols

    payload = {
        "filter": [],
        "options": {"lang": "ko"},
        "markets": [m_info["screener"]],
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": actual_cols,
        "sort": {"column": "market_cap_basic", "direction": "desc"}, # 시가총액 순 정렬
        "range": [0, limit]
    }

    # PER 필터 적용 (국내주식 한정)
    if "국내주식" in market:
        payload["filter"].append({"left": "price_earnings_ttm", "operation": "less", "right": per_limit})

    try:
        res = requests.post(m_info["url"], json=payload, timeout=10).json()
        return res.get('data', [])
    except:
        return []

# --- 메인 실행 ---
if start_btn:
    st.write(f"### 🔎 {market_choice} ({selected_tf}) 분석 결과")
    progress_bar = st.progress(0)
    
    raw_data = get_tradingview_data(market_choice, interval, top_n, per_filter)
    
    found_list = []
    
    if raw_data:
        for i, item in enumerate(raw_data):
            d = item['d']
            # 데이터 매핑 (API 리턴 순서에 맞춤)
            curr_c, bb_low, curr_l, mcap, s_name, desc = d[0], d[1], d[2], d[3], d[4], d[5]
            
            # 🎯 전략 판정: 현재가 > 하단선 AND 저가 <= 하단선 (약간의 오차 허용)
            # 비트코인 사례처럼 하단선이 따라 올라가는 경우를 위해 2% 유격을 줍니다.
            if curr_c > bb_low and curr_l <= bb_low * 1.02:
                found_list.append({
                    "종목명": desc if desc else s_name,
                    "현재가": f"{curr_c:,.0f}" if curr_c > 100 else f"{curr_c:,.4f}",
                    "1번 하단선": f"{bb_low:,.0f}",
                    "저가": f"{curr_l:,.0f}",
                    "시가총액": f"{mcap/100000000:,.0f}억" if mcap else "N/A"
                })
            progress_bar.progress((i + 1) / len(raw_data))

        if found_list:
            st.success(f"총 {len(found_list)}개의 종목이 포착되었습니다!")
            st.table(pd.DataFrame(found_list))
        else:
            st.warning("조건에 부합하는 종목이 없습니다. 타임프레임을 바꾸거나 범위를 넓혀보세요.")
    else:
        st.error("데이터를 가져오지 못했습니다. 시장 설정을 확인해주세요.")
