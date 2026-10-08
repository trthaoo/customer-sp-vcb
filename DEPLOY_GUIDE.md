# HƯỚNG DẪN DEPLOY TRỌN GÓI: RENDER + UPTIMEROBOT (+ VERCEL NẾU CẦN)

## 1. TẠI SAO NÊN CHỌN RENDER CHO TOÀN BỘ PROJECT?
- Project này gồm **FastAPI Backend (Python)** + **Giao diện Playground UI (HTML/CSS/JS)**.
- Giao diện UI đã được FastAPI đóng gói sẵn và phục vụ trực tiếp tại route `/playground` và `/`.
- **Lý do KHÔNG NÊN chạy API trên Vercel Serverless**:
  - Vercel Serverless gói Free giới hạn timeout **10 - 15 giây**.
  - Mô hình DeepSeek Reasoning mất từ **10 - 25 giây** để suy luận. Nếu để Vercel gọi DeepSeek, bạn sẽ thường xuyên bị lỗi **504 FUNCTION_INVOCATION_TIMEOUT**.
- **Giải pháp vàng**: **Host toàn bộ trên Render (Web Service)**.
  - Chạy liên tục (long-running).
  - Không bị giới hạn 10s timeout.
  - Phục vụ CẢ giao diện Playground UI lẫn Backend API trên 1 link HTTPS duy nhất (tránh 100% lỗi CORS).
  - Kết hợp với **UptimeRobot** ping định kỳ mỗi 5 phút -> Server thức 24/7, không bao giờ bị sleep!

---

## 2. CÁCH DEPLOY LÊN RENDER (3 PHÚT)

### Bước 1: Đẩy mã nguồn lên GitHub (hoặc GitLab)
Nếu chưa đẩy lên GitHub:
1. Tạo một repository mới trên GitHub (Private hoặc Public).
2. Đẩy toàn bộ thư mục project này lên GitHub.

