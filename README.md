# Customer Service Auto-Reply Gateway (Instagram, Facebook, TikTok)

Hệ thống phản hồi tự động thông minh cho bình luận (comments) và tin nhắn (DMs) trên 3 nền tảng: **Instagram**, **Facebook** và **TikTok**, vận hành độc quyền qua transport **Zernio** (`https://zernio.com/api/v1`).

---

## 1. Kiến Trúc Tổng Quan (Architecture)

Hệ thống được thiết kế theo mô hình 2 funnel tách biệt tuyệt đối (không dùng chung rule trả lời):
- **Meta Funnel**: Quản lý Instagram & Facebook (hỗ trợ lọc platform `ig` | `fb` | `all`).
- **TikTok Funnel**: Quản lý TikTok chuyên biệt (`tiktok`).

Mã nguồn dùng chung chỉ bao gồm các tiện ích chuẩn hóa (normalize, product match, intent classification, rule engine core, reply composer, escalation, event log).

### Pipeline 8 Bước Xử Lý Mọi Tin Nhắn:
1. **Normalize**: Chuẩn hóa platform (`ig`, `fb`, `tiktok`), channel (`meta`, `tiktok`), surface (`comment`, `dm`), text, context (caption video/post), thread_id, user_id, message_id.
2. **Match Product**: Khớp sản phẩm qua tên và aliases trong catalogue. **Nếu 2 sản phẩm cùng khớp (ambiguity), tuyệt đối không đoán mò**, chuyển sang hỏi lại khách hoặc handover.
3. **Classify Intent**: Phân loại intent chuẩn (`ask_price`, `ask_material`, `ask_size`, `ask_stock`, `ask_shipping`, v.v.).
4. **Match Edge Case & Rule**: 
   - Ưu tiên kiểm tra **Edge Case** trước (Edge case luôn ghi đè rule thông thường).
   - Nếu không có edge case, kiểm tra **Channel Rule** theo funnel tương ứng.
   - Nếu không có rule, chuyển sang **Fallback**.
5. **Load Knowledge Fields**: Chỉ nạp đúng các trường dữ liệu mà rule trích dẫn (ví dụ: `catalogue.price`, `policies.shipping`).
6. **Compose Human Reply**: Soạn câu trả lời tự nhiên theo Brand Voice và sự thật cho phép. Giới hạn độ dài kiểm soát theo cấu hình per-platform (`PLATFORM_LIMITS`), không hardcode trong prompt.
7. **Verify & Escalation**: Nếu thiếu dữ liệu bắt buộc (null/empty), hoặc edge case yêu cầu escalate: **tuyệt đối không bịa đặt số liệu**, trả về câu fallback, gán cờ `flag="handover"`, `needs_human=true`. Nếu cấu hình `HOLD_ON_HANDOVER=true`, giữ lại tin nhắn không gửi ra ngoài.
8. **Audit Event Log**: Ghi log quyết định và danh sách file kiến thức đã sử dụng vào cơ sở dữ liệu SQLite.

---

## 2. Cài Đặt & Môi Trường (Setup & Environment)

### Yêu Cầu:
- Python 3.10+ (Đã kiểm tra trên Python 3.12).
- Cài đặt dependencies:
  ```bash
  pip install -r requirements.txt
  ```

### File Cấu Hình `.env`:
Tạo file `.env` từ `.env.example`:
```bash
cp .env.example .env
```

Nội dung `.env.example`:
```env
ZERNIO_API_KEY=
ZERNIO_BASE_URL=https://zernio.com/api/v1
ZERNIO_WEBHOOK_SECRET=
ZERNIO_PROFILE_ID_INSTAGRAM=
ZERNIO_PROFILE_ID_FACEBOOK=
ZERNIO_PROFILE_ID_TIKTOK=

MODEL_PROVIDER=
MODEL_API_KEY=
MODEL_BASE_URL=
MODEL_NAME=

AUTO_SEND=false
HOLD_ON_HANDOVER=true
```

> **Ghi chú về bảo mật và khởi động app:**
> - `ZERNIO_API_KEY` và API Model được để trống mặc định.
> - Khi thiếu API key, ứng dụng **vẫn khởi động bình thường**, chế độ **dry-run và template fallback hoạt động trơn tru**, còn tính năng gửi live ra Zernio sẽ được tự động vô hiệu hóa an toàn.

---

## 3. Cấu Trúc Thư Mục Kiến Thức (Knowledge Base Tree)

