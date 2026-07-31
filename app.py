import csv
import hashlib
import html
import io
import json
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import ollama
import requests
import streamlit as st
from bs4 import BeautifulSoup
from ddgs import DDGS
from PIL import Image, ImageOps


APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
UPLOAD_DIR = APP_DIR / "uploads"
SAVED_POSTS_FILE = DATA_DIR / "saved_posts.json"

DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

TEXT_MODEL = "qwen3:4b"
VISION_MODEL = "qwen2.5vl:3b"
WRITING_MODELS = ["qwen3:4b", "qwen2.5:3b"]
PLANNING_CONTEXT_TOKENS = 8192
WEEK_PLAN_MAX_TOKENS = 4200
CAPTION_MAX_TOKENS = 3200
VISION_CONTEXT_TOKENS = 4096
VISION_RETRY_CONTEXT_TOKENS = 8192
VISION_MAX_IMAGE_SIDE = 768
VISION_JPEG_QUALITY = 85
# None lets long local model generations finish instead of falling back early.
OLLAMA_TIMEOUT_SECONDS = None
GOOGLE_CUSTOM_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"
FACEBOOK_GRAPH_API_DEFAULT_VERSION = "v25.0"
PAGE_FETCH_LIMIT = 4
PAGE_TEXT_LIMIT = 1600
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "vi,en;q=0.8",
}
SOCIAL_DOMAINS = {"facebook.com", "instagram.com", "tiktok.com", "threads.net"}
POSITIVE_STYLE_TERMS = {
    "inbox",
    "ib",
    "san hang",
    "chot",
    "feedback",
    "review",
    "size",
    "outfit",
    "sale",
    "uu dai",
    "dat hang",
    "comment",
    "tu van",
}
NEGATIVE_RESEARCH_TERMS = {
    "code",
    "sourcecode",
    "do an",
    "file bao cao",
    "ban buon",
    "ban si",
    "can si",
    "nguon hang",
    "tong kho",
    "wholesale",
    "nha cung cap",
    "tuyen dung",
    "viec lam",
    "wiki",
    "download",
    "cho tot",
    "chotot",
    "website analysis",
    "seowebstat",
    "taobao",
}
NEGATIVE_DOMAINS = {"chotot.com", "github.com", "stackoverflow.com", "wikipedia.org"}

MASTER_ELECTRIC_INDUSTRIAL_CONTEXT_TERMS = [
    "tu dien",
    "dien cong nghiep",
    "thiet bi tu dien",
    "tu dieu khien",
    "tu phan phoi",
    "nha may",
    "nha xuong",
    "ky thuat bao tri",
    "nha thau m&e",
    "switchboard",
    "electrical panel",
    "control cabinet",
    "electrical enclosure",
    "industrial electrical",
]

MASTER_ELECTRIC_PRODUCT_TERMS = [
    "quat tu dien",
    "quat hut",
    "filter",
    "luoi loc",
    "bo on nhiet",
    "thermostat",
    "bien dong",
    "current transformer",
    "dong ho dien",
    "tu bu",
    "bo dieu khien tu bu",
    "cuon khang",
    "may bien ap",
    "busbar",
    "su do thanh cai",
    "cau chi",
    "mcb",
    "rcbo",
    "mccb",
    "contactor",
    "relay",
    "timer",
    "den bao",
    "nut nhan",
    "cong tac xoay",
    "dien tro suoi",
    "gen co nhiet",
]

MASTER_ELECTRIC_CONSUMER_NEGATIVE_TERMS = [
    "gia dung",
    "dan dung",
    "phong ngu",
    "nha bep",
    "do choi",
    "o to",
    "xe may",
    "dong ho deo tay",
    "quat cay",
    "quat ban",
    "quat tich dien",
    "quat sac",
    "quat mini",
    "pin sac",
    "cong tac thong minh gia dinh",
]

PROFILE_QUERY_CONTEXT = {
    "fan": "tủ điện công nghiệp",
    "capacitor": "tủ tụ bù công nghiệp",
    "reactor": "hệ thống điện công nghiệp",
    "protection": "tủ điện công nghiệp",
    "meter": "đo lường điện công nghiệp",
    "power_quality_meter": "phân tích chất lượng điện năng nhà máy",
    "thermal_control": "tủ điện công nghiệp",
    "control": "tủ điều khiển công nghiệp",
    "busbar": "tủ điện busbar",
    "transformer": "điện công nghiệp",
    "catalog": "phụ kiện tủ điện công nghiệp",
    "generic": "thiết bị điện công nghiệp",
}

PROFILE_QUERY_NEGATIVES = {
    "fan": ["gia dụng", "phòng ngủ", "quạt cây", "quạt bàn", "tích điện", "pin", "sạc", "mini"],
    "meter": ["đồng hồ đeo tay", "smartwatch", "đồng hồ thể thao", "đồng hồ ô tô", "đồng hồ xe máy"],
    "power_quality_meter": ["đồng hồ đeo tay", "smartwatch", "đồng hồ thể thao", "đồng hồ ô tô", "đồng hồ xe máy"],
    "control": ["gia đình", "đồ chơi", "ô tô", "xe máy"],
    "transformer": ["đồ chơi", "âm thanh", "sạc điện thoại"],
    "generic": ["gia dụng", "dân dụng", "đồ chơi", "ô tô", "xe máy"],
}

B2B_ELECTRICAL_PLAYBOOK = """
Định vị tool: không chỉ viết caption, mà hỗ trợ vận hành nội dung bán hàng ngành điện công nghiệp.
Insight tham khảo từ page cùng ngành:
- Page đăng khá đều trong ngắn hạn, ước tính 2-4 bài/tuần, thiên về B2B + tư vấn kỹ thuật + giới thiệu giải pháp.
- Bài ảnh/caption dài có tính chuyên môn nhưng khó viral rộng; Reels/video ngắn có cơ hội kéo reach tốt hơn.
- Nội dung hiệu quả hơn khi đi theo công thức: vấn đề -> hậu quả -> giải pháp -> thông số/bằng chứng -> CTA inbox tư vấn.
- Không hứa "lên xu hướng"; mục tiêu thực tế là đăng đều, đúng tệp, tăng chia sẻ trong ngành và tạo lead/inbox.
- Với fanpage công ty mới/ít follower, ưu tiên đa dạng content: 60% giá trị kỹ thuật, 25% bán hàng mềm, 15% thương hiệu/hậu trường/tăng follow.
- Mỗi tuần nên có ít nhất 1 bài cho người chưa mua: giới thiệu năng lực, kho hàng, quy trình tư vấn, lý do nên theo dõi page.
""".strip()

CONTENT_PILLARS = [
    "Tăng nhận diện thương hiệu công ty",
    "Bán hàng theo mã sản phẩm",
    "Tư vấn lỗi thường gặp",
    "Giải pháp theo hệ thống",
    "Checklist chọn/lắp đúng",
    "Reels/video ngắn kéo reach",
    "Nuôi follow bằng kiến thức dễ lưu",
    "Hậu trường/kho hàng/quy trình tư vấn",
]

CONTENT_MACHINES = {
    "Sự cố & bài học an toàn": "Nguồn: cháy nổ, tai nạn điện, tủ quá nhiệt. Góc viết: từ sự cố này doanh nghiệp nên kiểm tra gì. Gắn sản phẩm: quạt lọc, tụ bù chống cháy nổ, cuộn kháng, MCCB, relay bảo vệ.",
    "Tin tức ngành điện": "Nguồn: EVN, báo công nghiệp, điện lực, năng lượng. Góc viết: giá điện, tiết kiệm điện, phụ tải tăng, ổn định hệ thống. Gắn sản phẩm: tụ bù, đồng hồ đo, giám sát điện.",
    "Bài báo/cộng đồng nhắc đến sản phẩm": "Nguồn: khách hàng, hội nhóm kỹ thuật, nhà cung cấp, website đối tác. Góc viết: cảm ơn/ghi nhận, nhắc lại ưu điểm và CTA tư vấn.",
    "Case study khách hàng": "Nguồn: ảnh công trình, feedback, đơn hàng, video lắp đặt. Góc viết: tình huống sử dụng, thông số, kết quả sau lắp.",
    "So sánh trước/sau": "Nguồn: ảnh tủ cũ/mới, vệ sinh, thay thiết bị. Góc viết: dấu hiệu trước khi thay và lợi ích sau khi xử lý.",
    "Checklist kỹ thuật": "Ví dụ: dấu hiệu tụ bù hỏng, lý do tủ nóng, khi nào cần cuộn kháng, cách chọn quạt lọc tủ điện.",
    "Giải thích thuật ngữ đơn giản": "Chủ đề: kVAr, cos phi, sóng hài, CT, IP rating, MCCB, contactor. Góc viết: nói dễ hiểu cho người mới mua.",
    "Myth-busting hiểu lầm thường gặp": "Ví dụ: tụ bù càng rẻ càng tốt, tủ có quạt là đủ mát, không có cuộn kháng vẫn dùng tụ bù được.",
    "Bảng chọn nhanh sản phẩm": "Ví dụ: tủ nhỏ dùng quạt lọc nào, tải có biến tần chọn tụ/cuộn kháng ra sao, công suất kVAr nào phù hợp.",
    "Nội dung mùa vụ": "Mùa nóng: quá nhiệt. Mùa mưa: ẩm/rò điện. Cuối năm: bảo trì. Sau Tết: kiểm tra hệ thống trước khi chạy lại.",
    "Tin chính sách/quy định/tiêu chuẩn": "Nguồn: an toàn điện, PCCC, tiêu chuẩn tủ điện. Góc viết: doanh nghiệp nên kiểm tra thiết bị gì để an toàn hơn.",
    "Review sản phẩm theo tình huống": "Góc viết: dòng này hợp tủ ngoài trời không, dùng cho xưởng nhiều biến tần không, hợp tủ tụ bù không.",
    "Câu hỏi từ khách hàng": "Nguồn: inbox, comment, sale team. Góc viết: khách hỏi - shop trả lời bằng tư vấn cụ thể.",
    "Bắt trend chuyên ngành": "Ví dụ: 3 dấu hiệu, đừng mua nếu chưa biết, sai lầm phổ biến. Giữ chuyên môn, không lố giải trí.",
    "Cảm ơn/ghi nhận": "Nguồn: khách hàng/đối tác/bài viết nhắc đến sản phẩm. Góc viết: cảm ơn, ứng dụng thực tế, lưu ý khi chọn.",
    "Cảnh báo hàng giả/kém chất lượng": "Nguồn: thị trường, phản ánh khách hàng, nhóm ngành. Góc viết: rủi ro hàng rẻ bất thường, CO/CQ, bảo hành.",
    "Mini-series": "Ví dụ: 7 ngày hiểu về tụ bù, một tuần kiểm tra tủ điện, mỗi ngày một lỗi thường gặp.",
    "Bài kéo inbox": "Ví dụ: gửi ảnh tủ điện, gửi công suất tải, comment từ khóa để nhận checklist. Mục tiêu lead, không chỉ like.",
    "Giới thiệu năng lực công ty": "Góc viết: công ty cung cấp nhóm sản phẩm gì, phục vụ ai, tư vấn theo quy trình nào. Mục tiêu: tăng tin cậy và follow, không chỉ chốt đơn.",
    "Hậu trường kho/đóng hàng": "Nguồn: ảnh kho, đóng gói, kiểm tem, kiểm mã, chuẩn bị đơn. Góc viết: quy trình cẩn thận giúp khách yên tâm khi mua hàng kỹ thuật.",
    "Q&A nhanh cho người mới": "Góc viết: 1 câu hỏi phổ biến, trả lời ngắn dễ hiểu, cuối bài mời follow để xem thêm kiến thức tủ điện.",
    "Bài tăng follow/lưu bài": "Góc viết: checklist, bảng nhớ nhanh, series kiến thức có ích để khách lưu lại hoặc theo dõi page.",
    "Bản đồ sản phẩm theo nhu cầu": "Góc viết: tủ điện cần làm mát/bù công suất/bảo vệ/đo lường thì nên kiểm tra nhóm sản phẩm nào. Phù hợp quảng bá danh mục công ty.",
    "Combo giải pháp hệ thống": "Góc viết: không bán một món riêng lẻ mà gợi ý bộ giải pháp theo tình huống như làm mát tủ, bù công suất, bảo vệ tải, đo lường.",
}

MACHINE_IDEA_BLUEPRINTS = {
    "Sự cố & bài học an toàn": {
        "emoji": "🚨", "priority": "Cao",
        "hook": "Một dấu hiệu nhỏ ở {label} có thể là cảnh báo sớm trước khi tủ điện dừng vận hành.",
        "outline": ["Nêu dấu hiệu/sự cố thực tế", "Giải thích rủi ro nếu bỏ qua", "Đưa checklist kiểm tra an toàn"],
        "image": "Ảnh hiện trạng tủ, điểm nóng/bụi hoặc thiết bị cũ cần kiểm tra.",
        "cta": "Gửi ảnh hiện trạng và tem thiết bị để được hỗ trợ khoanh vùng trước khi thay.",
    },
    "Tin tức ngành điện": {
        "emoji": "📰", "priority": "Vừa",
        "hook": "Tin ngành điện chỉ thật sự hữu ích khi biến thành việc cần kiểm tra ngay tại nhà xưởng.",
        "outline": ["Tóm tắt một thay đổi/tín hiệu ngành", "Liên hệ ảnh hưởng tới vận hành tủ điện", "Gợi ý hành động thực tế, không giật tin"],
        "image": "Thiết kế một số liệu chính kèm ảnh tủ điện hoặc nhà xưởng.",
        "cta": "Lưu bài và gửi tình trạng hệ thống nếu cần gợi ý nhóm thiết bị nên kiểm tra.",
    },
    "Bài báo/cộng đồng nhắc đến sản phẩm": {
        "emoji": "📣", "priority": "Vừa",
        "hook": "Khi cộng đồng nhắc đến {product}, điều đáng nói nhất là ứng dụng thực tế phía sau sản phẩm.",
        "outline": ["Nêu ngữ cảnh được nhắc đến", "Rút ra bài học chọn đúng thông số", "Cảm ơn nguồn nhưng không sao chép nội dung"],
        "image": "Ảnh sản phẩm thật kèm trích ý ngắn đã diễn đạt lại.",
        "cta": "Inbox mã hoặc ứng dụng đang quan tâm để được đối chiếu thông tin phù hợp.",
    },
    "Case study khách hàng": {
        "emoji": "🏭", "priority": "Cao",
        "hook": "Bài toán không phải bán một món {label}, mà là giúp khách chọn đúng cho tình trạng đang gặp.",
        "outline": ["Tình trạng trước khi tư vấn", "Thông tin đã dùng để chọn sản phẩm", "Kết quả/kinh nghiệm chỉ nêu khi có bằng chứng"],
        "image": "Bộ ảnh trước–sau, ảnh tem cũ và ảnh sản phẩm thay thế.",
        "cta": "Gửi ca thực tế của bạn để team đề xuất checklist thông tin cần đối chiếu.",
    },
    "So sánh trước/sau": {
        "emoji": "🔄", "priority": "Cao",
        "hook": "Trước và sau khi xử lý {label}, khác biệt nên được nhìn bằng dữ liệu chứ không chỉ bằng ảnh đẹp.",
        "outline": ["Mô tả tình trạng trước", "Nêu thao tác/thay đổi đã thực hiện", "So sánh bằng nhiệt độ, độ ổn định hoặc dấu hiệu quan sát được"],
        "image": "Hai ảnh cùng góc chụp trước và sau, có chú thích rõ.",
        "cta": "Gửi ảnh trước–sau hoặc thông số đo để được hỗ trợ biên tập thành case study.",
    },
    "Checklist kỹ thuật": {
        "emoji": "✅", "priority": "Cao",
        "hook": "Trước khi chọn {product}, hãy kiểm tra 5 điểm này để tránh mua đúng tên nhưng sai ứng dụng.",
        "outline": ["Kiểm tra {checks}", "Đối chiếu mã/tem và vị trí lắp", "Chốt điều kiện bắt buộc trước khi đặt"],
        "image": "Ảnh sản phẩm đánh số từng vị trí cần kiểm tra.",
        "cta": "Gửi ảnh tem và thông số cũ để shop đối chiếu theo checklist.",
    },
    "Giải thích thuật ngữ đơn giản": {
        "emoji": "💡", "priority": "Vừa",
        "hook": "Thông số trên {product} có ý nghĩa gì, và thông số nào thật sự ảnh hưởng đến việc chọn đúng?",
        "outline": ["Chọn một thuật ngữ khách hay gặp", "Giải thích bằng ngôn ngữ đời thường", "Cho ví dụ ứng dụng trong tủ điện"],
        "image": "Cận cảnh tem sản phẩm, khoanh tròn thông số đang giải thích.",
        "cta": "Comment thuật ngữ bạn chưa rõ để làm chủ đề Q&A tiếp theo.",
    },
    "Myth-busting hiểu lầm thường gặp": {
        "emoji": "🧨", "priority": "Cao",
        "hook": "Đúng hay sai: chỉ cần cùng kích thước là có thể thay {label} cho nhau?",
        "outline": ["Nêu hiểu lầm phổ biến", "Giải thích vì sao dễ dẫn đến chọn sai", "Đưa nguyên tắc kiểm tra đúng"],
        "image": "Thiết kế Đúng/Sai đặt cạnh hai tem hoặc hai mẫu sản phẩm.",
        "cta": "Gửi hai mã đang phân vân để được hỗ trợ chỉ ra điểm khác nhau.",
    },
    "Bảng chọn nhanh sản phẩm": {
        "emoji": "📊", "priority": "Cao",
        "hook": "Không biết bắt đầu chọn {label} từ đâu? Dùng bảng 3 bước này trước khi hỏi giá.",
        "outline": ["Chia theo nhu cầu/ứng dụng", "Liệt kê thông số cần đối chiếu", "Nêu trường hợp cần hỏi kỹ thuật"],
        "image": "Bảng so sánh ngắn 3–4 cột, chữ lớn và dễ lưu.",
        "cta": "Gửi nhu cầu và thông số hiện có để nhận gợi ý nhánh lựa chọn phù hợp.",
    },
    "Nội dung mùa vụ": {
        "emoji": "🌦️", "priority": "Vừa",
        "hook": "Trước mùa nóng/mưa, {label} trong tủ điện nên được kiểm tra ở điểm nào?",
        "outline": ["Nêu rủi ro theo mùa", "Checklist bảo trì ngắn", "Gợi ý chuẩn bị vật tư trước cao điểm"],
        "image": "Ảnh tủ điện trong môi trường nóng, bụi hoặc ẩm kèm checklist.",
        "cta": "Lưu checklist và gửi ảnh tủ nếu cần xác định hạng mục nên ưu tiên.",
    },
    "Tin chính sách/quy định/tiêu chuẩn": {
        "emoji": "📜", "priority": "Vừa",
        "hook": "Một quy định kỹ thuật chỉ có giá trị khi doanh nghiệp biết nó tác động đến khâu kiểm tra nào.",
        "outline": ["Dẫn đúng nguồn chính thức", "Diễn giải tác động bằng tiếng Việt dễ hiểu", "Đưa danh sách việc doanh nghiệp nên rà soát"],
        "image": "Card tóm tắt quy định, ghi rõ nguồn và ngày hiệu lực.",
        "cta": "Lưu bài để trao đổi với đội kỹ thuật; luôn đối chiếu văn bản gốc trước khi áp dụng.",
    },
    "Review sản phẩm theo tình huống": {
        "emoji": "🔍", "priority": "Cao",
        "hook": "{product} phù hợp tình huống nào, và trường hợp nào không nên chọn vội?",
        "outline": ["Mô tả 2–3 tình huống phù hợp", "Nêu giới hạn/điều kiện cần kiểm tra", "Kết luận theo nhu cầu thay vì khen chung chung"],
        "image": "Ảnh sản phẩm thật trong bối cảnh lắp hoặc sơ đồ ứng dụng.",
        "cta": "Mô tả tình huống sử dụng để được kiểm tra sản phẩm có phù hợp không.",
    },
    "Câu hỏi từ khách hàng": {
        "emoji": "💬", "priority": "Cao",
        "hook": "Khách hỏi: “{product} có thay trực tiếp cho mẫu cũ của tôi được không?”",
        "outline": ["Trả lời ngắn: chưa thể kết luận chỉ từ tên", "Nêu thông tin cần khách cung cấp", "Giải thích cách đối chiếu an toàn"],
        "image": "Ảnh mô phỏng đoạn hỏi đáp kèm tem sản phẩm.",
        "cta": "Gửi câu hỏi và ảnh tem thật để được trả lời theo đúng trường hợp.",
    },
    "Bắt trend chuyên ngành": {
        "emoji": "⚡", "priority": "Vừa",
        "hook": "Đừng mua {label} nếu bạn chưa kiểm tra ba thông tin này.",
        "outline": ["Dùng format trend ngắn", "Giữ nội dung kỹ thuật chính xác", "Kết bằng một hành động kiểm tra cụ thể"],
        "image": "Video dọc 10–20 giây, chữ lớn, quay cận tem và vị trí lắp.",
        "cta": "Lưu video và gửi cho người đang phụ trách mua vật tư/kỹ thuật.",
    },
    "Cảm ơn/ghi nhận": {
        "emoji": "🤝", "priority": "Thấp",
        "hook": "Cảm ơn khách hàng đã tin tưởng quy trình đối chiếu kỹ trước khi chọn {product}.",
        "outline": ["Ghi nhận khách hàng/đối tác", "Nhắc giá trị tư vấn đúng mã", "Không bịa lời khen hoặc kết quả"],
        "image": "Ảnh đơn hàng, bàn giao hoặc đội ngũ; che thông tin riêng tư.",
        "cta": "Cần đối chiếu sản phẩm tương tự, hãy gửi tem/mã cũ để team kiểm tra.",
    },
    "Cảnh báo hàng giả/kém chất lượng": {
        "emoji": "🛡️", "priority": "Cao",
        "hook": "Giá rẻ bất thường ở {label} có thể đi kèm những rủi ro nào khi lắp trong tủ điện?",
        "outline": ["Nêu dấu hiệu cần cảnh giác", "Giải thích rủi ro kỹ thuật/bảo hành", "Chỉ cách kiểm tra nguồn gốc và tem nhãn"],
        "image": "Ảnh tem, bao bì và chi tiết nhận diện; không quy kết khi thiếu bằng chứng.",
        "cta": "Gửi ảnh tem/bao bì nếu cần hỗ trợ kiểm tra các dấu hiệu cơ bản.",
    },
    "Mini-series": {
        "emoji": "🗓️", "priority": "Vừa",
        "hook": "Series 5 ngày hiểu đúng về {label}: mỗi ngày một lỗi chọn sai thường gặp.",
        "outline": ["Ngày 1: khái niệm/ứng dụng", "Ngày 2–4: thông số, lỗi và cách kiểm tra", "Ngày 5: bảng chọn nhanh + CTA"],
        "image": "Bộ template đồng nhất, đánh số từng tập.",
        "cta": "Theo dõi page và lưu series để dùng khi cần mua hoặc bảo trì.",
    },
    "Bài kéo inbox": {
        "emoji": "📩", "priority": "Cao",
        "hook": "Không chắc {product} có đúng mẫu cần thay? Chỉ cần gửi ba ảnh này.",
        "outline": ["Ảnh tem/mã cũ", "Ảnh tổng thể vị trí lắp", "Ảnh thông số hoặc sơ đồ liên quan"],
        "image": "Collage ba ảnh mẫu khách cần gửi, đánh số 1–2–3.",
        "cta": "Inbox đủ ba ảnh để team đối chiếu trước khi báo mẫu phù hợp.",
    },
    "Giới thiệu năng lực công ty": {
        "emoji": "🏢", "priority": "Vừa",
        "hook": "Master Electric không chỉ cung cấp một mã hàng, mà hỗ trợ khách chọn đúng nhóm phụ kiện tủ điện.",
        "outline": ["Nêu nhóm sản phẩm công ty cung cấp", "Nêu đối tượng khách hàng phục vụ", "Mô tả quy trình tư vấn/đối chiếu"],
        "image": "Ảnh đội ngũ, kho hàng và các nhóm sản phẩm chính.",
        "cta": "Gửi danh sách vật tư hoặc ảnh tủ để được hỗ trợ phân nhóm nhu cầu.",
    },
    "Hậu trường kho/đóng hàng": {
        "emoji": "📦", "priority": "Vừa",
        "hook": "Một đơn {product} trước khi rời kho được kiểm tra những gì?",
        "outline": ["Kiểm mã và tem thông số", "Kiểm ngoại quan/số lượng", "Đóng gói và đối chiếu đơn"],
        "image": "Ảnh thật từng bước kiểm hàng và đóng gói.",
        "cta": "Theo dõi page để xem thêm quy trình chuẩn bị hàng kỹ thuật.",
    },
    "Q&A nhanh cho người mới": {
        "emoji": "❓", "priority": "Cao",
        "hook": "Người mới hỏi: chọn {label} nên nhìn tên sản phẩm hay nhìn thông số trước?",
        "outline": ["Trả lời trong một câu", "Giải thích ba thông số quan trọng", "Cho ví dụ chọn sai thường gặp"],
        "image": "Card hỏi–đáp một màn hình, chữ ít và dễ đọc.",
        "cta": "Để lại câu hỏi cơ bản; page sẽ trả lời bằng ví dụ dễ hiểu.",
    },
    "Bài tăng follow/lưu bài": {
        "emoji": "🔖", "priority": "Cao",
        "hook": "Lưu lại bảng kiểm {label} này — đến lúc bảo trì sẽ đỡ phải tìm lại từ đầu.",
        "outline": ["Tạo tài liệu có thể dùng lại", "Trình bày ngắn, có thứ tự", "Hứa series tiếp theo cụ thể"],
        "image": "Infographic checklist hoặc bảng nhớ nhanh theo khổ dọc.",
        "cta": "Lưu bài và theo dõi page để nhận thêm bảng kiểm thiết bị tủ điện.",
    },
    "Bản đồ sản phẩm theo nhu cầu": {
        "emoji": "🧭", "priority": "Cao",
        "hook": "Tủ điện đang nóng, đo sai, đóng cắt bất ổn hay cần bù công suất? Mỗi vấn đề đi với một nhóm giải pháp khác.",
        "outline": ["Chia nhu cầu: làm mát/đo lường/bảo vệ/bù công suất", "Gắn nhóm sản phẩm tương ứng", "Nhắc cần kiểm tra thông số trước khi chọn mã"],
        "image": "Sơ đồ nhánh từ vấn đề đến nhóm sản phẩm.",
        "cta": "Gửi vấn đề đang gặp để được chỉ đúng nhánh sản phẩm cần tìm hiểu.",
    },
    "Combo giải pháp hệ thống": {
        "emoji": "🧩", "priority": "Cao",
        "hook": "Một tủ điện vận hành ổn định thường cần cả bộ giải pháp, không phải chỉ thay một thiết bị.",
        "outline": ["Nêu vấn đề hệ thống", "Ghép các nhóm thiết bị có vai trò bổ trợ", "Đưa thứ tự kiểm tra và điều kiện lựa chọn"],
        "image": "Sơ đồ combo thiết bị trong một tủ điện, có chú thích vai trò.",
        "cta": "Gửi sơ đồ hoặc ảnh tổng thể tủ để được gợi ý danh sách hạng mục cần rà soát.",
    },
}
MACHINE_IDEA_VERSION = 2
CONTENT_GENERATION_VERSION = 3

MACHINE_CAPTION_ICONS = {
    "Sự cố & bài học an toàn": ("🚨", "⚠️", "🛡️", "🔧"),
    "Tin tức ngành điện": ("📰", "⚡", "📈", "🏭"),
    "Bài báo/cộng đồng nhắc đến sản phẩm": ("📣", "💬", "🔎", "🤝"),
    "Case study khách hàng": ("🏭", "📍", "🛠️", "📈"),
    "So sánh trước/sau": ("🔄", "⏪", "🛠️", "⏩"),
    "Checklist kỹ thuật": ("✅", "🔍", "📏", "🔧"),
    "Giải thích thuật ngữ đơn giản": ("💡", "📖", "⚙️", "🧠"),
    "Myth-busting hiểu lầm thường gặp": ("🧨", "❌", "🔍", "✅"),
    "Bảng chọn nhanh sản phẩm": ("📊", "1️⃣", "2️⃣", "3️⃣"),
    "Nội dung mùa vụ": ("🌦️", "🌡️", "💧", "🧰"),
    "Tin chính sách/quy định/tiêu chuẩn": ("📜", "🏛️", "📌", "🔎"),
    "Review sản phẩm theo tình huống": ("🔍", "🎯", "⚙️", "📌"),
    "Câu hỏi từ khách hàng": ("💬", "❓", "🔎", "📩"),
    "Bắt trend chuyên ngành": ("⚡", "🎬", "👀", "📌"),
    "Cảm ơn/ghi nhận": ("🤝", "💙", "📦", "🙏"),
    "Cảnh báo hàng giả/kém chất lượng": ("🛡️", "⚠️", "🔍", "📌"),
    "Mini-series": ("🗓️", "1️⃣", "2️⃣", "3️⃣"),
    "Bài kéo inbox": ("📩", "1️⃣", "2️⃣", "3️⃣"),
    "Giới thiệu năng lực công ty": ("🏢", "⚙️", "📦", "🤝"),
    "Hậu trường kho/đóng hàng": ("📦", "🔍", "🧾", "🚚"),
    "Q&A nhanh cho người mới": ("❓", "💡", "🔍", "📌"),
    "Bài tăng follow/lưu bài": ("🔖", "📋", "💡", "➕"),
    "Bản đồ sản phẩm theo nhu cầu": ("🧭", "🌡️", "🛡️", "📊"),
    "Combo giải pháp hệ thống": ("🧩", "🌡️", "⚡", "🛡️"),
}

BLOCKED_RESULT_KEYWORDS = [
    "nhà cái",
    "casino",
    "cá cược",
    "bóng đá",
    "soi kèo",
    "slot",
    "xổ số",
    "lô đề",
    "poker",
    "game bài",
    "betting",
    "bet365",
    "trực tiếp bóng đá",
    "chọn đúng nơi chơi",
]

BLOCKED_DOMAINS = [
    "188bet",
    "w88",
    "bk8",
    "m88",
    "fun88",
    "fb88",
    "188.",
    "casino",
    "nhacai",
    "keonhacai",
    "bongda",
]

DEFAULT_BRAND_LABEL = "MASTER ELECTRIC"
DEFAULT_COMPANY_NAME = "CÔNG TY TNHH THƯƠNG MẠI KỸ THUẬT THIÊN LỘC PHÁT"
DEFAULT_COMPANY_FOOTER = """
CÔNG TY TNHH THƯƠNG MẠI KỸ THUẬT THIÊN LỘC PHÁT
Địa chỉ: 22 đường 14 (khu 38ha), P. Đông Hưng Thuận, TPHCM
Số Điện Thoại Liên Hệ: 0901104339 - 0932706899
Website: giadiencongnghiep.com
Website: masterelectric.com.vn
Youtube: https://www.youtube.com/@thietbiienmaster
Tiktok: https://www.tiktok.com/@masterelectricvietnam
Fanpage: https://www.facebook.com/thietbidiencongnghiepTLP
""".strip()

DEFAULT_COMPANY_HASHTAGS = [
    "#MasterElectric",
    "#ThietBiDienCongNghiep",
    "#TuDienCongNghiep",
]


