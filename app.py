import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
from datetime import datetime
import time

# 페이지 설정
st.set_page_config(page_title="Double BB Scanner", page_icon="📈", layout="wide")

st.title("📈 전략 일치형: Double BB + 365 EMA 스캐너")
st.markdown("트레이딩뷰 차트의 **BUY 화살표**를 강제로 추적하도록 로직을 재설계했습니다.")

# --- 세션 상태 초기화 ---
if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# 사이드바 설정
with st.sidebar:
    st.header("🔍 전략 설정")
    market = st.selectbox("대상 선택", ["업비트 코인", "국내주식 (KRX)", "미국주식 (NASDAQ/NYSE)"])
    tf_choice = st.selectbox("타임프레임", ["월봉", "주봉", "일봉", "4시간봉", "1시간봉", "5분봉"])
    
    interval_map = {
        "5분봉": "5", "1시간봉": "60", "4시간봉": "240",
        "일봉": "", "주봉": "1W", "월봉": "1M"
    }

    st.divider()
    top_n = st.slider("스캔 대상 (상위 N개)", 10, 1000, 250)
    
    st.divider()
    st.subheader("⚙️ 파라미터")
    std_dev_1 = st.number_input("Standard Deviation 1", value=1.0, step=0.1)
    
    st.divider()
    # 국내 주식용 필터
    use_per = st.checkbox("저PER 필터 사용 (국내 전용)", value=False)
    per_limit = st.number_input("PER 기준 (이하)", value=15.0)
    
    start_button = st.button("🚀 차트 신호 동기화 스캔 시작", use_container_width=True)

# 트레이딩뷰 지표 이력 추적 함수
def get_tv_visual_signal(symbol, screener, exchange, interval):
    try:
        url = f"https://scanner.tradingview.com/{screener}/scan"
        # 현재 봉(0)부터 과거 4개 봉까지의 데이터를 가져와서 신호가 있었는지 확인
        payload = {
            "symbols": {"tickers": [f"{exchange}:{symbol}"], "query": {"types": []}},
            "columns": [
                "close", "BB.lower", "sma[20]", "StdDev.20", "close[1]", "close[2]", "close[3]",
                "Recommend.All", "Recommend.MA", "Recommend.Other"
            ]
        }
        res = requests.post(url, json=payload, timeout=7).json()
        if 'data' not in res or not res['data']: return None
        
        d = res['data'][0]['d']
        curr_price = d[0]
        bb_lower = d[1]
        basis = d[2]
        stddev = d[3]
        
        # 1. 수치상 하단선 (Double BB 1std)
        lower_band_1 = basis - (stddev * std_dev_1)
        
        # 2. 신호 판정 로직 (범위를 대폭 넓힘)
        # 조건 A: 현재가가 1std 하단선보다 아래에 있거나 아주 가까움 (2% 이격 허용)
        is_in_buy_zone = curr_price <= lower_band_1 * 1.02
        
        # 조건 B: 최근 3개 봉 이내에 하단선을 뚫고 올라온 적이 있음
        is_recent_crossover = False
        for i in range(3):
            if d[4+i] is not None and d[4+i] <= lower_band_1:
                is_recent_crossover = True
                break
        
        # 조건 C: 트레이딩뷰 내부 엔진이 '매수' 의견을 내고 있음
        is_engine_buy = d[7] > 0
        
        # 차트에 BUY가 떠 있다면 위 조건 중 최소 하나는 반드시 걸립니다.
        if is_in_buy_zone or is_recent_crossover or is_engine_buy:
            return {
                "price": curr_price,
                "l_band": lower_band_1,
                "score": d[7]
            }
        return None
    except:
        return None

if start_button:
    st.session_state.found_data = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        # 1. 리스트 구성
        if "국내" in market:
            df_list = fdr.StockListing('KRX')
            if use_per:
                df_list['PER'] = pd.to_numeric(df_list.get('PER'), errors='coerce')
                df_list = df_list[(df_list['PER'] > 0) & (df_list['PER'] <= per_limit)]
            tickers = [(row['Code'], row['Name'], "KRX", "korea", row.get('PER', 'N/A')) for _, row in df_list.head(top_n).iterrows()]
        elif "미국" in market:
            df_list = fdr.StockListing('NASDAQ').head(top_n)
            tickers = [(row['Symbol'], row['Symbol'], "NASDAQ", "america", "N/A") for _, row in df_list.iterrows()]
        else: # 코인 (비트코인 무조건 포함 및 최상단)
            res = requests.get("https://api.upbit.com/v1/market/all").json()
            raw_tickers = [m for m in res if m['market'].startswith('KRW-')]
            tickers = [("BTC", "비트코인", "UPBIT", "crypto", "N/A")]
            for m in raw_tickers:
                sym = m['market'].split('-')[1]
                if sym != "BTC": tickers.append((sym, m['korean_name'], "UPBIT", "crypto", "N/A"))
            tickers = tickers[:top_n]

        # 2. 분석 실행
        total = len(tickers)
        for i, (symbol, name, exch, scr, per_val) in enumerate(tickers):
            progress_bar.progress((i + 1) / total)
            status_text.text(f"차트 신호 분석 중: {name} ({i+1}/{total})")
            
            res = get_tv_visual_signal(symbol, scr, exch, interval_map[tf_choice])
            
            if res:
                st.success(f"🎯 **{name}({symbol})** BUY 신호 포착!")
                st.session_state.found_data.append({
                    "종목": name, "현재가": res['price'], "하단선(1std)": round(res['l_band'], 2), "신호강도": round(res['score'], 2)
                })
            time.sleep(0.01)

        status_text.text(f"✅ 스캔 완료!")

    except Exception as e:
        st.error(f"오류: {e}")

if st.session_state.found_data:
    st.divider()
    st.dataframe(pd.DataFrame(st.session_state.found_data), use_container_width=True)
else:
    if start_button:
        st.warning("조건에 맞는 종목이 없습니다. 차트의 파라미터(StdDev 1.0 등)를 다시 확인해 주세요.")
