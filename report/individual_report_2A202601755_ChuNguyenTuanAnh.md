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
| Baseline orchestration | `src/pipelines/phase1.py:14-54` | Raw records, settings, clean contract | Clean dataset, baseline index, evaluation, quality/freshness artifacts, baseline report | Hoàn thành |
| Corruption and repair orchestration | `src/pipelines/corruption_flow.py:29-111` | Baseline artifacts and raw records | Corrupted/repaired datasets, indexes, metrics, quality/freshness artifacts, comparison report | Hoàn thành |
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
| Bảo đảm dữ liệu corruption và repair được đánh giá công bằng | `tests/test_pipelines.py` | Baseline và repaired evaluation cùng dùng `data/eval/test_set.json` | `pytest -q`, 8 tests passed |

Output cụ thể: comparison report ghi nhận baseline/repaired đạt `retrieval_hit_rate=1.0`, còn corrupted giảm xuống `0.0`; quality chuyển từ PASS sang FAIL rồi trở lại PASS, freshness từ FRESH sang STALE rồi trở lại FRESH.

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
- **Kết quả thực tế:** `8 passed`; cả hai entrypoint thoát mã 0; OpenRouter `o4-mini` được sử dụng với 0/9 lượt judge fallback.
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
- **Cách xác minh sau khi sửa:** Chạy lại hai entrypoint; provider thực tế là `openrouter`, model `o4-mini`, cả 9 lượt judge không dùng fallback.
- **Điều học được:** Pipeline có thể vẫn thoát mã 0 khi evaluator lỗi vì code có fallback; cần kiểm tra answer artifacts và reasoning, không chỉ dựa vào exit code.

## 7. Hiểu biết về luồng end-to-end

1. Raw response và raw records được lấy từ Crossref, sau đó cleaning chuẩn hóa dữ liệu và tạo `text_for_embedding`. MiniLM biến nội dung này thành vector và ChromaDB lưu index để truy vấn.
2. Evaluation set chứa câu hỏi, ground truth và `ground_truth_doc_ids`. Retrieval hit được tính bằng cách đối chiếu document IDs truy hồi với các IDs đúng; token F1 và judge metrics đo chất lượng answer.
3. Quality checks kiểm tra schema, completeness, uniqueness, validity và consistency của từng dòng. Freshness monitoring tập trung vào ngày publication, tuổi dữ liệu và số dòng vượt ngưỡng freshness.
4. Cùng test set giúp ba trạng thái nhận cùng một bài kiểm tra; nếu thay test set, metric delta có thể do sample khác chứ không phải do corruption.
5. Repair thành công khi dataset repaired tạo lại từ raw, quality/freshness trở về trạng thái đạt và metrics được cải thiện so với corrupted. Trong lần chạy đã xác minh, repaired đạt lại 1.0 cho ba metric tỷ lệ và judge score 5.

## 8. Phân tích kết quả

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0 | 0.0 | 1.0 | Corruption làm mất khả năng truy hồi đúng; repair phục hồi hoàn toàn. |
| `mean_token_f1` | 1.0 | 0.0 | 1.0 | Answer corrupted không còn khớp ground truth; repaired trở lại mức baseline. |
| `judge_accuracy` | 1.0 | 0.0 | 1.0 | LLM judge đánh giá đúng sự suy giảm và phục hồi trong artifacts. |
| `mean_judge_score` | 5 | 1 | 5 | Chênh lệch rõ ràng giữa ba trạng thái. |
| Quality checks | PASS | FAIL | PASS | Corrupted có 6 failed error checks; repaired không còn failed error check. |
| Freshness status | FRESH | STALE | FRESH | Corrupted có 3 stale rows; repaired về 0 stale rows. |

### Kết luận từ số liệu

1. Corruption gồm blank/noisy summary, title truncation, stale dates và duplicate rows làm quality chuyển sang FAIL và freshness chuyển sang STALE; đồng thời `retrieval_hit_rate`, `mean_token_f1`, `judge_accuracy` giảm từ 1.0 xuống 0.0 và judge score giảm từ 5 xuống 1.
2. Repair đọc lại raw records và chạy lại cleaning, giúp quality trở lại PASS, freshness trở lại FRESH và toàn bộ bốn metrics chính trở về mức baseline.

Corruption ảnh hưởng rõ nhất là nhóm thay đổi nội dung/độ đầy đủ của trường dùng trong retrieval, kết hợp với duplicate và stale records. Bằng chứng là corrupted dataset có 6 failed error checks, 3 stale rows và metrics giảm đồng thời ở cả retrieval lẫn answer quality.

Kết quả cần lưu ý là baseline vẫn có một warning `categories_not_null` do một số record thiếu categories; warning này không làm baseline quality chuyển FAIL và được ghi trong `data/quality/baseline_quality.json` và baseline report.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Orchestration phải giữ đúng thứ tự và contract giữa các module; chạy được từng module riêng chưa đảm bảo pipeline end-to-end đúng.
2. Quality và freshness là bằng chứng nguyên nhân giúp giải thích vì sao metrics agent thay đổi, không chỉ là các con số tổng kết.
3. Cùng evaluation set và artifacts của cả ba trạng thái là điều kiện để comparison có ý nghĩa và có thể tái hiện.

### Nếu có thêm thời gian

Mở rộng evaluation set thêm nhiều câu hỏi và thêm coverage cho các loại câu hỏi categories/authors, sau đó đo lại metrics trên cùng test set versioned. Điều này giúp kết luận bớt phụ thuộc vào ba mẫu hiện tại.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Chu Nguyễn Tuấn Anh
**Ngày xác nhận:** 2026-08-06
