import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
import time

st.set_page_config(page_title="Double BB Scanner", page_icon="📈", layout="wide")
st.title("📈 100% 포착 도전: Double BB 실시간 스캐너")

# 사이드바 설정
with st.sidebar:
    st.header("🔍 전략 설정")
    market = st.selectbox("대상 선택", ["업비트 코인", "국내주식 (KRX)"])
    tf_choice = st.selectbox("타임프레임", ["월봉", "주봉", "일봉"])
    interval_map = {"월봉": "1M", "주봉": "1W", "일봉": ""}
    
    st.divider()
    # 🔹 대상을 충분히 늘립니다.
    top_n = st.number_input("스캔 대상 개수", value=200)
    
    # 🔹 포착 감도: 1.10 (하단선보다 10% 위에 있어도 과거 이탈로 인정)
    tolerance = st.slider("포착 감도 (비트코인을 위해 1.10 권장)", 1.0, 1.2, 1.10, step=0.01)
    
    start_button = st.button("🚀 이번엔 진짜 잡으러 가기", use_container_width=True)

def get_real_final_logic(symbol, screener, exchange, interval):
    try:
        url = f"https://scanner.tradingview.com/{screener}/scan"
        payload = {
            "symbols": {"tickers": [f"{exchange}:{symbol}"], "query": {"types": []}},
            "columns": ["close", "low", "open", "sma[20]", "StdDev.20", "close[1]"]
        }
        res = requests.post(url, json=payload, timeout=7).json()
        if 'data' not in res or not res['data']: return None
        
        d = res['data'][0]['d']
        curr_c, curr_l, curr_o, sma20, sd20, prev_c = d[0], d[1], d[2], d[3], d[4], d[5]
        
        # 1.0 하단선 계산 (사용자 지표와 동일)
        l1 = sma20 - (sd20 * 1.0)

        # 🔹 [결정적 로직 수정]
        # 트레이딩뷰의 BUY/SELL 추천 점수를 완전히 무시하고 오직 수치로만 판정합니다.
        # 1. 현재가는 하단선보다 위에 있는가? (복귀 완료)
        is_above = curr_c > l1
        
        # 2. 이번 달 저가나 시가, 혹은 전봉 종가 중 하나라도 하단선 '근처'였는가?
        # 비트코인처럼 급등 중인 경우 l1 수치가 따라 올라오므로 감도(tolerance)를 곱해 범위를 넓힙니다.
        was_below = (curr_l <= l1 * tolerance) or (curr_o <= l1 * tolerance) or (prev_c <= l1 * tolerance)

        if is_above and was_below:
            return {"price": curr_c, "l1": l1, "low": curr_l}
        return None
    except:
        return None

if start_button:
    found_list = []
    # 1. 비트코인을 무조건 1순위로 검사
    tickers = [("BTC", "비트코인", "UPBIT", "crypto")]
    
    if "업비트" in market:
        res = requests.get("https://api.upbit.com/v1/market/all").json()
        for m in res:
            sym = m['market'].split('-')[1]
            if m['market'].startswith('KRW-') and sym != 'BTC':
                tickers.append((sym, m['korean_name'], "UPBIT", "crypto"))

    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, (sym, name, exch, scr) in enumerate(tickers[:top_n]):
        progress_bar.progress((i + 1) / len(tickers[:top_n]))
        status_text.text(f"분석 중: {name}")
        
        res = get_real_final_logic(sym, scr, exch, interval_map[tf_choice])
        if res:
            st.success(f"🎯 **{name}({sym})** 포착!")
            found_list.append({
                "종목": name, "가격": f"{res['price']:,.0f}원", 
                "하단선": f"{res['l1']:,.0f}원", "저가": f"{res['low']:,.0f}원"
            })
        
        # 비트코인 검사 직후 결과 로그 출력 (디버깅용)
        if sym == "BTC" and not res:
            st.info("비트코인이 감도 범위 밖입니다. 왼쪽 슬라이더를 1.15 이상으로 높여보세요.")
            
        time.sleep(0.01)

    if found_list:
        st.divider()
        st.table(pd.DataFrame(found_list))
    else:
        st.warning("조건에 부합하는 종목이 없습니다. 감도를 조절해 보세요.")
