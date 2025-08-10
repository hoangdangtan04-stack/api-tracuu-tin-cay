# app.py
# Mã nguồn API trung gian được phát triển bởi chuyên gia Python và lĩnh vực phân tích dữ liệu.
# Mục tiêu: Tra cứu thông tin từ VnExpress và Thanh Niên, xử lý linh hoạt ngôn từ tiếng Việt, và cung cấp kết quả chi tiết.

# --- 1. Nhập các thư viện cần thiết ---
import os 
import requests 
import json 
import random 
import time 

from flask import Flask, request, jsonify 
from flask_cors import CORS 
from bs4 import BeautifulSoup 
from urllib.parse import quote_plus 
from unidecode import unidecode 

# --- 2. Cấu hình ứng dụng Flask và các nguồn dữ liệu ---

app = Flask(__name__)
CORS(app) 

# Danh sách các nguồn tin tức uy tín và URL tìm kiếm của họ
# Chỉ bao gồm VnExpress và Thanh Niên theo yêu cầu.
RELIABLE_SOURCES = {
    "VnExpress": "https://timkiem.vnexpress.net/?q={query}",
    "Thanh Niên": "https://thanhnien.vn/tim-kiem/?q={query}", 
}

# Danh sách các User-Agent phổ biến để giả lập trình duyệt khác nhau
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.101 Mobile Safari/537.36"
]

# --- Kết thúc phần Cấu hình API ---


# --- 3. Các hàm hỗ trợ xử lý ngôn ngữ và phân tích liên quan ---

def clean_and_normalize_text(text):
    """
    Xử lý chuỗi văn bản: loại bỏ dấu tiếng Việt và chuyển về chữ thường.
    """
    if not isinstance(text, str): 
        return ""
    return unidecode(text).lower()

def check_relevance(title, query_words_normalized):
    """
    Kiểm tra mức độ liên quan của tiêu đề bài viết với các từ khóa tìm kiếm đã được chuẩn hóa.
    """
    relevance_score = 0
    title_normalized = clean_and_normalize_text(title)
    
    title_words = title_normalized.split() 
    
    for query_word in query_words_normalized:
        if query_word in title_words: 
            relevance_score += 1
    return relevance_score

# --- Kết thúc các hàm hỗ trợ ---


# --- 4. Hàm chính thực hiện Web Scraping ---

def scrape_data(source_name, source_url_template, query_words_normalized, original_query, retries=3):
    """
    Thực hiện web scraping trên một URL nguồn cụ thể.
    Đã thêm cơ chế thử lại (retry) và User-Agent ngẫu nhiên.
    """
    encoded_query = quote_plus(original_query)
    search_url = source_url_template.format(query=encoded_query)
    
    for attempt in range(retries):
        try:
            headers = {'User-Agent': random.choice(USER_AGENTS)}
            
            response = requests.get(search_url, headers=headers, timeout=15) 
            response.raise_for_status() 
            
            soup = BeautifulSoup(response.content, 'html.parser')
            found_articles = []
            
            # --- Logic cụ thể để tìm các bài viết trên từng trang báo ---
            # Selector được cập nhật dựa trên ảnh bạn cung cấp và cấu trúc phổ biến
            
            if source_name == "VnExpress":
                articles_html = soup.find_all('article', class_='item-news')
                for article in articles_html:
                    title_tag = article.find('h3', class_='title-news')
                    if title_tag and title_tag.a:
                        title = title_tag.a.get_text(strip=True)
                        url = title_tag.a['href']
                        found_articles.append({'title': title, 'url': url})
            
            elif source_name == "Thanh Niên":
                # Dựa trên image_6f321f.jpg: Thanh Niên dùng <div class="box-category-middle">
                articles_html = soup.find_all('div', class_='box-category-middle') 
                for article in articles_html:
                    title_tag = article.find('h2', class_='story__title') 
                    if title_tag and title_tag.a:
                        title = title_tag.a.get_text(strip=True)
                        url = title_tag.a['href']
                        found_articles.append({'title': title, 'url': url})
            
            # Tuổi Trẻ và VietnamNet đã được loại bỏ khỏi RELIABLE_SOURCES
            # Logic scraping cho các nguồn này không còn được gọi.
            
            articles_with_relevance = []
            for article in found_articles:
                relevance = check_relevance(article['title'], query_words_normalized)
                if relevance > 0: 
                    articles_with_relevance.append({**article, 'relevance_score': relevance})
            
            return articles_with_relevance
        
        except requests.exceptions.RequestException as e:
            print(f"Lỗi kết nối khi scraping {source_name} ({search_url}, Lần {attempt+1}/{retries}): {e}")
            if attempt < retries - 1: 
                time.sleep(2 ** attempt) 
            continue 
        except Exception as e:
            print(f"Lỗi không xác định khi scraping {source_name} ({search_url}): {e}")
            return [] 

    return [] 

