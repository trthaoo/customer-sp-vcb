# Meta Reply Rules (US Market)

## Purpose
Defines automated response rules specifically for the Meta funnel (Instagram and Facebook). These rules are isolated from the TikTok funnel.

## QUY TẮC 1: PHẢN HỒI BÌNH LUẬN CÔNG KHAI (PUBLIC COMMENT REPLY)
- **Độ dài**: Bắt buộc dưới 15 từ (< 15 words).
- **BẢO MẬT GIÁ CẢ**: Tuyệt đối **KHÔNG BÁO GIÁ CÔNG KHAI**, không viết số tiền, không dùng ký hiệu `$`. Luôn điều hướng khách vào kiểm tra hộp thư riêng (DM/inbox) để xem báo giá và chi tiết độc quyền.

## QUY TẮC PHONG CÁCH: CẤM DẤU GẠCH NGANG EM-DASH (—)
- **CẤM DÙNG DẤU `—`**: Tuyệt đối không sử dụng dấu gạch ngang `—` (em-dash) trong bất kỳ phản hồi nào (cả comment lẫn DM). Dấu này mang phong cách AI nhân tạo rõ rệt. Dùng dấu phẩy `,`, dấu chấm, hoặc tách dòng tự nhiên.

## Rules Specification

```yaml
- id: meta_ask_price_dm
  channel: meta
  surface: dm
  when:
    intent: ask_price
    contains_any: ["price", "how much", "cost", "giá", "nhiêu", "bao nhiêu", "tiền"]
    product_required: true
  use_knowledge: ["catalogue.price", "catalogue.currency"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) it's the [piece name]; 2) currently $[price] with complimentary free US shipping; 3) what US ring size do you usually wear? ✨"

- id: meta_ask_price_comment
  channel: meta
  surface: comment
  when:
    intent: ask_price
    contains_any: ["price", "how much", "cost", "giá", "nhiêu", "bao nhiêu", "tiền"]
    product_required: true
  use_knowledge: ["catalogue.price", "catalogue.currency"]
  if_missing: escalate
  reply_guide: "QUY TẮC 1 (< 15 từ): Tuyệt đối KHÔNG BÁO GIÁ CÔNG KHAI, không viết số tiền hay ký hiệu $. Luôn hướng dẫn khách check DM/inbox nhận giá và ưu đãi độc quyền ✨ (Ví dụ: 'mình gửi giá và chi tiết qua inbox cho bạn rồi nha ✨' hoặc 'check your DM for exclusive pricing and details ✨')"

- id: meta_ask_material_any
  channel: meta
  surface: any
  when:
    intent: ask_material
    contains_any: ["material", "silver", "sterling", "gold", "chất liệu", "bằng gì", "vàng", "bạc", "kim loại"]
    product_required: true
  use_knowledge: ["catalogue.material"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) not plated, it's solid S925 sterling silver with protective platinum plating; 2) hypoallergenic, tarnish-resistant, and holds up way better for everyday wear; 3) want our quick silver care tips? 🤍"

- id: meta_ask_size_any
  channel: meta
  surface: any
  when:
    intent: ask_size
    contains_any: ["size", "sizing", "measurement", "dimensions", "kích thước", "đo size", "vừa không", "chiều dài", "đường kính"]
    product_required: true
  use_knowledge: ["catalogue.variants", "catalogue.size_guide"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) standard US ring sizes 5 through 11 (or dimensions); 2) explain how it sits comfortably; 3) what size do you usually wear or want our 1-minute sizing guide? ✨"

- id: meta_ask_stock_any
  channel: meta
  surface: any
  when:
    intent: ask_stock
    contains_any: ["in stock", "available", "sold out", "ready to ship", "còn hàng", "sẵn không", "hết hàng", "còn không"]
    product_required: true
  use_knowledge: ["catalogue.in_stock"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) confirm availability directly (yes in stock and ready to ship, or being crafted in current workshop batch); 2) share estimated ready time; 3) want me to save one for your size? ✨"

- id: meta_ask_shipping_any
  channel: meta
  surface: any
  when:
    intent: ask_shipping
    contains_any: ["shipping", "delivery", "shipping fee", "how long to ship", "ship", "vận chuyển", "giao hàng", "phí ship", "bao lâu nhận"]
    product_required: false
  use_knowledge: ["policies.shipping"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) domestic US shipping is 100% free (included in price); 2) 2–5 business days for in-stock US warehouse pieces, ~2–3 weeks if traveling from our artisan workshop (1–3 days prep); 3) what city or state are you ordering from? 🤍"

- id: meta_ask_payment_any
  channel: meta
  surface: any
  when:
    intent: ask_payment
    contains_any: ["payment", "pay", "paypal", "credit card", "apple pay", "google pay", "klarna", "installment", "cod", "cash on delivery", "thanh toán", "thẻ", "quẹt thẻ", "ship cod"]
    product_required: false
  use_knowledge: ["policies.payment"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) we currently process checkout securely via PayPal with full PayPal Buyer Protection; 2) no COD for insured US delivery; 3) if you need special payment handling, our concierge team can assist you directly ✨"

- id: meta_ask_return_warranty_any
  channel: meta
  surface: any
  when:
    intent: ask_return_warranty
    contains_any: ["return", "exchange", "warranty", "refund", "đổi trả", "bảo hành", "hoàn tiền", "đổi size", "làm sáng"]
    product_required: false
  use_knowledge: ["policies.returns", "policies.warranty"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) free return/exchange within 8 days of receipt for initial workshop defects; 2) free 1-to-1 replacement for craft flaws and cancellations allowed before shipment; 3) feel free to DM us or reach order@huykjeweler.com anytime 🤍"

- id: meta_ask_silver_quality_any
  channel: meta
  surface: any
  when:
    intent: ask_silver_quality
    contains_any: ["real silver", "s925", "pure silver", "hallmark", "bạc thật không", "chất lượng bạc", "bạc chuẩn không", "có bị đen không"]
    product_required: false
  use_knowledge: ["policies.warranty"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) 100% solid S925 sterling silver with protective platinum plating; 2) stamped with official studio hallmark and backed by our 10x authenticity refund guarantee; 3) diamagnetic so it never sticks to a magnet ✨"

- id: meta_ask_bulk_discount_any
  channel: meta
  surface: any
  when:
    intent: ask_bulk_discount
    contains_any: ["buy multiple", "bulk", "buy 2", "discount", "mua nhiều", "giảm giá", "bớt giá", "ưu đãi", "mua sỉ"]
    product_required: false
  use_knowledge: ["policies.promotions"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) love this! choosing 2+ pieces includes free US shipping, individual presentation boxes, and polishing cloths; 2) for 3+ pieces our concierge can set up a special bundle perk; 3) which designs are you looking to pair up? ✨"

- id: meta_ask_order_dm
  channel: meta
  surface: dm
  when:
    intent: ask_order
    contains_any: ["buy", "order", "purchase", "how to buy", "how can i buy", "how to order", "where to buy", "want to buy", "mua", "đặt hàng", "mua thế nào", "chốt đơn"]
    product_required: true
  use_knowledge: ["catalogue.price", "catalogue.currency", "catalogue.variants", "policies.shipping", "policies.payment"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) it's the [piece name] at $[price] with complimentary free US shipping; 2) secure checkout via PayPal Buyer Protection; 3) what US ring size would you like us to prepare for you? 🤍"

- id: meta_ask_order_comment
  channel: meta
  surface: comment
  when:
    intent: ask_order
    contains_any: ["buy", "order", "purchase", "how to buy", "how can i buy", "how to order", "where to buy", "want to buy", "mua", "đặt hàng", "mua thế nào", "chốt đơn"]
    product_required: true
  use_knowledge: ["catalogue.price", "catalogue.currency", "catalogue.variants", "policies.shipping"]
  if_missing: escalate
  reply_guide: "QUY TẮC 1 (< 15 từ): Tuyệt đối KHÔNG BÁO GIÁ CÔNG KHAI, không viết số tiền hay ký hiệu $. Hướng dẫn khách check DM hoặc bio link để nhận báo giá và hướng dẫn đặt hàng ✨ (Ví dụ: 'check your DM or bio link for direct order details ✨')"

- id: meta_ask_order_general_dm
  channel: meta
  surface: dm
  when:
    intent: ask_order
    contains_any: ["buy", "order", "purchase", "how to buy", "how can i buy", "how to order", "where to buy", "want to buy", "mua", "đặt hàng", "mua thế nào"]
    product_required: false
  use_knowledge: ["policies.shipping", "policies.payment"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) all pieces include free US shipping and secure checkout via PayPal; 2) handcrafted in solid S925 sterling silver; 3) which design or stone do you have your eye on? ✨"

- id: meta_ask_photo_dm
  channel: meta
  surface: dm
  when:
    intent: ask_photo
    contains_any: ["photo", "pic", "pics", "picture", "image", "visual", "look like", "see it", "ảnh", "hình", "ảnh thật"]
    product_required: true
  use_knowledge: ["catalogue.material", "catalogue.price"]
  if_missing: escalate
  reply_guide: "Send 1–2 short bubbles: 1) here's a close-up look at the [piece name] in our studio lighting ✨; 2) handcrafted in solid S925 sterling silver with secure setting, want to check wrist/ring sizing? 🤍"
```

## TODO Sections
<!-- TODO: Add Meta rules for seasonal Instagram story giveaway drops -->
<!-- TODO: Add VIP returning client personalized greeting rules -->

<!-- EXAMPLE_DELETE_ME -->
EXAMPLE CONTENT THAT MUST BE COMPLETELY IGNORED BY LOADER:
```yaml
- id: meta_rule_old_sample_example_delete_me
  channel: meta
  surface: comment
  when:
    intent: old_sample_intent
    contains_any: ["test_old_keyword"]
    product_required: false
  use_knowledge: ["catalogue.price"]
  if_missing: escalate
  reply_guide: "Old sample product priced at 123,456đ with free thermos bottle."
```
<!-- /EXAMPLE_DELETE_ME -->
