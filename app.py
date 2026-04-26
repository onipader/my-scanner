import streamlit as st
import FinanceDataReader as fdr
import pd as pd
from tradingview_ta import TA_Handler, Interval
import requests
from datetime import datetime
import time

# 페이지 설정
st.set_page_config(page_title="트레이딩뷰 스캐너", page_icon="📊", layout="wide")

st.title("📊 트레이딩뷰 실시간 기술적 분석 스캐너")
st.markdown("트레이딩뷰 엔진에 **저PER 필터**를 다시 결합했습니다.")

# 사이드바 설정
with st.sidebar:
    st.header("🔍 검색 설정")
    market = st.selectbox("대상 선택", ["국내주식 (KRX)", "미국주식 (NASDAQ/NYSE)", "업비트 코인"])
    tf_choice = st.selectbox("타임프레임", ["5분봉", "1시간봉", "4시간봉", "일봉", "주봉", "월봉"])
    
    interval_map = {
        "5분봉": Interval.INTERVAL_5_MINUTES,
        "1시간봉": Interval.INTERVAL_1_HOUR,
        "4시간봉": Interval.INTERVAL_4_HOURS,
        "일봉": Interval.INTERVAL_1_DAY,
        "주봉": Interval.INTERVAL_1_WEEK,
        "월봉": Interval.INTERVAL_1_MONTH
    }

    st.divider()
    st.subheader("⚙️ 필터 세부 조절")
    top_n = st.number_input("스캔할 종목 수", min_value=1, max_value=300, value=100)
    
    # --- PER 필터 부활 ---
    use_per = st.checkbox("저PER 필터 사용 (국내 전용)", value=True)
    per_limit = st.number_input("PER 기준 (이하)", min_value=0.0, max_value=100.0, value=15.0)
    
    rsi_limit = st.slider("RSI 과매도 기준", 10, 70, 35)
    start_button = st.button("🚀 스캔 시작", use_container_width=True)

# 트레이딩뷰 분석 함수
def get_tv_signal(symbol, exchange, screener, interval):
    try:
        handler = TA_Handler(
            symbol=symbol,
            exchange=exchange,
            screener=screener,
            interval=interval,
            timeout=7
        )
        analysis = handler.get_analysis()
        inds = analysis.indicators
        
        close = inds.get("close")
        lower_bb = inds.get("BB.lower")
        rsi = inds.get("RSI")
        
        if close and lower_bb and rsi:
            if close <= lower_bb and rsi <= rsi_limit:
                return {"price": close, "rsi": rsi}
        return None
    except:
        return None

if start_button:
    progress_bar = st.progress(0)
    status_text = st.empty()
    found_data = []

    try:
        # 1. 리스트 구성 및 PER 필터링
        with st.spinner("리스트 분석 중..."):
            if "국내" in market:
                df_list = fdr.StockListing('KRX')
                
                # PER 필터 적용
                if use_per and 'PER' in df_list.columns:
                    df_list['PER'] = pd.to_numeric(df_list['PER'], errors='coerce')
                    df_list = df_list[(df_list['PER'] > 0) & (df_list['PER'] <= per_limit)]
                
                cap_col = next((c for c in ['MarCap', '시가총액'] if c in df_list.columns), None)
                df_list = df_list.sort_values(cap_col, ascending=False).head(top_n)
                tickers = [(row['Code'], row['Name'], "KRX", "korea", row.get('PER', 'N/A')) for _, row in df_list.iterrows()]
            
            elif "미국" in market:
                df_list = fdr.StockListing('NASDAQ').head(top_n)
                tickers = [(row['Symbol'], row['Symbol'], "NASDAQ", "america", "N/A") for _, row in df_list.iterrows()]
            
            else: # 업비트
                res = requests.get("https://api.upbit.com/v1/market/all").json()
                tickers = [(m['market'].split('-')[1], m['korean_name'], "UPBIT", "crypto", "N/A") for m in res if m['market'].startswith('KRW-')][:top_n]

        # 2. 분석 실행
        for i, (symbol, name, exch, scr, per_val) in enumerate(tickers):
            progress_bar.progress((i + 1) / len(tickers))
            status_text.text(f"분석 중: {name} (PER: {per_val})")
            
            res = get_tv_signal(symbol, exch, scr, interval_map[tf_choice])
            if res:
                st.success(f"✅ {name} 포착! (PER: {per_val}, RSI: {res['rsi']:.1f})")
                found_data.append({"종목": name, "가격": res['price'], "RSI": round(res['rsi'], 1), "PER": per_val})
            
            time.sleep(0.05)

        status_text.text(f"✅ {tf_choice} 분석 완료!")
        if found_data:
            st.divider()
            st.dataframe(pd.DataFrame(found_data), use_container_width=True)
        else:
            st.warning("조건에 맞는 종목이 없습니다. 필터를 조정해 보세요.")

    except Exception as e:
        st.error(f"오류: {e}")
