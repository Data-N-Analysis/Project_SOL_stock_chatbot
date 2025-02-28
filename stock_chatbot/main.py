import streamlit as st
from news_crawler import crawl_news
from rag_process import get_text_chunks, get_vectorstore, create_chat_chain
from stock_data import get_ticker, get_intraday_data_yahoo, get_daily_stock_data_fdr
from visualization import plot_stock_plotly


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
        st.session_state.chat_history = None
    if "processComplete" not in st.session_state:
        st.session_state.processComplete = False
    if "news_data" not in st.session_state:
        st.session_state.news_data = None
    if "company_name" not in st.session_state:
        st.session_state.company_name = None
    if "selected_period" not in st.session_state:
        st.session_state.selected_period = "1day"

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

        news_data = crawl_news(company_name, days)
        if not news_data:
            st.warning("해당 기업의 최근 뉴스를 찾을 수 없습니다.")
            st.stop()

        # 분석 결과를 session_state에 저장
        st.session_state.news_data = news_data
        st.session_state.company_name = company_name

        text_chunks = get_text_chunks(news_data)
        vectorstore = get_vectorstore(text_chunks)

        st.session_state.conversation = create_chat_chain(vectorstore, openai_api_key)
        st.session_state.processComplete = True

    # 분석 결과가 있으면 상단에 출력
    if st.session_state.processComplete and st.session_state.company_name:
        st.subheader(f"📈 {st.session_state.company_name} 최근 주가 추이")

        # 선택된 기간을 강제 업데이트하여 즉시 반영
        st.session_state.radio_selection = st.session_state.selected_period
        selected_period = st.radio(
            "기간 선택",
            options=["1day", "week", "1month", "1year"],
            index=["1day", "week", "1month", "1year"].index(st.session_state.selected_period),
            key="radio_selection",
            on_change=update_period
        )

        if selected_period != st.session_state.selected_period:
            st.session_state.selected_period = selected_period

        st.write(f"🔍 선택된 기간: {st.session_state.selected_period}")

        with st.spinner(f"📊 {st.session_state.company_name} ({st.session_state.selected_period}) 데이터 불러오는 중..."):
            # 주식 데이터 가져오기
            if selected_period in ["1day", "week"]:
                ticker = get_ticker(st.session_state.company_name, source="yahoo")

                if not ticker:
                    st.error("해당 기업의 야후 파이낸스 티커 코드를 찾을 수 없습니다.")
                    return

                interval = "1m" if st.session_state.selected_period == "1day" else "5m"
                df = get_intraday_data_yahoo(ticker,
                                             period="5d" if st.session_state.selected_period == "week" else "1d",
                                             interval=interval)
            else:
                ticker = get_ticker(st.session_state.company_name, source="fdr")
                if not ticker:
                    st.error("해당 기업의 FinanceDataReader 티커 코드를 찾을 수 없습니다.")
                    return

                df = get_daily_stock_data_fdr(ticker, st.session_state.selected_period)

            # 주식 차트 시각화
            if df.empty:
                st.warning(
                    f"📉 {st.session_state.company_name} - 해당 기간({st.session_state.selected_period})의 거래 데이터가 없습니다.")
            else:
                plot_stock_plotly(df, st.session_state.company_name, st.session_state.selected_period)

        st.markdown("최근 기업 뉴스 목록을 보려면 누르시오")

    # 뉴스 목록 표시
    if st.session_state.processComplete:
        with st.expander("뉴스 보기"):
            news_data = st.session_state.news_data

            # 처음 10개 뉴스만 표시
            for i, news in enumerate(news_data[:10]):
                st.markdown(f"- **{news['title']}** ([링크]({news['link']}))")

            # '더보기' 버튼 클릭 시 나머지 뉴스 표시
            if len(news_data) > 10:
                if st.button('더보기', key="show_more"):
                    for news in news_data[10:]:
                        st.markdown(f"- **{news['title']}** ([링크]({news['link']}))")

    # 채팅 부분: 사용자가 질문을 입력하면 대화가 이어짐
    if query := st.chat_input("질문을 입력해주세요."):
        with st.chat_message("user"):
            st.markdown(query)

        with st.chat_message("assistant"):
            with st.spinner("분석 중..."):
                result = st.session_state.conversation({"question": query})
                response = result['answer']

                st.markdown(response)
                with st.expander("참고 뉴스 확인"):
                    for doc in result['source_documents']:
                        st.markdown(f"- [{doc.metadata['source']}]({doc.metadata['source']})")


if __name__ == '__main__':
    main()