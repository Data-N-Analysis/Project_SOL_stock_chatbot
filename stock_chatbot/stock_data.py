import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import streamlit as st

# ✅ 세션 상태 업데이트 함수 (기간 변경 시 즉시 반영)
def update_period():
    st.session_state.selected_period = st.session_state.radio_selection

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


def get_intraday_data_yahoo(ticker, period="1d", interval="1m"):
    """
    야후 파이낸스에서 분봉 데이터를 가져오는 함수

    Args:
        ticker (str): 티커 코드
        period (str): 기간 ("1d" 또는 "5d")
        interval (str): 간격 ("1m" 또는 "5m")

    Returns:
        DataFrame: 주식 데이터
    """
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        if df.empty:
            return pd.DataFrame()
        df = df.reset_index()
        df = df.rename(columns={"Datetime": "Date", "Close": "Close",
                                "Open": "Open", "High": "High", "Low": "Low"})
        # 주말 데이터 제거
        df["Date"] = pd.to_datetime(df["Date"])
        df = df[df["Date"].dt.weekday < 5].reset_index(drop=True)
        return df
    except Exception as e:
        st.error(f"야후 파이낸스 데이터 불러오기 오류: {e}")
        return pd.DataFrame()


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
        # 주말 데이터 완전 제거
        df["Date"] = pd.to_datetime(df["Date"])
        df = df[df["Date"].dt.weekday < 5].reset_index(drop=True)
        return df
    except Exception as e:
        st.error(f"FinanceDataReader 데이터 불러오기 오류: {e}")
        return pd.DataFrame()