st.set_page_config(page_title="Social AI Planner", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');

/* Global typography */
.stApp { font-family: 'Inter', sans-serif; }
h1, h2, h3 { font-family: 'Space Grotesk', sans-serif !important; font-weight: 700 !important; letter-spacing: -0.02em !important; }
h1 { font-size: 2rem !important; }

/* ===== FB Post Simulation ===== */
.fb-post { padding: 0; }
.fb-profile-header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 4px 0 10px 0;
}
.fb-avatar {
    width: 42px; height: 42px;
    border-radius: 50%;
    background: linear-gradient(135deg, #1877F2, #0d5bbd);
    display: flex; align-items: center; justify-content: center;
    color: #fff; font-weight: 700; font-size: 1rem;
    font-family: 'Space Grotesk', sans-serif;
    flex-shrink: 0;
}
.fb-avatar.ig { background: linear-gradient(135deg, #E1306C, #C13584, #833AB4); }
.fb-profile-info { line-height: 1.3; }
.fb-profile-name {
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700; font-size: 0.95rem;
}
.fb-profile-meta {
    font-size: 0.75rem; color: #888;
    display: flex; align-items: center; gap: 6px;
}
.fb-caption {
    font-size: 0.94rem;
    line-height: 1.65;
    padding: 4px 0 8px 0;
    white-space: pre-wrap;
}

/* Platform badge pills */
.platform-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.65rem;
    font-weight: 600;
    font-family: 'Space Grotesk', sans-serif;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}
.badge-fb { background: #e7f0fd; color: #1877F2; }
.badge-ig { background: #fce4ec; color: #C13584; }

/* Status pill */
.status-pill {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 20px;
    font-size: 0.7rem;
    font-weight: 600;
    font-family: 'Space Grotesk', sans-serif;
    letter-spacing: 0.03em;
}
.status-approved { background: #d4edda; color: #155724; }
.status-draft { background: #fff3cd; color: #856404; }

/* Hashtag styling */
.hashtag-line {
    font-size: 0.88rem;
    font-weight: 500;
    color: #1877F2;
    letter-spacing: 0.01em;
    padding: 2px 0 6px 0;
}

/* CTA box */
.cta-box {
    border-left: 3px solid #1877F2;
    padding: 10px 16px;
    background: rgba(24, 119, 242, 0.04);
    border-radius: 0 8px 8px 0;
    font-weight: 500;
    font-size: 0.92rem;
    margin: 8px 0;
    color: inherit;
}

/* Image guidance caption */
.img-guidance {
    font-size: 0.8rem;
    color: #999;
    font-style: italic;
    margin-top: 4px;
}

/* Section label */
.section-label {
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 600;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #888;
    margin-bottom: 4px;
}

/* Card header */
.card-header {
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700;
    font-size: 1.15rem;
    letter-spacing: -0.01em;
}

/* Post timestamp */
.post-meta {
    font-size: 0.75rem;
    color: #999;
    text-align: right;
}

/* Topic tag */
.topic-tag {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 6px;
    background: #f0f2f5;
    font-size: 0.78rem;
    font-weight: 500;
    color: #555;
    margin-top: 2px;
}

/* Image grid in post card */
.fb-image-grid {
    display: grid;
    gap: 4px;
    border-radius: 8px;
    overflow: hidden;
    margin: 6px 0;
    max-width: 520px;
}
.fb-image-grid img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}
.fb-image-grid.grid-1 { grid-template-columns: 1fr; max-height: 380px; }
.fb-image-grid.grid-2 { grid-template-columns: 1fr 1fr; max-height: 300px; }
.fb-image-grid.grid-3 { grid-template-columns: 1fr 1fr; max-height: 360px; }
.fb-image-grid.grid-3 > :first-child { grid-row: 1 / 3; }
.fb-image-grid.grid-many { grid-template-columns: 1fr 1fr 1fr; max-height: 260px; }

/* Upload gallery */
.upload-count {
    font-size: 0.85rem;
    font-weight: 500;
    color: #666;
    margin-bottom: 6px;
}

/* ===== Machine Idea Cards ===== */
.machine-idea-card {
    border: 1px solid #e3e8ef;
    border-radius: 12px;
    padding: 18px 20px;
    margin-bottom: 14px;
    background: linear-gradient(135deg, #fafbfd 0%, #f4f7fb 100%);
    transition: box-shadow 0.25s ease, transform 0.2s ease;
    position: relative;
    overflow: hidden;
}
.machine-idea-card:hover {
    box-shadow: 0 6px 24px rgba(24, 119, 242, 0.12);
    transform: translateY(-2px);
}
.machine-idea-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, #1877F2, #42a5f5, #1877F2);
    border-radius: 12px 12px 0 0;
}
.machine-card-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
}
.machine-card-emoji {
    font-size: 1.5rem;
    line-height: 1;
}
.machine-card-title {
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700;
    font-size: 0.95rem;
    color: #1a2332;
    letter-spacing: -0.01em;
}
.machine-card-number {
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 600;
    font-size: 0.65rem;
    color: #fff;
    background: #1877F2;
    border-radius: 50%;
    width: 22px;
    height: 22px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
.machine-card-hook {
    font-size: 0.92rem;
    font-weight: 600;
    color: #1877F2;
    margin-bottom: 8px;
    line-height: 1.5;
    font-style: italic;
}
.machine-card-outline {
    font-size: 0.88rem;
    color: #4a5568;
    line-height: 1.6;
    margin-bottom: 10px;
    white-space: pre-wrap;
}
.machine-card-cta {
    border-left: 3px solid #1877F2;
    padding: 8px 14px;
    background: rgba(24, 119, 242, 0.06);
    border-radius: 0 8px 8px 0;
    font-weight: 500;
    font-size: 0.85rem;
    margin-bottom: 8px;
    color: #1a2332;
}
.machine-card-image-tip {
    font-size: 0.8rem;
    color: #718096;
    font-style: italic;
}
.machine-card-priority {
    margin-left: auto;
    padding: 3px 9px;
    border-radius: 999px;
    font-size: 0.68rem;
    font-weight: 700;
    white-space: nowrap;
}
.machine-priority-high {
    color: #9f1239;
    background: #ffe4e6;
}
.machine-priority-medium {
    color: #92400e;
    background: #fef3c7;
}
.machine-priority-low {
    color: #166534;
    background: #dcfce7;
}
.machine-chat-input-wrapper {
    background: linear-gradient(135deg, #f0f4ff 0%, #e8f0fe 100%);
    border: 2px solid #c3d7f7;
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 20px;
}
.machine-chat-title {
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700;
    font-size: 1.1rem;
    color: #1a2332;
    margin-bottom: 4px;
}
.machine-chat-subtitle {
    font-size: 0.82rem;
    color: #718096;
    margin-bottom: 12px;
}
.machine-ideas-grid-header {
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700;
    font-size: 1.15rem;
    color: #1a2332;
    letter-spacing: -0.01em;
    margin: 24px 0 6px 0;
    display: flex;
    align-items: center;
    gap: 10px;
}
.machine-ideas-product-badge {
    display: inline-block;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 600;
    font-family: 'Space Grotesk', sans-serif;
    background: linear-gradient(135deg, #1877F2, #42a5f5);
    color: #fff;
    letter-spacing: 0.02em;
}
</style>
""", unsafe_allow_html=True)



def read_json_file(path, fallback):
    if not path.exists():
        return fallback

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return fallback


def write_json_file(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def ollama_chat_with_timeout(**kwargs):
    client = ollama.Client(timeout=OLLAMA_TIMEOUT_SECONDS)
    return client.chat(**kwargs)


def prepare_image_for_vision(image_bytes):
    with Image.open(io.BytesIO(image_bytes)) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((VISION_MAX_IMAGE_SIDE, VISION_MAX_IMAGE_SIDE))

        output = io.BytesIO()
        image.save(output, format="JPEG", quality=VISION_JPEG_QUALITY, optimize=True)
        return output.getvalue()


def load_saved_posts():
    return read_json_file(SAVED_POSTS_FILE, [])


def save_saved_posts(posts):
    write_json_file(SAVED_POSTS_FILE, posts)


def app_secret(name, default=""):
    value = os.getenv(name)
    if value:
        return value.strip()

    try:
        value = st.secrets.get(name, default)
    except (FileNotFoundError, KeyError):
        value = default
    return str(value).strip() if value is not None else ""


def facebook_config():
    return {
        "page_id": app_secret("FACEBOOK_PAGE_ID"),
        "access_token": app_secret("FACEBOOK_PAGE_ACCESS_TOKEN"),
        "api_version": app_secret(
            "FACEBOOK_GRAPH_API_VERSION",
            FACEBOOK_GRAPH_API_DEFAULT_VERSION,
        ),
    }


def facebook_configured(config=None):
    config = config or facebook_config()
    return bool(config["page_id"] and config["access_token"])


def facebook_post_message(post):
    parts = [post.get("caption", "").strip()]
    hashtags = post.get("hashtags", [])
    hashtag_text = " ".join(hashtags).strip()
    if hashtag_text:
        parts.append(hashtag_text)
    return "\n\n".join(part for part in parts if part)


def facebook_api_error(response):
    try:
        payload = response.json()
    except ValueError:
        return f"Facebook trả về HTTP {response.status_code}."

    error = payload.get("error", {})
    message = error.get("message") or payload.get("message")
    code = error.get("code")
    subcode = error.get("error_subcode")
    suffix = ""
    if code:
        suffix += f" (mã {code}"
        if subcode:
            suffix += f"/{subcode}"
        suffix += ")"
    return f"{message or 'Facebook từ chối yêu cầu.'}{suffix}"


def facebook_graph_post(url, *, data, files=None, timeout=60):
    try:
        response = requests.post(url, data=data, files=files, timeout=timeout)
    except requests.RequestException as exc:
        raise RuntimeError(f"Không kết nối được Facebook: {exc}") from exc

    if not response.ok:
        raise RuntimeError(facebook_api_error(response))

    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("Facebook trả về dữ liệu không hợp lệ.") from exc


def facebook_graph_get(url, *, params, timeout=30):
    try:
        response = requests.get(url, params=params, timeout=timeout)
    except requests.RequestException as exc:
        raise RuntimeError(f"Khong ket noi duoc Facebook: {exc}") from exc

    if not response.ok:
        raise RuntimeError(facebook_api_error(response))

    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("Facebook tra ve du lieu khong hop le.") from exc


def facebook_page_access_token(page_id, access_token, api_root):
    identity = facebook_graph_get(
        f"{api_root}/me",
        params={"fields": "id", "access_token": access_token},
    )
    if str(identity.get("id", "")) == str(page_id):
        return access_token

    accounts = facebook_graph_get(
        f"{api_root}/me/accounts",
        params={
            "fields": "id,name,access_token,tasks",
            "limit": 100,
            "access_token": access_token,
        },
    )
    for page in accounts.get("data", []):
        if str(page.get("id", "")) == str(page_id) and page.get("access_token"):
            return page["access_token"]

    raise RuntimeError(
        "Token Facebook hiện tại không đại diện cho Page đã cấu hình. "
        "Hãy cấp quyền pages_show_list, pages_read_engagement và "
        "pages_manage_posts, hoặc thay bằng Page Access Token."
    )


def facebook_summary_count(payload, field):
    value = payload.get(field, {})
    if not isinstance(value, dict):
        return 0
    summary = value.get("summary", {})
    if not isinstance(summary, dict):
        return 0
    try:
        return int(summary.get("total_count", 0) or 0)
    except (TypeError, ValueError):
        return 0


def facebook_insight_value(payload):
    for metric in payload.get("data", []):
        values = metric.get("values", [])
        if not values:
            continue
        value = values[-1].get("value", 0)
        if isinstance(value, dict):
            value = sum(
                int(item or 0)
                for item in value.values()
                if isinstance(item, (int, float))
            )
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            continue
    return None


def fetch_facebook_post_metrics(post, config=None):
    config = config or facebook_config()
    if not facebook_configured(config):
        raise RuntimeError(
            "Chua cau hinh FACEBOOK_PAGE_ID va FACEBOOK_PAGE_ACCESS_TOKEN."
        )

    publish_info = post.get("facebook_publish", {})
    post_id = publish_info.get("post_id", "")
    if not post_id:
        raise RuntimeError(
            "Bai nay chua co Facebook Post ID. Hay dang bai tu app truoc."
        )

    access_token = config["access_token"]
    api_version = config["api_version"] or FACEBOOK_GRAPH_API_DEFAULT_VERSION
    api_root = f"https://graph.facebook.com/{api_version}"
    fields = (
        "reactions.type(LIKE).limit(0).summary(true),"
        "comments.limit(0).summary(true),shares"
    )
    try:
        payload = facebook_graph_get(
            f"{api_root}/{post_id}",
            params={"fields": fields, "access_token": access_token},
        )
    except RuntimeError as exc:
        if "pages_read_user_content" in str(exc):
            raise RuntimeError(
                "Token chua co quyen pages_read_user_content de doc "
                "Like, Comment va Share cua bai viet."
            ) from exc
        raise

    shares = payload.get("shares", {})
    try:
        share_count = int(shares.get("count", 0) or 0)
    except (AttributeError, TypeError, ValueError):
        share_count = 0

    result = {
        "likes": facebook_summary_count(payload, "reactions"),
        "comments": facebook_summary_count(payload, "comments"),
        "shares": share_count,
        "views": None,
        "views_error": "",
    }

    try:
        insights = facebook_graph_get(
            f"{api_root}/{post_id}/insights",
            params={
                "metric": "post_impressions_unique",
                "access_token": access_token,
            },
        )
        result["views"] = facebook_insight_value(insights)
    except RuntimeError as exc:
        result["views_error"] = str(exc)

    return result


def publish_post_to_facebook(post, config=None):
    config = config or facebook_config()
    if not facebook_configured(config):
        raise RuntimeError(
            "Chưa cấu hình FACEBOOK_PAGE_ID và FACEBOOK_PAGE_ACCESS_TOKEN."
        )

    page_id = config["page_id"]
    access_token = config["access_token"]
    api_version = config["api_version"] or FACEBOOK_GRAPH_API_DEFAULT_VERSION
    api_root = f"https://graph.facebook.com/{api_version}"
    access_token = facebook_page_access_token(page_id, access_token, api_root)
    message = facebook_post_message(post)
    image_paths = [
        Path(path)
        for path in post.get("image_files", [])
        if Path(path).is_file()
    ]

    if not image_paths:
        result = facebook_graph_post(
            f"{api_root}/{page_id}/feed",
            data={"message": message, "access_token": access_token},
        )
        return {
            "post_id": result.get("id", ""),
            "url": (
                f"https://www.facebook.com/{result['id'].replace('_', '/posts/')}"
                if result.get("id") and "_" in result["id"]
                else ""
            ),
        }

    if len(image_paths) == 1:
        with image_paths[0].open("rb") as image_file:
            result = facebook_graph_post(
                f"{api_root}/{page_id}/photos",
                data={"caption": message, "access_token": access_token},
                files={"source": (image_paths[0].name, image_file)},
            )
        post_id = result.get("post_id") or result.get("id", "")
        return {
            "post_id": post_id,
            "photo_id": result.get("id", ""),
            "url": (
                f"https://www.facebook.com/{post_id.replace('_', '/posts/')}"
                if post_id and "_" in post_id
                else ""
            ),
        }

    uploaded_photo_ids = []
    for image_path in image_paths:
        with image_path.open("rb") as image_file:
            result = facebook_graph_post(
                f"{api_root}/{page_id}/photos",
                data={
                    "published": "false",
                    "access_token": access_token,
                },
                files={"source": (image_path.name, image_file)},
            )
        photo_id = result.get("id")
        if not photo_id:
            raise RuntimeError("Facebook không trả về mã ảnh đã tải lên.")
        uploaded_photo_ids.append(photo_id)

    feed_data = {
        "message": message,
        "access_token": access_token,
    }
    for index, photo_id in enumerate(uploaded_photo_ids):
        feed_data[f"attached_media[{index}]"] = json.dumps(
            {"media_fbid": photo_id}
        )

    result = facebook_graph_post(
        f"{api_root}/{page_id}/feed",
        data=feed_data,
    )
    post_id = result.get("id", "")
    return {
        "post_id": post_id,
        "photo_ids": uploaded_photo_ids,
        "url": (
            f"https://www.facebook.com/{post_id.replace('_', '/posts/')}"
            if post_id and "_" in post_id
            else ""
        ),
    }


def make_id(prefix):
    raw = f"{prefix}-{datetime.now().isoformat()}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:12]


def remove_vietnamese_accents(text):
    text = text.replace("Đ", "D").replace("đ", "d")
    normalized_text = unicodedata.normalize("NFD", text)
    return "".join(char for char in normalized_text if unicodedata.category(char) != "Mn")


def clean_hashtag_value(value):
    value = remove_vietnamese_accents(str(value))
    value = re.sub(r"[^A-Za-z0-9]", "", value)
    return f"#{value}" if value else ""


def normalize_hashtags(value):
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = re.findall(r"#?[^\s,#]+", str(value))

    hashtags = []
    for item in raw_items:
        cleaned = clean_hashtag_value(str(item).lstrip("#"))
        if cleaned and cleaned not in hashtags:
            hashtags.append(cleaned)

    return hashtags[:6]


def hashtag_from_phrase(phrase):
    words = re.findall(r"[A-Za-z0-9]+", remove_vietnamese_accents(str(phrase)).title())
    return f"#{''.join(words)}" if words else ""


def product_profile(product, content_brief=""):
    product_text = remove_vietnamese_accents(str(product)).lower()
    context_text = remove_vietnamese_accents(str(content_brief)).lower()
    combined_text = f"{product_text} {context_text}"
    power_quality_markers = [
        "dpfhmf",
        "dien nang thong minh",
        "chat luong dien nang",
        "power quality",
        "thdv",
        "thdi",
        "pf va dpf",
        "pf/dpf",
        "maximum demand",
        "modbus rtu",
        "scada",
        "ems",
        "bms",
        "song hai den bac 50",
    ]
    if any(marker in combined_text for marker in power_quality_markers):
        return {
            "key": "power_quality_meter",
            "terms": [
                "dong ho dien nang",
                "chat luong dien nang",
                "power quality",
                "thdv",
                "thdi",
                "song hai",
                "demand",
                "modbus",
                "scada",
                "ems",
                "bms",
            ],
            "label": "đồng hồ phân tích chất lượng điện năng",
            "hashtags": ["#DongHoDienNang", "#ChatLuongDienNang", "#SongHai", "#ModbusRTU"],
            "queries": [
                "đồng hồ phân tích chất lượng điện năng 3 pha",
                "PF và DPF khác nhau thế nào",
                "phân tích sóng hài THDv THDi bậc 50",
                "Demand Maximum Demand trong quản lý điện năng",
                "giám sát mất cân bằng điện áp dòng điện",
                "đồng hồ điện RS485 Modbus RTU SCADA",
                "quản lý điện năng 6 biểu giá",
                "giám sát điện năng nhà máy EMS BMS",
            ],
            "cta": "Gửi sơ đồ hệ thống, loại tải đang dùng (biến tần/UPS/tải phi tuyến), nhu cầu theo dõi sóng hài, Demand hoặc kết nối SCADA/EMS/BMS để được tư vấn cấu hình phù hợp.",
            "image_checks": "mã MT-DPFHMF_CD2, hệ thống điện 3 pha, loại tải, sơ đồ đấu nối, tỷ số CT nếu sử dụng CT ngoài, nhu cầu RS485 Modbus, SCADA/EMS/BMS, các chỉ số PF/DPF, THDv/THDi và Demand cần giám sát",
            "verified_specs": (
                "Đo điện áp pha/dây, dòng từng pha và dòng trung tính, tần số, góc pha, "
                "kW, kVAR, kVA, PF và DPF; đo kWh, kVARh, kVAh và điện năng phát ngược; "
                "phân tích THDv/THDi và sóng hài đến bậc 50; giám sát mất cân bằng pha, "
                "Max/Min, Demand/Maximum Demand; quản lý 6 biểu giá; có RTC, bộ nhớ, relay cảnh báo "
                "và RS485 Modbus RTU tối đa 115200bps; kết nối SCADA, EMS, BMS, PLC và IoT."
            ),
            "avoid_terms": [
                "quạt cũ",
                "lưới lọc",
                "vị trí bắt vít",
                "chọn CT cho đồng hồ" ,
                "biến dòng CT là gì",
            ],
        }
    group_markers = {
        "fan": ["quat", "fan", "thong gio", "lam mat", "tam loc gio", "luoi loc"],
        "capacitor": ["tu bu", "cos phi", "cong suat phan khang", "kvar"],
        "protection": ["mccb", "aptomat", "relay", "contactor", "cau chi", "ngan mach", "qua tai"],
        "meter": ["dong ho", "meter", "ct", "bien dong", "do luong", "giam sat dien"],
        "reactor": ["cuon khang", "reactor", "song hai"],
        "thermal_control": ["bo on nhiet", "thermostat", "dien tro suoi", "heater"],
        "control": ["den bao", "nut nhan", "cong tac xoay", "selector switch", "push button"],
        "busbar": ["busbar", "thanh cai", "su do", "goi do", "thanh do"],
        "transformer": ["may bien ap", "bien ap", "transformer"],
    }
    matched_groups = [
        group
        for group, terms in group_markers.items()
        if any(term in product_text for term in terms)
    ]
    if len(matched_groups) >= 2:
        return {
            "key": "catalog",
            "terms": [],
            "label": "danh mục phụ kiện/thiết bị tủ điện",
            "hashtags": ["#PhuKienTuDien", "#ThietBiDien", "#TuDienCongNghiep", "#MasterElectric"],
            "queries": [
                "phụ kiện tủ điện công nghiệp gồm những gì",
                "thiết bị trong tủ điện công nghiệp",
                "checklist bảo trì tủ điện công nghiệp",
                "giải pháp làm mát bảo vệ đo lường tủ điện",
            ],
            "cta": "Gửi ảnh tủ điện, nhóm thiết bị đang cần kiểm tra hoặc mã/tem cũ, shop hỗ trợ gợi ý đúng nhóm sản phẩm trước khi chọn mã.",
            "image_checks": "nhu cầu trong tủ, ảnh tổng thể tủ điện, tem/mã thiết bị cũ, vị trí lắp, điện áp/dòng/công suất nếu có",
            "avoid_terms": [],
        }
    profiles = [
        {
            "key": "capacitor",
            "terms": ["tu bu", "cos phi", "cong suat phan khang", "kvar", "capacitor"],
            "label": "tụ bù",
            "hashtags": ["#TuBuKho", "#TuBuMikro", "#CosPhi", "#TuBuCongNghiep"],
            "queries": [
                "dấu hiệu tụ bù bị hỏng",
                "cos phi thấp bị phạt tiền điện",
                "cách chọn tụ bù theo kVAr",
                "khi nào cần cuộn kháng cho tụ bù",
                "sóng hài làm hỏng tụ bù",
                "tủ tụ bù đóng cắt không ổn định",
            ],
            "cta": "Gửi ảnh tủ tụ bù, tem tụ cũ, thông tin kVAr hoặc hóa đơn điện, shop hỗ trợ đối chiếu hướng chọn phù hợp.",
            "image_checks": "tem thông số, dung lượng kVAr, contactor, bộ điều khiển tụ, dấu hiệu tụ phồng/chảy dầu nếu có",
            "avoid_terms": ["quạt cũ", "quạt tủ điện", "quạt thông gió", "lưới lọc", "vị trí bắt vít", "hướng gió", "120x120x38", "EA12038S"],
        },
        {
            "key": "fan",
            "terms": ["quat", "fan", "thong gio", "lam mat"],
            "label": "quạt tủ điện",
            "hashtags": ["#QuatTuDien", "#QuatTanNhiet", "#TuDien", "#ThietBiDien"],
            "queries": [
                "cách chọn quạt tủ điện theo kích thước",
                "tủ điện nóng nên thay quạt hay lắp thêm lọc",
                "quạt lọc tủ điện chống quá nhiệt",
                "dấu hiệu quạt tủ điện yếu",
            ],
            "cta": "Gửi ảnh quạt cũ, tem thông số, kích thước hoặc vị trí lắp, shop hỗ trợ đối chiếu đúng mẫu trước khi đặt.",
            "image_checks": "tem thông số, nguồn điện, kích thước, vị trí bắt vít, hướng gió, lưới lọc",
            "avoid_terms": [],
        },
        {
            "key": "reactor",
            "terms": ["cuon khang", "reactor", "song hai"],
            "label": "cuộn kháng",
            "hashtags": ["#CuonKhang", "#SongHai", "#TuBu", "#ThietBiDien"],
            "queries": [
                "khi nào cần dùng cuộn kháng cho tụ bù",
                "cuộn kháng lọc sóng hài là gì",
                "cách chọn cuộn kháng cho biến tần",
                "sóng hài ảnh hưởng tụ bù như thế nào",
            ],
            "cta": "Gửi ảnh hệ thống, thông số tải/biến tần hoặc tủ tụ bù, shop hỗ trợ kiểm tra có cần cuộn kháng không.",
            "image_checks": "tem thông số, điện áp, dòng định mức, vị trí lắp trong tủ, tải có biến tần hay không",
            "avoid_terms": ["quạt cũ", "quạt tủ điện", "lưới lọc", "120x120x38", "EA12038S"],
        },
        {
            "key": "protection",
            "terms": ["mccb", "aptomat", "relay", "contactor", "khoi dong tu", "ngan mach", "qua tai", "dong dinh muc", "kha nang cat"],
            "label": "thiết bị bảo vệ/đóng cắt",
            "hashtags": ["#MCCB", "#ThietBiDien", "#BaoVeDien", "#TuDien"],
            "queries": [
                "cách chọn MCCB theo dòng tải",
                "MCCB hay nhảy nguyên nhân",
                "khả năng cắt kA của MCCB là gì",
                "MCCB bảo vệ quá tải ngắn mạch như thế nào",
                "chọn MCCB 3P cho tủ điện công nghiệp",
                "thiết bị bảo vệ tủ điện công nghiệp",
            ],
            "cta": "Gửi ảnh tem MCCB cũ, dòng tải, số cực, điện áp làm việc hoặc khả năng cắt kA, shop hỗ trợ đối chiếu mẫu phù hợp.",
            "image_checks": "tem thông số, dòng định mức A, số cực, điện áp làm việc, khả năng cắt kA/Icu/Ics, vị trí lắp trong tủ",
            "avoid_terms": ["quạt cũ", "lưới lọc", "hướng gió", "120x120x38", "EA12038S"],
        },
        {
            "key": "meter",
            "terms": ["dong ho", "meter", "ct", "bien dong", "do luong", "giam sat dien"],
            "label": "thiết bị đo/giám sát điện",
            "hashtags": ["#DongHoDien", "#BienDongCT", "#GiamSatDien", "#TuDien"],
            "queries": [
                "biến dòng CT là gì",
                "cách chọn CT cho đồng hồ điện",
                "đồng hồ đo điện đa năng trong tủ điện",
                "giám sát điện năng nhà xưởng",
            ],
            "cta": "Gửi thông số CT, tỷ số biến dòng, sơ đồ đấu nối hoặc ảnh đồng hồ cũ, shop hỗ trợ đối chiếu trước khi đặt.",
            "image_checks": "tỷ số CT, sơ đồ đấu dây, mã đồng hồ, nguồn nuôi, vị trí lắp",
            "avoid_terms": ["quạt cũ", "quạt tủ điện", "lưới lọc", "120x120x38", "EA12038S"],
        },
        {
            "key": "thermal_control",
            "terms": ["bo on nhiet", "thermostat", "dien tro suoi", "heater", "chong am"],
            "label": "điều khiển nhiệt độ/điện trở sưởi tủ điện",
            "hashtags": ["#BoOnNhiet", "#DienTroSuoi", "#TuDien", "#ThietBiDien"],
            "queries": [
                "cách chọn thermostat cho tủ điện",
                "điện trở sưởi chống ẩm tủ điện",
                "kiểm soát nhiệt độ độ ẩm trong tủ điện",
                "thermostat điều khiển quạt tủ điện",
            ],
            "cta": "Gửi ảnh tủ, dải nhiệt cần kiểm soát, điện áp và thiết bị cần đóng cắt, shop hỗ trợ đối chiếu bộ ổn nhiệt phù hợp.",
            "image_checks": "dải nhiệt, điện áp, tiếp điểm điều khiển, vị trí lắp DIN rail, nhu cầu làm mát hoặc chống ẩm",
            "avoid_terms": ["thermostat ô tô", "bình nóng lạnh", "tủ lạnh gia đình"],
        },
        {
            "key": "control",
            "terms": ["den bao", "nut nhan", "cong tac xoay", "selector switch", "push button"],
            "label": "đèn báo/nút nhấn/công tắc tủ điện",
            "hashtags": ["#NutNhan", "#DenBao", "#CongTacXoay", "#TuDien"],
            "queries": [
                "cách chọn đèn báo tủ điện theo điện áp",
                "nút nhấn công nghiệp NO NC là gì",
                "công tắc xoay tủ điều khiển",
                "selector switch tủ điện công nghiệp",
            ],
            "cta": "Gửi ảnh mặt tủ, điện áp đèn báo, đường kính lỗ khoét và yêu cầu tiếp điểm NO/NC, shop hỗ trợ đối chiếu.",
            "image_checks": "điện áp, màu đèn, đường kính lỗ khoét, số vị trí công tắc, tiếp điểm NO/NC",
            "avoid_terms": ["công tắc gia đình", "đồ chơi", "ô tô", "xe máy"],
        },
        {
            "key": "busbar",
            "terms": ["busbar", "thanh cai", "su do", "goi do", "thanh do"],
            "label": "sứ đỡ/thanh đỡ Busbar",
            "hashtags": ["#Busbar", "#ThanhCai", "#SuDo", "#TuDienCongNghiep"],
            "queries": [
                "cách chọn sứ đỡ thanh cái tủ điện",
                "khoảng cách lắp thanh cái busbar",
                "thanh đỡ busbar tủ điện công nghiệp",
                "cách điện thanh cái trong tủ điện",
            ],
            "cta": "Gửi kích thước thanh cái, dòng tải, khoảng cách lắp và ảnh bố trí trong tủ, shop hỗ trợ chọn sứ/thanh đỡ phù hợp.",
            "image_checks": "kích thước thanh cái, số pha, khoảng cách lắp, dòng tải, vị trí bắt bulông",
            "avoid_terms": ["busbar ô tô", "thanh trang trí", "đồ nội thất"],
        },
        {
            "key": "transformer",
            "terms": ["may bien ap", "bien ap", "transformer"],
            "label": "máy biến áp công nghiệp",
            "hashtags": ["#MayBienAp", "#BienAp", "#ThietBiDien", "#CongNghiep"],
            "queries": [
                "cách chọn máy biến áp công nghiệp",
                "máy biến áp điều khiển trong tủ điện",
                "chọn công suất VA máy biến áp",
                "điện áp sơ cấp thứ cấp máy biến áp",
            ],
            "cta": "Gửi điện áp vào/ra, công suất tải VA và ứng dụng thực tế, shop hỗ trợ đối chiếu máy biến áp phù hợp.",
            "image_checks": "điện áp sơ cấp/thứ cấp, công suất VA, tần số, kiểu lắp và tải sử dụng",
            "avoid_terms": ["đồ chơi", "âm thanh", "sạc điện thoại"],
        },
    ]
    for profile in profiles:
        if any(term in product_text for term in profile["terms"]):
            return profile
    for profile in profiles:
        if context_text and any(term in context_text for term in profile["terms"]):
            return profile
    return {
        "key": "generic",
        "terms": [],
        "label": "sản phẩm kỹ thuật",
        "hashtags": ["#ThietBiDien", "#TuVanKyThuat", "#HangChinhHang", "#CongNghiep"],
        "queries": [
            "cách chọn thiết bị điện công nghiệp",
            "thiết bị điện công nghiệp chính hãng",
            "checklist mua thiết bị điện cho nhà xưởng",
        ],
        "cta": "Gửi ảnh tem, thông số đang dùng hoặc tình trạng thực tế, shop hỗ trợ đối chiếu trước khi đặt.",
        "image_checks": "tem thông số, mã hàng, điện áp/dòng/công suất, vị trí lắp và tình trạng thực tế",
        "avoid_terms": [],
    }


def product_specific_cta(product, content_brief=""):
    return product_profile(product, content_brief)["cta"]


def extract_brand_label(content_brief=""):
    for line in str(content_brief).splitlines():
        normalized_line = remove_vietnamese_accents(line).lower().strip(" -")
        if normalized_line.startswith("ten shop/thuong hieu:"):
            brand = line.split(":", 1)[1].strip(" -") if ":" in line else ""
            normalized_brand = remove_vietnamese_accents(brand).lower()
            looks_like_audience = any(
                word in normalized_brand
                for word in ["tho dien", "ky thuat", "bao tri", "chu xuong", "khach hang", "don vi thi cong"]
            )
            if brand and len(brand) <= 70 and not looks_like_audience:
                return brand
    return DEFAULT_BRAND_LABEL


def has_company_footer(caption):
    normalized = remove_vietnamese_accents(str(caption)).lower()
    return (
        "cong ty tnhh thuong mai ky thuat thien loc phat" in normalized
        or "masterelectric.com.vn" in normalized
        or "0901104339" in normalized
    )


def append_company_footer(caption):
    caption = str(caption).strip()
    if not caption or has_company_footer(caption):
        return caption
    return f"{caption}\n\n{DEFAULT_COMPANY_FOOTER}"


def caption_conflicts_product(caption, product, content_brief=""):
    profile = product_profile(product, content_brief)
    normalized = remove_vietnamese_accents(caption).lower()
    return any(term in normalized for term in profile.get("avoid_terms", []))


def fallback_hashtags(product, audience=""):
    profile = product_profile(product)
    normalized_product = remove_vietnamese_accents(product).lower()
    if profile["key"] == "power_quality_meter":
        tags = [
            "#MTDPFHMFCD2" if "dpfhmf" in normalized_product else "#DongHoDienNang",
            "#ChatLuongDienNang",
            "#PhanTichSongHai",
            "#QuanLyDienNang",
            "#ModbusRTU",
            "#GiamSatDienNang",
        ]
        return tags[:6]
    if profile["key"] == "protection" and "mccb" in normalized_product:
        protection_tags = ["#MCCB"]
        if "schneider" in normalized_product:
            protection_tags.append("#MCCBSchneider")
        if "3p" in normalized_product or "3 pha" in normalized_product:
            protection_tags.append("#MCCB3P")
        protection_tags.extend(["#ThietBiDienCongNghiep", "#TuDienCongNghiep", "#BaoVeQuaTai", "#BaoVeNganMach"])
        return protection_tags[:6]

    product_words = [
        word
        for word in re.findall(r"[A-Za-z0-9]+", remove_vietnamese_accents(product))
        if len(word) >= 3 and word.lower() not in {"ban", "cho", "voi", "hang", "san", "pham", "all"}
    ]
    product_code = next((word.upper() for word in product_words if re.search(r"\d", word)), "")
    descriptive_words = [word for word in product_words if word.upper() != product_code]
    compact_product = "".join(word.title() for word in descriptive_words[:4])

    audience_text = remove_vietnamese_accents(audience).lower()
    audience_tag = ""
    if "tho dien" in audience_text:
        audience_tag = "#ThoDien"
    elif "bao tri" in audience_text or "ky thuat" in audience_text:
        audience_tag = "#KyThuatBaoTri"
    elif "dai ly" in audience_text:
        audience_tag = "#DaiLyThietBiDien"
    elif audience and len(str(audience).split()) <= 3 and audience.lower() != "all":
        audience_tag = hashtag_from_phrase(audience)

    base = [
        f"#{product_code}" if product_code else "",
        *profile["hashtags"],
        clean_hashtag_value(compact_product),
        audience_tag,
        "#TuDien" if "tu dien" in remove_vietnamese_accents(product).lower() else "",
        "#ThietBiDien" if any(word in remove_vietnamese_accents(product).lower() for word in ["dien", "master", "quat", "tu bu", "mccb"]) else "",
        "#HangChinhHang",
    ]

    hashtags = []
    for item in base:
        cleaned = clean_hashtag_value(item.lstrip("#"))
        if cleaned and cleaned not in hashtags:
            hashtags.append(cleaned)

    return hashtags[:4]


def build_content_brief(product_specs, customer_problem, proof_points, offer_info, differentiator, brand_voice, content_goal, source_material="", brand_name=""):
    brief_parts = [
        f"Mục tiêu bài viết: {content_goal}",
        f"Giọng thương hiệu: {brand_voice}",
    ]
    optional_parts = [
        ("Tên shop/thương hiệu", brand_name),
        ("Thông số/đặc điểm bắt buộc", product_specs),
        ("Nỗi đau hoặc nhu cầu khách hàng", customer_problem),
        ("Bằng chứng được phép dùng", proof_points),
        ("Ưu đãi/chính sách được phép nhắc", offer_info),
        ("Điểm khác biệt so với bài ChatGPT chung chung", differentiator),
        ("Nguồn vào/link/feedback/câu hỏi cần khai thác", source_material),
    ]
    for label, value in optional_parts:
        if str(value).strip():
            brief_parts.append(f"{label}: {str(value).strip()}")
    return "\n".join(f"- {part}" for part in brief_parts)


def build_strategy_context(enable_b2b_playbook, weekly_frequency, content_mix, format_focus):
    if not enable_b2b_playbook:
        return ""

    return f"""
{B2B_ELECTRICAL_PLAYBOOK}

Chiến lược áp dụng cho lần tạo nội dung này:
- Nhịp đăng mục tiêu: {weekly_frequency}
- Trụ cột nội dung ưu tiên: {content_mix}
- Định dạng ưu tiên: {format_focus}
- Mỗi bài nên có vai trò trong phễu: kéo chú ý, tư vấn, xây niềm tin, hoặc chốt inbox.
- Caption phải mở bằng nỗi đau/tình huống thật trước khi nói tên sản phẩm nếu phù hợp.
- CTA nên cụ thể: gửi ảnh tủ điện, gửi tem thông số, inbox công suất/kích thước, hỏi còn hàng/bảo hành.
- Nếu mục tiêu là quảng bá công ty/tăng follower, không viết 100% bài bán hàng. Hãy chia mix:
  60% kiến thức kỹ thuật dễ lưu/chia sẻ, 25% bán hàng mềm theo sản phẩm/nhu cầu, 15% thương hiệu/hậu trường/năng lực công ty.
- Trong 5-7 bài, phải có ít nhất 1 bài giới thiệu công ty/kho/quy trình tư vấn hoặc lý do nên theo dõi page.
- Nội dung tăng follow phải cho người đọc lý do ở lại page: kiến thức chọn đúng thiết bị, checklist bảo trì, cảnh báo lỗi thường gặp, Q&A dễ hiểu.
""".strip()


def build_content_machine_context(selected_machines):
    if not selected_machines:
        return ""

    machine_lookup = {
        remove_vietnamese_accents(machine).lower(): (machine, description)
        for machine, description in CONTENT_MACHINES.items()
    }
    lines = [
        "Máy tạo nội dung được phép dùng:",
        "Khi viết, hãy chọn đúng máy phù hợp với từng bài và ghi rõ vai trò/góc hook. Không copy nguyên văn nguồn, chỉ biến thành insight hoặc bài mới.",
    ]
    for selected_machine in selected_machines:
        lookup_key = remove_vietnamese_accents(str(selected_machine)).lower()
        machine, description = machine_lookup.get(lookup_key, (selected_machine, ""))
        if description:
            lines.append(f"- {machine}: {description}")
    return "\n".join(lines)


def local_content_playbook(product, audience, weekly_frequency, content_mix, format_focus):
    clean_product = short_product_name(product) or "sản phẩm"
    profile = product_profile(product)
    clean_audience = audience.strip() or "khách kỹ thuật"
    hooks = [
        "Tủ điện nóng bất thường? Đừng vội thay linh kiện khi chưa kiểm tra phần làm mát.",
        f"Chọn sai {clean_product} là mất thời gian tháo ra đổi lại, nhất là khi tủ đang cần chạy ổn định.",
        "Một lỗi nhỏ trong tủ điện có thể kéo theo cả hệ thống vận hành chập chờn.",
        "Anh em kỹ thuật thường không sợ thiếu lựa chọn, chỉ sợ chọn nhầm thông số.",
        "Trước khi chốt hàng, kiểm tra đúng mã - đúng nguồn - đúng kích thước vẫn là bước đáng tiền nhất.",
    ]
    ctas = [
        "Gửi ảnh tem hoặc ảnh tủ điện, shop đối chiếu giúp trước khi đặt.",
        "Inbox mã hàng/thông số đang dùng để được tư vấn mẫu phù hợp.",
        "Cần thay nhanh đúng mã, nhắn shop kiểm tra tồn kho và thông số.",
        "Chưa chắc chọn loại nào, gửi hiện trạng tủ để shop gợi ý cấu hình.",
    ]
    reels = [
        f"Reels 15s: quay cận ảnh {clean_product}, text mở đầu bằng nỗi đau thật của nhóm {profile['label']}, sau đó hiện 3 điểm cần kiểm tra.",
        f"Reels 20s: format lỗi thường gặp khi chọn {profile['label']} sai thông số, cuối video nhắc inbox để đối chiếu trước khi chốt.",
        "Reels 30s: quay theo kiểu checklist kỹ thuật: ảnh sản phẩm, tem thông số, vị trí lắp, ứng dụng trong tủ điện, CTA hỏi tư vấn.",
        "Reels 20s: hậu trường kiểm hàng/đóng hàng/kho sản phẩm, text nhấn mạnh quy trình tư vấn đúng mã trước khi giao.",
    ]
    schedule = [
        ("Thứ 2", "Kiến thức dễ lưu/Q&A nhanh", "Tăng follow và save"),
        ("Thứ 3", "Bài sản phẩm cụ thể theo nhu cầu", "Tạo nhu cầu"),
        ("Thứ 4", "Hậu trường kho/quy trình tư vấn", "Xây niềm tin công ty"),
        ("Thứ 5", "Reels/checklist ngắn", "Tăng reach"),
        ("Thứ 6 hoặc 7", "Bài kéo inbox/tư vấn theo ảnh tem", "Tạo lead"),
    ]
    return {
        "summary": f"Khuyến nghị cho {clean_audience}: {weekly_frequency}, ưu tiên {content_mix}, định dạng {format_focus}.",
        "hooks": hooks,
        "ctas": ctas,
        "reels": reels,
        "schedule": schedule,
    }


def image_recommendation_for_machine(content_machine, product=""):
    clean_product = short_product_name(product) or "sản phẩm"
    profile = product_profile(product)
    machine = remove_vietnamese_accents(content_machine).lower()
    default = [
        f"Ảnh sản phẩm {clean_product} rõ mặt chính/tem thông số.",
        "Ảnh cận chi tiết quan trọng để khách đối chiếu trước khi mua.",
        f"Ảnh ứng dụng thực tế hoặc ảnh mô phỏng vị trí lắp/dùng, ưu tiên thấy rõ {profile['image_checks']}.",
    ]

    recommendations = {
        "su co": [
            "Ảnh/screenshot nguồn tin sự cố công khai, che thông tin nhạy cảm nếu cần.",
            "Ảnh minh họa tủ điện quá nhiệt/cháy sém/bụi bẩn nếu có quyền dùng.",
            f"Ảnh sản phẩm/thiết bị liên quan trực tiếp như {clean_product}, ưu tiên thấy rõ {profile['image_checks']}.",
        ],
        "tin tuc": [
            "Screenshot tiêu đề tin ngành/EVN/báo công nghiệp kèm nguồn rõ ràng.",
            "Ảnh sản phẩm/giải pháp liên quan đặt bên cạnh để nối với nhu cầu thực tế.",
            "Ảnh infographic ngắn: vấn đề -> thiết bị nên kiểm tra.",
        ],
        "bai bao": [
            "Screenshot bài khách/đối tác/cộng đồng đã nhắc đến sản phẩm hoặc thương hiệu.",
            f"Ảnh sản phẩm {clean_product} đang được nhắc tới.",
            "Ảnh cảm ơn dạng đơn giản: logo/shop + sản phẩm + câu cảm ơn ngắn.",
        ],
        "case study": [
            "Ảnh công trình/tủ điện thực tế trước hoặc sau khi lắp.",
            "Ảnh cận sản phẩm trong tủ điện, thấy vị trí lắp và dây/khung nếu có.",
            "Ảnh tem/mã/thông số để tăng độ tin cậy.",
        ],
        "so sanh": [
            "Ảnh trước/sau đặt cạnh nhau: tủ cũ - tủ đã xử lý, thiết bị cũ - thiết bị mới.",
            "Ảnh chi tiết lỗi cũ: bụi, nóng, rỉ, quạt yếu, tụ phồng nếu có.",
            f"Ảnh sản phẩm thay thế: {clean_product}.",
        ],
        "checklist": [
            "Ảnh dạng checklist 3-5 dòng ngắn, ít chữ, dễ đọc trên điện thoại.",
            f"Ảnh sản phẩm {clean_product} làm hình nền/phụ họa.",
            f"Ảnh cận điểm cần kiểm tra: {profile['image_checks']}.",
        ],
        "thuat ngu": [
            "Ảnh infographic giải thích thuật ngữ bằng sơ đồ đơn giản.",
            "Ảnh sản phẩm liên quan tới thuật ngữ đó.",
            "Ảnh ví dụ thực tế trong tủ điện để người mới dễ hình dung.",
        ],
        "myth": [
            "Ảnh text hook kiểu 'Đừng mua nếu chưa kiểm tra 3 điểm này'.",
            "Ảnh so sánh lựa chọn sai và lựa chọn đúng.",
            f"Ảnh sản phẩm {clean_product} kèm điểm cần đối chiếu.",
        ],
        "bang chon": [
            "Ảnh bảng chọn nhanh 2-4 cột, chữ ngắn, ưu tiên dễ đọc.",
            "Ảnh sản phẩm theo từng nhóm/mã nếu có.",
            "Ảnh CTA: gửi thông số để shop chọn mã phù hợp.",
        ],
        "mua vu": [
            "Ảnh theo mùa: tủ điện nóng/mùa nắng, hơi ẩm/mùa mưa, checklist bảo trì cuối năm.",
            f"Ảnh sản phẩm {clean_product} liên quan trực tiếp đến mùa đó.",
            "Ảnh thực tế nhà xưởng/tủ điện nếu có quyền dùng.",
        ],
        "chinh sach": [
            "Screenshot/tóm tắt nguồn quy chuẩn hoặc tin chính sách, chỉ lấy phần công khai.",
            "Ảnh thiết bị bảo vệ/đo lường/làm mát liên quan.",
            "Ảnh checklist kiểm tra an toàn cho doanh nghiệp.",
        ],
        "review": [
            f"Ảnh sản phẩm {clean_product} từ nhiều góc.",
            "Ảnh cận tem, thông số, phụ kiện đi kèm.",
            "Ảnh tình huống sử dụng: tủ ngoài trời, xưởng nhiều biến tần, tủ tụ bù.",
        ],
        "cau hoi": [
            "Screenshot câu hỏi inbox/comment đã che tên/số điện thoại khách.",
            f"Ảnh sản phẩm {clean_product} hoặc thiết bị được tư vấn trong câu trả lời.",
            f"Ảnh minh họa thông tin khách cần gửi: {profile['image_checks']}.",
        ],
        "bat trend": [
            "Ảnh hook ngắn dạng trend: '3 dấu hiệu...', 'Đừng mua nếu...'.",
            f"Ảnh sản phẩm {clean_product} rõ ràng, không quá nhiều chữ.",
            "Ảnh/Reels quay thao tác chỉ điểm kiểm tra nhanh.",
        ],
        "cam on": [
            "Screenshot bài đăng/feedback của khách hoặc đối tác, che thông tin riêng tư nếu cần.",
            f"Ảnh sản phẩm {clean_product} được khách nhắc tới hoặc sản phẩm liên quan.",
            "Ảnh cảm ơn đơn giản: sản phẩm + logo/shop + dòng 'Cảm ơn anh/chị đã tin dùng'.",
        ],
        "hang gia": [
            "Ảnh so sánh hàng chính hãng và dấu hiệu hàng kém chất lượng nếu có bằng chứng.",
            "Ảnh CO/CQ, tem, bao bì, phiếu bảo hành nếu được phép công khai.",
            f"Ảnh cận tem/thông số của {clean_product}.",
        ],
        "mini": [
            "Ảnh bìa series có số tập/ngày rõ ràng.",
            "Ảnh thống nhất template để khách nhận ra đây là chuỗi nội dung.",
            f"Ảnh sản phẩm/chủ đề chính của series: {clean_product}.",
        ],
        "keo inbox": [
            f"Ảnh CTA rõ, bám hành động: {profile['cta']}",
            f"Ảnh sản phẩm {clean_product} + 3 thông tin khách cần gửi: {profile['image_checks']}.",
            "Ảnh ví dụ tin nhắn/câu hỏi mẫu, che thông tin riêng tư.",
        ],
        "gioi thieu": [
            "Ảnh bìa fanpage/ảnh đội ngũ/kho hàng hoặc logo công ty đặt cạnh nhóm sản phẩm chính.",
            "Ảnh collage 4 nhóm sản phẩm công ty cung cấp: làm mát tủ, bù công suất, bảo vệ, đo lường/phụ kiện.",
            "Ảnh quy trình tư vấn ngắn: nhận ảnh tem -> đối chiếu thông số -> báo mẫu phù hợp.",
        ],
        "hau truong": [
            "Ảnh kho hàng, kệ sản phẩm, đóng gói đơn hoặc kiểm tem/mã trước khi giao.",
            f"Ảnh cận {clean_product} đang được kiểm tra tem/thông số.",
            "Ảnh thao tác chuẩn bị đơn hàng đã che thông tin riêng tư của khách.",
        ],
        "q&a": [
            "Ảnh nền đơn giản dạng hỏi đáp: 1 câu hỏi lớn, 1 câu trả lời ngắn.",
            f"Ảnh sản phẩm hoặc chi tiết cần kiểm tra: {profile['image_checks']}.",
            "Ảnh minh họa trong tủ điện để người mới dễ hiểu câu trả lời.",
        ],
        "tang follow": [
            "Ảnh checklist/bảng nhớ nhanh ít chữ để khách lưu lại.",
            "Ảnh bìa mini-series có số tập rõ ràng, cùng template để nhận diện page.",
            "Ảnh CTA nhẹ: follow page để xem thêm checklist chọn thiết bị tủ điện.",
        ],
        "ban do": [
            "Ảnh sơ đồ nhu cầu trong tủ điện: làm mát, bù công suất, bảo vệ, đo lường, phụ kiện.",
            "Ảnh nhóm sản phẩm đặt theo từng nhu cầu để khách nhìn nhanh.",
            "Ảnh bảng gợi ý: gặp vấn đề gì -> nên kiểm tra nhóm thiết bị nào.",
        ],
        "combo": [
            "Ảnh bộ giải pháp theo tình huống, ví dụ tủ nóng gồm quạt/lưới lọc/thermostat/chống ẩm nếu có.",
            "Ảnh trước/sau hoặc ảnh bố trí các thiết bị trong tủ.",
            "Ảnh CTA: gửi ảnh tủ để shop gợi ý bộ thiết bị cần kiểm tra.",
        ],
    }

    for key, value in recommendations.items():
        if key in machine:
            return "\n".join(f"- {item}" for item in value)

    return "\n".join(f"- {item}" for item in default)


def ensure_image_guidance(post, product=""):
    if post.get("image_guidance", "").strip():
        return post
    post["image_guidance"] = image_recommendation_for_machine(post.get("content_machine", ""), product)
    return post


def infer_content_machine_from_brief(content_brief, fallback=""):
    normalized = remove_vietnamese_accents(content_brief).lower()
    for machine in CONTENT_MACHINES:
        machine_key = remove_vietnamese_accents(machine).lower()
        if machine_key in normalized:
            return machine
    if fallback:
        return fallback
    if any(word in normalized for word in ["su co", "chay", "chap dien", "qua nhiet", "an toan"]):
        return "Sự cố & bài học an toàn"
    if any(word in normalized for word in ["tin tuc", "evn", "phu tai", "tiet kiem dien"]):
        return "Tin tức ngành điện"
    if "checklist" in normalized:
        return "Checklist kỹ thuật"
    if any(word in normalized for word in ["cam on", "ghi nhan", "feedback"]):
        return "Cảm ơn/ghi nhận"
    return ""


def selected_machines_from_brief(content_brief):
    exact_machines = []
    machine_lookup = {
        remove_vietnamese_accents(machine).lower(): machine
        for machine in CONTENT_MACHINES
    }
    for raw_machine in re.findall(r"(?m)^-\s*([^:\n]+):", content_brief):
        machine = machine_lookup.get(remove_vietnamese_accents(raw_machine.strip()).lower())
        if machine and machine not in exact_machines:
            exact_machines.append(machine)
    if exact_machines:
        return exact_machines

    normalized = remove_vietnamese_accents(content_brief).lower()
    machines = []
    for machine in CONTENT_MACHINES:
        machine_key = remove_vietnamese_accents(machine).lower()
        if machine_key in normalized:
            machines.append(machine)
    return machines


def fallback_machine_for_index(content_brief, index, fallback=""):
    machines = selected_machines_from_brief(content_brief)
    if machines:
        return machines[(index - 1) % len(machines)]
    return infer_content_machine_from_brief(content_brief, fallback)


def content_mission_instruction(selected_machines_text=""):
    return """
Mỗi bài phải có một nhiệm vụ riêng, không được lặp ý giữa các bài.
Nếu tạo 3 bài, hãy chia tối thiểu như sau:
- Bài 1: Kiến thức/Q&A/checklist dễ lưu để người mới có lý do theo dõi page.
- Bài 2: Bán hàng mềm theo tình huống sản phẩm hoặc giải pháp.
- Bài 3: Kéo inbox/chốt lead bằng hành động cụ thể.
Nếu tạo 5-7 bài, thêm các nhiệm vụ: giới thiệu năng lực công ty, hậu trường kho/quy trình tư vấn, review tình huống, myth-busting, case/công trình, Reels kéo reach, bảng chọn nhanh.

Không được để nhiều bài cùng chỉ nói "đúng mã, đúng nguồn, đúng kích thước".
Không được để toàn bộ lịch chỉ là bài sản phẩm. Fanpage công ty cần có bài cho người chưa mua: kiến thức, năng lực, hậu trường, lý do nên follow.
Mỗi bài chỉ được dùng 1 hook chính và 1 CTA chính.
Mỗi bài phải ghi rõ:
- content_role: nhiệm vụ của bài trong phễu.
- hook_angle: góc mở riêng.
- kpi_goal: chỉ số thành công phù hợp.
""".strip()


def human_writing_instruction():
    return """
Phong cách viết bắt buộc:
- Viết như một người bán hàng/kỹ thuật đang tư vấn thật trên Facebook, không viết như báo cáo nội bộ.
- Mở bài bằng tình huống gần đời, câu hỏi ngắn, hoặc nỗi đau khách hay gặp. Tránh mở bài bằng định nghĩa sản phẩm.
- Có nhịp tự nhiên: câu ngắn xen câu vừa, đoạn 2-4 dòng, có thể dùng gạch đầu dòng khi cần khách kiểm tra nhanh.
- Với bài tư vấn kỹ thuật Facebook, ưu tiên format dễ copy đăng: hook mạnh -> giải thích ngắn -> checklist 4-6 dòng dùng icon đúng máy nội dung -> cảnh báo/chốt ý -> CTA cụ thể -> hashtag sát sản phẩm.
- Với MCCB/CB/thiết bị bảo vệ, nếu nói chuyện chọn sai dòng A hoặc MCCB hay nhảy, hãy dùng kiểu: "MCCB cứ chọn dòng A lớn hơn là sẽ đỡ nhảy? Không hẳn." rồi liệt kê dòng tải, số cực, điện áp, khả năng cắt kA/Icu/Ics, kích thước/vị trí lắp.
- Icon phải thay đổi theo content_machine. Không dùng cùng một bộ ❌/✅/👉 cho mọi bài.
- Dùng giọng thân thiện, dễ tiếp cận với cả chủ xưởng, thợ điện, kỹ thuật bảo trì và người mua không quá rành kỹ thuật.
- Không lạm dụng cụm "đúng mã, đúng nguồn, đúng kích thước"; nếu cần nhắc, hãy đặt trong ngữ cảnh khác nhau.
- Không nói quá, không hứa chắc chắn giảm nhiệt/tiết kiệm/không cháy nếu không có bằng chứng.
- Hashtag ngắn, dễ đọc, không ghép cả câu dài thành hashtag.
- Brand trong bài là đơn vị đăng/cung cấp/tư vấn. Không biến brand sản phẩm thành tên page nếu người dùng đã nhập thương hiệu shop.
""".strip()


def machine_caption_icon_instruction():
    icon_lines = [
        f"- {machine}: {' '.join(icons)}"
        for machine, icons in MACHINE_CAPTION_ICONS.items()
    ]
    return """
Quy tắc icon theo máy nội dung:
{icon_lines}

- Mỗi caption mở bằng icon đầu tiên của đúng content_machine.
- Dùng thêm 2-3 icon còn lại cho các ý chính, checklist hoặc CTA.
- Không dùng nguyên một bộ ❌ ✅ 👉 cho mọi caption.
- Emoji vừa phải: khoảng 3-6 icon trong một caption; không đặt icon ở mọi câu.
- Icon phải đứng đầu dòng liên quan và giữ đúng ý nghĩa.
""".strip().format(icon_lines="\n".join(icon_lines))


def engagement_totals(posts):
    totals = {"likes": 0, "comments": 0, "shares": 0, "inboxes": 0, "views": 0}
    for post in posts:
        metrics = post.get("metrics", {})
        for key in totals:
            try:
                totals[key] += int(metrics.get(key, 0) or 0)
            except (TypeError, ValueError):
                pass
    score = totals["likes"] + totals["comments"] * 3 + totals["shares"] * 4 + totals["inboxes"] * 6 + totals["views"] * 0.02
    totals["score"] = round(score, 1)
    return totals


def post_quality_notes(post, product, content_brief=""):
    caption = post.get("caption", "")
    normalized_caption = remove_vietnamese_accents(caption).lower()
    normalized_product = remove_vietnamese_accents(product).lower()
    normalized_brief = remove_vietnamese_accents(content_brief).lower()
    notes = []
    strategy_first = any(
        word in normalized_brief
        for word in ["su co", "bai hoc an toan", "tin tuc nganh dien", "chinh sach", "quy dinh", "tieu chuan"]
    )

    product_tokens = [
        word
        for word in re.findall(r"[a-z0-9]+", normalized_product)
        if len(word) >= 4 and word not in {"hang", "chinh", "dien", "quat", "master"}
    ]
    if product_tokens and not strategy_first and not any(token in normalized_caption for token in product_tokens[:5]):
        notes.append("Caption chưa nhắc rõ mã/tên sản phẩm.")

    generic_phrases = [
        "mon do nhin don gian",
        "lam moi ban than",
        "di choi",
        "gap ban be",
        "phong cach nhe nhang",
        "lua chon de dung moi ngay",
        "chat luong cao",
        "san pham tuyet voi",
        "khong the bo lo",
    ]
    if any(phrase in normalized_caption for phrase in generic_phrases):
        notes.append("Caption còn chung chung, cần gắn vào tình huống sử dụng thật.")

    if any(word in normalized_brief for word in ["tu dien", "ky thuat", "b2b", "cong nghiep", "dien"]) and not any(
        word in normalized_caption for word in ["tu dien", "thiet bi", "linh kien", "nhiet", "lap dat", "bao tri", "dien"]
    ):
        notes.append("Bài chưa đủ chất kỹ thuật/B2B so với brief.")

    if len(caption.strip()) < 180:
        notes.append("Caption hơi ngắn, nên bổ sung lợi ích hoặc ngữ cảnh dùng.")

    return notes[:4]


def hashtag_quality_instruction():
    return """
- Hashtag chỉ đặt cuối bài, không nhồi trong từng đoạn.
- Mỗi bài dùng 3-5 hashtag, ưu tiên hashtag sát sản phẩm, nhu cầu, dịp dùng hoặc nhóm khách hàng.
- Không dùng hashtag mẫu cứng như #NuocHoaMini #MuiHuongMoiNgay nếu không thật sự khớp.
- Không dùng hashtag placeholder như #HashtagSatSanPham #NhuCauKhachHang #GoiYHomNay.
- Không dùng hashtag tiếng Anh chung chung như #TrendyStyle nếu người dùng không yêu cầu.
- Không dùng hashtag vô nghĩa, sai chính tả, quá dài, hoặc nghe như máy dịch.
- Hashtag phải không dấu, chỉ dùng chữ Latin và số.
""".strip()


def caption_style_instruction():
    return """
- Viết như người bán hàng hiểu sản phẩm, không phải copywriter đang viết cho mọi ngành.
- Câu mở đầu phải bám vấn đề thật của khách: chọn sai mã, sai kích thước, thiếu thông số, cần hàng sẵn, cần tư vấn, hoặc cần dùng đúng ngữ cảnh.
- Nếu giọng thương hiệu là Facebook trending/dễ tiếp cận, hãy viết giống bài bán hàng Facebook thật: hook ngắn, emoji vừa phải, câu dễ hiểu cho cả người không chuyên, có vài dòng gạch đầu dòng lợi ích/điểm cần kiểm tra.
- Với sản phẩm kỹ thuật nhưng muốn dễ tiếp cận, không dùng quá nhiều thuật ngữ khô. Hãy giải thích kiểu "gửi tem/thông số cũ shop đối chiếu giúp", "mua đúng thông số để khỏi mất công đổi".
- Nếu sản phẩm là hàng kỹ thuật/B2B, dùng giọng rõ ràng, chắc, có ích. Không cố làm thơ, không lifestyle hóa, không viết kiểu "đẹp", "đi chơi", "làm mới bản thân".
- Nếu sản phẩm là hàng tiêu dùng/lifestyle, có thể gần gũi hơn nhưng vẫn phải có chi tiết cụ thể từ ảnh, brief hoặc research.
- Xen kẽ câu ngắn và câu dài để dễ đọc. Xuống dòng hợp lý, mỗi đoạn 1-3 câu.
- Ưu tiên tư vấn và lọc nhu cầu hơn là khen sản phẩm. Viết sao để khách biết cần hỏi gì trước khi mua.
- CTA phải tạo hành động rõ: inbox gửi mã/thông số/ảnh hiện trạng, hỏi còn hàng, hỏi bảo hành, hỏi tư vấn chọn đúng mẫu.
- KHÔNG dùng các cụm từ sáo rỗng: "chất lượng cao", "giá cả phải chăng", "sản phẩm tuyệt vời", "không thể bỏ lỡ", "đẳng cấp vượt trội".
- KHÔNG dùng giọng văn AI: tránh câu quá trau chuốt, quá đều tay, quá chung chung.
""".strip()


def clean_hashtags_in_text(text):
    def normalize_match(match):
        cleaned = clean_hashtag_value(match.group(1))
        return cleaned

    return re.sub(r"#([^\s,#]+)", normalize_match, text)


def remove_hashtags_from_caption(text):
    text = re.sub(r"(?m)^\s*(#\S+\s*)+$", "", str(text))
    text = re.sub(r"\s*(#\S+)(?=\s|$)", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def contains_cjk(text):
    return bool(re.search(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af]", str(text)))


def strip_non_vietnamese_language_noise(text):
    cleaned_lines = []
    for line in str(text).splitlines():
        sentence_parts = re.split(r"(?<=[.!?。！？])\s+", line)
        kept_parts = []

        for sentence in sentence_parts:
            if contains_cjk(sentence):
                continue
            kept_parts.append(sentence)

        cleaned_lines.append(" ".join(kept_parts))

    text = "\n".join(cleaned_lines)
    text = re.sub(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af]+", "", text)
    text = re.sub(r"[。！？]", "", text)
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()


def strip_markdown_artifacts(text):
    text = str(text)
    text = re.sub(r"(?m)^\s*#{1,6}\s*", "", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"__(.*?)__", r"\1", text)
    return text.strip()


def clean_model_text(text):
    text = strip_non_vietnamese_language_noise(text)
    text = text.replace("[", "").replace("]", "")
    text = strip_markdown_artifacts(text)
    return clean_hashtags_in_text(text)


def remove_image_analysis_voice(text):
    text = str(text)
    patterns = [
        r"(?im)^\s*(anh|hinh|image|photo)\s*\d+\s*[:.-]\s*",
        r"(?im)^\s*(toi thay|trong anh|dua tren anh)[^.\n]*[.:]\s*",
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text)
    return text.strip()


def remove_caption_meta_voice(text):
    text = str(text)
    text = re.sub(r"(?im)^\s*(caption|bai viet|phien ban)\s*\d*\s*[:.-]\s*", "", text)
    text = re.sub(r"(?im)^\s*(goi y|luu y|phan tich|reasoning)\s*[:.-]\s*", "", text)
    return text.strip()


def format_caption_for_facebook(text):
    text = re.sub(r"[ \t]+", " ", str(text)).strip()
    if "\n\n" in text:
        return re.sub(r"\n{3,}", "\n\n", text)

    sentences = re.split(r"(?<=[.!?])\s+", text)
    if len(sentences) <= 2:
        return text

    paragraphs = []
    current = []
    for sentence in sentences:
        current.append(sentence)
        if len(current) >= 2:
            paragraphs.append(" ".join(current).strip())
            current = []
    if current:
        paragraphs.append(" ".join(current).strip())
    return "\n\n".join(part for part in paragraphs if part)


def add_facebook_attention_note(text):
    text = str(text).strip()
    if not text:
        return text
    first_line = text.splitlines()[0].strip()
    if len(first_line) <= 95:
        return text
    parts = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)
    if len(parts) == 2 and len(parts[0]) <= 120:
        return f"{parts[0]}\n\n{parts[1]}".strip()
    return text


def merge_lonely_emoji_paragraphs(text):
    lines = str(text).splitlines()
    merged = []
    for line in lines:
        stripped = line.strip()
        if merged and re.fullmatch(r"[\W_]{1,4}", stripped, flags=re.UNICODE):
            merged[-1] = f"{merged[-1]} {stripped}".strip()
        else:
            merged.append(line)
    return "\n".join(merged).strip()


def normalize_checklist_spacing(text):
    text = str(text)
    content_icons = "🚨⚠️🛡️🔧📰⚡📈🏭📣💬🔎🤝📍🛠️🔄⏪⏩✅🔍📏💡📖⚙️🧠🧨❌📊🌦️🌡️💧🧰📜🏛️📌🎯🎬👀💙🙏🗓️📩🏢📦🧾🚚❓🔖📋➕🧭🧩🔹👉🔥"
    text = re.sub(rf"([^\n])\s*([{content_icons}])", r"\1\n\2", text)
    text = re.sub(rf"(:)\s*([{content_icons}])", r"\1\n\n\2", text)
    text = re.sub(rf"([{content_icons}][^\n]+?)\s+([{content_icons}])", r"\1\n\2", text)
    text = re.sub(
        r"(✅[^\n]*(?:tủ|không|kA|Ics|tải|bảo vệ|thống|mã|trì))\s+(Nguyên nhân|Nếu thay|Chọn MCCB|Đừng thay|Gửi ảnh|MASTER ELECTRIC|CÔNG TY|Nhóm giải pháp|Quy trình|Page sẽ|Các vấn đề|Nếu hệ thống|Cần)",
        r"\1\n\n\2",
        text,
    )
    text = re.sub(r"(❌[^\n]+?)\s+(MASTER ELECTRIC|Nhóm giải pháp|Quy trình|Các vấn đề|Nếu hệ thống)", r"\1\n\n\2", text)
    text = re.sub(r"(🔹[^\n]+?)\s+(🔹|✅|👉)", r"\1\n\n\2", text)
    text = re.sub(r"(✅[^\n]+?)\s+(👉)", r"\1\n\n\2", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def apply_machine_caption_icons(text, content_machine):
    icons = MACHINE_CAPTION_ICONS.get(content_machine)
    if not icons:
        return text

    lines = str(text).splitlines()
    first_text_index = next((index for index, line in enumerate(lines) if line.strip()), None)
    if first_text_index is None:
        return text

    all_machine_icons = {icon for palette in MACHINE_CAPTION_ICONS.values() for icon in palette}
    first_line = lines[first_text_index].strip()
    if not any(first_line.startswith(icon) for icon in all_machine_icons):
        lines[first_text_index] = f"{icons[0]} {first_line}"

    replacements = {
        "❌": icons[1],
        "✅": icons[2],
        "🔹": icons[2],
        "👉": icons[3],
    }
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        prefix_space = line[: len(line) - len(stripped)]
        for old_icon, new_icon in replacements.items():
            if stripped.startswith(old_icon):
                lines[index] = prefix_space + new_icon + stripped[len(old_icon):]
                break

    return normalize_checklist_spacing("\n".join(lines))


def polish_caption_text(text):
    text = clean_model_text(text)
    text = remove_image_analysis_voice(text)
    text = remove_caption_meta_voice(text)
    text = re.sub(r"(?i)\b(duoi day la|toi se|chatgpt|ai)\b", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = format_caption_for_facebook(text)
    text = add_facebook_attention_note(text)
    text = merge_lonely_emoji_paragraphs(text)
    text = normalize_checklist_spacing(text)
    return text.strip()


def safe_filename(filename):
    stem = Path(filename).stem[:50] or "image"
    suffix = Path(filename).suffix.lower() or ".jpg"
    stem = remove_vietnamese_accents(stem)
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", stem).strip("-") or "image"
    return f"{stem}{suffix}"


def cache_uploaded_images(uploaded_images):
    records = []
    for index, uploaded_image in enumerate(uploaded_images or [], start=1):
        image_bytes = uploaded_image.getvalue()
        digest = hashlib.sha1(image_bytes).hexdigest()[:12]
        filename = f"{digest}-{safe_filename(uploaded_image.name)}"
        path = UPLOAD_DIR / filename
        if not path.exists():
            path.write_bytes(image_bytes)

        records.append(
            {
                "label": f"Ảnh {index}",
                "name": uploaded_image.name,
                "path": str(path),
                "digest": digest,
            }
        )

    return records


def clean_search_query(query):
    query = str(query).strip()
    query = re.sub(r"\s+", " ", query)
    query = query.replace("“", '"').replace("”", '"')
    return query[:160]


def master_electric_query(query, product):
    profile_key = product_profile(product)["key"]
    query = clean_search_query(query)[:112].rstrip()
    normalized_query = remove_vietnamese_accents(query).lower()
    context = PROFILE_QUERY_CONTEXT.get(profile_key, PROFILE_QUERY_CONTEXT["generic"])
    if not any(term in normalized_query for term in MASTER_ELECTRIC_INDUSTRIAL_CONTEXT_TERMS):
        query = f"{query} {context}"

    if profile_key == "power_quality_meter":
        return clean_search_query(query)

    negatives = PROFILE_QUERY_NEGATIVES.get(profile_key, PROFILE_QUERY_NEGATIVES["generic"])
    for term in negatives[:5]:
        negative = f'-"{term}"' if " " in term else f"-{term}"
        candidate = f"{query} {negative}"
        if len(candidate) > 160:
            break
        query = candidate
    return clean_search_query(query)


def short_product_name(product):
    text = str(product).strip()
    first_part = re.split(r"[,.;\n]", text, maxsplit=1)[0].strip()
    if first_part:
        text = first_part
    text = re.sub(r"\b(dùng cho|su dung cho|sử dụng cho|phù hợp cho|phu hop cho)\s*$", "", text, flags=re.IGNORECASE).strip()
    words = text.split()
    if len(words) > 8:
        candidate = " ".join(words[:14])
        candidate = re.sub(r"\s+(và|va|hoặc|hoac|để|de)\s*$", "", candidate, flags=re.IGNORECASE).strip()
        candidate = re.sub(r"\b(dùng cho|su dung cho|sử dụng cho|phù hợp cho|phu hop cho)\s*$", "", candidate, flags=re.IGNORECASE).strip()
        return candidate
    return " ".join(words) if words else str(product).strip()


def product_search_terms(product):
    text = short_product_name(product)
    normalized = remove_vietnamese_accents(text).lower()
    words = re.findall(r"[A-Za-z0-9]+", normalized)
    codes = [word.upper() for word in words if re.search(r"\d", word)]
    profile = product_profile(text)

    terms = [text]
    if codes:
        terms.extend(codes)

    terms.extend(profile["queries"])

    if profile["key"] == "power_quality_meter":
        terms = [
            text,
            *profile["queries"],
            "MT-DPFHMF_CD2 thông số",
            "đồng hồ đo PF DPF",
            "đồng hồ phân tích sóng hài bậc 50",
            "đồng hồ giám sát Demand nhà máy",
            "đồng hồ điện đa biểu giá",
            "RS485 Modbus RTU SCADA EMS BMS",
        ]
    elif profile["key"] == "meter" and any(
        marker in normalized
        for marker in ["dien nang thong minh", "dpfhmf", "power quality", "modbus"]
    ):
        terms = [
            text,
            *codes,
            "đồng hồ đo điện năng thông minh 3 pha",
            "đồng hồ đo chất lượng điện năng",
            "phân tích sóng hài THDv THDi bậc 50",
            "đo PF DPF công suất phản kháng",
            "đồng hồ điện RS485 Modbus RTU",
            "giám sát Demand Maximum Demand nhà máy",
            "đồng hồ điện kết nối SCADA EMS BMS",
            "quản lý điện năng đa biểu giá",
            *terms,
        ]

    if "quat" in words and "dien" in words:
        terms.extend(
            [
                "quạt gió tủ điện",
                "quạt tủ điện",
                "quạt thông gió tủ điện",
                "quạt axial fan tủ điện",
                "quạt tủ điện 220V",
                "quạt tủ điện 120x120x38",
                "axial fan 12038 220V",
            ]
        )
    if profile["key"] == "fan":
        terms.extend(
            [
                "tủ điện quá nhiệt",
                "tủ điện bị nóng",
                "chập điện nhà xưởng",
                "bảo trì tủ điện công nghiệp",
            ]
        )
    elif profile["key"] in {"capacitor", "reactor"}:
        terms.extend(
            [
                "công suất phản kháng nhà xưởng",
                "hệ số công suất cos phi",
                "tủ tụ bù công nghiệp",
                "sóng hài biến tần tụ bù",
            ]
        )
    elif any(word in words for word in ["tu", "dien", "cong", "nghiep"]):
        terms.extend(
            [
                "thiết bị điện công nghiệp an toàn",
                "bảo trì tủ điện công nghiệp",
                "checklist thiết bị điện nhà xưởng",
            ]
        )

    return dedupe_queries(terms)


def domain_from_url(url):
    try:
        domain = urlparse(url).netloc.lower()
    except Exception:
        return ""
    return domain[4:] if domain.startswith("www.") else domain


def url_text(url):
    try:
        parsed = urlparse(url)
    except Exception:
        return ""
    text = f"{parsed.netloc} {parsed.path}"
    text = re.sub(r"[-_/]+", " ", text)
    return html.unescape(text)


def is_social_url(url):
    domain = domain_from_url(url)
    return any(domain == item or domain.endswith(f".{item}") for item in SOCIAL_DOMAINS)


def dedupe_queries(queries):
    cleaned_queries = []
    seen = set()
    for query in queries:
        cleaned = clean_search_query(query)
        key = remove_vietnamese_accents(cleaned).lower()
        if cleaned and key not in seen:
            seen.add(key)
            cleaned_queries.append(cleaned)
    return cleaned_queries


def product_codes(product):
    return [
        token.upper()
        for token in re.findall(r"[A-Za-z0-9_-]+", remove_vietnamese_accents(str(product)))
        if re.search(r"\d", token) and len(token) >= 4
    ]


def classify_research_query(query, product):
    normalized = remove_vietnamese_accents(query).lower()
    clean_product = remove_vietnamese_accents(short_product_name(product)).lower()
    if "site:masterelectric.com.vn" in normalized or (
        clean_product and clean_product in normalized and any(word in normalized for word in ["thong so", "catalog", "datasheet"])
    ):
        return "product"
    if "site:facebook.com" in normalized or "site:instagram.com" in normalized or any(
        word in normalized
        for word in ["loi thuong gap", "noi dau", "su co", "cau hoi", "kinh nghiem", "tinh huong", "nha xuong"]
    ):
        return "insight"
    return "technical"


def build_research_query_plan(product, brand_name, audience, platforms, selected_machines=None):
    clean_product = short_product_name(product)
    profile = product_profile(clean_product)
    codes = product_codes(clean_product)
    primary_code = codes[0] if codes else ""
    exact_target = primary_code or clean_product

    product_queries = [
        f'site:masterelectric.com.vn/products "{exact_target}"',
        f'"{clean_product}" thông số',
    ]
    if brand_name:
        product_queries.append(f'"{brand_name}" "{exact_target}"')

    technical_queries = list(profile.get("queries", []))[:5]
    technical_queries.extend(machine_search_queries(selected_machines, clean_product)[:3])

    insight_queries = [
        f'{profile["label"]} lỗi thường gặp nhà máy',
        f'{profile["label"]} tình huống ứng dụng thực tế',
    ]
    if "Facebook" in platforms:
        insight_queries.append(f'site:facebook.com "{profile["label"]}"')
    if "Instagram" in platforms:
        insight_queries.append(f'site:instagram.com "{profile["label"]}"')
    if audience:
        insight_queries.append(f'{profile["label"]} "{audience}"')

    ordered = [
        *product_queries[:2],
        *technical_queries[:5],
        *insight_queries[:3],
    ]
    return dedupe_queries(ordered)


def machine_search_queries(selected_machines, product=""):
    queries = []
    normalized = remove_vietnamese_accents(" ".join(selected_machines or [])).lower()
    profile = product_profile(product)
    queries.extend(profile["queries"])

    if "su co" in normalized or "an toan" in normalized:
        queries.extend(
            [
                "tủ điện quá nhiệt nguyên nhân",
                "chập điện tủ điện nhà xưởng",
                "cháy tủ điện công nghiệp",
                "sự cố tủ điện do quá nhiệt",
                "cách phòng tránh cháy nổ tủ điện",
                "bảo trì tủ điện nhà xưởng mùa nóng",
                "thiết bị bảo vệ tủ điện công nghiệp",
            ]
        )
        if profile["key"] == "fan":
            queries.append("quạt lọc tủ điện chống quá nhiệt")
        elif profile["key"] == "capacitor":
            queries.extend(["tụ bù bị nổ nguyên nhân", "sóng hài làm hỏng tụ bù"])

    if "tin tuc" in normalized or "nganh dien" in normalized:
        queries.extend(
            [
                "EVN phụ tải điện tăng nhà xưởng",
                "tiết kiệm điện công nghiệp công suất phản kháng",
                "giá điện sản xuất doanh nghiệp tiết kiệm điện",
                "ổn định hệ thống điện nhà xưởng thiết bị đo giám sát",
            ]
        )

    if "chinh sach" in normalized or "quy dinh" in normalized or "tieu chuan" in normalized:
        queries.extend(
            [
                "quy định an toàn điện nhà xưởng tủ điện",
                "tiêu chuẩn an toàn tủ điện công nghiệp",
                "PCCC tủ điện nhà xưởng kiểm tra thiết bị",
            ]
        )

    if "hang gia" in normalized or "kem chat luong" in normalized:
        queries.extend(
            [
                "thiết bị điện công nghiệp giả kém chất lượng rủi ro",
                "cách nhận biết thiết bị điện chính hãng CO CQ bảo hành",
            ]
        )

    if "mua vu" in normalized:
        queries.extend(
            [
                "mùa nóng tủ điện quá nhiệt nhà xưởng",
                "mùa mưa tủ điện bị ẩm rò điện",
                "bảo trì tủ điện cuối năm nhà xưởng",
            ]
        )

    if "thuat ngu" in normalized:
        if profile["key"] == "capacitor":
            queries.extend(["cos phi là gì công suất phản kháng", "kVAr là gì trong tụ bù", "sóng hài là gì trong hệ thống điện"])
        elif profile["key"] == "fan":
            queries.extend(["IP rating tủ điện là gì", "lưu lượng gió quạt tủ điện là gì", "quạt lọc tủ điện là gì"])
        elif profile["key"] == "power_quality_meter":
            queries.extend([
                "PF và DPF khác nhau thế nào",
                "THDv THDi là gì",
                "Demand Maximum Demand là gì",
                "mất cân bằng pha ảnh hưởng nhà máy",
            ])
        elif profile["key"] == "meter":
            queries.extend(["biến dòng CT là gì", "tỷ số biến dòng CT là gì", "đồng hồ đo điện đa năng là gì"])
        else:
            queries.extend(["thông số thiết bị điện công nghiệp cần biết", "cách đọc tem thiết bị điện"])

    if "checklist" in normalized:
        queries.extend(profile["queries"])

    if "cau hoi" in normalized or "keo inbox" in normalized:
        if profile["key"] == "capacitor":
            queries.extend(["gửi ảnh tủ tụ bù tư vấn kVAr", "tủ tụ bù bị phồng nên thay loại nào", "cos phi thấp cần thay tụ hay kiểm tra hệ thống"])
        elif profile["key"] == "fan":
            queries.extend(["tủ điện nóng nên thay quạt hay lắp thêm lọc", "gửi ảnh tủ điện tư vấn quạt lọc", "cách chọn quạt tủ điện theo kích thước"])
        elif profile["key"] == "power_quality_meter":
            queries.extend([
                "cần thông tin gì khi lắp đồng hồ chất lượng điện năng",
                "kết nối đồng hồ điện RS485 Modbus với SCADA",
                "giám sát sóng hài cho hệ thống có biến tần UPS",
            ])
        else:
            queries.extend(["gửi ảnh tem thiết bị điện tư vấn đúng mã", "cách chọn thiết bị điện thay thế đúng thông số"])

    return dedupe_queries(queries)


def base_search_queries(product, brand_name, audience, platforms, selected_machines=None):
    clean_product = short_product_name(product)
    clean_brand = brand_name.strip()
    clean_audience = audience.strip()
    terms = product_search_terms(clean_product)
    exact_terms = terms[:3]
    broad_terms = terms[3:] or terms[:1]
    intent_queries = machine_search_queries(selected_machines, clean_product)

    queries = [
        *intent_queries,
        f'"{clean_product}"',
        *[f'"{term}" giá' for term in exact_terms],
        *[f'"{term}" thông số' for term in exact_terms],
        *[f'"{term}" mua' for term in exact_terms],
        *[f'{term} giá bán' for term in broad_terms[:3]],
        *[f'{term} cách chọn' for term in broad_terms[:3]],
        *[f'{term} thay thế' for term in broad_terms[:3]],
        *[f'site:facebook.com "{term}"' for term in exact_terms[:2]],
        *[f'site:facebook.com {term} giá' for term in broad_terms[:2]],
        *[f'site:instagram.com "{term}"' for term in exact_terms[:2]],
    ]

    if clean_audience:
        queries.extend(
            [
                f'"{clean_product}" "{clean_audience}"',
                f'{broad_terms[0]} "{clean_audience}"' if broad_terms else "",
            ]
        )

    if clean_brand:
        queries.extend(
            [
                f'"{clean_brand}" "{clean_product}"',
                f'"{clean_brand}" "{product_profile(clean_product)["label"]}"',
            ]
        )

    if "Facebook" not in platforms:
        queries = [query for query in queries if "facebook.com" not in query]

    if "Instagram" not in platforms:
        queries = [query for query in queries if "instagram.com" not in query]

    return dedupe_queries(queries)


def ai_suggest_search_queries(product, brand_name, audience, platforms, selected_machines=None, max_queries=8):
    clean_product = short_product_name(product)
    profile = product_profile(clean_product)
    machine_context = build_content_machine_context(selected_machines or [])
    prompt = f"""
Bạn là research assistant cho content Facebook/Instagram.

Hãy đề xuất {max_queries} từ khóa tìm kiếm tốt nhất để tìm nội dung công khai liên quan.

Thông tin:
- Sản phẩm/dịch vụ: {clean_product}
- Thương hiệu/shop: {brand_name or "Chưa cung cấp"}
- Khách hàng mục tiêu: {audience}
- Nền tảng cần học: {", ".join(platforms)}
- Máy tạo nội dung đang chọn:
{machine_context or "Không có"}
- Nhóm sản phẩm đã nhận diện: {profile["label"]}
- Query bắt buộc phải bám nhóm này, tránh kéo sang sản phẩm khác.

Mục tiêu search:
- Nếu máy là sự cố/an toàn/tin ngành/chính sách, ưu tiên tìm nguồn tin, bài cảnh báo, nguyên nhân, bài học, checklist kiểm tra.
- Nếu máy là bán hàng/checklist/review, tìm thông số, cách chọn, CTA, tình huống mua thật.
- Tìm insight hình ảnh/reel nhưng không copy nội dung.

Quy tắc query:
- Ưu tiên tiếng Việt.
- Có cả query rộng và query theo site:facebook.com/site:instagram.com nếu phù hợp.
- Không dùng query quá dài.
- Không đưa query về sản phẩm khác như quạt, tụ bù, CT, IP rating nếu không liên quan trực tiếp đến sản phẩm hiện tại.
- Không tìm nội dung riêng tư.
- Không bịa tên đối thủ cụ thể.

Trả về JSON đúng cấu trúc:
{{"queries": ["query 1", "query 2"]}}
"""
    try:
        raw = call_json_model(TEXT_MODEL, prompt, max_tokens=500)
        data = parse_json_response(raw, {"queries": []})
    except Exception:
        return []

    queries = data.get("queries", []) if isinstance(data, dict) else []
    return dedupe_queries(queries)[:max_queries]


def generate_search_queries(product, brand_name, audience, platforms, use_ai_queries=True, max_queries=10, selected_machines=None):
    clean_product = short_product_name(product)
    profile = product_profile(clean_product)
    planned_queries = build_research_query_plan(
        clean_product,
        brand_name,
        audience,
        platforms,
        selected_machines=selected_machines,
    )
    ai_queries = ai_suggest_search_queries(clean_product, brand_name, audience, platforms, selected_machines=selected_machines) if use_ai_queries else []
    if profile["key"] == "power_quality_meter":
        ai_queries = [
            query for query in ai_queries
            if not (
                any(term in remove_vietnamese_accents(query).lower() for term in ["bien dong ct la gi", "cach chon ct", "ti so bien dong"])
                and not any(term in remove_vietnamese_accents(query).lower() for term in ["pf", "dpf", "song hai", "demand", "modbus", "chat luong dien"])
            )
        ]
        queries = dedupe_queries(planned_queries + ai_queries)[:max_queries]
    else:
        queries = dedupe_queries(planned_queries + ai_queries)[:max_queries]
    return dedupe_queries([master_electric_query(query, clean_product) for query in queries])[:max_queries]


def fallback_brief_seed(product, brand_name="", product_specs=""):
    profile = product_profile(product, product_specs)
    clean_product = short_product_name(product) or "sản phẩm"
    brand = brand_name.strip() or DEFAULT_BRAND_LABEL
    base = {
        "audience": "Chủ xưởng, kỹ thuật bảo trì nhà máy, thợ điện công nghiệp, đơn vị thi công tủ điện và nhà thầu M&E cần chọn thiết bị đúng thông số.",
        "product_specs": product_specs.strip() or f"{clean_product}. Cần bám đúng tem/mã, điện áp, dòng/công suất, kích thước lắp và ứng dụng thực tế trong tủ điện.",
        "customer_problem": "Khách chưa chắc nên chọn mã nào, sợ mua sai thông số, hệ thống vận hành không ổn định, cần tư vấn nhanh nhưng vẫn phải đúng nhu cầu thực tế.",
        "proof_points": f"{brand} hỗ trợ tư vấn theo ảnh tem/mã cũ, ảnh tủ điện hoặc thông số hiện có. Không bịa giá/feedback nếu chưa được cung cấp.",
        "offer_info": "Hỗ trợ đối chiếu ảnh tem, mã cũ, thông số tải hoặc ảnh tủ điện trước khi khách đặt hàng.",
        "differentiator": "Không viết chung chung và không tư vấn theo kiểu đoán mã; ưu tiên phân tích nhu cầu, thông số, vị trí lắp và tình trạng hệ thống.",
        "source_material": f"Sản phẩm mới cần ra mắt: {clean_product}. Mục tiêu là tạo nội dung dễ hiểu, có khả năng được lưu/chia sẻ, giúp khách biết cần gửi thông tin gì để được tư vấn.",
        "content_goal": "Tăng nhận diện thương hiệu công ty",
        "brand_voice": "B2B chuyên nghiệp",
        "content_mix": "Tăng nhận diện thương hiệu công ty",
        "format_focus": "Ảnh + caption",
        "selected_machines": [
            "Giới thiệu năng lực công ty",
            "Bản đồ sản phẩm theo nhu cầu",
            "Combo giải pháp hệ thống",
            "Bài tăng follow/lưu bài",
            "Bài kéo inbox",
        ],
    }

    if profile["key"] == "fan":
        base["customer_problem"] = "Tủ điện nóng, quạt cũ yếu/hỏng, bụi bẩn làm giảm thông gió, khách sợ chọn sai nguồn điện, kích thước hoặc vị trí bắt vít."
        base["selected_machines"] = ["Checklist kỹ thuật", "Q&A nhanh cho người mới", "Bài kéo inbox", "Hậu trường kho/đóng hàng", "Bắt trend chuyên ngành"]
    elif profile["key"] == "capacitor":
        base["customer_problem"] = "Hệ số công suất thấp, bị phạt công suất phản kháng, tụ bù nóng/phồng/nhanh xuống cấp, tải có biến tần hoặc sóng hài."
        base["selected_machines"] = ["Giới thiệu năng lực công ty", "Bản đồ sản phẩm theo nhu cầu", "Myth-busting hiểu lầm thường gặp", "Bảng chọn nhanh sản phẩm", "Bài kéo inbox"]
    elif profile["key"] == "protection":
        base["customer_problem"] = "CB/MCCB cũ hay nhảy, thiết bị nóng, hệ thống chập chờn, khách sợ chọn sai dòng A hoặc sai khả năng cắt kA."
        base["selected_machines"] = ["Myth-busting hiểu lầm thường gặp", "Checklist kỹ thuật", "Câu hỏi từ khách hàng", "Bài kéo inbox", "Bắt trend chuyên ngành"]
        base["content_goal"] = "Tư vấn đúng nhu cầu"
    elif profile["key"] == "meter":
        base["customer_problem"] = "Khách cần đo/giám sát thông số điện nhưng chưa rõ tỷ số CT, sơ đồ đấu dây, nguồn nuôi hoặc mã đồng hồ phù hợp."
        base["selected_machines"] = ["Giải thích thuật ngữ đơn giản", "Q&A nhanh cho người mới", "Checklist kỹ thuật", "Bản đồ sản phẩm theo nhu cầu", "Bài kéo inbox"]
    elif profile["key"] == "power_quality_meter":
        base["product_specs"] = product_specs.strip() or f"{clean_product}. {profile['verified_specs']}"
        base["audience"] = "Kỹ sư điện, quản lý năng lượng, kỹ thuật bảo trì nhà máy, đơn vị tích hợp SCADA/EMS/BMS, tòa nhà, data center và hệ thống có biến tần/UPS/tải phi tuyến."
        base["customer_problem"] = "Doanh nghiệp chỉ nhìn kWh nên chưa thấy rõ sóng hài, PF/DPF, mất cân bằng pha, công suất phản kháng và phụ tải đỉnh; khó tìm nguyên nhân tăng tổn hao hoặc tối ưu vận hành."
        base["proof_points"] = f"{brand} cung cấp mã MT-DPFHMF_CD2 với khả năng đo PF/DPF, THDv/THDi, sóng hài đến bậc 50, Demand/Maximum Demand, 6 biểu giá và RS485 Modbus RTU. Không tự suy đoán điện áp nguồn nuôi, kích thước hoặc cấp chính xác nếu tài liệu chưa công bố."
        base["offer_info"] = "Hỗ trợ tư vấn theo sơ đồ hệ thống, loại tải, tỷ số CT, nhu cầu giám sát và yêu cầu kết nối SCADA/EMS/BMS."
        base["differentiator"] = "Tập trung vào phân tích chất lượng điện năng và quản lý năng lượng, không viết như đồng hồ Volt/Ampere cơ bản và không biến nội dung thành bài hướng dẫn chọn CT."
        base["selected_machines"] = ["Giải thích thuật ngữ đơn giản", "Myth-busting hiểu lầm thường gặp", "Checklist kỹ thuật", "Review sản phẩm theo tình huống", "Bài tăng follow/lưu bài", "Bài kéo inbox"]
        base["content_goal"] = "Xây uy tín chuyên môn và kéo tư vấn giải pháp giám sát điện năng"
    elif profile["key"] == "catalog":
        base["customer_problem"] = "Khách cần nhiều nhóm thiết bị cho tủ điện nhưng chưa biết nên kiểm tra nhóm nào trước: làm mát, bù công suất, bảo vệ, đo lường hay phụ kiện."
        base["selected_machines"] = ["Giới thiệu năng lực công ty", "Bản đồ sản phẩm theo nhu cầu", "Combo giải pháp hệ thống", "Bài tăng follow/lưu bài", "Hậu trường kho/đóng hàng"]

    return base


def ai_generate_brief_seed(product, brand_name="", product_specs="", model=TEXT_MODEL):
    if not str(product).strip():
        return fallback_brief_seed(product, brand_name, product_specs)

    fallback = fallback_brief_seed(product, brand_name, product_specs)
    machine_names = list(CONTENT_MACHINES.keys())
    prompt = f"""
Bạn là strategist nội dung ngành điện công nghiệp.
Người dùng chỉ có rất ít dữ liệu đầu vào, hãy tự điền brief còn thiếu để app tạo content tốt hơn.

Dữ liệu người dùng có:
- Sản phẩm/dịch vụ: {product}
- Công ty/thương hiệu: {brand_name or DEFAULT_BRAND_LABEL}
- Thông số kỹ thuật hiện có: {product_specs or "Chưa cung cấp"}

Hãy suy luận thận trọng, không bịa giá, không bịa feedback, không bịa chứng nhận.
Ưu tiên mục tiêu ra mắt sản phẩm mới, tăng nhận diện, kéo follow/save/inbox.
Chọn 5 máy content phù hợp nhất trong danh sách sau:
{json.dumps(machine_names, ensure_ascii=False)}

Trả về JSON đúng cấu trúc:
{{
  "audience": "...",
  "product_specs": "...",
  "customer_problem": "...",
  "proof_points": "...",
  "offer_info": "...",
  "differentiator": "...",
  "source_material": "...",
  "content_goal": "Tăng nhận diện thương hiệu công ty/Tư vấn đúng nhu cầu/Chốt inbox/Giải thích kỹ thuật/Xây dựng niềm tin/Tăng follow fanpage",
  "brand_voice": "B2B chuyên nghiệp/Tư vấn kỹ thuật rõ ràng/Facebook trending dễ tiếp cận/Bán hàng gần gũi",
  "content_mix": "Tăng nhận diện thương hiệu công ty/Bán hàng theo mã sản phẩm/Tư vấn lỗi thường gặp/Giải pháp theo hệ thống/Checklist chọn/lắp đúng/Reels/video ngắn kéo reach/Nuôi follow bằng kiến thức dễ lưu/Hậu trường/kho hàng/quy trình tư vấn",
  "format_focus": "Ảnh + caption/Reels/video ngắn/Album sản phẩm/Kết hợp ảnh và Reels",
  "selected_machines": ["...", "..."]
}}
"""
    try:
        raw = call_json_model(model, prompt, max_tokens=1100, context_tokens=4096)
        data = parse_json_response(raw, fallback)
        if not isinstance(data, dict):
            return fallback
    except Exception:
        return fallback

    merged = {**fallback}
    for key in [
        "audience",
        "product_specs",
        "customer_problem",
        "proof_points",
        "offer_info",
        "differentiator",
        "source_material",
        "content_goal",
        "brand_voice",
        "content_mix",
        "format_focus",
    ]:
        value = clean_model_text(data.get(key, ""))
        if value:
            merged[key] = value

    valid_machines = [m for m in data.get("selected_machines", []) if m in CONTENT_MACHINES]
    if valid_machines:
        merged["selected_machines"] = valid_machines[:6]
    return merged


def suggest_content_machines_from_chat(goal_text, product="", content_goal="", content_mix=""):
    text = remove_vietnamese_accents(f"{goal_text} {product} {content_goal} {content_mix}").lower()
    profile = product_profile(product)
    goal_matched = False

    def valid(machine_names):
        return [name for name in machine_names if name in CONTENT_MACHINES]

    pack_label = "Bộ cân bằng để vừa quảng bá vừa kéo khách hỏi"
    reason = "Phù hợp khi bạn mô tả mục tiêu còn chung chung: có bài nhận diện, bài kiến thức dễ lưu và bài kéo inbox."
    machines = [
        "Giới thiệu năng lực công ty",
        "Checklist kỹ thuật",
        "Q&A nhanh cho người mới",
        "Bài tăng follow/lưu bài",
        "Bài kéo inbox",
        "Review sản phẩm theo tình huống",
    ]

    if any(keyword in text for keyword in ["tin tuc", "xu huong", "cap nhat", "thi truong", "nganh dien", "evn", "gia dien", "quy dinh", "tieu chuan", "chinh sach", "thoi su"]):
        goal_matched = True
        pack_label = "Bộ tin tức/xu hướng ngành để tăng độ chuyên môn"
        reason = "Dùng khi bạn muốn page bắt kịp thị trường, giải thích tin ngành theo ngôn ngữ dễ hiểu và kéo người đọc về tư vấn sản phẩm liên quan."
        machines = [
            "Tin tức ngành điện",
            "Bắt trend chuyên ngành",
            "Giải thích thuật ngữ đơn giản",
            "Q&A nhanh cho người mới",
            "Bài tăng follow/lưu bài",
            "Bài kéo inbox",
        ]
    elif any(keyword in text for keyword in ["ra mat", "san pham moi", "viral", "quang ba", "phu song", "nhan dien", "follow"]):
        goal_matched = True
        pack_label = "Bộ quảng bá sản phẩm mới"
        reason = "Dùng để biến một sản phẩm mới thành chuỗi bài dễ hiểu, dễ lưu, có nhận diện công ty và có điểm chạm inbox."
        machines = [
            "Giới thiệu năng lực công ty",
            "Bắt trend chuyên ngành",
            "Review sản phẩm theo tình huống",
            "Bài tăng follow/lưu bài",
            "Bản đồ sản phẩm theo nhu cầu",
            "Bài kéo inbox",
        ]
    elif any(keyword in text for keyword in ["ban hang", "chot", "inbox", "lead", "khach hoi", "tu van", "don hang"]):
        goal_matched = True
        pack_label = "Bộ kéo inbox/tư vấn chốt đơn"
        reason = "Tập trung vào câu hỏi thật của khách, bảng chọn nhanh và CTA gửi ảnh tem/thông số để tư vấn."
        machines = [
            "Bài kéo inbox",
            "Câu hỏi từ khách hàng",
            "Bảng chọn nhanh sản phẩm",
            "Review sản phẩm theo tình huống",
            "Checklist kỹ thuật",
            "Myth-busting hiểu lầm thường gặp",
        ]
    elif any(keyword in text for keyword in ["kien thuc", "giai thich", "nguoi moi", "de hieu", "luu bai", "save"]):
        goal_matched = True
        pack_label = "Bộ kiến thức dễ lưu/tăng follow"
        reason = "Hợp với fanpage muốn tăng theo dõi bằng nội dung có ích, ít bán gắt nhưng vẫn dẫn về tư vấn."
        machines = [
            "Giải thích thuật ngữ đơn giản",
            "Q&A nhanh cho người mới",
            "Checklist kỹ thuật",
            "Mini-series",
            "Bài tăng follow/lưu bài",
            "Bài kéo inbox",
        ]
    elif any(keyword in text for keyword in ["su co", "canh bao", "an toan", "chay", "chap", "qua nhiet", "hu hong"]):
        goal_matched = True
        pack_label = "Bộ cảnh báo sự cố/an toàn"
        reason = "Dùng khi muốn lấy rủi ro thực tế làm hook, sau đó chuyển sang checklist và giải pháp đúng thông số."
        machines = [
            "Sự cố & bài học an toàn",
            "Cảnh báo hàng giả/kém chất lượng",
            "Checklist kỹ thuật",
            "Myth-busting hiểu lầm thường gặp",
            "Bài kéo inbox",
            "Tin tức ngành điện",
        ]
    elif any(keyword in text for keyword in ["cong ty", "thuong hieu", "nang luc", "uy tin", "doi thu", "fanpage"]):
        goal_matched = True
        pack_label = "Bộ tăng nhận diện công ty"
        reason = "Phù hợp khi mục tiêu là làm fanpage giống một đơn vị có năng lực thật, không chỉ đăng từng mã sản phẩm."
        machines = [
            "Giới thiệu năng lực công ty",
            "Hậu trường kho/đóng hàng",
            "Bản đồ sản phẩm theo nhu cầu",
            "Combo giải pháp hệ thống",
            "Bài tăng follow/lưu bài",
            "Case study khách hàng",
        ]

    if not goal_matched and profile["key"] == "protection" and any(keyword in text for keyword in ["mccb", "cb", "bao ve", "dong a", "ka"]):
        pack_label = "Bộ MCCB/thiết bị bảo vệ"
        reason = "Ưu tiên phá hiểu lầm chọn dòng A, kiểm tra kA/số cực và kéo khách gửi ảnh tem để đối chiếu."
        machines = [
            "Myth-busting hiểu lầm thường gặp",
            "Checklist kỹ thuật",
            "Câu hỏi từ khách hàng",
            "Bảng chọn nhanh sản phẩm",
            "Bài kéo inbox",
            "Review sản phẩm theo tình huống",
        ]
    elif not goal_matched and profile["key"] == "capacitor":
        machines = valid(["Giới thiệu năng lực công ty", "Bản đồ sản phẩm theo nhu cầu", "Myth-busting hiểu lầm thường gặp", "Bảng chọn nhanh sản phẩm", "Combo giải pháp hệ thống", "Bài kéo inbox"])
    elif not goal_matched and profile["key"] == "fan":
        machines = valid(["Checklist kỹ thuật", "Q&A nhanh cho người mới", "Bài kéo inbox", "Hậu trường kho/đóng hàng", "Bắt trend chuyên ngành", "Review sản phẩm theo tình huống"])
    elif not goal_matched and profile["key"] == "catalog":
        machines = valid(["Giới thiệu năng lực công ty", "Bản đồ sản phẩm theo nhu cầu", "Combo giải pháp hệ thống", "Bài tăng follow/lưu bài", "Hậu trường kho/đóng hàng", "Bài kéo inbox"])

    return {
        "label": pack_label,
        "reason": reason,
        "machines": valid(machines)[:6],
    }


def build_machine_fallback_idea(machine_name, product_input):
    profile = product_profile(product_input)
    clean_product = short_product_name(product_input) or "sản phẩm"
    blueprint = MACHINE_IDEA_BLUEPRINTS[machine_name]
    format_values = {
        "product": clean_product,
        "label": profile["label"],
        "checks": profile["image_checks"],
    }
    outline = "\n".join(
        f"• {item.format(**format_values)}"
        for item in blueprint["outline"]
    )
    return {
        "machine": machine_name,
        "hook": blueprint["hook"].format(**format_values),
        "outline": outline,
        "cta": blueprint["cta"].format(**format_values),
        "image_tip": blueprint["image"].format(**format_values),
        "emoji": blueprint["emoji"],
        "priority": blueprint["priority"],
    }


def normalize_machine_idea(idea, machine_name, product_input, used_hooks):
    fallback = build_machine_fallback_idea(machine_name, product_input)
    if not isinstance(idea, dict):
        return fallback

    hook = clean_model_text(idea.get("hook", ""))
    normalized_hook = remove_vietnamese_accents(hook).lower()
    generic_hook = (
        len(hook) < 24
        or normalized_hook.startswith("y tuong bai")
        or normalized_hook in used_hooks
    )
    if generic_hook:
        hook = fallback["hook"]
        normalized_hook = remove_vietnamese_accents(hook).lower()
    used_hooks.add(normalized_hook)

    outline_value = idea.get("outline", "")
    if isinstance(outline_value, list):
        outline = "\n".join(f"• {clean_model_text(item)}" for item in outline_value if clean_model_text(item))
    else:
        outline = clean_model_text(outline_value)
    if len(outline) < 70:
        outline = fallback["outline"]

    cta = clean_model_text(idea.get("cta", ""))
    if len(cta) < 20:
        cta = fallback["cta"]

    image_tip = clean_model_text(idea.get("image_tip", ""))
    if len(image_tip) < 20:
        image_tip = fallback["image_tip"]

    return {
        "machine": machine_name,
        "hook": hook,
        "outline": outline,
        "cta": cta,
        "image_tip": image_tip,
        # Icons and priority are product UI metadata, not model output.
        "emoji": fallback["emoji"],
        "priority": fallback["priority"],
    }


def generate_machine_content_ideas(product_input, model="qwen2.5:3b"):
    """Generate and normalize one actionable idea for each of the 24 content machines."""
    profile = product_profile(product_input)
    clean_product = short_product_name(product_input) or "sản phẩm"
    priority_pack = suggest_content_machines_from_chat(product_input, product=product_input)
    priority_machines = [
        name for name in priority_pack.get("machines", [])
        if name in CONTENT_MACHINES
    ][:6]
    machine_list = "\n".join(
        f"- {name}: {CONTENT_MACHINES[name]}" for name in priority_machines
    )
    prompt = f"""
Bạn là chiến lược gia nội dung ngành điện công nghiệp.
Người dùng muốn quảng bá sản phẩm sau: {product_input}
Nhóm sản phẩm nhận diện: {profile["label"]}

Dưới đây là {len(priority_machines)} máy ưu tiên cần AI viết sâu:
{machine_list}

Hãy tạo đúng {len(priority_machines)} ý tưởng, mỗi máy một ý tưởng, bám sát sản phẩm "{clean_product}".
Mỗi máy cần có:
- hook: câu mở bài cụ thể, có thể dùng ngay (1-2 câu)
- outline: đúng 3 ý triển khai, mỗi ý bám sản phẩm/tình huống
- cta: lời kêu gọi hành động cụ thể
- image_tip: gợi ý ảnh nên dùng (1 dòng)

Trả về JSON:
{{"ideas": [
  {{"machine": "tên máy", "hook": "...", "outline": ["ý 1", "ý 2", "ý 3"], "cta": "...", "image_tip": "..."}},
  ...
]}}

Quy tắc:
- Viết tiếng Việt tự nhiên, giọng tư vấn B2B.
- Hook phải bám nỗi đau hoặc tình huống thật của khách dùng {clean_product}.
- Không bịa giá, feedback, chứng nhận.
- Mỗi máy phải có ý tưởng khác nhau, không lặp.
- CTA phải phù hợp riêng với mục tiêu của máy, không dùng cùng một CTA cho cả 24 máy.
- Không viết hook kiểu "Ý tưởng bài [tên máy] cho [sản phẩm]".
- Gợi ý ảnh phải nói rõ chụp/thiết kế cái gì, không ghi chung chung "ảnh sản phẩm".
"""
    try:
        raw = call_json_model(model, prompt, max_tokens=1300, context_tokens=PLANNING_CONTEXT_TOKENS)
        data = parse_json_response(raw, {"ideas": []})
    except Exception:
        data = {"ideas": []}

    raw_ideas = data.get("ideas", []) if isinstance(data, dict) else []
    machine_lookup = {
        remove_vietnamese_accents(name).lower(): name
        for name in CONTENT_MACHINES
    }
    generated_by_machine = {}
    for idea in raw_ideas:
        if not isinstance(idea, dict):
            continue
        raw_name = remove_vietnamese_accents(str(idea.get("machine", ""))).lower()
        machine_name = machine_lookup.get(raw_name)
        if machine_name and machine_name not in generated_by_machine:
            generated_by_machine[machine_name] = idea

    used_hooks = set()
    return [
        normalize_machine_idea(
            generated_by_machine.get(machine_name),
            machine_name,
            product_input,
            used_hooks,
        )
        for machine_name in CONTENT_MACHINES
    ]


def is_blocked_result(title, body, url=""):
    text = remove_vietnamese_accents(f"{title} {body} {url}").lower()
    domain = remove_vietnamese_accents(urlparse(url).netloc).lower()
    if any(keyword in text for keyword in [remove_vietnamese_accents(k).lower() for k in BLOCKED_RESULT_KEYWORDS]):
        return True
    return any(blocked in domain for blocked in BLOCKED_DOMAINS)


def research_relevance_score(product, title, body, url="", selected_machines=None):
    text = remove_vietnamese_accents(f"{title} {body} {url}").lower()
    machine_text = remove_vietnamese_accents(" ".join(selected_machines or [])).lower()
    profile = product_profile(product)
    score = 0
    reasons = []

    def add(points, reason):
        nonlocal score
        score += points
        reasons.append(reason)

    product_tokens = [
        word
        for word in re.findall(r"[a-z0-9]+", remove_vietnamese_accents(product).lower())
        if len(word) >= 4 and word not in {"quat", "dien", "master", "hang", "chinh", "dung", "cong", "nghiep", "pha"}
    ]
    if any(token in text for token in product_tokens):
        add(3, "khớp sản phẩm/mã hàng")

    profile_terms = [term for term in profile.get("terms", []) if len(term) >= 4]
    has_product_group = any(term in text for term in profile_terms)
    if not has_product_group and profile["key"] in {"generic", "catalog"}:
        has_product_group = any(term in text for term in MASTER_ELECTRIC_PRODUCT_TERMS)
    if has_product_group:
        add(4, f"khớp nhóm {profile['label']}")

    if profile["key"] == "power_quality_meter":
        feature_matches = [
            term for term in ["pf", "dpf", "thdv", "thdi", "song hai", "demand", "modbus", "scada", "ems", "bms", "mat can bang"]
            if term in text
        ]
        if feature_matches:
            add(3, f"khớp tính năng chất lượng điện: {', '.join(feature_matches[:3])}")
        if any(term in text for term in ["bien dong la gi", "cach chon bien dong", "ti so bien dong"]) and not feature_matches:
            score -= 6
            reasons.append("lệch sang nội dung CT cơ bản")

    has_industrial_context = any(term in text for term in MASTER_ELECTRIC_INDUSTRIAL_CONTEXT_TERMS)
    if has_industrial_context:
        add(2, "khớp ngành điện công nghiệp")

    consumer_noise = [term for term in MASTER_ELECTRIC_CONSUMER_NEGATIVE_TERMS if term in text]
    if consumer_noise:
        score -= 7
        reasons.append(f"lệch sang dân dụng/gia dụng: {', '.join(consumer_noise[:2])}")

    if any(word in machine_text for word in ["su co", "an toan"]):
        if any(term in text for term in ["qua nhiet", "chap dien", "chay", "su co", "bao tri", "pccc", "an toan"]):
            add(4, "khớp nhánh sự cố/an toàn")
    elif "tin tuc" in machine_text:
        if any(term in text for term in ["evn", "gia dien", "phu tai", "tiet kiem dien", "nang luong"]):
            add(4, "khớp tin ngành")
    elif "cam on" in machine_text or "ghi nhan" in machine_text:
        if any(term in text for term in ["feedback", "cam on", "khach hang", "doi tac", "tin dung", "review"]):
            add(3, "khớp social proof/cảm ơn")
        if any(token in text for token in product_tokens):
            add(2, "có sản phẩm để ghi nhận")
    elif "checklist" in machine_text:
        if any(term in text for term in ["checklist", "dau hieu", "nguyen nhan", "cach chon", "kiem tra"]):
            add(3, "khớp checklist/hướng dẫn")
    elif "review" in machine_text:
        if any(term in text for term in ["review", "ung dung", "phu hop", "cach chon", "thong so"]):
            add(3, "khớp review tình huống")

    if is_blocked_result(title, body, url):
        score -= 10
        reasons.append("nguồn rác/không phù hợp")

    if not has_product_group:
        score = min(score, 4)
        reasons.append("thiếu tín hiệu nhóm sản phẩm")
    if not has_industrial_context:
        score = min(score, 6)
        reasons.append("thiếu ngữ cảnh tủ điện/điện công nghiệp")

    return score, reasons


def source_trust_label(score, url=""):
    domain = urlparse(url).netloc.lower()
    if score >= 7:
        return "Nguồn mạnh: có thể dùng làm insight chính"
    if score >= 5:
        return "Nguồn vừa: dùng để tham khảo góc viết"
    if score >= 2:
        return "Nguồn thấp: chỉ dùng làm tín hiệu phụ"
    if domain:
        return "Không dùng: chưa đủ liên quan"
    return "Không dùng: thiếu nguồn rõ"


def classify_research_source(product, query, title, body, url):
    domain = domain_from_url(url)
    text = remove_vietnamese_accents(f"{title} {body} {url}").lower()
    query_role = classify_research_query(query, product)
    codes = [remove_vietnamese_accents(code).lower() for code in product_codes(product)]

    if domain == "masterelectric.com.vn" or domain.endswith(".masterelectric.com.vn"):
        return "product"
    if is_social_url(url):
        return "insight"
    if query_role == "product" and any(code in text for code in codes):
        return "product_candidate"
    if query_role == "insight":
        return "insight"
    return "technical"


def research_source_label(source_role):
    return {
        "product": "Nguồn sản phẩm chính hãng",
        "product_candidate": "Nguồn sản phẩm tham khảo",
        "technical": "Nguồn kiến thức kỹ thuật",
        "insight": "Nguồn insight/content",
    }.get(source_role, "Nguồn tham khảo")


def result_matches_product(product, title, body, selected_machines=None):
    product_text = remove_vietnamese_accents(product).lower().strip()
    result_text = remove_vietnamese_accents(f"{title} {body}").lower()
    machine_text = remove_vietnamese_accents(" ".join(selected_machines or [])).lower()
    profile = product_profile(product)

    category_required_terms = {
        "capacitor": ["tu bu", "cos phi", "kvar", "cong suat phan khang", "song hai", "cuon khang"],
        "reactor": ["cuon khang", "song hai", "bien tan", "tu bu", "reactor"],
        "fan": ["quat", "thong gio", "lam mat", "luu luong gio", "tu dien"],
        "protection": ["mccb", "aptomat", "cb", "relay", "contactor", "dong cat"],
        "meter": ["bien dong", "ct", "dong ho", "do luong", "giam sat dien"],
        "power_quality_meter": [
            "dong ho dien",
            "dien nang",
            "chat luong dien",
            "power quality",
            "pf",
            "dpf",
            "thdv",
            "thdi",
            "demand",
            "modbus",
            "scada",
            "ems",
            "bms",
        ],
        "thermal_control": ["bo on nhiet", "thermostat", "dien tro suoi", "heater", "chong am"],
        "control": ["den bao", "nut nhan", "cong tac xoay", "selector switch", "push button"],
        "busbar": ["busbar", "thanh cai", "su do", "goi do", "thanh do"],
        "transformer": ["may bien ap", "bien ap", "transformer"],
    }
    required_terms = category_required_terms.get(profile["key"], [])
    if required_terms and not any(term in result_text for term in required_terms):
        return False

    if profile["key"] == "power_quality_meter":
        power_quality_signals = [
            "chat luong dien",
            "power quality",
            "pf",
            "dpf",
            "thdv",
            "thdi",
            "song hai",
            "demand",
            "modbus",
            "scada",
            "ems",
            "bms",
            "mat can bang",
            "da bieu gia",
        ]
        if not any(term in result_text for term in power_quality_signals):
            return False
        ct_only_terms = ["bien dong la gi", "cach chon bien dong", "ti so bien dong"]
        if any(term in result_text for term in ct_only_terms) and not any(
            term in result_text for term in ["song hai", "demand", "modbus", "pf", "dpf", "chat luong dien"]
        ):
            return False

    if any(term in result_text for term in MASTER_ELECTRIC_CONSUMER_NEGATIVE_TERMS):
        return False

    if any(word in machine_text for word in ["su co", "an toan", "tin tuc", "chinh sach", "quy dinh", "mua vu"]):
        intent_terms = [
            "tu dien",
            "qua nhiet",
            "chay",
            "chap dien",
            "nha xuong",
            "cong nghiep",
            "an toan dien",
            "bao tri",
            "tiet kiem dien",
            "pccc",
        ]
        if any(term in result_text for term in intent_terms):
            return True

    if product_text and product_text in result_text:
        return True

    keywords = [
        word
        for word in re.findall(r"[a-z0-9]+", product_text.replace('"', " "))
        if len(word) >= 3 and word not in {"cho", "voi", "với", "cua", "của", "dung", "cong", "nghiep", "pha", "kho"}
    ]
    product_codes = [word for word in keywords if re.search(r"\d", word)]

    if any(code in result_text for code in product_codes):
        return True

    if not keywords:
        return True

    matched_count = sum(1 for word in keywords if word in result_text)
    broad_match = all(word in result_text for word in ["quat", "dien"]) and (
        "tu dien" in result_text or "axial" in result_text or "12038" in result_text
    )
    return broad_match or matched_count >= min(2, len(keywords))


def search_google_custom(query, api_key, cx, max_results):
    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "num": min(max_results, 10),
        "lr": "lang_vi",
    }
    response = requests.get(GOOGLE_CUSTOM_SEARCH_URL, params=params, timeout=20)
    response.raise_for_status()
    data = response.json()

    results = []
    for item in data.get("items", []):
        results.append(
            {
                "query": query,
                "title": item.get("title", "").strip(),
                "href": item.get("link", "").strip(),
                "body": item.get("snippet", "").strip(),
            }
        )

    return results


def extract_style_sample(text, limit=PAGE_TEXT_LIMIT):
    text = clean_model_text(text)
    lines = []
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        normalized = remove_vietnamese_accents(line).lower()
        if any(remove_vietnamese_accents(term).lower() in normalized for term in POSITIVE_STYLE_TERMS):
            lines.append(line)
        elif len(line) >= 45 and len(lines) < 5:
            lines.append(line)

    sample = " ".join(lines) if lines else text
    sample = re.sub(r"\s+", " ", sample).strip()
    return sample[:limit]


def fetch_public_page_text(url):
    if not url or is_social_url(url):
        return ""

    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=8)
        response.raise_for_status()
    except Exception:
        return ""

    content_type = response.headers.get("content-type", "").lower()
    if "text/html" not in content_type:
        return ""

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form", "noscript"]):
        tag.decompose()

    parts = []
    for selector in [
        "meta[name='description']",
        "meta[property='og:description']",
        "h1",
        "h2",
        "p",
        "li",
    ]:
        for node in soup.select(selector):
            text = node.get("content") if node.name == "meta" else node.get_text(" ", strip=True)
            text = html.unescape(text or "")
            text = re.sub(r"\s+", " ", text).strip()
            if text and len(text) >= 20:
                parts.append(text)

    page_text = "\n".join(dict.fromkeys(parts))
    return extract_style_sample(page_text)


def enrich_search_results_with_page_text(results, product):
    enriched = []
    fetched_count = 0
    for item in results:
        item = dict(item)
        page_text = ""
        if item.get("href") and fetched_count < PAGE_FETCH_LIMIT and not is_social_url(item.get("href", "")):
            page_text = fetch_public_page_text(item["href"])
            if page_text:
                fetched_count += 1

        item["page_text"] = page_text
        item["research_sample"] = page_text or extract_style_sample(f"{item.get('title', '')}. {item.get('body', '')}")
        item["source_type"] = "Da doc trang" if page_text else "Snippet search"
        enriched.append(item)
    return enriched


def balance_research_results(results, limit=12):
    quotas = {
        "product": 2,
        "product_candidate": 1,
        "technical": 6,
        "insight": 3,
    }
    selected = []
    selected_urls = set()
    domain_counts = {}

    ranked = sorted(
        results,
        key=lambda item: (
            1 if item.get("source_role") == "product" else 0,
            item.get("relevance_score", 0),
        ),
        reverse=True,
    )
    for role, quota in quotas.items():
        role_count = 0
        for item in ranked:
            if role_count >= quota or len(selected) >= limit:
                break
            if item.get("source_role") != role or item.get("href") in selected_urls:
                continue
            domain = domain_from_url(item.get("href", ""))
            if domain and domain_counts.get(domain, 0) >= 2:
                continue
            selected.append(item)
            selected_urls.add(item.get("href"))
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
            role_count += 1

    for item in ranked:
        if len(selected) >= limit:
            break
        if item.get("href") in selected_urls:
            continue
        domain = domain_from_url(item.get("href", ""))
        if domain and domain_counts.get(domain, 0) >= 2:
            continue
        selected.append(item)
        selected_urls.add(item.get("href"))
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

    return selected


def search_public_web(
    product,
    queries,
    results_per_query,
    search_provider="DuckDuckGo",
    google_api_key="",
    google_cx="",
    selected_machines=None,
):
    results = []
    seen_urls = set()
    raw_results_per_query = min(max(results_per_query * 5, 8), 20)

    if search_provider == "Google Programmable Search API":
        if not google_api_key or not google_cx:
            return [
                {
                    "query": "",
                    "title": "Thiếu cấu hình Google Search",
                    "href": "",
                    "body": "Bạn cần nhập Google API key và Search Engine ID (cx), hoặc chuyển về DuckDuckGo.",
                }
            ]

        for query in queries:
            try:
                found_items = search_google_custom(query, google_api_key, google_cx, raw_results_per_query)
            except Exception as error:
                continue

            accepted_for_query = 0
            for item in found_items:
                if accepted_for_query >= results_per_query:
                    break
                url = item.get("href") or item.get("url") or ""
                if url in seen_urls:
                    continue

                title = item.get("title", "").strip()
                body = item.get("body", "").strip()
                relevance_score, relevance_reasons = research_relevance_score(product, title, body, url, selected_machines)
                source_role = classify_research_source(product, query, title, body, url)
                if source_role == "product":
                    relevance_score = max(relevance_score, 9)
                    relevance_reasons.append("đúng website sản phẩm Master Electric")
                if is_blocked_result(title, body, url) or relevance_score < 2:
                    continue
                if not result_matches_product(product, title, body, selected_machines=selected_machines):
                    continue

                seen_urls.add(url)
                results.append(
                    {
                        "query": query,
                        "title": title,
                        "href": url,
                        "body": body,
                        "relevance_score": relevance_score,
                        "relevance_reasons": relevance_reasons,
                        "source_role": source_role,
                    }
                )
                accepted_for_query += 1

        return enrich_search_results_with_page_text(balance_research_results(results), product)

    with DDGS() as ddgs:
        for query in queries:
            try:
                found_items = ddgs.text(query, max_results=raw_results_per_query)
            except Exception as error:
                continue

            accepted_for_query = 0
            for item in found_items:
                if accepted_for_query >= results_per_query:
                    break
                url = item.get("href") or item.get("url") or ""
                if url in seen_urls:
                    continue

                title = item.get("title", "").strip()
                body = item.get("body", "").strip()
                relevance_score, relevance_reasons = research_relevance_score(product, title, body, url, selected_machines)
                source_role = classify_research_source(product, query, title, body, url)
                if source_role == "product":
                    relevance_score = max(relevance_score, 9)
                    relevance_reasons.append("đúng website sản phẩm Master Electric")
                if is_blocked_result(title, body, url) or relevance_score < 2:
                    continue
                if not result_matches_product(product, title, body, selected_machines=selected_machines):
                    continue

                seen_urls.add(url)
                results.append(
                    {
                        "query": query,
                        "title": title,
                        "href": url,
                        "body": body,
                        "relevance_score": relevance_score,
                        "relevance_reasons": relevance_reasons,
                        "source_role": source_role,
                    }
                )
                accepted_for_query += 1

    return enrich_search_results_with_page_text(balance_research_results(results), product)


def extract_research_signals(search_results):
    text = " ".join(
        f"{item.get('title', '')} {item.get('body', '')} {item.get('research_sample', '')}"
        for item in search_results
    ).lower()
    known_signals = [
        "review",
        "feedback",
        "inbox",
        "đặt hàng",
        "sale",
        "ưu đãi",
        "giá tốt",
        "giá rẻ",
        "chính hãng",
        "authentic",
        "combo",
        "quà tặng",
        "dễ mang theo",
        "tiện lợi",
        "thơm lâu",
        "lưu hương",
        "tư vấn",
        "best seller",
        "hàng sẵn",
    ]

    return [signal for signal in known_signals if signal in text]


def build_research_context(search_results):
    if not search_results:
        return "Không có dữ liệu research công khai."

    grouped = {
        "product": [],
        "product_candidate": [],
        "technical": [],
        "insight": [],
    }
    for item in search_results:
        grouped.setdefault(item.get("source_role", "technical"), []).append(item)

    def format_group(items, max_items):
        notes = []
        for item in items[:max_items]:
            title = clean_model_text(item.get("title", ""))[:140]
            body = clean_model_text(item.get("research_sample") or item.get("body", ""))[:420]
            score = item.get("relevance_score", 0)
            notes.append(f"- {title} | độ phù hợp {score}/10 | {body}")
        return "\n".join(notes) if notes else "- Chưa có nguồn đủ phù hợp."

    product_notes = format_group(grouped["product"] + grouped["product_candidate"], 3)
    technical_notes = format_group(grouped["technical"], 5)
    insight_notes = format_group(grouped["insight"], 3)
    unverified_note = (
        "Không dùng thông số riêng của sản phẩm đối thủ để gán cho sản phẩm hiện tại. "
        "Các thông số như điện áp nguồn nuôi, kích thước, cấp chính xác, tỷ số CT, lưu lượng, công suất hoặc chuẩn bảo vệ "
        "chỉ được viết khi có trong brief, ảnh tem, website chính hãng hoặc datasheet đúng mã."
    )

    result_notes = []
    for index, item in enumerate(search_results[:10], start=1):
        title = clean_model_text(item.get("title", ""))[:140]
        body = clean_model_text(item.get("research_sample") or item.get("body", ""))[:520]
        query = clean_model_text(item.get("query", ""))[:120]
        score = item.get("relevance_score", 0)
        reasons = ", ".join(item.get("relevance_reasons", [])) or "chưa rõ lý do"
        trust_label = source_trust_label(score, item.get("href", ""))
        source_type = item.get("source_type", "Snippet search")
        source_role = research_source_label(item.get("source_role"))
        result_notes.append(
            f"{index}. Query: {query}\n"
            f"   Loại nguồn: {source_role} | {source_type}\n"
            f"   Độ phù hợp: {score}/10 ({reasons})\n"
            f"   Nhãn nguồn: {trust_label}\n"
            f"   Nội dung thấy được: {title}. {body}"
        )

    result_text = "\n".join(result_notes)

    return f"""
Đã chọn {len(search_results)} nguồn công khai sau khi cân bằng nguồn sản phẩm, kỹ thuật và insight.

NGUỒN SẢN PHẨM / THÔNG SỐ ĐÚNG MÃ:
{product_notes}

KIẾN THỨC KỸ THUẬT CÓ THỂ DÙNG ĐỂ GIẢI THÍCH:
{technical_notes}

INSIGHT KHÁCH HÀNG / GÓC CONTENT:
{insight_notes}

THÔNG TIN CHƯA XÁC MINH, KHÔNG ĐƯỢC TỰ VIẾT:
{unverified_note}

CHI TIẾT NGUỒN ĐÃ CHỌN:
{result_text}

Chỉ nguồn sản phẩm chính hãng/đúng mã mới được dùng để xác nhận thông số. Nguồn kỹ thuật dùng để giải thích khái niệm. Nguồn insight chỉ dùng cho nỗi đau, hook và tình huống; không dùng để xác nhận thông số sản phẩm.
""".strip()


def run_public_research(
    product,
    brand_name,
    audience,
    platforms,
    results_per_query,
    search_provider,
    use_ai_queries,
    google_api_key="",
    google_cx="",
    expanded=True,
    max_queries=10,
    selected_machines=None,
):
    with st.spinner("Đang tạo từ khóa tìm kiếm..."):
        search_queries = generate_search_queries(
            product,
            brand_name,
            audience,
            platforms,
            use_ai_queries=use_ai_queries,
            max_queries=max_queries,
            selected_machines=selected_machines,
        )

    with st.expander("Từ khóa AI dùng để search", expanded=expanded):
        for query in search_queries:
            st.write(f"- {query}")

    with st.spinner("Đang tìm nội dung công khai trên web..."):
        search_results = search_public_web(
            product,
            search_queries,
            results_per_query,
            search_provider=search_provider,
            google_api_key=google_api_key,
            google_cx=google_cx,
            selected_machines=selected_machines,
        )

    with st.expander("Kết quả công khai tìm được", expanded=expanded):
        if not search_results:
            st.info("Chưa tìm thấy kết quả phù hợp sau khi lọc nguồn rác và nguồn lệch nội dung.")

        for result in search_results:
            st.markdown(f"**{result['title'] or 'Không có tiêu đề'}**")
            if result["href"]:
                st.caption(result["href"])
            score = result.get("relevance_score", 0)
            reasons = ", ".join(result.get("relevance_reasons", [])) or "chưa rõ lý do"
            source_role = research_source_label(result.get("source_role"))
            st.caption(f"{source_role} | {source_trust_label(score, result.get('href', ''))} | Độ phù hợp: {score}/10 | {reasons}")
            st.write(result["body"])
            st.divider()

    return search_results


def analyze_uploaded_images(uploaded_images):
    if not uploaded_images:
        return "Chưa có ảnh người dùng upload."

    image_notes = []
    for index, uploaded_image in enumerate(uploaded_images, start=1):
        image_bytes = uploaded_image.getvalue()
        try:
            image_bytes_for_model = prepare_image_for_vision(image_bytes)
        except Exception:
            image_bytes_for_model = image_bytes

        prompt = """
Bạn là trợ lý phân tích ảnh sản phẩm để viết caption bán hàng.

Hãy mô tả ngắn gọn ảnh này bằng tiếng Việt:
- Ảnh có sản phẩm gì?
- Màu sắc/bố cục/cảm giác hình ảnh ra sao?
- Điểm nào có thể dùng để viết caption?
- Ảnh phù hợp kiểu bài nào trên Facebook/Instagram?

Không bịa thương hiệu, giá, feedback hoặc công dụng nếu ảnh không thể hiện rõ.
Trả lời tối đa 6 dòng.
"""

        last_error = None
        for context_tokens in (VISION_CONTEXT_TOKENS, VISION_RETRY_CONTEXT_TOKENS):
            try:
                response = ollama_chat_with_timeout(
                    model=VISION_MODEL,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt,
                            "images": [image_bytes_for_model],
                        }
                    ],
                    options={"temperature": 0.4, "num_ctx": context_tokens, "num_predict": 220},
                )
                image_notes.append(f"Ảnh {index} ({uploaded_image.name}):\n{response['message']['content']}")
                break
            except Exception as error:
                last_error = error
                if "exceeds the available context size" in str(error) and context_tokens != VISION_RETRY_CONTEXT_TOKENS:
                    continue

                error_text = str(last_error)
                if "exceeds the available context size" in error_text:
                    image_notes.append(
                        f"Ảnh {index} ({uploaded_image.name}): Chưa phân tích được ảnh vì ảnh quá lớn so với ngữ cảnh model. "
                        "Hãy thử ảnh nhỏ hơn hoặc tăng VISION_RETRY_CONTEXT_TOKENS trong app.py."
                    )
                else:
                    image_notes.append(f"Ảnh {index} ({uploaded_image.name}): Chưa phân tích được ảnh. Lỗi: {last_error}")
                break

    return "\n\n".join(image_notes)


def call_json_model(model, prompt, max_tokens=1200, context_tokens=4096):
    response = ollama_chat_with_timeout(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "Bạn là trợ lý viết nội dung mạng xã hội bằng tiếng Việt. "
                    "Chỉ dùng tiếng Việt tự nhiên, có thể dùng emoji phổ biến. "
                    "Tuyệt đối không dùng tiếng Trung, tiếng Nhật, tiếng Hàn hoặc tiếng Anh dài trong caption, kể cả khi dữ liệu đầu vào có ngôn ngữ đó. "
                    "Nếu gặp thông tin nước ngoài, hãy diễn đạt lại hoàn toàn bằng tiếng Việt. "
                    "Chỉ trả về JSON hợp lệ, không dùng markdown."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        format="json",
        options={"temperature": 0.55, "num_ctx": context_tokens, "num_predict": max_tokens},
    )
    return response["message"]["content"]


def parse_json_response(text, fallback):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        if not match:
            return fallback

    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return fallback


def normalize_post(item, fallback_day=""):
    hashtags = normalize_hashtags(item.get("hashtags", []))
    caption = remove_hashtags_from_caption(polish_caption_text(item.get("caption", "")))
    return {
        "id": item.get("id") or make_id("post"),
        "day": clean_model_text(item.get("day") or fallback_day),
        "platforms": item.get("platforms") or ["Facebook", "Instagram"],
        "topic": clean_model_text(item.get("topic", "")),
        "caption": caption,
        "hashtags": hashtags,
        "cta": clean_model_text(item.get("cta", "")),
        "image_guidance": clean_model_text(item.get("image_guidance", "")),
        "content_role": clean_model_text(item.get("content_role", "")),
        "content_machine": clean_model_text(item.get("content_machine", "")),
        "hook_angle": clean_model_text(item.get("hook_angle", "")),
        "kpi_goal": clean_model_text(item.get("kpi_goal", "")),
        "reels_script": clean_model_text(item.get("reels_script", "")),
        "status": item.get("status", "draft"),
        "created_at": item.get("created_at", datetime.now().isoformat(timespec="seconds")),
        "image_files": item.get("image_files", []),
        "metrics": item.get("metrics", {}),
        "source": item.get("source", "AI"),
    }


def polish_post_hashtags(post, product, audience=""):
    generic_hashtags = {
        "#NuocHoaMini",
        "#MuiHuongMoiNgay",
        "#SanPham",
        "#HangMoi",
        "#Sale",
        "#HashtagSatSanPham",
        "#NhuCauKhachHang",
        "#GoiYHomNay",
        "#TenSanPhamKhongDau",
        "#NhuCauCuThe",
        "#DoiTuongKhachHang",
        "#AoLenNu",
        "#PhoiDoHangNgay",
        "#ThoiTrangNu",
        "#TrendyStyle",
        "#Hashtag1",
        "#Hashtag2",
        "#TenSanPhamThat",
        "#NhuCauThat",
        "#KhachHangThat",
    }
    hashtags = post.get("hashtags", [])
    has_generic_pair = "#NuocHoaMini" in hashtags and "#MuiHuongMoiNgay" in hashtags
    generic_words = [tag.lstrip("#").lower() for tag in generic_hashtags]
    has_placeholder = any(
        tag in generic_hashtags
        or any(generic_word in tag.lower() for generic_word in generic_words)
        for tag in hashtags
    )

    if not hashtags or has_generic_pair or has_placeholder or all(tag in generic_hashtags for tag in hashtags):
        post["hashtags"] = fallback_hashtags(product, audience)

    return post


def fallback_caption(product, audience, day_number, topic, content_brief="", content_machine=""):
    clean_product = short_product_name(product) or "sản phẩm này"
    profile = product_profile(product, content_brief)
    brand_label = extract_brand_label(content_brief)
    clean_audience = audience.strip()
    if clean_audience.lower() in {"all", "mọi người", "tat ca", "tất cả"}:
        clean_audience = "khách đang cần đúng linh kiện để lắp đặt hoặc thay thế"
    elif not clean_audience:
        clean_audience = "khách đang cần tư vấn"
    elif len(clean_audience.split()) > 10:
        clean_audience = "thợ điện, kỹ thuật bảo trì và đơn vị thi công tủ điện"

    normalized_context = remove_vietnamese_accents(f"{clean_product} {content_brief} {content_machine}").lower()
    normalized_machine = remove_vietnamese_accents(content_machine).lower()
    is_incident_machine = any(word in normalized_machine for word in ["su co", "bai hoc an toan", "chay", "chap dien", "qua nhiet"])
    is_news_machine = any(word in normalized_machine for word in ["tin tuc nganh dien", "evn", "tiet kiem dien", "phu tai"])
    is_checklist_machine = "checklist" in normalized_machine
    is_thanks_machine = any(word in normalized_machine for word in ["cam on", "ghi nhan", "feedback"])
    if not any([is_incident_machine, is_news_machine, is_checklist_machine, is_thanks_machine]):
        is_incident_machine = any(word in normalized_context for word in ["su co", "bai hoc an toan", "chay", "chap dien", "qua nhiet"])
        is_news_machine = any(word in normalized_context for word in ["tin tuc nganh dien", "evn", "tiet kiem dien", "phu tai"])
        is_checklist_machine = "checklist" in normalized_context
        is_thanks_machine = any(word in normalized_context for word in ["cam on", "ghi nhan", "feedback"])
    is_technical = any(word in normalized_context for word in ["tu dien", "dien", "cong nghiep", "b2b", "ky thuat", "linh kien", "lap dat"])
    is_social_style = any(word in normalized_context for word in ["facebook trending", "de tiep can", "gan gui", "chot inbox"])
    is_company_intro = any(word in normalized_machine for word in ["gioi thieu", "nang luc cong ty"])
    is_behind_scene = any(word in normalized_machine for word in ["hau truong", "kho", "dong hang"])
    is_qa_machine = any(word in normalized_machine for word in ["q&a", "hoi dap", "nguoi moi"])
    is_follow_machine = any(word in normalized_machine for word in ["tang follow", "luu bai"])
    is_map_machine = any(word in normalized_machine for word in ["ban do san pham", "nhu cau"])
    is_combo_machine = any(word in normalized_machine for word in ["combo", "giai phap he thong"])

    if profile["key"] == "power_quality_meter":
        machine_templates = {
            "term": (
                "PF và DPF cùng nói về hệ số công suất, nhưng vì sao đồng hồ chất lượng điện năng cần đo cả hai?",
                f"{clean_product} không chỉ theo dõi điện áp, dòng điện và kWh. Thiết bị đo đồng thời PF và DPF để kỹ sư phân biệt ảnh hưởng của công suất phản kháng với ảnh hưởng do sóng hài.\n\n💡 Khi hệ thống có biến tần, UPS, bộ chỉnh lưu hoặc tải phi tuyến, chỉ nhìn một chỉ số PF có thể chưa đủ để hiểu nguyên nhân vận hành kém hiệu quả.\n\n📖 Đồng hồ còn đo THDv/THDi, phân tích sóng hài đến bậc 50, theo dõi mất cân bằng pha và Demand/Maximum Demand.\n\n⚙️ Dữ liệu có thể truyền qua RS485 Modbus RTU về SCADA, EMS hoặc BMS để theo dõi tập trung.\n\n{profile['cta']}",
            ),
            "myth": (
                "Đã có số kWh thì đã đủ để quản lý điện năng nhà máy? Chưa hẳn.",
                f"kWh cho biết lượng điện đã tiêu thụ, nhưng không chỉ ra đầy đủ vì sao hệ thống có thể nóng, tổn hao hoặc giảm hệ số công suất.\n\n🧨 Với {clean_product}, đội kỹ thuật có thể theo dõi thêm PF/DPF, công suất phản kháng, THDv/THDi, từng bậc sóng hài đến bậc 50 và mức mất cân bằng điện áp/dòng điện.\n\n❌ Nếu chỉ nhìn điện năng tổng, doanh nghiệp dễ bỏ qua phụ tải đỉnh, tải phi tuyến và những dấu hiệu ảnh hưởng tụ bù, máy biến áp hoặc dây trung tính.\n\n🔍 Demand/Maximum Demand và 6 biểu giá giúp nhìn rõ hơn thời điểm và cách hệ thống sử dụng điện.\n\n✅ Đây là công cụ phân tích vận hành, không chỉ là đồng hồ cộng dồn kWh.\n\n{profile['cta']}",
            ),
            "checklist": (
                f"Trước khi triển khai {clean_product}, đội kỹ thuật nên chốt 5 câu hỏi này.",
                "✅ Hệ thống điện 3 pha đang cần đo những chỉ số nào: kW, kVAR, kVA, PF/DPF hay điện năng hai chiều?\n\n🔍 Có biến tần, UPS, bộ chỉnh lưu hoặc tải phi tuyến cần phân tích THDv/THDi và sóng hài không?\n\n📏 Có cần giám sát mất cân bằng pha, dòng trung tính và phụ tải đỉnh Demand/Maximum Demand không?\n\n🔧 Dữ liệu sẽ đọc tại chỗ hay truyền qua RS485 Modbus RTU về SCADA, EMS, BMS hoặc PLC?\n\n📌 Cần quản lý điện năng theo một hay nhiều khung giờ/biểu giá?\n\n" + profile["cta"],
            ),
            "review": (
                f"{clean_product} phù hợp nhất khi doanh nghiệp cần nhìn sâu hơn con số điện năng tiêu thụ.",
                "🔍 Thiết bị phù hợp cho nhà máy, tòa nhà, data center, hệ thống điện mặt trời, BESS hoặc trạm sạc có nhu cầu giám sát điện năng và chất lượng điện năng cùng lúc.\n\n🎯 Điểm đáng chú ý là đo PF/DPF, THDv/THDi, sóng hài đến bậc 50, mất cân bằng pha và Demand/Maximum Demand.\n\n⚙️ RS485 Modbus RTU giúp đưa dữ liệu về SCADA, EMS, BMS, PLC hoặc nền tảng IoT thay vì chỉ xem tại mặt tủ.\n\n📌 Sản phẩm không nên được chọn chỉ vì có nhiều chỉ số; cần xác định rõ loại tải, mục tiêu giám sát và kiến trúc truyền thông của hệ thống.\n\n" + profile["cta"],
            ),
            "follow": (
                "Lưu lại 6 chỉ số nên theo dõi khi nhà máy sử dụng nhiều biến tần hoặc UPS.",
                "🔖 PF và DPF để phân biệt ảnh hưởng công suất phản kháng và méo dạng.\n\n📋 THDv/THDi và từng bậc sóng hài để đánh giá chất lượng điện năng.\n\n💡 Mất cân bằng điện áp/dòng điện để phát hiện nguy cơ nóng và tăng tổn hao.\n\n➕ Demand/Maximum Demand để theo dõi phụ tải đỉnh.\n\n📊 kWh, kVARh, kVAh và điện năng phát ngược để quản lý dòng năng lượng.\n\n⚡ Dữ liệu RS485 Modbus để đưa về SCADA/EMS/BMS và theo dõi tập trung.\n\nTheo dõi page để xem thêm các bài giải thích từng chỉ số bằng ví dụ dễ hiểu.",
            ),
            "inbox": (
                f"Muốn biết {clean_product} có phù hợp hệ thống hiện tại không? Đừng chỉ gửi ảnh mặt đồng hồ.",
                "📩 Để tư vấn sát hơn, đội kỹ thuật cần biết:\n\n1️⃣ Hệ thống 3 pha và loại tải đang vận hành, đặc biệt biến tần/UPS/tải phi tuyến.\n\n2️⃣ Các chỉ số cần giám sát: PF/DPF, THDv/THDi, sóng hài, mất cân bằng pha, Demand hay điện năng đa biểu giá.\n\n3️⃣ Yêu cầu truyền dữ liệu: đọc tại chỗ hay kết nối RS485 Modbus với SCADA, EMS, BMS hoặc PLC.\n\nNếu dùng CT ngoài, bổ sung tỷ số CT và sơ đồ đấu nối. CT là một thông tin đầu vào, không phải trọng tâm duy nhất của bài toán.\n\n" + profile["cta"],
            ),
            "company": (
                f"⚡ {brand_label} – GIẢI PHÁP GIÁM SÁT VÀ PHÂN TÍCH CHẤT LƯỢNG ĐIỆN NĂNG",
                f"{clean_product} giúp doanh nghiệp đi xa hơn việc chỉ ghi nhận kWh.\n\n🏢 Giám sát điện áp, dòng điện, công suất và điện năng trong hệ thống 3 pha.\n\n📊 Theo dõi PF/DPF, THDv/THDi, sóng hài đến bậc 50, mất cân bằng pha và phụ tải đỉnh.\n\n⚙️ Kết nối RS485 Modbus RTU với SCADA, EMS, BMS, PLC và IoT.\n\n🧾 Quản lý điện năng theo 6 biểu giá, hỗ trợ theo dõi vận hành theo từng khung thời gian.\n\n{brand_label} hỗ trợ tư vấn theo kiến trúc hệ thống và mục tiêu giám sát, không chỉ đối chiếu tên mã.\n\n{profile['cta']}",
            ),
        }
        if "myth" in normalized_machine or "hieu lam" in normalized_machine:
            hook, body = machine_templates["myth"]
        elif "checklist" in normalized_machine:
            hook, body = machine_templates["checklist"]
        elif "review" in normalized_machine:
            hook, body = machine_templates["review"]
        elif "tang follow" in normalized_machine or "luu bai" in normalized_machine:
            hook, body = machine_templates["follow"]
        elif "keo inbox" in normalized_machine or "chot" in normalized_machine:
            hook, body = machine_templates["inbox"]
        elif "gioi thieu" in normalized_machine or "nang luc" in normalized_machine:
            hook, body = machine_templates["company"]
        else:
            hook, body = machine_templates["term"]
        return f"{hook}\n\n{body}"

    if any([is_company_intro, is_behind_scene, is_qa_machine, is_follow_machine, is_map_machine, is_combo_machine]):
        solution_title = f"⚡ {brand_label} – GIẢI PHÁP THIẾT BỊ ĐIỆN CÔNG NGHIỆP CHO TỦ ĐIỆN"
        catalog_signal_count = sum(
            1
            for terms in [
                ["quat", "lam mat", "thong gio"],
                ["tu bu", "cos", "kvar", "cuon khang"],
                ["mccb", "cb", "relay", "cau chi"],
                ["bien dong", "ct", "dong ho", "do luong"],
            ]
            if any(term in normalized_context for term in terms)
        )
        if profile["key"] == "catalog" or catalog_signal_count >= 2:
            solution_title = f"⚡ {brand_label} – GIẢI PHÁP THIẾT BỊ ĐIỆN CÔNG NGHIỆP CHO TỦ ĐIỆN"
        elif profile["key"] in {"capacitor", "reactor"}:
            solution_title = f"⚡ {brand_label} – GIẢI PHÁP CHẤT LƯỢNG ĐIỆN NĂNG"
        elif profile["key"] == "fan":
            solution_title = f"⚡ {brand_label} – GIẢI PHÁP LÀM MÁT TỦ ĐIỆN CÔNG NGHIỆP"
        elif profile["key"] == "protection":
            solution_title = f"⚡ {brand_label} – GIẢI PHÁP BẢO VỆ HỆ THỐNG ĐIỆN CÔNG NGHIỆP"
        elif profile["key"] in {"meter", "power_quality_meter"}:
            solution_title = f"⚡ {brand_label} – GIẢI PHÁP ĐO LƯỜNG VÀ GIÁM SÁT ĐIỆN"

        company_templates = {
            "company": (
                solution_title,
                f"Trong hệ thống điện công nghiệp, chọn đúng thiết bị ảnh hưởng trực tiếp đến độ ổn định vận hành, tuổi thọ linh kiện và thời gian xử lý sự cố của doanh nghiệp.\n\nNếu chọn sai thông số hoặc thay thiết bị theo cảm tính, hệ thống có thể gặp các vấn đề như:\n\n❌ Mua nhầm mã, mất thời gian đổi hàng\n❌ Thiết bị vận hành kém ổn định\n❌ Tủ điện nóng, CB/MCCB nhảy hoặc thiết bị nhanh xuống cấp\n❌ Khó kiểm soát thông số khi bảo trì\n❌ Tăng rủi ro dừng máy trong nhà xưởng\n\n{brand_label} hỗ trợ khách chọn thiết bị theo nhu cầu thực tế:\n\n🔹 Tư vấn theo ảnh tem/mã cũ\nGiúp đối chiếu nhanh thông số, hạn chế chọn nhầm.\n\n🔹 Gợi ý theo tình trạng tủ điện\nDựa trên tải, không gian lắp, vị trí thiết bị và vấn đề khách đang gặp.\n\n🔹 Định hướng nhóm sản phẩm phù hợp\nLàm mát tủ điện, bù công suất, bảo vệ đóng cắt, đo lường và phụ kiện tủ điện.\n\n🔹 Hỗ trợ nội dung kỹ thuật dễ hiểu\nGiúp thợ điện, kỹ thuật bảo trì và chủ xưởng có thêm checklist để lưu lại khi cần.\n\n✅ Tư vấn sát nhu cầu\n✅ Hạn chế mua sai mã\n✅ Tối ưu thời gian xử lý\n✅ Tăng độ tin cậy cho hệ thống\n\n{brand_label} không chỉ cung cấp từng thiết bị riêng lẻ, mà còn hướng đến giải pháp phù hợp cho tủ điện công nghiệp, nhà máy và công trình M&E.\n\n👉 Cần đối chiếu {clean_product} hoặc nhóm thiết bị đang dùng? Gửi ảnh tem, ảnh tủ điện hoặc thông số hiện có để được hỗ trợ chọn cấu hình phù hợp.",
            ),
            "behind": (
                f"⚙️ HẬU TRƯỜNG {brand_label} – KIỂM TRA KỸ TRƯỚC KHI GIAO HÀNG",
                f"Một đơn hàng kỹ thuật không nên chỉ đóng gói cho nhanh. Với thiết bị tủ điện, sai một thông số nhỏ có thể làm thợ mất thời gian tháo lắp, đổi hàng hoặc dừng việc tại công trình.\n\nTrước khi tư vấn/giao các sản phẩm như {clean_product}, những điểm nên rà lại gồm:\n\n❌ Mã cũ không trùng model mới\n❌ Sai điện áp, dòng A, kA hoặc kích thước lắp\n❌ Không kiểm tra vị trí trong tủ\n❌ Chỉ nhìn hình sản phẩm rồi chốt vội\n\nQuy trình nên làm kỹ hơn:\n\n🔹 Nhận ảnh tem/mã cũ từ khách\n🔹 Đối chiếu thông số chính\n🔹 Hỏi thêm tình trạng tủ hoặc tải đang dùng\n🔹 Kiểm tra nhóm sản phẩm phù hợp trước khi báo mẫu\n\n✅ Đơn hàng chắc hơn\n✅ Khách dễ kiểm tra lại\n✅ Hạn chế mua nhầm\n✅ Tư vấn có cơ sở hơn\n\n👉 Cần thay {clean_product}? Gửi ảnh tem hoặc ảnh vị trí lắp, {brand_label} hỗ trợ đối chiếu trước khi đặt.",
            ),
            "qa": (
                f"Khách hỏi nhanh: mua {clean_product} thì cần gửi shop thông tin gì trước?",
                f"Câu trả lời ngắn là: đừng chỉ gửi tên sản phẩm.\n\nVới nhóm {profile['label']}, nếu thiếu thông tin thì rất dễ gặp các lỗi:\n\n❌ Chọn sai mã\n❌ Sai thông số lắp đặt\n❌ Không khớp vị trí trong tủ\n❌ Mất thời gian đổi hàng\n\nTrước khi tư vấn, khách nên gửi:\n\n✅ {profile['image_checks']}\n✅ Ảnh vị trí lắp hoặc tủ đang dùng nếu có\n✅ Nhu cầu thay mới, thay tương đương hay lắp bổ sung\n\nCó đủ thông tin này, {brand_label} tư vấn sẽ sát hơn và khách cũng dễ kiểm tra lại trước khi đặt.\n\n👉 Cần đối chiếu {clean_product}? Gửi ảnh tem/mã cũ để được hỗ trợ.",
            ),
            "follow": (
                f"📌 LƯU LẠI PAGE {brand_label} NẾU ANH EM THƯỜNG LÀM TỦ ĐIỆN",
                f"Không phải lúc nào khách cũng cần mua ngay. Nhưng khi tủ nóng, CB hay nhảy, tụ bù có vấn đề hoặc cần thay phụ kiện đúng mã, có một nơi đăng checklist dễ hiểu sẽ giúp tra nhanh hơn.\n\nPage sẽ tập trung vào các nội dung thực tế:\n\n🔹 Cách đọc tem/thông số\n🔹 Dấu hiệu nên kiểm tra thiết bị\n🔹 Lỗi chọn sai hay gặp\n🔹 Bảng chọn nhanh theo nhu cầu\n🔹 Q&A từ câu hỏi khách gửi thật\n\n✅ Dễ lưu lại\n✅ Dễ gửi cho đồng đội/kỹ thuật\n✅ Dễ đối chiếu trước khi mua\n✅ Phù hợp thợ điện, bảo trì nhà máy và đơn vị thi công tủ\n\n👉 Cần tư vấn riêng cho {clean_product}? Gửi ảnh tem/thông số để {brand_label} đối chiếu.",
            ),
            "map": (
                f"🧭 {brand_label} – BẢN ĐỒ NHÓM THIẾT BỊ CHO TỦ ĐIỆN CÔNG NGHIỆP",
                f"Một tủ điện công nghiệp không chỉ có một món cần quan tâm. Nếu mục tiêu là vận hành ổn định, khách nên nhìn theo nhu cầu của hệ thống.\n\nCác vấn đề thường gặp:\n\n❌ Tủ điện nóng khi chạy liên tục\n❌ Hệ số công suất thấp, cần bù công suất\n❌ CB/MCCB hay nhảy, khó xác định nguyên nhân\n❌ Cần đo lường, giám sát dòng/áp/công suất\n❌ Cần thay phụ kiện đúng mã trong tủ\n\nNhóm giải pháp nên kiểm tra:\n\n🔹 Làm mát tủ điện\nQuạt tủ điện, tấm lọc gió, thermostat, giải pháp hỗ trợ tản nhiệt.\n\n🔹 Bù công suất\nTụ bù, cuộn kháng, bộ điều khiển tụ bù.\n\n🔹 Bảo vệ và đóng cắt\nMCCB, CB, relay, contactor, cầu chì.\n\n🔹 Đo lường và giám sát\nBiến dòng CT, đồng hồ đo điện, thiết bị theo dõi thông số.\n\n✅ Nhìn đúng nhu cầu\n✅ Chọn đúng nhóm sản phẩm\n✅ Hạn chế mua sai mã\n✅ Dễ lập checklist bảo trì\n\n👉 Gửi ảnh tủ điện hoặc thiết bị cũ, {brand_label} hỗ trợ gợi ý nhóm sản phẩm cần kiểm tra.",
            ),
            "combo": (
                solution_title,
                f"Nhiều vấn đề trong tủ điện không nên xử lý bằng một món rời rạc. Trước khi thay thiết bị, khách nên nhìn lại toàn bộ tình huống vận hành.\n\nNếu hệ thống có dấu hiệu bất ổn, doanh nghiệp có thể gặp:\n\n❌ Tủ điện nóng, linh kiện nhanh xuống cấp\n❌ MCCB/CB nhảy nhưng chưa rõ nguyên nhân\n❌ Tụ bù đóng cắt không ổn định\n❌ Thông số đo lường không được kiểm soát tốt\n❌ Dừng máy hoặc mất thời gian xử lý tại xưởng\n\n{brand_label} có thể hỗ trợ theo hướng giải pháp đồng bộ:\n\n🔹 Kiểm tra nhóm làm mát\nQuạt tủ điện, lưới lọc, thermostat, tình trạng bụi/ẩm.\n\n🔹 Kiểm tra nhóm bù công suất\nTụ bù, cuộn kháng, bộ điều khiển, cosφ và nguy cơ sóng hài.\n\n🔹 Kiểm tra nhóm bảo vệ\nMCCB/CB, dòng tải, khả năng cắt kA, số cực, điện áp làm việc.\n\n🔹 Kiểm tra nhóm đo lường\nBiến dòng CT, đồng hồ đo, sơ đồ đấu dây và nguồn nuôi.\n\n✅ Tối ưu hệ thống\n✅ Giảm rủi ro chọn sai thiết bị\n✅ Hỗ trợ vận hành ổn định hơn\n✅ Dễ bảo trì và kiểm soát thông số\n\n👉 Gửi ảnh tủ, ảnh tem thiết bị cũ hoặc mô tả tình trạng, {brand_label} sẽ gợi ý hướng kiểm tra phù hợp hơn.",
            ),
        }
        if is_company_intro:
            hook, body = company_templates["company"]
        elif is_behind_scene:
            hook, body = company_templates["behind"]
        elif is_qa_machine:
            hook, body = company_templates["qa"]
        elif is_follow_machine:
            hook, body = company_templates["follow"]
        elif is_map_machine:
            hook, body = company_templates["map"]
        else:
            hook, body = company_templates["combo"]
        return f"{hook}\n\n{body}"

    if profile["key"] != "protection" and ("keo inbox" in normalized_machine or "chot lead" in normalized_machine):
        hook = f"Không chắc nên chọn {clean_product} theo mã nào? Gửi thông tin trước khi chốt sẽ đỡ mua nhầm."
        body = (
            f"Với nhóm {profile['label']}, khách không cần mô tả quá dài. "
            f"Chỉ cần gửi ảnh tem/mã cũ, ảnh vị trí lắp hoặc thông tin đang dùng để {brand_label} đối chiếu các điểm chính: {profile['image_checks']}.\n\n"
            "Cách này phù hợp cho thợ điện, kỹ thuật bảo trì hoặc bên thi công cần xử lý nhanh nhưng vẫn muốn đúng thông số.\n\n"
            f"{profile['cta']}"
        )
        return f"{hook}\n\n{body}"

    if profile["key"] != "fan":
        if profile["key"] == "protection":
            protection_cta = (
                f"Gửi ảnh tem MCCB cũ, dòng tải hoặc ảnh tủ điện, {brand_label} hỗ trợ đối chiếu mẫu phù hợp trước khi bạn đặt hàng."
            )
            machine_templates = {
                "myth": (
                    "MCCB cứ chọn dòng A lớn hơn là sẽ đỡ nhảy? Không hẳn.",
                    f"Với {clean_product}, chọn dòng A quá lớn có thể làm thiết bị bảo vệ không còn sát với tải thực tế.\n\nKhi MCCB cũ hay nhảy, bạn nên kiểm tra trước:\n\n✅ Dòng tải thực tế\n✅ Số cực: 3P nếu tủ đang dùng 3P\n✅ Điện áp làm việc\n✅ Khả năng cắt kA / Icu / Ics\n✅ Kích thước và vị trí lắp trong tủ\n\nNguyên nhân MCCB nhảy có thể do quá tải thật, thiết bị xuống cấp, đấu nối nóng hoặc chọn sai thông số ngay từ đầu.\n\nĐừng thay theo kiểu đoán dòng.\n\n{protection_cta}",
                ),
                "review": (
                    f"{clean_product} phù hợp khi cần thay MCCB cho tủ máy hoặc tủ phân phối, nhưng phải đối chiếu theo tình huống lắp thực tế.",
                    f"Với tủ đang cấp cho motor hoặc thiết bị trong xưởng, thông tin cần xem không chỉ là 3P.\n\nTrước khi thay, nên rà lại:\n\n✅ Dòng định mức A\n✅ Khả năng cắt kA / Icu / Ics\n✅ Điện áp làm việc\n✅ Không gian lắp trong tủ\n✅ Thiết bị/tải mà MCCB đang bảo vệ\n\nNếu thay tương đương MCCB cũ, ảnh tem/mã cũ sẽ giúp đối chiếu nhanh hơn nhiều.\n\n{protection_cta}",
                ),
                "bang chon": (
                    "Bảng chọn nhanh trước khi thay MCCB 3P trong tủ điện.",
                    f"Trước khi chốt mã, nên kiểm tra nhanh:\n\n✅ Tủ cấp tải gì: motor, máy, tủ nhánh hay tủ tổng?\n✅ Dòng tải thực tế khoảng bao nhiêu A?\n✅ MCCB cũ là mấy cực?\n✅ Khả năng cắt bao nhiêu kA?\n✅ Điện áp làm việc và không gian lắp có khớp không?\n✅ Có dấu hiệu nóng, nhảy CB, cháy xém đầu cos không?\n\nChọn MCCB không nên chỉ nhìn một thông số dòng A. Nếu sai khả năng cắt hoặc sai ứng dụng, thiết bị bảo vệ có thể không còn phù hợp với hệ thống.\n\n{protection_cta}",
                ),
                "su co": (
                    "MCCB hay nhảy không nên xử lý bằng cách tăng dòng A cho nhanh.",
                    f"Nếu CB/MCCB nhảy liên tục, nguyên nhân có thể là quá tải thật, ngắn mạch, tiếp xúc kém, thiết bị xuống cấp hoặc chọn sai khả năng cắt.\n\nCách an toàn hơn là kiểm tra lại:\n\n✅ Dòng tải thực tế\n✅ Số cực đang dùng\n✅ Khả năng cắt kA / Icu / Ics\n✅ Điện áp làm việc\n✅ Dấu hiệu nóng, lỏng cos hoặc cháy xém trong tủ\n\nChọn đại MCCB lớn hơn có thể làm rủi ro bảo vệ sai tăng lên.\n\n{protection_cta}",
                ),
                "keo inbox": (
                    "Không chắc MCCB cũ nên thay mẫu nào? Gửi tem trước khi chốt sẽ đỡ mua nhầm.",
                    f"Chỉ cần ảnh tem MCCB cũ, ảnh vị trí trong tủ và thông tin tải đang cấp, {brand_label} có thể hỗ trợ đối chiếu các điểm chính:\n\n✅ Dòng A\n✅ Số cực\n✅ Điện áp làm việc\n✅ Khả năng cắt kA / Icu / Ics\n✅ Kích thước lắp trong tủ\n\nCách này phù hợp cho thợ điện, bảo trì nhà máy hoặc chủ xưởng cần thay nhanh nhưng vẫn muốn đúng thông số.\n\n{protection_cta}",
                ),
            }
            if "myth" in normalized_machine or "hieu lam" in normalized_machine:
                hook, body = machine_templates["myth"]
            elif "review" in normalized_machine:
                hook, body = machine_templates["review"]
            elif "bang chon" in normalized_machine:
                hook, body = machine_templates["bang chon"]
            elif "su co" in normalized_machine or "an toan" in normalized_machine:
                hook, body = machine_templates["su co"]
            elif "keo inbox" in normalized_machine:
                hook, body = machine_templates["keo inbox"]
            else:
                keys = ["myth", "review", "bang chon", "su co", "keo inbox"]
                hook, body = machine_templates[keys[(day_number - 1) % len(keys)]]
            return f"{hook}\n\n{body}"

        hooks = [
            f"Trước khi chọn {clean_product}, điều quan trọng không phải là mua nhanh mà là kiểm tra đúng nhu cầu thực tế.",
            f"Nếu hệ thống đang có dấu hiệu bất ổn, đừng vội thay {profile['label']} theo cảm tính.",
            f"Một thiết bị nhỏ trong tủ điện có thể ảnh hưởng lớn nếu chọn sai thông số.",
            f"Khách hỏi về {clean_product} thường cần tư vấn đúng vấn đề trước khi chốt mã.",
            f"Với hàng kỹ thuật như {clean_product}, thông số đúng luôn quan trọng hơn caption hay.",
        ]
        if profile["key"] == "capacitor":
            bodies = [
                "Với tủ tụ bù, nên kiểm tra cos phi hiện tại, dung lượng kVAr đang dùng, tình trạng tụ cũ và tải có nhiều biến tần/sóng hài hay không.\n\nNếu tụ đã phồng, đóng cắt không ổn định hoặc hóa đơn điện vẫn bị phạt công suất phản kháng, cần rà lại cả dung lượng tụ lẫn khả năng cần cuộn kháng bảo vệ.\n\n" + profile["cta"],
                "Tụ bù không nên chọn chỉ theo cảm giác 'thêm vài bình cho đủ'. Chọn thiếu thì cos phi vẫn thấp, chọn sai điều kiện hệ thống thì tụ dễ nhanh xuống cấp.\n\nChecklist nên gửi trước khi tư vấn:\n- Ảnh tủ tụ bù hiện tại\n- Tem tụ cũ/dung lượng kVAr\n- Hóa đơn điện hoặc cos phi đang bị báo thấp\n- Hệ thống có biến tần, UPS, tải điện tử nhiều không\n\n" + profile["cta"],
                "Nhiều xưởng chỉ chú ý thay tụ khi thấy tụ phồng hoặc nổ, nhưng dấu hiệu cần kiểm tra thường xuất hiện sớm hơn: cos phi tụt, contactor đóng cắt bất thường, tủ nóng, hoặc tiền điện bị cộng phạt.\n\nVới trường hợp này, tư vấn đúng phải dựa trên kVAr, điện áp, tình trạng tải và nguy cơ sóng hài chứ không chỉ nhìn tên sản phẩm.\n\n" + profile["cta"],
            ]
        else:
            bodies = [
                f"Trước khi đặt, nên kiểm tra các điểm chính: {profile['image_checks']}.\n\nCách làm này giúp hạn chế mua sai mã, sai thông số hoặc chọn thiết bị không hợp với tình trạng hệ thống.\n\n{profile['cta']}",
                f"Với nhóm {profile['label']}, bài toán thường không chỉ là có hàng hay không, mà là thông số có khớp với hệ thống hiện tại không.\n\nNếu chưa chắc, nên gửi ảnh tem/mã cũ và mô tả ngắn tình trạng đang gặp để được đối chiếu trước.\n\n{profile['cta']}",
                f"Để tư vấn sát hơn, shop cần nhìn thấy thông tin thực tế thay vì đoán: {profile['image_checks']}.\n\nThông tin càng rõ thì khả năng chọn đúng mẫu, đúng ứng dụng và đúng chính sách bảo hành càng cao.\n\n{profile['cta']}",
            ]
        hook = hooks[(day_number - 1) % len(hooks)]
        body = bodies[(day_number - 1) % len(bodies)]
        return f"{hook}\n\n{body}"

    if is_incident_machine:
        hooks = [
            "Một tủ điện quá nóng không chỉ làm thiết bị nhanh xuống cấp, mà còn có thể kéo theo rủi ro dừng cả hệ thống.",
            "Nhìn từ các sự cố chập điện/cháy tủ điện, điểm đáng sợ nhất thường không nằm ở lúc hỏng, mà ở những dấu hiệu bị bỏ qua trước đó.",
            "Tủ điện chạy lâu trong nhà xưởng mà không kiểm tra nhiệt, bụi và thông gió thì rủi ro sẽ tăng dần theo thời gian.",
        ]
        bodies = [
            f"Khi đọc các tin sự cố về tủ điện quá nhiệt hoặc chập điện, bài học rút ra khá rõ: doanh nghiệp nên kiểm tra định kỳ phần thông gió, bụi bẩn, điểm đấu nối và thiết bị bảo vệ.\n\nChecklist nên rà nhanh:\n- Tủ có bị nóng bất thường không\n- Quạt/lưới lọc còn hoạt động tốt không\n- Bên trong có nhiều bụi hoặc hơi ẩm không\n- Dây, terminal, CB/MCCB có dấu hiệu lỏng/nóng không\n- Có cần lắp thêm quạt lọc, thermostat hoặc giải pháp chống ẩm không\n\nVới nhóm làm mát tủ điện, {clean_product} có thể là một lựa chọn cần đối chiếu khi tủ cần bổ sung/thay quạt thông gió. Quan trọng nhất vẫn là chọn đúng mã, đúng nguồn và đúng kích thước trước khi lắp.",
            f"Sự cố điện thường không đến từ một nguyên nhân duy nhất. Nhiệt độ cao, bụi, ẩm, thiết bị bảo vệ không phù hợp hoặc quạt tủ điện yếu đều có thể làm hệ thống vận hành kém ổn định.\n\nNếu tủ đang chạy liên tục trong nhà xưởng, đừng chỉ đợi hỏng mới kiểm tra. Hãy xem lại luồng gió, vị trí lắp quạt, tình trạng lưới lọc và nhiệt độ bên trong tủ.\n\nNếu cần thay quạt tủ điện, có thể gửi ảnh tủ/tem quạt cũ để shop đối chiếu mẫu phù hợp như {clean_product}.",
            f"Bài cảnh báo này không nhằm làm khách hoang mang, mà để nhắc một việc rất thực tế: tủ điện cần được kiểm tra trước mùa nóng hoặc trước giai đoạn chạy tải cao.\n\nCác điểm nên kiểm tra gồm: quạt làm mát, lưới lọc, thermostat, điểm đấu nối, thiết bị bảo vệ và tình trạng bụi/ẩm trong tủ.\n\nNếu chưa chắc tủ nên dùng quạt loại nào, gửi ảnh tủ điện hoặc thông số quạt cũ, shop sẽ hỗ trợ đối chiếu để tránh chọn sai.",
        ]
    elif is_news_machine:
        hooks = [
            "Khi phụ tải tăng hoặc chi phí điện được nhắc nhiều hơn, doanh nghiệp nên nhìn lại hệ thống điện trong xưởng.",
            "Tin ngành điện không chỉ để đọc cho biết. Với nhà xưởng, nó là lời nhắc để kiểm tra lại phần đo lường, bù công suất và làm mát tủ điện.",
            "Tiết kiệm điện không chỉ nằm ở thói quen sử dụng, mà còn ở cách hệ thống điện được kiểm tra và vận hành.",
        ]
        bodies = [
            f"Từ các thông tin về phụ tải, chi phí điện và nhu cầu vận hành ổn định, doanh nghiệp nên rà lại những phần dễ bị bỏ sót: hệ số công suất, tụ bù, thiết bị đo, nhiệt độ tủ điện và tình trạng quạt/lưới lọc.\n\nNếu tủ điện nóng hoặc quạt cũ yếu, nhóm quạt thông gió như {clean_product} là một phần có thể kiểm tra trong kế hoạch bảo trì.\n\nCần tư vấn theo hiện trạng, gửi ảnh tủ điện hoặc thông số đang dùng để shop đối chiếu.",
            f"Một hệ thống điện ổn định thường bắt đầu từ những kiểm tra rất cơ bản: điện áp, dòng tải, nhiệt độ tủ, bụi/ẩm và thiết bị phụ trợ.\n\nVới tủ điện công nghiệp, làm mát không phải chi tiết phụ. Quạt hoạt động yếu hoặc sai thông số có thể làm linh kiện bên trong chịu nhiệt lâu hơn.\n\nNếu cần thay quạt đúng mã/kích thước, shop có thể hỗ trợ đối chiếu {clean_product} với quạt cũ.",
        ]
    elif is_thanks_machine:
        hooks = [
            "Cảm ơn anh/chị đã tin dùng và nhắc đến sản phẩm của shop mình.",
            "Một bài đăng/feedback từ khách luôn là động lực rất thật với team bán hàng kỹ thuật.",
            "Có những đơn hàng không chỉ là bán đúng sản phẩm, mà còn là tư vấn đúng mã để khách yên tâm lắp vào hệ thống.",
            "Feedback của khách giúp shop nhìn lại một điều rất quan trọng: tư vấn đúng ngay từ đầu vẫn là giá trị lớn nhất.",
            "Một lời cảm ơn nhỏ gửi đến anh/chị đã tin tưởng sản phẩm và cách tư vấn của Thien Loc Phat.",
        ]
        bodies = [
            f"Với thiết bị kỹ thuật như {clean_product}, chọn đúng mã quan trọng hơn chọn nhanh.\n\nTrước khi thay quạt tủ điện, anh/chị nên kiểm tra:\n- Mã quạt cũ\n- Nguồn điện\n- Kích thước lắp đặt\n- Ảnh mặt trước/mặt sau\n- Vị trí lắp trong tủ\n\n{brand_label} hỗ trợ đối chiếu thông số trước khi đặt, giúp hạn chế mua nhầm và mất thời gian đổi hàng.",
            f"Nhân tiện từ feedback này, shop chia sẻ thêm một tình huống rất hay gặp: khách có ảnh quạt cũ nhưng chưa chắc model, nguồn điện hoặc kích thước có trùng không.\n\nVới {clean_product}, team sẽ ưu tiên đối chiếu tem, vị trí bắt vít và không gian lắp trong tủ trước khi tư vấn. Cách này không ồn ào nhưng giúp đơn hàng kỹ thuật chắc hơn.",
            f"Nếu anh/chị đang bảo trì tủ điện, đừng chỉ nhìn quạt còn quay hay không. Hãy kiểm tra thêm tiếng ồn, bụi bám, nhiệt độ trong tủ và tem thông số của quạt cũ.\n\n{clean_product} phù hợp khi cần thay đúng nhóm quạt thông gió/làm mát tủ điện. Nhưng trước khi đặt, shop vẫn khuyên gửi ảnh hiện trạng để đối chiếu.",
            f"Một feedback tốt không chỉ để cảm ơn, mà còn là dịp nhắc lại cách mua hàng kỹ thuật cho chắc: có ảnh sản phẩm, có tem thông số, có nhu cầu lắp thực tế thì tư vấn sẽ chính xác hơn.\n\n{brand_label} cảm ơn anh/chị đã tin dùng. Cần kiểm tra mẫu tương tự {clean_product}, cứ gửi ảnh tem/quạt cũ để bên mình xem trước.",
        ]
    elif is_checklist_machine:
        hooks = [
            "Trước khi mua quạt tủ điện, check nhanh vài điểm này để đỡ mất công đổi hàng.",
            "Tủ điện nóng chưa chắc chỉ cần thay quạt. Nhưng quạt là một trong những điểm nên kiểm tra đầu tiên.",
            "Checklist nhỏ cho anh em kỹ thuật trước khi chốt quạt tủ điện.",
        ]
        bodies = [
            f"- Kiểm tra mã quạt cũ\n- Kiểm tra nguồn điện\n- Đo kích thước lắp\n- Xem vị trí bắt vít\n- Kiểm tra hướng gió và không gian trong tủ\n\nNếu đang đối chiếu với {clean_product}, khách có thể gửi ảnh tem/quạt cũ để shop kiểm tra trước. Làm kỹ bước này sẽ giảm rủi ro mua sai nguồn hoặc sai kích thước.",
            f"Với tủ điện công nghiệp, một chi tiết nhỏ như quạt thông gió cũng nên chọn đúng thông số. Sai kích thước hoặc sai nguồn là không lắp được, còn quạt yếu thì hiệu quả làm mát không như mong muốn.\n\nGửi shop ảnh quạt cũ, tem thông số hoặc ảnh vị trí lắp, shop hỗ trợ đối chiếu {clean_product} trước khi đặt.",
        ]
    elif is_technical and is_social_style:
        hooks = [
            "Tủ điện nóng hoài mà quạt cũ chạy yếu? Đừng chọn đại nha anh em 🔧",
            f"Cần thay quạt tủ điện đúng mã? Lưu lại mã {clean_product} này để đối chiếu cho nhanh.",
            "Một cái quạt nhỏ thôi, nhưng chọn sai là mất công đổi hàng liền 😅",
            "Anh em làm tủ điện chắc hiểu cảm giác: thiếu đúng linh kiện là đứng việc ngay.",
            "Nhìn quạt thì đơn giản, nhưng khi lắp vào tủ điện phải đúng mã - đúng nguồn - đúng kích thước.",
        ]
        bodies = [
            f"{clean_product} dùng cho nhu cầu thông gió/làm mát tủ điện, hỗ trợ giảm nhiệt cho linh kiện bên trong.\n\nĐiểm cần check trước khi đặt:\n- Model: EA12038S\n- Nguồn: 220/240VAC\n- Kích thước: 120x120x38mm\n- Vị trí bắt vít và hướng lắp\n\nKhách chỉ cần gửi ảnh tem quạt cũ hoặc ảnh mặt sau, shop mình đối chiếu giúp trước khi chốt để tránh mua nhầm.",
            f"{clean_product} hợp với thợ điện, kỹ thuật bảo trì hoặc bên thi công cần thay nhanh đúng mã.\n\nẢnh sản phẩm có tem EA12038S, thân vuông màu đen, lưới bảo vệ phía sau và 4 lỗ bắt vít rõ ràng. Mấy chi tiết này giúp đối chiếu nhanh với quạt cũ đang dùng trong tủ.\n\nKhông chắc đúng mẫu chưa? Cứ gửi tem thông số, shop kiểm tra giúp rồi hãy đặt.",
            f"Với quạt tủ điện, đừng chỉ nhìn hình rồi mua vội.\n\nMình sẽ ưu tiên kiểm tra 3 thứ trước:\n- Có đúng mã EA12038S không\n- Nguồn có khớp 220/240VAC không\n- Kích thước 120x120x38mm có vừa vị trí lắp không\n\nChọn đúng ngay từ đầu sẽ đỡ mất thời gian tháo ra đổi lại, nhất là khi tủ đang cần chạy ổn định.",
        ]
    elif is_technical:
        hooks = [
            "Khi tủ điện chạy lâu, phần làm mát không nên chọn đại cho có.",
            f"{clean_product} hợp với những đơn hàng cần đúng mã, đúng kích thước và lắp vào là dùng được.",
            "Có những linh kiện nhỏ nhưng ảnh hưởng trực tiếp đến độ ổn định của cả tủ điện.",
            "Nếu anh em đang tìm quạt thay thế cho tủ điện, điểm cần nhìn đầu tiên không phải là ảnh đẹp.",
            "Một con quạt tủ điện tốt là loại giúp tủ thoát nhiệt đều, chạy ổn và dễ kiểm tra khi bảo trì.",
        ]
        bodies = [
            f"Với {clean_product}, khách nên kiểm tra rõ mã EA12038S, điện áp 220/240VAC, kích thước 120x120x38mm và vị trí lắp trước khi chốt.\n\nMấy thông số này nhìn nhỏ nhưng rất quan trọng, nhất là khi cần thay quạt cũ trong tủ điện đang vận hành. Đi đúng mã ngay từ đầu sẽ giảm rủi ro mua nhầm quạt, sai nguồn điện hoặc mất thời gian đổi hàng.\n\nDòng này phù hợp cho nhu cầu thông gió/làm mát tủ điện, hỗ trợ giảm nhiệt cho linh kiện bên trong. Nếu chưa chắc quạt cũ có cùng thông số không, khách chỉ cần gửi ảnh tem hoặc ảnh mặt sau để shop đối chiếu.",
            f"{clean_product} có điểm dễ nhận là thân vuông màu đen, lưới bảo vệ phía sau và tem thông số ở giữa.\n\nKhi tư vấn, mình sẽ không chỉ nhìn ảnh rồi chốt vội. Cần hỏi thêm khách đang thay quạt cũ hay lắp mới, tủ đang dùng nguồn nào, vị trí bắt vít có khớp kích thước 120x120x38mm không.\n\nCách làm này giúp khách chọn đúng linh kiện ngay từ đầu, đặc biệt với thợ điện, kỹ thuật bảo trì hoặc đơn vị thi công cần xử lý nhanh cho tủ điện.",
            f"Lý do mua {clean_product} thường rất thực tế: tủ điện nóng, quạt cũ yếu, quạt hỏng hoặc cần thay nhanh đúng mã EA12038S.\n\nTrong trường hợp này, caption không nên viết kiểu khen chung chung. Điều khách cần là biết quạt dùng nguồn 220/240VAC, kích thước 120x120x38mm và có phù hợp với vị trí lắp hiện tại không.\n\nNếu khách còn giữ tem quạt cũ, chỉ cần chụp gửi shop. Mình sẽ đối chiếu model, điện áp và kích thước trước khi báo hàng để tránh mua sai.",
        ]
    else:
        hooks = [
            f"Nếu đang cân nhắc {clean_product}, mình sẽ bắt đầu từ nhu cầu thật trước.",
            f"{clean_product} không nên chỉ viết bằng vài câu khen chung chung.",
            f"Điểm đáng nói của {clean_product} là nó phải gắn với đúng người dùng và đúng tình huống.",
        ]
        bodies = [
            f"Với nhóm {clean_audience}, bài đăng nên nói rõ sản phẩm giải quyết việc gì, phù hợp khi nào và cần lưu ý điều gì trước khi mua. Cách viết này giúp khách hiểu nhanh thay vì chỉ thấy một caption đẹp.",
            "Nội dung nên lấy thông tin từ ảnh, từ mô tả sản phẩm và từ insight đã search để tạo thành một lời tư vấn ngắn. Như vậy bài đăng có lý do để tồn tại, không chỉ là chữ trang trí cạnh ảnh.",
            "Nên ưu tiên thông tin cụ thể: điểm nổi bật, cách dùng, đối tượng phù hợp và điều shop có thể hỗ trợ sau khi khách inbox.",
        ]

    hook = hooks[(day_number - 1) % len(hooks)]
    body = bodies[(day_number - 1) % len(bodies)]
    return f"{hook}\n\n{body}"


def fallback_role_for_machine(machine):
    normalized = remove_vietnamese_accents(machine).lower()
    if any(word in normalized for word in ["gioi thieu", "nang luc cong ty", "hau truong", "kho", "dong hang"]):
        return "Xây niềm tin thương hiệu"
    if any(word in normalized for word in ["tang follow", "luu bai", "q&a", "hoi dap", "nguoi moi"]):
        return "Tăng follow/Save"
    if any(word in normalized for word in ["ban do san pham", "combo", "giai phap he thong"]):
        return "Định vị giải pháp"
    if "su co" in normalized or "an toan" in normalized:
        return "Tư vấn/Cảnh báo"
    if "review" in normalized:
        return "Tư vấn sản phẩm"
    if "bang chon" in normalized or "checklist" in normalized:
        return "Tư vấn chọn đúng"
    if "myth" in normalized or "hieu lam" in normalized:
        return "Đính chính hiểu lầm"
    if "keo inbox" in normalized:
        return "Chốt inbox"
    return "Tư vấn"


def fallback_hook_for_machine(machine):
    normalized = remove_vietnamese_accents(machine).lower()
    if "gioi thieu" in normalized or "nang luc cong ty" in normalized:
        return "Lý do nên theo dõi công ty"
    if any(word in normalized for word in ["hau truong", "kho", "dong hang"]):
        return "Quy trình kiểm hàng tạo niềm tin"
    if any(word in normalized for word in ["tang follow", "luu bai"]):
        return "Checklist đáng lưu cho người làm tủ điện"
    if any(word in normalized for word in ["q&a", "hoi dap", "nguoi moi"]):
        return "Câu hỏi phổ biến được trả lời ngắn gọn"
    if any(word in normalized for word in ["ban do san pham", "combo", "giai phap he thong"]):
        return "Từ nhu cầu hệ thống đến nhóm thiết bị cần kiểm tra"
    if "su co" in normalized or "an toan" in normalized:
        return "Rủi ro khi chọn sai thiết bị bảo vệ"
    if "review" in normalized:
        return "Review theo tình huống sử dụng"
    if "bang chon" in normalized:
        return "Bảng chọn nhanh theo thông số"
    if "myth" in normalized or "hieu lam" in normalized:
        return "Hiểu lầm thường gặp khi chọn thiết bị"
    if "keo inbox" in normalized:
        return "Gửi thông số để đối chiếu"
    return "Chọn đúng nhu cầu"


def fallback_kpi_for_machine(machine):
    normalized = remove_vietnamese_accents(machine).lower()
    if any(word in normalized for word in ["gioi thieu", "nang luc cong ty", "hau truong", "tang follow", "q&a", "hoi dap", "luu bai"]):
        return "Follow/Save"
    if any(word in normalized for word in ["ban do san pham", "combo", "giai phap he thong"]):
        return "Save/Inbox"
    if "su co" in normalized or "myth" in normalized or "hieu lam" in normalized:
        return "Share/Comment"
    if "keo inbox" in normalized or "bang chon" in normalized:
        return "Inbox"
    if "review" in normalized:
        return "Inbox/Save"
    return "Inbox"


def normalize_posts(raw_data, product="", audience="", expected_count=None, content_brief=""):
    if isinstance(raw_data, dict):
        items = raw_data.get("posts") or raw_data.get("captions") or []
    elif isinstance(raw_data, list):
        items = raw_data
    else:
        items = []

    normalized = []
    seen_ids = set()
    for index, item in enumerate(items, start=1):
        if isinstance(item, str):
            item = {"caption": item}
        post = normalize_post(item, fallback_day=f"Ngày {index}")
        if post["id"] in seen_ids:
            post["id"] = make_id("post")
        seen_ids.add(post["id"])
        if not post.get("content_machine"):
            post["content_machine"] = fallback_machine_for_index(content_brief, index, post.get("topic", ""))
        if not post["caption"] or len(post["caption"]) < 40 or caption_conflicts_product(post["caption"], product, content_brief):
            post["caption"] = polish_caption_text(
                fallback_caption(product, audience, index, post.get("topic", ""), content_brief, post.get("content_machine", ""))
            )
            post["source"] = "fallback"
        if post.get("source") == "fallback":
            post["content_role"] = post.get("content_role") or fallback_role_for_machine(post.get("content_machine", ""))
            post["hook_angle"] = post.get("hook_angle") or fallback_hook_for_machine(post.get("content_machine", ""))
            post["kpi_goal"] = post.get("kpi_goal") or fallback_kpi_for_machine(post.get("content_machine", ""))
        if post.get("source") == "fallback" and not post.get("cta"):
            post["cta"] = product_specific_cta(product, content_brief)
        if caption_conflicts_product(post.get("cta", ""), product, content_brief):
            post["cta"] = product_specific_cta(product, content_brief)
        if caption_conflicts_product(post.get("image_guidance", ""), product, content_brief):
            post["image_guidance"] = image_recommendation_for_machine(post.get("content_machine", ""), product)
        polished_caption = polish_caption_text(post.get("caption", ""))
        post["caption"] = append_company_footer(
            apply_machine_caption_icons(polished_caption, post.get("content_machine", ""))
        )
        post["content_brief"] = content_brief
        post = ensure_image_guidance(post, product)
        post = polish_post_hashtags(post, product, audience)
        if product_profile(product, content_brief)["key"] == "power_quality_meter":
            disallowed_meter_tags = {"#CD2", "#BienDongCT"}
            post["hashtags"] = [
                tag for tag in post.get("hashtags", [])
                if tag not in disallowed_meter_tags
            ]
            for tag in fallback_hashtags(product, audience):
                if tag not in post["hashtags"]:
                    post["hashtags"].append(tag)
            post["hashtags"] = post["hashtags"][:6]
        for tag in DEFAULT_COMPANY_HASHTAGS:
            if tag not in post["hashtags"]:
                post["hashtags"].append(tag)
        post["quality_notes"] = post_quality_notes(post, product, content_brief)
        normalized.append(post)

    if expected_count:
        while len(normalized) < expected_count:
            day_number = len(normalized) + 1
            topic = f"Gợi ý ngày {day_number}"
            inferred_machine = fallback_machine_for_index(content_brief, day_number, topic)
            normalized.append(
                {
                    "id": make_id("post"),
                    "day": f"Ngày {day_number}",
                    "platforms": ["Facebook", "Instagram"],
                    "topic": topic,
                    "content_machine": inferred_machine,
                    "content_role": fallback_role_for_machine(inferred_machine),
                    "hook_angle": fallback_hook_for_machine(inferred_machine),
                    "kpi_goal": fallback_kpi_for_machine(inferred_machine),
                    "caption": append_company_footer(
                        apply_machine_caption_icons(
                            polish_caption_text(fallback_caption(product, audience, day_number, topic, content_brief, inferred_machine)),
                            inferred_machine,
                        )
                    ),
                    "hashtags": [*fallback_hashtags(product, audience), *[tag for tag in DEFAULT_COMPANY_HASHTAGS if tag not in fallback_hashtags(product, audience)]],
                    "cta": product_specific_cta(product, content_brief),
                    "image_guidance": image_recommendation_for_machine(inferred_machine or topic, product),
                    "status": "draft",
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                    "image_files": [],
                    "source": "fallback",
                    "content_brief": content_brief,
                    "quality_notes": [],
                }
            )

        normalized = normalized[:expected_count]

    for post in normalized:
        post["quality_notes"] = post_quality_notes(post, product, content_brief)

    return normalized


def image_context_from_records(image_records):
    if not image_records:
        return "Chưa có ảnh lưu từ máy."

    return "\n".join(f"- {item['label']}: {item['name']} ({item['path']})" for item in image_records)


def match_images_for_post(post, image_records):
    """Return all uploaded images for every post."""
    return list(image_records) if image_records else []


def attach_image_files(post, image_records):
    post = dict(post)
    post["image_files"] = [item["path"] for item in image_records]
    return post


def approve_post(post, image_records):
    posts = load_saved_posts()
    approved = attach_image_files(post, image_records)
    approved["id"] = make_id("approved")
    approved["status"] = "approved"
    approved["created_at"] = datetime.now().isoformat(timespec="seconds")
    posts.append(approved)
    save_saved_posts(posts)
    return approved


def count_by(posts, key):
    counts = {}
    for post in posts:
        value = post.get(key) or "Chưa phân loại"
        counts[value] = counts.get(value, 0) + 1
    return counts


def format_counts(counts):
    return ", ".join(f"{key}: {value}" for key, value in counts.items() if key) or "chưa có"


def plan_overview_rows(posts):
    return [
        {
            "Ngày": post.get("day", ""),
            "Máy nội dung": post.get("content_machine", ""),
            "Vai trò": post.get("content_role", ""),
            "Hook": post.get("hook_angle", ""),
            "KPI": post.get("kpi_goal", ""),
            "Chủ đề": post.get("topic", ""),
        }
        for post in posts
    ]


def display_plan_overview(posts):
    rows = plan_overview_rows(posts)
    if not rows:
        return

    st.markdown("**Bảng kế hoạch nội dung**")
    st.caption(
        "Phân bổ: "
        f"máy nội dung ({format_counts(count_by(posts, 'content_machine'))}); "
        f"vai trò ({format_counts(count_by(posts, 'content_role'))}); "
        f"KPI ({format_counts(count_by(posts, 'kpi_goal'))})."
    )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def posts_to_csv_bytes(posts):
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "day",
            "platforms",
            "topic",
            "caption",
            "hashtags",
            "cta",
            "image_guidance",
            "content_role",
            "content_machine",
            "hook_angle",
            "kpi_goal",
            "reels_script",
            "metrics",
            "image_files",
            "status",
            "created_at",
        ],
    )
    writer.writeheader()
    for post in posts:
        writer.writerow(
            {
                "day": post.get("day", ""),
                "platforms": ", ".join(post.get("platforms", [])),
                "topic": post.get("topic", ""),
                "caption": post.get("caption", ""),
                "hashtags": " ".join(post.get("hashtags", [])),
                "cta": post.get("cta", ""),
                "image_guidance": post.get("image_guidance", ""),
                "content_role": post.get("content_role", ""),
                "content_machine": post.get("content_machine", ""),
                "hook_angle": post.get("hook_angle", ""),
                "kpi_goal": post.get("kpi_goal", ""),
                "reels_script": post.get("reels_script", ""),
                "metrics": json.dumps(post.get("metrics", {}), ensure_ascii=False),
                "image_files": ", ".join(post.get("image_files", [])),
                "status": post.get("status", ""),
                "created_at": post.get("created_at", ""),
            }
        )
    return buffer.getvalue().encode("utf-8-sig")


def posts_to_markdown(posts):
    lines = ["# Lịch nội dung đã duyệt", ""]
    for post in posts:
        lines.extend(
            [
                f"## {post.get('day', '')}: {post.get('topic', '')}",
                f"- Nền tảng: {', '.join(post.get('platforms', []))}",
                f"- Caption: {post.get('caption', '')}",
                f"- Hashtag: {' '.join(post.get('hashtags', []))}",
                f"- CTA: {post.get('cta', '')}",
                f"- Ảnh dùng: {post.get('image_guidance', '')}",
                f"- Vai trò: {post.get('content_role', '')}",
                f"- Máy tạo nội dung: {post.get('content_machine', '')}",
                f"- Góc hook: {post.get('hook_angle', '')}",
                f"- KPI mục tiêu: {post.get('kpi_goal', '')}",
                f"- Script Reels/video: {post.get('reels_script', '')}",
                f"- Hiệu quả: {json.dumps(post.get('metrics', {}), ensure_ascii=False)}",
                "",
            ]
        )
    return "\n".join(lines).encode("utf-8")


def _resolve_display_images(post, image_records):
    """Resolve images to display for a post — from matched records or saved paths."""
    matched = match_images_for_post(post, image_records or [])
    paths = []
    for record in matched:
        if Path(record["path"]).exists():
            paths.append(record)
    if not paths and post.get("image_files"):
        for img_path in post["image_files"]:
            p = Path(img_path)
            if p.exists():
                paths.append({"path": str(p), "label": p.stem[:20], "name": p.name})
    return paths, matched


def _post_profile_name(post, brand_name_fallback=""):
    """Get display name for the FB-style profile header."""
    return brand_name_fallback or "Shop của bạn"


def display_post_card(post, key_prefix, image_records=None, allow_approve=False, brand_name="", instance_key=None):
    card_id = f"{key_prefix}-{instance_key or post['id']}"
    edit_key = f"editing-{card_id}"
    if edit_key not in st.session_state:
        st.session_state[edit_key] = False

    display_paths, matched_images = _resolve_display_images(post, image_records)
    platforms = post.get("platforms", [])
    profile_name = _post_profile_name(post, brand_name)
    avatar_letter = profile_name[0].upper() if profile_name else "S"
    avatar_cls = "fb-avatar ig" if "Instagram" in platforms and "Facebook" not in platforms else "fb-avatar"

    # Platform badges HTML
    badges_html = " ".join(
        f"<span class='platform-badge {'badge-fb' if p == 'Facebook' else 'badge-ig'}'>{p}</span>" for p in platforms
    )

    topic = post.get("topic", "")
    day_label = post.get("day", "")

    with st.container(border=True):
        # --- FB-style profile header ---
        st.markdown(f"""
        <div class='fb-profile-header'>
            <div class='{avatar_cls}'>{avatar_letter}</div>
            <div class='fb-profile-info'>
                <div class='fb-profile-name'>{profile_name}</div>
                <div class='fb-profile-meta'>
                    {day_label} {badges_html}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if topic:
            st.markdown(f"<span class='topic-tag'>{topic}</span>", unsafe_allow_html=True)

        strategy_bits = []
        if post.get("content_role"):
            strategy_bits.append(f"Vai trò: {post['content_role']}")
        if post.get("content_machine"):
            strategy_bits.append(f"Máy: {post['content_machine']}")
        if post.get("hook_angle"):
            strategy_bits.append(f"Hook: {post['hook_angle']}")
        if post.get("kpi_goal"):
            strategy_bits.append(f"KPI: {post['kpi_goal']}")
        if strategy_bits:
            st.caption(" | ".join(strategy_bits))

        quality_notes = post.get("quality_notes", [])
        if quality_notes:
            st.warning("Cần rà lại: " + " ".join(f"- {note}" for note in quality_notes))

        # --- Editing mode ---
        if st.session_state[edit_key]:
            new_caption = st.text_area(
                "Caption", post.get("caption", ""),
                key=f"edit-caption-{card_id}", height=200
            )
            new_hashtags = st.text_input(
                "Hashtag", " ".join(post.get("hashtags", [])),
                key=f"edit-hashtags-{card_id}"
            )
            new_cta = st.text_input(
                "CTA", post.get("cta", ""),
                key=f"edit-cta-{card_id}"
            )
            new_content_role = st.text_input(
                "Vai trò nội dung",
                post.get("content_role", ""),
                key=f"edit-role-{card_id}",
            )
            new_content_machine = st.text_input(
                "Máy tạo nội dung",
                post.get("content_machine", ""),
                key=f"edit-machine-{card_id}",
            )
            new_hook_angle = st.text_input(
                "Góc hook",
                post.get("hook_angle", ""),
                key=f"edit-hook-{card_id}",
            )
            new_kpi_goal = st.text_input(
                "KPI mục tiêu",
                post.get("kpi_goal", ""),
                key=f"edit-kpi-{card_id}",
            )
            new_reels_script = st.text_area(
                "Script Reels/video ngắn",
                post.get("reels_script", ""),
                key=f"edit-reels-{card_id}",
                height=110,
            )
            new_image_guidance = st.text_area(
                "Gợi ý ảnh nên dùng",
                post.get("image_guidance", ""),
                key=f"edit-image-guidance-{card_id}",
                height=110,
            )

            if image_records:
                st.markdown("**Chọn ảnh cho bài này:**")
                selected_images = []
                sel_cols = st.columns(min(len(image_records), 4))
                for idx, record in enumerate(image_records):
                    with sel_cols[idx % len(sel_cols)]:
                        is_matched = record in matched_images
                        if st.checkbox(
                            record["label"],
                            value=is_matched,
                            key=f"sel-img-{card_id}-{idx}"
                        ):
                            selected_images.append(record)
                        st.image(record["path"], use_container_width=True)

            btn_save, btn_cancel = st.columns(2)
            with btn_save:
                if st.button("Lưu chỉnh sửa", key=f"save-edit-{card_id}", use_container_width=True):
                    post["caption"] = polish_caption_text(new_caption)
                    post["hashtags"] = normalize_hashtags(new_hashtags)
                    post["cta"] = clean_model_text(new_cta)
                    post["content_role"] = clean_model_text(new_content_role)
                    post["content_machine"] = clean_model_text(new_content_machine)
                    post["hook_angle"] = clean_model_text(new_hook_angle)
                    post["kpi_goal"] = clean_model_text(new_kpi_goal)
                    post["reels_script"] = clean_model_text(new_reels_script)
                    post["image_guidance"] = clean_model_text(new_image_guidance)
                    if image_records:
                        post["image_files"] = [r["path"] for r in selected_images]
                        guidance_parts = [r["label"] for r in selected_images]
                        if guidance_parts:
                            post["image_guidance"] = "Dùng " + ", ".join(guidance_parts)
                    st.session_state[edit_key] = False
                    st.rerun()
            with btn_cancel:
                if st.button("Hủy", key=f"cancel-edit-{card_id}", use_container_width=True):
                    st.session_state[edit_key] = False
                    st.rerun()
        else:
            # --- Display mode: Caption FIRST (like FB), then image ---
            caption_text = post.get("caption", "")
            st.markdown(f"<div class='fb-caption'>{caption_text}</div>", unsafe_allow_html=True)

            hashtag_str = " ".join(post.get("hashtags", []))
            if hashtag_str:
                st.markdown(f"<div class='hashtag-line'>{hashtag_str}</div>", unsafe_allow_html=True)

            if post.get("cta"):
                st.markdown(f"<div class='cta-box'>{post['cta']}</div>", unsafe_allow_html=True)

            if post.get("reels_script"):
                with st.expander("Script Reels/video ngắn", expanded=False):
                    st.write(post["reels_script"])

            if post.get("image_guidance"):
                with st.expander("Gợi ý ảnh nên dùng", expanded=True):
                    st.write(post["image_guidance"])

            # --- Image BELOW caption (FB style) ---
            if display_paths:
                num_imgs = len(display_paths)
                if num_imgs == 1:
                    img_col, _ = st.columns([2, 3])
                    with img_col:
                        st.image(display_paths[0]["path"], use_container_width=True)
                elif num_imgs == 2:
                    img_cols = st.columns(2)
                    for idx, record in enumerate(display_paths[:2]):
                        with img_cols[idx]:
                            st.image(record["path"], use_container_width=True)
                else:
                    img_cols = st.columns(min(num_imgs, 4))
                    for idx, record in enumerate(display_paths[:8]):
                        with img_cols[idx % len(img_cols)]:
                            st.image(record["path"], use_container_width=True)

            # --- Action buttons ---
            full_text = caption_text
            if hashtag_str:
                full_text += "\n\n" + hashtag_str

            action_cols = st.columns(3 if allow_approve else 2)
            col_idx = 0

            with action_cols[col_idx]:
                if st.button("Chỉnh sửa", key=f"edit-{card_id}", use_container_width=True):
                    st.session_state[edit_key] = True
                    st.rerun()
            col_idx += 1

            with action_cols[col_idx]:
                st.download_button(
                    "Copy caption",
                    data=full_text,
                    file_name=f"caption-{post['id']}.txt",
                    mime="text/plain",
                    key=f"copy-{card_id}",
                    use_container_width=True,
                )
            col_idx += 1

            if allow_approve and col_idx < len(action_cols):
                with action_cols[col_idx]:
                    if st.button("Duyệt và lưu", key=f"approve-{card_id}", use_container_width=True, type="primary"):
                        selected_records = matched_images if matched_images else (image_records or [])
                        approve_post(post, selected_records)
                        st.success("Đã lưu vào lịch đã duyệt.")
                        st.rerun()


def generate_week_plan(
    product,
    brand_name,
    audience,
    platforms,
    content_brief,
    research_context,
    uploaded_image_context,
    image_records,
    planning_model,
):
    example_hashtags = json.dumps(fallback_hashtags(product, audience)[:3], ensure_ascii=False)
    profile = product_profile(product, content_brief)
    avoid_terms = ", ".join(profile.get("avoid_terms", [])) or "không có"
    prompt = f"""
Bạn là một người bán hàng online thực thụ trên Facebook/Instagram — không phải copywriter, không phải AI.
Bạn viết bài đăng bằng cảm xúc thật, bằng trải nghiệm với sản phẩm, bằng sự thấu hiểu khách hàng.

Thông tin:
- Sản phẩm/dịch vụ: {product}
- Tên shop/thương hiệu: {brand_name or "shop mình"}
- Khách hàng mục tiêu: {audience}
- Nền tảng: {", ".join(platforms)}
- Thông tin công ty mặc định phải dùng nếu cần footer/liên hệ:
{DEFAULT_COMPANY_FOOTER}
- Nhóm sản phẩm đã nhận diện: {profile["label"]}
- Thông số/chức năng đã xác minh: {profile.get("verified_specs", "Chỉ dùng thông tin trong brief, research và ảnh; không tự suy đoán.")}
- CTA đúng nhóm sản phẩm: {profile["cta"]}
- Thông tin ảnh/tem nên hỏi khách: {profile["image_checks"]}
- Cụm từ phải tránh nếu không đúng sản phẩm này: {avoid_terms}

Brief vận hành nội dung:
{content_brief}

Research công khai:
{research_context}

Ảnh người dùng upload, nếu có:
{uploaded_image_context}

Ảnh đang có trong máy:
{image_context_from_records(image_records)}

Hãy tạo đúng 7 bài đăng cho một tuần. Mỗi bài phải có vai trò riêng trong phễu bán hàng, không được lặp cấu trúc.

Nhiệm vụ khác nhau cho từng content:
{content_mission_instruction()}

Mục tiêu tăng trưởng fanpage công ty:
- Công ty đang cần quảng bá thương hiệu và nhận nhiều lượt theo dõi hơn, nên lịch bài không được chỉ toàn caption bán sản phẩm.
- Hãy cân bằng theo hướng 60% kiến thức kỹ thuật dễ lưu/chia sẻ, 25% bán hàng mềm theo sản phẩm/nhu cầu, 15% thương hiệu/hậu trường/quy trình tư vấn.
- Phải có bài cho người chưa mua nhưng muốn theo dõi page: checklist, Q&A, mini-series, bản đồ sản phẩm theo nhu cầu, hậu trường kiểm hàng.
- Bài thương hiệu vẫn phải cụ thể, không viết chung chung kiểu "uy tín, chất lượng"; hãy nói bằng quy trình, nhóm sản phẩm, cách tư vấn và lý do khách nên gửi ảnh tem/thông số.

Phong cách viết:
{human_writing_instruction()}

Icon cho từng máy nội dung:
{machine_caption_icon_instruction()}

Gợi ý đa dạng bài:
- Bài tư vấn chọn đúng mã/thông số.
- Bài nêu vấn đề khách hay gặp và cách sản phẩm xử lý.
- Bài đọc ảnh sản phẩm: nhìn ảnh biết gì, kiểm tra gì.
- Bài checklist trước khi mua/lắp.
- Bài so sánh sai lầm thường gặp, nhưng không bịa đối thủ.
- Bài social proof/chính sách nếu brief có cung cấp bằng chứng.
- Bài CTA chốt đơn, hỏi khách gửi thông số hoặc ảnh tủ/mặt bằng.
- Bài giới thiệu năng lực công ty: công ty cung cấp nhóm sản phẩm gì, phục vụ ai, tư vấn theo quy trình nào.
- Bài hậu trường kho/đóng hàng/kiểm tem để xây niềm tin.
- Bài Q&A nhanh hoặc checklist đáng lưu để kéo follow từ người làm tủ điện.
- Bài bản đồ sản phẩm theo nhu cầu: làm mát, bù công suất, bảo vệ, đo lường, phụ kiện.
- Ít nhất 2 bài nên có script Reels/video ngắn 15-30 giây vì Reels có cơ hội kéo reach tốt hơn bài ảnh tĩnh.
- Ưu tiên công thức ngành điện công nghiệp: vấn đề -> hậu quả -> giải pháp -> thông số/bằng chứng -> CTA cụ thể.
- Nếu brief có phần "Máy tạo nội dung", mỗi bài phải chọn một máy phù hợp và ghi vào content_machine.
- Nếu brief có nguồn/link/feedback/câu hỏi, hãy biến nó thành bài mới theo dạng cảnh báo, cảm ơn, phân tích, checklist, so sánh, hướng dẫn chọn, case study, Reels script hoặc bài kéo inbox. Không copy nguyên văn nguồn.
- Nếu content_machine là "Sự cố & bài học an toàn", caption phải theo format:
  1. Nguồn/tình huống tham khảo công khai hoặc "Từ các sự cố tủ điện quá nhiệt/chập điện thường gặp".
  2. Tóm tắt trung lập, không giật tít quá đà.
  3. Bài học an toàn cho doanh nghiệp/xưởng.
  4. Checklist kiểm tra phải bám nhóm sản phẩm đã nhận diện, không dùng checklist của sản phẩm khác.
  5. Gợi ý sản phẩm/giải pháp liên quan chỉ khi phù hợp với brief.
  6. CTA dùng đúng CTA nhóm sản phẩm đã ghi ở trên.

Trả về JSON đúng cấu trúc:
{{
  "posts": [
    {{
      "day": "Ngày 1",
      "platforms": ["Facebook", "Instagram"],
      "topic": "Chủ đề ngắn 3-5 từ",
      "content_role": "Kéo chú ý/Tư vấn/Xây niềm tin/Chốt inbox/Reels kéo reach",
      "content_machine": "Tên máy tạo nội dung đã dùng",
      "hook_angle": "Nỗi đau hoặc góc mở bài chính",
      "kpi_goal": "Like/Share/Comment/Inbox/View",
      "caption": "Bài đăng hoàn chỉnh, bám brief, có thông tin cụ thể, có xuống dòng.",
      "hashtags": {example_hashtags},
      "cta": "CTA tự nhiên, nhẹ nhàng.",
      "image_guidance": "Danh sách ảnh nên dùng/chụp/screenshot cho bài này. Nếu đã có ảnh upload thì chỉ rõ ảnh nào; nếu chưa có ảnh thì đề xuất bộ ảnh phù hợp.",
      "reels_script": "Nếu phù hợp, viết kịch bản video 15-30 giây; nếu không thì để trống."
    }}
  ]
}}

Quy tắc tối quan trọng:
- Viết bằng tiếng Việt. Không dùng tiếng Trung, Nhật, Hàn.
- KHÔNG viết kiểu AI: tránh "chất lượng cao", "sản phẩm tuyệt vời", "không thể bỏ lỡ", "trải nghiệm tuyệt hảo".
- KHÔNG lặp cấu trúc giữa các bài. Mỗi bài phải mở đầu khác nhau.
- Hashtag phải là hashtag thật theo sản phẩm người dùng nhập.
- Không dùng hashtag placeholder kiểu #Hashtag1, #Hashtag2, #TenSanPhamThat, #NhuCauThat.
- Không bịa giá, feedback, thương hiệu hoặc công dụng nếu chưa cung cấp.
- Tuyệt đối không đưa chi tiết của nhóm sản phẩm khác. Ví dụ sản phẩm là tụ bù thì không nói quạt cũ, lưới lọc, vị trí bắt vít quạt; sản phẩm là quạt thì không tự chuyển sang kVAr/cos phi.
- Tên shop/thương hiệu là đơn vị đăng bài/cung cấp. Nếu người dùng nhập Thien Loc Phat Technology Trading thì phải làm nổi rõ tên này; không thay bằng brand sản phẩm như Master Electric.
- Nếu chưa có tên shop, dùng "{DEFAULT_BRAND_LABEL}".
- Không bịa địa chỉ/số điện thoại/website khác. Footer liên hệ mặc định sẽ là thông tin Thiên Lộc Phát/Master Electric ở trên.
- Nếu có ảnh upload, caption phải bám sát ảnh. Nếu chưa có ảnh upload, vẫn viết bài bình thường và image_guidance phải gợi ý ảnh nên chuẩn bị.
- image_guidance phải cụ thể, ví dụ: screenshot bài cảm ơn/feedback đã che thông tin riêng tư + ảnh sản phẩm được nhắc tới + ảnh cận tem/thông số.
- Nếu sản phẩm là hàng kỹ thuật/B2B, ưu tiên giọng tư vấn rõ ràng: đúng mã, đúng thông số, đúng ứng dụng, hỗ trợ kiểm tra trước khi mua.
- Với hàng kỹ thuật/B2B, mở bài nên chạm nỗi đau trước: tủ nóng, sai thông số, mua nhầm, hệ thống chập chờn, cần thay nhanh.
- Mỗi caption phải nhắc ít nhất 1 chi tiết cụ thể từ brief, research hoặc ảnh. Không viết kiểu "món đồ đẹp", "làm mới bản thân", "đi chơi/gặp bạn bè" nếu không liên quan.

Phong cách bài đăng:
{caption_style_instruction()}

Quy tắc hashtag:
{hashtag_quality_instruction()}
"""
    try:
        raw = call_json_model(planning_model, prompt, max_tokens=WEEK_PLAN_MAX_TOKENS, context_tokens=PLANNING_CONTEXT_TOKENS)
        parsed = parse_json_response(raw, {"posts": []})
    except Exception as error:
        st.warning(f"Model viết nội dung phản hồi quá lâu hoặc lỗi: {error}. App sẽ tạo bản dự phòng bám brief để bạn không bị kẹt.")
        parsed = {"posts": []}
    return normalize_posts(parsed, product, audience, expected_count=7, content_brief=content_brief)


def caption_length_instruction(caption_length):
    if caption_length == "Rất dài":
        return """
- Mỗi caption dài 12-16 câu, chia 4-6 đoạn ngắn.
- Có hook, câu chuyện/ngữ cảnh, phân tích lợi ích, gợi ý sử dụng, xử lý băn khoăn và CTA.
- Phù hợp bài Facebook bán hàng hoặc bài giới thiệu sản phẩm kỹ.
""".strip()

    if caption_length == "Ngắn":
        return """
- Mỗi caption dài 4-6 câu, chia 2-3 đoạn ngắn.
- Vẫn phải đủ hook, lợi ích chính, liên hệ ảnh và CTA.
""".strip()

    return """
- Mỗi caption dài 8-12 câu, chia 3-5 đoạn ngắn.
- Đây là một bài đăng hoàn chỉnh, không phải ghi chú hay ý tưởng.
- Cấu trúc bắt buộc:
  1. Hook mở đầu — câu gây tò mò, chạm cảm xúc hoặc hỏi ngược.
  2. Kể chuyện/vẽ cảnh — miêu tả tình huống sử dụng sản phẩm gắn với ảnh upload.
  3. Lợi ích thật — dựa trên insight từ search, nói bằng ngôn ngữ khách hàng.
  4. CTA nhẹ nhàng — mời inbox, comment, hoặc save bài.
- Viết tự nhiên, có chỗ xuống dòng tạo nhịp thở. Không viết thành khối text dày đặc.
""".strip()


def generate_image_captions(
    product,
    brand_name,
    audience,
    platforms,
    content_brief,
    research_context,
    uploaded_image_context,
    image_records,
    planning_model,
    caption_length,
    caption_count=5,
):
    example_hashtags = json.dumps(fallback_hashtags(product, audience)[:3], ensure_ascii=False)
    profile = product_profile(product, content_brief)
    avoid_terms = ", ".join(profile.get("avoid_terms", [])) or "không có"
    prompt = f"""
Bạn là một người bán hàng online có tâm trên Facebook/Instagram.
Bạn yêu sản phẩm mình bán, bạn hiểu khách hàng, và bạn viết bài đăng bằng cảm xúc thật — không phải bằng công thức.

Thông tin:
- Sản phẩm/dịch vụ: {product}
- Tên shop/thương hiệu: {brand_name or "shop mình"}
- Khách hàng mục tiêu: {audience}
- Nền tảng: {", ".join(platforms)}
- Thông tin công ty mặc định phải dùng nếu cần footer/liên hệ:
{DEFAULT_COMPANY_FOOTER}
- Nhóm sản phẩm đã nhận diện: {profile["label"]}
- Thông số/chức năng đã xác minh: {profile.get("verified_specs", "Chỉ dùng thông tin trong brief, research và ảnh; không tự suy đoán.")}
- CTA đúng nhóm sản phẩm: {profile["cta"]}
- Thông tin ảnh/tem nên hỏi khách: {profile["image_checks"]}
- Cụm từ phải tránh nếu không đúng sản phẩm này: {avoid_terms}

Brief vận hành nội dung:
{content_brief}

Research công khai (insight từ thị trường):
{research_context}

Mô tả ảnh đã upload, nếu có (AI đã xem):
{uploaded_image_context}

Ảnh đang có:
{image_context_from_records(image_records)}

Nhiệm vụ: Viết đúng {caption_count} bài đăng hoàn chỉnh, mỗi bài khác nhau về góc nhìn, mục tiêu và lý do khách nên đọc.

Nhiệm vụ khác nhau cho từng content:
{content_mission_instruction()}

Mục tiêu tăng trưởng fanpage công ty:
- Công ty cần quảng bá thương hiệu và tăng lượt theo dõi, nên không viết toàn bài bán hàng trực diện.
- Hãy cân bằng: kiến thức kỹ thuật dễ lưu/chia sẻ, bán hàng mềm theo nhu cầu, và một phần nội dung thương hiệu/hậu trường/quy trình tư vấn.
- Ít nhất một caption nên làm người chưa mua vẫn muốn follow page: Q&A nhanh, checklist, mini-series, bản đồ sản phẩm theo nhu cầu, hoặc hậu trường kiểm hàng.
- Bài thương hiệu phải có chất thật: nhóm sản phẩm đang cung cấp, quy trình kiểm mã/tem, cách tư vấn theo ảnh/thông số, đối tượng khách hàng phục vụ.

Phong cách viết:
{human_writing_instruction()}

Icon cho từng máy nội dung:
{machine_caption_icon_instruction()}

Các bài phải đa dạng, ví dụ:
1. Bài tư vấn chọn đúng mã/thông số
2. Bài nêu vấn đề khách gặp và hậu quả nếu chọn sai
3. Bài đọc ảnh sản phẩm nếu có ảnh; nếu chưa có ảnh thì đề xuất ảnh nên chuẩn bị cho bài
4. Bài checklist trước khi mua/lắp
5. Bài chốt đơn bằng chính sách/bằng chứng có trong brief; nếu chưa có thì không bịa
6. Bài giới thiệu công ty/kho/quy trình tư vấn để xây niềm tin.
7. Bài Q&A/checklist/mini-series để khách có lý do follow page.
8. Có thể tạo biến thể Reels/video ngắn nếu sản phẩm cần kéo reach.

Công thức ưu tiên cho ngành kỹ thuật/B2B:
Vấn đề thật -> hậu quả nếu bỏ qua/chọn sai -> giải pháp -> thông số/bằng chứng -> CTA cụ thể.

Nếu brief có phần "Máy tạo nội dung", mỗi caption phải chọn một máy phù hợp và ghi vào content_machine.
Nếu brief có nguồn/link/feedback/câu hỏi, hãy biến nó thành bài mới theo dạng cảnh báo, cảm ơn, phân tích, checklist, so sánh, hướng dẫn chọn, case study, Reels script hoặc bài kéo inbox. Không copy nguyên văn nguồn.
Nếu content_machine là "Sự cố & bài học an toàn", caption phải theo format:
1. Nguồn/tình huống tham khảo công khai hoặc "Từ các sự cố tủ điện quá nhiệt/chập điện thường gặp".
2. Tóm tắt trung lập, không giật tít quá đà.
3. Bài học an toàn cho doanh nghiệp/xưởng.
4. Checklist kiểm tra phải bám nhóm sản phẩm đã nhận diện, không dùng checklist quạt/tụ/CT nếu không liên quan.
5. Gợi ý sản phẩm/giải pháp liên quan chỉ khi phù hợp với brief.
6. CTA dùng đúng CTA nhóm sản phẩm đã ghi ở trên.

Trả về JSON đúng cấu trúc:
{{
  "captions": [
    {{
      "day": "Bài 1",
      "platforms": ["Facebook", "Instagram"],
      "topic": "Chủ đề ngắn 3-5 từ, hấp dẫn",
      "content_role": "Kéo chú ý/Tư vấn/Xây niềm tin/Chốt inbox/Reels kéo reach",
      "content_machine": "Tên máy tạo nội dung đã dùng",
      "hook_angle": "Nỗi đau hoặc góc mở bài chính",
      "kpi_goal": "Like/Share/Comment/Inbox/View",
      "caption": "Bài đăng hoàn chỉnh, bám brief, có thông tin cụ thể, có xuống dòng, dựa trên ảnh và insight.",
      "hashtags": {example_hashtags},
      "cta": "CTA tự nhiên, nhẹ nhàng.",
      "image_guidance": "Danh sách ảnh nên dùng/chụp/screenshot cho bài này. Nếu đã có ảnh upload thì chỉ rõ ảnh nào; nếu chưa có ảnh thì đề xuất bộ ảnh phù hợp.",
      "reels_script": "Nếu bài này hợp làm video ngắn, viết script 15-30 giây; nếu không thì để trống."
    }}
  ]
}}

Quy tắc tối quan trọng:
- Viết bằng tiếng Việt tự nhiên. Không dùng tiếng Trung, Nhật, Hàn.
- KHÔNG viết kiểu AI/máy. Cấm dùng: "chất lượng cao", "sản phẩm tuyệt vời", "không thể bỏ lỡ", "trải nghiệm tuyệt hảo", "đẳng cấp vượt trội".
- KHÔNG lặp cấu trúc câu mở đầu giữa 5 bài. Mỗi bài mở đầu hoàn toàn khác.
- Nếu có ảnh upload, caption phải khớp với ảnh: nhắc đến thứ nhìn thấy trong ảnh. Nếu chưa có ảnh upload, vẫn viết bài bình thường và image_guidance phải gợi ý ảnh nên chuẩn bị.
- image_guidance phải cụ thể theo content_machine. Ví dụ bài Cảm ơn/ghi nhận: screenshot bài khách đã che thông tin riêng tư + ảnh sản phẩm được nhắc tới + ảnh cảm ơn đơn giản. Bài Checklist: ảnh checklist 3-5 dòng + ảnh cận tem/thông số + ảnh sản phẩm.
- Dùng insight từ research để bài có chiều sâu, nhưng không copy nguyên văn.
- Hashtag phải thật, sát sản phẩm — không dùng hashtag mẫu.
- Không dùng hashtag placeholder kiểu #Hashtag1, #Hashtag2, #TenSanPhamThat, #NhuCauThat.
- Không bịa giá, feedback, thương hiệu nếu chưa cung cấp.
- Tên shop/thương hiệu là đơn vị đăng bài/cung cấp. Nếu người dùng nhập Thien Loc Phat Technology Trading thì phải làm nổi rõ tên này; không thay bằng brand sản phẩm như Master Electric.
- Nếu chưa có tên shop, dùng "{DEFAULT_BRAND_LABEL}".
- Không bịa địa chỉ/số điện thoại/website khác. Footer liên hệ mặc định sẽ là thông tin Thiên Lộc Phát/Master Electric ở trên.
- Nếu sản phẩm là hàng kỹ thuật/B2B, viết như người tư vấn bán hàng hiểu sản phẩm: rõ ứng dụng, thông số, lưu ý chọn mua, không lifestyle hóa.
- Với hàng kỹ thuật/B2B, đừng mở bài bằng tên sản phẩm quá khô nếu có thể mở bằng nỗi đau: tủ nóng, mua nhầm thông số, cần thay nhanh, hệ thống chập chờn.
- Mỗi caption phải nhắc ít nhất 1 chi tiết cụ thể từ brief, research, nguồn vào hoặc ảnh nếu có. Không viết kiểu "món đồ đẹp", "làm mới bản thân", "đi chơi/gặp bạn bè" nếu không liên quan.
- Tuyệt đối không đưa chi tiết của nhóm sản phẩm khác. Ví dụ sản phẩm là tụ bù thì không nói quạt cũ, lưới lọc, vị trí bắt vít quạt; sản phẩm là quạt thì không tự chuyển sang kVAr/cos phi.

Phong cách bài đăng:
{caption_style_instruction()}

Quy tắc hashtag:
{hashtag_quality_instruction()}

Yêu cầu độ dài:
{caption_length_instruction(caption_length)}
"""
    max_tokens = CAPTION_MAX_TOKENS if caption_count >= 5 else 2200
    try:
        raw = call_json_model(planning_model, prompt, max_tokens=max_tokens, context_tokens=PLANNING_CONTEXT_TOKENS)
        parsed = parse_json_response(raw, {"captions": []})
    except Exception as error:
        st.warning(f"Model viết nội dung phản hồi quá lâu hoặc lỗi: {error}. App sẽ tạo bản dự phòng bám brief để bạn không bị kẹt.")
        parsed = {"captions": []}
    return normalize_posts(parsed, product, audience, expected_count=caption_count, content_brief=content_brief)


def ensure_session_defaults():
    st.session_state.setdefault("generated_plan", [])
    st.session_state.setdefault("caption_variants", [])
    st.session_state.setdefault("last_image_analysis", "")
    st.session_state.setdefault("ai_brief_seed", {})
    st.session_state.setdefault("machine_chat_ideas", [])
    st.session_state.setdefault("machine_chat_product", "")
    if st.session_state.get("machine_idea_version") != MACHINE_IDEA_VERSION:
        st.session_state["machine_chat_ideas"] = []
        st.session_state["machine_chat_product"] = ""
        st.session_state["machine_idea_version"] = MACHINE_IDEA_VERSION
    if st.session_state.get("content_generation_version") != CONTENT_GENERATION_VERSION:
        st.session_state["caption_variants"] = []
        st.session_state["generated_plan"] = []
        st.session_state["content_generation_version"] = CONTENT_GENERATION_VERSION


ensure_session_defaults()

st.title("Social AI Planner")
st.caption("Local AI: tự search nội dung công khai, biến nguồn vào thành bài đăng, gợi ý ảnh nên dùng, lập kế hoạch và lưu lịch đã duyệt.")

with st.expander("App này khác gì nhập ảnh vào ChatGPT?", expanded=False):
    st.markdown(
        """
- **Brief dùng lại được:** lưu thông số, nỗi đau khách hàng, bằng chứng, chính sách, nguồn vào và giọng thương hiệu cho cả bộ nội dung.
- **Research trước khi viết:** tự tạo từ khóa, lấy insight công khai và đưa vào prompt.
- **Playbook ngành:** áp dụng công thức B2B: vấn đề -> hậu quả -> giải pháp -> thông số -> CTA.
- **Không chỉ caption:** tạo vai trò bài, hook, KPI mục tiêu, script Reels/video ngắn và gợi ý bộ ảnh nên dùng.
- **Kiểm tra chất lượng:** cảnh báo khi caption quá chung, thiếu mã/tên sản phẩm hoặc không bám chất kỹ thuật/B2B.
- **Quy trình duyệt & đo hiệu quả:** preview, chỉnh sửa, duyệt, lưu lịch, export và nhập like/comment/share/inbox/view sau khi đăng.
"""
    )

create_tab, saved_tab, strategy_tab, guide_tab = st.tabs(["Tạo nội dung", "Lịch đã duyệt", "Chiến lược", "Cách dùng"])

with create_tab:
    st.subheader("Thông tin đầu vào")
    pending_seed = st.session_state.pop("pending_ai_brief_seed", None)
    if pending_seed:
        field_map = {
            "input_audience": "audience",
            "input_product_specs": "product_specs",
            "input_customer_problem": "customer_problem",
            "input_proof_points": "proof_points",
            "input_offer_info": "offer_info",
            "input_differentiator": "differentiator",
            "input_source_material": "source_material",
            "input_content_goal": "content_goal",
            "input_brand_voice": "brand_voice",
            "input_content_mix": "content_mix",
            "input_format_focus": "format_focus",
            "input_selected_machines": "selected_machines",
        }
        for state_key, seed_key in field_map.items():
            value = pending_seed.get(seed_key)
            if value:
                st.session_state[state_key] = value
        st.success("Đã điền brief gợi ý. Bạn có thể rà lại rồi bấm tạo nội dung.")

    product = st.text_area("Bạn bán gì? Mô tả sản phẩm/dịch vụ của bạn", key="input_product")
    brand_name = st.text_input("Tên shop/thương hiệu (nếu có)", key="input_brand_name")
    audience = st.text_input("Khách hàng mục tiêu", placeholder="Ví dụ: thợ điện, kỹ thuật bảo trì, chủ xưởng, đại lý thiết bị điện", key="input_audience")
    product_specs = st.text_area(
        "Thông số/đặc điểm bắt buộc phải bám",
        placeholder="Ví dụ: mã EA12038S, 220VAC 50/60Hz, 120x120x38mm, lưu lượng gió 138m3/h, dùng làm mát tủ điện",
        key="input_product_specs",
    )
    customer_problem = st.text_area(
        "Nỗi đau/nhu cầu khách hàng",
        placeholder="Ví dụ: tủ điện nóng, quạt cũ yếu, cần thay đúng mã, sợ mua sai kích thước hoặc sai điện áp",
        key="input_customer_problem",
    )
    proof_points = st.text_area(
        "Bằng chứng được phép dùng",
        placeholder="Ví dụ: hàng mới 100%, bảo hành 12 tháng, có sẵn kho, hỗ trợ kỹ thuật. Để trống nếu chưa có.",
        key="input_proof_points",
    )
    offer_info = st.text_input("Ưu đãi/chính sách được phép nhắc", placeholder="Ví dụ: hỗ trợ kiểm tra thông số trước khi đặt", key="input_offer_info")
    differentiator = st.text_input("Điểm khác biệt muốn nhấn mạnh", placeholder="Ví dụ: không viết chung chung, tập trung tư vấn đúng mã và đúng ứng dụng", key="input_differentiator")
    source_material = st.text_area(
        "Nguồn vào muốn biến thành content",
        placeholder="Dán link báo, bài viết Facebook, feedback khách, câu hỏi inbox, ghi chú sale, ảnh công trình... Tool sẽ dùng làm insight và không copy nguyên văn.",
        key="input_source_material",
    )
    autofill_col_1, autofill_col_2 = st.columns([1, 2])
    with autofill_col_1:
        autofill_brief = st.button("AI điền brief còn thiếu", use_container_width=True)
    with autofill_col_2:
        st.caption("Dùng khi chỉ có tên sản phẩm/công ty/thông số. AI sẽ tự đề xuất khách hàng, nỗi đau, máy content và hướng ra mắt sản phẩm.")
    if autofill_brief:
        if not product.strip():
            st.warning("Nhập ít nhất tên sản phẩm/dịch vụ trước khi để AI điền brief.")
        else:
            with st.spinner("AI đang tạo brief nhanh từ dữ liệu tối thiểu..."):
                seed = ai_generate_brief_seed(product, brand_name, product_specs, model=planning_model if "planning_model" in locals() else TEXT_MODEL)
            st.session_state["pending_ai_brief_seed"] = seed
            st.rerun()
    content_goal = st.selectbox(
        "Mục tiêu nội dung",
        [
            "Tư vấn đúng nhu cầu",
            "Chốt inbox",
            "Giải thích kỹ thuật",
            "Xây dựng niềm tin",
            "Tăng nhận diện thương hiệu công ty",
            "Tăng follow fanpage",
            "Kế hoạch nuôi khách 7 ngày",
        ],
        key="input_content_goal",
    )
    brand_voice = st.selectbox(
        "Giọng thương hiệu",
        ["Facebook trending dễ tiếp cận", "Bán hàng gần gũi", "Tư vấn kỹ thuật rõ ràng", "B2B chuyên nghiệp", "Ngắn gọn chốt đơn", "Giải thích dễ hiểu cho người mới"],
        key="input_brand_voice",
    )
    platforms = st.multiselect("Nền tảng", ["Facebook", "Instagram"], default=["Facebook", "Instagram"])
    planning_model = st.selectbox("Model viết nội dung", WRITING_MODELS)
    if planning_model == "qwen3:4b":
        st.caption("qwen3:4b viết sâu hơn nhưng dễ chậm trên máy local. Nếu cần demo nhanh, chọn qwen2.5:3b hoặc bật chế độ demo nhanh.")
    caption_length = st.selectbox("Độ dài caption", ["Bài đăng đầy đủ", "Rất dài", "Ngắn"])
    enable_b2b_playbook = st.checkbox(
        "Bật playbook ngành điện/B2B (vấn đề -> hậu quả -> giải pháp -> thông số -> CTA)",
        value=True,
    )
    strategy_col_1, strategy_col_2, strategy_col_3 = st.columns(3)
    with strategy_col_1:
        weekly_frequency = st.selectbox("Nhịp đăng mục tiêu", ["3-5 bài/tuần", "2-4 bài/tuần", "1 bài/ngày", "Theo chiến dịch sản phẩm"])
    with strategy_col_2:
        content_mix = st.selectbox("Trụ cột ưu tiên", CONTENT_PILLARS, key="input_content_mix")
    with strategy_col_3:
        format_focus = st.selectbox("Định dạng ưu tiên", ["Ảnh + caption", "Reels/video ngắn", "Album sản phẩm", "Kết hợp ảnh và Reels"], key="input_format_focus")
    # Gợi ý bộ máy tạo nội dung theo mục tiêu chiến dịch.
    machine_suggest_goal = st.text_input(
        "Bạn muốn chiến dịch này đạt mục tiêu gì?",
        placeholder="Ví dụ: kéo inbox tư vấn, ra mắt sản phẩm mới, xây uy tín chuyên môn, đăng tin tức ngành điện...",
        key="machine_suggest_goal"
    )

    suggest_text = machine_suggest_goal.strip() or product.strip()
    if suggest_text:
        suggestion = suggest_content_machines_from_chat(
            suggest_text,
            product=product,
            content_goal=content_goal,
            content_mix=content_mix,
        )
        st.markdown(f"""
        <div style="background-color: rgba(24, 119, 242, 0.05); border-left: 3px solid #1877F2; padding: 12px 16px; border-radius: 4px; margin-bottom: 12px;">
            <div style="font-weight: 600; font-size: 0.9rem; color: #1877F2; margin-bottom: 4px;">💡 Bộ máy tạo nội dung nên dùng:</div>
            <div style="font-size: 0.85rem; font-weight: 600; color: #1a2332;">{suggestion['label']}</div>
            <div style="font-size: 0.8rem; color: #555; margin-bottom: 8px;">{suggestion['reason']}</div>
            <div style="font-size: 0.82rem; color: #333;"><b>Chọn các máy này:</b> {', '.join(f'<code>{m}</code>' for m in suggestion['machines'])}</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("👉 Áp dụng bộ máy gợi ý", key="apply_suggested_machines", use_container_width=True):
            st.session_state["input_selected_machines"] = suggestion["machines"]
            st.rerun()

    selected_machines = st.multiselect(
        "Máy tạo nội dung",
        list(CONTENT_MACHINES.keys()),
        default=["Checklist kỹ thuật", "Q&A nhanh cho người mới", "Giới thiệu năng lực công ty", "Hậu trường kho/đóng hàng", "Bài kéo inbox", "Bắt trend chuyên ngành"],
        key="input_selected_machines",
    )
    fast_demo_mode = st.checkbox(
        "Chế độ demo nhanh (ít search hơn, 3 caption, tránh chờ lâu)",
        value=True,
    )
    caption_count = 3 if fast_demo_mode else 5
    strategy_context = build_strategy_context(enable_b2b_playbook, weekly_frequency, content_mix, format_focus)
    machine_context = build_content_machine_context(selected_machines)
    content_brief = build_content_brief(product_specs, customer_problem, proof_points, offer_info, differentiator, brand_voice, content_goal, source_material, brand_name)
    if strategy_context:
        content_brief = f"{content_brief}\n\n{strategy_context}"
    if machine_context:
        content_brief = f"{content_brief}\n\n{machine_context}"

    with st.expander("Brief app sẽ dùng để kiểm soát chất lượng", expanded=False):
        st.write(content_brief)
        st.caption("Đây là lớp khác ChatGPT copy/paste: brief được dùng lại cho search, prompt, fallback và kiểm tra chất lượng từng bài.")

    if enable_b2b_playbook:
        playbook = local_content_playbook(product, audience, weekly_frequency, content_mix, format_focus)
        with st.expander("Playbook gợi ý cho ngành điện công nghiệp", expanded=False):
            st.write(playbook["summary"])
            st.markdown("**Lịch mẫu:**")
            for day_name, pillar, goal in playbook["schedule"]:
                st.write(f"- {day_name}: {pillar} -> {goal}")
            st.markdown("**Hook có thể dùng:**")
            for hook in playbook["hooks"][:3]:
                st.write(f"- {hook}")
            st.markdown("**Ý tưởng Reels:**")
            for reels in playbook["reels"][:2]:
                st.write(f"- {reels}")
            st.markdown("**Máy tạo nội dung đang bật:**")
            for machine in selected_machines:
                st.write(f"- {machine}")

    use_research = st.checkbox("AI tự search nội dung công khai trước khi viết caption/lập kế hoạch", value=True)
    use_ai_queries = st.checkbox("AI đề xuất thêm từ khóa search", value=True)
    search_provider = st.selectbox("Nguồn search", ["DuckDuckGo", "Google Programmable Search API"])
    results_per_query = st.slider("Số kết quả mỗi từ khóa", min_value=1, max_value=5, value=2)
    if fast_demo_mode:
        use_ai_queries = False
        results_per_query = 1
        st.caption("Demo nhanh đang bật: app tắt AI tạo thêm query, lấy 1 kết quả/query và chỉ viết 3 caption.")
    google_api_key = ""
    google_cx = ""

    if search_provider == "Google Programmable Search API":
        st.info("Google Search chính thức cần API key và Search Engine ID (cx). Nếu chưa có, dùng DuckDuckGo trước.")
        google_api_key = st.text_input("Google API key", type="password")
        google_cx = st.text_input("Google Search Engine ID (cx)")

    uploaded_images = st.file_uploader(
        "Upload ảnh từ máy (không bắt buộc)",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        help="Có ảnh thì tool phân tích ảnh thật. Chưa có ảnh thì tool sẽ gợi ý nên chụp/screenshot/thiết kế ảnh gì cho từng bài.",
    )
    image_records = cache_uploaded_images(uploaded_images)

    if uploaded_images:
        st.markdown(f"<div class='upload-count'>{len(uploaded_images)} ảnh đã upload</div>", unsafe_allow_html=True)
        num_cols = min(5, len(uploaded_images))
        preview_columns = st.columns(num_cols)
        for index, uploaded_image in enumerate(uploaded_images):
            with preview_columns[index % num_cols]:
                st.image(uploaded_image, use_container_width=True)

    action_left, action_right = st.columns(2)

    with action_left:
        write_captions = st.button("Tạo nội dung & gợi ý ảnh", use_container_width=True)

    with action_right:
        create_plan = st.button("Tạo kế hoạch tuần", use_container_width=True)

    if write_captions:
        if not product.strip():
            st.warning("Bạn nhập sản phẩm/dịch vụ trước nhé.")
            st.stop()

        search_results = []
        if use_research:
            search_results = run_public_research(
                product,
                brand_name,
                audience,
                platforms,
                results_per_query,
                search_provider,
                use_ai_queries,
                google_api_key=google_api_key,
                google_cx=google_cx,
                expanded=True,
                max_queries=4 if fast_demo_mode else 10,
                selected_machines=selected_machines,
            )

        research_context = build_research_context(search_results)

        uploaded_image_context = "Chưa có ảnh upload. Hãy ưu tiên đề xuất bộ ảnh nên chuẩn bị cho từng bài."
        if uploaded_images:
            with st.spinner("AI đang xem ảnh bạn upload..."):
                uploaded_image_context = analyze_uploaded_images(uploaded_images)
                st.session_state["last_image_analysis"] = uploaded_image_context

        with st.expander("Ngữ cảnh AI sẽ dùng để viết caption", expanded=True):
            st.markdown("**Research công khai**")
            st.write(research_context)
            st.markdown("**Ảnh upload / gợi ý ảnh**")
            st.write(uploaded_image_context)

        with st.spinner("AI đang viết caption..."):
            st.session_state["caption_variants"] = generate_image_captions(
                product,
                brand_name,
                audience,
                platforms,
                content_brief,
                research_context,
                uploaded_image_context,
                image_records,
                planning_model,
                caption_length,
                caption_count,
            )

    if create_plan:
        if not product.strip():
            st.warning("Bạn nhập sản phẩm/dịch vụ trước nhé.")
            st.stop()

        search_results = []
        if use_research:
            search_results = run_public_research(
                product,
                brand_name,
                audience,
                platforms,
                results_per_query,
                search_provider,
                use_ai_queries,
                google_api_key=google_api_key,
                google_cx=google_cx,
                expanded=True,
                max_queries=4 if fast_demo_mode else 10,
                selected_machines=selected_machines,
            )

        research_context = build_research_context(search_results)
        uploaded_image_context = "Chưa có ảnh người dùng upload."

        if uploaded_images:
            with st.spinner("AI đang xem ảnh bạn upload..."):
                uploaded_image_context = analyze_uploaded_images(uploaded_images)
                st.session_state["last_image_analysis"] = uploaded_image_context

            with st.expander("Phân tích ảnh đã upload", expanded=True):
                st.write(uploaded_image_context)

        with st.spinner("AI đang lập kế hoạch tuần..."):
            st.session_state["generated_plan"] = generate_week_plan(
                product,
                brand_name,
                audience,
                platforms,
                content_brief,
                research_context,
                uploaded_image_context,
                image_records,
                planning_model,
            )
            if any(post.get("source") == "fallback" for post in st.session_state["generated_plan"]):
                st.info("Một vài bài bị thiếu hoặc chưa đạt chất lượng, app đã tự bổ sung bài tiếng Việt dự phòng.")

    if st.session_state["last_image_analysis"]:
        with st.expander("Phân tích ảnh gần nhất"):
            st.write(st.session_state["last_image_analysis"])

    if st.session_state["caption_variants"]:
        st.markdown("<div class='section-label'>Caption gợi ý</div>", unsafe_allow_html=True)
        st.subheader("Xem trước bài đăng")
        st.caption("Xem trước bài đăng kèm ảnh. Bấm Chỉnh sửa trước khi duyệt.")
        for index, post in enumerate(st.session_state["caption_variants"], start=1):
            display_post_card(post, "caption", image_records=image_records, allow_approve=True, brand_name=brand_name, instance_key=f"{index}-{post['id']}")

    if st.session_state["generated_plan"]:
        st.markdown("<div class='section-label'>Kế hoạch tuần</div>", unsafe_allow_html=True)
        display_plan_overview(st.session_state["generated_plan"])
        st.subheader("Xem trước bài đăng")
        st.caption("Xem trước từng bài kèm ảnh. Chỉnh sửa hoặc duyệt từng bài, hoặc duyệt tất cả.")
        if st.button("Duyệt và lưu toàn bộ kế hoạch", use_container_width=True, type="primary"):
            for post in st.session_state["generated_plan"]:
                approve_post(post, image_records)
            st.success("Đã lưu toàn bộ kế hoạch vào lịch đã duyệt.")
            st.rerun()

        for index, post in enumerate(st.session_state["generated_plan"], start=1):
            display_post_card(post, "plan", image_records=image_records, allow_approve=True, brand_name=brand_name, instance_key=f"{index}-{post['id']}")

with saved_tab:
    st.subheader("Lịch đã duyệt")
    saved_posts = load_saved_posts()
    fb_config = facebook_config()

    with st.expander("Kết nối đăng bài lên Facebook Page", expanded=False):
        if facebook_configured(fb_config):
            st.success(
                f"Đã cấu hình Facebook Page ID: {fb_config['page_id']} "
                f"· Graph API {fb_config['api_version']}"
            )
            st.caption(
                "Token được đọc từ biến môi trường hoặc Streamlit secrets "
                "và không hiển thị trên giao diện."
            )
            st.caption(
                "Đăng bài cần pages_manage_posts. Đồng bộ Like/Comment/Share cần "
                "pages_read_user_content; đồng bộ View cần read_insights."
            )
        else:
            st.warning("Chưa cấu hình kết nối Facebook Page.")
            st.code(
                'FACEBOOK_PAGE_ID = "your_page_id"\n'
                'FACEBOOK_PAGE_ACCESS_TOKEN = "your_page_access_token"\n'
                f'FACEBOOK_GRAPH_API_VERSION = "{FACEBOOK_GRAPH_API_DEFAULT_VERSION}"',
                language="toml",
            )
            st.caption(
                "Sao chép .streamlit/secrets.toml.example thành "
                ".streamlit/secrets.toml, điền thông tin thật rồi khởi động lại app."
            )

    if not saved_posts:
        st.info("Chưa có bài nào được duyệt. Hãy tạo nội dung ở tab 'Tạo nội dung' rồi bấm Duyệt.")
    else:
        st.caption(f"Đang có {len(saved_posts)} bài đã duyệt.")
        totals = engagement_totals(saved_posts)
        metric_col_1, metric_col_2, metric_col_3, metric_col_4, metric_col_5, metric_col_6 = st.columns(6)
        metric_col_1.metric("Like", totals["likes"])
        metric_col_2.metric("Comment", totals["comments"])
        metric_col_3.metric("Share", totals["shares"])
        metric_col_4.metric("Inbox/lead", totals["inboxes"])
        metric_col_5.metric("View", totals["views"])
        metric_col_6.metric("Điểm", totals["score"])

        # --- Export buttons ---
        export_col_1, export_col_2, export_col_3 = st.columns(3)
        with export_col_1:
            st.download_button(
                "Tải CSV",
                posts_to_csv_bytes(saved_posts),
                file_name="lich-noi-dung-da-duyet.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with export_col_2:
            st.download_button(
                "Tải JSON",
                json.dumps(saved_posts, ensure_ascii=False, indent=2).encode("utf-8"),
                file_name="lich-noi-dung-da-duyet.json",
                mime="application/json",
                use_container_width=True,
            )
        with export_col_3:
            st.download_button(
                "Tải Markdown",
                posts_to_markdown(saved_posts),
                file_name="lich-noi-dung-da-duyet.md",
                mime="text/markdown",
                use_container_width=True,
            )

        st.divider()

        for index, post in enumerate(saved_posts):
            saved_edit_key = f"saved-editing-{post['id']}"
            if saved_edit_key not in st.session_state:
                st.session_state[saved_edit_key] = False

            platforms = post.get("platforms", [])
            profile_name = post.get("source_brand", "") or "Shop của bạn"
            avatar_letter = profile_name[0].upper() if profile_name else "S"
            avatar_cls = "fb-avatar ig" if "Instagram" in platforms and "Facebook" not in platforms else "fb-avatar"
            badges_html = " ".join(
                f"<span class='platform-badge {'badge-fb' if p == 'Facebook' else 'badge-ig'}'>{p}</span>" for p in platforms
            )

            with st.container(border=True):
                # --- FB-style header with status ---
                head_col, status_col = st.columns([3, 1])
                with head_col:
                    day_label = post.get("day", "")
                    topic = post.get("topic", "")
                    st.markdown(f"""
                    <div class='fb-profile-header'>
                        <div class='{avatar_cls}'>{avatar_letter}</div>
                        <div class='fb-profile-info'>
                            <div class='fb-profile-name'>{profile_name}</div>
                            <div class='fb-profile-meta'>
                                {day_label} {badges_html}
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    if topic:
                        st.markdown(f"<span class='topic-tag'>{topic}</span>", unsafe_allow_html=True)
                with status_col:
                    status = post.get("status", "approved")
                    status_cls = "status-approved" if status == "approved" else "status-draft"
                    status_label = {"approved": "Đã duyệt", "draft": "Nháp"}.get(status, status)
                    created = post.get("created_at", "")
                    st.markdown(f"<div style='text-align:right;padding-top:8px;'><span class='status-pill {status_cls}'>{status_label}</span><br/><span class='post-meta'>{created}</span></div>", unsafe_allow_html=True)

                if st.session_state[saved_edit_key]:
                    # --- Editing mode ---
                    caption = st.text_area(
                        "Caption", post.get("caption", ""),
                        key=f"saved-caption-edit-{post['id']}", height=200
                    )
                    hashtags = st.text_input(
                        "Hashtag", " ".join(post.get("hashtags", [])),
                        key=f"saved-hashtags-edit-{post['id']}"
                    )
                    cta = st.text_input(
                        "CTA", post.get("cta", ""),
                        key=f"saved-cta-edit-{post['id']}"
                    )
                    content_role = st.text_input(
                        "Vai trò nội dung",
                        post.get("content_role", ""),
                        key=f"saved-role-edit-{post['id']}",
                    )
                    content_machine = st.text_input(
                        "Máy tạo nội dung",
                        post.get("content_machine", ""),
                        key=f"saved-machine-edit-{post['id']}",
                    )
                    hook_angle = st.text_input(
                        "Góc hook",
                        post.get("hook_angle", ""),
                        key=f"saved-hook-edit-{post['id']}",
                    )
                    kpi_goal = st.text_input(
                        "KPI mục tiêu",
                        post.get("kpi_goal", ""),
                        key=f"saved-kpi-edit-{post['id']}",
                    )
                    reels_script = st.text_area(
                        "Script Reels/video ngắn",
                        post.get("reels_script", ""),
                        key=f"saved-reels-edit-{post['id']}",
                        height=110,
                    )
                    image_guidance = st.text_input(
                        "Gợi ý ảnh",
                        post.get("image_guidance", ""),
                        key=f"saved-image-edit-{post['id']}",
                    )

                    new_images = st.file_uploader(
                        "Thêm/thay ảnh cho bài này",
                        type=["png", "jpg", "jpeg", "webp"],
                        accept_multiple_files=True,
                        key=f"saved-upload-{post['id']}",
                    )

                    btn_save_col, btn_cancel_col = st.columns(2)
                    with btn_save_col:
                        if st.button("Cập nhật bài", key=f"saved-update-{post['id']}", use_container_width=True, type="primary"):
                            saved_posts[index]["caption"] = polish_caption_text(caption)
                            saved_posts[index]["hashtags"] = normalize_hashtags(hashtags)
                            saved_posts[index]["cta"] = clean_model_text(cta)
                            saved_posts[index]["content_role"] = clean_model_text(content_role)
                            saved_posts[index]["content_machine"] = clean_model_text(content_machine)
                            saved_posts[index]["hook_angle"] = clean_model_text(hook_angle)
                            saved_posts[index]["kpi_goal"] = clean_model_text(kpi_goal)
                            saved_posts[index]["reels_script"] = clean_model_text(reels_script)
                            saved_posts[index]["image_guidance"] = clean_model_text(image_guidance)
                            if new_images:
                                new_records = cache_uploaded_images(new_images)
                                saved_posts[index]["image_files"] = [r["path"] for r in new_records]
                            save_saved_posts(saved_posts)
                            st.session_state[saved_edit_key] = False
                            st.success("Đã cập nhật.")
                            st.rerun()
                    with btn_cancel_col:
                        if st.button("Hủy", key=f"saved-cancel-{post['id']}", use_container_width=True):
                            st.session_state[saved_edit_key] = False
                            st.rerun()
                else:
                    strategy_bits = []
                    if post.get("content_role"):
                        strategy_bits.append(f"Vai trò: {post['content_role']}")
                    if post.get("content_machine"):
                        strategy_bits.append(f"Máy: {post['content_machine']}")
                    if post.get("hook_angle"):
                        strategy_bits.append(f"Hook: {post['hook_angle']}")
                    if post.get("kpi_goal"):
                        strategy_bits.append(f"KPI: {post['kpi_goal']}")
                    if strategy_bits:
                        st.caption(" | ".join(strategy_bits))

                    # --- Display mode: caption first, then image (FB style) ---
                    caption_text = post.get("caption", "")
                    st.markdown(f"<div class='fb-caption'>{caption_text}</div>", unsafe_allow_html=True)

                    hashtag_str = " ".join(post.get("hashtags", []))
                    if hashtag_str:
                        st.markdown(f"<div class='hashtag-line'>{hashtag_str}</div>", unsafe_allow_html=True)

                    if post.get("cta"):
                        st.markdown(f"<div class='cta-box'>{post['cta']}</div>", unsafe_allow_html=True)

                    if post.get("reels_script"):
                        with st.expander("Script Reels/video ngắn", expanded=False):
                            st.write(post["reels_script"])

                    if post.get("image_guidance"):
                        with st.expander("Gợi ý ảnh nên dùng", expanded=True):
                            st.write(post["image_guidance"])

                    # Image below caption
                    image_files = post.get("image_files", [])
                    existing_images = [p for p in image_files if Path(p).exists()]
                    if existing_images:
                        num_imgs = len(existing_images)
                        if num_imgs == 1:
                            img_col, _ = st.columns([2, 3])
                            with img_col:
                                st.image(existing_images[0], use_container_width=True)
                        elif num_imgs == 2:
                            img_cols = st.columns(2)
                            for idx, img_path in enumerate(existing_images[:2]):
                                with img_cols[idx]:
                                    st.image(img_path, use_container_width=True)
                        else:
                            img_cols = st.columns(min(num_imgs, 4))
                            for idx, img_path in enumerate(existing_images[:8]):
                                with img_cols[idx % len(img_cols)]:
                                    st.image(img_path, use_container_width=True)

                    # Full text for copy
                    full_text = caption_text
                    if hashtag_str:
                        full_text += "\n\n" + hashtag_str

                    publish_info = post.get("facebook_publish", {})
                    if publish_info.get("status") == "published":
                        published_at = publish_info.get("published_at", "")
                        facebook_url = publish_info.get("url", "")
                        published_message = f"Đã đăng Facebook lúc {published_at}"
                        if facebook_url:
                            st.success(f"{published_message} · [Mở bài đăng]({facebook_url})")
                        else:
                            st.success(published_message)
                    elif publish_info.get("status") == "failed":
                        st.error(
                            "Lần đăng Facebook gần nhất thất bại: "
                            f"{publish_info.get('error', 'Không rõ lỗi')}"
                        )

                    # --- Action buttons ---
                    act_col_1, act_col_2, act_col_3, act_col_4 = st.columns(4)
                    with act_col_1:
                        if st.button("Chỉnh sửa", key=f"saved-edit-btn-{post['id']}", use_container_width=True):
                            st.session_state[saved_edit_key] = True
                            st.rerun()
                    with act_col_2:
                        st.download_button(
                            "Copy caption",
                            data=full_text,
                            file_name=f"caption-{post['id']}.txt",
                            mime="text/plain",
                            key=f"saved-copy-{post['id']}",
                            use_container_width=True,
                        )
                    with act_col_3:
                        can_publish_facebook = (
                            "Facebook" in platforms
                            and facebook_configured(fb_config)
                        )
                        publish_label = (
                            "Đăng lại Facebook"
                            if publish_info.get("status") == "published"
                            else "Đăng Facebook"
                        )
                        if st.button(
                            publish_label,
                            key=f"saved-facebook-{post['id']}",
                            use_container_width=True,
                            type="primary",
                            disabled=not can_publish_facebook,
                            help=(
                                None
                                if can_publish_facebook
                                else "Bài phải chọn nền tảng Facebook và app cần được cấu hình Page ID + Page Access Token."
                            ),
                        ):
                            with st.spinner("Đang đăng bài lên Facebook..."):
                                try:
                                    result = publish_post_to_facebook(
                                        saved_posts[index],
                                        fb_config,
                                    )
                                    saved_posts[index]["facebook_publish"] = {
                                        "status": "published",
                                        "post_id": result.get("post_id", ""),
                                        "photo_id": result.get("photo_id", ""),
                                        "photo_ids": result.get("photo_ids", []),
                                        "url": result.get("url", ""),
                                        "published_at": datetime.now().isoformat(
                                            timespec="seconds"
                                        ),
                                        "error": "",
                                    }
                                    save_saved_posts(saved_posts)
                                    st.success("Đã đăng bài lên Facebook Page.")
                                    st.rerun()
                                except Exception as exc:
                                    saved_posts[index]["facebook_publish"] = {
                                        "status": "failed",
                                        "post_id": "",
                                        "url": "",
                                        "published_at": "",
                                        "failed_at": datetime.now().isoformat(
                                            timespec="seconds"
                                        ),
                                        "error": str(exc),
                                    }
                                    save_saved_posts(saved_posts)
                                    st.error(f"Không đăng được lên Facebook: {exc}")
                    with act_col_4:
                        if st.button("Xóa bài", key=f"saved-delete-{post['id']}", use_container_width=True):
                            saved_posts.pop(index)
                            save_saved_posts(saved_posts)
                            st.success("Đã xóa bài.")
                            st.rerun()

                    with st.expander("Cập nhật hiệu quả sau khi đăng", expanded=False):
                        metrics = post.get("metrics", {})
                        facebook_post_id = publish_info.get("post_id", "")
                        can_sync_metrics = bool(
                            facebook_post_id and facebook_configured(fb_config)
                        )
                        sync_col, sync_note_col = st.columns([1, 2])
                        with sync_col:
                            if st.button(
                                "Đồng bộ từ Facebook",
                                key=f"sync-facebook-metrics-{post['id']}",
                                use_container_width=True,
                                disabled=not can_sync_metrics,
                                help=(
                                    None
                                    if can_sync_metrics
                                    else "Chỉ đồng bộ được khi bài đã đăng từ app và có Facebook Post ID."
                                ),
                            ):
                                with st.spinner("Đang đọc số liệu từ Facebook..."):
                                    try:
                                        synced = fetch_facebook_post_metrics(
                                            saved_posts[index],
                                            fb_config,
                                        )
                                        current_metrics = saved_posts[index].get(
                                            "metrics", {}
                                        )
                                        current_metrics.update(
                                            {
                                                "likes": synced["likes"],
                                                "comments": synced["comments"],
                                                "shares": synced["shares"],
                                                "updated_at": datetime.now().isoformat(
                                                    timespec="seconds"
                                                ),
                                                "source": "facebook",
                                            }
                                        )
                                        if synced["views"] is not None:
                                            current_metrics["views"] = synced["views"]
                                        current_metrics.setdefault("inboxes", 0)
                                        saved_posts[index]["metrics"] = current_metrics
                                        saved_posts[index]["facebook_metrics_sync"] = {
                                            "synced_at": datetime.now().isoformat(
                                                timespec="seconds"
                                            ),
                                            "views_error": synced["views_error"],
                                        }
                                        save_saved_posts(saved_posts)
                                        if synced["views_error"]:
                                            st.warning(
                                                "Đã đồng bộ Like, Comment và Share. "
                                                "View chưa đọc được; hãy thêm quyền read_insights."
                                            )
                                        else:
                                            st.success(
                                                "Đã đồng bộ số liệu thật từ Facebook."
                                            )
                                        st.rerun()
                                    except Exception as exc:
                                        st.error(
                                            f"Không đồng bộ được từ Facebook: {exc}"
                                        )
                        with sync_note_col:
                            last_sync = post.get("facebook_metrics_sync", {}).get(
                                "synced_at", ""
                            )
                            if last_sync:
                                st.caption(f"Lần đồng bộ gần nhất: {last_sync}")
                            elif not facebook_post_id:
                                st.caption(
                                    "Bài này chưa có Facebook Post ID; hãy đăng từ app trước."
                                )

                        met_cols = st.columns(5)
                        likes = met_cols[0].number_input("Like", min_value=0, value=int(metrics.get("likes", 0) or 0), key=f"metric-like-{post['id']}")
                        comments = met_cols[1].number_input("Comment", min_value=0, value=int(metrics.get("comments", 0) or 0), key=f"metric-comment-{post['id']}")
                        shares = met_cols[2].number_input("Share", min_value=0, value=int(metrics.get("shares", 0) or 0), key=f"metric-share-{post['id']}")
                        inboxes = met_cols[3].number_input("Inbox", min_value=0, value=int(metrics.get("inboxes", 0) or 0), key=f"metric-inbox-{post['id']}")
                        views = met_cols[4].number_input("View", min_value=0, value=int(metrics.get("views", 0) or 0), key=f"metric-view-{post['id']}")
                        if st.button("Lưu hiệu quả", key=f"save-metrics-{post['id']}", use_container_width=True):
                            saved_posts[index]["metrics"] = {
                                "likes": likes,
                                "comments": comments,
                                "shares": shares,
                                "inboxes": inboxes,
                                "views": views,
                                "updated_at": datetime.now().isoformat(timespec="seconds"),
                            }
                            save_saved_posts(saved_posts)
                            st.success("Đã lưu hiệu quả bài đăng.")
                            st.rerun()

        st.divider()
        if st.button("Xóa toàn bộ lịch đã duyệt"):
            save_saved_posts([])
            st.success("Đã xóa toàn bộ lịch.")
            st.rerun()

with strategy_tab:
    st.subheader("Chiến lược nội dung cho ngành điện công nghiệp")
    st.markdown(
        """
Tool nên được định vị là **hệ thống vận hành nội dung bán hàng B2B**, không chỉ là nơi nhờ AI viết caption.

**Bài học từ page cùng ngành**
- Nhịp đăng hợp lý: khoảng **2-4 bài/tuần** hoặc **3-5 bài/tuần** nếu đang chạy chiến dịch sản phẩm.
- Nội dung đang hiệu quả ở nhóm kỹ thuật thường là: nỗi đau thật, rủi ro vận hành, thông số cần kiểm tra, giải pháp và CTA tư vấn.
- Bài ảnh/caption dài giúp xây niềm tin nhưng khó viral rộng. Reels/video ngắn có cơ hội kéo reach tốt hơn.
- Hashtag chỉ hỗ trợ phân loại nội dung, không cam kết lên xu hướng.
- Với page công ty mới/ít follower, mục tiêu không chỉ là inbox ngay mà còn là làm page có lý do để khách theo dõi lâu dài.

**Công thức bài nên dùng**
`Vấn đề -> Hậu quả -> Giải pháp -> Thông số/bằng chứng -> CTA cụ thể`

**Tỷ lệ nội dung đề xuất**
- 60% kiến thức kỹ thuật dễ lưu/chia sẻ: checklist, Q&A, myth-busting, lỗi thường gặp.
- 25% bán hàng mềm: mã sản phẩm, tình huống sử dụng, bảng chọn nhanh, CTA gửi ảnh tem/thông số.
- 15% thương hiệu/hậu trường: giới thiệu năng lực, kho hàng, kiểm tem, đóng hàng, quy trình tư vấn.

**Lịch đề xuất**
- 1 bài kiến thức dễ lưu: checklist/Q&A/bảng chọn nhanh.
- 1 bài sản phẩm cụ thể: mã hàng, thông số, ứng dụng, chính sách nếu có.
- 1 bài thương hiệu/hậu trường: kho hàng, kiểm tem, quy trình tư vấn đúng mã.
- 1 bài giải pháp hệ thống: làm mát, bù công suất, bảo vệ, đo lường, phụ kiện.
- 1 Reels/checklist ngắn: 3 điểm cần kiểm tra trước khi mua/lắp.

**KPI nên theo dõi**
- Share: nội dung có giá trị tham khảo trong ngành.
- Follow/save: tín hiệu page có giá trị lâu dài, đặc biệt với bài kiến thức.
- Comment/inbox: tín hiệu lead rõ nhất.
- View Reels: tín hiệu format có thể nhân rộng.
- Like chỉ là tín hiệu phụ, không nên dùng làm KPI chính cho B2B.
"""
    )
    with st.expander(f"{len(CONTENT_MACHINES)} máy tạo nội dung có thể dùng", expanded=False):
        for name, description in CONTENT_MACHINES.items():
            st.markdown(f"**{name}**")
            st.write(description)
    st.info(
        "Bước tự động đăng thật nên dùng Meta Graph API với quyền Page chính thức. MVP hiện tại nên ưu tiên soạn bài, duyệt, export/lên lịch và đo hiệu quả trước."
    )

    # ===== Chat box: Generate content ideas for machines =====
    st.divider()
    st.markdown("""
    <div class='machine-chat-input-wrapper'>
        <div class='machine-chat-title'>💡 Nhập sản phẩm cần quảng bá</div>
        <div class='machine-chat-subtitle'>Nhập tên sản phẩm rồi bấm tạo — AI sẽ gợi ý bộ content cho tất cả 24 máy tạo nội dung.</div>
    </div>
    """, unsafe_allow_html=True)

    machine_chat_input = st.text_input(
        "Sản phẩm muốn quảng bá",
        placeholder="Ví dụ: quạt tủ điện 120x120x38, tụ bù Mikro 25kVAr, MCCB Schneider 3P 100A...",
        key="machine_chat_input",
        label_visibility="collapsed",
    )

    generate_machine_ideas = st.button(
        "✨ Tạo 24 ý tưởng nội dung",
        key="generate_machine_ideas",
        type="primary",
        use_container_width=True,
    )

    if generate_machine_ideas and machine_chat_input.strip():
        # Show quick suggestion first
        suggestion = suggest_content_machines_from_chat(machine_chat_input, product=machine_chat_input)
        with st.container(border=True):
            st.markdown(f"⚡ **{suggestion['label']}**")
            st.caption(suggestion["reason"])
            st.markdown("**Máy ưu tiên:** " + " · ".join(f"`{m}`" for m in suggestion["machines"]))

        # Generate full ideas
        with st.spinner("🤖 AI đang viết sâu 6 máy ưu tiên và hoàn thiện bộ 24 nội dung..."):
            ideas = generate_machine_content_ideas(machine_chat_input)
            st.session_state["machine_chat_ideas"] = ideas
            st.session_state["machine_chat_product"] = machine_chat_input.strip()
    elif generate_machine_ideas:
        st.warning("Bạn nhập tên sản phẩm trước nhé.")

    # Display generated ideas
    if st.session_state.get("machine_chat_ideas") and st.session_state.get("machine_chat_product"):
        product_label = html.escape(st.session_state["machine_chat_product"])
        st.markdown(
            f"<div class='machine-ideas-grid-header'>"
            f"🎯 Bộ content cho <span class='machine-ideas-product-badge'>{product_label}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.caption(f"{len(st.session_state['machine_chat_ideas'])} ý tưởng đã tạo. Mỗi card là 1 máy tạo nội dung.")

        # Display in 2-column grid
        ideas = st.session_state["machine_chat_ideas"]
        for idx in range(0, len(ideas), 2):
            cols = st.columns(2)
            for col_offset in range(2):
                idea_idx = idx + col_offset
                if idea_idx >= len(ideas):
                    break
                idea = ideas[idea_idx]
                if not isinstance(idea, dict):
                    continue
                machine_name = html.escape(str(idea.get("machine", "Máy")))
                emoji = html.escape(str(idea.get("emoji", "📝")))
                priority = str(idea.get("priority", "Vừa"))
                priority_class = {
                    "Cao": "machine-priority-high",
                    "Vừa": "machine-priority-medium",
                    "Thấp": "machine-priority-low",
                }.get(priority, "machine-priority-medium")
                hook_text = html.escape(str(idea.get("hook", "")))
                outline_text = html.escape(str(idea.get("outline", "")))
                cta_text = html.escape(str(idea.get("cta", "")))
                image_tip_text = html.escape(str(idea.get("image_tip", "")))
                number = idea_idx + 1

                with cols[col_offset]:
                    card_html = f"""
                    <div class='machine-idea-card'>
                        <div class='machine-card-header'>
                            <div class='machine-card-number'>{number}</div>
                            <span class='machine-card-emoji'>{emoji}</span>
                            <span class='machine-card-title'>{machine_name}</span>
                            <span class='machine-card-priority {priority_class}'>{html.escape(priority)}</span>
                        </div>
                        <div class='machine-card-hook'>"{hook_text}"</div>
                        <div class='machine-card-outline'>{outline_text}</div>
                        <div class='machine-card-cta'>👉 {cta_text}</div>
                        <div class='machine-card-image-tip'>🖼️ {image_tip_text}</div>
                    </div>
                    """
                    st.markdown(card_html, unsafe_allow_html=True)

        # Button to clear
        if st.button("🗑️ Xóa kết quả", key="clear_machine_chat"):
            st.session_state["machine_chat_ideas"] = []
            st.session_state["machine_chat_product"] = ""
            st.rerun()

with guide_tab:
    st.subheader("Cách dùng cho người mới")
    st.markdown(
        """
Tool này giúp bạn đi từ **thông tin sản phẩm** thành **caption, gợi ý ảnh, lịch đăng tuần và danh sách bài đã duyệt**.
Nếu bạn là marketing mới, hãy xem nó như trợ lý soạn nội dung. Bạn không cần biết kỹ thuật, chỉ cần nhập đúng thứ bạn biết.

---

### 1. Quy trình nhanh nếu sếp giao 3-5 bài/tuần

1. Vào tab **Tạo nội dung**.
2. Nhập **Bạn bán gì?** bằng tên sản phẩm/dịch vụ cụ thể.
3. Điền ít nhất 4 ô: **Khách hàng mục tiêu**, **Thông số/đặc điểm**, **Nỗi đau/nhu cầu**, **Bằng chứng được phép dùng**.
4. Chọn **Nhịp đăng mục tiêu** là `3-5 bài/tuần`.
5. Ở ô **Bạn muốn chiến dịch này đạt mục tiêu gì?**, viết mục tiêu bằng ngôn ngữ bình thường.
6. Bấm **Áp dụng bộ máy gợi ý** nếu thấy gợi ý hợp lý.
7. Bật **AI tự search nội dung công khai** để lấy insight thị trường.
8. Bấm **Tạo nội dung & gợi ý ảnh** để có caption nhanh, hoặc **Tạo kế hoạch tuần** để có lịch 7 ngày.
9. Đọc lại bài, bấm **Chỉnh sửa** nếu cần.
10. Bấm **Duyệt và lưu** cho bài muốn dùng.
11. Qua tab **Lịch đã duyệt** để copy, tải file hoặc nhập hiệu quả sau khi đăng.

Ví dụ mục tiêu nên nhập:

```text
Tuần này cần 3-5 bài để giới thiệu sản phẩm mới, kéo inbox tư vấn và làm page nhìn chuyên nghiệp hơn.
```

---

### 2. Tab Tạo nội dung dùng để làm gì?

Đây là tab chính. Bạn dùng nó để nhập brief, tạo caption, tạo kế hoạch tuần và gợi ý ảnh.

**Nhóm thông tin đầu vào**

- **Bạn bán gì?**: nhập tên sản phẩm/dịch vụ. Càng cụ thể càng tốt.
- **Tên shop/thương hiệu**: tên công ty, shop hoặc nhãn hàng sẽ xuất hiện trong bài.
- **Khách hàng mục tiêu**: ai sẽ đọc hoặc mua. Ví dụ: thợ điện, kỹ thuật bảo trì, chủ xưởng, nhà thầu M&E.
- **Thông số/đặc điểm bắt buộc phải bám**: những thông tin không được viết sai như mã hàng, điện áp, kích thước, bảo hành.
- **Nỗi đau/nhu cầu khách hàng**: vấn đề khách đang gặp. Ví dụ: tủ điện nóng, sợ mua sai mã, cần thay nhanh đúng kích thước.
- **Bằng chứng được phép dùng**: chỉ nhập thứ có thật. Ví dụ: có VAT, bảo hành 12 tháng, có sẵn kho, hỗ trợ kiểm tra thông số.
- **Ưu đãi/chính sách**: hỗ trợ tư vấn, bảo hành, giao hàng, kiểm tra mã. Không có thì để trống.
- **Điểm khác biệt muốn nhấn mạnh**: điều bạn muốn bài viết tránh bị chung chung.
- **Nguồn vào muốn biến thành content**: dán link, ghi chú sale, feedback, câu hỏi inbox, tin ngành hoặc nội dung sếp đưa.

**Nhóm lựa chọn chiến lược**

- **Mục tiêu nội dung**: bài viết/chiến dịch này muốn đạt điều gì. Người mới nên chọn `Tư vấn đúng nhu cầu` hoặc `Chốt inbox`.
- **Giọng thương hiệu**: bài viết nên nói theo kiểu nào. B2B thì chọn `B2B chuyên nghiệp`; muốn gần gũi hơn thì chọn `Tư vấn thân thiện`.
- **Nền tảng**: nơi bạn định đăng, thường là Facebook và Instagram.
- **Model viết nội dung**: model AI dùng để viết. `qwen3:4b` sâu hơn nhưng có thể chậm; model nhỏ hơn thường nhanh hơn.
- **Độ dài caption**: chọn ngắn/dài tùy kênh đăng.
- **Playbook ngành điện/B2B**: nên bật nếu bạn viết cho ngành điện công nghiệp. Nó ép bài đi theo logic vấn đề -> hậu quả -> giải pháp -> thông số -> CTA.
- **Nhịp đăng mục tiêu**: số bài muốn đăng trong tuần.
- **Trụ cột ưu tiên**: tuần này nội dung nghiêng về chủ đề nào, ví dụ checklist, bán theo mã sản phẩm, hậu trường, kiến thức dễ lưu.
- **Định dạng ưu tiên**: ảnh + caption, Reels, album hoặc kết hợp.
- **Bạn muốn chiến dịch này đạt mục tiêu gì?**: nhập mong muốn thật của bạn. Tool sẽ gợi ý bộ máy tạo nội dung phù hợp.

**Máy tạo nội dung là gì?**

Máy tạo nội dung là các kiểu bài khác nhau. Ví dụ:

- `Checklist kỹ thuật`: bài dạng danh sách kiểm tra.
- `Q&A nhanh cho người mới`: hỏi đáp dễ hiểu.
- `Bài kéo inbox`: bài có CTA để khách nhắn tin.
- `Tin tức ngành điện`: bài bám tin/xu hướng trong ngành.
- `Hậu trường kho/đóng hàng`: bài xây niềm tin về công ty thật, hàng thật.

Nếu chưa biết chọn gì, cứ nhập mục tiêu chiến dịch rồi bấm **Áp dụng bộ máy gợi ý**.

**Search nội dung công khai**

- **AI tự search nội dung công khai**: tool tìm title/snippet/nội dung công khai để lấy insight.
- **AI đề xuất thêm từ khóa search**: AI tự nghĩ thêm query liên quan.
- **Nguồn search**: dùng DuckDuckGo mặc định; Google API chỉ dùng khi bạn có key.
- **Số kết quả mỗi từ khóa**: càng nhiều thì nhiều nguyên liệu hơn nhưng lâu hơn.

Kết quả search chỉ nên dùng để rút insight, không copy nguyên văn. Nếu thấy nguồn không liên quan, hãy bỏ qua hoặc chỉnh prompt/brief rõ hơn.

**Hai nút tạo kết quả**

- **Tạo nội dung & gợi ý ảnh**: tạo vài caption để dùng nhanh.
- **Tạo kế hoạch tuần**: tạo lịch nhiều ngày, có vai trò bài, KPI và gợi ý Reels/ảnh.

---

### 3. Tab Lịch đã duyệt dùng để làm gì?

Tab này là nơi lưu các bài bạn đã chọn từ tab **Tạo nội dung**.

Bạn dùng tab này để:

- Xem lại các bài đã duyệt.
- Chỉnh caption, hashtag, CTA, vai trò bài, máy tạo nội dung, KPI.
- Thêm hoặc thay ảnh cho từng bài.
- Copy caption để đăng thủ công.
- Tải lịch dưới dạng CSV, JSON hoặc Markdown.
- Nhập hiệu quả sau khi đăng: like, comment, share, inbox, view.

Nếu bạn làm việc theo tuần, workflow nên là:

```text
Tạo kế hoạch tuần -> chọn 3-5 bài tốt nhất -> Duyệt và lưu -> Lịch đã duyệt -> copy đăng hoặc xuất file gửi sếp.
```

Sau khi bài đăng thật, quay lại tab này nhập số liệu. Tool sẽ giúp bạn biết bài nào đáng nhân rộng.

---

### 4. Tab Chiến lược dùng để làm gì?

Tab này giúp bạn hiểu cách vận hành nội dung, không chỉ viết từng caption lẻ.

Trong tab này có:

- Gợi ý tỷ lệ nội dung cho page B2B: kiến thức, bán hàng mềm, thương hiệu/hậu trường.
- Công thức bài viết nên dùng: vấn đề -> hậu quả -> giải pháp -> thông số/bằng chứng -> CTA.
- Danh sách 24 máy tạo nội dung.
- Ô nhập sản phẩm để AI gợi ý ý tưởng cho từng máy tạo nội dung.

Khi bí ý tưởng, hãy vào tab **Chiến lược**, nhập sản phẩm, rồi xem 24 hướng content khác nhau. Sau đó quay lại **Tạo nội dung** để tạo bài cụ thể.

---

### 5. Tab Cách dùng dùng để làm gì?

Đây là phần hướng dẫn. Khi quên một mục nghĩa là gì, bạn quay lại đây để xem.

Người mới nên nhớ 3 câu:

```text
Mục tiêu nội dung = muốn bài làm gì.
Giọng thương hiệu = bài nói theo kiểu nào.
Trụ cột ưu tiên = tuần này tập trung loại nội dung gì.
```

---

### 6. Combo chọn nhanh cho người mới

Nếu chưa biết chọn gì, dùng combo này trước:

```text
Mục tiêu nội dung: Tư vấn đúng nhu cầu
Giọng thương hiệu: B2B chuyên nghiệp
Nhịp đăng mục tiêu: 3-5 bài/tuần
Trụ cột ưu tiên: Checklist chọn/lắp đúng
Định dạng ưu tiên: Ảnh + caption
Máy tạo nội dung: Checklist kỹ thuật, Q&A nhanh cho người mới, Bài kéo inbox, Review sản phẩm theo tình huống, Hậu trường kho/đóng hàng
```

Nếu sếp muốn có inbox nhanh hơn:

```text
Mục tiêu nội dung: Chốt inbox
Giọng thương hiệu: Tư vấn thân thiện
Trụ cột ưu tiên: Bán hàng theo mã sản phẩm
Máy tạo nội dung: Bài kéo inbox, Bảng chọn nhanh sản phẩm, Câu hỏi từ khách hàng, Review sản phẩm theo tình huống
```

Nếu sếp muốn page nhìn chuyên nghiệp hơn:

```text
Mục tiêu nội dung: Tăng nhận diện thương hiệu công ty
Giọng thương hiệu: B2B chuyên nghiệp
Trụ cột ưu tiên: Hậu trường/kho hàng/quy trình tư vấn
Máy tạo nội dung: Giới thiệu năng lực công ty, Hậu trường kho/đóng hàng, Case study khách hàng, Checklist kỹ thuật
```

---

**Lưu ý:** App này không tạo ảnh, không tạo video và không tự đăng bài. App giúp bạn soạn nội dung, duyệt bài, gợi ý ảnh cần chuẩn bị và lưu lịch. Phần đăng/lên lịch tự động là bước riêng khi có tài khoản Meta Business và quyền API chính thức.
"""
    )
