# app.py
# Mã nguồn API trung gian được phát triển bởi chuyên gia Python và lĩnh vực phân tích dữ liệu.
# Mục tiêu: Tra cứu thông tin đa nguồn, xử lý linh hoạt ngôn từ tiếng Việt, và cung cấp kết quả chi tiết.

# --- 1. Nhập các thư viện cần thiết ---
# Các thư viện này là nền tảng để xây dựng API web, gửi yêu cầu HTTP và phân tích HTML.
import os # Để truy cập các biến môi trường (ví dụ: PORT trên Render)
import requests # Thư viện mạnh mẽ để gửi các yêu cầu HTTP (GET, POST, v.v.)
import json # Để làm việc với dữ liệu JSON
from flask import Flask, request, jsonify # Flask framework để xây dựng API web
from flask_cors import CORS # Để xử lý CORS (Cross-Origin Resource Sharing)
from bs4 import BeautifulSoup # Thư viện để phân tích cú pháp HTML (web scraping)
from urllib.parse import quote_plus # Để mã hóa chuỗi truy vấn cho URL
from unidecode import unidecode # Thư viện để chuyển đổi văn bản tiếng Việt có dấu thành không dấu

# --- 2. Cấu hình ứng dụng Flask và các nguồn dữ liệu ---

# Khởi tạo ứng dụng Flask. Đây là "trái tim" của API.
app = Flask(__name__)

# Cấu hình CORS (Cross-Origin Resource Sharing)
# Điều này cho phép API của bạn nhận yêu cầu từ các domain khác (ví dụ: giao diện web của bạn)
# Nếu không có CORS, trình duyệt sẽ chặn các yêu cầu từ domain khác đến API.
CORS(app) 

# Danh sách các nguồn tin tức uy tín và URL tìm kiếm của họ
# Mỗi URL có một placeholder '{query}' sẽ được thay thế bằng nội dung tìm kiếm.
# Cấu trúc: "Tên Nguồn": "URL Tìm Kiếm"
RELIABLE_SOURCES = {
    "VnExpress": "https://timkiem.vnexpress.net/?q={query}",
    "Thanh Niên": "https://thanhnien.vn/tim-kiem/?q={query}",
    "Tuổi Trẻ": "https://tuoitre.vn/tim-kiem.html?q={query}",
    "VietnamNet": "https://vietnamnet.vn/tim-kiem/{query}.html"
}

# --- Kết thúc phần Cấu hình API ---


# --- 3. Các hàm hỗ trợ xử lý ngôn ngữ và phân tích liên quan ---

def clean_and_normalize_text(text):
    """
    Hàm này xử lý chuỗi văn bản để chuẩn hóa cho việc so sánh:
    1. Loại bỏ dấu tiếng Việt (ví dụ: "Đà Nẵng" -> "Da Nang").
    2. Chuyển toàn bộ văn bản về chữ thường.
    Điều này giúp tăng cường khả năng khớp từ khóa, ngay cả khi có sự khác biệt về dấu
    hoặc cách viết hoa/thường giữa nội dung tra cứu và bài báo.
    """
    if not isinstance(text, str): # Đảm bảo đầu vào là chuỗi
        return ""
    return unidecode(text).lower()

def check_relevance(title, query_words_normalized):
    """
    Kiểm tra mức độ liên quan của tiêu đề bài viết với các từ khóa tìm kiếm đã được chuẩn hóa.
    Mức độ liên quan được tính bằng số lượng từ khóa khớp.
    Càng nhiều từ khóa khớp, bài viết càng liên quan.
    """
    relevance_score = 0
    title_normalized = clean_and_normalize_text(title)
    
    # Phân tách tiêu đề thành các từ để so sánh
    title_words = title_normalized.split() 
    
    for query_word in query_words_normalized:
        # Kiểm tra nếu từ khóa có trong tiêu đề đã được chuẩn hóa
        if query_word in title_words: # So sánh từng từ khóa
            relevance_score += 1
    return relevance_score

