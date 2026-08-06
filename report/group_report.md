# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin | Nội dung |
| --- | --- |
| Khóa/Lớp | K3 |
| Tên nhóm | F2-LabD305 |
| Repository | https://github.com/VuTienDung28/K3_Day10_Data-Pipeline-F2LabD305 |
| Ngày hoàn thành | 2026-08-06 |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Vũ Tiến Dũng | 2A202602009 | Nhóm trưởng, Source Ingestion | `src/ingestion/crossref.py` |
| 2 | Đào Thị Trang | 2A202601809 | Cleaning & Test Set | `src/ingestion/cleaning.py`, `src/evaluation/testset.py` |
| 3 | Nguyễn Đức Chung | 2A202601705 | Observability | `src/observability/quality.py`, `src/observability/reporting.py` |
| 4 | Lê Minh Ngọc | 2A202601471 | Corruption & Repair | `src/ingestion/corruption.py`, `tests/test_corruption.py` |
| 5 | Chu Nguyễn Tuấn Anh | 2A202601755 | Integration & Comparison | `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py`, `tests/test_pipelines.py` |

## 2. Tóm tắt kết quả

Nhóm đã hoàn thành pipeline end-to-end từ Crossref đến RAG evaluation và data observability. Baseline lưu raw response/raw records, làm sạch 24 papers, tạo MiniLM embeddings, xây ChromaDB index, giữ evaluation set 3 câu hỏi và tạo metrics, answer, quality, freshness cùng Markdown report. Baseline đạt `retrieval_hit_rate`, `mean_token_f1`, `judge_accuracy` bằng 1.0 và `mean_judge_score` bằng 5; quality PASS và freshness FRESH.

Corruption flow tạo 18 events tái lập với seed 42: drop records mới nhất, blank/noisy summary, title ngắn, stale dates và duplicates. Ba ground-truth papers bị drop làm toàn bộ ba metric tỷ lệ giảm xuống 0.0, judge score giảm xuống 1, quality FAIL với 6 failed error checks và freshness STALE với 3 stale rows. Repair không chỉnh ngược corrupted rows mà đọc lại raw snapshot, chạy cleaning/index/evaluation trên cùng test set. Repaired phục hồi quality PASS, freshness FRESH và toàn bộ metrics về mức baseline.

OpenRouter `o4-mini` thực hiện 9/9 lượt judge, không dùng heuristic fallback. Giới hạn chính là evaluation set chỉ có 3 samples và Crossref không cung cấp categories cho corpus hiện tại; Ragas được giữ ở chế độ tùy chọn để tránh tăng thời gian/chi phí chạy mặc định.

## 3. Kiến trúc và luồng dữ liệu

```text
Crossref REST API
    -> data/raw/crossref_response.json
    -> data/raw/crossref_records.json
    -> cleaning + data contract
    -> clean CSV/JSON
    -> MiniLM embedding + ChromaDB collections
    -> shared evaluation set
    -> baseline metrics/answers + quality/freshness + report
    -> deterministic corruption + audit log
    -> corrupted index/evaluation/observability
    -> repair from raw records
    -> repaired index/evaluation/observability
    -> three-state comparison report
```

### Trách nhiệm của từng khối

