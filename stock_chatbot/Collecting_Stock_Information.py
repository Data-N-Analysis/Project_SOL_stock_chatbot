import requests
from bs4 import BeautifulSoup
import FinanceDataReader as fdr
from datetime import datetime, timedelta

# 향상된 주식 정보 수집 함수 (fdr과 네이버 금융 크롤링만 사용)
def get_enhanced_stock_info(ticker_krx):
    """
    여러 소스(FinanceDataReader, 네이버 금융)에서 주식 정보를 수집하여 통합하는 함수

    Args:
        ticker_krx (str): 한국 주식 코드 (예: '005930')

    Returns:
        dict: 통합된 주식 정보 딕셔너리
    """
    stock_info = {}

    try:
        # 1. FinanceDataReader 사용 (한국 주식 정보)
        fdr_info = get_fdr_stock_info(ticker_krx)

        # 2. 네이버 금융 웹 크롤링 사용
        naver_info = get_stock_info_naver(ticker_krx)

        # 통합하여 저장 (두 소스의 결과 병합, 우선순위: 네이버 > FinanceDataReader)

        # 현재 주가 설정
        if naver_info and naver_info.get('현재가') and naver_info.get('현재가') != 'N/A':
            current_price = naver_info.get('현재가')
        else:
            current_price_val = fdr_info.get('current_price')
            if current_price_val and current_price_val != '정보 없음':
                current_price = f"{int(current_price_val):,}원"
            else:
                current_price = '정보 없음'

        # 가격 변동 계산
        previous_close = fdr_info.get('previous_close')

        if current_price != '정보 없음' and previous_close and previous_close != '정보 없음':
            try:
                # 문자열에서 숫자 추출
                if isinstance(current_price, str):
                    current_price_val = int(current_price.replace(',', '').replace('원', ''))
                else:
                    current_price_val = current_price

                price_change = ((current_price_val - previous_close) / previous_close) * 100
                color = "green" if price_change >= 0 else "red"
                price_change_str = f"<span style='color:{color};'>({price_change:+.2f}%)</span>"
            except:
                price_change_str = ""
        else:
            price_change_str = ""

        # 52주 최고/최저 설정
        if naver_info and naver_info.get('52주 최고') and naver_info.get('52주 최고') != 'N/A':
            year_high = naver_info.get('52주 최고')
        else:
            year_high_val = fdr_info.get('year_high')
            if year_high_val and year_high_val != '정보 없음':
                year_high = f"{int(year_high_val):,}원"
            else:
                year_high = '정보 없음'

        if naver_info and naver_info.get('52주 최저') and naver_info.get('52주 최저') != 'N/A':
            year_low = naver_info.get('52주 최저')
        else:
            year_low_val = fdr_info.get('year_low')
            if year_low_val and year_low_val != '정보 없음':
                year_low = f"{int(year_low_val):,}원"
            else:
                year_low = '정보 없음'

        # 시가총액 계산
        if naver_info and naver_info.get('시가총액') and naver_info.get('시가총액') != 'N/A':
            market_cap_str = naver_info.get('시가총액')
        else:
            market_cap = fdr_info.get('market_cap')
            if market_cap and market_cap != '정보 없음':
                market_cap = market_cap / 1000000000000  # 조 단위로 변환
                market_cap_str = f"{market_cap:.2f}조 원"
            else:
                market_cap_str = "정보 없음"

        # PER 및 PBR 설정
        if naver_info and naver_info.get('PER') and naver_info.get('PER') != 'N/A':
            per = naver_info.get('PER')
        else:
            per_val = fdr_info.get('per')
            if per_val and per_val != '정보 없음':
                per = f"{per_val:.2f}"
            else:
                per = '정보 없음'

        if naver_info and naver_info.get('PBR') and naver_info.get('PBR') != 'N/A':
            pbr = naver_info.get('PBR')
        else:
            pbr_val = fdr_info.get('pbr')
            if pbr_val and pbr_val != '정보 없음':
                pbr = f"{pbr_val:.2f}"
            else:
                pbr = '정보 없음'

        # 배당수익률 추가
        if naver_info and naver_info.get('배당수익률') and naver_info.get('배당수익률') != 'N/A':
            dividend_yield = naver_info.get('배당수익률')
        else:
            dividend_yield_val = fdr_info.get('dividend_yield')
            if dividend_yield_val and dividend_yield_val != '정보 없음':
                if isinstance(dividend_yield_val, (int, float)) and dividend_yield_val < 1:  # 소수점으로 표시된 경우
                    dividend_yield = f"{dividend_yield_val * 100:.2f}%"
                else:
                    dividend_yield = f"{dividend_yield_val:.2f}%"
            else:
                dividend_yield = '정보 없음'

        # 네이버에서만 가져올 수 있는 추가 정보들
        if naver_info:
            bps = naver_info.get('BPS', '정보 없음')
            debt_ratio = naver_info.get('부채비율', '정보 없음')
            net_income = naver_info.get('당기순이익', '정보 없음')
        else:
            bps = '정보 없음'
            debt_ratio = '정보 없음'
            net_income = '정보 없음'

    except Exception as e:
        # 오류 발생 시 기본값으로 설정
        current_price = '정보 없음'
        price_change_str = ""
        year_high = '정보 없음'
        year_low = '정보 없음'
        market_cap_str = '정보 없음'
        per = '정보 없음'
        pbr = '정보 없음'
        dividend_yield = '정보 없음'
        bps = '정보 없음'
        debt_ratio = '정보 없음'
        net_income = '정보 없음'

    # 결과 딕셔너리에 저장
    stock_info['current_price'] = current_price
    stock_info['price_change_str'] = price_change_str
    stock_info['year_high'] = year_high
    stock_info['year_low'] = year_low
    stock_info['market_cap_str'] = market_cap_str
    stock_info['per'] = per
    stock_info['pbr'] = pbr
    stock_info['dividend_yield'] = dividend_yield
    stock_info['bps'] = bps
    stock_info['debt_ratio'] = debt_ratio
    stock_info['net_income'] = net_income

    return stock_info


