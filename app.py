import streamlit as st
import yfinance as yf
import pandas as pd
import time
import requests
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="글로벌 자산 스캐너", layout="wide")
st.title("💰 글로벌 주식 & 코인 매수신호 스캐너")

if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# 2. 사이드바 설정
with st.sidebar:
    st.header("🔍 검색 설정")
    market_choice = st.selectbox("대상 선택", ["국내주식 (KOSPI/KOSDAQ)", "업비트 코인 (원화마켓)"])
    top_n = st.slider("스캔 범위 (상위 N개)", 10, 1000, 200, 50)
    tf_display = ["5분봉", "1시간봉", "4시간봉", "일봉", "주봉", "월봉"]
    tf_choice = st.selectbox("타임프레임", tf_display)
    start_button = st.button("🚀 분석 시작", use_container_width=True)

# 3. 매핑 및 신호 함수
yf_tf_map = {
    "5분봉": ("5m", "1d"), "1시간봉": ("60m", "1w"), "4시간봉": ("90m", "1mo"), 
    "일봉": ("1d", "1y"), "주봉": ("1wk", "2y"), "월봉": ("1mo", "5y")
}

def check_signal(df):
    if df is None or len(df) < 20: return None
    try:
        close = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
    except:
        close = df['Close']
    
    ma20 = close.rolling(window=20).mean()
    std = close.rolling(window=20).std()
    lower_band = ma20 - (std * 2)
    
    curr = close.iloc[-1]
    # 신호 포착: 하단선 2% 이내 근접 시 (더 잘 잡히게 조정)
    if curr <= lower_band.iloc[-1] * 1.02:
        return curr
    return None

# 4. 분석 실행
if start_button:
    st.session_state.found_data = []
    status_area = st.empty()
    progress_bar = st.progress(0)
    results_container = st.container()

    # 🔹 종목 리스트 생성 (외부 파일 의존성 제거)
    if "국내" in market_choice:
        # 주요 시총 상위 티커 리스트 (에러 방지용 직접 지정 + 확장)
        # 실제 운영 시에는 정제된 리스트를 사용해야 하나, 우선 작동을 위해 주요 종목 구성
        base_list = [
            ("005930.KS", "삼성전자"), ("000660.KS", "SK하이닉스"), ("373220.KS", "LG에너지솔루션"),
            ("207940.KS", "삼성바이오로직스"), ("005380.KS", "현대차"), ("068270.KS", "셀트리온"),
            ("000270.KS", "기아"), ("005490.KS", "POSCO홀딩스"), ("035420.KS", "NAVER"),
            ("006400.KS", "삼성SDI"), ("051910.KS", "LG화학"), ("035720.KS", "카카오"),
            ("012330.KS", "현대모비스"), ("000810.KS", "삼성화재"), ("066570.KS", "LG전자"),
            ("105560.KS", "KB금융"), ("055550.KS", "신한지주"), ("032830.KS", "삼성생명")
            # ... 추가 종목들
        ]
        target_list = base_list[:top_n]
    else:
        upbit_res = requests.get("https://api.upbit.com/v1/market/all").json()
        target_list = [[m['market'], m['korean_name']] for m in upbit_res if m['market'].startswith('KRW-')][:top_n]

    # 5. 스캔 루프
    for i, (ticker, name) in enumerate(target_list):
        progress_bar.progress((i + 1) / len(target_list))
        status_area.markdown(f"🔍 **분석 중 ({i+1}/{len(target_list)}):** `{name}`")
        
        try:
            itv, per = yf_tf_map[tf_choice]
            search_ticker = ticker.replace("KRW-", "") + "-KRW" if "업비트" in market_choice else ticker
            
            data = yf.download(search_ticker, interval=itv, period=per, progress=False, show_errors=False)
            if data.empty: continue
            
            price = check_signal(data)
            if price:
                with results_container:
                    st.success(f"✅ **{name}** 포착!")
                st.session_state.found_data.append({"시간": datetime.now().strftime('%H:%M'), "종목": name, "코드": ticker, "현재가": f"{price:,.0f}"})
            time.sleep(0.1)
        except: continue

    status_area.info(f"✅ 총 {len(target_list)}개 종목 분석 완료!")

# 6. 결과 출력
if st.session_state.found_data:
    st.table(pd.DataFrame(st.session_state.found_data))
elif start_button:
    st.warning("조건에 맞는 종목이 없습니다. 타임프레임을 일봉이나 1시간봉으로 바꿔보세요!")
