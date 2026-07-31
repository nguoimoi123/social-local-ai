# Social AI Planner

Ứng dụng local để lập kế hoạch nội dung Facebook/Instagram bằng model mã nguồn mở qua Ollama.

## Chức năng

- Nhập sản phẩm, thương hiệu, khách hàng mục tiêu.
- Upload ảnh thật từ máy.
- AI phân tích ảnh đã upload.
- AI tự search nội dung công khai để lấy insight chung.
- Lọc kết quả search rác, đọc nội dung trang công khai khi truy cập được và dùng sample thay vì chỉ title/snippet.
- Viết bài đăng/caption hoàn chỉnh bằng cách kết hợp search nội dung công khai và ngữ cảnh ảnh đã upload.
- AI đề xuất thêm từ khóa search theo sản phẩm, khách hàng mục tiêu và nền tảng.
- Chọn nguồn search: DuckDuckGo mặc định hoặc Google Programmable Search API.
- Tạo kế hoạch đăng bài 7 ngày.
- Xem bảng tổng quan kế hoạch theo máy nội dung, vai trò, hook và KPI.
- Duyệt và lưu bài vào lịch nội dung.
- Chỉnh lại bài đã duyệt.
- Đăng ngay bài chữ, một ảnh hoặc nhiều ảnh lên Facebook Page qua Meta Graph API.
- Xuất lịch dạng CSV, JSON hoặc Markdown.

Ứng dụng không tạo ảnh hoặc video. Tính năng Facebook hiện hỗ trợ đăng ngay;
chưa có bộ lập lịch chạy nền khi máy tắt.

## Chạy app

```bash
cd /Users/cps/Documents/social-ai-chatbot
source .venv/bin/activate
streamlit run app.py --server.port 8501
```

Mở:

```text
http://localhost:8501
```

## Kết nối Facebook Page

Sao chép `.streamlit/secrets.toml.example` thành `.streamlit/secrets.toml`,
sau đó điền:

```toml
FACEBOOK_PAGE_ID = "your_page_id"
FACEBOOK_PAGE_ACCESS_TOKEN = "your_page_access_token"
FACEBOOK_GRAPH_API_VERSION = "v25.0"
```

Page Access Token cần quyền `pages_manage_posts`. File `secrets.toml` đã được
gitignore và không được commit lên Git.

## Model cần có trong Ollama

```bash
ollama pull qwen2.5:3b
ollama pull qwen2.5vl:3b
```

`qwen2.5:3b` dùng để viết caption/kế hoạch.  
`qwen2.5vl:3b` dùng để phân tích ảnh upload.

## Google Search chính thức

App hỗ trợ Google Programmable Search API nếu bạn có:

- Google API key
- Search Engine ID (`cx`)

Khi chưa có hai thông tin này, dùng DuckDuckGo trước. Không nên dùng thư viện scrape Google trực tiếp vì dễ bị chặn captcha và không ổn định.

## Dữ liệu local

- `uploads/`: ảnh người dùng upload được lưu local.
- `data/saved_posts.json`: lịch nội dung đã duyệt.
