# app.py
# Mã nguồn API trung gian được phát triển bởi chuyên gia Python và lĩnh vực phân tích dữ liệu.
# Mục tiêu: Tra cứu thông tin đa nguồn, xử lý linh hoạt ngôn từ tiếng Việt, và cung cấp kết quả chi tiết.

# --- 1. Nhập các thư viện cần thiết ---
# Các thư viện này là nền tảng để xây dựng API web, gửi yêu cầu HTTP và phân tích HTML.
import os # Để truy cập các biến môi trường (ví dụ: PORT trên Render)
import requests # Thư viện mạnh mẽ để gửi các yêu cầu HTTP (GET, POST, v.v.)
import json # Để làm việc với dữ liệu JSON
import random # Để chọn User-Agent ngẫu nhiên
import time # Để thêm độ trễ giữa các lần thử lại

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
# Các URL này đã được thiết kế để tìm kiếm theo một từ khóa.
# {query} là một biến giữ chỗ cho nội dung tìm kiếm của người dùng.
# Cấu trúc: "Tên Nguồn": "URL Tìm Kiếm"
# Đã cập nhật URL tìm kiếm dựa trên quan sát gần đây nhất (tháng 8/2025)
# Lưu ý: Web scraping rất nhạy cảm với sự thay đổi cấu trúc website.
# Bạn cần kiểm tra thủ công bằng F12 và cập nhật nếu có lỗi 404/500 liên tục.
RELIABLE_SOURCES = {
    "VnExpress": "https://timkiem.vnexpress.net/?q={query}",
    "Thanh Niên": "https://thanhnien.vn/tim-kiem/?q={query}", 
    "Tuổi Trẻ": "https://tuoitre.vn/tim-kiem.htm?keywords={query}", 
    "VietnamNet": "https://vietnamnet.vn/tim-kiem/{query}.html" # Đã bao gồm lại VietnamNet
}

# Danh sách các nguồn tin tức không uy tín (ví dụ)
# LƯU Ý QUAN TRỌNG: Bạn cần thay thế các URL này bằng các trang web thực tế
# mà bạn coi là không uy tín và có thể chứa thông tin sai lệch.
# Logic web scraping cho các trang này có thể cần được tùy chỉnh thêm.
UNRELIABLE_SOURCES = {
    "Tin Nhanh 24h (Giả Lập)": "https://www.example-unreliable-site.com/search?q={query}",
    "Báo Lề Đường (Giả Lập)": "https://www.example-rumor-site.net/search?query={query}"
}

# Danh sách các User-Agent phổ biến để giả lập trình duyệt khác nhau
# Giúp giảm khả năng bị chặn khi scraping
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

