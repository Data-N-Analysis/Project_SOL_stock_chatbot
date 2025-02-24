import streamlit as st
import requests
import random
import time
import urllib.parse
import mplfinance as mpf
import FinanceDataReader as fdr
import tiktoken
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS
from langchain.chat_models import ChatOpenAI
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import os
import random
from difflib import SequenceMatcher
import urllib.parse



# 현재 파일(파이썬 스크립트) 기준 폰트 경로를 지정
font_path = os.path.join(os.path.dirname(__file__), 'fonts', 'NanumGothic.ttf')
if os.path.exists(font_path):
    font_name = fm.FontProperties(fname=font_path).get_name()
    plt.rcParams['font.family'] = font_name
    plt.rcParams['axes.unicode_minus'] = False
else:
    st.warning("폰트 파일을 찾을 수 없습니다. 한글이 깨질 수 있습니다.")


def main():
    st.set_page_config(page_title="Stock Analysis Chatbot", page_icon=":chart_with_upwards_trend:")
    st.title("기업 정보 분석 QA Chat :red[QA Chat]_ :chart_with_upwards_trend:")

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

    with st.sidebar:
        openai_api_key = st.text_input("OpenAI API Key", key="chatbot_api_key", type="password")
        company_name = st.text_input("분석할 기업명 (코스피 상장)")
        days = st.number_input("며칠 전부터의 기사를 검색할까요?", min_value=1, value=7)  # 기간을 사용자 입력받기
        process = st.button("분석 시작")

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

    # 분석 결과가 있으면 항상 상단에 출력
    if st.session_state.processComplete and st.session_state.company_name:
        st.subheader(f"{st.session_state.company_name} 최근 주가 추이")
        visualize_stock(st.session_state.company_name, "일")
        
        st.markdown("최근 기업 뉴스 목록을 보려면 누르시오")
        
    # 뉴스 보기 섹션은 이제 첫 화면에서는 표시하지 않음
    if st.session_state.processComplete:
        with st.expander("뉴스 보기"):
            # 처음에는 10개의 뉴스만 표시
            for i, news in enumerate(st.session_state.news_data[:10]):
                st.markdown(f"- **{news['title']}** ([링크]({news['link']}))")

            # '더보기'를 클릭했을 때 나머지 뉴스도 표시
            if len(st.session_state.news_data) > 10:
                if st.button('더보기'):
                    for news in st.session_state.news_data[10:]:
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



def similar(a, b):
    """두 문자열의 유사도를 0과 1 사이의 값으로 반환 (1은 완전 일치)"""
    return SequenceMatcher(None, a, b).ratio()


def crawl_news(company, days, threshold=0.8):
    today = datetime.today()
    start_date = (today - timedelta(days=days)).strftime('%Y%m%d')
    end_date = today.strftime('%Y%m%d')
    encoded_query = urllib.parse.quote(company)

    # 뉴스 검색 URL, 페이지를 추가하여 여러 번 요청
    url_template = f"https://search.naver.com/search.naver?where=news&query={encoded_query}&nso=so:r,p:from{start_date}to{end_date}&start={{}}"
    
    headers = {
        "User-Agent": random.choice([
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Safari/537.36"
        ])
    }

    data = []
    for page in range(1, 6):  # 1부터 5페이지까지 요청
        url = url_template.format((page - 1) * 10 + 1)  # 페이지마다 다른 'start' 값
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        articles = soup.select("ul.list_news > li")

        for article in articles:
            title = article.select_one("a.news_tit").text
            link = article.select_one("a.news_tit")['href']
            content = article.select_one("div.news_dsc").text if article.select_one("div.news_dsc") else ""
            data.append({"title": title, "link": link, "content": content})

    # 뉴스 중복 제거
    return deduplicate_news(data, threshold)


def deduplicate_news(news_data, threshold=0.8):
    # 중복 뉴스 제거 함수
    seen_titles = set()
    unique_news = []

    for news in news_data:
        if news["title"] not in seen_titles:
            seen_titles.add(news["title"])
            unique_news.append(news)
    
    # 뉴스 내용 유사도 확인하여 중복 제거
    unique_news_filtered = []
    for i, news in enumerate(unique_news):
        add_news = True
        for j in range(i):
            if calculate_similarity(news['content'], unique_news[j]['content']) > threshold:
                add_news = False
                break
        if add_news:
            unique_news_filtered.append(news)

    return unique_news_filtered


