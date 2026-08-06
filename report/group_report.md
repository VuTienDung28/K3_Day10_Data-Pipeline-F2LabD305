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

Nhóm đã hoàn thành pipeline end-to-end từ Crossref đến RAG evaluation và data observability. Baseline lưu raw response/raw records, làm sạch 24 papers, tạo MiniLM embeddings, xây ChromaDB index và dùng evaluation set 6 câu hỏi semantic (2 summary, 2 authors, 2 date). Bằng chứng được tách thành deterministic reference và real LangChain agent; baseline agent đạt `retrieval_hit_rate=1.0`, `judge_accuracy=1.0`, `mean_judge_score=5`, quality PASS và freshness FRESH.

Corruption flow tạo 18 events tái lập với seed 42: drop records mới nhất, blank/noisy summary, title ngắn, stale dates và duplicates. Agent metrics giảm xuống `retrieval_hit_rate=0.5`, `judge_accuracy=0.3333`, `mean_judge_score=2.3333`; quality FAIL với 6 failed error checks và freshness STALE với 3 stale rows. Repair không chỉnh ngược corrupted rows mà đọc lại raw snapshot, chạy cleaning/index/evaluation trên cùng test set. Repaired phục hồi agent hit rate và judge accuracy về 1.0, quality PASS và freshness FRESH.

Final artifacts ghi 36 judge verdicts qua hai evaluation modes và ba trạng thái, tất cả dùng OpenRouter `o4-mini` với `fallback_count=0`. Ragas chạy trên cả ba agent answer sets bằng cùng OpenRouter key và MiniLM local; đủ bốn metric hữu hạn. Giới hạn nguồn còn lại là Crossref không cung cấp categories cho corpus hiện tại, được giữ thành warning thay vì tự tạo metadata.

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
| Ragas | Bật cho evidence run (`RUN_RAGAS=1`); dùng OpenRouter LLM và MiniLM local |

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
| Baseline pipeline | Thành công, exit 0 | 2026-08-06 08:23 | `baseline_run.json`, baseline deterministic/agent/Ragas artifacts |
| Corruption flow | Thành công, exit 0 | 2026-08-06 08:33 | `corruption_run.json`, corruption log và corrupted/repaired artifacts |
| Full tests | 15 passed | 2026-08-06 | `pytest -q` output |

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
| Số câu hỏi | 6 (2 summary, 2 authors, 2 date) |
| Question design | Cue gồm một phần title và abstract; không chứa full exact title |
| Ground-truth document ID | Lấy trực tiếp từ `paper_id` của clean row |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Vector store/collections | ChromaDB: `papers-baseline`, `papers-corrupted`, `papers-repaired` |
| Retrieval `top_k` | 4 |
| LLM provider/model | OpenRouter / `o4-mini` |
| Evaluation modes | Deterministic reference và real tool-using agent |
| Shared test set | `data/eval/test_set.json` |
| Test-set SHA-256 | `7c31f69a37d9c7dff9d49e500603084024675b849924bf94c8d25f2167781a8a` |

Cùng một test set được dùng cho baseline, corrupted và repaired để câu hỏi, ground truth và document IDs không đổi. Vì vậy metric delta phản ánh thay đổi corpus/index thay vì thay đổi sample. Category question không được tạo vì cả 24 source records thiếu category; nhóm không tự bịa ground truth.

## 7. Kết quả baseline

### Artifact checklist

| Artifact | Đường dẫn | Trạng thái | Ghi chú |
| --- | --- | --- | --- |
| Raw response/records | `data/raw/` | Có | Response gốc và 24 flat records |
| Cleaned dataset | `data/clean/papers_clean.csv/json` | Có | 24 records |
| Embedding manifest | `data/embeddings/papers_embeddings.json` | Có | MiniLM baseline manifest |
| Evaluation set | `data/eval/test_set.json` | Có | 6 semantic samples, shared SHA-256 |
| Baseline metrics/answers | `data/results/baseline_*.json` | Có | Deterministic và real-agent artifacts, 6 samples mỗi mode |
| Run provenance | `data/results/baseline_run.json`, `corruption_run.json` | Có | Run ID, timestamps, provider/model và test-set hash |
| Visualization | `data/reports/corruption_metrics.svg` | Có | So sánh real-agent metrics ba trạng thái |
| Quality/freshness | `data/quality/baseline_quality.json`, `freshness_report.json` | Có | PASS/FRESH |
| Baseline report | `data/reports/phase1_report.md` | Có | Khớp JSON artifacts |

### Baseline metrics

| Metric | Deterministic reference | Real agent | Diễn giải |
| --- | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | 1.0000 | Ground-truth document xuất hiện trong top-k cho 6/6 samples |
| `mean_token_f1` | 0.6667 | 0.3227 | Agent trả lời đầy đủ hơn ground truth nên token-set overlap thấp hơn judge correctness |
| `judge_accuracy` | 0.6667 | 1.0000 | Real agent trả lời đúng 6/6 theo OpenRouter judge |
| `mean_judge_score` | 3.6667 | 5.0000 | Real agent đạt điểm judge tối đa |
| Judge fallback | 0/6 | 0/6 | Không dùng heuristic fallback |

