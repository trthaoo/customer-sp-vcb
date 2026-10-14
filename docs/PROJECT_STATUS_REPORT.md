# 📊 BÁO CÁO TIẾN TRÌNH DỰ ÁN & TỔNG HỢP THAY ĐỔI (3 NGÀY VỪA QUA)
**Dự án:** Customer Service Auto-Reply Gateway (Huy K Jewelry / Viễn Chí Bảo)  
**Thời gian lập báo cáo:** 14/10/2026  
**Phạm vi rà soát:** Từ 12/10/2026 đến 14/10/2026 (Kèm bối cảnh hoàn thiện từ 09/10/2026)  
**Tình trạng hiện tại:** 🟢 **Hoạt động ổn định · 100% Test Passed (90/90 tests)**

---

## I. TỔNG QUAN TIẾN TRÌNH DỰ ÁN HIỆN TẠI

### 1. Mục tiêu & Bản chất hệ thống
Hệ thống là một **AI Concierge & Trợ lý bán hàng tự động chuyên sâu** cho thương hiệu trang sức thủ công Huy K / Viễn Chí Bảo, vận hành đa kênh trên **Instagram, Facebook** (Meta Funnel) và **TikTok** (TikTok Funnel) thông qua transport Zernio.

### 2. Trạng thái kiểm thử & Chất lượng (Quality Assurance)
- **Bộ kiểm thử tự động:** Đạt **90/90 unit & regression tests** (tỷ lệ đạt **100%**).
- **Phạm vi bảo vệ kiểm thử:**
  - Quy chuẩn phân tách 2 Funnel: Meta vs TikTok.
  - Zero-Guessing Grounding: Tuyệt đối không bịa đặt thông tin khi thiếu dữ liệu hoặc giá sản phẩm chưa công bố.
  - Quy chuẩn phản hồi: Comment công khai (<15 từ, 1 dòng, không lộ giá, không tách bong bóng) vs Private DM (chuỗi tin nhắn tự nhiên, chuyên sâu, hỗ trợ PayPal).
  - Tích hợp mô hình kép: System 1 (Jev System One / Cloudflare Bridge) + System 2 (DeepSeek AI Reasoning).
  - Bảo mật truy cập & Phân quyền trang Ops và Logs.
  - Quản lý phiên chat, live backup ra file cục bộ (`data/chat_logs/`) và PostHog replay tracking.

### 3. Trạng thái hạ tầng & Triển khai thực tế (Deployment Status)
- **Môi trường Live (Production VPS):** Đang chạy thực tế tại địa chỉ: `https://62-106-66-4.sslip.io`
- **Cơ chế CI/CD tự động:**
  - Mỗi khi push commit lên nhánh `main`, VPS tự động kéo code mới trong 1 phút, chạy test kiểm tra tính hợp lệ của toàn bộ file kiến thức/YAML, và tự động restart app an toàn.
  - Toàn bộ dữ liệu phiên chat (`events.db`), feedback, file backup và vector store nằm biệt lập trên VPS, không bị ghi đè khi deploy.
- **Phân tách 2 giao diện người dùng:**
  - **`/playground`**: Môi trường kiểm thử cho đội ngũ Tester (bảo vệ bằng `BASIC_AUTH_USER`/`PASS`). Hỗ trợ upload ảnh/video từ máy, đính kèm link, đổi kênh, xem live streaming diagnostics.
  - **`/ops`**: Ops Dashboard dành riêng cho Admin (`ADMIN_USER`/`ADMIN_PASS`). Quản lý toàn bộ lịch sử phiên chat, metrics, transcript từng turn, đánh giá Đạt / Lỗi (Golden Examples vs Case lỗi cần fix), export CSV.

---

## II. CHI TIẾT CÁC THAY ĐỔI & CHỈNH SỬA TRONG 3 NGÀY VỪA QUA (12/10 - 14/10/2026)

Trong 3 ngày vừa qua, dự án đã trải qua 5 đợt commit lớn với **1.501 dòng code được thêm mới** và **187 dòng code được tinh chỉnh/loại bỏ** trên **24 files**:

