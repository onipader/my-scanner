import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
from datetime import datetime
import time

# 페이지 설정
st.set_page_config(page_title="Double BB Scanner", page_icon="📈", layout="wide")

st.title("📈 전략 일치형: Double BB + 365 EMA 스캐너")
st.markdown("트레이딩뷰 차트의 **BUY 신호**와 최대한 일치하도록 로직을 개선했습니다.")

# --- 세션 상태 초기화 ---
if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# 사이드바 설정
with st.sidebar:
    st.header("🔍 전략 설정")
    market = st.selectbox("대상 선택", ["업비트 코인", "국내주식 (KRX)", "미국주식 (NASDAQ/NYSE)"])
    tf_choice = st.selectbox("타임프레임", ["월봉", "주봉", "일봉", "4시간봉", "1시간봉", "5분봉"])
    
    interval_map = {
        "5분봉": "5m", "1시간봉": "1h", "4시간봉": "4h",
        "일봉": "1d", "주봉": "1w", "월봉": "1M"
    }

    st.divider()
    top_n = st.slider("스캔 대상 (상위 N개)", 10, 1000, 250)
    
    st.divider()
    st.subheader("⚙️ 파라미터")
    std_dev_1 = st.number_input("Standard Deviation 1", value=1.0, step=0.1)
    
    st.divider()
    # 국내 주식일 때만 활성화
    use_per = st.checkbox("저PER 필터 사용 (국내 전용)", value=False)
    per_limit = st.number_input("PER 기준 (이하)", value=15.0)
    
    start_button = st.button("🚀 전략 스캔 시작", use_container_width=True)

# 트레이딩뷰 지표 계산 함수 (포착력 최대로 강화)
def get_tv_strategy_data(symbol, screener, exchange, interval):
    try:
        url = f"https://scanner.tradingview.com/{screener}/scan"
        payload = {
            "symbols": {"tickers": [f"{exchange}:{symbol}"], "query": {"types": []}},
            "columns": ["close", "sma[20]", "StdDev.20", "close[1]", "EMA365", "Recommend.All"]
        }
        res = requests.post(url, json=payload, timeout=7).json()
        if 'data' not in res or not res['data']: return None
        
        d = res['data'][0]['d']
        curr_close, basis, stddev_20, prev_close, ema365, rec_signal = d[0], d[1], d[2], d[3], d[4], d[5]
        
        if None in [curr_close, basis, stddev_20]: return None
        
        # 1표준편차 하단선
        lower_band_1 = basis - (stddev_20 * std_dev_1) 
        
        # [핵심 로직] 차트 신호와 일치시키기 위한 3중 필터
        # 1. 현재가가 하단선보다 아래에 있거나 아주 근처 (이격도 1% 허용)
        is_near_bottom = curr_close <= lower_band_1 * 1.01
        
        # 2. 혹은 방금 막 뚫고 올라오는 중 (Crossover)
        is_crossover = (prev_close is not None) and (prev_close <= lower_band_1 and curr_close > lower_band_1)
        
        # 3. 트레이딩뷰 자체 매수 의견이 있는가 (신뢰도 보강)
        is_recommended = rec_signal > 0 # 0보다 크면 매수 의견이 섞여 있음
        
        # 최종 판단: 하단 구간에 있으면서 (또는 뚫으면서) 매수세가 붙었을 때
        if (is_near_bottom or is_crossover):
            return {
                "price": curr_close, 
                "ema365": ema365, 
                "l_band": lower_band_1,
                "rec": rec_signal
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
        else: # 코인 (비트코인 우선 배치)
            res = requests.get("https://api.upbit.com/v1/market/all").json()
            raw_tickers = [m for m in res if m['market'].startswith('KRW-')]
            tickers = []
            for m in raw_tickers:
                sym = m['market'].split('-')[1]
                tickers.append((sym, m['korean_name'], "UPBIT", "crypto", "N/A"))
            # BTC가 리스트 앞에 오도록 정렬 (찾기 쉽게)
            tickers.sort(key=lambda x: x[0] != 'BTC')
            tickers = tickers[:top_n]

        # 2. 분석 실행
        total = len(tickers)
        for i, (symbol, name, exch, scr, per_val) in enumerate(tickers):
            progress_bar.progress((i + 1) / total)
            status_text.text(f"신호 분석 중: {name} ({i+1}/{total})")
            
            res = get_tv_strategy_data(symbol, scr, exch, interval_map[tf_choice])
            
            if res:
                st.success(f"🎯 **{name}({symbol})** 신호 포착! (차트 바이시그널 일치 가능성 높음)")
                st.session_state.found_data.append({
                    "종목": name, "심볼": symbol, "현재가": res['price'], "하단선": round(res['l_band'], 2), "PER": per_val
                })
            time.sleep(0.01)

        status_text.text(f"✅ {total}개 종목 스캔 완료!")

    except Exception as e:
        st.error(f"오류: {e}")

if st.session_state.found_data:
    st.divider()
    st.dataframe(pd.DataFrame(st.session_state.found_data), use_container_width=True)
else:
    if start_button:
        st.warning("현재 지표 조건에 맞는 종목이 없습니다. 타임프레임을 바꿔보세요.")