# --- Kết thúc các hàm hỗ trợ ---


# --- 4. Hàm chính thực hiện Web Scraping (lấy dữ liệu từ trang web) ---

def scrape_data(source_name, source_url_template, query_words_normalized, original_query):
    """
    Hàm này thực hiện web scraping trên một URL nguồn cụ thể.
    Nó gửi yêu cầu đến trang tìm kiếm của báo, phân tích HTML và trích xuất thông tin bài viết.
    """
    # Mã hóa chuỗi truy vấn gốc để sử dụng an toàn trong URL
    encoded_query = quote_plus(original_query)
    search_url = source_url_template.format(query=encoded_query)
    
    try:
        # Giả lập một trình duyệt web để tránh bị chặn bởi các trang web
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        
        # Gửi yêu cầu HTTP GET để tải nội dung trang web
        # Thiết lập timeout để tránh treo máy nếu trang web phản hồi chậm
        response = requests.get(search_url, headers=headers, timeout=15) # Tăng timeout lên 15 giây
        response.raise_for_status() # Ném lỗi HTTPError cho các mã trạng thái lỗi (4xx, 5xx)
        
        # Dùng BeautifulSoup để phân tích cú pháp HTML của trang
        soup = BeautifulSoup(response.content, 'html.parser')
        found_articles = []
        
        # --- Logic cụ thể để tìm các bài viết trên từng trang báo ---
        # Mỗi trang báo có cấu trúc HTML khác nhau, cần phải tùy chỉnh selector
        # Các selector này có thể thay đổi theo thời gian nếu trang web cập nhật giao diện.
        
        if source_name == "VnExpress":
            # VnExpress: Bài viết thường nằm trong thẻ <article> với class 'item-news'
            articles_html = soup.find_all('article', class_='item-news')
            for article in articles_html:
                title_tag = article.find('h3', class_='title-news')
                if title_tag and title_tag.a:
                    title = title_tag.a.get_text(strip=True)
                    url = title_tag.a['href']
                    found_articles.append({'title': title, 'url': url})
        
        elif source_name == "Thanh Niên":
            # Thanh Niên: Bài viết thường nằm trong thẻ <article> với class 'story'
            articles_html = soup.find_all('article', class_='story')
            for article in articles_html:
                title_tag = article.find('h2', class_='story__title')
                if title_tag and title_tag.a:
                    title = title_tag.a.get_text(strip=True)
                    url = title_tag.a['href']
                    found_articles.append({'title': title, 'url': url})
        
        elif source_name == "Tuổi Trẻ":
            # Tuổi Trẻ: Bài viết thường nằm trong thẻ <h3> với class 'story__title'
            articles_html = soup.find_all('h3', class_='story__title')
            for article in articles_html:
                title_tag = article.find('a')
                if title_tag:
                    title = title_tag.get_text(strip=True)
                    url = title_tag['href']
                    found_articles.append({'title': title, 'url': url})
        
        elif source_name == "VietnamNet":
            # VietnamNet: Bài viết thường nằm trong thẻ <h3> với class 'title'
            articles_html = soup.find_all('h3', class_='title')
            for article in articles_html:
                title_tag = article.find('a')
                if title_tag:
                    title = title_tag.get_text(strip=True)
                    url = title_tag['href']
                    # VietnamNet đôi khi trả về URL tương đối, cần chuyển thành tuyệt đối
                    if not url.startswith("http"):
                        url = "https://vietnamnet.vn" + url
                    found_articles.append({'title': title, 'url': url})
        
        # Tính điểm liên quan cho từng bài viết tìm được
        articles_with_relevance = []
        for article in found_articles:
            relevance = check_relevance(article['title'], query_words_normalized)
            if relevance > 0: # Chỉ thêm bài viết nếu có ít nhất 1 từ khóa khớp
                articles_with_relevance.append({**article, 'relevance_score': relevance})
        
        return articles_with_relevance
    
    except requests.exceptions.RequestException as e:
        # In lỗi kết nối ra console để gỡ lỗi trên Render
        print(f"Lỗi kết nối khi scraping {source_name} ({search_url}): {e}")
        return []
    except Exception as e:
        # Xử lý các lỗi khác trong quá trình scraping
        print(f"Lỗi không xác định khi scraping {source_name} ({search_url}): {e}")
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
        # Lấy dữ liệu JSON từ phần thân của yêu cầu POST
        data = request.get_json()
        original_query = data.get('query', '')
        
        # Kiểm tra nếu không có nội dung tìm kiếm được cung cấp
        if not original_query:
            return jsonify({
                "message": "Vui lòng cung cấp nội dung tra cứu.",
                "is_reliable": False,
                "matched_sources": [],
                "matching_articles_count": 0
            }), 400 # Trả về lỗi 400 Bad Request

        # Chuẩn hóa các từ khóa tìm kiếm từ nội dung gốc
        query_words_normalized = [clean_and_normalize_text(word) for word in original_query.split()]
        
        all_found_articles = [] # Danh sách tổng hợp tất cả các bài viết tìm được từ mọi nguồn
        
        # Vòng lặp qua từng nguồn uy tín để scrape dữ liệu
        for source_name, source_url_template in RELIABLE_SOURCES.items():
            articles_from_source = scrape_data(source_name, source_url_template, query_words_normalized, original_query)
            if articles_from_source:
                all_found_articles.extend(articles_from_source) # Thêm các bài viết tìm được vào danh sách tổng

        # Sắp xếp tất cả các bài viết tìm được theo điểm liên quan giảm dần
        all_found_articles.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        # Lọc ra các nguồn duy nhất đã tìm thấy bài viết
        unique_sources_found = set(article['name'] for article in all_found_articles)

        # Phân tích kết quả và trả về phản hồi JSON chi tiết hơn
        if all_found_articles:
            return jsonify({
                "message": f"Tìm thấy {len(all_found_articles)} bài viết liên quan trên {len(unique_sources_found)} nguồn đáng tin cậy.",
                "is_reliable": True, # Kết luận là tin cậy vì tìm thấy trên nguồn uy tín
                "matched_sources": all_found_articles,
                "matching_articles_count": len(all_found_articles)
            })
        else:
            # Nếu không tìm thấy bài viết nào trên các nguồn uy tín
            return jsonify({
                "message": "Không tìm thấy nội dung liên quan trên các nguồn đáng tin cậy.",
                "is_reliable": False, # Kết luận là không đáng tin cậy (hoặc không xác định)
                "matched_sources": [],
                "matching_articles_count": 0
            })
    
    except Exception as e:
        # Xử lý các lỗi ngoại lệ không mong muốn xảy ra ở cấp độ API
        print(f"Lỗi không xác định ở điểm cuối API: {e}")
        return jsonify({
            "message": f"Có lỗi xảy ra ở máy chủ: {str(e)}",
            "is_reliable": None, # Dùng None để chỉ ra trạng thái lỗi
            "matched_sources": [],
            "matching_articles_count": 0
        }), 500 # Trả về lỗi 500 Internal Server Error

# --- Kết thúc phần Điểm cuối API (Endpoint) ---


# --- 6. Khởi chạy ứng dụng Flask ---

if __name__ == '__main__':
    # Lấy cổng từ biến môi trường PORT (Render sẽ cung cấp biến này)
    # Nếu không có, mặc định sử dụng cổng 5000 cho môi trường phát triển cục bộ
    port = int(os.environ.get('PORT', 5000))
    
    # Chạy ứng dụng Flask
    # host='0.0.0.0' cho phép ứng dụng chấp nhận kết nối từ bên ngoài (cần cho Render)
    # debug=True bật chế độ gỡ lỗi (chỉ dùng khi phát triển)
    app.run(host='0.0.0.0', debug=True, port=port)

# --- Kết thúc phần Khởi chạy ứng dụng ---
