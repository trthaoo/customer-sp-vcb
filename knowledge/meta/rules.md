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
    contains_any: ["material", "silver", "sterling", "chất liệu", "bằng gì", "bạc", "kim loại"]
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
  reply_guide: "Send 2–3 short bubbles: 1) confirm availability directly (yes in stock and ready to ship, or currently being hand-finished by our craft team); 2) share estimated ready time; 3) want me to save one for your size? ✨"

- id: meta_ask_shipping_any
  channel: meta
  surface: any
  when:
    intent: ask_shipping
    contains_any: ["shipping", "delivery", "shipping fee", "how long to ship", "ship", "vận chuyển", "giao hàng", "phí ship", "bao lâu nhận"]
    product_required: false
  use_knowledge: ["policies.shipping"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) domestic US shipping is 100% free (included in price); 2) 2–5 business days for in-stock US warehouse pieces, ~2–3 weeks if traveling from our artisan craft studio (1–3 days prep); 3) what city or state are you ordering from? 🤍"

- id: meta_ask_payment_any
  channel: meta
  surface: any
  when:
    intent: ask_payment
    contains_any: ["payment", "pay", "paypal", "credit card", "apple pay", "google pay", "klarna", "installment", "cod", "cash on delivery", "thanh toán", "thẻ", "quẹt thẻ", "ship cod"]
    product_required: false
  use_knowledge: ["policies.payment"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) we currently process checkout securely via PayPal with full PayPal Buyer Protection; 2) no COD for insured US delivery; 3) if you need special payment handling, my craft team can assist you directly ✨"

- id: meta_ask_return_warranty_any
  channel: meta
  surface: any
  when:
    intent: ask_return_warranty
    contains_any: ["return", "exchange", "warranty", "refund", "đổi trả", "bảo hành", "hoàn tiền", "đổi size", "làm sáng"]
    product_required: false
  use_knowledge: ["policies.returns", "policies.warranty"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) free return/exchange within 8 days of receipt for initial crafting defects; 2) free 1-to-1 replacement for craft flaws and cancellations allowed before shipment; 3) feel free to DM us or reach order@huykjeweler.com anytime 🤍"

- id: meta_ask_silver_quality_any
  channel: meta
  surface: any
  when:
    intent: ask_silver_quality
    contains_any: ["real silver", "s925", "pure silver", "hallmark", "bạc thật không", "chất lượng bạc", "bạc chuẩn không"]
    product_required: false
  use_knowledge: ["policies.warranty"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) 100% solid S925 sterling silver with protective platinum plating; 2) stamped with official studio hallmark and backed by our 10x authenticity refund guarantee; 3) diamagnetic so it never sticks to a magnet ✨"

- id: meta_ask_tarnish_care_any
  channel: meta
  surface: any
  when:
    intent: ask_material
    contains_any: ["tarnish", "turn black", "turn green", "đen không", "gỉ không", "bị đen", "có bị đen không"]
    product_required: false
  use_knowledge: ["policies.warranty"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) solid S925 sterling silver finished with multi-layer platinum plating to resist tarnishing and stay skin-safe; 2) silver naturally interacts with body chemistry and sulfur (absorbing negative elements), but our platinum finish protects it for long-lasting daily wear; 3) includes lifetime polishing cloth and 1-to-1 replacement warranty! ✨ (Nếu là comment: QUY TẮC 1 < 15 từ: 'Solid S925 with platinum plating keeps it radiant! DM for care tips ✨')"

- id: meta_ask_custom_design_any
  channel: meta
  surface: any
  when:
    intent: request_custom
    contains_any: ["custom", "custom design", "chế tác", "làm theo mẫu", "đặt làm", "mẫu riêng", "custom jewelry", "make something similar", "theo yêu cầu", "thiết kế riêng"]
    product_required: false
  use_knowledge: ["catalogue.material"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) my craft team definitely takes custom orders; 2) we primarily craft in solid S925 silver and also custom-craft in 14K/18K solid yellow or white gold; 3) send over a photo or sketch of your idea and let's bring it to life! ✨ (Nếu là comment: QUY TẮC 1 < 15 từ: 'We do custom silver & gold! DM us your design or photo ✨')"

- id: meta_ask_size_general_any
  channel: meta
  surface: any
  when:
    intent: ask_size
    contains_any: ["size", "sizing", "measurement", "dimensions", "kích thước", "đo size", "vừa không", "chiều dài", "đường kính", "cỡ tay", "size tay"]
    product_required: false
  use_knowledge: ["catalogue.size_guide", "catalogue.variants"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) we craft standard US ring sizes from 4 to 12 directly for most pieces; 2) what size are you looking for, or would you like our quick 1-minute finger measurement guide? 3) feel free to share which piece you're eyeing! ✨ (Nếu là comment: QUY TẮC 1 < 15 từ: 'We craft standard US sizes 4 to 12! DM us your size ✨')"

