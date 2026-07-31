# Social AI Planner

Trợ lý lập kế hoạch và vận hành nội dung mạng xã hội chạy hoàn toàn trên máy cá nhân. Ứng dụng kết hợp **Streamlit**, **Ollama** và dữ liệu công khai trên web để hỗ trợ đội marketing tạo caption, xây lịch nội dung, quản lý bài đã duyệt và đăng bài lên Facebook Page.

> Dữ liệu, ảnh và lịch nội dung được lưu cục bộ. Bạn chủ động model AI, tài khoản và thông tin kết nối API.

## Tính năng nổi bật

### Tạo nội dung bằng AI

- Nhập sản phẩm, thương hiệu, khách hàng mục tiêu và mục tiêu chiến dịch.
- Tạo caption theo giọng thương hiệu và độ dài mong muốn.
- Phân tích ảnh sản phẩm bằng vision model.
- Gợi ý hình ảnh, hook, CTA, hashtag và kịch bản Reels.
- Tạo kế hoạch nội dung 7 ngày theo trụ cột, vai trò bài và KPI.
- Cung cấp 24 “máy tạo nội dung” dành cho marketing B2B và ngành điện công nghiệp.

### Nghiên cứu nội dung công khai

- Tìm kiếm bằng DuckDuckGo mà không cần API key.
- Hỗ trợ Google Programmable Search API.
- Đề xuất thêm từ khóa theo sản phẩm và khách hàng mục tiêu.
- Lọc nguồn kém liên quan và đọc nội dung trang công khai khi truy cập được.
- Chỉ dùng kết quả tìm kiếm làm nguyên liệu tham khảo, không sao chép nguyên văn.

### Quản lý và xuất bản

- Duyệt, lưu và chỉnh sửa bài trong lịch nội dung.
- Gắn một hoặc nhiều ảnh vào từng bài.
- Xuất lịch dưới dạng CSV, JSON hoặc Markdown.
- Theo dõi like, comment, share, inbox và lượt xem.
- Đăng ngay bài chữ, một ảnh hoặc album ảnh lên Facebook Page qua Meta Graph API.

Ứng dụng **không tạo ảnh hoặc video** và chưa có tiến trình chạy nền để tự đăng bài khi máy đã tắt.

## Yêu cầu hệ thống

- Python 3.10 trở lên
- [Ollama](https://ollama.com/) đang chạy trên máy
- RAM tối thiểu 8 GB; nên có 16 GB nếu sử dụng đồng thời model văn bản và vision
- Kết nối Internet nếu dùng tìm kiếm web hoặc đăng Facebook

## Cài đặt

### 1. Tải mã nguồn

```bash
git clone https://github.com/nguoimoi123/social-local-ai.git
cd social-local-ai
```

### 2. Tạo môi trường Python

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

macOS hoặc Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Cài model Ollama

```bash
ollama pull qwen3:4b
ollama pull qwen2.5vl:3b
ollama pull qwen2.5:3b
```

| Model | Vai trò |
| --- | --- |
| `qwen3:4b` | Viết caption, lập kế hoạch và xử lý brief |
| `qwen2.5vl:3b` | Phân tích hình ảnh |
| `qwen2.5:3b` | Model viết dự phòng, nhẹ hơn |

Bạn có thể kiểm tra model đã cài bằng:

```bash
ollama list
```

### 4. Chạy ứng dụng

```bash
streamlit run app.py --server.port 8501
```

Mở [http://localhost:8501](http://localhost:8501) trong trình duyệt.

## Cách sử dụng nhanh

1. Mở tab **Tạo nội dung** và nhập thông tin sản phẩm.
2. Điền khách hàng mục tiêu, thông số bắt buộc và bằng chứng được phép dùng.
3. Chọn mục tiêu, giọng thương hiệu, nhịp đăng và máy tạo nội dung.
4. Upload ảnh thật nếu muốn AI phân tích sản phẩm.
5. Chọn **Tạo nội dung & gợi ý ảnh** hoặc **Tạo kế hoạch tuần**.
6. Kiểm tra lại thông số, chỉnh sửa và duyệt những bài phù hợp.
7. Mở **Lịch đã duyệt** để xuất file, đăng Facebook hoặc nhập số liệu hiệu quả.

AI có thể tạo nội dung không chính xác. Luôn kiểm tra lại mã sản phẩm, thông số kỹ thuật, giá, chính sách và các tuyên bố trước khi đăng.

## Kết nối Facebook Page

Sao chép file cấu hình mẫu:

Windows PowerShell:

```powershell
Copy-Item .streamlit\secrets.toml.example .streamlit\secrets.toml
```

macOS hoặc Linux:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Điền thông tin thật vào `.streamlit/secrets.toml`:

```toml
FACEBOOK_PAGE_ID = "your_page_id"
FACEBOOK_PAGE_ACCESS_TOKEN = "your_page_access_token"
FACEBOOK_GRAPH_API_VERSION = "v25.0"
```

Page Access Token cần quyền phù hợp để quản lý và đăng bài, trong đó có `pages_manage_posts`. Hãy cấu hình ứng dụng Meta và quyền truy cập Page theo chính sách hiện hành của Meta.

Không commit `.streamlit/secrets.toml`. File này đã được khai báo trong `.gitignore`.

## Tùy chọn tìm kiếm

### DuckDuckGo

Đây là lựa chọn mặc định, không cần cấu hình API. Phù hợp để thử nghiệm hoặc nghiên cứu nhanh.

### Google Programmable Search

Chọn Google trong giao diện và nhập:

- Google API key
- Search Engine ID (`cx`)

Thông tin này chỉ được dùng cho phiên làm việc hiện tại. Không đưa API key vào mã nguồn hoặc commit lên Git.

## Dữ liệu cục bộ

| Đường dẫn | Nội dung |
| --- | --- |
| `uploads/` | Ảnh người dùng upload |
| `data/saved_posts.json` | Bài viết và lịch nội dung đã duyệt |
| `.streamlit/secrets.toml` | Thông tin kết nối Facebook |

Các đường dẫn trên được bỏ qua bởi Git để tránh đưa dữ liệu cá nhân và thông tin nhạy cảm lên repository.

## Cấu trúc dự án

```text
social-local-ai/
├── .streamlit/
│   └── secrets.toml.example
├── app.py
├── requirements.txt
├── TODO_PRODUCT_PRIORITIES.md
└── README.md
```

## Xử lý lỗi thường gặp

### Không kết nối được Ollama

Kiểm tra Ollama đang chạy và model đã tồn tại:

```bash
ollama list
```

Nếu thiếu model, chạy lại các lệnh `ollama pull` trong phần cài đặt.

### PowerShell không cho kích hoạt môi trường

Chạy lệnh sau trong cửa sổ PowerShell hiện tại rồi kích hoạt lại:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Không đăng được Facebook

Kiểm tra:

- Page ID có đúng không.
- Access Token còn hiệu lực không.
- Token có thuộc đúng Page không.
- Ứng dụng Meta đã được cấp đủ quyền đăng bài chưa.
- Phiên bản Graph API trong cấu hình còn được hỗ trợ không.

## Bảo mật

- Không commit access token, API key hoặc dữ liệu khách hàng.
- Không dùng dữ liệu tìm kiếm công khai như một nguồn xác thực tuyệt đối.
- Không đăng nội dung AI tạo ra khi chưa có người kiểm duyệt.
- Nên sao lưu `data/saved_posts.json` nếu lịch nội dung có giá trị.
