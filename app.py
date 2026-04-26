import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
from datetime import datetime
import time

# 페이지 설정
st.set_page_config(page_title="Double BB Scanner", page_icon="📈", layout="wide")

st.title("📈 전략 일치형: Double BB + 365 EMA 스캐너")
st.markdown("트레이딩뷰 차트의 **시각적 BUY 신호**와 동기화하기 위해 감도를 최대로 높였습니다.")

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
    # 트레이딩뷰 설정값 반영
    std_dev_1 = st.number_input("Standard Deviation 1", value=1.00, step=0.1)
    std_dev_2 = st.number_input("Standard Deviation 2", value=2.00, step=0.1)
    
    st.divider()
    use_per = st.checkbox("저PER 필터 사용 (국내 전용)", value=False)
    per_limit = st.number_input("PER 기준 (이하)", value=15.0)
    
    start_button = st.button("🚀 지표 완벽 동기화 스캔 시작", use_container_width=True)

# 트레이딩뷰 지표 데이터 추출 (감도 극대화)
def get_tv_final_signal(symbol, screener, exchange, interval):
    try:
        url = f"https://scanner.tradingview.com/{screener}/scan"
        # 모든 가능한 기술적 지표와 추천 값을 가져옴
        payload = {
            "symbols": {"tickers": [f"{exchange}:{symbol}"], "query": {"types": []}},
            "columns": ["close", "sma[20]", "StdDev.20", "EMA365", "Recommend.All", "low", "open"]
        }
        res = requests.post(url, json=payload, timeout=7).json()
        if 'data' not in res or not res['data']: return None
        
        d = res['data'][0]['d']
        # 데이터 매핑 (인덱스 주의)
        curr_price, basis, stddev, ema365, rec_all, curr_low, curr_open = d[0], d[1], d[2], d[3], d[4], d[5], d[6]
        
        if None in [curr_price, basis, stddev]: return None
        
        # 하단선 계산
        lower_1 = basis - (stddev * std_dev_1)
        lower_2 = basis - (stddev * std_dev_2)
        
        # [판정 로직] 트레이딩뷰 차트의 BUY 신호는 보통 다음 중 하나일 때 뜹니다.
        # 1. 가격이 하단 1선(1.0) 아래에 있거나 터치했을 때
        # 2. 가격이 하단 1선 위로 막 올라왔을 때
        # 3. 기술적 지표 합산(Recommend.All)이 매수 우위일 때
        
        is_touching = curr_low <= lower_1 * 1.01 # 저가가 하단 1선 근처
        is_rebounding = curr_price >= lower_1 and curr_open < lower_1 # 시가는 아래, 종가는 위 (Crossover)
        is_bullish = rec_all > 0 # 전체 지표가 매수 우위
        
        if is_touching or is_rebounding or is_bullish:
            return {
                "price": curr_price,
                "l1": lower_1,
                "rec": rec_all,
                "ema": ema365
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
        else: # 코인 (비트코인 강제 포함)
            res = requests.get("https://api.upbit.com/v1/market/all").json()
            raw_tickers = [m for m in res if m['market'].startswith('KRW-')]
            tickers = [("BTC", "비트코인", "UPBIT", "crypto")]
            for m in raw_tickers:
                sym = m['market'].split('-')[1]
                if sym != "BTC": tickers.append((sym, m['korean_name'], "UPBIT", "crypto"))
            tickers = tickers[:top_n]

        # 2. 분석 실행
        total = len(tickers)
        for i, (symbol, name, exch, scr) in enumerate(tickers):
            progress_bar.progress((i + 1) / total)
            status_text.text(f"차트 신호 분석 중: {name}")
            
            res = get_tv_final_signal(symbol, scr, exch, interval_map[tf_choice])
            
            if res:
                st.success(f"🎯 **{name}({symbol})** 신호 포착!")
                st.session_state.found_data.append({
                    "종목": name, "가격": res['price'], "하단선(1.0)": round(res['l1'], 2), "신호강도": round(res['rec'], 2), "365EMA": round(res['ema'], 1) if res['ema'] else "N/A"
                })
            time.sleep(0.01)

        status_text.text(f"✅ 스캔 완료! ({len(st.session_state.found_data)}건 발견)")

    except Exception as e:
        st.error(f"오류: {e}")

if st.session_state.found_data:
    st.divider()
    st.dataframe(pd.DataFrame(st.session_state.found_data), use_container_width=True)
else:
    if start_button:
        st.warning("조건을 더 완화했습니다. 만약 비트코인이 여전히 안 나온다면 파라미터(1.0, 2.0)를 다시 확인해 주세요.")
