import streamlit as st
import streamlit.components.v1 as components
from news_crawler import crawl_news
from rag_process import get_text_chunks, get_vectorstore, create_chat_chain
from stock_data import  get_naver_fchart_minute_data, get_daily_stock_data_fdr
from Collecting_Stock_Information import get_ticker, generate_company_summary, enhance_llm_response
from visualization import plot_stock_plotly
def update_period():
    """세션 상태 업데이트 함수 (기간 변경 시 즉시 반영)"""
    st.session_state.selected_period = st.session_state.radio_selection

def main():
    st.set_page_config(page_title="Stock Analysis Chatbot", page_icon=":chart_with_upwards_trend:")
    st.title("📈 기업 정보 분석 QA Chat")

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

    if not process:
        st.markdown(
            "<p style='margin: 0;'>원하는 기업명을 입력하면 주가, 재무 정보, 최신 뉴스까지 한눈에 분석해드립니다!</p>"
            "<p style='margin: 0;'>⏳ 기간(일수)도 함께 입력하면 더 정확한 시장 동향을 알려드릴게요! 🚀🔥</p>",
            unsafe_allow_html=True
        )


    # 분석 시작 버튼 클릭 시
    if process:
        if not openai_api_key or not company_name:
            st.info("OpenAI API 키와 기업명을 입력해주세요.")
            st.stop()

        # 새 분석 시작 시 이전 대화 내역 초기화
        st.session_state.chat_history = []

        with st.spinner(f"🔍 {company_name}에 대한 정보 수집 중..."):
            news_data = crawl_news(company_name, days)
            if not news_data:
                st.warning("해당 기업의 최근 뉴스를 찾을 수 없습니다.")
                st.stop()

        # 분석 결과를 session_state에 저장
        st.session_state.news_data = news_data
        st.session_state.company_name = company_name

        text_chunks = get_text_chunks(news_data)
        vectorstore = get_vectorstore(text_chunks)

        # 기업 정보 요약 생성
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

             # 주식 차트 시각화
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

if __name__ == '__main__':
    main()