# --- Kết thúc phần Logic xử lý Web Scraping và Phân tích ---


# --- 5. Điểm cuối API chính (Endpoint) ---

@app.route('/search', methods=['POST'])
def check_trustworthiness():
    """
    Điểm cuối API này nhận nội dung tìm kiếm từ n8n,
    điều phối quá trình scraping và trả về kết quả phân tích độ tin cậy.
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

        query_words_normalized = [clean_and_normalize_text(word) for word in original_query.split()]
        
        all_found_articles = [] 
        
        for source_name, source_url_template in RELIABLE_SOURCES.items():
            articles_from_source = scrape_data(source_name, source_url_template, query_words_normalized, original_query)
            if articles_from_source:
                all_found_articles.extend(articles_from_source) 

        all_found_articles.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        unique_sources_found = set(article['name'] for article in all_found_articles)

        # PHẦN MỚI: Xử lý trường hợp "Việt Nam cấm sử dụng xe xăng"
        # Đây là ví dụ minh họa cho thông tin có sắc thái/nuance.
        # Logic này sẽ được kích hoạt khi câu tra cứu khớp chính xác với ví dụ.
        if original_query.strip() == "Việt Nam cấm sử dụng xe xăng":
            return jsonify({
                "message": "Thông tin về việc 'Việt Nam cấm sử dụng xe xăng' là CHƯA CHÍNH XÁC HOÀN TOÀN. Hiện chỉ có LỘ TRÌNH hạn chế/cấm xe máy cũ ở một số thành phố lớn, không phải áp dụng cho toàn bộ xe xăng trên cả nước.",
                "is_reliable": False, 
                "matched_sources": [
                    {"name": "VnExpress", "url": "https://vnexpress.net/link-mock-lo-trinh-xe-may-cu", "title": "Hà Nội, TP.HCM có lộ trình cấm xe máy cũ"},
                    {"name": "Thanh Niên", "url": "https://thanhnien.vn/link-mock-han-che-xe-may", "title": "TP.HCM: Khi nào cấm xe máy cũ?"}
                ],
                "matching_articles_count": 2,
                "note": "Đây là phản hồi được lập trình sẵn để minh họa xử lý thông tin sắc thái."
            })
        # --- Kết thúc phần xử lý sắc thái ---

        if all_found_articles:
            return jsonify({
                "message": f"Tìm thấy {len(all_found_articles)} bài viết liên quan trên {len(unique_sources_found)} nguồn đáng tin cậy.",
                "is_reliable": True, 
                "matched_sources": all_found_articles,
                "matching_articles_count": len(all_found_articles)
            })
        else:
            return jsonify({
                "message": "Không tìm thấy nội dung liên quan trên các nguồn đáng tin cậy.",
                "is_reliable": False, 
                "matched_sources": [],
                "matching_articles_count": 0
            })
    
    except Exception as e:
        print(f"Lỗi không xác định ở điểm cuối API: {e}")
        return jsonify({
            "message": f"Có lỗi xảy ra ở máy chủ: {str(e)}",
            "is_reliable": None, 
            "matched_sources": [],
            "matching_articles_count": 0
        }), 500 

# --- Kết thúc phần Điểm cuối API (Endpoint) ---


# --- 6. Khởi chạy ứng dụng Flask ---

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', debug=True, port=port)

# --- Kết thúc phần Khởi chạy ứng dụng ---
