import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
from datetime import datetime
import time

# 페이지 설정
st.set_page_config(page_title="Double BB Scanner", page_icon="📈", layout="wide")

st.title("📈 차트 신호 동기화: Double BB + 365 EMA 스캐너")
st.markdown("트레이딩뷰 차트의 **BUY 화살표**를 실시간으로 추적하여 리스트업합니다.")

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
    st.subheader("⚙️ 신호 감도")
    # 차트의 BUY와 일치시키기 위해 감도를 조정 가능하게 함
    sensitivity = st.slider("신호 감도 (낮을수록 더 많이 포착)", -0.5, 0.5, 0.0, step=0.1)
    
    st.divider()
    use_per = st.checkbox("저PER 필터 사용 (국내 전용)", value=False)
    per_limit = st.number_input("PER 기준 (이하)", value=15.0)
    
    start_button = st.button("🚀 차트 신호 직접 스캔 시작", use_container_width=True)

# 트레이딩뷰 내부 엔진 신호 추출 함수
def get_tv_direct_signal(symbol, screener, exchange, interval):
    try:
        url = f"https://scanner.tradingview.com/{screener}/scan"
        # Recommend.All: 모든 지표를 종합하여 트레이딩뷰가 내리는 결론 (BUY/SELL)
        payload = {
            "symbols": {"tickers": [f"{exchange}:{symbol}"], "query": {"types": []}},
            "columns": ["Recommend.All", "close", "EMA365", "BB.lower", "low", "open"]
        }
        res = requests.post(url, json=payload, timeout=7).json()
        if 'data' not in res or not res['data']: return None
        
        d = res['data'][0]['d']
        # d[0]: 종합 추천(1.0에 가까울수록 강한 BUY), d[1]: 현재가, d[2]: EMA365, d[3]: BB하단
        rec_val, curr_price, ema365, bb_low, low_val, open_val = d[0], d[1], d[2], d[3], d[4], d[5]

        # [판정 핵심] 
        # 차트에 BUY가 떠 있다면 rec_val은 0보다 큽니다.
        # 또한, 현재가가 BB하단 근처(Double BB 구간)에 있는지도 함께 확인합니다.
        is_buy_signal = (rec_val > sensitivity) or (curr_price <= bb_low * 1.02) or (low_val <= bb_low)

        if is_buy_signal:
            return {
                "price": curr_price,
                "rec": rec_val,
                "ema": ema365,
                "bb_low": bb_low
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
        else: # 코인 (BTC 최우선 배치)
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
            status_text.text(f"차트 내부 신호 확인 중: {name}")
            
            res = get_tv_direct_signal(symbol, scr, exch, interval_map[tf_choice])
            
            if res:
                st.success(f"🎯 **{name}({symbol})** 포착! (신호 강도: {res['rec']:.2f})")
                st.session_state.found_data.append({
                    "종목": name, "가격": res['price'], "BB하단": round(res['bb_low'], 2) if res['bb_low'] else "N/A", "신호강도": round(res['rec'], 2), "365EMA": round(res['ema'], 1) if res['ema'] else "N/A"
                })
            time.sleep(0.01)

        status_text.text(f"✅ 스캔 완료! (총 {len(st.session_state.found_data)}건 발견)")

    except Exception as e:
        st.error(f"오류 발생: {e}")

if st.session_state.found_data:
    st.divider()
    st.dataframe(pd.DataFrame(st.session_state.found_data), use_container_width=True)
else:
    if start_button:
        st.warning("조건에 부합하는 종목이 없습니다. 사이드바의 '신호 감도'를 낮춰서 다시 시도해 보세요.")
