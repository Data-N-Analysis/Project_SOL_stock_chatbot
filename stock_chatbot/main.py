import streamlit as st
from news_crawler import crawl_news
from rag_process import get_text_chunks, get_vectorstore, create_chat_chain
from stock_data import get_ticker, get_intraday_data_yahoo, get_daily_stock_data_fdr
from visualization import plot_stock_plotly
import re
from langchain_community.chat_models import ChatOpenAI
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import streamlit.components.v1 as components

def update_period():
    """세션 상태 업데이트 함수 (기간 변경 시 즉시 반영)"""
    st.session_state.selected_period = st.session_state.radio_selection

def main():
    st.set_page_config(page_title="Stock Analysis Chatbot", page_icon=":chart_with_upwards_trend:")
    st.title("기업 정보 분석 QA Chat")

    # 세션 상태 초기화
    if "conversation" not in st.session_state:
        st.session_state.conversation = None
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "processComplete" not in st.session_state:
        st.session_state.processComplete = False
    if "news_data" not in st.session_state:
        st.session_state.news_data = None
    if "company_name" not in st.session_state:
        st.session_state.company_name = None
    if "selected_period" not in st.session_state:
        st.session_state.selected_period = "1day"
    if "company_summary" not in st.session_state:
        st.session_state.company_summary = None

    # 사이드바 설정
    with st.sidebar:
        openai_api_key = st.text_input("OpenAI API Key", key="chatbot_api_key", type="password")
        company_name = st.text_input("분석할 기업명 (코스피 상장)")
        days = st.number_input("최근 며칠 동안의 기사를 검색할까요?", min_value=1, max_value=30, value=7)
        process = st.button("분석 시작")

    # 분석 시작 버튼 클릭 시
    if process:
        if not openai_api_key or not company_name:
            st.info("OpenAI API 키와 기업명을 입력해주세요.")
            st.stop()
        st.session_state.chat_history = []

        with st.spinner(f"🔍 {company_name}에 대한 정보 수집 중..."):
            news_data = crawl_news(company_name, days)
            if not news_data:
                st.warning("해당 기업의 최근 뉴스를 찾을 수 없습니다.")
                st.stop()

        st.session_state.news_data = news_data
        st.session_state.company_name = company_name

        text_chunks = get_text_chunks(news_data)
        vectorstore = get_vectorstore(text_chunks)

        st.session_state.conversation = create_chat_chain(vectorstore, openai_api_key)
        st.session_state.company_summary = generate_company_summary(company_name, news_data, openai_api_key)
        st.session_state.processComplete = True

    # 분석 결과 출력
    if st.session_state.processComplete and st.session_state.company_name:
        st.subheader(f"📈 {st.session_state.company_name} 최근 주가 추이")

        # ✅ 애니메이션 포함한 CSS 스타일 추가 (기간 선택 글씨 제거)
        st.markdown("""
        <style>
            /* 라디오 버튼 컨테이너 스타일 */
            div[role="radiogroup"] {
                display: flex;
                justify-content: center;
                gap: 20px;
                margin-top: -10px; /* 위쪽 여백 줄이기 */
            }

            /* 버튼 스타일 */
            div[role="radiogroup"] label {
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 10px 15px;
                border: 2px solid #ddd;
                border-radius: 20px;
                font-size: 16px;
                font-weight: bold;
                cursor: pointer;
                transition: all 0.3s ease-in-out;
            }

            /* 선택된 버튼 스타일 */
            div[role="radiogroup"] input:checked + label {
                background-color: #ff4757;
                color: white;
                border-color: #e84118;
                transform: scale(1.1);
            }

            /* 마우스 올렸을 때 (호버 효과) */
            div[role="radiogroup"] label:hover {
                background-color: #dcdde1;
                border-color: #7f8c8d;
            }
        </style>
        """, unsafe_allow_html=True)

        # ✅ "기간 선택" 문구 제거한 버튼 UI
        selected_period = st.radio(
            "",  # ✅ 라벨 제거
            options=["1day", "week", "1month", "1year"],
            index=["1day", "week", "1month", "1year"].index(st.session_state.selected_period),
            key="radio_selection",
            horizontal=True,
            on_change=update_period
        )

        st.write(f"🔍 선택된 기간: {st.session_state.selected_period}")

        with st.spinner(f"📊 {st.session_state.company_name} ({st.session_state.selected_period}) 데이터 불러오는 중..."):
            ticker = get_ticker(st.session_state.company_name)
            if not ticker:
                st.error("해당 기업의 티커 코드를 찾을 수 없습니다.")
                return

            if selected_period in ["1day", "week"]:
                df = get_naver_fchart_minute_data(ticker, "1" if selected_period == "1day" else "5", 1 if selected_period == "1day" else 7)
            else:
                df = get_daily_stock_data_fdr(ticker, selected_period)

            if df.empty:
                st.warning(f"📉 {st.session_state.company_name} - 해당 기간({st.session_state.selected_period})의 거래 데이터가 없습니다.")
            else:
                plot_stock_plotly(df, st.session_state.company_name, st.session_state.selected_period)
                
        # 기업 정보 요약은 차트 이후에 표시
        if st.session_state.company_summary:
            # st.markdown 대신 components.html 사용
            components.html(st.session_state.company_summary, height=600, scrolling=True)

        # 대화 인터페이스 섹션
        st.markdown("### 💬 질문과 답변")

        # 안내 메시지 표시 - 대화 여부에 관계없이 항상 표시되도록 수정
        st.markdown("""
        #### 💬 어떤 정보가 궁금하신가요?
        * 이 기업의 최근 실적은 어떤가요?
        * 현재 주가가 과대평가된 것 같나요?
        * 이 기업의 향후 성장 전망은 어떤가요?
        * 현재 시장 상황에서 투자 전략을 조언해주세요.
        """)

        # 대화 히스토리 표시
        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                # HTML 형식으로 변환된 마크다운 콘텐츠 표시
                st.markdown(message["content"], unsafe_allow_html=True)

                # 소스 문서 표시 (응답인 경우에만)
                if message["role"] == "assistant" and "source_documents" in message:
                    with st.expander("참고 뉴스 확인"):
                        for doc in message["source_documents"]:
                            st.markdown(f"- [{doc.metadata['source']}]({doc.metadata['source']})")

        # 채팅 입력 - 루프 밖으로 이동
        if st.session_state.processComplete:  # 분석이 완료된 경우에만 입력창 표시
            query = st.chat_input("질문을 입력해주세요.")
            if query:
                # 사용자 메시지 추가
                st.session_state.chat_history.append({"role": "user", "content": query})

                # 응답 생성
                with st.chat_message("assistant"):
                    with st.spinner("분석 중..."):
                        try:
                            result = st.session_state.conversation({"question": query})
                            response = result['answer']

                            # 응답 강조 및 이모지 추가 처리
                            response = enhance_llm_response(response)

                            # 응답 표시 (HTML 허용)
                            st.markdown(response, unsafe_allow_html=True)

                            # 소스 문서 표시
                            with st.expander("참고 뉴스 확인"):
                                for doc in result['source_documents']:
                                    st.markdown(f"- [{doc.metadata['source']}]({doc.metadata['source']})")

                            # 응답을 대화 히스토리에 추가
                            st.session_state.chat_history.append({
                                "role": "assistant",
                                "content": response,
                                "source_documents": result.get('source_documents', [])
                            })
                        except Exception as e:
                            st.error(f"오류가 발생했습니다: {str(e)}")

                # 자동으로 페이지 새로고침 없이 대화 내용 업데이트
                st.rerun()


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


