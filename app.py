import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
from datetime import datetime
import time

# 페이지 설정
st.set_page_config(page_title="Double BB Scanner", page_icon="📈", layout="wide")

st.title("📈 전략 일치형: Double BB + 365 EMA 스캐너")
st.markdown("트레이딩뷰 서버의 **실시간 기술적 분석 신호**를 직접 가져오도록 수정했습니다.")

# --- 세션 상태 초기화 ---
if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# 사이드바 설정
with st.sidebar:
    st.header("🔍 전략 설정")
    market = st.selectbox("대상 선택", ["업비트 코인", "국내주식 (KRX)", "미국주식 (NASDAQ/NYSE)"])
    tf_choice = st.selectbox("타임프레임", ["월봉", "주봉", "일봉", "4시간봉", "1시간봉", "5분봉"])
    
    # 트레이딩뷰 서버용 인터벌
    interval_map = {
        "5분봉": "5", "1시간봉": "60", "4시간봉": "240",
        "일봉": "", "주봉": "1W", "월봉": "1M"
    }

    st.divider()
    top_n = st.slider("스캔 대상 (상위 N개)", 10, 1000, 250)
    
    st.divider()
    st.subheader("⚙️ 필터 강도")
    # 신호 강도 선택 (강력 매수 신호가 포함된 종목만 필터)
    sig_strength = st.select_slider("신호 감도 (오른쪽일수록 엄격)", options=["매수 권장", "강력 매수"])

    st.divider()
    use_per = st.checkbox("저PER 필터 사용 (국내 전용)", value=False)
    per_limit = st.number_input("PER 기준 (이하)", value=15.0)
    
    start_button = st.button("🚀 실시간 신호 스캔 시작", use_container_width=True)

# 트레이딩뷰 엔진 신호 직접 추출 함수
def get_tv_engine_signal(symbol, screener, exchange, interval):
    try:
        url = f"https://scanner.tradingview.com/{screener}/scan"
        # 핵심: 트레이딩뷰의 모든 기술적 지표 합산 결과(Recommend.All)를 가져옴
        payload = {
            "symbols": {"tickers": [f"{exchange}:{symbol}"], "query": {"types": []}},
            "columns": ["Recommend.All", "close", "EMA365", "RSI", "BB.lower", "BB.upper"]
        }
        res = requests.post(url, json=payload, timeout=7).json()
        if 'data' not in res or not res['data']: return None
        
        d = res['data'][0]['d']
        rec_val, curr_price, ema365, rsi, bb_low = d[0], d[1], d[2], d[3], d[4]

        # 트레이딩뷰 추천 값 기준: 0.1~0.5(매수), 0.5~1.0(강력 매수)
        is_hit = False
        if sig_strength == "매수 권장":
            is_hit = rec_val > 0.1
        else:
            is_hit = rec_val > 0.5

        # 추가 조건: 현재가가 BB 하단 근처이거나 하단선 부근일 때 (Double BB 로직 보완)
        # 차트 지표의 BUY와 동기화하기 위해 하단 터치 여부 확인
        if is_hit or (curr_price <= bb_low * 1.02):
            return {
                "price": curr_price,
                "rec": rec_val,
                "ema365": ema365,
                "rsi": rsi
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
        else: # 코인 (비트코인 무조건 최상단)
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
            status_text.text(f"엔진 신호 분석 중: {name}")
            
            res = get_tv_engine_signal(symbol, scr, exch, interval_map[tf_choice])
            
            if res:
                st.success(f"🎯 **{name}({symbol})** 포착! (엔진 신호 강도: {res['rec']:.2f})")
                st.session_state.found_data.append({
                    "종목": name, "가격": res['price'], "신호강도": round(res['rec'], 2), "RSI": round(res['rsi'], 1), "EMA365": round(res['ema365'], 1) if res['ema365'] else "N/A"
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
        st.warning("현재 엔진에서 '매수' 신호로 분류된 종목이 없습니다. 감도를 조절해 보세요.")