| Khối | Input | Xử lý chính | Output/artifact | Owner |
| --- | --- | --- | --- | --- |
| Ingestion | Crossref query/filter | Request, retry/backoff, parse, raw retention | `data/raw/crossref_response.json`, `crossref_records.json` | Vũ Tiến Dũng |
| Cleaning | `list[PaperRecord]` | Normalize, validate, deduplicate, derive dates/text | `data/clean/papers_clean.*` | Đào Thị Trang |
| Embedding/index | Clean/corrupted/repaired DataFrame | MiniLM vectors và persistent Chroma collections | `data/embeddings/*.json`, local `data/chroma/` | Retrieval reference module |
| Evaluation | Index và shared test set | Retrieval, factual answer, token F1, LLM judge | `data/results/*_metrics.json`, `*_answers.json` | Integration sử dụng evaluation contract |
| Observability | Mỗi dataset state | Quality checks, freshness, Markdown rendering | `data/quality/*.json`, `data/reports/*.md` | Nguyễn Đức Chung |
| Corruption/repair | Clean baseline và raw records | 6 failure modes; repair bằng re-clean raw snapshot | Corrupted/repaired datasets và `corruption_log.json` | Lê Minh Ngọc |
| Orchestration | Settings và artifacts | Chạy đúng thứ tự, giữ cùng test set, comparison | Baseline và corruption flows | Chu Nguyễn Tuấn Anh |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình | Giá trị sử dụng |
| --- | --- |
| `LLM_PROVIDER` | `openrouter` |
| `LLM_MODEL` | `o4-mini` |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Số lượng Crossref records | 24 |
| Retrieval `top_k` | 4 |
| Freshness threshold | 180 ngày |
| Corruption seed/rate | 42 / 10% |
| Ragas | Không bật; `RUN_RAGAS` mặc định tắt |

API key chỉ nằm trong `.env` local, không xuất hiện trong source, reports hoặc Git.

### Lệnh cài đặt và chạy

Nhóm sử dụng Python 3.11 và môi trường `.venv` đã cài project editable. Cách cài tương đương từ môi trường sạch:

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"
```

Baseline:

```bash
.venv/Scripts/python.exe script/run_phase1.py
```

Corruption/repair:

```bash
.venv/Scripts/python.exe script/run_corruption_flow.py
```

Tests:

```bash
.venv/Scripts/python.exe -m pytest -q
```

### Kết quả tái hiện gần nhất

| Lệnh | Trạng thái | Thời điểm UTC | Bằng chứng |
| --- | --- | --- | --- |
| Baseline pipeline | Thành công, exit 0 | 2026-08-06 06:03 | `data/reports/phase1_report.md`, baseline metrics/answers/quality/freshness |
| Corruption flow | Thành công, exit 0 | 2026-08-06 06:03 | `data/reports/corruption_report.md`, corruption log và corrupted/repaired artifacts |
| Full tests | 8 passed | 2026-08-06 | `pytest -q` output |

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính | Giá trị |
| --- | --- |
| Source | Crossref REST API, `https://api.crossref.org/works` |
| Query | `agentic retrieval augmented generation large language model` |
| Filter | `from-pub-date:2026-02-07,has-abstract:true` |
| Raw snapshot | `data/raw/crossref_response.json` |
| Thời điểm pipeline cuối | 2026-08-06 |
| Số record nhận/parse | 24/24 |
| Retry/backoff | Retry 429/503, ưu tiên `Retry-After`, fallback exponential 1/2/4 giây, tối đa 4 requests |

### Raw và clean schema

| Trường | Kiểu dữ liệu | Bắt buộc | Ý nghĩa | Xử lý khi thiếu/sai |
| --- | --- | --- | --- | --- |
| `paper_id` | string | Có | Document identity, ưu tiên DOI | Loại record nếu không có ID; deduplicate theo ID |
| `title` | string | Có | Tiêu đề paper | Normalize markup/whitespace; loại nếu rỗng |
| `summary` | string | Có | Abstract dùng trả lời và embedding | Normalize; loại nếu dưới 100 ký tự |
| `authors` | list | Không | Danh sách tác giả | Chuẩn hóa string/nested author, loại trùng |
| `categories` | list | Không | Crossref subjects | Giữ rỗng nếu source không cung cấp; warning quality |
| `published`, `updated` | ISO date | Có/Không | Publication/update dates | Parse UTC; loại nếu publication invalid |
| `age_days` | integer | Có | Tuổi dữ liệu tại thời điểm chạy | Tính từ `published`, yêu cầu không âm |
| `summary_chars` | integer | Có | Độ dài summary hiện tại | Tính lại sau cleaning/corruption |
| `text_for_embedding` | string | Có | Nội dung MiniLM | `Title: ... | Authors: ... | Summary: ...`; đồng bộ sau mutation |
| URL/comment fields | string | Không | Metadata truy vết | Chuẩn hóa string, cho phép rỗng |