def generate_company_summary(company_name, news_data, openai_api_key):
    try:
        # 기업 정보 수집
        ticker_krx = get_ticker(company_name, source="fdr")
        if not ticker_krx:
            return f"## {company_name}에 대한 정보를 찾을 수 없습니다."

        ticker_yahoo = ticker_krx + ".KS"

        # 주가 정보 수집 (향상된 방식)
        stock_info = get_enhanced_stock_info(ticker_yahoo, ticker_krx)

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
            <h4>최신 동향</h4>
            <ol>
                <li>[동향 내용 1] (출처: <a href="뉴스링크" target="_blank">출처명</a>)</li>
                <li>[동향 내용 2] (출처: <a href="뉴스링크" target="_blank">출처명</a>)</li>
                <!-- 4-7개 항목 -->
            </ol>

            <h4>투자 영향 요인</h4>
            <div>
                <h5 style="color: green;">✅ 긍정적 요인</h5>
                <ul>
                    <li>[긍정적 요인 1]</li>
                    <!-- 2-3개 항목 -->
                </ul>

                <h5 style="color: red;">⚠️ 부정적 요인</h5>
                <ul>
                    <li>[부정적 요인 1]</li>
                    <!-- 2-3개 항목 -->
                </ul>
            </div>

            <h4>💹 투자 전망 및 조언</h4>
            <p>[투자 전망 및 조언 내용]</p>
        </div>
        """
        news_analysis = llm.predict(prompt)

        # Markdown 형식으로 요약 생성
        # Instead of returning markdown, return HTML:
        summary_html = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #1f77b4; margin-bottom: 20px;">📊 {company_name} ({ticker_krx}) 투자 분석</h2>

            <h3 style="color: #2c3e50; margin-top: 25px; margin-bottom: 15px;">🏢 기업 정보 요약</h3>

            <table style="width: 100%; border-collapse: collapse; margin-bottom: 30px;">
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
                    <td style="padding: 10px; border: 1px solid #ddd;">{stock_info['per']}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #ddd;"><strong>PBR (주가순자산비율)</strong></td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{stock_info['pbr']}</td>
                </tr>
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 10px; border: 1px solid #ddd;"><strong>배당수익률</strong></td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{stock_info['dividend_yield']}</td>
                </tr>
            </table>

            <h3 style="color: #2c3e50; margin-top: 25px; margin-bottom: 15px;">📰 최신 뉴스 및 분석</h3>

            <div style="line-height: 1.6;">
                {news_analysis.replace('\n', '<br>').replace('1. ', '<br>1. ').replace('2. ', '<br>2. ').replace('3. ', '<br>3. ')}
            </div>
        </div>
        """

        return summary_html
    except Exception as e:
        return f"<div style='color: red;'><h2>⚠️ {company_name} 정보 분석 중 오류가 발생했습니다:</h2> <p>{str(e)}</p></div>"


