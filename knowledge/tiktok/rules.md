# TikTok Reply Rules (US Market)

## Purpose
Defines automated response rules specifically for the TikTok funnel. These rules are isolated from the Meta funnel.

## QUY TẮC 1: PHẢN HỒI BÌNH LUẬN CÔNG KHAI (PUBLIC COMMENT REPLY)
- **Độ dài**: Bắt buộc dưới 15 từ (< 15 words).
- **BẢO MẬT GIÁ CẢ**: Tuyệt đối **KHÔNG BÁO GIÁ CÔNG KHAI**, không viết số tiền, không dùng ký hiệu `$`. Luôn điều hướng khách vào kiểm tra hộp thư riêng (DM/inbox) để xem báo giá và chi tiết độc quyền.

## Rules Specification

```yaml
- id: tiktok_ask_price_comment
  channel: tiktok
  surface: comment
  when:
    intent: ask_price
    contains_any: ["price", "how much", "cost", "giá", "nhiêu", "bao nhiêu", "tiền", "ib giá"]
    product_required: true
  use_knowledge: ["catalogue.price", "catalogue.currency"]
  if_missing: escalate
  reply_guide: "QUY TẮC 1 (< 15 từ): Tuyệt đối KHÔNG BÁO GIÁ CÔNG KHAI, không viết số tiền hay ký hiệu $. Luôn điều hướng khách check DM/inbox nhận giá và ưu đãi độc quyền ✨ (Ví dụ: 'mình nhắn giá qua inbox cho bạn rồi nha ✨' hoặc 'check your DM for exclusive pricing and details ✨')"

- id: tiktok_ask_price_dm
  channel: tiktok
  surface: dm
  when:
    intent: ask_price
    contains_any: ["price", "how much", "cost", "giá", "nhiêu", "bao nhiêu", "tiền"]
    product_required: true
  use_knowledge: ["catalogue.price", "catalogue.currency"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) it's the [piece name]; 2) currently $[price] with complimentary free US shipping; 3) what US ring size do you usually wear? ✨"

- id: tiktok_ask_material_any
  channel: tiktok
  surface: any
  when:
    intent: ask_material
    contains_any: ["material", "silver", "sterling", "gold", "titanium", "real silver", "chất liệu", "bằng gì", "bạc", "vàng", "titan", "thật không"]
    product_required: true
  use_knowledge: ["catalogue.material"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) not plated, it's solid S925 sterling silver with platinum plating; 2) holds up way better for everyday wear and won't turn your skin green; 3) want the care notes? 🤍"

- id: tiktok_ask_size_any
  channel: tiktok
  surface: any
  when:
    intent: ask_size
    contains_any: ["size", "sizing", "measurement", "fit", "size 7", "size 8", "kích thước", "đo size", "vừa không", "tay nhỏ"]
    product_required: true
  use_knowledge: ["catalogue.variants", "catalogue.size_guide"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) available in standard US sizes 5 through 11 (or dimensions); 2) fits super comfortable for all-day wear; 3) what size do you usually wear? ✨"

- id: tiktok_ask_stock_any
  channel: tiktok
  surface: any
  when:
    intent: ask_stock
    contains_any: ["in stock", "available", "sold out", "ready to ship", "còn hàng", "sẵn không", "hết hàng", "còn k", "sẵn ko"]
    product_required: true
  use_knowledge: ["catalogue.in_stock"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) yes, ready to ship in stock (or currently crafting in our atelier batch); 2) ships out with insured packaging; 3) want me to save one for your size? ✨"

- id: tiktok_ask_shipping_any
  channel: tiktok
  surface: any
  when:
    intent: ask_shipping
    contains_any: ["shipping", "delivery", "shipping fee", "ship to us", "ship", "vận chuyển", "giao hàng", "mấy ngày nhận"]
    product_required: false
  use_knowledge: ["policies.shipping"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) US shipping is 100% free; 2) 2–5 business days for in-stock US warehouse pieces, ~2–3 weeks if traveling from our overseas studio; 3) what state are you shopping from? 🤍"

- id: tiktok_ask_payment_any
  channel: tiktok
  surface: any
  when:
    intent: ask_payment
    contains_any: ["payment", "pay", "paypal", "credit card", "apple pay", "google pay", "klarna", "installment", "cod", "cash on delivery", "thanh toán", "thẻ", "quẹt thẻ", "ship cod"]
    product_required: false
  use_knowledge: ["policies.payment"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) we accept secure online payment via PayPal (with full PayPal Buyer Protection); 2) no COD for insured US delivery; 3) if you need a custom checkout arrangement, our team can help directly ✨"

- id: tiktok_ask_return_warranty_any
  channel: tiktok
  surface: any
  when:
    intent: ask_return_warranty
    contains_any: ["return", "exchange", "warranty", "refund", "đổi trả", "bảo hành", "hoàn tiền", "đổi size", "làm sáng"]
    product_required: false
  use_knowledge: ["policies.returns", "policies.warranty"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) free return/exchange within 8 days of receipt for initial workshop defects; 2) free replacement for crafting flaws, cancellations allowed before shipment; 3) drop us a DM or reach order@huykjeweler.com anytime 🤍"

- id: tiktok_ask_silver_quality_any
  channel: tiktok
  surface: any
  when:
    intent: ask_silver_quality
    contains_any: ["real silver", "s925", "pure silver", "hallmark", "bạc thật không", "chất lượng bạc", "bạc chuẩn không"]
    product_required: false
  use_knowledge: ["policies.warranty"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) 100% solid S925 sterling silver with protective platinum plating; 2) stamped with our studio hallmark and backed by our 10x authenticity refund guarantee; 3) diamagnetic so it never sticks to a magnet 🌿"

- id: tiktok_ask_bulk_discount_any
  channel: tiktok
  surface: any
  when:
    intent: ask_bulk_discount
    contains_any: ["buy multiple", "bulk", "buy 2", "discount", "mua nhiều", "giảm giá", "bớt giá", "ưu đãi", "mua sỉ"]
    product_required: false
  use_knowledge: ["policies.promotions"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) 2+ pieces include free US shipping, luxury gift boxes, and polishing cloths; 2) DM us for custom bundle perks on 3+ pieces; 3) which ones are you pairing up? ✨"

- id: tiktok_ask_order_dm
  channel: tiktok
  surface: dm
  when:
    intent: ask_order
    contains_any: ["buy", "order", "purchase", "how to buy", "how can i buy", "how to order", "where to buy", "want to buy", "mua", "đặt hàng", "mua thế nào", "chốt đơn"]
    product_required: true
  use_knowledge: ["catalogue.price", "catalogue.currency", "catalogue.variants", "policies.shipping", "policies.payment"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) it's the [piece name] at $[price] with complimentary free US shipping; 2) checkout is processed securely via PayPal Buyer Protection; 3) what US ring size would you like us to prepare for you? 🤍"

- id: tiktok_ask_order_comment
  channel: tiktok
  surface: comment
  when:
    intent: ask_order
    contains_any: ["buy", "order", "purchase", "how to buy", "how can i buy", "how to order", "where to buy", "want to buy", "mua", "đặt hàng", "mua thế nào", "chốt đơn"]
    product_required: true
  use_knowledge: ["catalogue.price", "catalogue.currency", "catalogue.variants", "policies.shipping"]
  if_missing: escalate
  reply_guide: "QUY TẮC 1 (< 15 từ): Tuyệt đối KHÔNG BÁO GIÁ CÔNG KHAI, không viết số tiền hay ký hiệu $. Điều hướng khách vào DM hoặc tap bio showcase để nhận báo giá và hướng dẫn đặt hàng ✨ (Ví dụ: 'check your DM or bio showcase for direct order link ✨')"

- id: tiktok_ask_order_general_dm
  channel: tiktok
  surface: dm
  when:
    intent: ask_order
    contains_any: ["buy", "order", "purchase", "how to buy", "how can i buy", "how to order", "where to buy", "want to buy", "mua", "đặt hàng", "mua thế nào"]
    product_required: false
  use_knowledge: ["policies.shipping", "policies.payment"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) all pieces include free US shipping and secure checkout via PayPal; 2) handcrafted in solid S925 sterling silver; 3) which design or stone do you have your eye on? ✨"

- id: tiktok_ask_photo_dm
  channel: tiktok
  surface: dm
  when:
    intent: ask_photo
    contains_any: ["photo", "pic", "pics", "picture", "image", "visual", "look like", "see it", "ảnh", "hình", "ảnh thật"]
    product_required: true
  use_knowledge: ["catalogue.material", "catalogue.price"]
  if_missing: escalate
  reply_guide: "Send 1–2 short bubbles: 1) here's a close-up look at the [piece name] in our studio lighting ✨; 2) shows the exact stone setting and double-latch clasp, want to check sizing? 🤍"
```

## TODO Sections
<!-- TODO: Add TikTok rules for LIVE stream flash giveaways -->

<!-- EXAMPLE_DELETE_ME -->
EXAMPLE CONTENT THAT MUST BE COMPLETELY IGNORED BY LOADER:
```yaml
- id: tiktok_rule_old_sample_delete_me
  channel: tiktok
  surface: comment
  when:
    intent: old_sample_intent
    contains_any: ["old_tiktok_keyword"]
    product_required: false
  use_knowledge: ["catalogue.price"]
  if_missing: escalate
  reply_guide: "Old TikTok sample reply."
```
<!-- /EXAMPLE_DELETE_ME -->