Hệ thống đọc dữ liệu duy nhất từ cây thư mục `/knowledge`:
```
knowledge/
  ├── shared/
  │   ├── brand_voice.md       # Giọng văn, xưng hô, cấm nhận là AI/bot
  │   ├── escalation.md        # Tiêu chuẩn chuyển giao nhân viên
  │   ├── fallbacks.md         # Câu phản hồi dự phòng khi thiếu dữ liệu
  │   └── intents.md           # Danh sách tên các intent
  ├── meta/
  │   ├── funnel.md            # Quy chuẩn comment vs inbox, IG vs FB
  │   ├── rules.md             # Quy tắc trả lời riêng của Meta
  │   ├── edge_cases.md        # Trường hợp đặc biệt kênh Meta
  │   └── policies.md          # Chính sách riêng cho Meta
  ├── tiktok/
  │   ├── funnel.md            # Quy chuẩn TikTok video & DM
  │   ├── rules.md             # Quy tắc trả lời riêng của TikTok
  │   ├── edge_cases.md        # Trường hợp đặc biệt kênh TikTok
  │   └── policies.md          # Chính sách riêng cho TikTok
  ├── catalogue/
  │   ├── products.template.json # Template catalogue (mảng products rỗng)
  │   └── README.md
  └── policies/
      ├── shipping.md          # Chính sách vận chuyển
      ├── returns.md           # Chính sách đổi trả
      ├── warranty.md          # Chính sách bảo hành
      ├── payment.md           # Chính sách thanh toán & cọc
      └── promotions.md        # Chính sách khuyến mãi
```

### Quy Tắc Khối `EXAMPLE_DELETE_ME`:
- Mỗi file markdown kiến thức đều chứa: mục đích (`Purpose`), các phần chờ điền (`TODO`), và **một khối đánh dấu `EXAMPLE_DELETE_ME`**.
- Bộ nạp kiến thức (`KnowledgeBase Loader`) **tự động loại bỏ hoàn toàn mọi khối `EXAMPLE_DELETE_ME`**. Bộ test tự động bảo đảm câu trả lời không bao giờ chứa thông tin từ các khối ví dụ này.

### Schema Sản Phẩm (`catalogue/products.template.json`):
```json
{
  "id": "SP001",
  "name": "Tên sản phẩm",
  "aliases": ["tên gọi khác 1", "tên gọi khác 2"],
  "price": 500000,
  "currency": "VND",
  "material": "Bạc S925",
  "variants": ["Size 16", "Size 17"],
  "in_stock": true,
  "ship_note": "Giao ngay trong 24h",
  "size_guide": "Đo chu vi ngón tay",
  "url": "https://brand.com/sp001",
  "notes": "Hàng bán chạy"
}
```
*Bất kỳ trường nào là `null` hoặc file chính sách bị rỗng, hệ thống sẽ tự động kích hoạt fallback + handover. Tuyệt đối không tự suy đoán thông tin.*

---

## 4. Cách Thêm Rule Và Edge Case

### Thêm một Rule mới:
Chỉnh sửa file `knowledge/meta/rules.md` (nếu cho Meta) hoặc `knowledge/tiktok/rules.md` (nếu cho TikTok) trong khối ````yaml`:
```yaml
- id: meta_ask_custom_inquiry
  channel: meta
  surface: dm
  when:
    intent: request_custom
    contains_any: ["đặt làm", "khắc tên", "thiết kế riêng"]
    product_required: false
  use_knowledge: ["policies.payment"]
  if_missing: escalate
  reply_guide: "Hỏi khách về ý tưởng mẫu hoặc chữ muốn khắc, thông báo quy định cọc nếu có trong chính sách."
```

### Thêm một Edge Case mới:
Chỉnh sửa file `knowledge/meta/edge_cases.md` hoặc `knowledge/tiktok/edge_cases.md`:
```yaml
- id: meta_edge_urgent_gift
  channel: meta
  trigger: "Khách cần gấp làm quà tặng trong ngày"
  contains_any: ["cần gấp", "tặng sinh nhật hôm nay", "giao liền bây giờ"]
  do: "Ưu tiên tư vấn các mẫu sẵn hàng và báo hotline hỗ trợ hỏa tốc"
  do_not: "Không cam kết thời gian giao khi chưa xác định được địa chỉ khách"
  escalate: true
  example_user_message: "Shop ơi mình cần gấp chiều nay để đi sinh nhật có kịp ko?"
  example_good_reply: "Dạ bên em có các mẫu sẵn tại shop giao hỏa tốc được ạ. Em xin phép kết nối chuyên viên hỗ trợ ship nhanh cho mình liền nha!"
```

---

## 5. Hướng Dẫn Dry-Run (CLI Testing)

Chạy thử nghiệm hệ thống mà **không gửi tin nhắn ra Zernio**, ghi nhận event dưới nguồn `dry_run` (không làm ô nhiễm bảng metrics live của Dashboard):

```bash
# Thử nghiệm hỏi giá trên Instagram comment:
python -m src.cli --text "Mẫu nhẫn hoa này giá bao nhiêu bạn ơi" --platform ig --surface comment

# Thử nghiệm hỏi chất liệu trên TikTok comment:
python -m src.cli --text "Sản phẩm này làm bằng chất liệu gì vậy shop" --platform tiktok --surface comment