# 향상된 주식 정보 수집 함수 (여러 소스에서 정보 통합)
def get_enhanced_stock_info(ticker_yahoo, ticker_krx):
    stock_info = {}

    # 두 방식으로 정보 수집 시도
    try:
        # 1. yfinance 사용
        yf_info = yf.Ticker(ticker_yahoo).info

        # 2. FinanceDataReader 사용 (한국 주식 정보)
        fdr_info = get_fdr_stock_info(ticker_krx)

        # 통합하여 저장 (yfinance와 FinanceDataReader 결과 병합)
        current_price = yf_info.get('currentPrice') or fdr_info.get('current_price')
        if current_price and current_price != '정보 없음':
            current_price = f"{int(current_price):,}원"
        else:
            current_price = '정보 없음'

        previous_close = yf_info.get('previousClose') or fdr_info.get('previous_close')

        # 가격 변동 계산
        if current_price != '정보 없음' and previous_close and previous_close != '정보 없음':
            try:
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
        year_high = yf_info.get('fiftyTwoWeekHigh') or fdr_info.get('year_high')
        if year_high and year_high != '정보 없음':
            year_high = f"{int(year_high):,}원"
        else:
            year_high = '정보 없음'

        year_low = yf_info.get('fiftyTwoWeekLow') or fdr_info.get('year_low')
        if year_low and year_low != '정보 없음':
            year_low = f"{int(year_low):,}원"
        else:
            year_low = '정보 없음'

        # 시가총액 계산
        market_cap = yf_info.get('marketCap') or fdr_info.get('market_cap')
        if market_cap and market_cap != '정보 없음':
            market_cap = market_cap / 1000000000000  # 조 단위로 변환
            market_cap_str = f"{market_cap:.2f}조 원"
        else:
            market_cap_str = "정보 없음"

        # PER 및 PBR 설정
        per = yf_info.get('trailingPE') or fdr_info.get('per')
        if per and per != '정보 없음':
            per = f"{per:.2f}"
        else:
            per = '정보 없음'

        pbr = yf_info.get('priceToBook') or fdr_info.get('pbr')
        if pbr and pbr != '정보 없음':
            pbr = f"{pbr:.2f}"
        else:
            pbr = '정보 없음'

        # 배당수익률 추가
        dividend_yield = yf_info.get('dividendYield') or fdr_info.get('dividend_yield')
        if dividend_yield and dividend_yield != '정보 없음':
            if dividend_yield < 1:  # 소수점으로 표시된 경우
                dividend_yield = f"{dividend_yield * 100:.2f}%"
            else:
                dividend_yield = f"{dividend_yield:.2f}%"
        else:
            dividend_yield = '정보 없음'

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

    # 결과 딕셔너리에 저장
    stock_info['current_price'] = current_price
    stock_info['price_change_str'] = price_change_str
    stock_info['year_high'] = year_high
    stock_info['year_low'] = year_low
    stock_info['market_cap_str'] = market_cap_str
    stock_info['per'] = per
    stock_info['pbr'] = pbr
    stock_info['dividend_yield'] = dividend_yield

    return stock_info


