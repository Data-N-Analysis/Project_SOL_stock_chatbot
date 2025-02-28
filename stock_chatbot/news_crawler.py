import requests
import urllib.parse
import random
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def crawl_news(company, days, threshold=0.3):
    """
    특정 기업에 대한 최근 뉴스를 크롤링하고 중복 제거하여 반환

    Args:
        company (str): 검색할 기업명
        days (int): 검색할 날짜 범위(일)
        threshold (float): 중복 판단을 위한 유사도 임계값

    Returns:
        list: 뉴스 데이터 목록 (제목, 링크, 내용 포함)
    """
    today = datetime.today()
    start_date = (today - timedelta(days=days)).strftime('%Y%m%d')
    end_date = today.strftime('%Y%m%d')
    encoded_query = urllib.parse.quote(company)

    url_template = f"https://search.naver.com/search.naver?where=news&query={encoded_query}&nso=so:r,p:from{start_date}to{end_date}&start={{}}"

    headers = {
        "User-Agent": random.choice([
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Safari/537.36"
        ])
    }

    data = []
    for page in range(1, 6):
        url = url_template.format((page - 1) * 10 + 1)
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        articles = soup.select("ul.list_news > li")

        for article in articles:
            title = article.select_one("a.news_tit").text
            link = article.select_one("a.news_tit")['href']
            content = article.select_one("div.news_dsc").text if article.select_one("div.news_dsc") else ""
            data.append({"title": title, "link": link, "content": content})

    return deduplicate_news(data, threshold)


def deduplicate_news(news_data, threshold=0.3):
    """
    중복된 뉴스를 제거하는 함수

    Args:
        news_data (list): 뉴스 데이터 리스트
        threshold (float): 중복 판단 임계값

    Returns:
        list: 중복이 제거된 뉴스 데이터
    """
    if len(news_data) <= 1:
        return news_data

    # 제목과 본문을 합친 텍스트 생성
    combined_texts = [news['title'] + " " + news['content'] for news in news_data]
    vectorizer = TfidfVectorizer().fit_transform(combined_texts)
    cosine_sim = cosine_similarity(vectorizer, vectorizer)

    filtered_news = []
    seen_indices = set()

    for i, news in enumerate(news_data):
        if i in seen_indices:
            continue

        filtered_news.append(news)
        for j in range(i + 1, len(news_data)):
            if news_data[j]['title'] == news['title'] or cosine_sim[i, j] > threshold:
                seen_indices.add(j)

    return filtered_news