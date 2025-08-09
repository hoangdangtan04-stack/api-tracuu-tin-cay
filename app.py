# app.py
# Mã nguồn được phát triển bởi chuyên gia Python và Promt để cải thiện quy trình tra cứu thông tin.

import os
import requests
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

# --- Bắt đầu phần Cấu hình API ---

app = Flask(__name__)
CORS(app) # Cho phép các yêu cầu từ các domain khác truy cập API.

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


# --- Bắt đầu phần Logic xử lý Web Scraping và Phân tích ---

def check_relevance(title, query_words):
    """
    Kiểm tra mức độ liên quan của tiêu đề bài viết với các từ khóa tìm kiếm.
    Trả về số từ khóa khớp.
    """
    relevance_score = 0
    title_lower = title.lower()
    for word in query_words:
        if word in title_lower:
            relevance_score += 1
    return relevance_score

def scrape_data(source_name, source_url, query_words, original_query):
    """
    Hàm này thực hiện web scraping trên một URL nguồn cụ thể.
    Nó tìm kiếm các bài viết liên quan và trích xuất tiêu đề, URL.
    """
    # Mã hóa chuỗi truy vấn để sử dụng trong URL
    encoded_query = quote_plus(original_query)
    search_url = source_url.format(query=encoded_query)
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(search_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            matched_articles = []
            
            # --- Logic cụ thể cho từng trang báo (đã mở rộng) ---
            if "vnexpress" in source_url:
                articles = soup.find_all('article', class_='item-news')
            elif "thanhnien" in source_url:
                articles = soup.find_all('article', class_='story')
            elif "tuoitre" in source_url:
                articles = soup.find_all('div', class_='name-news')
            elif "vietnamnet" in source_url:
                articles = soup.find_all('div', class_='box-content-search-result')
            else:
                articles = []

            for article in articles:
                title_tag = article.find('h3', class_='title-news') or article.find('h2', class_='story__title') or article.find('h3', class_='title')
                if title_tag:
                    title = title_tag.a.get_text(strip=True)
                    url = title_tag.a['href']
                    
                    # Cập nhật URL đầy đủ cho VietnamNet
                    if "vietnamnet" in source_url and not url.startswith("http"):
                        url = "https://vietnamnet.vn" + url
                    
                    relevance = check_relevance(title, query_words)
                    
                    # Chỉ thêm bài viết nếu có ít nhất 1 từ khóa khớp
                    if relevance > 0:
                        matched_articles.append({'title': title, 'url': url, 'relevance_score': relevance})
            
            return matched_articles
        return []
    except requests.exceptions.RequestException as e:
        # Xử lý lỗi kết nối một cách chi tiết
        print(f"Lỗi khi kết nối đến {source_name}: {e}")
        return []

# --- Kết thúc phần Logic xử lý Web Scraping và Phân tích ---


# --- Bắt đầu phần Điểm cuối API (Endpoint) ---

@app.route('/search', methods=['POST'])
def check_trustworthiness():
    """
    Điểm cuối API này nhận nội dung tìm kiếm từ n8n,
    gọi hàm scraping và trả về kết quả phân tích.
    """
    try:
        data = request.get_json()
        original_query = data.get('query', '')
        
        if not original_query:
            return jsonify({
                "message": "Vui lòng cung cấp nội dung tra cứu.",
                "is_reliable": False,
                "matched_sources": [],
                "matching_articles_count": 0
            }), 400

        # Phân tách nội dung tra cứu thành các từ khóa
        query_words = [word.lower() for word in original_query.split()]

        all_matched_sources = []
        total_articles = 0
        total_relevance_score = 0
        
        for source_name, source_url_template in RELIABLE_SOURCES.items():
            articles = scrape_data(source_name, source_url_template, query_words, original_query)
            
            if articles:
                # Sắp xếp các bài viết theo điểm liên quan giảm dần
                articles.sort(key=lambda x: x['relevance_score'], reverse=True)
                
                # Giới hạn số bài viết trả về từ mỗi nguồn để tối ưu hóa
                for article in articles[:5]:
                    all_matched_sources.append({
                        "name": source_name,
                        "url": article['url'],
                        "title": article['title'],
                        "relevance_score": article['relevance_score']
                    })
                    total_articles += 1
                    total_relevance_score += article['relevance_score']

        # Phân tích kết quả và trả về phản hồi JSON chi tiết hơn
        if total_articles > 0 and total_relevance_score > 0:
            return jsonify({
                "message": f"Tìm thấy {total_articles} bài viết liên quan trên {len(set(source['name'] for source in all_matched_sources))} nguồn đáng tin cậy.",
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
        print(f"Có lỗi xảy ra: {e}")
        return jsonify({
            "message": f"Có lỗi xảy ra ở máy chủ: {str(e)}",
            "is_reliable": None,
            "matched_sources": [],
            "matching_articles_count": 0
        }), 500

# --- Kết thúc phần Điểm cuối API (Endpoint) ---


# --- Bắt đầu phần Khởi chạy ứng dụng ---

if __name__ == '__main__':
    # Sử dụng biến môi trường PORT để Render có thể chạy ứng dụng
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', debug=True, port=port)

# --- Kết thúc phần Khởi chạy ứng dụng ---
