# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Chu Nguyễn Tuấn Anh |
| MSSV | 2A202601755 |
| Khóa/Lớp | K3 |
| Tên nhóm | F2-LabD305 |
| Vai trò chính | Integration & Comparison |
| Repository | https://github.com/VuTienDung28/K3_Day10_Data-Pipeline-F2LabD305 |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Baseline orchestration | `src/pipelines/phase1.py` | Raw records, settings, clean contract | Clean dataset, baseline index, deterministic/agent/Ragas evidence, quality/freshness, run manifest và report | Hoàn thành |
| Corruption and repair orchestration | `src/pipelines/corruption_flow.py` | Baseline artifacts and raw records | Corrupted/repaired datasets, indexes, dual metrics, run manifest, comparison report và SVG | Hoàn thành |
| Integration verification | `tests/test_pipelines.py` | Temporary settings and pipeline dependencies | Regression coverage for artifact reuse, shared test set, and repair from raw | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Kiểm tra contract giữa pipeline, evaluation và observability | Ingestion, evaluation, quality/reporting | Hai flow dùng đúng các artifact và cùng evaluation set; kết quả được ghi vào `data/`. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Ghép baseline flow | `src/pipelines/phase1.py` | `data/clean/`, `data/embeddings/papers_embeddings.json`, baseline metrics/answers, quality/freshness và `data/reports/phase1_report.md` | `.venv/Scripts/python.exe script/run_phase1.py` |
| Ghép corruption, repair và comparison | `src/pipelines/corruption_flow.py`, `src/observability/reporting.py` | Corrupted/repaired artifacts, `data/results/corruption_log.json`, `data/reports/corruption_report.md` | `.venv/Scripts/python.exe script/run_corruption_flow.py` |
| Bảo đảm dữ liệu corruption và repair được đánh giá công bằng | `tests/test_pipelines.py` | Tất cả deterministic/agent evaluations cùng dùng `data/eval/test_set.json` | `pytest -q`, 15 tests passed |

Output cụ thể: comparison report ghi nhận agent `retrieval_hit_rate` là `1.0 → 0.5 → 1.0`, judge accuracy `1.0 → 0.3333 → 1.0`; quality chuyển PASS → FAIL → PASS, freshness FRESH → STALE → FRESH. Ragas passed ở cả ba trạng thái và SVG được sinh từ agent metrics.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Các module ingestion, cleaning, retrieval, evaluation và observability cần được chạy theo đúng thứ tự, dùng đúng đường dẫn artifact và giữ nguyên evaluation set giữa ba trạng thái. Nếu flow tự tạo lại test set hoặc repair từ dataset đã hỏng thì comparison sẽ không còn đáng tin cậy.

### Cách triển khai

Baseline flow load raw records hiện có hoặc fetch source khi cần, làm sạch dữ liệu, ghi clean CSV/JSON, build `LocalEmbeddingIndex`, tạo hoặc tái sử dụng evaluation set, evaluate rồi chạy quality, freshness và baseline report.

Corruption flow yêu cầu các baseline artifact trước khi chạy. Flow đọc clean baseline, tạo corrupted dataset và index riêng, evaluate trên `settings.paths.eval_testset`, chạy quality/freshness; sau đó đọc lại raw records, chạy lại cleaning để tạo repaired dataset, build index và evaluate lại trên chính test set cũ. Comparison report nhận metrics và observability results của cả ba trạng thái.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `Settings`, raw records tại `data/raw/crossref_records.json`, clean baseline và evaluation set tại `data/eval/test_set.json` |
| Output | Clean/corrupted/repaired datasets, embedding manifests, answers, metrics, quality/freshness JSON và Markdown reports |
| Module phụ thuộc | `ingestion.cleaning`, `ingestion.crossref`, `ingestion.corruption`, `evaluation.metrics`, `observability.quality`, `observability.reporting`, `retrieval.index` |
| Module sử dụng output | Report generation, comparison flow và người dùng kiểm tra kết quả |
| Điều kiện lỗi cần xử lý | Thiếu baseline artifacts, clean dataset rỗng hoặc repair từ raw không tạo được record |

### Cách xác minh

```bash
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe script/run_phase1.py
.venv/Scripts/python.exe script/run_corruption_flow.py
```

