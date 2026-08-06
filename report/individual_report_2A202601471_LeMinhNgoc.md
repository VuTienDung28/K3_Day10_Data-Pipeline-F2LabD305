# Báo cáo cá nhân — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Lê Minh Ngọc |
| MSSV | 2A202601471 |
| Khóa/Lớp | K3 |
| Tên nhóm | F2-LabD305 |
| Vai trò chính | Thành viên 4 — Corruption & Repair Owner |
| Repository | <https://github.com/VuTienDung28/K3_Day10_Data-Pipeline-F2LabD305> |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Mô phỏng data corruption | `src/ingestion/corruption.py` — `corrupt_clean_dataframe()` | Clean DataFrame theo clean schema | Corrupted DataFrame và JSON corruption log | Hoàn thành |
| Kiểm thử corruption | `tests/test_corruption.py` | DataFrame sạch giả lập và DataFrame sai schema | Kết quả kiểm thử tính tái lập, audit, không mutation và schema validation | Hoàn thành |
| Contract tích hợp | Chữ ký hàm và cấu trúc log | `clean_df`, `settings.paths.corruption_log` | Đầu vào cho `corruption_flow.py` của thành viên 5 | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Kiểm tra tương thích với quality/freshness signals | Observability (`quality.py`) | Thiết kế marker và mức phá để có thể phát hiện duplicate, summary rỗng/nhiễu, title ngắn và dữ liệu stale |
| Hướng dẫn tích hợp | Integration (`corruption_flow.py`) | Bàn giao cách gọi hàm, log path và yêu cầu repair lại từ raw records |

Tôi không nhận ownership cho `phase1.py` hoặc `corruption_flow.py`; hai module điều phối này thuộc thành viên 5.

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Xây dựng sáu kịch bản corruption | `src/ingestion/corruption.py` | Drop latest record, blank summary, inject noise, truncate title, stale date và duplicate record | Đọc `counts_by_type` trong corruption log |
| Bảo đảm reproducibility | `CORRUPTION_SEED = 42`, `CORRUPTION_RATE = 0.10` | Cùng input sinh cùng corrupted DataFrame | Chạy hàm hai lần và dùng `assert_frame_equal` |
| Bảo vệ baseline | `df.copy(deep=True)` | Không sửa DataFrame đầu vào | So sánh input trước/sau trong unit test |
| Giữ derived-field contract | `_rebuild_embedding_text()` | Dựng lại `text_for_embedding` sau khi title/summary thay đổi | Kiểm tra title và summary hiện tại đều có trong embedding text |
| Tạo audit trail | `corruption_log.json` payload | Có schema version, timestamp, seed, input/output rows, tổng event, count theo loại và before/after | Đọc JSON log trong unit test |
| Kiểm tra schema đầu vào | `_REQUIRED_COLUMNS` | Báo `ValueError` rõ ràng nếu thiếu cột | `test_corruption_rejects_data_outside_clean_contract` |

Trên fixture 20 dòng của test, tỷ lệ 10% làm mỗi kịch bản tác động 2 bản ghi. Hai bản ghi mới nhất bị xóa và hai dòng khác được duplicate nên output vẫn có 20 dòng. Trường hợp này cố ý chứng minh rằng row count có thể không thay đổi dù dữ liệu đã mất và bị trùng.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Pipeline cần một corrupted dataset đủ thực tế để đo tác động của chất lượng dữ liệu lên RAG. Việc phá phải có kiểm soát, tái lập được, không làm hỏng baseline và phải để lại bằng chứng cho biết bản ghi nào đã bị tác động.

### Cách triển khai

Hàm nhận một clean DataFrame rồi kiểm tra các cột bắt buộc. Hàm tạo deep copy trước khi xử lý. Số dòng tác động của mỗi kịch bản được tính bằng `ceil(row_count * 10%)`, tối thiểu một dòng khi input không rỗng.

Các bản ghi mới nhất được xác định bằng cách sắp xếp `published` giảm dần rồi loại khỏi corrupted dataset. Các dòng còn lại được xáo bằng seed 42 và chia theo offset cho năm nhóm mutation tiếp theo. Cách này giảm thiên lệch do thứ tự nguồn và tạo kết quả ổn định giữa các lần chạy.

Sáu kịch bản gồm:

1. `drop_latest_record`: mô phỏng incremental load bị thiếu dữ liệu mới.
2. `blank_summary`: mô phỏng lỗi mapping làm mất abstract.
3. `inject_summary_noise`: chèn `[CORRUPTED_NOISE] noise_token` để mô phỏng dữ liệu scraping/encoding bẩn.
4. `truncate_title`: cắt title còn 8 ký tự, thấp hơn ngưỡng kiểm tra 15 ký tự.
5. `stale_published_date`: lùi ngày xuất bản 3.650 ngày và tính lại `age_days`.
6. `duplicate_record`: mô phỏng cơ chế at-least-once load không có deduplication.

Sau mutation, `text_for_embedding` được dựng lại theo dạng `Title | Authors | Summary`. Vì vậy index downstream nhận đúng nội dung corrupted hiện tại, thay vì nhận một derived field cũ không đồng bộ.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `pandas.DataFrame` có `paper_id`, `title`, `summary`, `published`, `age_days`, `authors_joined`, `text_for_embedding` |
| Tham số log | Đường dẫn file JSON, thường là `settings.paths.corruption_log` |
| Output | DataFrame mới, giữ schema clean nhưng chứa các lỗi mô phỏng |
| Log output | JSON có `schema_version`, `generated_at`, `seed`, `corruption_rate`, row counts, event counts và danh sách before/after |
| Module phụ thuộc | `pandas`, `core.utils.write_json` |
| Module sử dụng output | `src/pipelines/corruption_flow.py`, retrieval index, evaluation và observability |
| Điều kiện lỗi | Thiếu cột clean schema sẽ dừng sớm bằng `ValueError`; input rỗng vẫn tạo log hợp lệ |