```
.env.example                    |   9 +
knowledge/meta/edge_cases.md    |  40 ++---
knowledge/meta/rules.md         | 113 ++++++++++++-
knowledge/policies/payment.md   |   7 +-
knowledge/shared/brand_voice.md |  60 +++++--
knowledge/shared/fallbacks.md   |   6 +-
knowledge/tiktok/edge_cases.md  |  18 +-
knowledge/tiktok/rules.md       | 109 ++++++++++++-
requirements.txt                |   1 +
src/adapters/embedding.py       |  21 ++-
src/adapters/jev.py             | 353 ++++++++++++++++++++++++++++++++++++++++
src/adapters/model.py           | 123 ++++++++++----
src/config.py                   |   8 +
src/knowledge/chunker.py        |  70 +++++---
src/knowledge/loader.py         |   2 +-
src/knowledge/rag_service.py    |  34 +++-
src/pipeline/composer.py        | 124 +++++++++-----
src/pipeline/engine.py          |  20 ++-
src/pipeline/intent.py          |  59 +++++--
src/pipeline/orchestrator.py    |  34 +++-
src/web/app.py                  |  13 +-
tests/test_case_loi.py          | 172 ++++++++++++++++++++
tests/test_jev_rag.py           | 285 ++++++++++++++++++++++++++++++++
tests/test_playground.py        |   7 +-
```

### 1. Commit `9b3f653` (13/10/2026 15:23): Tích hợp hoàn chỉnh Jev System One RAG Reranking & Gating với Live Cloudflare Bridge
- **Tích hợp Cloudflare Bridge & Jev:**
  - Hoàn thiện module `JevAdapter` kết nối với Cloudflare AI Bridge, cho phép đánh giá xác suất mức độ liên quan của các đoạn kiến thức RAG nhanh và nhẹ hơn.
  - Cơ chế **Gating & Abstain**: Nếu toàn bộ các đoạn văn bản trong cơ sở tri thức bị Jev đánh giá là không liên quan hoặc không chứa dữ kiện câu hỏi ("Abstain: Not in Docs"), hệ thống sẽ chủ động ngắt không đưa tài liệu rác vào LLM để triệt tiêu hoàn toàn nguy cơ bịa đặt thông tin.
- **Tối ưu hóa Intent Pipeline:** Bỏ các logic thủ công dư thừa, cho phép Jev và Semantic Classifier phối hợp mượt mà.
- **Kiểm thử bổ sung:** Bổ sung unit test kết nối live cloudflare bridge trong `tests/test_jev_rag.py`.

### 2. Commit `3d4ccd2` (13/10/2026 10:19): Đồng bộ toàn bộ Knowledge Base theo Sales Test Feedback & Nâng cấp Pipeline
Đợt cập nhật quan trọng nhất nhằm đáp ứng trực tiếp kết quả thử nghiệm thực tế của Đội ngũ Bán hàng (Sales Team):
- **Chuẩn hóa Persona & Giọng điệu thương hiệu (Brand Voice):**
  - Đóng đinh đại từ nhân xưng: **Huy K & Đội ngũ thợ chế tác kim hoàn** ("chúng mình", "tụi mình", "thợ bên mình", "our artisans").
  - **Cấm tiệt lối nói đùn đẩy trách nhiệm** của bên thứ ba như: *"để em hỏi thợ"*, *"chờ em check xưởng"*, *"em chỉ là tư vấn viên"*, *"specialist"*, *"workshop"*. Mọi câu trả lời đều thể hiện sự am hiểu kỹ thuật trang sức sâu sắc ngay tại chỗ.
- **Bổ sung bộ tiêu chuẩn tư vấn bán hàng thực tế (Sales Team Standards):**
  - **Tư vấn Size:** Cung cấp dải size chuẩn US 4–12 ngay khi khách hỏi chung chung, hướng dẫn đo chu vi ngón tay, không bắt khách chờ hỏi xưởng.
  - **Chất liệu & Đá quý:** Xác nhận nhận gia công vàng 14K/18K theo yêu cầu, tùy chọn đá Moissanite hoặc Kim cương tự nhiên.
  - **Chống đen xỉn & Bảo quản:** Giải thích cơ chế bạc S925 mạ bạch kim (platinum plating), tặng kèm khăn lau bạc chuyên dụng, cảnh báo không ngâm hóa chất tẩy rửa mạnh.
  - **Cam kết uy tín & Chống lừa đảo:** Cam kết đền bù 10 lần giá trị nếu phát hiện bạc giả, nhấn mạnh 10 năm chế tác thủ công.
  - **Thanh toán & Vận chuyển quốc tế:** Hướng dẫn thanh toán an toàn qua PayPal bằng đường link ở Bio (Bio link), **tuyệt đối không gửi ảnh mã QR** trong khung chat; hỗ trợ giao hàng quốc tế (US, EU, Úc, Canada, Á - kể cả Trung Quốc).