def get_stock_info_naver(ticker_krx):
    """
    네이버 금융에서 특정 종목의 주요 재무 지표를 크롤링하여 반환

    Args:
        ticker_krx (str): 한국 주식 코드 (예: '005930')

    Returns:
        dict: 주식 정보 딕셔너리 또는 None (실패 시)
    """
    # 티커 형식 처리 (문자열 확인)
    if isinstance(ticker_krx, str) and not ticker_krx.isdigit():
        print(f"잘못된 티커 형식: {ticker_krx}")
        return None

    ticker_krx = str(ticker_krx).zfill(6)  # 6자리 숫자로 포맷팅
    url = f"https://finance.naver.com/item/main.naver?code={ticker_krx}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"요청 실패: {response.status_code}")
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        # 결과 저장 딕셔너리 초기화
        result = {
            "현재가": "N/A",
            "PER": "N/A",
            "PBR": "N/A",
            "52주 최고": "N/A",
            "52주 최저": "N/A",
            "시가총액": "N/A",
            "BPS": "N/A",
            "배당수익률": "N/A",
            "부채비율": "N/A",
            "당기순이익": "N/A"
        }

        # 1. 현재가 추출 - 개선된 방식
        try:
            current_price_area = soup.select_one(".new_totalinfo .no_today .no_up .no_down span.blind")
            if current_price_area:
                result["현재가"] = f"{int(current_price_area.text.replace(',', '')):,}원"
            else:
                # 대체 방법 시도
                today_element = soup.select_one(".today")
                if today_element:
                    blind_price = today_element.select_one("span.blind")
                    if blind_price:
                        result["현재가"] = f"{int(blind_price.text.replace(',', '')):,}원"
        except Exception as e:
            print(f"현재가 추출 오류: {e}")

        # 2. 시가총액 추출 - 개선된 방식
        try:
            market_cap_elem = soup.select_one(".first .line_dot")
            if market_cap_elem:
                cap_text = market_cap_elem.text.strip()
                # "시가총액" 텍스트가 포함된 요소 찾기
                if "시가총액" in cap_text:
                    # 시가총액 값 추출
                    cap_value = cap_text.split('\n')[-1].strip()
                    result["시가총액"] = cap_value
        except Exception as e:
            print(f"시가총액 추출 오류: {e}")

        # 3. 52주 최고/최저
        try:
            # 52주 최고/최저 테이블 찾기 (더 정확한 선택자 사용)
            highest_lowest = soup.select(".no_info tbody tr td")

            for td in highest_lowest:
                if "52주 최고" in td.text:
                    high_value = td.select_one("span.blind")
                    if high_value:
                        result["52주 최고"] = f"{int(high_value.text.replace(',', '')):,}원"

                if "52주 최저" in td.text:
                    low_value = td.select_one("span.blind")
                    if low_value:
                        result["52주 최저"] = f"{int(low_value.text.replace(',', '')):,}원"
        except Exception as e:
            print(f"52주 최고/최저 추출 오류: {e}")

        # 4. 투자지표 테이블에서 PER, PBR, BPS 등 추출 - 개선된 방식
        try:
            # 테이블에서 th와 em 태그를 함께 검사
            for table in soup.select("table.tb_type1"):
                rows = table.select("tr")
                for row in rows:
                    cells = row.select("th, td")
                    for i, cell in enumerate(cells):
                        cell_text = cell.text.strip()

                        # PER 추출
                        if "PER" in cell_text and i + 1 < len(cells):
                            result["PER"] = cells[i + 1].text.strip()

                        # PBR 추출
                        if "PBR" in cell_text and i + 1 < len(cells):
                            result["PBR"] = cells[i + 1].text.strip()

                        # BPS 추출
                        if "BPS" in cell_text and i + 1 < len(cells):
                            result["BPS"] = cells[i + 1].text.strip()

                        # 배당수익률 추출
                        if "배당수익률" in cell_text and i + 1 < len(cells):
                            result["배당수익률"] = cells[i + 1].text.strip()

            # em 태그를 통한 추가 검색
            for table in soup.select("table.tb_type1"):
                for em in table.select("em"):
                    em_text = em.text.strip()

                    # 각 지표별 검색
                    if "부채비율" in em_text:
                        td = em.find_parent("th").find_next_sibling("td")
                        if td:
                            result["부채비율"] = td.text.strip()

                    if "당기순이익" in em_text:
                        td = em.find_parent("th").find_next_sibling("td")
                        if td:
                            result["당기순이익"] = td.text.strip()
        except Exception as e:
            print(f"투자지표 추출 오류: {e}")

        # 5. 재무제표 섹션에서 추가 정보 추출
        try:
            # 재무제표 섹션 찾기
            finance_summary = soup.select("#content .section.cop_analysis")
            if finance_summary:
                # 테이블 내 모든 행 검사
                rows = finance_summary[0].select("table.tb_type1 tbody tr")
                for row in rows:
                    # 각 행의 셀 텍스트 확인
                    th = row.select_one("th")
                    if th:
                        th_text = th.text.strip()

                        # 부채비율 찾기
                        if "부채비율" in th_text and result["부채비율"] == "N/A":
                            td = row.select_one("td")
                            if td:
                                result["부채비율"] = td.text.strip()

                        # 당기순이익 찾기
                        if "당기순이익" in th_text and result["당기순이익"] == "N/A":
                            td = row.select_one("td")
                            if td:
                                result["당기순이익"] = td.text.strip()
        except Exception as e:
            print(f"재무제표 추출 오류: {e}")

        # 디버깅 출력
        print(f"크롤링 결과: 현재가={result['현재가']}, PER={result['PER']}, PBR={result['PBR']}")
        print(f"부채비율={result['부채비율']}, 당기순이익={result['당기순이익']}")

        return result

    except Exception as e:
        print(f"네이버 금융 크롤링 중 오류 발생: {e}")
        return None


