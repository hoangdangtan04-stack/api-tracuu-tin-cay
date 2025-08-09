# app.py

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup

# --- Bắt đầu phần Cấu hình API ---

app = Flask(__name__)
CORS(app)

# Danh sách các nguồn tin tức uy tín và URL tìm kiếm của họ
# Các URL này đã được thiết kế để tìm kiếm theo một từ khóa.
# {query} là một biến giữ chỗ cho nội dung tìm kiếm của người dùng.
RELIABLE_SOURCES = {
    "VnExpress": "https://timkiem.vnexpress.net/?q={query}",
    "Thanh Niên": "https://thanhnien.vn/tim-kiem/?q={query}",
    "Tuổi Trẻ": "https://tuoitre.vn/tim-kiem.html?q={query}",
    "VietnamNet": "https://vietnamnet.vn/tim-kiem/{query}.html"
}

# --- Kết thúc phần Cấu hình API ---


# --- Bắt đầu phần Logic xử lý Web Scraping ---

def scrape_data(source_url, query):
    """
    Hàm này thực hiện web scraping trên một URL nguồn cụ thể.
    Nó tìm kiếm các bài viết liên quan đến query và trích xuất tiêu đề, URL.
    """
    search_url = source_url.format(query=query)
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(search_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            matched_articles = []
            
            # --- Logic cụ thể cho từng trang báo ---
            if "vnexpress" in source_url:
                articles = soup.find_all('article', class_='item-news')
                for article in articles:
                    title_tag = article.find('h3', class_='title-news')
                    if title_tag:
                        title = title_tag.a.get_text(strip=True)
                        url = title_tag.a['href']
                        matched_articles.append({'title': title, 'url': url})
            
            elif "thanhnien" in source_url:
                articles = soup.find_all('article', class_='story')
                for article in articles:
                    title_tag = article.find('h2', class_='story__title')
                    if title_tag:
                        title = title_tag.a.get_text(strip=True)
                        url = title_tag.a['href']
                        matched_articles.append({'title': title, 'url': url})
            
            elif "tuoitre" in source_url:
                articles = soup.find_all('div', class_='name-news')
                for article in articles:
                    title_tag = article.find('h3', class_='title-news')
                    if title_tag:
                        title = title_tag.a.get_text(strip=True)
                        url = title_tag.a['href']
                        matched_articles.append({'title': title, 'url': url})

            elif "vietnamnet" in source_url:
                articles = soup.find_all('div', class_='box-content-search-result')
                for article in articles:
                    title_tag = article.find('h3', class_='title')
                    if title_tag:
                        title = title_tag.a.get_text(strip=True)
                        url = "https://vietnamnet.vn" + title_tag.a['href']
                        matched_articles.append({'title': title, 'url': url})
            
            return matched_articles
        return []
    except requests.exceptions.RequestException:
        return []

# --- Kết thúc phần Logic xử lý Web Scraping ---


# --- Bắt đầu phần Điểm cuối API (Endpoint) ---

@app.route('/search', methods=['POST'])
def check_trustworthiness():
    """
    Điểm cuối API này nhận nội dung tìm kiếm từ n8n,
    gọi hàm scraping và trả về kết quả phân tích.
    """
    try:
        data = request.get_json()
        query = data.get('query', '')
        
        if not query:
            return jsonify({
                "message": "Không tìm thấy nội dung tra cứu.",
                "is_reliable": False,
                "matched_sources": [],
                "matching_articles_count": 0
            }), 400

        all_matched_sources = []
        total_articles = 0
        
        for source_name, source_url_template in RELIABLE_SOURCES.items():
            articles = scrape_data(source_url_template, query)
            
            if articles:
                for article in articles:
                    all_matched_sources.append({
                        "name": source_name,
                        "url": article['url'],
                        "title": article['title']
                    })
                total_articles += len(articles)

        if total_articles > 0:
            return jsonify({
                "message": f"Tìm thấy {total_articles} bài viết liên quan trên các nguồn đáng tin cậy.",
                "is_reliable": True,
                "matched_sources": all_matched_sources,
                "matching_articles_count": total_articles
            })
        else:
            return jsonify({
                "message": "Không tìm thấy nội dung liên quan trên các nguồn đáng tin cậy.",
                "is_reliable": False,
                "matched_sources": [],
                "matching_articles_count": 0
            })
    
    except Exception as e:
        return jsonify({
            "message": f"Có lỗi xảy ra: {str(e)}",
            "is_reliable": None,
            "matched_sources": [],
            "matching_articles_count": 0
        }), 500

# --- Kết thúc phần Điểm cuối API (Endpoint) ---


# --- Bắt đầu phần Khởi chạy ứng dụng ---

if __name__ == '__main__':
    app.run(debug=True, port=5000)

# --- Kết thúc phần Khởi chạy ứng dụng ---