### Cách xác minh

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_corruption.py
```

- **Kết quả mong đợi:** Hai test pass; output có đủ sáu loại corruption, có log audit, tái lập được và input không đổi.
- **Kết quả thực tế:** `2 passed in 0.78s`.
- **Artifact/code:** `src/ingestion/corruption.py`, `tests/test_corruption.py`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần chọn cách tạo corrupted dataset có thể dùng để đánh giá công bằng và tái hiện trong buổi demo.
- **Các phương án đã cân nhắc:** Chọn dòng ngẫu nhiên không seed; chọn cố định các dòng đầu; hoặc dùng random order với seed cố định.
- **Phương án đã chọn:** Dùng `random_state=42` sau khi loại các bản ghi mới nhất.
- **Lý do:** Random order giảm phụ thuộc vào thứ tự input, còn seed cố định bảo đảm cùng input sinh cùng output. Điều này giúp so sánh baseline/corrupted/repaired có thể tái hiện.
- **Bằng chứng:** Unit test chạy corruption hai lần rồi xác nhận hai DataFrame bằng nhau hoàn toàn.

Một quyết định liên quan là rebuild `text_for_embedding` thay vì cố tình để field này không đồng bộ. Nhờ đó tác động retrieval đến từ nội dung bị phá thực sự, không phải do lỗi triển khai derived field ngoài kịch bản.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** DataFrame không đúng contract có thể gây `KeyError` tại một bước mutation bất kỳ, khiến nguyên nhân khó xác định.
- **Bước tái hiện:** Truyền DataFrame chỉ có `paper_id` vào `corrupt_clean_dataframe()`.
- **Nguyên nhân gốc:** Module corruption phụ thuộc vào nhiều cột của clean schema nhưng input chưa được kiểm tra trước khi xử lý.
- **Cách xử lý:** Khai báo `_REQUIRED_COLUMNS`, tính danh sách cột thiếu và raise `ValueError` có đầy đủ tên cột.
- **Cách xác minh:** `test_corruption_rejects_data_outside_clean_contract` đã pass.
- **Điều học được:** Data contract nên được kiểm tra tại ranh giới module để lỗi xuất hiện sớm và có thông báo hữu ích.

Sau tích hợp, baseline và corruption flow đã chạy end-to-end. `corruption_log.json` ghi 18 events, gồm 3 events cho mỗi loại corruption; các metrics và quality/freshness artifacts của ba trạng thái đã được tạo để đối chiếu.

## 7. Hiểu biết về luồng end-to-end

Crossref trả raw response; ingestion parse thành danh sách paper records và lưu raw artifact. Cleaning chuẩn hóa trường dữ liệu, loại record không hợp lệ, tính `age_days` và tạo `text_for_embedding`. Clean dataset được embedding bằng MiniLM và nạp vào ChromaDB. Evaluation set chứa câu hỏi, ground truth và `ground_truth_doc_ids`; retrieval hit rate được xác định bằng việc document ID đúng có xuất hiện trong top-k hay không, còn token F1/judge metrics đánh giá câu trả lời.

Quality checks kiểm tra schema, completeness, uniqueness, validity và consistency. Freshness tập trung vào tuổi dữ liệu theo `published` và ngưỡng ngày. Hai nhóm tín hiệu bổ sung cho nhau: dữ liệu có thể đúng schema nhưng đã quá cũ, hoặc còn mới nhưng bị thiếu/trùng/nhiễu.

Corrupted dataset phải được re-index và đánh giá bằng đúng test set của baseline để biến độc lập duy nhất là trạng thái dữ liệu. Repair không nên sửa ngược dựa trên corrupted rows mà phải build lại từ raw records đáng tin cậy. Repair chỉ được xem là thành công khi repaired quality/freshness phục hồi và metrics/answer artifacts được tạo lại trên cùng test set.

## 8. Phân tích kết quả

### Real-agent metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.5000 | 1.0000 | Ba trong sáu ground-truth documents bị drop; repair phục hồi ID coverage. |
| `mean_token_f1` | 0.3227 | 0.0893 | 0.2945 | Answer overlap giảm mạnh và repaired tiến gần baseline. |
| `judge_accuracy` | 1.0000 | 0.3333 | 1.0000 | LLM judge xác nhận suy giảm và phục hồi, không dùng fallback. |
| `mean_judge_score` | 5.0000 | 2.3333 | 5.0000 | Chênh lệch rõ giữa ba trạng thái. |
| Ragas context precision/recall | 0.6667/0.6667 | 0.1667/0.1667 | 0.6667/0.6667 | Retrieval-context quality giảm và phục hồi đúng kỳ vọng. |
| Quality checks | PASS | FAIL | PASS | Corrupted có 6 failed error checks; repaired có 0. |
| Freshness status | FRESH | STALE | FRESH | Ba record bị lùi 3.650 ngày làm corrupted stale. |

### Kết luận từ bằng chứng thực tế

`corruption_log.json` ghi 18 events: mỗi loại corruption tác động 3 record. Corrupted quality phát hiện 6 rows thuộc duplicate IDs, 3 title ngắn, 3 summary rỗng/ngắn, 3 summary có noise và 3 stale rows. Các signal này khớp trực tiếp với failure modes đã tạo trong module.

Trên cùng test set sáu samples, `drop_latest_record` loại ba ground-truth documents nên real-agent hit rate giảm từ 1.0 xuống 0.5; deterministic reference giảm từ 1.0 xuống 0.3333. Repair từ raw records và re-index phục hồi hit rate, judge metrics, Ragas context precision/recall, quality và freshness. Answer relevancy và faithfulness của Ragas có biến thiên giữa các LLM runs nên không được dùng riêng để tuyên bố recovery.

Một kết quả đáng chú ý là input và output đều có 24 dòng vì 3 dòng bị drop được bù bởi 3 dòng duplicate. `row_count` vẫn PASS trong khi uniqueness FAIL, chứng minh volume riêng lẻ không đủ phát hiện corruption; phải kết hợp document identity và quality dimensions.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Corruption có giá trị khi mô phỏng một failure mode có nguyên nhân, tín hiệu quan sát và tác động downstream rõ ràng.
2. Reproducibility và audit log là điều kiện cần để so sánh metrics công bằng, debug được và trình bày kết quả thuyết phục.
3. Data volume không đủ để kết luận corpus đầy đủ; mất record và duplicate có thể triệt tiêu nhau về row count nhưng vẫn làm RAG suy giảm.

### Nếu có thêm thời gian

Tôi sẽ bổ sung cấu hình riêng cho tỷ lệ từng loại corruption và lưu baseline fingerprint/document-ID diff vào log. Cải thiện này giúp đo trực tiếp precision/recall của corpus, phát hiện trường hợp row count không đổi nhưng identity đã sai, đồng thời cho phép chạy nhiều mức severity 5%, 10% và 20% để vẽ đường tác động lên retrieval metrics.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Các kết luận đã có đều dựa trên code hoặc test có thể đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần end-to-end chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không sao chép nguyên văn báo cáo nhóm hoặc báo cáo của thành viên khác.

**Họ và tên:** Lê Minh Ngọc  
**Ngày xác nhận:** 2026-08-06
