# Báo cáo cá nhân — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Đức Chung |
| MSSV | 2A202601705 |
| Khóa/Lớp | K3 |
| Tên nhóm | F2-LabD305 |
| Vai trò chính | Observability |
| Repository | https://github.com/VuTienDung28/K3_Day10_Data-Pipeline-F2LabD305 |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Data quality checks | `src/observability/quality.py` — `run_data_quality_checks()` | Clean, corrupted hoặc repaired DataFrame và `Settings` | JSON quality report có checks, dimensions, severity, observed/expected và overall status | Hoàn thành |
| Freshness monitoring | `src/observability/quality.py` — `build_freshness_report()` | DataFrame có publication dates, freshness threshold và output path | Freshness JSON gồm latest/oldest date, stale/invalid/future rows và trạng thái | Hoàn thành |
| Markdown reporting | `src/observability/reporting.py` — `generate_phase1_report()`, `generate_corruption_report()` | Source summary, metrics, quality và freshness payloads | Baseline report và bảng so sánh baseline/corrupted/repaired | Hoàn thành |
| Observability tests | `tests/test_observability.py` | Fixtures clean, corrupted, dropped và malformed | Regression coverage cho checks, freshness, report values và comparison deltas | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Thống nhất corruption signals | Corruption & Repair | Noise marker, title/summary threshold, duplicates và stale dates được quality checks phát hiện đúng. |
| Bàn giao report contract | Integration & Comparison | Pipeline truyền đủ quality/freshness của baseline, corrupted và repaired vào comparison report. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Xây dựng quality suite | `src/observability/quality.py`, `data/quality/*_quality.json` | 17 checks bao phủ volume, schema, completeness, uniqueness, validity, consistency và freshness | Đọc `checks`, `failed_checks`, `warning_checks` trong JSON |
| Tạo freshness reports | `data/quality/freshness_report.json`, `corrupted_freshness.json`, `repaired_freshness.json` | Baseline FRESH, corrupted STALE, repaired FRESH | Đối chiếu `stale_rows`, `max_age_days`, `is_fresh` |
| Tạo baseline Markdown | `data/reports/phase1_report.md` | Source/config, metrics, quality table, freshness và conclusion | Đọc report và đối chiếu JSON artifacts |
| Tạo comparison Markdown | `data/reports/corruption_report.md` | Metrics delta, recovery, quality/freshness ba trạng thái và evidence-based conclusion | Test report rendering và đối chiếu `data/results/*_metrics.json` |
| Xử lý malformed input sạch | `tests/test_observability.py` | Missing schema tạo quality FAIL; freshness UNKNOWN thay vì crash | `pytest -q tests/test_observability.py` |

Output cụ thể: corrupted quality có 6 failed error checks và 1 warning; repaired quality có 0 failed error checks và 1 warning. Corrupted freshness có 3 stale rows, trong khi baseline và repaired có 0.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Pipeline chạy không lỗi chưa chứng minh dữ liệu đủ tốt cho RAG. Cần có các tín hiệu xác định dataset có đủ schema, ID duy nhất, nội dung hợp lệ, derived embedding text đồng bộ và publication dates còn mới. Các tín hiệu phải được lưu thành artifacts để audit và giải thích metric thay đổi.

### Cách triển khai

`run_data_quality_checks()` tạo từng check dưới một contract thống nhất gồm `name`, `dimension`, `severity`, `success`, `observed`, `expected` và danh sách sample IDs. Error checks quyết định overall PASS/FAIL; category completeness là warning vì Crossref có thể không cung cấp `subject` dù record vẫn dùng được.

Quality suite kiểm tra row count và required columns; null/duplicate IDs; title/summary null và minimum length; noise markers; embedding text null và đồng bộ với title/summary hiện tại; publication date và `age_days`; freshness threshold; consistency giữa date và age; category completeness. Payload cuối cùng ghi số check pass/fail/warning và được lưu dưới `data/quality/`.

