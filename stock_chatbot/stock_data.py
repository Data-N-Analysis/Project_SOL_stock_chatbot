import pandas as pd
from bs4 import BeautifulSoup
import datetime
import FinanceDataReader as fdr
from datetime import datetime, timedelta, time  
import streamlit as st
import requests

# 📌 가장 최근 거래일을 구하는 함수
def get_recent_trading_day():
    """
    가장 최근 거래일을 구하는 함수
    Returns:
        str: 최근 거래일(YYYY-MM-DD 형식)
    """
    today = datetime.now()  # ✅ datetime.datetime.now() → datetime.now()
    if today.hour < 9:  
        today -= timedelta(days=1)
    while today.weekday() in [5, 6]:  
        today -= timedelta(days=1)
    return today.strftime('%Y-%m-%d')


# 📌 기업명으로부터 증권 코드를 찾는 함수 (KRX 기준)
def get_ticker(company):
    """
    기업명으로부터 증권 코드를 찾는 함수
    Args:
        company (str): 기업명
    Returns:
        str: 티커 코드 (6자리 숫자 문자열)
    """
    try:
        listing = fdr.StockListing('KRX')
        ticker_row = listing[listing["Name"].str.strip() == company.strip()]
        if not ticker_row.empty:
            return str(ticker_row.iloc[0]["Code"]).zfill(6)  # KRX용 티커 반환
        return None
    except Exception as e:
        st.error(f"티커 조회 중 오류 발생: {e}")
        return None


def get_naver_fchart_minute_data(stock_code, minute="1", days=1):
    """
    네이버 금융 Fchart API에서 분봉 데이터를 가져와서 DataFrame으로 변환
    """
    now = datetime.now()

    if now.hour < 9:
        now -= timedelta(days=1)

    if now.weekday() == 6:  # 일요일
        now -= timedelta(days=2)  # 금요일로 이동
    elif now.weekday() == 5:  # 토요일
        now -= timedelta(days=1)  # 금요일로 이동

    target_date = now.strftime("%Y-%m-%d") if days == 1 else None

    url = f"https://fchart.stock.naver.com/sise.nhn?symbol={stock_code}&timeframe=minute&count={days * 78}&requestType=0"
    response = requests.get(url)

    if response.status_code != 200:
        return pd.DataFrame()

    soup = BeautifulSoup(response.text, "lxml")

    data_list = []
    for item in soup.find_all("item"):
        values = item["data"].split("|")
        if len(values) < 6:
            continue

        time_str, _, _, _, close, _ = values  
        if close == "null":
            continue

        time_val = datetime.strptime(time_str, "%Y%m%d%H%M")  # ✅ datetime 변환
        close = float(close)

        if target_date:
            if time_val.strftime("%Y-%m-%d") == target_date:
                data_list.append([time_val, close])
        else:
            data_list.append([time_val, close])

    df = pd.DataFrame(data_list, columns=["시간", "종가"])

    # ✅ '시간'을 datetime 형식으로 변환
    df["시간"] = pd.to_datetime(df["시간"])

    # ✅ 9시 ~ 15시 30분 데이터만 필터링 (datetime.time 올바르게 사용)
    df = df[(df["시간"].dt.time >= time(9, 0)) & (df["시간"].dt.time <= time(15, 30))]

    return df


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
        df = df.rename(columns={"Date": "Date", "Close": "Close"})
        df["Date"] = pd.to_datetime(df["Date"])
        df = df[df["Date"].dt.weekday < 5].reset_index(drop=True)
        return df
    except Exception as e:
        st.error(f"FinanceDataReader 데이터 불러오기 오류: {e}")
        return pd.DataFrame()