# FinanceDataReader를 통한 추가 주식 정보 수집 함수
def get_fdr_stock_info(ticker_krx):
    try:
        # 오늘 날짜 기준 데이터 가져오기
        today = datetime.now().strftime('%Y-%m-%d')
        last_year = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

        # 지난 1년간의 주가 데이터 수집
        df = fdr.DataReader(ticker_krx, last_year, today)

        if df.empty:
            return {
                'current_price': '정보 없음',
                'previous_close': '정보 없음',
                'year_high': '정보 없음',
                'year_low': '정보 없음',
                'per': '정보 없음',
                'pbr': '정보 없음',
                'dividend_yield': '정보 없음',
                'market_cap': '정보 없음'
            }

        # 52주 최고/최저가 계산
        year_high = df['High'].max()
        year_low = df['Low'].min()

        # 현재가 (마지막 종가)
        current_price = df['Close'].iloc[-1]
        previous_close = df['Close'].iloc[-2] if len(df) > 1 else current_price

        # KRX 통합정보 가져오기 시도
        try:
            krx_df = fdr.StockListing('KRX')
            stock_row = krx_df[krx_df['Code'] == ticker_krx]

            if not stock_row.empty:
                per = stock_row['PER'].iloc[0]
                pbr = stock_row['PBR'].iloc[0]
                market_cap = stock_row['Market Cap'].iloc[0]
            else:
                per = '정보 없음'
                pbr = '정보 없음'
                market_cap = '정보 없음'
        except:
            per = '정보 없음'
            pbr = '정보 없음'
            market_cap = '정보 없음'

        # 배당수익률은 일반적으로 KRX 정보에서 제공하지 않음
        dividend_yield = '정보 없음'

        return {
            'current_price': current_price,
            'previous_close': previous_close,
            'year_high': year_high,
            'year_low': year_low,
            'per': per,
            'pbr': pbr,
            'dividend_yield': dividend_yield,
            'market_cap': market_cap
        }
    except Exception as e:
        return {
            'current_price': '정보 없음',
            'previous_close': '정보 없음',
            'year_high': '정보 없음',
            'year_low': '정보 없음',
            'per': '정보 없음',
            'pbr': '정보 없음',
            'dividend_yield': '정보 없음',
            'market_cap': '정보 없음'
        }

if __name__ == '__main__':
    main()
