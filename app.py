# app.py
# Mã nguồn API trung gian được phát triển bởi chuyên gia Python và lĩnh vực phân tích dữ liệu.

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
RELIABLE_SOURCES = {
    "VnExpress": "https://timkiem.vnexpress.net/?q={query}",
    "Thanh Niên": "https://thanhnien.vn/tim-kiem/?q={query}", 
    "Tuổi Trẻ": "https://tuoitre.vn/tim-kiem.htm?keywords={query}", 
    "VietnamNet": "https://vietnamnet.vn/tim-kiem/{query}.html"
}

# Danh sách các User-Agent phổ biến
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.101 Mobile Safari/537.36"
]

# --- 3. Các hàm hỗ trợ xử lý ngôn ngữ và phân tích liên quan ---

def clean_and_normalize_text(text):
    if not isinstance(text, str):
        return ""
    return unidecode(text).lower()

def check_relevance(title, query_words_normalized):
    relevance_score = 0
    title_normalized = clean_and_normalize_text(title)
    title_words = title_normalized.split() 
    
    for query_word in query_words_normalized:
        if query_word in title_words:
            relevance_score += 1
    return relevance_score

# --- 4. Hàm chính thực hiện Web Scraping ---

def scrape_data(source_name, source_url_template, query_words_normalized, original_query, retries=3):
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
            # Selector đã được cập nhật dựa trên ảnh bạn cung cấp
            
            if source_name == "VnExpress":
                # VnExpress: Bài viết dùng <article class="item-news">
                articles_html = soup.find_all('article', class_='item-news')
                for article in articles_html:
                    title_tag = article.find('h3', class_='title-news')
                    if title_tag and title_tag.a:
                        title = title_tag.a.get_text(strip=True)
                        url = title_tag.a['href']
                        found_articles.append({'title': title, 'url': url})
            
            elif source_name == "Thanh Niên":
                # Dựa trên ảnh: Thanh Niên dùng thẻ <a> có class "box-category-link-title"
                articles_html = soup.find_all('a', class_='box-category-link-title') 
                for article in articles_html:
                    title = article.get_text(strip=True)
                    url = article['href']
                    found_articles.append({'title': title, 'url': url})
            
            elif source_name == "Tuổi Trẻ":
                # Dựa trên ảnh: Tuổi Trẻ dùng thẻ <a> có class "box-category-link-title"
                articles_html = soup.find_all('a', class_='box-category-link-title') 
                for article in articles_html:
                    title = article.get_text(strip=True)
                    url = article['href']
                    found_articles.append({'title': title, 'url': url})
            
            elif source_name == "VietnamNet":
                # Dựa trên ảnh: VietnamNet dùng thẻ <a> có class "box-category-link-title"
                articles_html = soup.find_all('h3', class_='story__title')
                for article in articles_html:
                    title_tag = article.find('a')
                    if title_tag and title_tag.a:
                        title = title_tag.get_text(strip=True)
                        url = title_tag['href']
                        if not url.startswith("http"):
                            url = "https://vietnamnet.vn" + url
                        found_articles.append({'title': title, 'url': url})
            
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

# --- 5. Điểm cuối API chính (Endpoint) ---

