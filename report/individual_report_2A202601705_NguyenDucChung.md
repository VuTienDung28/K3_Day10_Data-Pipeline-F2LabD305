# Báo cáo vai trò thành viên — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Đức Chung |
| MSSV | 2A202601705 |
| Khóa/Lớp | K3 |
| Tên nhóm | F2-D305 |
| Vai trò chính | Role 3 — Observability: Data Quality, Freshness và Reporting |
| Repository | https://github.com/VuTienDung28/K3_Day10_Data-Pipeline-F2LabD305 |
| Branch thực hiện | `2A202601705_NguyenDucChung` |
| Commit bàn giao | `612557f` — `feat: implement observability and reporting` |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Data quality | `src/observability/quality.py` — `run_data_quality_checks()` | Clean/Corrupted/Repaired DataFrame và `Settings` | Dictionary kết quả quality và JSON trong `data/quality/` | Hoàn thành |
| Freshness monitoring | `src/observability/quality.py` — `build_freshness_report()` | DataFrame có cột `published`; freshness threshold | Freshness dictionary và JSON report | Hoàn thành |
| Baseline reporting | `src/observability/reporting.py` — `generate_phase1_report()` | Source summary, metrics, quality và freshness | `data/reports/phase1_report.md` khi Role 5 tích hợp | Hoàn thành phần hàm; chờ pipeline gọi |
| Comparison reporting | `src/observability/reporting.py` — `generate_corruption_report()` | Metrics và quality/freshness của ba trạng thái | `data/reports/corruption_report.md` khi Role 5 tích hợp | Hoàn thành phần hàm; chờ metrics thật |
| Validation | `tests/test_observability.py` | Synthetic clean/corrupted/repaired fixtures | 4 automated tests cho quality, freshness và reports | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Kiểm tra đầu ra Role 1–2 | `crossref.py`, `cleaning.py`, `testset.py` | Xác minh 24 raw records, 24 clean records, ID unique và artifact tái lập được; phát hiện test set mới có 3 câu và thiếu categories |
| Chuẩn bị contract cho Role 4 | `src/ingestion/corruption.py` | Xác định corruption marker, helper fields cần rebuild và các tín hiệu quality/freshness phải thay đổi |
| Preflight corruption/repair | Quality và freshness modules | Corrupted state được phát hiện `FAIL/STALE`; clean snapshot dùng làm repaired state trở lại `PASS/FRESH` |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Xây bộ quality checks có audit details | `run_data_quality_checks()` | Kiểm tra volume, schema, completeness, uniqueness, validity, consistency và freshness; mỗi check có `observed`, `expected`, `severity`, `details` | `python -m pytest -q` |
| Xây freshness monitoring độc lập với `age_days` | `build_freshness_report()` | Tự tính tuổi dữ liệu từ `published`; phát hiện stale, future và invalid dates | Test clean/corrupted fixtures và preflight trên clean artifact thật |
| Sinh báo cáo baseline | `generate_phase1_report()` | Markdown có source, metrics, quality table, freshness và kết luận dựa trên evidence | `test_reports_render_real_values_and_comparison_deltas` |
| Sinh báo cáo comparison | `generate_corruption_report()` | Bảng baseline/corrupted/repaired, corruption delta, repair delta và recovery ratio | `test_reports_render_real_values_and_comparison_deltas` |
| Kiểm thử edge cases | `tests/test_observability.py` | 4 tests, bao phủ clean data, corruption, thiếu schema, drop rows và report rendering | Kết quả: `4 passed in 1.10s` tại thời điểm bàn giao Role 3 |

Output cụ thể do phần việc của tôi tạo ra là hai module observability hoàn chỉnh và bộ test tự động trong commit `612557f`. Khi chạy với 24 clean records thật, quality trả `PASS` với 0 error và 1 warning về categories; freshness trả `FRESH`, stale rows bằng 0 và tuổi lớn nhất là 175 ngày.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Pipeline không chỉ cần chạy xong mà phải phát hiện được dữ liệu bị thiếu, trùng, nhiễu hoặc quá cũ trước khi dữ liệu đó ảnh hưởng đến retrieval và câu trả lời. Đồng thời, báo cáo phải phản ánh đúng artifact và metrics thật, không được mặc định kết luận corruption có tác động hoặc repair đã thành công.

### Cách triển khai

Tôi tổ chức quality report thành danh sách các check độc lập. Mỗi check có tên, quality dimension, mức độ `error` hoặc `warning`, trạng thái pass/fail, giá trị quan sát và kỳ vọng. Overall quality chỉ pass khi không còn failed error check; warning vẫn được giữ trong artifact và Markdown report để không che mất vấn đề metadata.

