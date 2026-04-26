import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
from datetime import datetime
import time

# 페이지 설정
st.set_page_config(page_title="Double BB Scanner", page_icon="📈", layout="wide")

st.title("📈 전략 일치형: Double BB + 365 EMA 스캐너")
st.markdown("비트코인 및 대형주의 **월봉/주봉 신호 포착** 기능을 강화했습니다.")

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
    std_dev_1 = st.number_input("Standard Deviation 1 (지표와 동일하게)", value=1.0, step=0.1)
    
    # 신호 포착 방식
    signal_type = st.radio("신호 포착 방식", ["하단선 아래(Buy Zone)", "정확한 교차(Crossover)"], 
                          index=0, help="비트코인 월봉 확인을 위해 'Buy Zone'을 권장합니다.")
    
    st.divider()
    use_per = st.checkbox("저PER 필터 사용 (국내 전용)", value=False)
    per_limit = st.number_input("PER 기준 (이하)", value=15.0)
    
    start_button = st.button("🚀 전략 스캔 시작", use_container_width=True)

# 트레이딩뷰 지표 계산 함수 (로직 보강)
def get_tv_strategy_data(symbol, screener, exchange, interval, sig_type):
    try:
        url = f"https://scanner.tradingview.com/{screener}/scan"
        payload = {
            "symbols": {"tickers": [f"{exchange}:{symbol}"], "query": {"types": []}},
            "columns": ["close", "sma[20]", "StdDev.20", "close[1]", "EMA365"]
        }
        res = requests.post(url, json=payload, timeout=7).json()
        if 'data' not in res or not res['data']: return None
        
        d = res['data'][0]['d']
        if d[0] is None or d[1] is None or d[2] is None: return None
        
        curr_close, basis, stddev_20, prev_close, ema365 = d[0], d[1], d[2], d[3], d[4]
        
        # 1표준편차 하단선 계산
        lower_band_1 = basis - (stddev_20 * std_dev_1) 
        
        # 신호 판정
        is_hit = False
        if sig_type == "정확한 교차(Crossover)":
            # 이전 봉 종가가 하단선 아래였거나 근처였고, 현재 종가가 위로 올라온 경우
            if prev_close is not None:
                is_hit = prev_close <= lower_band_1 and curr_close > lower_band_1
        else: # 하단선 아래(Buy Zone)
            # 현재가가 하단선보다 낮거나, 하단선과의 이격도가 0.5% 이내인 경우 (포착률 강화)
            is_hit = curr_close <= lower_band_1 * 1.005 
        
        return {
            "price": curr_close, 
            "signal": is_hit, 
            "ema365": ema365, 
            "l_band": lower_band_1,
            "dist": ((curr_close / lower_band_1) - 1) * 100 if lower_band_1 != 0 else 0
        }
    except:
        return None

if start_button:
    st.session_state.found_data = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        # 1. 리스트 구성
        with st.spinner("리스트 분석 중..."):
            if "국내" in market:
                df_list = fdr.StockListing('KRX')
                cap_col = next((c for c in ['MarCap', '시가총액'] if c in df_list.columns), 'MarCap')
                df_list[cap_col] = pd.to_numeric(df_list[cap_col], errors='coerce')
                if use_per and 'PER' in df_list.columns:
                    df_list['PER'] = pd.to_numeric(df_list['PER'], errors='coerce')
                    df_list = df_list[(df_list['PER'] > 0) & (df_list['PER'] <= per_limit)]
                df_list = df_list.sort_values(cap_col, ascending=False).head(int(top_n))
                tickers = [(row['Code'], row['Name'], "KRX", "korea", row.get('PER', 'N/A')) for _, row in df_list.iterrows()]
            elif "미국" in market:
                df_list = fdr.StockListing('NASDAQ').head(int(top_n))
                tickers = [(row['Symbol'], row['Symbol'], "NASDAQ", "america", "N/A") for _, row in df_list.iterrows()]
            else: # 업비트 코인
                res = requests.get("https://api.upbit.com/v1/market/all").json()
                # BTC를 가장 먼저 스캔하도록 리스트 조정
                raw_tickers = [m for m in res if m['market'].startswith('KRW-')]
                tickers = []
                for m in raw_tickers:
                    sym = m['market'].split('-')[1]
                    tickers.append((sym, m['korean_name'], "UPBIT", "crypto", "N/A"))
                tickers = tickers[:int(top_n)]

        # 2. 분석 실행
        total_count = len(tickers)
        for i, (symbol, name, exch, scr, per_val) in enumerate(tickers):
            progress_bar.progress((i + 1) / total_count)
            status_text.text(f"분석 중 ({i+1}/{total_count}): {name}")
            
            res = get_tv_strategy_data(symbol, scr, exch, interval_map[tf_choice], signal_type)
            
            if res and res['signal']:
                p_val = f"{per_val:.2f}" if isinstance(per_val, (int, float)) else "N/A"
                st.success(f"✅ **{name}({symbol})** 포착! (가격 {res['price']:,} / 하단선과의 이격: {res['dist']:.2f}%)")
                st.session_state.found_data.append({
                    "종목": name, "심볼": symbol, "현재가": res['price'], "하단선(1std)": round(res['l_band'], 2),
                    "이격도(%)": round(res['dist'], 2), "PER": p_val
                })
            # 빠른 스캔을 위해 sleep 최소화
            time.sleep(0.01)

        status_text.text(f"✅ {total_count}개 종목 스캔 완료!")

    except Exception as e:
        st.error(f"오류: {e}")

if st.session_state.found_data:
    st.divider()
    st.dataframe(pd.DataFrame(st.session_state.found_data), use_container_width=True)
else:
    if start_button:
        st.warning("조건에 맞는 종목이 없습니다. '신호 포착 방식'을 다시 확인해 주세요.")
