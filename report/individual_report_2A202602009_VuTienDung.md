# Báo cáo vai trò thành viên — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                                                         |
| --------------- | ---------------------------------------------------------------- |
| Họ và tên       | Vũ Tiến Dũng                                                     |
| MSSV            | 2A202602009                                                      |
| Khóa/Lớp        | K3                                                               |
| Tên nhóm        | F2-LabD305                                                       |
| Vai trò chính   | Nhóm trưởng, Source Ingestion                                    |
| Repository      | https://github.com/VuTienDung28/K3_Day10_Data-Pipeline-F2LabD305 |
| Ngày hoàn thành | 2026-08-06                                                       |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable        | File/hàm phụ trách                                    | Input nhận vào                                       | Output bàn giao                          | Trạng thái |
| ------------------------- | ----------------------------------------------------- | ---------------------------------------------------- | ---------------------------------------- | ---------- |
| Thu thập dữ liệu Crossref | `src/ingestion/crossref.py`: `fetch_source_records()` | Query, filter, số kết quả và đường dẫn từ `Settings` | `list[PaperRecord]` và hai raw artifacts | Hoàn thành |
| Parse dữ liệu nguồn       | `parse_crossref_payload()` và các helper              | JSON payload của Crossref                            | Records phẳng, đủ title và summary       | Hoàn thành |
| Retry và backoff          | `fetch_source_records()`                              | HTTP response/lỗi kết nối                            | Retry 429/503 có giới hạn                | Hoàn thành |
| Nạp raw snapshot          | `load_raw_records()`                                  | `crossref_records.json`                              | `list[PaperRecord]` cho downstream       | Hoàn thành |

Output của tôi là đầu vào trực tiếp cho cleaning của thành viên 2 và baseline pipeline của thành viên 5.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                        | Thành viên/module được hỗ trợ | Kết quả                                                                    |
| -------------------------------- | ----------------------------- | -------------------------------------------------------------------------- |
| Phối hợp với vai trò nhóm trưởng | Các thành viên                | Xác định ownership và contract bàn giao giữa các module                    |
| Kiểm tra contract dữ liệu        | Cleaning và integration       | Xác nhận records có đủ 11 trường của `PaperRecord` và nạp lại được từ JSON |

## 3. Kết quả theo vai trò

| Nhiệm vụ                       | File/hàm/artifact                 | Kết quả bàn giao                             | Cách xác minh            |
| ------------------------------ | --------------------------------- | -------------------------------------------- | ------------------------ |
| Gọi Crossref theo query/filter | `fetch_source_records()`          | Response từ `https://api.crossref.org/works` | Kiểm tra `message.query` |
| Lưu response nguồn             | `data/raw/crossref_response.json` | Payload Crossref gồm 24 items                | Đếm `message.items`      |
| Parse record hợp lệ            | `parse_crossref_payload()`        | 24/24 records có title và summary            | Parse lại và đối chiếu   |
| Lưu flat records               | `data/raw/crossref_records.json`  | 24 records, đủ 11 trường, không trùng ID     | Kiểm tra JSON/schema     |
| Xử lý lỗi tạm thời             | Retry 429/503                     | Backoff 1, 2, 4 giây; tối đa 4 request       | Mock các chuỗi response  |

Hai artifact được tạo cùng thời điểm. Parse lại raw response cho kết quả khớp 100% với raw records; không có title/summary rỗng và không có `paper_id` trùng.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Pipeline cần dữ liệu học thuật có thể truy vết và tái sử dụng. Module ingestion phải gọi Crossref, giữ response nguồn để audit và chuyển metadata lồng nhau thành schema phẳng cho cleaning, embedding và evaluation. API bên ngoài có thể rate-limit hoặc tạm thời không sẵn sàng nên cũng cần timeout, retry và backoff.

### Cách triển khai

`fetch_source_records()` tạo request params từ `source_query`, `source_filter` và `max_results`, rồi gọi `/works` với timeout 30 giây. Cấu hình hiện tại dùng query `agentic retrieval augmented generation large language model`, lọc công trình trong 180 ngày gần nhất có abstract và giới hạn 24 items.

