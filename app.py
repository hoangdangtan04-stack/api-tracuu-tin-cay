# app.py
# Dòng đầu tiên này là một chú thích, không phải mã code
# Nó giúp bạn nhớ tên file này là gì.

# Nhập các thư viện cần thiết để chạy API
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup

# --- Bắt đầu phần Cấu hình API ---

# Tạo một ứng dụng Flask. Đây là "trái tim" của API của chúng ta.
app = Flask(__name__)
# Cho phép các yêu cầu từ các domain khác truy cập API.
CORS(app)

# Danh sách các nguồn tin tức uy tín và URL tìm kiếm của họ
# Các URL này đã được thiết kế để tìm kiếm theo một từ khóa.
# {query} là một biến giữ chỗ cho nội dung tìm kiếm của người dùng.
RELIABLE_SOURCES = {
    "VnExpress": "https://timkiem.vnexpress.net/?q={query}",
    "Thanh Niên": "https://thanhnien.vn/tim-kiem/?q={query}",
    # Bạn có thể thêm các nguồn khác vào đây
    # Ví dụ: "Tuoi Tre": "https://tuoitre.vn/tim-kiem.html?q={query}"
}

# --- Kết thúc phần Cấu hình API ---


# --- Bắt đầu phần Logic xử lý Web Scraping ---

# Hàm này thực hiện web scraping (lấy dữ liệu từ trang web)
def scrape_data(source_url, query):
    """
    Hàm này thực hiện web scraping trên một URL nguồn cụ thể.
    Nó tìm kiếm các bài viết liên quan đến query và trích xuất tiêu đề, URL.
    """
    # Tạo URL tìm kiếm hoàn chỉnh bằng cách thay thế {query}
    search_url = source_url.format(query=query)
    
    try:
        # Giả lập một trình duyệt web để tránh bị chặn bởi trang web
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        # Gửi yêu cầu HTTP GET để tải trang web
        response = requests.get(search_url, headers=headers, timeout=10)
        
        # Kiểm tra nếu yêu cầu thành công (HTTP status code 200)
        if response.status_code == 200:
            # Dùng BeautifulSoup để phân tích cú pháp HTML của trang
            soup = BeautifulSoup(response.content, 'html.parser')
            matched_articles = []
            
            # --- Logic cụ thể cho từng trang báo ---
            # Đây là phần quan trọng nhất, nơi chúng ta "nói" với code
            # cách tìm kiếm các bài viết trên từng trang web
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
            
            return matched_articles
            
        return []
    except requests.exceptions.RequestException:
        # Trả về mảng rỗng nếu có lỗi kết nối
        return []

# --- Kết thúc phần Logic xử lý Web Scraping ---


# --- Bắt đầu phần Điểm cuối API (Endpoint) ---

# Đây là URL mà n8n sẽ gọi để kích hoạt API của chúng ta.
# Nó chấp nhận phương thức POST để nhận dữ liệu.
@app.route('/search', methods=['POST'])
def check_trustworthiness():
    """
    Điểm cuối API này nhận nội dung tìm kiếm từ n8n,
    gọi hàm scraping và trả về kết quả phân tích.
    """
    try:
        # Lấy dữ liệu JSON từ phần thân của yêu cầu POST
        data = request.get_json()
        query = data.get('query', '')
        
        # Kiểm tra nếu không có nội dung tìm kiếm
        if not query:
            return jsonify({
                "message": "Không tìm thấy nội dung tra cứu.",
                "is_reliable": False,
                "matched_sources": [],
                "matching_articles_count": 0
            }), 400

        # Vòng lặp qua các nguồn uy tín đã định nghĩa
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

        # Phân tích kết quả và trả về phản hồi JSON
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
        # Xử lý các lỗi ngoại lệ và trả về phản hồi lỗi
        return jsonify({
            "message": f"Có lỗi xảy ra: {str(e)}",
            "is_reliable": None,
            "matched_sources": [],
            "matching_articles_count": 0
        }), 500

# --- Kết thúc phần Điểm cuối API (Endpoint) ---


# --- Bắt đầu phần Khởi chạy ứng dụng ---

# Dòng này đảm bảo ứng dụng chỉ chạy khi file được thực thi trực tiếp
if __name__ == '__main__':
    # Chạy ứng dụng trên máy tính của bạn, ở cổng 5000
    app.run(debug=True, port=5000)

# --- Kết thúc phần Khởi chạy ứng dụng ---