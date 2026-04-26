import streamlit as st
import yfinance as yf
import pandas as pd
import time
import requests
from datetime import datetime

# 페이지 설정
st.set_page_config(page_title="글로벌 자산 스캐너", layout="wide")
st.title("💰 글로벌 주식 & 코인 매수신호 스캐너")

if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# 사이드바 설정
with st.sidebar:
    st.header("🔍 검색 설정")
    market_choice = st.selectbox("대상 선택", ["국내주식 (KOSPI/KOSDAQ)", "업비트 코인 (원화마켓)"])
    
    # 시총 순위 범위 (이번 버전은 주요 종목 위주로 우선 복구)
    top_n = st.slider("시총 순위 범위 (상위 N개)", 10, 500, 100, 10)
    
    tf_display = ["5분봉", "1시간봉", "4시간봉", "일봉", "주봉", "월봉"]
    tf_choice = st.selectbox("타임프레임", tf_display)
    start_button = st.button("🚀 분석 시작", use_container_width=True)

# 타임프레임 매핑
yf_tf_map = {
    "5분봉": ("5m", "1d"), "1시간봉": ("60m", "1w"), "4시간봉": ("90m", "1mo"), 
    "일봉": ("1d", "1y"), "주봉": ("1wk", "2y"), "월봉": ("1mo", "5y")
}

def check_signal(df):
    if df is None or len(df) < 20: return None
    try:
        # 최신 yfinance MultiIndex 대응
        close = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
    except:
        close = df['Close']
        
    ma20 = close.rolling(window=20).mean()
    std = close.rolling(window=20).std()
    lower_band = ma20 - (std * 2)
    
    curr = close.iloc[-1]
    # 볼린저 밴드 하단선 1% 이내 근접 시 신호
    if curr <= lower_band.iloc[-1] * 1.01:
        return curr
    return None

if start_button:
    st.session_state.found_data = []
    status_area = st.empty()
    progress_bar = st.progress(0)
    results_container = st.container()

    # 1. 대상 리스트 확보 (404 에러 방지를 위해 직접 구성)
    if "국내" in market_choice:
        # 코스피/코스닥 주요 시총 상위 리스트 (예시를 확장하여 구성)
        krx_main = [
            ("005930.KS", "삼성전자"), ("000660.KS", "SK하이닉스"), ("373220.KS", "LG에너지솔루션"),
            ("207940.KS", "삼성바이오로직스"), ("005380.KS", "현대차"), ("068270.KS", "셀트리온"),
            ("000270.KS", "기아"), ("005490.KS", "POSCO홀딩스"), ("035420.KS", "NAVER"),
            ("006400.KS", "삼성SDI"), ("051910.KS", "LG화학"), ("035720.KS", "카카오"),
            ("003670.KS", "포스코푸처엠"), ("012330.KS", "현대모비스"), ("028260.KS", "삼성물산"),
            ("105560.KS", "KB금융"), ("055550.KS", "신한지주"), ("066570.KS", "LG전자"),
            ("000810.KS", "삼성화재"), ("032830.KS", "삼성생명"), ("086790.KS", "하나금융지주"),
            ("015760.KS", "한국전력"), ("033780.KS", "KT&G"), ("009150.KS", "삼성전기"),
            ("034730.KS", "SK"), ("329180.KS", "HD현대중공업"), ("010130.KS", "고려아연")
            # 필요시 여기에 더 추가 가능
        ]
        target_list = krx_main[:top_n]
    else:
        # 업비트 리스트 (이건 API라 404 안 남)
        upbit_res = requests.get("https://api.upbit.com/v1/market/all").json()
        target_list = [[m['market'], m['korean_name']] for m in upbit_res if m['market'].startswith('KRW-')][:top_n]

    # 2. 분석 루프
    count = len(target_list)
    for i, (ticker, name) in enumerate(target_list):
        progress_bar.progress((i + 1) / count)
        status_area.markdown(f"🔍 **분석 중 ({i+1}/{count}):** `{name}` ({ticker})")
        
        try:
            if "국내" in market_choice:
                itv, per = yf_tf_map[tf_choice]
                data = yf.download(ticker, interval=itv, period=per, progress=False, show_errors=False)
                if data.empty: continue
                price = check_signal(data)
            else:
                # 업비트용 yfinance 티커 변환
                coin_ticker = ticker.replace("KRW-", "") + "-KRW"
                itv, per = yf_tf_map[tf_choice]
                data = yf.download(coin_ticker, interval=itv, period=per, progress=False)
                price = check_signal(data)
                
            if price:
                with results_container:
                    st.success(f"✅ **{name}** 포착! 현재가: {price:,.0f}")
                st.session_state.found_data.append({"시간": datetime.now().strftime('%H:%M'), "종목": name, "코드": ticker, "현재가": price})
            
            time.sleep(0.2) # 속도 조절
        except:
            continue

    status_area.info(f"✅ 분석 완료! (대상: {len(target_list)}개 종목)")

if st.session_state.found_data:
    st.divider()
    st.table(pd.DataFrame(st.session_state.found_data))
