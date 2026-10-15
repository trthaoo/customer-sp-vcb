# TikTok Reply Rules (US Market)

## Purpose
Defines automated response rules specifically for the TikTok funnel. These rules are isolated from the Meta funnel.

## QUY TẮC 1: PHẢN HỒI BÌNH LUẬN CÔNG KHAI (PUBLIC COMMENT REPLY)
- **Độ dài**: Bắt buộc dưới 15 từ (< 15 words).
- **BẢO MẬT GIÁ CẢ**: Tuyệt đối **KHÔNG BÁO GIÁ CÔNG KHAI**, không viết số tiền, không dùng ký hiệu `$`. Luôn điều hướng khách vào kiểm tra hộp thư riêng (DM/inbox) để xem báo giá và chi tiết độc quyền.

## QUY TẮC PHONG CÁCH: CẤM DẤU GẠCH NGANG EM-DASH (—)
- **CẤM DÙNG DẤU `—`**: Tuyệt đối không sử dụng dấu gạch ngang `—` (em-dash) trong bất kỳ phản hồi nào (cả comment lẫn DM). Dấu này mang phong cách AI nhân tạo rõ rệt. Dùng dấu phẩy `,`, dấu chấm, hoặc tách dòng tự nhiên.

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
    contains_any: ["material", "silver", "sterling", "titanium", "real silver", "chất liệu", "bằng gì", "bạc", "titan", "thật không"]
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
  reply_guide: "Send 2–3 short bubbles: 1) yes, ready to ship in stock (or currently being hand-finished by our craft team); 2) ships out with insured packaging; 3) want me to save one for your size? ✨"

- id: tiktok_ask_shipping_any
  channel: tiktok
  surface: any
  when:
    intent: ask_shipping
    contains_any: ["shipping", "delivery", "shipping fee", "ship to us", "ship", "vận chuyển", "giao hàng", "mấy ngày nhận"]
    product_required: false
  use_knowledge: ["policies.shipping"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) US shipping is 100% free; 2) 2–5 business days for in-stock US warehouse pieces, ~2–3 weeks if traveling from our artisan craft studio; 3) what state are you shopping from? 🤍"

- id: tiktok_ask_payment_any
  channel: tiktok
  surface: any
  when:
    intent: ask_payment
    contains_any: ["payment", "pay", "paypal", "credit card", "apple pay", "google pay", "klarna", "installment", "cod", "cash on delivery", "thanh toán", "thẻ", "quẹt thẻ", "ship cod"]
    product_required: false
  use_knowledge: ["policies.payment"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) we accept secure online payment via PayPal (with full PayPal Buyer Protection); 2) no COD for insured US delivery; 3) if you need a custom checkout arrangement, my craft team can help directly ✨"

- id: tiktok_ask_return_warranty_any
  channel: tiktok
  surface: any
  when:
    intent: ask_return_warranty
    contains_any: ["return", "exchange", "warranty", "refund", "đổi trả", "bảo hành", "hoàn tiền", "đổi size", "làm sáng", "stone fell out", "stone has fallen out"]
    product_required: false
  use_knowledge: ["policies.returns", "policies.warranty"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) so sorry for any frustrating experience or issue with your jewelry; 2) please send us a quick photo of the piece along with your order number so my craft team can inspect the condition right away; 3) for crafting or manufacturing flaws within warranty, we cover 100% free repair or 1-to-1 replacement! 🤍 (Nếu là comment: QUY TẮC 1 < 15 từ: 'So sorry! Please DM your order # and photos so we can help 🤍')"

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

