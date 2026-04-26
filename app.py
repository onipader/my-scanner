import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
from datetime import datetime
import time

# 페이지 설정
st.set_page_config(page_title="Double BB Scanner", page_icon="📈", layout="wide")

st.title("📈 실시간 전략: Double BB + 365 EMA 스캐너")
st.markdown("과거 신호 제외! **현재 진행 중인 캔들**에서 조건이 충족된 종목만 실시간으로 추출합니다.")

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
    st.subheader("⚙️ 파라미터 (Double BB)")
    # 트레이딩뷰 설정값 (StdDev 1, 2)
    std_dev_1 = st.number_input("Standard Deviation 1", value=1.00, step=0.1)
    std_dev_2 = st.number_input("Standard Deviation 2", value=2.00, step=0.1)
    
    st.divider()
    use_per = st.checkbox("저PER 필터 사용 (국내 전용)", value=False)
    per_limit = st.number_input("PER 기준 (이하)", value=15.0)
    
    start_button = st.button("🚀 실시간 현재 봉 스캔 시작", use_container_width=True)

# 실시간 데이터 분석 함수 (현재 캔들 전용)
def get_tv_realtime_signal(symbol, screener, exchange, interval):
    try:
        url = f"https://scanner.tradingview.com/{screener}/scan"
        # 현재 진행 중인 캔들의 실시간 값들을 요청
        payload = {
            "symbols": {"tickers": [f"{exchange}:{symbol}"], "query": {"types": []}},
            "columns": ["close", "sma[20]", "StdDev.20", "low", "EMA365", "open"]
        }
        res = requests.post(url, json=payload, timeout=7).json()
        if 'data' not in res or not res['data']: return None
        
        d = res['data'][0]['d']
        # d[0]: 현재가, d[1]: 중심선, d[2]: 표준편차, d[3]: 저가, d[4]: 365EMA, d[5]: 시가
        curr_price, basis, stddev, curr_low, ema365, curr_open = d[0], d[1], d[2], d[3], d[4], d[5]
        
        if None in [curr_price, basis, stddev]: return None
        
        # 하단선 실시간 계산
        lower_1 = basis - (stddev * std_dev_1)
        lower_2 = basis - (stddev * std_dev_2)
        
        # [현재 캔들 BUY 신호 조건]
        # 1. 현재가가 하단 1선 아래에 있거나 (진행 중인 하락)
        # 2. 현재가가 하단 1선을 상향 돌파 중이거나 (실시간 반등)
        # 3. 이번 봉의 저가가 하단 1선 아래를 터치했음 (꼬리 발생)
        is_hit = (curr_price <= lower_1) or (curr_low <= lower_1) or (curr_open < lower_1 and curr_price > lower_1)
        
        if is_hit:
            return {
                "price": curr_price,
                "l1": lower_1,
                "l2": lower_2,
                "ema": ema365,
                "low": curr_low
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
            tickers = [(row['Code'], row['Name'], "KRX", "korea") for _, row in df_list.head(top_n).iterrows()]
        elif "미국" in market:
            df_list = fdr.StockListing('NASDAQ').head(top_n)
            tickers = [(row['Symbol'], row['Symbol'], "NASDAQ", "america") for _, row in df_list.iterrows()]
        else: # 코인 (비트코인 최우선)
            res = requests.get("https://api.upbit.com/v1/market/all").json()
            raw_tickers = [m for m in res if m['market'].startswith('KRW-')]
            tickers = [("BTC", "비트코인", "UPBIT", "crypto")]
            for m in raw_tickers:
                sym = m['market'].split('-')[1]
                if sym != "BTC": tickers.append((sym, m['korean_name'], "UPBIT", "crypto"))
            tickers = tickers[:top_n]

        # 2. 실시간 분석 실행
        total = len(tickers)
        for i, (symbol, name, exch, scr) in enumerate(tickers):
            progress_bar.progress((i + 1) / total)
            status_text.text(f"현재 캔들 분석 중: {name}")
            
            res = get_tv_realtime_signal(symbol, scr, exch, interval_map[tf_choice])
            
            if res:
                st.success(f"🎯 **{name}({symbol})** 실시간 신호 포착!")
                st.session_state.found_data.append({
                    "종목": name, "현재가": res['price'], "저가": res['low'], "하단1(1.0)": round(res['l1'], 2), "365EMA": round(res['ema'], 1) if res['ema'] else "N/A"
                })
            time.sleep(0.01)

        status_text.text(f"✅ 현재 캔들 스캔 완료! (총 {len(st.session_state.found_data)}건)")

    except Exception as e:
        st.error(f"오류 발생: {e}")

if st.session_state.found_data:
    st.divider()
    st.dataframe(pd.DataFrame(st.session_state.found_data), use_container_width=True)
else:
    if start_button:
        st.warning("현재 캔들에서 조건을 만족하는 종목이 없습니다. (실시간 가격이 하단선 근처인지 확인해 주세요)")