Ragas trên baseline agent: `answer_relevancy=0.6447`, `context_precision=0.6667`, `context_recall=0.6667`, `faithfulness=0.6962`; trạng thái `passed`, mọi giá trị hữu hạn.

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
| Drop latest records | Loại 3 rows mới nhất | 3 | Identity/coverage thay đổi nhưng row count bị duplicates bù | Ba ground-truth docs biến mất; aggregate agent hit rate còn 0.5 | Re-clean raw snapshot |
| Blank summary | Đặt summary rỗng | 3 | `summary_not_null`, `summary_min_length` FAIL | Mất nội dung answer/embedding | Khôi phục summary từ raw |
| Inject summary noise | Thêm corruption marker | 3 | `summary_noise_markers` FAIL | Semantic content bị nhiễu | Khôi phục summary từ raw |
| Truncate title | Giữ 8 ký tự đầu | 3 | `title_min_length` FAIL | Title signal suy giảm | Khôi phục title từ raw |
| Stale publication date | Lùi 3.650 ngày | 3 | `freshness_threshold` FAIL, STALE | Max age tăng tới 3794 | Khôi phục publication date |
| Duplicate records | Append 3 rows | 3 | 6 rows thuộc duplicate IDs | Volume vẫn 24 nhưng identity sai | Deduplicate khi cleaning raw |

Corruption log tại `data/results/corruption_log.json` có schema version 1.0, seed 42, rate 0.1, 24 input/output rows, 18 events, count theo loại và before/after values. Repair luôn đọc `data/raw/crossref_records.json` rồi chạy lại cleaning; không che lỗi bằng cách sửa metrics hoặc xóa quality signals.

## 10. So sánh baseline, corrupted và repaired

### Real-agent metrics

| Metric/signal | Baseline | Corrupted | Repaired | Corruption delta | Repair delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| `retrieval_hit_rate` | 1.0000 | 0.5000 | 1.0000 | -0.5000 | +0.5000 |
| `mean_token_f1` | 0.3227 | 0.0893 | 0.2945 | -0.2334 | +0.2052 |
| `judge_accuracy` | 1.0000 | 0.3333 | 1.0000 | -0.6667 | +0.6667 |
| `mean_judge_score` | 5.0000 | 2.3333 | 5.0000 | -2.6667 | +2.6667 |
| Quality status | PASS | FAIL | PASS | 6 failed errors | -6 failed errors |
| Freshness status | FRESH | STALE | FRESH | +3 stale rows | -3 stale rows |

### Ragas trên real-agent answers

| Metric | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| `answer_relevancy` | 0.6447 | 0.7498 | 0.6008 |
| `context_precision` | 0.6667 | 0.1667 | 0.6667 |
| `context_recall` | 0.6667 | 0.1667 | 0.6667 |
| `faithfulness` | 0.6962 | 0.7583 | 0.6466 |

Hai chuỗi nguyên nhân–bằng chứng:

1. Drop ba trong sáu ground-truth documents và tạo completeness/validity/uniqueness/freshness errors → quality FAIL, freshness STALE → agent hit rate giảm 1.0 xuống 0.5, judge accuracy giảm 1.0 xuống 0.3333; Ragas context precision/recall giảm 0.6667 xuống 0.1667.
2. Repair từ raw snapshot → failed errors 6 xuống 0, stale rows 3 xuống 0 → hit rate/judge metrics và context precision/recall trở lại baseline. Answer relevancy và faithfulness có biến thiên do LLM generation/judging, nên không được diễn giải như metric recovery đơn điệu.

Kết quả được đối chiếu giữa `corruption_log.json`, quality/freshness JSON, deterministic/agent metrics, answer traces, run manifests, comparison report và SVG visualization.

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** Pipeline dùng OpenAI trực tiếp với `o4-mini` vẫn thoát mã 0 nhưng evaluator calls rơi vào heuristic fallback.
- **Nguyên nhân:** `ChatOpenAI` truyền `temperature=0.0`; endpoint trực tiếp từ chối tham số và evaluator bắt exception để pipeline tiếp tục nên exit code không phản ánh lỗi LLM.
- **Cách xử lý:** Cấu hình provider OpenRouter với model `o4-mini`, giữ key trong `.env`, cập nhật `.env.example` không chứa secret và ghi provenance/fallback ở từng answer cùng metrics tổng hợp.
- **Cách xác minh:** Evidence run cuối có 36 judge verdicts (6 samples × 2 modes × 3 states), mọi artifact đều ghi `fallback_count=0`; ba Ragas passes cũng ghi provider/model và bốn metric hữu hạn.

Một lỗi tích hợp khác là main từng rename hai runner vào `data/embeddings/script/`; nhóm đã khôi phục `script/run_phase1.py` và `script/run_corruption_flow.py` để lệnh README hoạt động.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng | Hướng cải thiện có thể kiểm chứng |
| --- | --- | --- |
| Evaluation set có 6 samples | Metrics vẫn nhạy với từng document | Tăng sample mỗi type, giữ SHA-256/version và tính confidence intervals |
| Source không có categories | Quality luôn có 1 warning; không có category question | Dùng query/source có subject metadata hoặc giữ N/A có truy vết, không tự suy đoán |
| Ragas/LLM có tính ngẫu nhiên | Answer relevancy và faithfulness không phục hồi đơn điệu dù retrieval phục hồi | Lặp evaluation nhiều seed/run và báo mean/variance |
| Corruption severity cố định 10% | Chỉ có một điểm đo tác động | Chạy 5/10/20%, lưu fingerprints và vẽ trend metrics |
| Chroma binary không commit | Không có snapshot index binary trong Git | Rebuild từ portable manifest documents bằng runner; giảm repository bloat |
| Evaluator có fallback resilience | Exit 0 vẫn có thể che provider failure nếu chỉ nhìn process status | Dùng `fallback_count`, provenance và strict evidence gate như final run |

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
