import tiktoken
import json
import streamlit as st
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS
from langchain.chat_models import ChatOpenAI
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate


def tiktoken_len(text):
    """
    텍스트의 토큰 길이를 계산하는 함수

    Args:
        text (str): 토큰화할 텍스트

    Returns:
        int: 토큰 길이
    """
    tokenizer = tiktoken.get_encoding("cl100k_base")
    tokens = tokenizer.encode(text)
    return len(tokens)


def get_text_chunks(news_data, financial_data):
    """
    뉴스 데이터와 재무 데이터를 통합하여 청크로 나누는 함수

    Args:
        news_data (list): 뉴스 데이터 목록
        financial_data (list): 재무 데이터 목록

    Returns:
        list: 처리된 통합 텍스트 청크
    """
    # 디버깅 섹션 시작
    with st.expander("재무 데이터 디버깅 정보", expanded=False):
        st.write("## 받은 재무 데이터")
        st.write(f"재무 데이터 항목 수: {len(financial_data)}")

        for idx, item in enumerate(financial_data):
            st.write(f"### 재무 데이터 항목 {idx + 1}")
            try:
                st.json(item)  # JSON 형식으로 예쁘게 출력
            except Exception as e:
                st.error(f"데이터 출력 오류: {e}")
                st.write(str(item))

    def format_financial_text(item):
        """
        재무 데이터를 상세 텍스트로 변환하는 내부 함수
        """
        text = "기업 재무 데이터 상세 분석:\n"

        # 각 재무 지표를 안전하게 추가
        financial_keys = [
            ('current_price', '현재 주가'),
            ('per', 'PER'),
            ('pbr', 'PBR'),
            ('year_high', '52주 최고가'),
            ('year_low', '52주 최저가'),
            ('market_cap_str', '시가총액'),
            ('dividend_yield', '배당수익률'),
            ('debt_ratio', '부채비율'),
            ('net_income', '당기순이익')
        ]

        for key, label in financial_keys:
            value = item.get(key, 'N/A')
            if value is not None and value != 'N/A':
                text += f"{label}: {value}\n"

        return text

    # 뉴스 데이터 처리
    news_texts = [f"{item['title']}\n{item['content']}" for item in news_data]
    news_metadatas = [{"source": "news", "link": item["link"]} for item in news_data]

    # 재무 데이터 처리 (강화된 안전성)
    financial_texts = [
        format_financial_text(item)
        for item in financial_data
        if item is not None
    ]
    financial_metadatas = [{"source": "financial"} for _ in financial_texts]

    # 디버깅: 텍스트 변환 결과
    with st.expander("변환된 텍스트 디버깅", expanded=False):
        st.write(f"생성된 뉴스 텍스트 수: {len(news_texts)}")
        st.write(f"생성된 재무 텍스트 수: {len(financial_texts)}")

        if financial_texts:
            st.write("### 변환된 재무 텍스트 샘플")
            st.text(financial_texts[0])
        else:
            st.warning("변환된 재무 텍스트가 없습니다!")

    # 전체 텍스트와 메타데이터 통합
    all_texts = news_texts + financial_texts
    all_metadatas = news_metadatas + financial_metadatas

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=900,
        chunk_overlap=100,
        length_function=tiktoken_len
    )

    # 청크 생성
    chunks = text_splitter.create_documents(all_texts, metadatas=all_metadatas)

    # 디버깅: 최종 청크 정보
    with st.expander("생성된 청크 디버깅", expanded=False):
        st.write(f"총 생성된 청크 수: {len(chunks)}")

        # 청크 분류 (뉴스/재무)
        news_chunks = [chunk for chunk in chunks if chunk.metadata.get('source') == 'news']
        financial_chunks = [chunk for chunk in chunks if chunk.metadata.get('source') == 'financial']

        st.write(f"뉴스 청크 수: {len(news_chunks)}")
        st.write(f"재무 청크 수: {len(financial_chunks)}")

        if financial_chunks:
            st.write("### 재무 청크 샘플")
            st.text(financial_chunks[0].page_content)

    return chunks


