import re
from langchain_community.chat_models import ChatOpenAI
import FinanceDataReader as fdr

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

# LLM 응답 강화 함수 (이모지, 강조 등 추가)
def enhance_llm_response(text):
    # 섹션 제목에 이모지 추가
    text = re.sub(r'(## 최신 뉴스|## 뉴스 요약|## 최근 동향)', r'## 📰 \1', text)
    text = re.sub(r'(## 투자 전망|## 투자 분석|## 전망)', r'## 💹 \1', text)
    text = re.sub(r'(## 위험 요소|## 부정적 요인|## 리스크)', r'## ⚠️ \1', text)
    text = re.sub(r'(## 긍정적 요인|## 성장 기회|## 기회)', r'## ✅ \1', text)
    text = re.sub(r'(## 재무 분석|## 재무 상태|## 재무)', r'## 💰 \1', text)

    # 번호 매기기 강화 (1️⃣, 2️⃣, 3️⃣ 등)
    text = re.sub(r'(?m)^1\. ', r'1️⃣ ', text)
    text = re.sub(r'(?m)^2\. ', r'2️⃣ ', text)
    text = re.sub(r'(?m)^3\. ', r'3️⃣ ', text)
    text = re.sub(r'(?m)^4\. ', r'4️⃣ ', text)
    text = re.sub(r'(?m)^5\. ', r'5️⃣ ', text)

    # 중요 키워드 강조 - HTML 태그 사용
    text = re.sub(r'(매출액|영업이익|순이익|실적|성장률|시장 점유율)', r'<b>\1</b>', text)
    text = re.sub(r'(급등|급락|상승|하락|성장|감소|인수|합병|계약|협약)', r'<b>\1</b>', text)

    # 투자 관련 키워드에 색상 강조
    text = re.sub(r'(매수|매도|추천|중립|보유)',
                  lambda
                      m: f'<span style="color:{"green" if m.group(1) in ["매수", "추천"] else "red" if m.group(1) == "매도" else "orange"}; font-weight:bold;">{m.group(1)}</span>',
                  text)

    # 제목과 내용 사이 줄간격 조정 (제목과 내용 사이에 간격 추가)
    text = re.sub(r'(## .+?)(\n)', r'\1\n\n', text)
    text = re.sub(r'(### .+?)(\n)', r'\1\n\n', text)

    return text