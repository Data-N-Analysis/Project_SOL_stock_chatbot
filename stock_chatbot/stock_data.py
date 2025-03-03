import streamlit as st
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, time
import FinanceDataReader as fdr
from langchain_community.chat_models import ChatOpenAI

# 📌 가장 최근 거래일을 구하는 함수
def get_recent_trading_day():
    """
    가장 최근 거래일을 구하는 함수
    Returns:
        str: 최근 거래일(YYYY-MM-DD 형식)
    """
    today = datetime.now()
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

# 📌 네이버 Fchart API에서 분봉 데이터 가져오기 (최신 거래일 탐색 포함)
def get_naver_fchart_minute_data(stock_code, minute="1", days=1):
    """
    네이버 금융 Fchart API에서 분봉 데이터를 가져와서 DataFrame으로 변환
    """
    now = datetime.now()

    if now.hour < 9:
        now -= timedelta(days=1)

    # 📌 최신 거래일 찾기 (공휴일 대응)
    while True:
        target_date = now.strftime("%Y-%m-%d") if days == 1 else None
        url = f"https://fchart.stock.naver.com/sise.nhn?symbol={stock_code}&timeframe=minute&count={days * 78}&requestType=0"
        response = requests.get(url)

        if response.status_code != 200:
            return pd.DataFrame()  # 요청 실패 시 빈 데이터 반환

        soup = BeautifulSoup(response.text, "lxml")

        data_list = []
        for item in soup.find_all("item"):
            values = item["data"].split("|")
            if len(values) < 6:
                continue

            time_str, _, _, _, close, _ = values
            if close == "null":
                continue

            time_val = datetime.strptime(time_str, "%Y%m%d%H%M")
            close = float(close)

            if target_date:
                if time_val.strftime("%Y-%m-%d") == target_date:
                    data_list.append([time_val, close])
            else:
                data_list.append([time_val, close])

        df = pd.DataFrame(data_list, columns=["시간", "종가"])

        # 📌 ✅ 9시 ~ 15시 30분 데이터만 필터링
        df["시간"] = pd.to_datetime(df["시간"])
        df = df[(df["시간"].dt.time >= time(9, 0)) & (df["시간"].dt.time <= time(15, 30))]

        # ✅ 데이터가 없는 경우 → 하루 전으로 이동하여 다시 시도
        if df.empty:
            now -= timedelta(days=1)
            while now.weekday() in [5, 6]:  # 토요일(5) 또는 일요일(6)
                now -= timedelta(days=1)
        else:
            break  # 데이터를 찾았으면 반복 종료

    return df

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