Khi gặp 429 hoặc 503, hàm ưu tiên `Retry-After`; nếu không có số giây hợp lệ thì dùng `2**attempt`. `MAX_RETRIES = 3` tương ứng tối đa 4 request. Lỗi kết nối và lỗi JSON được retry có giới hạn; HTTP lỗi khác được báo ngay.

Sau response thành công, payload được lưu trước khi parse. Parser lấy title đầu tiên, ưu tiên `abstract` rồi fallback `description`, loại markup, chuẩn hóa whitespace và bỏ record thiếu title/summary. DOI được ưu tiên làm `paper_id`; URL hoặc ID fallback được dùng khi thiếu DOI. Authors, subjects, dates và URLs được ánh xạ vào `PaperRecord`.

### Input, output và contract

| Thành phần              | Mô tả                                                                       |
| ----------------------- | --------------------------------------------------------------------------- |
| Input                   | `Settings` hoặc Crossref JSON payload                                       |
| Output                  | `list[PaperRecord]`, raw response JSON và flat records JSON                 |
| Schema output           | 11 trường từ `paper_id`, `title`, `summary` đến URLs và metadata            |
| Module phụ thuộc        | `src/core/config.py`, `src/core/utils.py`, `requests`                       |
| Module sử dụng output   | Cleaning, baseline pipeline và repair flow                                  |
| Điều kiện lỗi cần xử lý | 429/503, timeout, lỗi kết nối/JSON, item sai kiểu, thiếu title hoặc summary |

### Cách xác minh

```powershell
$env:PYTHONPATH = (Resolve-Path src)
python -m compileall -q src/ingestion/crossref.py
$records = Get-Content -Raw data/raw/crossref_records.json | ConvertFrom-Json
$records.Count
($records | Where-Object { $_.title -and $_.summary }).Count
($records.paper_id | Sort-Object -Unique).Count
```

- **Kết quả mong đợi:** compile thành công; có 24 records; tất cả đủ title/summary và không trùng ID.
- **Kết quả thực tế:** 24 records, 24/24 đủ title/summary, 0 `paper_id` trùng. Mock 429/503 cũng pass.
- **Artifact/log:** `data/raw/crossref_response.json`, `data/raw/crossref_records.json`; không chứa secret.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Chọn chỉ lưu records đã parse hay lưu cả response nguồn và records phẳng.
- **Các phương án đã cân nhắc:** (1) chỉ lưu flat records; (2) lưu cả hai artifact; (3) luôn gọi lại API, không dùng snapshot.
- **Phương án đã chọn:** Lưu raw response theo schema Crossref và flat records theo `PaperRecord`.
- **Lý do:** Response giúp audit, parse lại và repair không phụ thuộc API; flat records tạo contract đơn giản cho downstream.
- **Bằng chứng quyết định phù hợp:** Response có 24 items; parse lại tạo đúng 24 records và khớp 100% với flat artifact.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `NotImplementedError: Student task: implement Crossref payload parsing.` hoặc `NotImplementedError: Student task: implement source fetching.`
- **Lệnh hoặc bước tái hiện:** Gọi parser/fetcher trong starter trước khi hoàn thành TODO.
- **Nguyên nhân gốc:** Starter mới có contract và pseudo-code, chưa có logic API, retry, parse hoặc ghi artifact.
- **Cách xử lý:** Implement parser, fetch/retry/backoff, hai artifacts và hàm load snapshot; bổ sung timeout và chuẩn hóa metadata.
- **Cách xác minh sau khi sửa:** Compile, parse lại response và mock 429/503. Có 24 records hợp lệ, không trùng ID; retry pass.
- **Điều học được:** External API cần snapshot, data contract, timeout, retry có giới hạn và giữ nguyên nguyên nhân lỗi để debug.

## 7. Hiểu biết về luồng end-to-end