### Quy tắc cleaning

| Quy tắc | Dimension | Record bị tác động ở lần chạy | Cách xác minh |
| --- | --- | ---: | --- |
| Loại ID/title rỗng hoặc summary dưới 100 ký tự | Completeness/Validity | 0 | Raw 24 → clean 24; summary ngắn nhất 826 ký tự |
| Normalize HTML/XML và whitespace | Validity | Áp dụng toàn bộ text | Clean JSON/CSV không còn markup nguồn |
| Deduplicate `paper_id` | Uniqueness | 0 duplicate | Baseline `paper_id_unique` PASS |
| Parse publication date và tính `age_days` | Validity/Freshness | 24 | `published_valid`, `age_days_valid`, consistency đều PASS |
| Tạo và kiểm tra embedding text | Consistency | 24 | `embedding_contains_title/summary` PASS |

Clean artifact có 16 trường, 24 rows, publication dates từ 2026-02-12 đến 2026-08-01. `paper_id` là document ID của Chroma và evaluation ground truth. `age_days` được tính so với thời điểm UTC của pipeline.

## 6. Evaluation setup

| Thành phần | Cấu hình thực tế |
| --- | --- |
| Số câu hỏi | 3 |
| `question_type` | `summary`, `authors`, `date` |
| Ground-truth document ID | Lấy trực tiếp từ `paper_id` của clean row |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Vector store/collections | ChromaDB: `papers-baseline`, `papers-corrupted`, `papers-repaired` |
| Retrieval `top_k` | 4 |
| LLM provider/model | OpenRouter / `o4-mini` |
| Shared test set | `data/eval/test_set.json` |
| Test-set SHA-256 | `e89671a152d221d170c28a0d6d547f1d600e93cd87c54bc2a2e6595e295f7cd5` |

Cùng một test set được dùng cho baseline, corrupted và repaired để câu hỏi, ground truth và document IDs không đổi. Vì vậy metric delta phản ánh thay đổi corpus/index thay vì thay đổi sample. Category question không được tạo vì cả 24 source records thiếu category; nhóm không tự bịa ground truth.

## 7. Kết quả baseline

### Artifact checklist

| Artifact | Đường dẫn | Trạng thái | Ghi chú |
| --- | --- | --- | --- |
| Raw response/records | `data/raw/` | Có | Response gốc và 24 flat records |
| Cleaned dataset | `data/clean/papers_clean.csv/json` | Có | 24 records |
| Embedding manifest | `data/embeddings/papers_embeddings.json` | Có | MiniLM baseline manifest |
| Evaluation set | `data/eval/test_set.json` | Có | 3 samples |
| Baseline metrics/answers | `data/results/baseline_*.json` | Có | 3 samples, LLM judge thật |
| Quality/freshness | `data/quality/baseline_quality.json`, `freshness_report.json` | Có | PASS/FRESH |
| Baseline report | `data/reports/phase1_report.md` | Có | Khớp JSON artifacts |

### Baseline metrics

| Metric | Giá trị | Diễn giải |
| --- | ---: | --- |
| `retrieval_hit_rate` | 1.0 | Ground-truth document xuất hiện trong top-k cho 3/3 samples |
| `mean_token_f1` | 1.0 | Answers khớp hoàn toàn ground truth theo token set |
| `judge_accuracy` | 1.0 | LLM judge đánh giá đúng 3/3 answers |
| `mean_judge_score` | 5 | Điểm judge trung bình tối đa |
| Ragas | N/A | Mặc định tắt; bật `RUN_RAGAS=1` cho lượt chạy chậm/tốn chi phí hơn |