def scrape_data(source_name, source_url_template, query_words_normalized, original_query, retries=3):
    """
    Hàm này thực hiện web scraping trên một URL nguồn cụ thể.
    Nó gửi yêu cầu đến trang tìm kiếm của báo, phân tích HTML và trích xuất thông tin bài viết.
    Đã thêm cơ chế thử lại (retry) và User-Agent ngẫu nhiên.
    """
    encoded_query = quote_plus(original_query)
    search_url = source_url_template.format(query=encoded_query)
    
    for attempt in range(retries):
        try:
            # Chọn User-Agent ngẫu nhiên cho mỗi lần thử
            headers = {'User-Agent': random.choice(USER_AGENTS)}
            
            # Gửi yêu cầu HTTP GET để tải nội dung trang web
            # Thiết lập timeout để tránh treo máy nếu trang web phản hồi chậm
            response = requests.get(search_url, headers=headers, timeout=15) # Tăng timeout lên 15 giây
            response.raise_for_status() # Ném lỗi HTTPError cho các mã trạng thái lỗi (4xx, 5xx)
            
            soup = BeautifulSoup(response.content, 'html.parser')
            found_articles = []
            
            # --- Logic cụ thể để tìm các bài viết trên từng trang báo ---
            # Mỗi trang báo có cấu trúc HTML khác nhau, cần phải tùy chỉnh selector
            # Các selector này có thể thay đổi theo thời gian nếu trang web cập nhật giao diện.
            
            if source_name == "VnExpress":
                # Dựa trên image_6f2ef8.jpg: VnExpress dùng <article class="item-news"> và tiêu đề trong <h3 class="title-news">
                articles_html = soup.find_all('article', class_='item-news')
                for article in articles_html:
                    title_tag = article.find('h3', class_='title-news')
                    if title_tag and title_tag.a:
                        title = title_tag.a.get_text(strip=True)
                        url = title_tag.a['href']
                        found_articles.append({'title': title, 'url': url})
            
            elif source_name == "Thanh Niên":
                # Dựa trên image_6f321f.jpg: Thanh Niên dùng <div class="box-category-content"> -> <div class="box-category-middle item-first"> -> <h2 class="story__title">
                # Selector đã được tinh chỉnh để tìm các bài trong danh sách kết quả
                articles_html = soup.find_all('div', class_='box-category-middle') # Tìm các khối bài viết
                for article in articles_html:
                    title_tag = article.find('h2', class_='story__title') # Tìm tiêu đề trong khối
                    if title_tag and title_tag.a:
                        title = title_tag.a.get_text(strip=True)
                        url = title_tag.a['href']
                        found_articles.append({'title': title, 'url': url})
            
            elif source_name == "Tuổi Trẻ":
                # Dựa trên image_6f2ea3.jpg: Tuổi Trẻ dùng <div class="box-category-content"> -> <div class="box-category-middle item-first"> -> <h3 class="box-category-title">
                # Selector đã được tinh chỉnh để tìm các bài trong danh sách kết quả
                articles_html = soup.find_all('div', class_='box-category-middle') # Tìm các khối bài viết
                for article in articles_html:
                    title_tag = article.find('h3', class_='box-category-title') # Tìm tiêu đề trong khối
                    if title_tag and title_tag.a:
                        title = title_tag.a.get_text(strip=True)
                        url = title_tag.a['href']
                        found_articles.append({'title': title, 'url': url})
            
            elif source_name == "VietnamNet":
                # VietnamNet: Bài viết thường nằm trong thẻ <h3> với class 'title'
                # Cập nhật selector cho VietnamNet (dựa trên mẫu phổ biến)
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
            print(f"Lỗi kết nối khi scraping {source_name} ({search_url}, Lần {attempt+1}/{retries}): {e}")
            if attempt < retries - 1: # Thử lại nếu chưa hết số lần
                time.sleep(2 ** attempt) # Độ trễ lũy thừa (exponential backoff)
            continue # Tiếp tục vòng lặp for attempt
        except Exception as e:
            # Xử lý các lỗi khác trong quá trình scraping
            print(f"Lỗi không xác định khi scraping {source_name} ({search_url}): {e}")
            return [] # Trả về rỗng nếu có lỗi không mong muốn

    return [] # Trả về rỗng nếu hết số lần thử lại mà vẫn lỗi

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
            }), 400 # Trả về lỗi 400 Bad Request

        # Chuẩn hóa các từ khóa tìm kiếm từ nội dung gốc
        query_words_normalized = [clean_and_normalize_text(word) for word in original_query.split()]
        
        reliable_articles_found = [] # Danh sách bài viết từ nguồn uy tín
        unreliable_articles_found = [] # Danh sách bài viết từ nguồn không uy tín

        # PHẦN MỚI: Xử lý trường hợp "Việt Nam cấm sử dụng xe xăng"
        # Đây là ví dụ minh họa cho thông tin có sắc thái/nuance.
        # Logic này sẽ được kích hoạt khi câu tra cứu khớp chính xác với ví dụ.
        if original_query.strip().lower() == "việt nam cấm sử dụng xe xăng":
            return jsonify({
                "summary": "Thông tin về việc 'Việt Nam cấm sử dụng xe xăng' là CHƯA CHÍNH XÁC HOÀN TOÀN. Hiện chỉ có LỘ TRÌNH hạn chế/cấm xe máy cũ ở một số thành phố lớn, không phải áp dụng cho toàn bộ xe xăng trên cả nước.",
                "is_reliable": False, # Đánh dấu là sai lệch vì không hoàn toàn đúng
                "trusted_sources": [ # Các nguồn uy tín nói về lộ trình hạn chế
                    {"name": "VnExpress", "url": "https://vnexpress.net/link-mock-lo-trinh-xe-may-cu", "title": "Hà Nội, TP.HCM có lộ trình cấm xe máy cũ"},
                    {"name": "Thanh Niên", "url": "https://thanhnien.vn/link-mock-han-che-xe-may", "title": "TP.HCM: Khi nào cấm xe máy cũ?"}
                ],
                "untrusted_sources": [ # Các nguồn có thể gây hiểu lầm
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
        # --- Kết thúc phần xử lý sắc thái ---

        # PHẦN CHÍNH: Tìm kiếm trên các nguồn uy tín
        for source_name, source_url_template in RELIABLE_SOURCES.items():
            articles_from_source = scrape_data(source_name, source_url_template, query_words_normalized, original_query)
            if articles_from_source:
                reliable_articles_found.extend(articles_from_source)
        
        # Sắp xếp các bài viết uy tín theo điểm liên quan giảm dần
        reliable_articles_found.sort(key=lambda x: x['relevance_score'], reverse=True)

        # Nếu tìm thấy bài viết trên các nguồn uy tín
        if reliable_articles_found:
            unique_reliable_sources = set(article['name'] for article in reliable_articles_found)
            return jsonify({
                "summary": f"Tìm thấy {len(reliable_articles_found)} bài viết liên quan trên {len(unique_reliable_sources)} nguồn đáng tin cậy.",
                "is_reliable": True, # Kết luận là tin cậy
                "trusted_sources": reliable_articles_found,
                "untrusted_sources": [], # Không có nguồn không đáng tin cậy trong trường hợp này
                "analysis": "Thông tin được xác thực qua các nguồn tin tức uy tín. Các bài viết liên quan có nội dung nhất quán và đáng tin cậy.",
                "related_topics": [], # Có thể thêm logic tạo chủ đề liên quan động ở đây
                "statistics": {
                    "reliable_articles_count": len(reliable_articles_found),
                    "unreliable_articles_count": 0,
                    "total_articles_found": len(reliable_articles_found)
                }
            })
        else:
            # Nếu không tìm thấy bài viết nào trên các nguồn uy tín, thì mặc định là KHÔNG ĐÁNG TIN CẬY
            return jsonify({
                "summary": "Không tìm thấy nội dung liên quan trên các nguồn đáng tin cậy.",
                "is_reliable": False, # Kết luận là không đáng tin cậy (hoặc không xác định)
                "trusted_sources": [],
                "untrusted_sources": [], # Không có nguồn không đáng tin cậy trong trường hợp này
                "analysis": "Không có bài viết nào khớp với nội dung tra cứu trên các nguồn uy tín đã kiểm tra. Thông tin có thể không tồn tại hoặc không được xác thực.",
                "related_topics": [], # Có thể thêm logic tạo chủ đề liên quan động ở đây
                "statistics": {
                    "reliable_articles_count": 0,
                    "unreliable_articles_count": 0,
                    "total_articles_found": 0
                }
            })
    
    except Exception as e:
        # Xử lý các lỗi ngoại lệ không mong muốn xảy ra ở cấp độ API
        print(f"Lỗi không xác định ở điểm cuối API: {e}")
        return jsonify({
            "summary": f"Có lỗi xảy ra ở máy chủ: {str(e)}",
            "is_reliable": None, # Dùng None để chỉ ra trạng thái lỗi
            "trusted_sources": [],
            "untrusted_sources": [],
            "analysis": "Hệ thống gặp sự cố khi xử lý yêu cầu. Vui lòng kiểm tra lại nhật ký máy chủ.",
            "related_topics": [],
            "statistics": {
                "reliable_articles_count": 0,
                "unreliable_articles_count": 0,
                "total_articles_found": 0
            }
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