- **Kết quả mong đợi:** Test pass; hai pipeline hoàn tất và tạo đủ artifacts.
- **Kết quả thực tế:** `15 passed`; cả hai entrypoint thoát mã 0; 36 judge verdicts qua hai modes/ba states dùng OpenRouter `o4-mini` với fallback bằng 0; Ragas passed cả ba agent states.
- **Artifact/log:** `data/results/`, `data/quality/`, `data/reports/`, `data/clean/`, `data/embeddings/`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Corrupted và repaired phải được so sánh trên cùng một evaluation set để thay đổi metrics phản ánh thay đổi dữ liệu thay vì thay đổi câu hỏi.
- **Các phương án đã cân nhắc:** Tạo test set mới cho từng trạng thái; hoặc giữ nguyên `data/eval/test_set.json` cho baseline, corrupted và repaired.
- **Phương án đã chọn:** Giữ nguyên test set và chỉ build lại dataset/index của từng trạng thái.
- **Lý do:** Cách này giữ cố định input đánh giá, cho phép đối chiếu trực tiếp retrieval, token F1, judge accuracy và judge score.
- **Bằng chứng quyết định phù hợp:** `tests/test_pipelines.py` kiểm tra cùng path evaluation set được truyền vào cả hai lần evaluate; comparison report ghi nhận corrupted giảm và repaired phục hồi các metrics.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** API OpenAI trả `Unsupported value: 'temperature' does not support 0.0 with this model. Only the default (1) value is supported.` khi chạy `o4-mini` trực tiếp.
- **Lệnh hoặc bước tái hiện:** Chạy structured evaluator sau khi cấu hình `LLM_PROVIDER=openai` và `LLM_MODEL=o4-mini`.
- **Nguyên nhân gốc:** Cấu hình `ChatOpenAI` truyền `temperature=0.0`, trong khi model `o4-mini` không chấp nhận giá trị đó.
- **Cách xử lý:** Dùng cấu hình OpenRouter với key/model hợp lệ theo môi trường chạy; cập nhật `.env.example` để thể hiện `LLM_PROVIDER=openrouter`, giữ key thật ngoài source/report.
- **Cách xác minh sau khi sửa:** Chạy lại hai entrypoint; provider thực tế là `openrouter`, model `o4-mini`, mọi metrics artifact có `fallback_count=0` và cả ba Ragas envelopes có `status=passed`.
- **Điều học được:** Pipeline có thể vẫn thoát mã 0 khi evaluator lỗi vì code có fallback; cần kiểm tra answer artifacts và reasoning, không chỉ dựa vào exit code.

## 7. Hiểu biết về luồng end-to-end

1. Raw response và raw records được lấy từ Crossref, sau đó cleaning chuẩn hóa dữ liệu và tạo `text_for_embedding`. MiniLM biến nội dung này thành vector và ChromaDB lưu index để truy vấn.
2. Evaluation set chứa câu hỏi, ground truth và `ground_truth_doc_ids`. Retrieval hit được tính bằng cách đối chiếu document IDs truy hồi với các IDs đúng; token F1 và judge metrics đo chất lượng answer.
3. Quality checks kiểm tra schema, completeness, uniqueness, validity và consistency của từng dòng. Freshness monitoring tập trung vào ngày publication, tuổi dữ liệu và số dòng vượt ngưỡng freshness.
4. Cùng test set SHA-256 `7c31f69a...7781a8a` giúp ba trạng thái nhận cùng một bài kiểm tra; nếu thay test set, metric delta có thể do sample khác chứ không phải do corruption.
5. Repair thành công khi dataset repaired tạo lại từ raw, quality/freshness trở về trạng thái đạt và metrics được cải thiện so với corrupted. Trong final agent run, repaired đạt hit rate/judge accuracy 1.0 và judge score 5; context precision/recall cũng phục hồi từ 0.1667 lên 0.6667.

## 8. Phân tích kết quả

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.5000 | 1.0000 | Ba trong sáu ground-truth documents bị drop; repair phục hồi toàn bộ ID coverage. |
| `mean_token_f1` | 0.3227 | 0.0893 | 0.2945 | Answer overlap giảm mạnh và repaired tiến gần baseline. |
| `judge_accuracy` | 1.0000 | 0.3333 | 1.0000 | LLM judge đánh giá đúng sự suy giảm và phục hồi. |
| `mean_judge_score` | 5.0000 | 2.3333 | 5.0000 | Chênh lệch rõ ràng giữa ba trạng thái. |
| Ragas context precision/recall | 0.6667/0.6667 | 0.1667/0.1667 | 0.6667/0.6667 | Retrieval-context quality giảm và phục hồi đúng kỳ vọng. |
| Quality checks | PASS | FAIL | PASS | Corrupted có 6 failed error checks; repaired không còn failed error check. |
| Freshness status | FRESH | STALE | FRESH | Corrupted có 3 stale rows; repaired về 0 stale rows. |

### Kết luận từ số liệu

1. Corruption gồm drop records, blank/noisy summary, title truncation, stale dates và duplicate rows làm quality chuyển FAIL, freshness STALE; agent hit rate giảm 1.0 xuống 0.5 và judge accuracy giảm 1.0 xuống 0.3333.
2. Repair đọc lại raw records và chạy lại cleaning, giúp quality/freshness phục hồi; hit rate, judge metrics và Ragas context precision/recall trở về baseline.

Answer relevancy và faithfulness biến thiên không đơn điệu giữa các LLM runs nên không được dùng riêng để tuyên bố recovery. Bằng chứng chính kết hợp document-ID hit, judge correctness, context precision/recall và quality/freshness.

Kết quả cần lưu ý là baseline vẫn có một warning `categories_not_null` do một số record thiếu categories; warning này không làm baseline quality chuyển FAIL và được ghi trong `data/quality/baseline_quality.json` và baseline report.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Orchestration phải giữ đúng thứ tự và contract giữa các module; chạy được từng module riêng chưa đảm bảo pipeline end-to-end đúng.
2. Quality và freshness là bằng chứng nguyên nhân giúp giải thích vì sao metrics agent thay đổi, không chỉ là các con số tổng kết.
3. Cùng evaluation set và artifacts của cả ba trạng thái là điều kiện để comparison có ý nghĩa và có thể tái hiện.

### Nếu có thêm thời gian

Mở rộng evaluation set vượt quá sáu câu hỏi hiện tại và thêm coverage cho categories khi nguồn có metadata, sau đó đo lại metrics trên cùng test set versioned. Điều này giúp kết luận bớt nhạy với từng document.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Chu Nguyễn Tuấn Anh
**Ngày xác nhận:** 2026-08-06
