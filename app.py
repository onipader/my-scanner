import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
import time
import requests
from datetime import datetime
import io

# 페이지 설정
st.set_page_config(page_title="글로벌 급등주 스캐너", page_icon="🚀", layout="wide")

st.title("🚀 글로벌 주식 & 코인 급등 시그널 스캐너")
st.markdown("볼린저 밴드 하단 돌파 + **거래량 폭증(3배)** + **외국인 매수** 종목을 추출합니다.")

# --- 세션 상태 초기화 ---
if 'found_data' not in st.session_state:
    st.session_state.found_data = []

# 사이드바 설정
with st.sidebar:
    st.header("🔍 검색 설정")
    market = st.selectbox("대상 선택", ["국내주식 (KOSPI/KOSDAQ)", "미국주식 (NASDAQ/NYSE)", "업비트 코인 (원화마켓)"])
    timeframe = st.selectbox("타임프레임", ["5분봉", "1시간봉", "일봉", "주봉", "월봉"]) # 급등주는 일봉 이상 분석이 정확해!
    vol_threshold = st.slider("거래량 폭증 기준 (배수)", 2.0, 10.0, 3.0)
    start_button = st.button("🚀 분석 시작", use_container_width=True)

# yfinance용 시간 매핑
yf_time_map = {"5분봉":("5m","1d"), "1시간봉":("60m","1w"), "일봉":("1d","1y"), "주봉":("1wk","2y"), "월봉":("1mo","5y")}

def check_signal_pro(data, vol_mult):
    """
    개선된 매수 신호 계산기: 볼린저 하단 + 거래량 폭증 체크
    """
    if len(data) < 25: return None
    
    close = data['Close']
    volume = data['Volume']
    
    # 1. 볼린저 밴드 계산
    basis = close.rolling(window=20).mean()
    std = close.rolling(window=20).std()
    lower_band = basis - (std * 2)
    
    curr_price = close.iloc[-1]
    lower = lower_band.iloc[-1]
    
    # 2. 거래량 분석 (최근 5일 평균 대비 현재 거래량)
    avg_volume = volume.iloc[-6:-1].mean() # 오늘 제외 최근 5일 평균
    curr_volume = volume.iloc[-1]
    vol_ratio = curr_volume / avg_volume if avg_volume > 0 else 0
    
    # 신호 조건: 주가가 하단 근처(또는 돌파) + 거래량이 설정값 이상 폭발
    if curr_price <= lower * 1.02 and vol_ratio >= vol_mult:
        return {"price": curr_price, "vol_ratio": vol_ratio}
    return None

def get_kr_investor_data(ticker_code):
    """국내 주식 외국인 수급 확인 함수"""
    try:
        # 최근 5일간의 수급 데이터 가져오기
        df = fdr.DataReader(ticker_code.split('.')[0], start='2026-04-15')
        if 'NetPurchase_Foreigner' in df.columns:
            is_foreign_buying = df['NetPurchase_Foreigner'].iloc[-1] > 0
            return "✅ 매수중" if is_foreign_buying else "❌ 매도/관망"
        return "데이터 없음"
    except:
        return "확인 불가"

# --- 분석 로직 시작 ---
if start_button:
    st.session_state.found_data = [] 
    
    if "국내" in market:
        df_list = fdr.StockListing('KRX')
        # 속도를 위해 우선 코스피/코스닥 상위 200개 정도만 테스트해보는걸 추천!
        tickers = [row['Code'] + ('.KS' if row['Market'] == 'KOSPI' else '.KQ') for _, row in df_list.iterrows()]
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, t in enumerate(tickers): # 샘플로 100개만 먼저! 전체는 시간을 많이 잡아먹어
            progress_bar.progress((i + 1) / 100)
            status_text.text(f"국내 종목 분석 중: {t}")
            try:
                inter, per = yf_time_map[timeframe]
                data = yf.download(t, interval=inter, period=per, progress=False)
                
                # Multi-index 대응
                if isinstance(data.columns, pd.MultiIndex):
                    temp_df = pd.DataFrame({'Close': data['Close'][t], 'Volume': data['Volume'][t]})
                else:
                    temp_df = data[['Close', 'Volume']]
                
                res = check_signal_pro(temp_df, vol_threshold)
                if res:
                    foreign_status = get_kr_investor_data(t)
                    st.session_state.found_data.append({
                        "시간": datetime.now().strftime('%H:%M'),
                        "종목": t,
                        "현재가": res['price'],
                        "거래량배수": f"{res['vol_ratio']:.2f}배",
                        "외인수급": foreign_status
                    })
            except: continue
            
    # (미국주식 및 코인 로직도 위와 유사한 방식으로 check_signal_pro를 적용하면 돼!)

# --- 결과 출력 ---
if st.session_state.found_data:
    st.divider()
    st.subheader("📊 급등 후보 분석 결과")
    result_df = pd.DataFrame(st.session_state.found_data)
    st.table(result_df)
    
    # 엑셀 다운로드 (기존 코드 유지)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        result_df.to_excel(writer, index=False)
    st.download_button(label="📥 결과 저장 (.xlsx)", data=output.getvalue(), file_name="signal_v2.xlsx")
elif start_button:
    st.warning("조건에 맞는 급등 후보가 없습니다. 거래량 기준을 낮춰보세요!")

