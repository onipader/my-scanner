import streamlit as st
import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
import time

# 제목 설정
st.title("💰 글로벌 주식 & 코인 낙폭과대 스캐너")
st.write("전 세계 주식과 코인을 분석하여 볼린저 밴드 하단을 돌파한 '단기 과매도' 종목을 찾습니다.")

# 분석 함수
def analyze_stock(ticker, name, is_kr=True):
    try:
        # 데이터 가져오기 (최근 100일치)
        df = yf.download(ticker, period="100d", interval="1d", progress=False)
        if len(df) < 30: return None

        # 볼린저 밴드 계산 (20일 기준)
        ma20 = df['Close'].rolling(window=20).mean()
        std = df['Close'].rolling(window=20).std()
        b_lower = ma20 - (std * 2) # 하단 밴드

        close = df['Close'].iloc[-1]
        lower_band = b_lower.iloc[-1]

        # 매수 신호 조건: 현재가가 볼린저 밴드 하단보다 낮을 때 (이평선 조건 삭제)
        if close < lower_band:
            return {
                "종목명": name,
                "티커": ticker,
                "현재가": f"{float(close):,.0f}" if is_kr else f"{float(close):,.2f}",
                "하단밴드": f"{float(lower_band):,.0f}" if is_kr else f"{float(lower_band):,.2f}",
                "상태": "🔴 하단 돌파"
            }
    except:
        return None
    return None

# 사이드바 설정
market = st.sidebar.selectbox("시장 선택", ["국내 코스피/코스닥", "미국 나스닥 100", "업비트 코인"])
start_btn = st.sidebar.button("분석 시작")

if start_btn:
    results = []
    status_text = st.empty()
    
    if "코인" in market:
        # 업비트 코인 리스트 (주요 코인)
        coin_list = {
            "KRW-BTC": "비트코인", "KRW-ETH": "이더리움", "KRW-XRP": "리플", 
            "KRW-SOL": "솔라나", "KRW-ADA": "에이다", "KRW-DOGE": "도지코인"
        }
        for ticker, name in coin_list.items():
            status_text.text(f"분석 중: {name}")
            res = analyze_stock(f"{ticker.split('-')[1]}-USD", name, is_kr=False)
            if res: results.append(res)
            
    else:
        is_kr = "국내" in market
        try:
            if is_kr:
                df_list = fdr.StockListing('KRX')
                # 상위 500개 정도만 우선 분석 (속도와 에러 방지)
                df_list = df_list.head(500)
                for _, row in df_list.iterrows():
                    name = row['Name']
                    code = row['Code']
                    ticker = code + (".KS" if row['Market'] == 'KOSPI' else ".KQ")
                    status_text.text(f"분석 중: {name}")
                    res = analyze_stock(ticker, name, is_kr=True)
                    if res: results.append(res)
            else:
                # 나스닥 100 예시
                tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META"] # 예시 리스트
                for ticker in tickers:
                    status_text.text(f"분석 중: {ticker}")
                    res = analyze_stock(ticker, ticker, is_kr=False)
                    if res: results.append(res)
        except:
            st.error("데이터를 불러오는 중 오류가 발생했습니다.")

    status_text.text("분석 완료!")
    
    if results:
        st.table(pd.DataFrame(results))
        # 엑셀 다운로드 기능
        df_res = pd.DataFrame(results)
        csv = df_res.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 결과 다운로드 (CSV)", csv, "scanner_results.csv", "text/csv")
    else:
        st.write("조건에 맞는 종목이 없습니다.")
