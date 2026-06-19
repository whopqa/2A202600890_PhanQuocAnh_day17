# Bonus Challenge: Vietnamese E-commerce CSKH Flywheel

## Bối cảnh vấn đề

Bài toán thực tế mình chọn là flywheel dữ liệu cho chatbot chăm sóc khách hàng của một sàn thương mại điện tử Việt Nam. Chatbot này chủ yếu trả lời các câu hỏi lặp đi lặp lại như "đơn hàng đang ở đâu", "đổi trả trong bao lâu", "bảo hành gadget thế nào", hoặc "sprocket đã mở có trả được không". Đây là một problem hợp lý vì repo hiện tại đã có đúng các primitive cần thiết để mô phỏng vòng lặp đó: `flywheel.py` tạo eval set và preference pairs từ agent traces, `pipeline/features.py` minh hoạ point-in-time safety bằng `ASOF`, `kg_demo.py` minh hoạ multihop retrieval, và `bonus/prototype_demo.py` cho thấy vì sao decontamination phải hiểu tiếng Việt tốt hơn exact match.

Điểm quan trọng là traffic CSKH tiếng Việt rất "templatic": cùng một intent có thể xuất hiện dưới nhiều biến thể như có dấu, không dấu, thêm số đơn, thêm từ lịch sự, hoặc đổi nhẹ wording. Repo này đã cho một tín hiệu rất rõ: từ 8 traces ban đầu, pipeline hiện tạo ra `2` eval rows, `3` raw preference pairs, rồi chỉ còn `1` clean pair sau decontamination. Nghĩa là nếu chúng ta làm sai bước chống overlap giữa train và eval, hệ thống vẫn "chạy", vẫn ra file JSONL, nhưng chất lượng offline sẽ bị nói dối.

## Kiến trúc được chọn

```text
Vietnamese CS chatbot
        |
        v
  Agent traces / spans
        |
        v
 Bronze trace landing  -----> Per-trace analyst summary
        |
        +-----> Eval holdout (successful traces only)
        |
        +-----> Raw preference pairs (ok vs error turns)
                         |
                         v
              VN-aware decontamination
                         |
                         v
                Clean training pairs
                         ^
                         |
 Orders/events --> PIT features via ASOF JOIN
                         |
                         v
             Offline eval + future training
```

Kiến trúc này cố ý giữ hai lane riêng như repo đang làm: lane trace/dataset cho flywheel, và lane event/feature cho point-in-time correctness. Mình không đề xuất một hệ thống "all-in-one" mới, vì bonus nên là phần mở rộng tự nhiên của repo chứ không phải kiến trúc khác hẳn.

## Open Questions and Decisions

### 1. Nên ingest trace theo real-time stream hay batch export mỗi ngày?

Tradeoff:
- Streaming cho độ tươi tốt hơn, có thể phát hiện lỗi chatbot sớm hơn trong ngày.
- Batch rẻ hơn, dễ vận hành hơn, và hợp với quy mô bài lab hiện tại.

Decision: chọn **batch export theo đợt**, ví dụ nightly hoặc vài lần mỗi ngày.

Lý do chọn: với CSKH tiếng Việt của e-commerce, phần lớn intent như hỏi trạng thái đơn, đổi trả, bảo hành không cần retrain từng phút. Cost vận hành của stream processing, state management, và alerting phức tạp hơn giá trị nhận được ở giai đoạn đầu. Repo hiện tại cũng phản ánh hướng này: `flywheel.py` là job có thể rerun idempotent để tái tạo artifact. Mình chỉ giữ streaming cho telemetry hoặc observability, chưa dùng làm cổng tạo dataset train/eval.

### 2. Eval set nên lấy toàn bộ câu hỏi thành công, hay giữ holdout thật nhỏ nhưng sạch?

Tradeoff:
- Giữ nhiều eval rows hơn giúp coverage tốt hơn.
- Giữ holdout nhỏ nhưng sạch giúp offline metric đáng tin, nhất là khi traffic có nhiều prompt gần giống nhau.

Decision: chọn **holdout nhỏ nhưng sạch**, ưu tiên trustworthiness hơn số lượng.

Lý do chọn: repo đang cho kết quả thực là `2 eval rows`. Con số này nhỏ, nhưng lại phù hợp để minh hoạ nguyên tắc: eval phải là phần không bị train chạm vào. Nếu greedily giữ thật nhiều prompt trong train lẫn eval, ta sẽ tự poison benchmark. Với traffic tiếng Việt, cùng một ý định "đơn hàng đâu rồi" có thể lặp rất nhiều lần; vì vậy một eval nhỏ nhưng chống overlap tốt đáng giá hơn một eval lớn nhưng contaminated.

### 3. Decontamination nên exact-match, VN-normalized heuristic, hay embedding similarity?

Tradeoff:
- Exact match rẻ và dễ giải thích, nhưng bỏ sót rewrite không dấu hoặc đổi dấu câu.
- VN-normalized heuristic vẫn rẻ, deterministic, và bắt được nhiều biến thể support phổ biến.
- Embedding similarity mạnh hơn nữa nhưng tốn chi phí, khó set threshold, và dễ false positive.