- id: tiktok_ask_tarnish_care_any
  channel: tiktok
  surface: any
  when:
    intent: ask_material
    contains_any: ["tarnish", "turn black", "turn green", "đen không", "gỉ không", "bị đen", "có bị đen không"]
    product_required: false
  use_knowledge: ["policies.warranty"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) solid S925 sterling silver is hypoallergenic and completely skin-safe (will not turn your skin green); 2) silver naturally reacts with body chemistry (like salty sweat) and air sulfur over time, which causes natural surface oxidation; 3) keep it dry, wipe gently with a soft cloth, and store sealed when not wearing! ✨ (Nếu là comment: QUY TẮC 1 < 15 từ: 'Solid S925 is skin-safe! Wipe dry and store sealed to maintain shine ✨')"

- id: tiktok_ask_custom_design_any
  channel: tiktok
  surface: any
  when:
    intent: request_custom
    contains_any: ["custom", "custom design", "chế tác", "làm theo mẫu", "đặt làm", "mẫu riêng", "custom jewelry", "make something similar", "theo yêu cầu", "thiết kế riêng", "engrave", "engraving", "khắc tên"]
    product_required: false
  use_knowledge: ["catalogue.material"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) my craft team does custom crafting and engraving depending on the piece (plain bands/surfaces can be engraved, whereas delicate pave stones cannot); 2) which design or idea do you have in mind—plain band or stone-set, in silver or 14K/18K gold? 3) what is your approximate budget so we can give exact options? ✨ (Nếu là comment: QUY TẮC 1 < 15 từ: 'We do custom silver & gold! DM us your design or photo ✨')"

- id: tiktok_ask_size_general_any
  channel: tiktok
  surface: any
  when:
    intent: ask_size
    contains_any: ["size", "sizing", "measurement", "dimensions", "kích thước", "đo size", "vừa không", "chiều dài", "đường kính", "cỡ tay", "size tay", "measure my ring size"]
    product_required: false
  use_knowledge: ["catalogue.size_guide", "catalogue.variants"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) we craft standard US ring sizes from 4 to 12 directly for most pieces; 2) easiest way: wrap a thin strip of paper snug around your finger, mark where it overlaps, and measure the mm against a standard US size chart; 3) what size are you looking for? ✨ (DO NOT offer video guides) (Nếu là comment: QUY TẮC 1 < 15 từ: 'We craft standard US sizes 4 to 12! DM us your size ✨')"

- id: tiktok_ask_shipping_international_any
  channel: tiktok
  surface: any
  when:
    intent: ask_shipping
    contains_any: ["china", "international", "ship to", "quốc tế", "nước ngoài", "ở trung quốc", "在中国能买吗", "overseas", "global shipping", "ship abroad"]
    product_required: false
  use_knowledge: ["policies.shipping"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) we primarily offer complimentary free shipping across the US; 2) for international destinations (including Asia/China/Europe), my craft team can arrange dedicated insured international courier shipping; 3) DM us your exact delivery address and we will confirm international transit options right away! ✨ (Nếu là comment: QUY TẮC 1 < 15 từ: 'We do US & international shipping! DM us your location ✨')"

- id: tiktok_ask_catalogue_website_any
  channel: tiktok
  surface: any
  when:
    intent: ask_order
    contains_any: ["website", "see more designs", "web", "collection", "trang web", "xem thêm"]
    product_required: false
  use_knowledge: ["policies.payment", "catalogue.material"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) our full ready-to-wear collection is in our bio link, primarily crafted in solid S925 sterling silver; 2) for custom gold pieces (14K/18K) or bespoke designs, my craft team creates those upon special request; 3) drop us a DM anytime with ideas or pieces you'd like to explore! ✨ (Nếu là comment: QUY TẮC 1 < 15 từ: 'Bio link has solid silver; DM us for custom gold & bespoke designs ✨')"

- id: tiktok_ask_gold_material_any
  channel: tiktok
  surface: any
  when:
    intent: ask_material
    contains_any: ["in gold", "have this in gold", "yellow gold", "white gold", "bằng vàng", "có vàng không", "mạ vàng", "làm bằng vàng"]
    product_required: false
  use_knowledge: ["catalogue.material"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) our ready-to-wear pieces are solid S925 silver with platinum plating; 2) my craft team also crafts this piece in 14K/18K yellow or white gold upon custom request; 3) would you prefer yellow gold or white gold? ✨ (Nếu là comment: QUY TẮC 1 < 15 từ: 'We craft in solid S925 & custom 14K/18K gold! DM us for details ✨')"