- id: meta_ask_shipping_international_any
  channel: meta
  surface: any
  when:
    intent: ask_shipping
    contains_any: ["china", "international", "ship to", "quốc tế", "nước ngoài", "ở trung quốc", "在中国能买吗", "overseas", "global shipping", "ship abroad"]
    product_required: false
  use_knowledge: ["policies.shipping"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) we primarily offer complimentary free shipping across the US; 2) for international destinations (including Asia/China/Europe), my craft team can arrange dedicated insured international courier shipping; 3) DM us your exact delivery address and we will confirm international transit options right away! ✨ (Nếu là comment: QUY TẮC 1 < 15 từ: 'We do US & international shipping! DM us your location ✨')"

- id: meta_ask_catalogue_website_any
  channel: meta
  surface: any
  when:
    intent: ask_order
    contains_any: ["website", "see more designs", "web", "collection", "trang web", "xem thêm"]
    product_required: false
  use_knowledge: ["policies.payment", "catalogue.material"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) our full ready-to-wear collection is in our bio link, primarily crafted in solid S925 sterling silver; 2) for custom gold pieces (14K/18K) or bespoke designs, my craft team creates those upon special request; 3) drop us a DM anytime with ideas or pieces you'd like to explore! ✨ (Nếu là comment: QUY TẮC 1 < 15 từ: 'Bio link has solid silver; DM us for custom gold & bespoke designs ✨')"

- id: meta_ask_gold_material_any
  channel: meta
  surface: any
  when:
    intent: ask_material
    contains_any: ["in gold", "have this in gold", "yellow gold", "white gold", "bằng vàng", "có vàng không", "mạ vàng", "làm bằng vàng"]
    product_required: false
  use_knowledge: ["catalogue.material"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) our ready-to-wear pieces are solid S925 silver with platinum plating; 2) my craft team also crafts this piece in 14K/18K yellow or white gold upon custom request; 3) would you prefer yellow gold or white gold? ✨ (Nếu là comment: QUY TẮC 1 < 15 từ: 'We craft in solid S925 & custom 14K/18K gold! DM us for details ✨')"

- id: meta_ask_stones_any
  channel: meta
  surface: any
  when:
    intent: ask_material
    contains_any: ["what kind of stone", "kind of stone", "stones do you use", "diamonds", "diamond or moissanite", "đá gì", "kim cương", "đá moissanite", "loại đá"]
    product_required: false
  use_knowledge: ["catalogue.material"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) our ready-to-wear designs feature premium brilliant Moissanite for diamond-rivaling fire and everyday durability; 2) my craft team also crafts custom designs with lab or natural diamonds; 3) which design are you looking to create? 🤍 (Nếu là comment: QUY TẮC 1 < 15 từ: 'Set with brilliant Moissanite, custom diamonds available! DM us to explore ✨')"

- id: meta_ask_bulk_discount_any
  channel: meta
  surface: any
  when:
    intent: ask_bulk_discount
    contains_any: ["buy multiple", "bulk", "buy 2", "discount", "mua nhiều", "giảm giá", "bớt giá", "ưu đãi", "mua sỉ"]
    product_required: false
  use_knowledge: ["policies.promotions"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) love this! choosing 2+ pieces includes free US shipping, individual presentation boxes, and polishing cloths; 2) for 3+ pieces my craft team can set up a special bundle perk; 3) which designs are you looking to pair up? ✨"

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

- id: meta_ask_direct_order_any
  channel: meta
  surface: any
  when:
    intent: ask_order
    contains_any: ["order directly", "order from you", "buy directly", "mua trực tiếp", "đặt trực tiếp"]
    product_required: false
  use_knowledge: ["policies.shipping", "policies.payment"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) yes, you can order directly right here with us in DM or via our bio link; 2) includes complimentary free US shipping and secure PayPal checkout; 3) what design can I prepare for you? ✨ (Nếu là comment: QUY TẮC 1 < 15 từ: 'Yes, order directly right here in DM with free US shipping! ✨')"

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

- id: meta_ask_store_location_any
  channel: meta
  surface: any
  when:
    intent: ask_location
    contains_any: ["store address", "where is your store", "where is your jewelry made", "cửa hàng ở đâu", "địa chỉ", "made in", "where is it made"]
    product_required: false
  use_knowledge: ["policies.shipping", "policies.payment"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) our jewelry is handcrafted by designer Huy K's craft team; 2) domestic US orders ship directly from our US fulfillment center with insured 2–5 day delivery via USPS/UPS; 3) all online orders are protected by 100% PayPal Buyer Protection ✨ (Nếu là comment: QUY TẮC 1 < 15 từ: 'Handcrafted by Huy K craft team, insured 2-5 day US delivery via bio link ✨')"

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