- **Nâng cấp `KnowledgeChunker`:**
  - Đánh chỉ mục (chunking) toàn diện các tiêu chuẩn bán hàng trong `brand_voice.md`, các từ khóa trigger và hướng dẫn xử lý trong `edge_cases.md` và `rules.md` vào kho RAG.
- **Nâng cấp `FunnelEngine` với 3-Pass Routing:**
  - *Pass 1:* Ưu tiên khớp các rule chuyên biệt khớp cả `intent` lẫn các từ khóa cụ thể trong `contains_any`.
  - *Pass 2:* Khớp các rule tổng quát theo channel, surface và intent.
  - *Pass 3:* Khớp các rule fallback với `surface="any"`.
- **Nâng cấp bộ lọc Output Sanitizer (`src/adapters/model.py`):**
  - Lọc sạch triệt để thẻ suy luận nội tâm `<think>...</think>`.
  - Cắt bỏ các token điều khiển nội bộ: `[HANDOVER]`, `[REASON]`, `[ESCALATE]`.
  - Loại bỏ các dấu ngoặc vuông `]` rơi rớt ở cuối câu do model sinh ra.
- **Bổ sung 25 Regression Test Cases thực chiến:** Toàn bộ các ca tư vấn vàng, đá, size, ship Trung Quốc, bảo quản, PayPal... trong `tests/test_case_loi.py` đều đạt 100%.

### 3. Commit `f82c366` (12/10/2026 10:41): Ngăn ngừa rò rỉ Reasoning Content, Khôi phục Budget 2048 Token & Bảo vệ Comment Fallbacks
- **Ngăn chặn rò rỉ suy luận DeepSeek:**
  - Khắc phục lỗi nội dung thẻ `<think>` hoặc trường `reasoning_content` bị tuồn ra câu trả lời gửi đến khách hàng khi sử dụng các mô hình DeepSeek Reasoner.
- **Khôi phục Budget Token:**
  - Tái lập mức 2048 token tối đa để DeepSeek có đủ không gian suy luận logic phức tạp trước khi sinh câu trả lời ngắn gọn cuối cùng.
- **Tăng cường Fallback cho Comment công khai:**
  - Đảm bảo câu trả lời comment công khai luôn tuân thủ nghiêm ngặt: **1 dòng duy nhất, dưới 15 từ, không báo giá lộ liễu, không gửi nhiều tin nhắn dồn dập**.

### 4. Commit `8bfc4b7` (12/10/2026 10:21): Tối ưu hóa hiệu năng song song (Parallelization Execution)
- **Tối ưu hóa độ trễ xử lý (Latency Reduction):**
  - Tại `src/pipeline/orchestrator.py`, hệ thống triển khai `ThreadPoolExecutor` để chạy đồng thời:
    1. **Product Matcher** (Khớp sản phẩm)
    2. **Intent Classifier** (Phân loại ý định)
    3. **RAG Knowledge Search** (Tìm kiếm kiến thức ứng viên)
  - Giảm thời gian xử lý pipeline từ **1.5x đến 2x**, trong khi vẫn bảo toàn 100% độ chính xác suy luận ngữ nghĩa của AI.

### 5. Commit `51775be` (12/10/2026 10:12): Tích hợp ban đầu Jev System One vào RAG Pipeline
- Đặt nền móng cho kiến trúc **Dual-System AI**:
  - **System 1 (Jev System One):** Mô hình xác suất nhanh, thực hiện lọc ban đầu, chấm điểm độ phù hợp của chunk kiến thức, kiểm tra xem tin nhắn có cần nạp tài liệu hay không (`needs_knowledge`).
  - **System 2 (DeepSeek / LLM):** Chịu trách nhiệm tổng hợp, tư vấn chuyên sâu và soạn thảo câu trả lời tự nhiên theo giọng văn nghệ nhân.

