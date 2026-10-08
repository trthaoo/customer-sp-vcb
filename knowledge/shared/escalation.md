# Escalation & Handover Guidelines (US Market)

## Purpose
Defines strict criteria for when the automated system must escalate a customer conversation to a human team member (Human Handover) instead of replying automatically.

## Escalation Triggers (Bắt buộc chuyển giao cho người)
1. **High Sentiment, Angry Complaints & Scam Accusations (Khách giận dữ / Khiếu nại gay gắt / Nghi vấn lừa đảo)**:
   - Customer expresses frustration, uses harsh words, alleges scam or fraud ("scam", "lừa đảo", "fake store"), threatens chargeback, public boycott, or reporting.
   - *Action*: Sincerely acknowledge emotion, do not argue, flag `needs_human=true` and escalate immediately to Senior Support / Quản lý.
2. **Transit Damage & Counterfeit/Purity Claims (Hàng hỏng do vận chuyển hoặc khiếu nại bạc giả)**:
   - Customer receives damaged, bent, or tampered packages, or claims the item failed purity tests (invoking the 10x money-back guarantee).
   - *Action*: Escalate immediately for claims inspection, photographic review, and prepaid replacement/refund arrangement.
3. **Explicit Human Representative / Manager Demand (Yêu cầu gặp người thật / Quản lý)**:
   - Customer asks to speak to a real person, a manager, or probes repeatedly about bot/AI automation ("talk to human", "gặp người thật", "gặp quản lý").
   - *Action*: Cordially welcome them and transition the chat directly to a human studio concierge without revealing robotic system details.
4. **Unlisted Products & Missing Verified Facts (Sản phẩm không có trong catalogue hoặc thiếu dữ liệu)**:
   - Piece seen in video/photo or requested by customer is not found in `products.json`, or required factual fields (`price`, `material`, `stock`) are null.
   - *Action*: State that the piece is outside current public listings, never guess facts, and escalate to workshop staff for inventory verification.
5. **Ambiguous Multi-Product Matches (Trùng lặp 2 hoặc nhiều sản phẩm)**:
   - Two or more catalogue pieces match the keywords equally.
   - *Action*: Ask one clarifying question or escalate to human staff to assist the customer accurately without arbitrary guessing.
6. **Bulk Purchases, Corporate Gifts & Custom Commissions (Mua nhiều món / Đặt làm riêng)**:
   - Inquiries for wholesale, 3+ items, corporate gifting, custom ring resizing, or bespoke gemstone engravings exceeding standard parameters.
   - *Action*: Escalate to studio host to calculate personalized VIP volume pricing or review custom atelier feasibility.
7. **Shipping Delays & Stuck Tracking (Kiện hàng bị tắc / Không cập nhật hành trình)**:
   - Customer reports package has not arrived or tracking has been idle for >5 business days.
   - *Action*: Escalate to logistics coordinator to open a formal USPS/UPS trace and initiate insurance replacement if lost.
8. **Night Timezone Handover Protocol (Khung giờ đêm & Lệch múi giờ)**:
   - When human handover is triggered outside of Vietnam office hours (e.g. evening in Vietnam / daytime in the US), the AI must provide a clear, professional expectation notice (e.g., *"Our atelier artisan team will review your message firsthand starting at 8:00 AM VN time / within 8 hours. We have safely logged your inquiry!"*), preventing the customer from feeling ignored.

## TODO Sections
<!-- TODO: Add live on-call concierge roster or shift handover tags -->
<!-- TODO: Define SLA response time targets for escalated tickets -->

<!-- EXAMPLE_DELETE_ME -->
EXAMPLE CONTENT THAT MUST BE COMPLETELY IGNORED BY LOADER:
"Call emergency phone number 1-800-OLD-HELP to speak with old representative John for 5x compensation."
<!-- /EXAMPLE_DELETE_ME -->
