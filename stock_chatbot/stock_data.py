import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import time
def get_recent_trading_day():
    """
    가장 최근 거래일을 구하는 함수

    Returns:
        str: 최근 거래일(YYYY-MM-DD 형식)
    """
    today = datetime.now()
    if today.hour < 9:  # 9시 이전이면 전날을 기준으로
        today -= timedelta(days=1)
    while today.weekday() in [5, 6]:  # 토요일(5), 일요일(6)이면 하루씩 감소
        today -= timedelta(days=1)
    return today.strftime('%Y-%m-%d')


def get_ticker(company, source="yahoo"):
    """
    기업명으로부터 증권 코드를 찾는 함수

    Args:
        company (str): 기업명
        source (str): 데이터 소스 ("yahoo" 또는 "fdr")

    Returns:
        str: 티커 코드
    """
    try:
        listing = fdr.StockListing('KRX')
        ticker_row = listing[listing["Name"].str.strip() == company.strip()]
        if not ticker_row.empty:
            krx_ticker = str(ticker_row.iloc[0]["Code"]).zfill(6)
            if source == "yahoo":
                return krx_ticker + ".KS"  # 야후 파이낸스용 티커 변환
            return krx_ticker  # FinanceDataReader용 티커
        return None
    except Exception as e:
        st.error(f"티커 조회 중 오류 발생: {e}")
        return None


# 📌 네이버 Fchart API에서 분봉 데이터 가져오기 (최신 거래일 탐색 포함)
def get_naver_fchart_minute_data(stock_code, minute="1", days=1):
    """
    네이버 금융 Fchart API에서 분봉 데이터를 더 효율적으로 가져오기

    Args:
        stock_code (str): 종목 코드
        minute (str): 분 단위 (기본 1분)
        days (int): 조회 일수

    Returns:
        pd.DataFrame: 분봉 데이터
    """
    # 요청 시도 최대 횟수 제한
    MAX_RETRIES = 3

    for attempt in range(MAX_RETRIES):
        try:
            # 현재 날짜 기준 최신 거래일 찾기
            now = datetime.now()
            if now.hour < 9:
                now -= timedelta(days=1)

            # 주말 제외
            while now.weekday() in [5, 6]:
                now -= timedelta(days=1)

            # API 요청 URL 구성 (더 많은 데이터 요청)
            url = f"https://fchart.stock.naver.com/sise.nhn?symbol={stock_code}&timeframe=minute&count={days * 200}&requestType=0"

            # 요청 시간 제한 추가
            response = requests.get(url, timeout=10)

            # 요청 실패 시 예외 발생
            response.raise_for_status()

            # BeautifulSoup 대신 더 빠른 XML 파싱
            soup = BeautifulSoup(response.text, "lxml")

            # 데이터 리스트 초기화 (리스트 컴프리헨션 사용)
            data_list = [
                [
                    datetime.strptime(item["data"].split("|")[0], "%Y%m%d%H%M"),
                    float(item["data"].split("|")[4])
                ]
                for item in soup.find_all("item")
                if len(item["data"].split("|")) >= 6 and item["data"].split("|")[4] != "null"
            ]

            # DataFrame 생성
            df = pd.DataFrame(data_list, columns=["시간", "종가"])

            # 거래 시간 필터링 (9시 ~ 15시 30분)
            df["시간"] = pd.to_datetime(df["시간"])
            df = df[
                (df["시간"].dt.time >= time(9, 0)) &
                (df["시간"].dt.time <= time(15, 30))
                ]

            # 데이터가 있으면 반환
            if not df.empty:
                return df

            # 데이터가 없으면 이전 날짜로 이동
            now -= timedelta(days=1)

        except (requests.RequestException, ValueError) as e:
            st.error(f"데이터 요청 중 오류 발생 (시도 {attempt + 1}/{MAX_RETRIES}): {e}")

            # 마지막 시도에서 실패하면 빈 DataFrame 반환
            if attempt == MAX_RETRIES - 1:
                return pd.DataFrame()

    return pd.DataFrame()

# 📌 FinanceDataReader를 통해 일별 시세를 가져오는 함수
def get_daily_stock_data_fdr(ticker, period):
    """
    FinanceDataReader를 통해 일별 시세를 가져오는 함수
    Args:
        ticker (str): 티커 코드
        period (str): 기간 ("1month" 또는 "1year")
    Returns:
        DataFrame: 주식 데이터
    """
    try:
        end_date = get_recent_trading_day()
        start_date = (datetime.strptime(end_date, '%Y-%m-%d') - timedelta(
            days=30 if period == "1month" else 365)).strftime('%Y-%m-%d')
        df = fdr.DataReader(ticker, start_date, end_date)
        if df.empty:
            return pd.DataFrame()
        df = df.reset_index()
        df["Date"] = pd.to_datetime(df["Date"])
        df = df[df["Date"].dt.weekday < 5].reset_index(drop=True)  # ✅ 주말 데이터 제거
        return df
    except Exception as e:
        st.error(f"FinanceDataReader 데이터 불러오기 오류: {e}")
        return pd.DataFrame()