def generate_company_summary(company_name, news_data, openai_api_key):
    try:
        # 기업 정보 수집
        ticker_krx = get_ticker(company_name)
        if not ticker_krx:
            return f"## {company_name}에 대한 정보를 찾을 수 없습니다."

        ticker_yahoo = ticker_krx + ".KS"

        # 향상된 주식 정보 수집 함수 사용
        stock_info = get_enhanced_stock_info(ticker_yahoo, ticker_krx)

        # 단위를 추가하기 위한 헬퍼 함수들
        def add_percent_if_needed(value):
            """비율 값에 퍼센트 단위가 없으면 추가"""
            if value == '정보 없음' or value == 'N/A':
                return value

            # 이미 % 기호가 포함되어 있는지 확인
            if '%' not in value:
                # 숫자만 추출
                import re
                num_match = re.search(r'[\d,.]+', value)
                if num_match:
                    num_str = num_match.group()
                    try:
                        # 콤마 제거 후 숫자로 변환
                        num = float(num_str.replace(',', ''))
                        return f"{num:.2f}%"
                    except:
                        return f"{value}%"
                else:
                    return f"{value}%"
            return value

        def add_won_if_needed(value):
            """BPS와 같은 값에 원 단위가 없으면 추가"""
            if value == '정보 없음' or value == 'N/A':
                return value

            # 이미 '원' 문자가 포함되어 있는지 확인
            if '원' not in value:
                # 숫자 형식인지 확인
                import re
                num_match = re.search(r'[\d,.]+', value)
                if num_match:
                    num_str = num_match.group()
                    try:
                        # 콤마 제거 후 숫자로 변환
                        num = float(num_str.replace(',', ''))
                        # 천 단위 콤마를 추가한 형식으로 반환
                        return f"{int(num):,}원"
                    except:
                        return f"{value}원"
                else:
                    return f"{value}원"
            return value

        def format_currency_value(value):
            """당기순이익과 같은 큰 금액에 적절한 단위(억원, 조원) 추가"""
            if value == '정보 없음' or value == 'N/A':
                return value

            # 이미 단위가 포함되어 있는지 확인
            if '억원' in value or '조원' in value or '만원' in value:
                return value

            # 숫자만 추출
            import re
            num_match = re.search(r'[\d,.]+', value)
            if not num_match:
                return value

            num_str = num_match.group()
            try:
                # 콤마 제거 후 숫자로 변환
                num = float(num_str.replace(',', ''))

                # 크기에 따라 적절한 단위 적용
                if abs(num) >= 1_0000_0000_0000:  # 1조 이상
                    return f"{num / 1_0000_0000_0000:.2f}조원"
                elif abs(num) >= 1_0000_0000:  # 1억 이상
                    return f"{num / 1_0000_0000:.2f}억원"
                else:
                    return f"{int(num):,}원"
            except:
                return f"{value}원"

        # 뉴스 요약 생성
        llm = ChatOpenAI(openai_api_key=openai_api_key, model_name='gpt-4', temperature=0)

        # 모든 뉴스 통합 후 전체 요약 요청
        all_news_text = "\n\n".join(
            [f"제목: {news['title']}\n내용: {news['content']}\n출처: {news['link']}" for news in news_data[:10]])

        prompt = f"""
        {company_name}에 관한 다음 뉴스들을 통합 분석하여 투자자에게 유용한 정보를 제공해주세요:

        {all_news_text}

        HTML 형식으로 응답해주세요:
        <div>
            <h4 style="font-size: 21px; margin-bottom: 0;">최신 동향</h4>
            <ol style="font-size: 14px; margin-top: 5px;">
                <li>[동향 내용 1] (출처: <a href="뉴스링크" target="_blank">출처명</a>)</li>
                <li>[동향 내용 2] (출처: <a href="뉴스링크" target="_blank">출처명</a>)</li>
                <!-- 4-7개 항목 -->
            </ol>

            <h4 style="font-size: 21px; margin-top: 1.5em; margin-bottom: 0;">투자 영향 요인</h4>
            <div style="font-size: 14px; margin-top: 5px;">
                <h5 style="color: green; font-size: 17px; margin-bottom: 0;">✅ 긍정적 요인</h5>
                <ul style="margin-top: 5px;">
                    <li>[긍정적 요인 1]</li>
                    <!-- 2-3개 항목 -->
                </ul>

                <h5 style="color: red; font-size: 17px; margin-bottom: 0;">⚠️ 부정적 요인</h5>
                <ul style="margin-top: 5px;">
                    <li>[부정적 요인 1]</li>
                    <!-- 2-3개 항목 -->
                </ul>
            </div>

            <h4 style="font-size: 21px; margin-top: 1.5em; margin-bottom: 0;">💹 투자 전망 및 조언</h4>
            <p style="font-size: 14px; margin-top: 5px;">[투자 전망 및 조언 내용]</p>
        </div>
        """
        news_analysis = llm.predict(prompt)

        # 새로운 HTML 템플릿으로 업데이트 (추가 정보 포함)
        summary_html = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #1f77b4; margin-bottom: 30px;">📊 {company_name} ({ticker_krx}) 투자 분석</h2>

            <h3 style="color: #2c3e50; margin-top: 25px; margin-bottom: 15px;">🏢 기업 정보 요약</h3>

            <table style="width: 100%; border-collapse: collapse; margin-bottom: 50px;">
                <tr style="background-color: #f8f9fa;">
                    <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">항목</th>
                    <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">정보</th>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #ddd;"><strong>현재 주가</strong></td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{stock_info['current_price']} {stock_info['price_change_str']}</td>
                </tr>
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 10px; border: 1px solid #ddd;"><strong>52주 최고/최저</strong></td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{stock_info['year_high']} / {stock_info['year_low']}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #ddd;"><strong>시가총액</strong></td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{stock_info['market_cap_str']}</td>
                </tr>
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 10px; border: 1px solid #ddd;"><strong>PER (주가수익비율)</strong></td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{add_percent_if_needed(stock_info['per'])}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #ddd;"><strong>PBR (주가순자산비율)</strong></td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{add_percent_if_needed(stock_info['pbr'])}</td>
                </tr>
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 10px; border: 1px solid #ddd;"><strong>배당수익률</strong></td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{stock_info['dividend_yield']}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #ddd;"><strong>BPS (주당순자산)</strong></td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{add_won_if_needed(stock_info['bps'])}</td>
                </tr>
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 10px; border: 1px solid #ddd;"><strong>부채비율</strong></td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{add_percent_if_needed(stock_info['debt_ratio'])}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #ddd;"><strong>당기순이익</strong></td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{format_currency_value(stock_info['net_income'])}</td>
                </tr>
            </table>

            <h3 style="color: #2c3e50; margin-top: 25px; margin-bottom: 15px;">📰 최신 뉴스 및 분석</h3>

            <div style="line-height: 1.6;">
                {news_analysis.replace('\n', '').replace('<h4>', '<h4 style="font-size: 21px; margin-bottom: 0;">').replace('<h5', '<h5 style="font-size: 14px; margin-bottom: 0;"').replace('<p>', '<p style="font-size: 14px; margin-top: 5px;">').replace('<li>', '<li style="font-size: 14px;">').replace('</ol>', '</ol><br><br>').replace('</ul>', '</ul><br><br>').replace('</p>', '</p><br><br>')}
            </div>
        </div>
        """

        return summary_html
    except Exception as e:
        return f"<div style='color: red;'><h2>⚠️ {company_name} 정보 분석 중 오류가 발생했습니다:</h2> <p>{str(e)}</p></div>"