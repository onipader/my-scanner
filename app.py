import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
import time

# 페이지 설정
st.set_page_config(page_title="Double BB Scanner", page_icon="📈", layout="wide")

st.title("📈 차트 신호 직결: Double BB 스캐너")
st.markdown("수치 계산 오차를 무시하고, **차트에 BUY 신호가 떠 있는 종목**을 실시간으로 찾아냅니다.")

# 사이드바 설정
with st.sidebar:
    st.header("🔍 전략 설정")
    market = st.selectbox("대상 선택", ["업비트 코인", "국내주식 (KRX)"])
    tf_choice = st.selectbox("타임프레임", ["월봉", "주봉", "일봉", "4시간봉", "1시간봉"])
    interval_map = {"1시간봉": "60", "4시간봉": "240", "일봉": "", "주봉": "1W", "월봉": "1M"}
    
    st.divider()
    top_n = st.number_input("스캔 대상 개수", value=250, min_value=10)
    
    # 🔹 신호 감도: 0.1 이상이면 매수 추천이 있는 종목을 잡습니다.
    sensitivity = st.slider("신호 감도 (낮을수록 더 많이 포착)", -1.0, 1.0, 0.1, step=0.1)
    
    start_button = st.button("🚀 차트 신호 스캔 시작", use_container_width=True)

def get_direct_signal(symbol, screener, exchange, interval):
    try:
        url = f"https://scanner.tradingview.com/{screener}/scan"
        # Recommend.All: 트레이딩뷰 지표를 종합한 매수/매도 의견 (1.0에 가까울수록 강한 BUY)
        payload = {
            "symbols": {"tickers": [f"{exchange}:{symbol}"], "query": {"types": []}},
            "columns": ["Recommend.All", "close", "BB.lower", "low"]
        }
        res = requests.post(url, json=payload, timeout=7).json()
        if 'data' not in res or not res['data']: return None
        
        d = res['data'][0]['d']
        rec_val, curr_c, bb_low, curr_l = d[0], d[1], d[2], d[3]

        # 🔹 판정 로직: 트레이딩뷰 자체 추천 점수가 존재하거나, 가격이 하단선 근처인 경우
        if rec_val > sensitivity or curr_c <= bb_low * 1.02:
            return {"price": curr_c, "score": rec_val, "bb_low": bb_low}
        return None
    except:
        return None

if start_button:
    found_list = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    if "업비트" in market:
        res = requests.get("https://api.upbit.com/v1/market/all").json()
        # 비트코인(BTC)을 가장 먼저 검사하도록 배치
        tickers = [("BTC", "비트코인", "UPBIT", "crypto")]
        for m in res:
            if m['market'].startswith('KRW-') and m['market'] != 'KRW-BTC':
                tickers.append((m['market'].split('-')[1], m['korean_name'], "UPBIT", "crypto"))
    else:
        df = fdr.StockListing('KRX')
        tickers = [(row['Code'], row['Name'], "KRX", "korea") for _, row in df.head(top_n).iterrows()]

    for i, (sym, name, exch, scr) in enumerate(tickers[:top_n]):
        progress_bar.progress((i + 1) / len(tickers[:top_n]))
        status_text.text(f"차트 신호 확인 중: {name}")
        
        res = get_direct_signal(sym, scr, exch, interval_map[tf_choice])
        if res:
            st.success(f"🎯 **{name}({sym})** 신호 포착!")
            found_list.append({
                "종목": name, "가격": f"{res['price']:,.0f}원", 
                "신호강도": round(res['score'], 2), "하단선(참고)": f"{res['bb_low']:,.0f}원"
            })
        time.sleep(0.01)

    status_text.text("✅ 스캔 완료!")
    if found_list:
        st.divider()
        st.table(pd.DataFrame(found_list))
    else:
        st.warning("신호가 잡히지 않습니다. 왼쪽 '신호 감도'를 -0.5 정도로 낮춰보세요!")
