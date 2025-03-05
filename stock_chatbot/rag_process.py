import tiktoken
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
    # 뉴스 데이터 처리
    news_texts = [f"{item['title']}\n{item['content']}" for item in news_data]
    news_metadatas = [{"source": "news", "link": item["link"]} for item in news_data]

    # 재무 데이터 처리
    financial_texts = [
        f"재무 지표 요약:\n"
        f"현재 주가: {item.get('현재가', 'N/A')}\n"
        f"PER: {item.get('PER', 'N/A')}\n"
        f"PBR: {item.get('PBR', 'N/A')}\n"
        f"52주 최고가: {item.get('52주 최고', 'N/A')}\n"
        f"52주 최저가: {item.get('52주 최저', 'N/A')}\n"
        f"시가총액: {item.get('시가총액', 'N/A')}\n"
        f"배당수익률: {item.get('배당수익률', 'N/A')}\n"
        f"부채비율: {item.get('부채비율', 'N/A')}\n"
        f"당기순이익: {item.get('당기순이익', 'N/A')}"
        for item in financial_data
    ]
    financial_metadatas = [{"source": "financial"} for _ in financial_data]

    # 전체 텍스트와 메타데이터 통합
    all_texts = news_texts + financial_texts
    all_metadatas = news_metadatas + financial_metadatas

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=900,
        chunk_overlap=100,
        length_function=tiktoken_len
    )
    return text_splitter.create_documents(all_texts, metadatas=all_metadatas)


def get_vectorstore(text_chunks):
    """
    텍스트 청크에서 벡터 저장소를 생성하는 함수

    Args:
        text_chunks (list): 텍스트 청크 목록

    Returns:
        FAISS: 생성된 벡터 저장소
    """
    embeddings = HuggingFaceEmbeddings(
        model_name="jhgan/ko-sroberta-multitask",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )
    return FAISS.from_documents(text_chunks, embeddings)


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
    llm = ChatOpenAI(openai_api_key=openai_api_key, model_name='gpt-4', temperature=0.3)

    # 맞춤형 프롬프트 템플릿 적용
    custom_prompt = create_financial_aware_prompt_template()

    return ConversationalRetrievalChain.from_llm(
        llm=llm,
        chain_type="stuff",
        retriever=vectorstore.as_retriever(),
        memory=ConversationBufferMemory(memory_key='chat_history', return_messages=True, output_key='answer'),
        get_chat_history=lambda h: h,
        return_source_documents=True,
        combine_docs_chain_kwargs={'prompt': custom_prompt}
    )