- id: tiktok_ask_stones_any
  channel: tiktok
  surface: any
  when:
    intent: ask_material
    contains_any: ["what kind of stone", "kind of stone", "stones do you use", "diamonds", "diamond or moissanite", "đá gì", "kim cương", "đá moissanite", "loại đá"]
    product_required: false
  use_knowledge: ["catalogue.material"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) our ready-to-wear designs feature premium brilliant Moissanite for diamond-rivaling fire and everyday durability; 2) my craft team also crafts custom designs with lab or natural diamonds; 3) which design are you looking to create? 🤍 (Nếu là comment: QUY TẮC 1 < 15 từ: 'Set with brilliant Moissanite, custom diamonds available! DM us to explore ✨')"

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

- id: tiktok_ask_direct_order_any
  channel: tiktok
  surface: any
  when:
    intent: ask_order
    contains_any: ["order directly", "order from you", "buy directly", "mua trực tiếp", "đặt trực tiếp"]
    product_required: false
  use_knowledge: ["policies.shipping", "policies.payment"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) yes, you can order directly right here with us in DM or via our bio link; 2) includes complimentary free US shipping and secure PayPal checkout; 3) what design can I prepare for you? ✨ (Nếu là comment: QUY TẮC 1 < 15 từ: 'Yes, order directly right here in DM with free US shipping! ✨')"

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

- id: tiktok_ask_store_location_any
  channel: tiktok
  surface: any
  when:
    intent: ask_store_location
    contains_any: ["store address", "where is your store", "where is your jewelry made", "cửa hàng ở đâu", "địa chỉ", "made in", "where is it made", "address", "where is the studio", "showroom", "physical store", "do you have a store", "cửa hàng", "where are you located"]
    product_required: false
  use_knowledge: ["policies.shipping", "policies.payment"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) in the US, we operate 100% online with complimentary insured 2–5 day delivery via USPS/UPS and PayPal Buyer Protection; 2) our physical boutique showrooms and silversmithing studio are in Vietnam; 3) which piece would you like us to prepare for you? ✨ (Nếu là comment: QUY TẮC 1 < 15 từ: '100% online in the US with free shipping; physical stores in Vietnam ✨')"

- id: tiktok_ask_gift_promotions_any
  channel: tiktok
  surface: any
  when:
    intent: ask_gift_promotions
    contains_any: ["free gift", "free gifts", "gift included", "tặng quà", "quà kèm", "quà tặng", "có quà không", "promotional gift"]
    product_required: false
  use_knowledge: ["policies.shipping", "policies.payment"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) we currently do not have a policy for free gift items with purchase; 2) instead, every US order receives 100% complimentary free insured shipping; 3) which design are you eyeing? ✨ (Nếu là comment: QUY TẮC 1 < 15 từ: 'No free gifts, but 100% free US shipping on all orders! ✨')"

- id: tiktok_ask_price_comparison_any
  channel: tiktok
  surface: any
  when:
    intent: ask_price_comparison
    contains_any: ["half the price", "cheaper online", "other stores sell this for less", "why are your prices so high", "identical online", "identical to one", "why should i buy yours", "why should i buy", "rẻ hơn một nửa", "bên khác rẻ hơn", "sao đắt thế", "giá cao thế"]
    product_required: false
  use_knowledge: ["catalogue.material", "policies.warranty"]
  if_missing: escalate
  reply_guide: "Send 2–3 short bubbles: 1) hello and thank you so much for your interest in Huy K jewelry! 2) our pieces are made with certified solid S925 silver and genuine stones, individually handcrafted with meticulous detail—not cheap mass alloy; 3) which piece are you looking at so I can share exact details? ✨"

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