def calculate_similarity(text1, text2):
    # 텍스트 유사도 계산 (예시로 cosine similarity 활용)
    return text1 == text2  # 간단한 예시로, 실제 구현시 다양한 유사도 방법을 사용할 수 있음.


def tiktoken_len(text):
    tokenizer = tiktoken.get_encoding("cl100k_base")
    tokens = tokenizer.encode(text)
    return len(tokens)

def get_text_chunks(news_data):
    texts = [f"{item['title']}\n{item['content']}" for item in news_data]
    metadatas = [{"source": item["link"]} for item in news_data]
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=900,
        chunk_overlap=100,
        length_function=tiktoken_len
    )
    return text_splitter.create_documents(texts, metadatas=metadatas)

def get_vectorstore(text_chunks):
    embeddings = HuggingFaceEmbeddings(
        model_name="jhgan/ko-sroberta-multitask",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )
    return FAISS.from_documents(text_chunks, embeddings)

def create_chat_chain(vectorstore, openai_api_key):
    llm = ChatOpenAI(openai_api_key=openai_api_key, model_name='gpt-4', temperature=0)
    return ConversationalRetrievalChain.from_llm(
        llm=llm, chain_type="stuff", retriever=vectorstore.as_retriever(),
        memory=ConversationBufferMemory(memory_key='chat_history', return_messages=True, output_key='answer'),
        get_chat_history=lambda h: h, return_source_documents=True)

def get_ticker(company):
    """
    FinanceDataReader를 통해 KRX 상장 기업 정보를 불러오고,
    입력한 기업명에 해당하는 티커 코드를 반환합니다.
    환경에 따라 컬럼명이 다를 수 있으므로 여러 경우를 처리합니다.
    """
    try:
        listing = fdr.StockListing('KRX')
        if listing.empty:
            listing = fdr.StockListing('KOSPI')
        if listing.empty:
            st.error("KRX 혹은 KOSPI 상장 기업 정보를 불러올 수 없습니다.")
            return None

        # 여러 가지 컬럼 조합에 대해 처리합니다.
        if "Code" in listing.columns and "Name" in listing.columns:
            name_col = "Name"
            ticker_col = "Code"
        elif "Symbol" in listing.columns and "Name" in listing.columns:
            name_col = "Name"
            ticker_col = "Symbol"
        elif "종목코드" in listing.columns and "기업명" in listing.columns:
            name_col = "기업명"
            ticker_col = "종목코드"
        else:
            st.error("상장 기업 정보의 컬럼명이 예상과 다릅니다: " + ", ".join(listing.columns))
            return None

        # 좌우 공백 제거 후 비교
        ticker_row = listing[listing[name_col].str.strip() == company.strip()]
        if ticker_row.empty:
            st.error(f"입력한 기업명 '{company}'에 해당하는 정보가 없습니다.\n예시: '삼성전자' 입력 시 티커 '005930'을 반환합니다.")
            return None
        else:
            ticker = ticker_row.iloc[0][ticker_col]
            # 숫자 형식인 경우 6자리 문자열로 변환 (예: 5930 -> '005930')
            return str(ticker).zfill(6)
    except Exception as e:
        st.error(f"티커 변환 중 오류 발생: {e}")
        return None


def visualize_stock(company, period):
    ticker = get_ticker(company)
    if not ticker:
        st.error("해당 기업의 티커 코드를 찾을 수 없습니다. 올바른 기업명을 입력했는지 확인해주세요.")
        return

    try:
        df = fdr.DataReader(ticker, '2024-01-01')
    except Exception as e:
        st.error(f"주가 데이터를 불러오는 중 오류 발생: {e}")
        return

    if period == "일":
        df = df.tail(30)
    elif period == "주":
        df = df.resample('W').last()
    elif period == "월":
        df = df.resample('M').last()
    elif period == "년":
        df = df.resample('Y').last()

    # returnfig=True 옵션으로 mplfinance가 Figure+Axes를 생성하게 한 뒤, st.pyplot()으로 출력
    fig, _ = mpf.plot(
        df,
        type='candle',
        style='charles',
        title=f"{company}({ticker}) 주가 ({period})",
        volume=True,
        returnfig=True
    )
    st.pyplot(fig)

if __name__ == '__main__':
    main()