Cả 3 baseline judge calls dùng OpenRouter `o4-mini`; không có heuristic fallback.

## 8. Data quality và freshness

### Quality checks tiêu biểu

| Check | Dimension | Ngưỡng | Baseline | Corrupted | Repaired |
| --- | --- | --- | ---: | ---: | ---: |
| `paper_id_unique` | Uniqueness | 0 duplicate rows | 0 PASS | 6 FAIL | 0 PASS |
| `title_min_length` | Validity | 0 title dưới 15 ký tự | 0 PASS | 3 FAIL | 0 PASS |
| `summary_not_null` | Completeness | 0 blank summaries | 0 PASS | 3 FAIL | 0 PASS |
| `summary_noise_markers` | Validity | 0 noise markers | 0 PASS | 3 FAIL | 0 PASS |
| `freshness_threshold` | Freshness | 0 rows trên 180 ngày | 0 PASS | 3 FAIL | 0 PASS |
| `embedding_contains_title/summary` | Consistency | 0 mismatch | 0 PASS | 0 PASS | 0 PASS |
| `categories_not_null` | Completeness warning | 0 blank categories | 24 WARN | 24 WARN | 24 WARN |

Overall quality: baseline PASS (0 failed errors, 1 warning), corrupted FAIL (6 failed errors, 1 warning), repaired PASS (0 failed errors, 1 warning).

### Freshness

| Thuộc tính | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| Trạng thái | FRESH | STALE | FRESH |
| Latest publication | 2026-08-01 | 2026-07-10 | 2026-08-01 |
| Oldest publication | 2026-02-12 | 2016-03-17 | 2026-02-12 |
| Stale rows | 0 | 3 | 0 |
| Invalid/future rows | 0/0 | 0/0 | 0/0 |
| Max age days | 175 | 3794 | 175 |

Freshness được tính lại từ `published`, không tin hoàn toàn vào derived `age_days`.

## 9. Corruption scenarios và repair

| Corruption | Cách tạo | Records | Quality signal thực tế | Tác động | Repair |
| --- | --- | ---: | --- | --- | --- |
| Drop latest records | Loại 3 rows mới nhất | 3 | Identity/coverage thay đổi nhưng row count bị duplicates bù | Ba ground-truth docs biến mất; retrieval hit 0.0 | Re-clean raw snapshot |
| Blank summary | Đặt summary rỗng | 3 | `summary_not_null`, `summary_min_length` FAIL | Mất nội dung answer/embedding | Khôi phục summary từ raw |
| Inject summary noise | Thêm corruption marker | 3 | `summary_noise_markers` FAIL | Semantic content bị nhiễu | Khôi phục summary từ raw |
| Truncate title | Giữ 8 ký tự đầu | 3 | `title_min_length` FAIL | Title signal suy giảm | Khôi phục title từ raw |
| Stale publication date | Lùi 3.650 ngày | 3 | `freshness_threshold` FAIL, STALE | Max age tăng tới 3794 | Khôi phục publication date |
| Duplicate records | Append 3 rows | 3 | 6 rows thuộc duplicate IDs | Volume vẫn 24 nhưng identity sai | Deduplicate khi cleaning raw |

Corruption log tại `data/results/corruption_log.json` có schema version 1.0, seed 42, rate 0.1, 24 input/output rows, 18 events, count theo loại và before/after values. Repair luôn đọc `data/raw/crossref_records.json` rồi chạy lại cleaning; không che lỗi bằng cách sửa metrics hoặc xóa quality signals.

## 10. So sánh baseline, corrupted và repaired