### Bước 2: Tạo Web Service trên Render
1. Đăng nhập [https://render.com](https://render.com).
2. Bấm nút **New +** -> Chọn **Web Service**.
3. Chọn repo GitHub của bạn.
4. Cấu hình cơ bản:
   - **Name**: `vcb-customer-concierge`
   - **Region**: Singapore (hoặc Oregon)
   - **Branch**: `main`
   - **Runtime**: `Python 3` (hoặc `Docker`)
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn src.web.app:app --host 0.0.0.0 --port $PORT`
   - **Plan**: `Free`
5. Nhập **Environment Variables (Môi trường)**:
   - `MODEL_PROVIDER`: `openai`
   - `MODEL_BASE_URL`: `https://openrouter.ai/api/v1`
   - `MODEL_API_KEY`: key OpenRouter (nhập trực tiếp trên Render, không commit vào repo)
   - `MODEL_NAME`: `deepseek/deepseek-v4.1-flash`
   - `BASIC_AUTH_USER` / `BASIC_AUTH_PASS`: tài khoản đăng nhập cho người test. Bỏ trống thì ai có link cũng vào được.
   - `AUTO_SEND`: `false`
   - `HOLD_ON_HANDOVER`: `true`
6. Bấm **Create Web Service**. Đợi 2-3 phút, bạn sẽ nhận được domain vĩnh viễn:
   `https://vcb-customer-concierge.onrender.com`
   -> Truy cập Playground: `https://vcb-customer-concierge.onrender.com/playground`

---

## 3. CÀI ĐẶT UPTIMEROBOT ĐỂ RENDER KHÔNG BAO GIỜ BỊ SLEEP (THỨC 24/7 MIỄN PHÍ)
Render gói Free sẽ tự động sleep sau 15 phút không có ai truy cập. Ta dùng UptimeRobot ping định kỳ:

1. Đăng ký tài khoản miễn phí tại: [https://uptimerobot.com](https://uptimerobot.com)
2. Bấm **Add New Monitor**:
   - **Monitor Type**: `HTTP(s)`
   - **Friendly Name**: `VCB Concierge Wakeup`
   - **URL (or IP)**: `https://vcb-customer-concierge.onrender.com/api/health`
   - **Monitoring Interval**: `5 minutes` (mỗi 5 phút ping 1 lần)
3. Bấm **Create Monitor**.
-> Xong! UptimeRobot sẽ ping endpoint `/api/health` 5 phút 1 lần suốt 24/7, giữ cho Render luôn thức tỉnh và phản hồi tức thì bất cứ lúc nào khách hàng nhắn tin!

---

## 4. NẾU BẠN VẪN MUỐN ĐẨY UI LÊN VERCEL
Nếu bạn muốn giao diện UI chạy riêng trên domain Vercel (`.vercel.app`):
1. Đăng nhập [https://vercel.com](https://vercel.com).
2. Import repo GitHub.
3. Trong phần cấu hình, tệp [`vercel.json`](file:///c:/Users/MR.%20WIND/OneDrive/Desktop/customer%20sp_vcb/vercel.json) đã được chuẩn bị sẵn trong project để Vercel phục vụ các trang `/playground` và `/`.
4. Trên giao diện UI `playground.html`, trỏ các lời gọi `fetch('/api/playground/chat')` về domain backend Render của bạn: `https://vcb-customer-concierge.onrender.com/api/playground/chat`.

---

## 5. LƯU GIỮ LOGS & CHAT SESSIONS TRÊN RENDER: CÓ CẦN DATABASE KHÔNG?

### 👉 Trả lời:
- **Ở máy Local**: **KHÔNG cần database**, hệ thống tự dùng SQLite cục bộ lưu vào file `.db`.
- **Khi deploy lên Render (Gói Free)**: **NÊN THÊM DATABASE CLOUD (Miễn phí 100%)**.
  - *Lý do:* Render Free sử dụng **ổ cứng tạm (ephemeral filesystem)**. Sau mỗi lần Render khởi động lại hoặc deploy bản mới, các file SQLite cục bộ trong container sẽ bị reset.
  - *Giải pháp:* Dự án đã được tích hợp **cơ chế Dual Database thông minh**:
    - Nếu **KHÔNG có `DATABASE_URL`**: Tự động dùng SQLite cục bộ.
    - Nếu **CÓ `DATABASE_URL`**: Tự động chuyển sang Cloud PostgreSQL, lưu giữ toàn bộ Chat Sessions, Turns, Metrics và Events vĩnh viễn!

### Cách lấy PostgreSQL miễn phí chỉ trong 1 phút:
1. **Cách 1 (Ngay trên Render - Khuyên dùng):**
   - Vào Dashboard Render -> Bấm **New +** -> **PostgreSQL**.
   - Đặt tên: `vcb-database` -> Bấm **Create Database**.
   - Copy mục **Internal Database URL** (dạng `postgresql://user:pass@host/dbname`).
   - Vào Web Service của bạn trên Render -> Mục **Environment** -> Thêm biến:
     `DATABASE_URL` = `<URL vừa copy>`.
   - Bấm **Save Changes**. Xong!
2. **Cách 2 (Neon.tech / Supabase - Free vĩnh viễn):**
   - Đăng ký tài khoản tại [https://neon.tech](https://neon.tech) (1-click login bằng GitHub).
   - Tạo database miễn phí -> Copy Connection String dán vào biến `DATABASE_URL` trên Render.

### Xem Lại Logs Chat:
- **Trên Ops Dashboard (`/`)**: Vào tab **"📜 Chat Sessions & Logs"** để xem toàn bộ danh sách phiên chat, số lượt trao đổi, lọc theo kênh, và xem transcript chi tiết từng tin nhắn khách và bot!
- **Trên Playground (`/playground`)**: Bấm nút **"📜 Logs Chat"** ở thanh header để xem lịch sử và tải CSV phiên chat trực tiếp.

---

## 6. VPS: TỰ DEPLOY KHI PUSH LÊN `main`

Bản đang chạy cho bên test nằm trên VPS (`https://62-106-66-4.sslip.io`), không dùng Render.

Quy trình khi sửa rule hoặc code:
1. Sửa file (ví dụ `knowledge/meta/rules.md`) rồi push lên nhánh `main`.
2. GitHub Actions (tab **Actions**) chạy test. Nếu một khối YAML trong rule hoặc edge case viết sai, test `tests/test_knowledge_valid.py` sẽ báo đỏ và chỉ ra file bị lỗi.
3. Trong vòng 1 phút, VPS tự kéo commit mới, chạy lại test kiểm tra kiến thức, rồi restart app.
4. Nếu test trên VPS fail hoặc app không lên, VPS giữ nguyên bản cũ và bỏ qua commit đó. Sửa lỗi rồi push commit mới là được.

Không cần secret nào trên GitHub: VPS tự kéo code từ repo public. Nếu chuyển repo sang private, cần thêm deploy key (read-only) cho VPS.

Xem log deploy trên VPS: `journalctl -u vcb-deploy -n 50`.
