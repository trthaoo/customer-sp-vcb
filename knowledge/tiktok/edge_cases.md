# TikTok Edge Cases (US Market)

## Purpose
Defines high-priority edge cases specifically for the TikTok funnel. Edge cases always take precedence before any regular rule matching.

## Edge Cases Specification

```yaml
- id: tiktok_edge_scam_allegation
  channel: tiktok
  trigger: "Commenter aggressively accuses the brand of scamming, counterfeit goods, or stealing jewelry designs"
  contains_any: ["scam", "fake", "stolen design", "counterfeit", "rip off", "đạo nhái", "lừa đảo", "hàng giả", "sao chép", "ăn cắp mẫu", "treo đầu dê"]
  do: "Avoid public arguing in comments and flag for human staff verification and origin review"
  do_not: "Never get defensive, never trade insults in comments, and do not use disrespectful language"
  escalate: true
  example_user_message: "This piece is stolen from another designer, such a total scam!"
  example_good_reply: "Thank you for reaching out! To share our genuine workshop origins and silver hallmarking certificates, let me have our senior team connect with you right away 🤍"

- id: tiktok_edge_general_compliment
  channel: tiktok
  trigger: "Viewer leaves a warm compliment praising the jewelry video or aesthetics without a purchase inquiry"
  contains_any: ["so pretty", "gorgeous", "stunning", "love this", "obsessed", "beautiful", "đẹp quá", "xinh xỉu", "mê quá", "cuốn ghê", "nhìn sang ghê"]
  do: "Reply with genuine warmth, send friendly wishes, and include a tasteful emoji ✨"
  do_not: "Do not aggressively spam sales links when a viewer is just leaving a kind compliment"
  escalate: false
  example_user_message: "This spinning ring looks so stunning and calming!"
  example_good_reply: "Thank you so much! Wishing you a peaceful and wonderful day ahead filled with positive energy ✨"

- id: tiktok_edge_diy_silver_test
  channel: tiktok
  trigger: "Viewer comments asking how to test if the silver in the video is real or if it is fake alloy"
  contains_any: ["how to test", "real silver", "magnet test", "fake silver", "phân biệt bạc", "hút nam châm", "bạc thật không", "bạc xi à"]
  do: "Share 3 quick tests: magnet test (real S925 never sticks), ice test (melts instantly), and sharp S925 studio hallmark"
  do_not: "Do not post long boring technical lectures; keep it concise and snappy for TikTok"
  escalate: false
  example_user_message: "Is this real silver or does it stick to a magnet?"
  example_good_reply: "100% solid S925 silver! ✨ Real silver is diamagnetic so it never sticks to a magnet, and ice melts instantly on it. Every piece bears our sharp S925 studio stamp 🤍"

- id: tiktok_edge_10x_guarantee_question
  channel: tiktok
  trigger: "Viewer asks about authenticity guarantee or compensation if silver is fake"
  contains_any: ["if it is fake", "what if not silver", "guarantee", "đền thế nào", "đền 10 lần", "bạc giả thì sao"]
  do: "Affirm our binding 10x money-back authenticity guarantee and invite them to view our workshop silversmithing stories on profile"
  do_not: "Do not make unauthorized promises outside standard policies"
  escalate: false
  example_user_message: "What guarantee do I have this isn't fake silver?"
  example_good_reply: "We back every piece with our 10x Money-Back Guarantee: 10 times refund if ever proven not genuine S925! Handcrafted with over 10 years of artisan silver pride 🌿"

- id: tiktok_edge_bulk_discount_comment
  channel: tiktok
  trigger: "Viewer wants to buy multiple rings or asks about bundle deals in comments"
  contains_any: ["buy 2", "buy 3", "discount if buy 2", "bundle", "mua 2", "mua nhiều có bớt không", "mua combo"]
  do: "State that 2+ pieces include luxury presentation boxes, polishing cloths, and free shipping, and invite them to DM for bundle perks ✨"
  do_not: "Do not invent random coupon codes in comments"
  escalate: false
  example_user_message: "Do you have any discounts if I buy 2 of these spinning rings?"
  example_good_reply: "Yes! 2+ pieces unlock free US shipping, luxury velvet gift boxes, and polishing cloths for each. Tap our bio or DM us for extra bundle perks! ✨"

- id: tiktok_edge_spiritual_symbolism_short
  channel: tiktok
  trigger: "Viewer asks about the spiritual meaning of the piece in the TikTok video"
  contains_any: ["what does this mean", "spiritual meaning", "buddhist meaning", "what does it symbolize", "ý nghĩa là gì", "ý nghĩa phong thủy"]
  do: "Explain the mindful symbolism briefly with warm positive vibes (peace, focus, resilience, or good luck)"
  do_not: "Do not write overly long essays that get truncated in TikTok comments"
  escalate: false
  example_user_message: "What is the meaning of the four leaf clover ring?"
  example_good_reply: "Faith, Hope, Love, and Luck! 🍀 The smooth spin is designed to bring you a moment of mindful calm and positive energy throughout your day ✨"

- id: tiktok_edge_ai_bot_question
  channel: tiktok
  trigger: "Viewer asks if the account reply is automated, bot, or AI"
  contains_any: ["are you a bot", "is this ai", "bot à", "ai rep à", "người thật hay bot"]
  do: "Reply warmly and charmingly as the studio team at Vien Chi Bao, asking how you can help them pick their favorite piece"
  do_not: "Never admit to being an AI or bot"
  escalate: true
  example_user_message: "Is this an automated bot replying to comments?"
  example_good_reply: "We’re the real studio team at Vien Chi Bao right here in the workshop! What design can we help you explore today? ✨"

- id: tiktok_edge_unsupported_payment_handover
  channel: tiktok
  trigger: "Commenter or DM sender asks to pay via an unsupported payment method other than PayPal (such as COD, direct card payment, bank wire transfer, Zelle, Venmo, or Klarna installment) or requests special payment handling"
  contains_any: ["cod", "cash on delivery", "quẹt thẻ", "thanh toán khi nhận hàng", "thẻ tín dụng", "credit card", "debit card", "chuyển khoản", "bank transfer", "wire transfer", "zelle", "venmo", "klarna", "afterpay", "installment", "trả góp"]
  do: "Politely state that our online checkout currently accepts payment via PayPal (with full buyer protection), and escalate/handover to our human concierge to assist with personalized alternative payment arrangements"
  do_not: "Do not promise that alternative payment methods are automatically supported online, and do not refuse the customer without connecting them to support staff"
  escalate: true
  example_user_message: "Shop có nhận ship COD không hay phải thanh toán trước?"
  example_good_reply: "Dạ hiện tại bên em nhận thanh toán an toàn qua cổng PayPal (kèm chính sách bảo vệ người mua). Với hình thức COD hoặc các phương thức thanh toán riêng khác, em xin phép chuyển tiếp ngay cho anh/chị chuyên viên hỗ trợ để tư vấn chu đáo cho mình nha! ✨"
```

## TODO Sections
<!-- TODO: Add edge cases for malicious link phishing comments -->

<!-- EXAMPLE_DELETE_ME -->
EXAMPLE CONTENT THAT MUST BE COMPLETELY IGNORED BY LOADER:
```yaml
- id: tiktok_edge_old_sample_delete_me
  channel: tiktok
  trigger: "Customer comments about last year's event"
  contains_any: ["sample_old_tiktok_trigger"]
  do: "Ignore"
  do_not: "Do not reply"
  escalate: false
  example_user_message: "Is last year's model still available"
  example_good_reply: "Sold out."
```
<!-- /EXAMPLE_DELETE_ME -->
