import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
from datetime import datetime
import time

# 페이지 설정
st.set_page_config(page_title="Double BB Scanner", page_icon="📈", layout="wide")

st.title("📈 전략 일치형: Double BB + 365 EMA 스캐너")
st.markdown("트레이딩뷰 지표의 **`ta.crossover(close, lower_band_1)`** 로직을 그대로 적용했습니다.")

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
    st.subheader("⚙️ 파라미터 (지표와 동일)")
    length = st.number_input("BB Length", value=20)
    std_dev_1 = st.number_input("Standard Deviation 1", value=1.0)
    
    st.divider()
    use_per = st.checkbox("저PER 필터 사용", value=True)
    per_limit = st.number_input("PER 기준 (이하)", value=15.0)
    
    start_button = st.button("🚀 전략 스캔 시작", use_container_width=True)

# 트레이딩뷰 지표 계산 함수 (주신 소스코드 로직)
def get_tv_strategy_data(symbol, screener, exchange, interval):
    try:
        url = f"https://scanner.tradingview.com/{screener}/scan"
        # 주신 코드의 핵심 지표들 요청
        payload = {
            "symbols": {"tickers": [f"{exchange}:{symbol}"], "query": {"types": []}},
            "columns": [
                "close", 
                f"BB.lower", # 기본 2표준편차 하단
                "RSI",
                "EMA365",
                "close[1]",    # 직전 봉 종가 (크로스오버 확인용)
                "lower_band_1" # 1표준편차 하단 (커스텀 필요하나 API 기본값 활용)
            ]
        }
        # 참고: API에서 lower_band_1(1표준편차)을 직접 주지 않는 경우가 많아 
        # API가 제공하는 Basis(SMA20)와 BB.lower(2std)를 이용해 1std를 역산합니다.
        payload["columns"] = ["close", "sma[20]", "StdDev.20", "close[1]", "EMA365"]
        
        res = requests.post(url, json=payload, timeout=5).json()
        d = res['data'][0]['d']
        
        curr_close = d[0]
        basis = d[1]
        stddev_20 = d[2]
        prev_close = d[3]
        ema365 = d[4]
        
        # 주신 코드의 lower_band_1 계산: basis - (stddev * 1.0)
        lower_band_1 = basis - (stddev_20 * 1.0)
        
        # ta.crossover(close, lower_band_1) 로직 구현
        # 조건: 이전 봉은 하단밴드보다 낮았고, 현재 봉은 하단밴드보다 높음
        is_crossover = prev_close < lower_band_1 and curr_close > lower_band_1
        
        return {
            "price": curr_close,
            "signal": is_crossover,
            "ema365": ema365,
            "lower_band_1": lower_band_1
        }
    except:
        return None

if start_button:
    st.session_state.found_data = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        # 1. 리스트 구성 (PER 데이터 보강)
        with st.spinner("종목 정보를 불러오는 중..."):
            if "국내" in market:
                # KRX 전체 상장종목 리스트와 재무상태 함께 로드
                df_list = fdr.StockListing('KRX')
                
                # [수정] PER N/A 문제 해결: 데이터 타입 강제 변환 및 결측치 제거
                if 'PER' in df_list.columns:
                    df_list['PER'] = pd.to_numeric(df_list['PER'], errors='coerce')
                    if use_per:
                        df_list = df_list[df_list['PER'] <= per_limit]
                        df_list = df_list[df_list['PER'] > 0] # 적자 기업 제외
                
                cap_col = next((c for c in ['MarCap', '시가총액'] if c in df_list.columns), 'MarCap')
                df_list = df_list.sort_values(cap_col, ascending=False).head(int(top_n))
                tickers = [(row['Code'], row['Name'], "KRX", "korea", row.get('PER', 'N/A')) for _, row in df_list.iterrows()]
            
            # ... (미국/코인은 기존과 동일)
            elif "미국" in market:
                df_list = fdr.StockListing('NASDAQ').head(int(top_n))
                tickers = [(row['Symbol'], row['Symbol'], "NASDAQ", "america", "N/A") for _, row in df_list.iterrows()]
            else:
                res = requests.get("https://api.upbit.com/v1/market/all").json()
                tickers = [(m['market'].split('-')[1], m['korean_name'], "UPBIT", "crypto", "N/A") for m in res if m['market'].startswith('KRW-')][:int(top_n)]

        # 2. 분석 실행
        for i, (symbol, name, exch, scr, per_val) in enumerate(tickers):
            progress_bar.progress((i + 1) / len(tickers))
            status_text.text(f"전략 분석 중: {name}")
            
            res = get_tv_strategy_data(symbol, scr, exch, interval_map[tf_choice])
            
            if res and res['signal']:
                # 포착 신호!
                per_display = f"{per_val:.2f}" if isinstance(per_val, (int, float)) else "N/A"
                st.success(f"🎯 **{name}** 매수 신호 발생! (현재가: {res['price']:,} / PER: {per_display})")
                
                found_data_row = {
                    "종목": name,
                    "현재가": res['price'],
                    "PER": per_display,
                    "365 EMA": round(res['ema365'], 1) if res['ema365'] else "N/A",
                    "상태": "하단밴드 상향돌파"
                }
                st.session_state.found_data.append(found_data_row)
            
            time.sleep(0.05)

        status_text.text(f"✅ {tf_choice} 전략 스캔 완료!")
        if st.session_state.found_data:
            st.divider()
            st.dataframe(pd.DataFrame(st.session_state.found_data), use_container_width=True)
        else:
            st.info("현재 전략 신호(BB 1std 돌파)가 발생한 종목이 없습니다.")

    except Exception as e:
        st.error(f"오류: {e}")