`build_freshness_report()` tính tuổi trực tiếp từ `published` thay vì tin hoàn toàn vào `age_days`. Dataset chỉ FRESH khi có dữ liệu, không có ngày invalid/future và không có dòng vượt ngưỡng 180 ngày. Reporting module escape nội dung Markdown, format số, dựng quality table và chỉ kết luận dựa trên metrics/signals được cung cấp.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input quality | `pandas.DataFrame`, `Settings`, tên report |
| Input freshness | DataFrame, freshness threshold và output path |
| Input reporting | Metrics dictionaries, quality/freshness payloads và source summary |
| Output | JSON quality/freshness artifacts và Markdown reports |
| Module phụ thuộc | `pandas`, `core.config.Settings`, `core.utils.now_utc/write_json/write_text` |
| Module sử dụng output | `phase1.py`, `corruption_flow.py`, group/individual reports và người đánh giá |
| Điều kiện lỗi cần xử lý | DataFrame thiếu cột, date invalid, dataset rỗng, check list/metric thiếu và ký tự Markdown đặc biệt |

### Cách xác minh

```bash
.venv/Scripts/python.exe -m pytest -q tests/test_observability.py
.venv/Scripts/python.exe -m pytest -q
```

- **Kết quả mong đợi:** Clean data PASS/FRESH; corrupted signals bị phát hiện; malformed input không crash; report có metrics/deltas thật.
- **Kết quả thực tế:** Full suite đạt `15 passed`; quality/freshness và report assertions đều pass.
- **Artifact/log:** `data/quality/`, `data/reports/phase1_report.md`, `data/reports/corruption_report.md`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cả 24 Crossref records đều thiếu `categories_joined`. Nếu coi check này là error, baseline và repaired sẽ FAIL dù ingestion/cleaning không thể tạo metadata mà source không cung cấp.
- **Các phương án đã cân nhắc:** Bỏ check; coi thiếu category là error; hoặc giữ check với severity warning.
- **Phương án đã chọn:** Giữ `categories_not_null` dưới dạng warning và không dùng nó để quyết định overall status.
- **Lý do:** Vẫn quan sát được completeness gap mà không đánh đồng optional source metadata với lỗi làm dataset không sử dụng được. Việc tự suy đoán category cũng sẽ làm ground truth không đáng tin cậy.
- **Bằng chứng quyết định phù hợp:** Baseline/repaired đều có 0 failed error checks và 1 warning; pipeline vẫn đánh giá được ba question types có ground truth thật. Reports hiển thị warning thay vì che mất tín hiệu.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** Corruption thay title hoặc summary nhưng derived `text_for_embedding` có thể vẫn giữ nội dung cũ; khi đó quality signal và index không phản ánh cùng một trạng thái dữ liệu.
- **Bước tái hiện:** Corrupt title/summary rồi kiểm tra chuỗi embedding có chứa giá trị hiện tại hay không.
- **Nguyên nhân gốc:** Derived field không tự đồng bộ khi cột nguồn bị mutation.
- **Cách xử lý:** Bổ sung checks `embedding_contains_title` và `embedding_contains_summary`; phối hợp corruption module rebuild `text_for_embedding` sau mutation. `summary_chars` cũng được cập nhật theo summary hiện tại.
- **Cách xác minh sau khi sửa:** Corrupted quality phát hiện đúng các lỗi có chủ đích nhưng hai consistency checks của embedding vẫn PASS; tests kiểm tra embedding chứa title/summary hiện tại.
- **Điều học được:** Observability không chỉ kiểm tra null/schema mà còn phải kiểm tra quan hệ giữa source fields và derived fields.

## 7. Hiểu biết về luồng end-to-end