Các check chính gồm:

- Row count và required columns.
- `paper_id` không rỗng và unique.
- Title/summary không rỗng và đạt độ dài tối thiểu.
- Phát hiện marker `[CORRUPTED_NOISE]`.
- `text_for_embedding` không rỗng và còn chứa title/summary hiện tại.
- `published` hợp lệ; `age_days` không âm và nhất quán với ngày xuất bản.
- Phát hiện stale rows theo `freshness_threshold_days`.
- Categories completeness được ghi ở mức warning vì Crossref không cung cấp `subject` cho corpus hiện tại.

Freshness report không tin hoàn toàn vào `age_days`. Tuổi dữ liệu được tính lại từ `published` và thời điểm UTC hiện tại. Cách này phát hiện được trường hợp corruption thay đổi ngày xuất bản nhưng quên rebuild `age_days`.

Reporting module chỉ nhận dictionaries do pipeline truyền vào. Nó không tính lại hay tự tạo metrics. Comparison report tính:

```text
corruption_delta = corrupted - baseline
repair_delta = repaired - corrupted
recovery_ratio = (repaired - corrupted) / (baseline - corrupted)
```

Khi thiếu metric hoặc Ragas bị skip, report hiển thị `N/A` hoặc payload tương ứng thay vì crash.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `pandas.DataFrame`, `Settings`, metrics dictionaries và source summary |
| Output | Quality/freshness dictionaries; JSON artifacts; baseline/comparison Markdown reports |
| Module phụ thuộc | `core.config`, `core.utils`, `pandas` |
| Module sử dụng output | `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py`, report và evaluation workflow |
| Điều kiện lỗi cần xử lý | DataFrame rỗng, thiếu cột, null, duplicate, summary nhiễu, title bị cắt, invalid/stale date, inconsistent embedding và thiếu metric optional |

### Cách xác minh

```powershell
conda activate python11
python -m compileall -q src script tests
python -m pytest -q
```

- **Kết quả mong đợi:** source compile được; baseline fixture pass/fresh; corrupted fixture fail/stale; repaired fixture pass/fresh; reports chứa đúng metrics và delta.
- **Kết quả thực tế:** compile thành công; `4 passed in 1.10s` tại commit bàn giao. Sau khi pull thêm Role 4, toàn repository có `6 passed`.
- **Artifact/log:** `tests/test_observability.py`, commit `612557f`; không chứa API key hoặc secret.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** 24/24 Crossref records hiện không có trường `subject`, làm `categories_joined` rỗng dù các trường dữ liệu quan trọng khác đều hợp lệ.
- **Các phương án đã cân nhắc:** (1) coi categories rỗng là error và làm baseline quality fail; (2) bỏ hoàn toàn check categories; (3) giữ check nhưng đánh mức warning.
- **Phương án đã chọn:** giữ `categories_not_null` ở mức `warning`.
- **Lý do:** phương án này vẫn lưu bằng chứng về metadata thiếu nhưng không biến một hạn chế của nguồn Crossref thành lỗi ngăn toàn bộ baseline. Nếu Role 1 bổ sung fallback từ `type` hoặc `container-title`, warning sẽ tự biến mất mà không cần đổi reporting contract.
- **Bằng chứng quyết định phù hợp:** trên 24 clean rows, quality trả `PASS`, 0 failed error checks và 1 warning `categories_not_null`; freshness vẫn `FRESH`.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** nếu corruption đổi `published` thành ngày cũ nhưng không cập nhật `age_days`, một freshness check chỉ đọc `age_days` có thể báo dữ liệu vẫn fresh.
- **Bước tái hiện:** sửa `published` của một row thành ngày cách hiện tại 400 ngày nhưng giữ nguyên `age_days`, sau đó chạy quality/freshness.
- **Nguyên nhân gốc:** có hai trường biểu diễn cùng thông tin tuổi dữ liệu và chúng có thể mất nhất quán sau mutation.
- **Cách xử lý:** freshness được tính lại trực tiếp từ `published`; quality bổ sung check `age_days_consistent_with_published` với tolerance một ngày.
- **Cách xác minh sau khi sửa:** corruption preflight trả `quality=FAIL`, `freshness=STALE`; khi phục hồi từ clean snapshot, kết quả trở lại `PASS/FRESH`.
- **Điều học được:** observability signal nên được tính từ dữ liệu nguồn đáng tin cậy và phải kiểm tra consistency giữa các derived fields, không chỉ tin vào một cột đã tính sẵn.

## 7. Hiểu biết về luồng end-to-end