| Metric/signal | Baseline | Corrupted | Repaired | Corruption delta | Repair delta | Recovery |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `retrieval_hit_rate` | 1.0 | 0.0 | 1.0 | -1.0 | +1.0 | 100% |
| `mean_token_f1` | 1.0 | 0.0 | 1.0 | -1.0 | +1.0 | 100% |
| `judge_accuracy` | 1.0 | 0.0 | 1.0 | -1.0 | +1.0 | 100% |
| `mean_judge_score` | 5 | 1 | 5 | -4 | +4 | 100% |
| Quality status | PASS | FAIL | PASS | 6 failed errors | -6 failed errors | Phục hồi |
| Freshness status | FRESH | STALE | FRESH | +3 stale rows | -3 stale rows | Phục hồi |

Hai chuỗi nguyên nhân–bằng chứng:

1. Drop ba latest ground-truth documents và tạo completeness/validity/uniqueness/freshness errors → quality FAIL, freshness STALE → retrieval, token F1 và judge accuracy cùng giảm từ 1.0 xuống 0.0; judge score giảm từ 5 xuống 1.
2. Repair từ raw snapshot → failed errors 6 xuống 0, stale rows 3 xuống 0 → bốn metrics chính trở lại đúng baseline.

Kết quả phù hợp kỳ vọng và được đối chiếu giữa `corruption_log.json`, quality/freshness JSON, metrics/answers JSON và comparison report.

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** Pipeline dùng OpenAI trực tiếp với `o4-mini` vẫn thoát mã 0 nhưng 9/9 evaluator calls rơi vào heuristic fallback.
- **Nguyên nhân:** `ChatOpenAI` truyền `temperature=0.0`; OpenAI endpoint của `o4-mini` chỉ chấp nhận temperature mặc định. Evaluator bắt exception để pipeline tiếp tục nên exit code không phản ánh lỗi LLM.
- **Cách xử lý:** Cấu hình provider OpenRouter với model `o4-mini`, giữ key trong `.env`, cập nhật `.env.example` không chứa secret và kiểm tra answer artifacts thay vì chỉ exit code.
- **Cách xác minh:** Chạy lại hai entrypoints; provider/model thực tế là `openrouter/o4-mini`, cả 9 judge reasonings không chứa fallback marker và metrics/reports được tái sinh.

Một lỗi tích hợp khác là main từng rename hai runner vào `data/embeddings/script/`; nhóm đã khôi phục `script/run_phase1.py` và `script/run_corruption_flow.py` để lệnh README hoạt động.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng | Hướng cải thiện có thể kiểm chứng |
| --- | --- | --- |
| Evaluation set chỉ có 3 samples | Metrics nhạy với từng document và chưa bao phủ nhiều dạng câu hỏi | Tăng số sample mỗi question type, version/hash test set và so sánh confidence intervals |
| Source không có categories | Quality luôn có 1 warning; không có category question | Dùng query/source có subject metadata hoặc giữ N/A có truy vết, không tự suy đoán |
| Ragas tắt mặc định | Chưa có faithfulness/context metrics | Chạy `RUN_RAGAS=1`, lưu kết quả và chi phí/thời gian |
| Corruption severity cố định 10% | Chỉ có một điểm đo tác động | Chạy 5/10/20%, lưu fingerprints và vẽ trend metrics |
| Chroma binary không commit | Không có snapshot index binary trong Git | Rebuild từ clean data và embedding manifest bằng runner; giảm repository bloat |
| LLM evaluator có fallback | Exit 0 có thể che provider failure | Ghi `fallback_count` vào metrics hoặc thêm strict-evaluation mode |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [x] Phân công khớp với module, artifact và kết quả thực tế.
- [x] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp.
- [x] Baseline, corrupted và repaired dùng cùng evaluation set.
- [x] Bảng metrics khớp với các file trong `data/results/`.
- [x] Quality/freshness conclusions khớp với `data/quality/`.
- [x] Các đường dẫn báo cáo và artifact truy cập được.
- [x] Cả 5 thành viên đã hoàn thành báo cáo vai trò riêng.
- [x] Không có `.env`, API key, token hoặc secret trong source, report hoặc artifacts được chọn để nộp.