1. Crossref tạo raw response/raw records. Cleaning chuẩn hóa và tạo `text_for_embedding`, `age_days`. Embedding model biến text thành vector; ChromaDB lưu vector cùng document ID và metadata.
2. Evaluation set chứa question, ground truth và `ground_truth_doc_ids`. Retrieval hit rate kiểm tra ID trong top-k; token F1 và judge metrics so sánh answer với ground truth.
3. Quality checks đo tính đầy đủ, hợp lệ, duy nhất và nhất quán. Freshness đo độ mới theo ngày và ngưỡng. Dữ liệu có thể đầy đủ nhưng stale, hoặc fresh nhưng vẫn duplicate.
4. Dùng cùng test set để chênh lệch metric phản ánh corruption/repair, không bị nhiễu do thay câu hỏi hoặc ground truth.
5. Repair thành công khi dataset/index được dựng lại từ raw artifact, quality/freshness phục hồi và metrics tiến gần baseline.

## 8. Phân tích kết quả

### Real-agent metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.5000 | 1.0000 | Corruption loại ba trong sáu ground-truth documents; repair từ raw phục hồi ID coverage. |
| `mean_token_f1` | 0.3227 | 0.0893 | 0.2945 | Answer overlap suy giảm và repaired tiến gần baseline. |
| `judge_accuracy` | 1.0000 | 0.3333 | 1.0000 | OpenRouter `o4-mini` judge xác nhận chênh lệch ba trạng thái; fallback bằng 0. |
| `mean_judge_score` | 5.0000 | 2.3333 | 5.0000 | Corrupted giảm rõ và repaired phục hồi. |
| Ragas context precision/recall | 0.6667/0.6667 | 0.1667/0.1667 | 0.6667/0.6667 | Context quality giảm và trở lại baseline. |
| Quality checks | PASS | FAIL | PASS | Corrupted có 6 failed error checks; baseline/repaired không có failed error check. |
| Freshness status | FRESH | STALE | FRESH | Corrupted có 3 stale rows; baseline/repaired có 0. |

### Kết luận từ số liệu

Raw snapshot ổn định cho phép repair mà không phải gọi lại Crossref hoặc suy đoán dữ liệu đã mất. Corruption xóa ba record mới nhất và đồng thời tạo lỗi completeness, uniqueness, validity và freshness; agent hit rate giảm 1.0 xuống 0.5, judge accuracy giảm 1.0 xuống 0.3333. Khi repair đọc lại `data/raw/crossref_records.json` và chạy cleaning/index lại, quality, freshness, hit rate, judge metrics và Ragas context precision/recall trở về baseline. Answer relevancy và faithfulness biến thiên giữa các LLM runs nên không được xem là recovery signal đơn điệu.

`corruption_log.json` cho thấy ba document mới nhất bị xóa khỏi corpus, tương ứng ba trong sáu ground-truth documents. Deterministic reference cũng ghi nhận hit rate `1.0 → 0.3333 → 1.0`. Kết quả này củng cố quyết định ingestion phải giữ raw artifacts có thể audit và tái sử dụng.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Pipeline đáng tin cậy cần lưu cả dữ liệu nguồn và dữ liệu đã parse để audit và repair.
2. Data quality bắt đầu từ ingestion: title/summary, ID ổn định và text chuẩn hóa giúp giảm lỗi lan truyền.
3. Nếu document ID không ổn định hoặc summary thiếu, retrieval và answer quality có thể giảm dù model không đổi.

### Nếu có thêm thời gian

Tôi sẽ thêm `pytest` cho parser/retry, cấu hình email Crossref bằng biến môi trường thay placeholder và lưu request URL/status/timestamp trong audit metadata. Cải thiện được đo bằng coverage cho 200/429/503/timeout/JSON lỗi và khả năng tái tạo chính xác records từ response.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Kết luận về ba trạng thái có artifact và metric thực tế để đối chiếu.
- [x] Tôi không ghi thành công cho phần chưa kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không sao chép nguyên văn báo cáo khác.

**Họ và tên:** Vũ Tiến Dũng

**Ngày xác nhận:** 2026-08-06