1. Crossref API trả raw response. Ingestion lưu response để truy vết rồi parse thành `PaperRecord`. Cleaning chuẩn hóa text, date, authors/categories, tính `age_days` và tạo `text_for_embedding`. MiniLM biến text thành embedding, sau đó ChromaDB lưu vector cùng metadata để semantic search và exact lookup.
2. Evaluation set chứa câu hỏi, ground truth và `ground_truth_doc_ids`. Retrieval hit được tính bằng việc kiểm tra tài liệu đúng có xuất hiện trong top-k hay không; câu trả lời được so với ground truth bằng token F1 và judge metrics.
3. Data quality kiểm tra completeness, uniqueness, validity và consistency của dữ liệu. Freshness tập trung vào độ mới theo ngày xuất bản và threshold. Một dataset có thể đúng schema nhưng vẫn stale, hoặc fresh nhưng có duplicate/blank summary.
4. Baseline, corrupted và repaired phải dùng cùng test set để loại bỏ biến số do câu hỏi thay đổi. Khi đó metric delta mới có thể được liên hệ với thay đổi dữ liệu.
5. Repair chỉ được xem là thành công khi repaired data được dựng lại từ raw snapshot, quality/freshness phục hồi, cùng test set được đánh giá lại và metrics/answers artifacts cho thấy mức phục hồi thực tế.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | N/A | N/A | N/A | Chờ Role 5 hoàn thiện pipeline và chạy cùng test set; không tự tạo số liệu |
| `mean_token_f1` | N/A | N/A | N/A | Chờ metrics artifact thật |
| `judge_accuracy` | N/A | N/A | N/A | Chờ OpenAI judge/evaluator chạy trong pipeline |
| `mean_judge_score` | N/A | N/A | N/A | Chờ metrics artifact thật |
| Quality checks | PASS | FAIL (preflight) | PASS (preflight) | Corruption được phát hiện; repaired preflight phục hồi quality |
| Freshness status | FRESH | STALE (preflight) | FRESH (preflight) | Stale date được phát hiện từ `published` |

Các giá trị corrupted/repaired ở trên là kết quả preflight in-memory để xác minh Role 3 và contract Role 4, chưa phải metrics cuối của `corruption_flow.py`.

### Kết luận từ số liệu

1. Drop rows/duplicate/blank summary/noise/truncated title/stale date → các quality checks tương ứng fail và freshness chuyển `FRESH → STALE` → chưa kết luận được agent metric vì Role 5 chưa tạo corrupted metrics artifact.
2. Repair từ clean/raw contract → quality/freshness phục hồi `PASS/FRESH` trong preflight → mức phục hồi của retrieval và answer metrics phải chờ pipeline đánh giá bằng test set cố định.

Corruption có tín hiệu rõ nhất ở tầng observability là stale publication date vì nó làm freshness chuyển trạng thái trực tiếp. Blank summary, noise, truncated title, duplicate và mất record cũng được các check chuyên biệt phát hiện. Chưa thể khẳng định loại nào ảnh hưởng agent mạnh nhất khi chưa có `baseline_metrics.json`, `corrupted_metrics.json` và `repaired_metrics.json`.

Kết quả khác kỳ vọng ban đầu là toàn bộ 24 records đều thiếu categories do Crossref không cung cấp `subject`. Tôi kiểm tra raw/clean artifacts, xác nhận đây là hạn chế nguồn dữ liệu và chọn lưu nó dưới dạng warning thay vì bỏ qua hoặc làm baseline fail hoàn toàn.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Một data pipeline có thể chạy thành công về kỹ thuật nhưng vẫn tạo dữ liệu không đủ tin cậy; cần lưu raw lineage và kiểm tra contract ở mỗi bước.
2. Data quality và freshness là hai nhóm tín hiệu khác nhau, đồng thời derived fields như `age_days` cần được đối chiếu với source field `published`.
3. Muốn kết luận dữ liệu ảnh hưởng đến RAG, phải nối được chuỗi bằng chứng: corruption log → quality/freshness signal → retrieved document/answer → metric delta.

### Nếu có thêm thời gian

Tôi sẽ bổ sung threshold cấu hình được cho từng quality check và lưu baseline row count làm reference thay vì chỉ dùng `settings.max_results`. Cải thiện này có thể đo bằng số false positive/false negative trên nhiều corruption fixtures và nhiều Crossref snapshots khác nhau.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận hiện có đều kèm artifact, commit hoặc kết quả kiểm thử để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần pipeline/metrics chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Đức Chung
**Ngày xác nhận:** 2026-08-06