Decision: chọn **VN-normalized heuristic trước**, exact match làm fallback nền.

Lý do chọn: `bonus/prototype_demo.py` đã cho evidence rõ ràng. Exact match còn giữ `2` pairs, còn VN-normalized chỉ giữ `1` pair. Với support tiếng Việt, bỏ dấu là hành vi rất phổ biến trên mobile hoặc khi user gõ nhanh. Vì vậy quyết định này grounded trực tiếp vào traffic tiếng Việt, không phải một "nice to have". Đồng thời heuristic này vẫn có failure semantics tốt: deterministic, rerun ra cùng kết quả, dễ audit khi analyst hỏi "vì sao pair này bị drop?".

### 4. Khi trace malformed hoặc schema sai, nên fail whole run hay quarantine rồi chạy tiếp?

Tradeoff:
- Fail fast giữ dataset sạch tuyệt đối nhưng dễ làm pipeline ngừng hoàn toàn.
- Quarantine giữ được phần dữ liệu tốt, nhưng cần theo dõi để không bỏ quên drift.

Decision: chọn **quarantine bad records và giữ raw append-only**.

Lý do chọn: repo đang đi đúng hướng này trong `pipeline/validate.py` và `verify.py`, với `3` quarantined bad records được check rõ ràng. Với chatbot production, điều nguy hiểm không phải chỉ là dữ liệu bẩn; còn là việc hệ thống im lặng bỏ sót hoặc sửa ngầm input. Quarantine cho phép team vừa tiếp tục tạo artifact từ phần data sạch, vừa giữ bằng chứng để debug upstream issue. Failure semantic ở đây là "partial success with explicit bad sink", phù hợp hơn "all or nothing".

### 5. Feature store cho training rows nên join kiểu latest snapshot hay point-in-time guard?

Tradeoff:
- Latest snapshot dễ viết SQL hơn, ít bảng hơn.
- Point-in-time join đòi hỏi lịch sử feature, nhưng tránh leak tương lai.

Decision: chọn **point-in-time bằng `ASOF JOIN`**.

Lý do chọn: repo đã có example leak rất cụ thể. Với user `u100`, event ngày `2026-06-01 10:00:00` chỉ nên thấy `spend_at_event = 50.0`, nhưng naive join lại đưa `spend_leaky = 300.0`. Trong e-commerce CSKH, feature như `lifetime_spend`, `refund_count`, hoặc "đã escalated chưa" đều rất nguy hiểm nếu lấy giá trị ở tương lai. Offline model sẽ tưởng nó dự đoán tốt, nhưng thật ra đang đọc đáp án từ tương lai. Đây là kiểu lỗi phá production quietly nhất vì pipeline vẫn sinh ra dataframe "đẹp".

### 6. Với retrieval cho policy/support docs, nên chỉ dùng vector chunks hay thêm knowledge graph cho một số câu hỏi?

Tradeoff:
- Flat chunk retrieval rẻ và đủ cho câu hỏi một fact.
- Knowledge graph tốn công extract triples và maintain schema hơn, nhưng mạnh ở multihop reasoning.

Decision: chọn **hybrid, nhưng KG chỉ cho nhóm câu hỏi cần nối fact**.

Lý do chọn: `kg_demo.py` cho ví dụ rất thuyết phục. Câu "Where does a widget ship from?" không có một chunk đơn nào chứa cả hai fact, nhưng graph đi được `widget -> accessory -> hanoi fulfillment center` trong `2` hops. Ngược lại, câu trực tiếp như "widget return window là bao lâu?" thì graph là overkill; chunk hoặc structured policy lookup là đủ. Vì vậy không nên thần thánh hoá KG cho mọi truy vấn support.

## Rejected Alternative

Một phương án mình **không chọn** là chạy embedding-similarity decontamination trên mọi run rồi drop tất cả prompt gần giống eval theo cosine threshold. Lý do từ chối:

- Chi phí inference/embedding cao hơn nhiều so với exact + VN-normalized heuristic.
- Threshold tuning khó, dễ drop nhầm các prompt support hợp lệ nhưng khác intent.
- Trong repo hiện tại, evidence chưa cho thấy exact + Vietnamese normalization đã bị exhausted.

Nói ngắn gọn: đây là hướng có thể làm ở phase sau, nhưng quá nặng cho một flywheel đầu tiên cần rẻ, audit được, và reproducible.

## Kết luận

Thiết kế phù hợp nhất cho repo này là một flywheel CSKH Việt Nam theo batch, có eval holdout nhỏ nhưng sạch, decontamination hiểu biến thể tiếng Việt, feature join theo point-in-time, và KG chỉ dùng cho truy vấn multihop thật sự. Quyết định quan trọng nhất là chống leakage theo ngữ cảnh tiếng Việt: repo đã cho thấy exact overlap detection là chưa đủ, còn prototype VN-aware có thể bắt được trường hợp rewrite mà exact match bỏ sót. Điều đó giúp offline eval trung thực hơn, dù phải chấp nhận hy sinh một số training pairs và giữ hệ thống đơn giản hơn so với embedding-heavy alternatives.