def get_fdr_stock_info(ticker_krx):
    """
    FinanceDataReader를 사용하여 주식 정보를 가져오는 함수

    Args:
        ticker_krx (str): 한국 주식 코드 (예: '005930')

    Returns:
        dict: 주식 정보 딕셔너리
    """


    try:
        # 기본 정보 딕셔너리 초기화
        stock_info = {
            'current_price': '정보 없음',
            'previous_close': '정보 없음',
            'year_high': '정보 없음',
            'year_low': '정보 없음',
            'market_cap': '정보 없음',
            'per': '정보 없음',
            'pbr': '정보 없음',
            'dividend_yield': '정보 없음'
        }

        # 오늘 날짜와 1년 전 날짜 계산
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)

        # 일별 주가 데이터 가져오기
        df = fdr.DataReader(ticker_krx, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))

        if not df.empty:
            # 현재가 (가장 최근 종가)
            stock_info['current_price'] = df['Close'].iloc[-1]

            # 전일 종가
            if len(df) > 1:
                stock_info['previous_close'] = df['Close'].iloc[-2]

            # 52주 최고가/최저가
            stock_info['year_high'] = df['High'].max()
            stock_info['year_low'] = df['Low'].min()

            # 시가총액은 FDR에서 직접 제공하지 않음 (별도 API 필요)

            # 기업정보 가져오기 (KRX에서 제공하는 경우)
            try:
                krx_info = fdr.StockListing('KRX')
                company_info = krx_info[krx_info['Symbol'] == ticker_krx]

                if not company_info.empty:
                    # 시가총액 (MarketCap 열이 있는 경우)
                    if 'MarketCap' in company_info.columns:
                        stock_info['market_cap'] = company_info['MarketCap'].iloc[0]

                    # PER (PER 열이 있는 경우)
                    if 'PER' in company_info.columns:
                        stock_info['per'] = company_info['PER'].iloc[0]

                    # PBR (PBR 열이 있는 경우)
                    if 'PBR' in company_info.columns:
                        stock_info['pbr'] = company_info['PBR'].iloc[0]

                    # 배당수익률 (DividendYield 열이 있는 경우)
                    if 'DividendYield' in company_info.columns:
                        stock_info['dividend_yield'] = company_info['DividendYield'].iloc[0]
            except:
                pass  # KRX 정보 가져오기 실패 시 기본값 유지

        return stock_info

    except Exception as e:
        print(f"FDR 데이터 가져오기 오류: {e}")
        return stock_info  # 기본값 반환