---

## III. TỔNG HỢP KIẾN TRÚC HỆ THỐNG HIỆN TẠI

```mermaid
flowchart TD
    A[Tin Nhắn Đến: IG / FB / TikTok] --> B[1. Normalizer]
    B --> C{Xử lý song song - ThreadPoolExecutor}
    
    C -->|Worker 1| D[Product Matcher]
    C -->|Worker 2| E[Intent Classifier]
    C -->|Worker 3| F[RAG Candidate Retrieval]
    
    D & E & F --> G[4. FunnelEngine: 3-Pass Routing]
    
    G --> H{Kiểm tra Edge Case?}
    H -->|Khớp Edge Case| I[Kích hoạt Edge Case / Escalation]
    H -->|Không| J[Khớp Channel Rule]
    
    I & J --> K[5. Jev System One: Reranking & Gating]
    K -->|Abstain: Thiếu dữ kiện| L[Handover sang người / Fallback an toàn]
    K -->|Grounded: Đầy đủ dữ kiện| M[6. Human Reply Composer: Persona Huy K]
    
    M --> N[7. Model Output Sanitizer]
    N -->|Loại bỏ think, token, bracket| O[8. Verify & Event Log]
    O --> P[Ghi SQLite / Postgres + Live Disk Backup data/chat_logs/]
    O --> Q[Phản hồi khách hàng qua Zernio Transport]
```

### Các nguyên tắc vàng đã được kiểm chứng bằng 90 tests:
1. **Zero-Guessing Grounding:** Nếu thiếu thông tin sản phẩm, thiếu giá hoặc không rõ thông tin bảo hành, AI trả về câu dự phòng ngắn gọn và tự động gán cờ `handover` cho nhân viên trực tiếp hỗ trợ.
2. **Comment vs DM:**
   - **Comment:** 1 câu ngắn (<15 từ), mời khách check tin nhắn riêng, không báo giá trực tiếp để tăng tương tác và bảo vệ chính sách giá.
   - **DM:** Trả lời tự nhiên bằng phong cách chat nhiều bong bóng (Sequential Bubbles) như người thật đang gõ phím.
3. **Phân quyền chặt chẽ:** Tester chỉ thao tác trong `/playground`, Admin độc quyền truy cập `/ops` để xem log nội bộ, session transcript và cấu hình nhạy cảm.

---

## IV. CÁC CÔNG VIỆC ĐANG TIẾP DIỄN & HƯỚNG PHÁT TRIỂN TIẾP THEO

### 1. Nhiệm vụ vừa được yêu cầu (Work In Progress):
- **Bổ sung chỉ số thời gian phản hồi của Bot (Bot Response Time) vào Chat Logs & Dashboard:**
  - *Mục tiêu:* Ghi nhận chính xác số giây/mili-giây mà bot tiêu tốn từ lúc nhận tin nhắn đến lúc sinh câu trả lời hoàn chỉnh.
  - *Hiển thị:* Hiển thị trực quan trong Modal xem Transcript của Ops Dashboard (`/ops`) và file backup Markdown/JSON để đội ngũ vận hành đo lường hiệu năng thực tế.

### 2. Các bước kế tiếp (Next Roadmap):
- **Đánh giá hiệu năng thực tế trên Production VPS:** Đo lường độ trễ trung bình của các câu trả lời phức tạp (DeepSeek Reasoning) kết hợp cùng Jev System One.
- **Theo dõi Session Replay qua PostHog:** Giám sát hành vi người dùng trên giao diện Playground và các phiên test thực tế để phát hiện sớm các trường hợp nhập liệu dị biệt của khách hàng.
- **Tiếp tục mở rộng danh mục sản phẩm:** Bổ sung thêm các dòng trang sức mới vào catalogue khi có bảng giá chính thức từ thương hiệu.

---
*Báo cáo được tổng hợp tự động từ Git Commit History, Kiến trúc mã nguồn và Kết quả thực thi Test Suite của dự án.*