# Thử nghiệm trường hợp khiếu nại (Edge Case):
python -m src.cli --text "Shop làm ăn lừa đảo hàng bị hỏng đòi hoàn tiền" --platform fb --surface dm
```

Kết quả hiển thị trên terminal:
- Nền tảng, Channel, Surface
- Sản phẩm khớp (hoặc cảnh báo trùng lặp alias)
- Intent phân loại
- Rule / Edge Case khớp
- Danh sách file kiến thức & dữ kiện đã nạp
- Quyết định (`auto_reply` / `fallback` / `escalate`)
- Cờ `flag` (`auto_reply` / `handover`) và trạng thái `needs_human`
- Bản thảo câu trả lời (`draft_reply`)

---

## 6. Ops Dashboard & Handover Console

Khởi động máy chủ Webhook và Dashboard:
```bash
uvicorn src.web.app:app --host 0.0.0.0 --port 8000 --reload
```

Truy cập Dashboard tại trình duyệt: **`http://localhost:8000/`**

### Các tính năng trên Dashboard:
1. **Tab Meta**:
   - Lọc theo platform: `Tất cả` | `Instagram (IG)` | `Facebook (FB)`.
   - Hiển thị đầy đủ 6 chỉ số live: `inbound_count`, `auto_replied_count`, `handover_open_count`, `resolved_count`, `fallback_count`, và bảng `Top Matched Rules`.
   - Hiển thị thời điểm sự kiện cuối `last_event_at`.
2. **Tab TikTok**:
   - Thống kê độc lập toàn bộ chỉ số của luồng TikTok.
3. **Tab Handover (Hàng đợi chuyển giao nhân viên)**:
   - Hiển thị badge số lượng ca đang mở: **chỉ tính `open` + `claimed`**.
   - Chi tiết từng ca: Kênh, Platform, Surface, Nội dung tin nhắn khách, Sản phẩm & Rule khớp, Lý do escalate, Draft reply.
   - Thao tác nhân viên: **Nhận xử lý (`claimed`)**, **Chờ tin (`waiting_on_us`)**, **Hoàn tất (`resolved`)**. Thao tác hoàn tất ghi nhận sự kiện thực vào cơ sở dữ liệu (không tự động resolve).
4. **Cập nhật Live theo thời gian thực**:
   - Sử dụng **Server-Sent Events (SSE)** tại `/api/events/stream` giúp cập nhật dữ liệu tự động ngay khi có tin nhắn mới hoặc ca handover được xử lý mà không cần tải lại trang.
5. **Quy tắc hiển thị dữ liệu**:
   - Chỉ lọc dữ liệu `env=prod` và `source=live`. Các ca test hoặc dry-run hoàn toàn bị loại trừ khỏi bảng điều khiển.
   - Nếu chưa có dữ liệu live, hiển thị chuẩn xác số `0` hoặc câu thông báo: `"Chưa có event live. Case test và dry-run không hiện ở đây."` (không bịa số liệu hay biểu đồ ảo).

---

## 7. Cấu Hình Webhook Zernio

Để nhận sự kiện comment và inbox từ Zernio:
- **Webhook Endpoint**: `POST https://your-domain.com/webhooks/zernio`
- **Xác thực chữ ký**: Xác thực `HMAC-SHA256` qua header `X-Zernio-Signature` (hoặc `X-Webhook-Signature`). Bắt buộc phải đặt `ZERNIO_WEBHOOK_SECRET`; nếu để trống, mọi request tới webhook đều bị từ chối.
- **Idempotency**: Tự động lọc trùng lặp theo `event.id` và `message.id`.

---

## 8. Chạy Bộ Kiểm Thử (Unit & Integration Tests)

Hệ thống đi kèm bộ test toàn diện đáp ứng đầy đủ 9 yêu cầu nghiệp vụ bắt buộc:
```bash
python -m pytest tests/test_auto_reply.py -v
```

### Danh mục kiểm thử:
- `test_missing_price_does_not_invent_a_number`: Thiếu giá trong catalogue không được bịa số tiền, chuyển sang fallback + handover.
- `test_meta_rule_does_not_fire_on_tiktok`: Rule của kênh Meta không bao giờ kích hoạt trên kênh TikTok.
- `test_edge_case_beats_a_general_rule`: Edge case luôn ưu tiên cao hơn rule thông thường.
- `test_empty_knowledge_returns_fallback_and_handover`: File kiến thức rỗng kích hoạt fallback + handover; `reply_sent=False` khi `HOLD_ON_HANDOVER=true`.
- `test_two_product_aliases_match_no_guessed_product`: Khi có 2 sản phẩm trùng từ khóa, không được đoán mò.
- `test_example_delete_me_never_appears_in_reply`: Nội dung trong các khối `EXAMPLE_DELETE_ME` không bao giờ xuất hiện trong câu trả lời.
- `test_dry_run_does_not_increase_dashboard_reply_count`: Chạy dry-run không làm tăng chỉ số `auto_replied_count` trên Dashboard.
- `test_test_handover_does_not_appear_on_handover_tab`: Dữ liệu test/dry-run không hiển thị trên danh sách hàng đợi Handover.
- `test_auto_send_false_never_calls_zernio_send`: Khi `AUTO_SEND=false`, hệ thống tuyệt đối không thực hiện gửi tin ra Zernio.