1. Crossref response được lưu nguyên và parse thành raw records. Cleaning chuẩn hóa records, tính freshness fields và tạo `text_for_embedding`; MiniLM sinh vectors và ChromaDB lưu index.
2. Evaluation set liên kết từng câu hỏi với ground truth và document IDs. Retrieval hit đo ID đúng trong top-k; token F1 và LLM judge đo answer quality.
3. Quality checks đo completeness, uniqueness, validity, consistency và volume; freshness monitoring đo độ mới theo publication dates. Một dataset có thể đúng schema nhưng stale hoặc fresh nhưng chứa duplicate/noise.
4. Baseline, corrupted và repaired dùng cùng test set để metric delta phản ánh trạng thái dữ liệu. Nếu đổi câu hỏi, comparison sẽ bị nhiễu.
5. Repair thành công khi build lại từ raw artifact, quality/freshness phục hồi và metrics trên cùng test set cải thiện so với corrupted. Lần chạy hiện tại cho thấy hit rate, judge metrics và Ragas context precision/recall trở lại baseline; agent token F1 tiến gần baseline.

## 8. Phân tích kết quả

### Real-agent metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.5000 | 1.0000 | Retrieval impact đồng thời với quality failures; repair phục hồi. |
| `mean_token_f1` | 0.3227 | 0.0893 | 0.2945 | Answer overlap giảm mạnh và repaired tiến gần baseline. |
| `judge_accuracy` | 1.0000 | 0.3333 | 1.0000 | OpenRouter `o4-mini` judge chạy thật; cả ba agent states có fallback bằng 0. |
| `mean_judge_score` | 5.0000 | 2.3333 | 5.0000 | Judge score suy giảm rõ và phục hồi. |
| Ragas context precision/recall | 0.6667/0.6667 | 0.1667/0.1667 | 0.6667/0.6667 | Context quality khớp với retrieval degradation/recovery. |
| Quality checks | PASS | FAIL | PASS | Failed error checks: 0 → 6 → 0; warning checks luôn là 1. |
| Freshness status | FRESH | STALE | FRESH | Stale rows: 0 → 3 → 0. |

### Kết luận từ số liệu

1. Corruption tạo 3 duplicate IDs, 3 title ngắn, 3 summary rỗng/ngắn, 3 noise markers và 3 stale dates; quality chuyển PASS → FAIL, freshness chuyển FRESH → STALE; agent hit rate giảm 1.0 xuống 0.5 và judge accuracy giảm 1.0 xuống 0.3333.
2. Repair chạy lại cleaning từ raw records; failed error checks về 0, stale rows về 0; hit rate, judge metrics và Ragas context precision/recall trở lại baseline. Deterministic reference cũng ghi nhận hit rate `1.0 → 0.3333 → 1.0`.

`drop_latest_record` tác động trực tiếp nhất tới evaluation vì ba trong sáu ground-truth documents bị loại. Observability artifacts không chỉ chứng minh dataset xấu mà còn chỉ ra các failure dimensions đi kèm metric degradation. Answer relevancy và faithfulness của Ragas biến thiên không đơn điệu giữa các LLM runs nên không được dùng riêng làm bằng chứng recovery.

Kết quả đáng chú ý là row count vẫn bằng 24 do ba dropped rows được bù bởi ba duplicates. Check volume PASS nhưng uniqueness FAIL, cho thấy cần dùng nhiều quality dimensions thay vì một chỉ số đơn lẻ. Một warning category còn tồn tại ở cả baseline và repaired vì source thiếu metadata; report giữ warning này để phản ánh giới hạn thực tế.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Quality checks cần mô tả failure bằng observed value và sample IDs để có thể truy nguyên, không chỉ trả boolean.
2. Freshness phải được tính lại từ timestamp nguồn và không nên tin hoàn toàn một derived age field.
3. Data signals và agent metrics phải được đọc cùng nhau để hình thành kết luận nhân quả có bằng chứng.

### Nếu có thêm thời gian

Tôi sẽ version quality contract và lưu fingerprint của dataset/test set trong reports. Sau đó chạy nhiều corruption severities để đo số failed checks và metric degradation theo tỷ lệ 5%, 10%, 20%. Cải thiện được xác minh bằng artifacts có version/fingerprint và bảng trend qua nhiều runs.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Đức Chung

**Ngày xác nhận:** 2026-08-06
