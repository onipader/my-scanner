import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
from datetime import datetime
import time

# 페이지 설정
st.set_page_config(page_title="Double BB Scanner", page_icon="📈", layout="wide")

st.title("📈 전략 일치형: Double BB + 365 EMA 스캐너")
st.markdown("저PER 필터는 **국내 주식(KRX)**일 때만 작동하도록 자동 설정되었습니다.")

# --- 세션 상태 초기화 ---
if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# 사이드바 설정
with st.sidebar:
    st.header("🔍 전략 설정")
    market = st.selectbox("대상 선택", ["국내주식 (KRX)", "미국주식 (NASDAQ/NYSE)", "업비트 코인"])
    tf_choice = st.selectbox("타임프레임", ["5분봉", "1시간봉", "4시간봉", "일봉", "주봉", "월봉"])
    
    interval_map = {
        "5분봉": "5m", "1시간봉": "1h", "4시간봉": "4h",
        "일봉": "1d", "주봉": "1w", "월봉": "1M"
    }

    st.divider()
    top_n = st.slider("스캔 대상 (시가총액 상위 N개)", 10, 1000, 200)
    
    st.divider()
    st.subheader("⚙️ 파라미터")
    length = st.number_input("BB Length", value=20)
    std_dev_1 = st.number_input("Standard Deviation 1", value=1.0)
    
    st.divider()
    # 이 체크박스가 켜져 있어도 '코인'이나 '미국주식'이면 아래 코드에서 자동으로 무시합니다.
    use_per = st.checkbox("저PER 필터 사용 (국내 전용)", value=True)
    per_limit = st.number_input("PER 기준 (이하)", value=15.0)
    
    start_button = st.button("🚀 전략 스캔 시작", use_container_width=True)

# 트레이딩뷰 지표 계산 함수
def get_tv_strategy_data(symbol, screener, exchange, interval):
    try:
        url = f"https://scanner.tradingview.com/{screener}/scan"
        payload = {
            "symbols": {"tickers": [f"{exchange}:{symbol}"], "query": {"types": []}},
            "columns": ["close", "sma[20]", "StdDev.20", "close[1]", "EMA365"]
        }
        res = requests.post(url, json=payload, timeout=5).json()
        if 'data' not in res or not res['data']: return None
        
        d = res['data'][0]['d']
        # 데이터 중 하나라도 None이면 패스
        if None in [d[0], d[1], d[2], d[3]]: return None
        
        # 주신 지표 로직: basis - (stddev * 1.0)
        lower_band_1 = d[1] - (d[2] * 1.0) 
        # ta.crossover 로직: 전봉은 하단보다 낮고, 현재봉은 하단보다 높음
        is_crossover = d[3] <= lower_band_1 and d[0] > lower_band_1
        
        return {"price": d[0], "signal": is_crossover, "ema365": d[4]}
    except:
        return None

if start_button:
    st.session_state.found_data = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        # 1. 리스트 구성
        with st.spinner("종목 리스트 분석 중..."):
            if "국내" in market:
                df_list = fdr.StockListing('KRX')
                cap_col = next((c for c in ['MarCap', '시가총액'] if c in df_list.columns), 'MarCap')
                df_list[cap_col] = pd.to_numeric(df_list[cap_col], errors='coerce')
                
                # 국내 주식일 때만 저PER 필터 적용
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
                # 코인은 PER 필터 없이 바로 top_n개 추출
                tickers = [(m['market'].split('-')[1], m['korean_name'], "UPBIT", "crypto", "N/A") for m in res if m['market'].startswith('KRW-')][:int(top_n)]

        # 2. 분석 실행
        total_count = len(tickers)
        for i, (symbol, name, exch, scr, per_val) in enumerate(tickers):
            progress_bar.progress((i + 1) / total_count)
            status_text.text(f"분석 중 ({i+1}/{total_count}): {name}")
            
            res = get_tv_strategy_data(symbol, scr, exch, interval_map[tf_choice])
            
            if res and res['signal']:
                p_val = f"{per_val:.2f}" if isinstance(per_val, (int, float)) else "N/A"
                st.success(f"🎯 **{name}** 매수 신호(Crossover) 포착!")
                st.session_state.found_data.append({
                    "종목": name, "현재가": res['price'], "PER": p_val, "EMA365": round(res['ema365'], 1) if res['ema365'] else "N/A"
                })
            time.sleep(0.02) # 속도 향상을 위해 대기시간 단축

        status_text.text(f"✅ 총 {total_count}개 종목 스캔 완료!")

    except Exception as e:
        st.error(f"오류: {e}")

if st.session_state.found_data:
    st.divider()
    st.dataframe(pd.DataFrame(st.session_state.found_data), use_container_width=True)
else:
    if start_button:
        st.info("현재 정확히 '골든크로스(Crossover)'가 발생한 종목이 없습니다. 타임프레임을 낮춰보세요(예: 1시간봉).")