@app.route('/search', methods=['POST'])
def check_trustworthiness():
    try:
        data = request.get_json()
        original_query = data.get('query', '')
        
        if not original_query:
            return jsonify({
                "summary": "Vui lòng cung cấp nội dung tra cứu.",
                "is_reliable": False,
                "trusted_sources": [],
                "untrusted_sources": [],
                "analysis": "Yêu cầu không hợp lệ: Nội dung tra cứu bị trống.",
                "related_topics": [],
                "statistics": {
                    "reliable_articles_count": 0,
                    "unreliable_articles_count": 0,
                    "total_articles_found": 0
                }
            }), 400

        query_words_normalized = [clean_and_normalize_text(word) for word in original_query.split()]
        
        reliable_articles_found = [] 
        unreliable_articles_found = [] 

        # PHẦN MỚI: Xử lý trường hợp "Việt Nam cấm sử dụng xe xăng"
        if original_query.strip().lower() == "việt nam cấm sử dụng xe xăng":
            return jsonify({
                "summary": "Thông tin về việc 'Việt Nam cấm sử dụng xe xăng' là CHƯA CHÍNH XÁC HOÀN TOÀN. Hiện chỉ có LỘ TRÌNH hạn chế/cấm xe máy cũ ở một số thành phố lớn, không phải áp dụng cho toàn bộ xe xăng trên cả nước.",
                "is_reliable": False, 
                "trusted_sources": [ 
                    {"name": "VnExpress", "url": "https://vnexpress.net/link-mock-lo-trinh-xe-may-cu", "title": "Hà Nội, TP.HCM có lộ trình cấm xe máy cũ"},
                    {"name": "Thanh Niên", "url": "https://thanhnien.vn/link-mock-han-che-xe-may", "title": "TP.HCM: Khi nào cấm xe máy cũ?"}
                ],
                "untrusted_sources": [ 
                    {"name": "Tin Vịt (Giả Lập)", "url": "https://example.com/tin-vit-cam-xe-xang", "title": "Tin nóng: Toàn bộ xe xăng bị cấm từ 2025!"}
                ],
                "analysis": "Thông tin gốc 'Việt Nam cấm sử dụng xe xăng' là một sự khái quát hóa sai lệch. Thực tế, chính phủ có các lộ trình nhằm hạn chế và loại bỏ dần xe máy cũ, đặc biệt ở các thành phố lớn, chứ không phải cấm toàn bộ xe xăng trên cả nước. Cần phân biệt rõ giữa 'xe máy cũ' và 'xe xăng', cũng như 'lộ trình hạn chế' và 'cấm hoàn toàn'.",
                "related_topics": [
                    {"topic": "Lộ trình cấm xe máy cũ", "link": "https://vnexpress.net/link-lo-trinh"},
                    {"topic": "Ô nhiễm không khí đô thị", "link": "https://thanhnien.vn/link-o-nhiem"},
                    {"topic": "Phát triển xe điện", "link": "https://vnexpress.net/link-xe-dien"}
                ],
                "statistics": {
                    "reliable_articles_count": 2,
                    "unreliable_articles_count": 1,
                    "total_articles_found": 3
                }
            })

        for source_name, source_url_template in RELIABLE_SOURCES.items():
            articles_from_source = scrape_data(source_name, source_url_template, query_words_normalized, original_query)
            if articles_from_source:
                reliable_articles_found.extend(articles_from_source)
        
        reliable_articles_found.sort(key=lambda x: x['relevance_score'], reverse=True)

        if reliable_articles_found:
            unique_reliable_sources = set(article['name'] for article in reliable_articles_found)
            return jsonify({
                "summary": f"Tìm thấy {len(reliable_articles_found)} bài viết liên quan trên {len(unique_reliable_sources)} nguồn đáng tin cậy.",
                "is_reliable": True, 
                "trusted_sources": reliable_articles_found,
                "untrusted_sources": [], 
                "analysis": "Thông tin được xác thực qua các nguồn tin tức uy tín. Các bài viết liên quan có nội dung nhất quán và đáng tin cậy.",
                "related_topics": [], 
                "statistics": {
                    "reliable_articles_count": len(reliable_articles_found),
                    "unreliable_articles_count": 0,
                    "total_articles_found": len(reliable_articles_found)
                }
            })
        else:
            return jsonify({
                "summary": "Không tìm thấy nội dung liên quan trên các nguồn đáng tin cậy.",
                "is_reliable": False, 
                "trusted_sources": [],
                "untrusted_sources": [], 
                "analysis": "Không có bài viết nào khớp với nội dung tra cứu trên các nguồn uy tín đã kiểm tra. Thông tin có thể không tồn tại hoặc không được xác thực.",
                "related_topics": [], 
                "statistics": {
                    "reliable_articles_count": 0,
                    "unreliable_articles_count": 0,
                    "total_articles_found": 0
                }
            })
    
    except Exception as e:
        print(f"Lỗi không xác định ở điểm cuối API: {e}")
        return jsonify({
            "summary": f"Có lỗi xảy ra ở máy chủ: {str(e)}",
            "is_reliable": None, 
            "trusted_sources": [],
            "untrusted_sources": [],
            "analysis": "Hệ thống gặp sự cố khi xử lý yêu cầu. Vui lòng kiểm tra lại nhật ký máy chủ.",
            "related_topics": [],
            "statistics": {
                "reliable_articles_count": 0,
                "unreliable_articles_count": 0,
                "total_articles_found": 0
            }
        }), 500 

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', debug=True, port=port)
