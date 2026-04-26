import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from tradingview_ta import TA_Handler, Interval, Exchange
import requests
from datetime import datetime
import time

# 페이지 설정
st.set_page_config(page_title="트레이딩뷰 스캐너", page_icon="📊", layout="wide")

st.title("📊 트레이딩뷰 실시간 기술적 분석 스캐너")
st.markdown("트레이딩뷰의 강력한 분석 엔진을 사용하여 **BB 하단 돌파 + RSI 과매도**를 포착합니다.")

# 사이드바 설정
with st.sidebar:
    st.header("🔍 검색 설정")
    market = st.selectbox("대상 선택", ["국내주식 (KRX)", "미국주식 (NASDAQ/NYSE)", "업비트 코인"])
    
    # 요청하신 6가지 타임프레임
    tf_choice = st.selectbox("타임프레임", ["5분봉", "1시간봉", "4시간봉", "일봉", "주봉", "월봉"])
    
    # 트레이딩뷰 인터벌 매핑
    interval_map = {
        "5분봉": Interval.INTERVAL_5_MINUTES,
        "1시간봉": Interval.INTERVAL_1_HOUR,
        "4시간봉": Interval.INTERVAL_4_HOURS,
        "일봉": Interval.INTERVAL_1_DAY,
        "주봉": Interval.INTERVAL_1_WEEK,
        "월봉": Interval.INTERVAL_1_MONTH
    }

    st.divider()
    top_n = st.number_input("스캔할 종목 수", min_value=1, max_value=300, value=50)
    rsi_limit = st.slider("RSI 과매도 기준", 10, 70, 35)
    
    start_button = st.button("🚀 트레이딩뷰 스캔 시작", use_container_width=True)

# 트레이딩뷰 분석 함수
def get_tv_signal(symbol, exchange, screener, interval):
    try:
        handler = TA_Handler(
            symbol=symbol,
            exchange=exchange,
            screener=screener,
            interval=interval,
            timeout=10
        )
        analysis = handler.get_analysis()
        indicators = analysis.indicators
        
        close = indicators.get("close")
        lower_bb = indicators.get("BB.lower")
        rsi = indicators.get("RSI")
        
        # 조건: 현재가 <= 볼린저밴드 하단 AND RSI <= 설정값
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
        # 1. 리스트 구성
        if "국내" in market:
            df_list = fdr.StockListing('KRX').head(top_n)
            tickers = [(row['Code'], row['Name'], "KRX", "korea") for _, row in df_list.iterrows()]
        elif "미국" in market:
            df_list = fdr.StockListing('NASDAQ').head(top_n)
            tickers = [(row['Symbol'], row['Symbol'], "NASDAQ", "america") for _, row in df_list.iterrows()]
        else:
            res = requests.get("https://api.upbit.com/v1/market/all").json()
            tickers = [(m['market'].split('-')[1], m['korean_name'], "UPBIT", "crypto") for m in res if m['market'].startswith('KRW-')][:top_n]

        # 2. 분석 실행
        for i, (symbol, name, exch, scr) in enumerate(tickers):
            progress_bar.progress((i + 1) / len(tickers))
            status_text.text(f"TV 분석 중: {name} ({i+1}/{len(tickers)})")
            
            res = get_tv_signal(symbol, exch, scr, interval_map[tf_choice])
            if res:
                st.success(f"✅ {name} 포착! (가격: {res['price']:,}, RSI: {res['rsi']:.1f})")
                found_data.append({"종목": name, "가격": res['price'], "RSI": round(res['rsi'], 1)})
            
            time.sleep(0.1) # 서버 부하 방지

        status_text.text(f"✅ {tf_choice} 분석 완료!")
        if found_data:
            st.divider()
            st.table(pd.DataFrame(found_data))
    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}\n\n라이브러리 'tradingview_ta'가 설치되어 있는지 확인해 주세요.")
