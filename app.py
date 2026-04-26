import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
from datetime import datetime
import time

# 페이지 설정
st.set_page_config(page_title="Double BB Scanner", page_icon="📈", layout="wide")

st.title("📈 전략 일치형: Double BB + 365 EMA 스캐너")
st.markdown("차트에 떠 있는 **과거의 BUY 신호**까지 모두 추적하여 리스트업합니다.")

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
    std_dev_1 = st.number_input("Standard Deviation 1", value=1.00, step=0.1)
    std_dev_2 = st.number_input("Standard Deviation 2", value=2.00, step=0.1)
    
    st.divider()
    use_per = st.checkbox("저PER 필터 사용 (국내 전용)", value=False)
    per_limit = st.number_input("PER 기준 (이하)", value=15.0)
    
    start_button = st.button("🚀 차트 신호 추적 스캔 시작", use_container_width=True)

# 트레이딩뷰 과거 이력 추적 함수 (가장 중요)
def get_tv_history_signal(symbol, screener, exchange, interval):
    try:
        url = f"https://scanner.tradingview.com/{screener}/scan"
        # 현재부터 과거 12개 봉(월봉 기준 1년)의 종가와 BB 데이터를 요청
        columns = ["close", "sma[20]", "StdDev.20", "EMA365"]
        for i in range(1, 13):
            columns.extend([f"close[{i}]", f"sma[20][{i}]", f"StdDev.20[{i}]"])
            
        payload = {
            "symbols": {"tickers": [f"{exchange}:{symbol}"], "query": {"types": []}},
            "columns": columns
        }
        res = requests.post(url, json=payload, timeout=10).json()
        if 'data' not in res or not res['data']: return None
        
        d = res['data'][0]['d']
        
        # 최근 12개 봉 중 '교차(Crossover)'가 발생한 지점이 있는지 확인
        # 차트의 BUY 신호는 한 번 발생하면 다음 신호 전까지 유지되는 경우가 많음
        found_signal = False
        signal_idx = -1
        
        for i in range(12):
            # i번째 봉 데이터 (i=0이 현재)
            c = d[i*3]     # close
            ma = d[i*3+1]  # sma[20]
            sd = d[i*3+2]  # stddev
            
            # i+1번째 봉 데이터 (이전 봉)
            prev_c = d[(i+1)*3]
            
            if None in [c, ma, sd, prev_c]: continue
            
            l1 = ma - (sd * std_dev_1)
            
            # 골든크로스 조건: 이전 봉은 하단선 아래, 현재 봉은 하단선 위
            if prev_c <= l1 and c > l1:
                found_signal = True
                signal_idx = i
                break
            
            # 혹은 현재가가 여전히 매수 구간(하단선 1.0 아래)에 머물러 있는 경우
            if i == 0 and c <= l1:
                found_signal = True
                signal_idx = 0
                break

        if found_signal:
            return {
                "price": d[0],
                "ema365": d[39], # EMA365는 리스트 마지막 즈음에 위치
                "idx": signal_idx
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
        else: # 코인 (BTC 최우선)
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
            status_text.text(f"과거 신호 이력 추적 중: {name}")
            
            res = get_tv_history_signal(symbol, scr, exch, interval_map[tf_choice])
            
            if res:
                msg = "현재 봉 신호" if res['idx'] == 0 else f"{res['idx']}개월 전 신호 발생"
                st.success(f"🎯 **{name}({symbol})** 포착! ({msg})")
                st.session_state.found_data.append({
                    "종목": name, "가격": res['price'], "신호시점": msg, "365EMA": round(res['ema365'], 1) if res['ema365'] else "N/A"
                })
            time.sleep(0.01)

        status_text.text(f"✅ 스캔 완료! (총 {len(st.session_state.found_data)}건 발견)")

    except Exception as e:
        st.error(f"오류: {e}")

if st.session_state.found_data:
    st.divider()
    st.dataframe(pd.DataFrame(st.session_state.found_data), use_container_width=True)
else:
    if start_button:
        st.warning("과거 1년치 이력에서도 신호를 찾지 못했습니다. 파라미터 설정을 다시 확인해 주세요.")
