import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from tradingview_ta import TA_Handler, Interval, Exchange
from datetime import datetime
import requests
import io

# 페이지 설정
st.set_page_config(page_title="트레이딩뷰 엔진 스캐너", page_icon="📈", layout="wide")

st.title("📈 트레이딩뷰 기반 글로벌 실시간 스캐너")
st.markdown("야후 파이낸스 대신 **트레이딩뷰 기술적 분석 엔진**을 사용하여 정확한 신호를 포착합니다.")

# --- 세션 상태 초기화 ---
if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# 사이드바 설정
with st.sidebar:
    st.header("🔍 검색 설정")
    market = st.selectbox("대상 선택", ["국내주식 (KOSPI/KOSDAQ)", "미국주식 (NASDAQ/NYSE)", "업비트 코인 (원화마켓)"])
    
    # 트레이딩뷰 인터벌 매핑
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
    top_n = st.number_input("스캔할 종목 수 (시총순)", min_value=1, max_value=500, value=100)
    
    use_per = st.checkbox("PER 필터 사용 (국내 전용)", value=True)
    per_limit = st.number_input("PER 기준 (이하)", min_value=0.0, max_value=100.0, value=15.0)
    
    rsi_threshold = st.slider("RSI 과매도 기준", 10, 70, 35)
    
    start_button = st.button("🚀 트레이딩뷰 엔진으로 스캔 시작", use_container_width=True)

# --- 분석 핵심 함수 ---
def get_tv_analysis(symbol, exchange, screen, interval):
    """트레이딩뷰에서 기술적 지표 결과만 쏙 뽑아오는 함수"""
    try:
        handler = TA_Handler(
            symbol=symbol,
            exchange=exchange,
            screener=screen,
            interval=interval,
            timeout=5
        )
        analysis = handler.get_analysis()
        
        # 볼린저 밴드 및 RSI 지표 추출
        indicators = analysis.indicators
        close = indicators.get("close")
        lower_bb = indicators.get("BB.lower")
        rsi = indicators.get("RSI")
        
        # 신호 체크: 현재가가 볼린저 하단보다 낮거나 같고, RSI가 기준치 이하인 경우
        if close and lower_bb and rsi:
            if close <= lower_bb and rsi <= rsi_threshold:
                return {"price": close, "rsi": rsi}
        return None
    except:
        return None

# --- 분석 시작 ---
if start_button:
    st.session_state.found_data = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        # 1. 리스트 확보 및 시총 필터링
        with st.spinner("리스트 분석 중..."):
            if "국내" in market:
                df_list = fdr.StockListing('KRX')
                cap_col = next((c for c in ['MarCap', '시가총액'] if c in df_list.columns), None)
                df_list[cap_col] = pd.to_numeric(df_list[cap_col], errors='coerce')
                if use_per and 'PER' in df_list.columns:
                    df_list['PER'] = pd.to_numeric(df_list['PER'], errors='coerce')
                    df_list = df_list[(df_list['PER'] > 0) & (df_list['PER'] <= per_limit)]
                df_list = df_list.sort_values(cap_col, ascending=False).head(int(top_n))
                # 트레이딩뷰용 포맷: KRX 종목은 보통 'KOSPI' 또는 'KOSDAQ'
                tickers = [(row['Code'], row['Name'], 'KRX', 'korea', row.get('PER', 'N/A')) for _, row in df_list.iterrows()]
            
            elif "미국" in market:
                df_list = fdr.StockListing('NASDAQ').head(int(top_n))
                tickers = [(row['Symbol'], row['Symbol'], 'NASDAQ', 'america', 'N/A') for _, row in df_list.iterrows()]
            
            else: # 업비트
                res = requests.get("https://api.upbit.com/v1/market/all").json()
                raw_coins = [m for m in res if m['market'].startswith('KRW-')]
                # 코인은 'UPBIT' 거래소 사용
                tickers = [(m['market'].split('-')[1], m['korean_name'], 'UPBIT', 'crypto', 'N/A') for m in raw_coins[:int(top_n)]]

        # 2. 트레이딩뷰 엔진으로 스캔
        scan_count = len(tickers)
        for i, (symbol, name, exch, screen, per_val) in enumerate(tickers):
            progress_bar.progress((i + 1) / scan_count)
            status_text.text(f"TV 분석 중: {name} ({i+1}/{scan_count})")
            
            # 트레이딩뷰 엔진 호출
            res = get_tv_analysis(symbol, exch, screen, interval_map[tf_choice])
            
            if res:
                st.success(f"✅ **{name}** 포착! (가격: {res['price']:,} / RSI: {res['rsi']:.1f})")
                st.session_state.found_data.append({
                    "시간": datetime.now().strftime('%H:%M'),
                    "종목": name,
                    "현재가": res['price'],
                    "RSI": round(res['rsi'], 1),
                    "PER": per_val
                })
            
            # 너무 빠르면 차단될 수 있으므로 아주 짧은 휴식
            time.sleep(0.1)

        status_text.text(f"✅ {tf_choice} 트레이딩뷰 스캔 완료!")

    except Exception as e:
        st.error(f"오류 발생: {e}")

# --- 결과 출력 ---
if st.session_state.found_data:
    st.divider()
    res_df = pd.DataFrame(st.session_state.found_data)
    st.dataframe(res_df, use_container_width=True)
    st.download_button("📥 결과 저장 (CSV)", res_df.to_csv(index=False).encode('utf-8-sig'), "tv_scan.csv", "text/csv")
elif start_button:
    st.warning("트레이딩뷰 분석 결과, 조건에 맞는 종목이 없습니다. RSI 기준을 높여보세요.")