def get_vectorstore(text_chunks):
    """
    텍스트 청크에서 벡터 저장소를 생성하는 함수

    Args:
        text_chunks (list): 텍스트 청크 목록

    Returns:
        FAISS: 생성된 벡터 저장소
    """
    # 디버깅: 벡터 저장소 생성 정보
    with st.expander("벡터 저장소 디버깅", expanded=False):
        st.write(f"벡터화할 텍스트 청크 수: {len(text_chunks)}")

        # 청크의 메타데이터 소스 확인
        sources = [chunk.metadata.get('source', 'unknown') for chunk in text_chunks]
        source_counts = {}
        for source in sources:
            source_counts[source] = source_counts.get(source, 0) + 1

        st.write("### 청크 소스 분포")
        for source, count in source_counts.items():
            st.write(f"{source}: {count}개")

    embeddings = HuggingFaceEmbeddings(
        model_name="jhgan/ko-sroberta-multitask",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )

    vector_store = FAISS.from_documents(text_chunks, embeddings)

    # 디버깅: 벡터 저장소 생성 완료
    with st.expander("벡터 저장소 생성 완료", expanded=False):
        st.write("벡터 저장소가 성공적으로 생성되었습니다.")
        st.write(f"인덱스 크기: {vector_store.index.ntotal}")

    return vector_store


def create_financial_aware_prompt_template():
    """
    재무 및 뉴스 데이터를 종합적으로 분석하는 프롬프트 템플릿 생성

    Returns:
        PromptTemplate: 맞춤형 프롬프트 템플릿
    """
    template = """
    당신은 기업 분석 전문 AI 어시스턴트입니다. 다음 문맥을 바탕으로 질문에 상세하고 통찰력 있는 답변을 제공하세요.

    문맥:
    {context}

    대화 이력:
    {chat_history}

    사용자 질문: {question}

    답변 지침:
    1. 최근 뉴스와 재무 데이터를 종합적으로 분석하세요.
    2. 기업의 최근 실적과 향후 성장 전망을 명확히 설명하세요.
    3. 투자 관점에서 중요한 인사이트를 제공하세요.
    4. 데이터 기반의 객관적이고 상세한 답변을 제공하세요.
    5. 불확실한 정보는 솔직히 인정하고, 가능한 한 근거를 제시하세요.

    답변:"""

    return PromptTemplate(
        template=template,
        input_variables=["context", "question", "chat_history"]
    )


def create_chat_chain(vectorstore, openai_api_key):
    """
    재무 인식 대화 체인 생성

    Args:
        vectorstore (FAISS): 벡터 저장소
        openai_api_key (str): OpenAI API 키

    Returns:
        ConversationalRetrievalChain: 생성된 대화 체인
    """
    # 디버깅: 대화 체인 생성 정보
    with st.expander("대화 체인 디버깅", expanded=False):
        st.write("대화 체인 생성 시작")
        st.write(f"벡터 저장소 크기: {vectorstore.index.ntotal}")

    llm = ChatOpenAI(openai_api_key=openai_api_key, model_name='gpt-4', temperature=0.3)

    # 맞춤형 프롬프트 템플릿 적용
    custom_prompt = create_financial_aware_prompt_template()

    # 디버깅: 프롬프트 템플릿 확인
    with st.expander("프롬프트 템플릿 디버깅", expanded=False):
        st.write("### 사용 중인 프롬프트 템플릿")
        st.text(custom_prompt.template)

    conversation_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        chain_type="stuff",
        retriever=vectorstore.as_retriever(),
        memory=ConversationBufferMemory(memory_key='chat_history', return_messages=True, output_key='answer'),
        get_chat_history=lambda h: h,
        return_source_documents=True,
        combine_docs_chain_kwargs={'prompt': custom_prompt}
    )

    # 디버깅: 대화 체인 생성 완료
    with st.expander("대화 체인 생성 완료", expanded=False):
        st.write("대화 체인이 성공적으로 생성되었습니다.")

    return conversation_chain