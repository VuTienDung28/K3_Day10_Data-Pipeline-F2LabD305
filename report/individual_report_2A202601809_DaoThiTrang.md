# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Đào Thị Trang |
| MSSV | 2A202601809 |
| Khóa/Lớp | K3 |
| Tên nhóm | F2-LabD305 |
| Vai trò chính | Role 2 — Cleaning & Test Set |
| Repository | https://github.com/VuTienDung28/K3_Day10_Data-Pipeline-F2LabD305 |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Cleaning và data modeling | `src/ingestion/cleaning.py` — `build_clean_dataframe()` | `list[PaperRecord]` từ raw snapshot và thời điểm chạy | Cleaned DataFrame, `papers_clean.csv`, `papers_clean.json` | Hoàn thành |
| Evaluation set | `src/evaluation/testset.py` — `build_test_set()` | Cleaned DataFrame | `data/eval/test_set.json` | Hoàn thành |

Phần việc của tôi nằm giữa ingestion và retrieval/evaluation. Tôi nhận schema `PaperRecord` từ Role 1, chuẩn hóa thành clean schema ổn định, sau đó tạo test set để Role 5 dùng khi đánh giá baseline, corrupted và repaired.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Kiểm tra contract tích hợp | Retrieval/index và pipeline integration | Xác minh clean data có đầy đủ `paper_id`, `title`, metadata và `text_for_embedding` mà `LocalEmbeddingIndex` sử dụng |
| Tạo artifact kiểm chứng | Nhóm tích hợp và báo cáo | Sinh clean CSV/JSON và test-set JSON từ 24 raw records thực tế |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Loại record không hợp lệ | `build_clean_dataframe()` | Loại record thiếu ID/title hoặc summary dưới 100 ký tự | So sánh số record raw và clean; kiểm tra `summary_chars >= 100` |
| Chuẩn hóa text | `_clean_text()` | Giải mã HTML entity, xóa XML/HTML và khoảng trắng thừa | Kiểm tra title/summary không còn mẫu `<...>` |
| Chuẩn hóa author/category | `_clean_string_list()` | Xử lý được list chuỗi và author dạng `{given, family}`; loại phần tử trùng | Kiểm tra `authors_joined`, `categories_joined` trong clean artifacts |
| Chuẩn hóa ngày và freshness | `_parse_date()`, `build_clean_dataframe()` | `published` dạng `YYYY-MM-DD`, có `age_days` | Kiểm tra regex ngày và `age_days >= 0` |
| Tạo nội dung embedding | `text_for_embedding` | Chuỗi theo mẫu `Title: ... | Authors: ... | Summary: ...` | Đối chiếu từng row với ba trường nguồn |
| Tạo evaluation set | `build_test_set()` | Câu hỏi summary, authors, date và category khi dữ liệu hỗ trợ | Đọc `data/eval/test_set.json`; kiểm tra document ID tồn tại trong clean data |

Artifact cụ thể đã tạo:

- `data/clean/papers_clean.csv`
- `data/clean/papers_clean.json`
- `data/eval/test_set.json`
- Commit triển khai Role 2: `d854776` (`feat: implement data cleaning pipeline`)

Trong lần xác minh Role 2, 24 raw records tạo thành 24 clean records; 24 `paper_id` là duy nhất; không có `text_for_embedding` rỗng và không có `age_days` âm. Summary ngắn nhất có 826 ký tự nên không có record nào bị loại bởi ngưỡng 100 ký tự. Test set chứa ba sample thuộc loại summary, authors và date. Không tạo câu hỏi category vì cả 24 record nguồn đều không có category, tránh sinh ground truth rỗng hoặc tự bịa dữ liệu.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Dữ liệu Crossref có text chứa markup, khoảng trắng không đồng nhất, author có thể là nested dictionary, trường ngày có thể thiếu hoặc sai định dạng và record có thể bị trùng DOI. Nếu đưa trực tiếp dữ liệu này vào embedding, retrieval sẽ chứa nhiễu và các module phía sau không có schema ổn định. Evaluation set cũng phải được tạo từ clean data thật và liên kết đúng với document ID trong index.

### Cách triển khai

Cleaning được thực hiện theo từng record. Text được giải mã HTML entity, xóa tag bằng biểu thức chính quy và chuẩn hóa khoảng trắng. Author dạng dictionary được ghép từ `given` và `family`; author/category được loại trùng không phân biệt hoa thường. Record thiếu định danh, thiếu title hoặc summary dưới 100 ký tự bị loại.

Ngày được parse bằng `pandas.to_datetime(..., utc=True)` và xuất lại theo ISO date. `age_days` là số ngày từ ngày xuất bản đến ngày chạy pipeline. Dữ liệu được deduplicate theo `paper_id`, sau đó sắp xếp theo ngày xuất bản giảm dần và ID tăng dần để kết quả có tính tái hiện.

Test-set builder kiểm tra các cột bắt buộc, chỉ chọn document có ID/title/summary hợp lệ và tạo ground truth trực tiếp từ cleaned row. Các câu hỏi có exact title để `qa.py` có thể lookup đúng paper. Mỗi sample giữ `ground_truth_doc_ids` là `paper_id` của document tương ứng.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `list[PaperRecord]`, gồm ID, title, summary, authors, categories, dates và URL; tham số `run_date` |
| Output | DataFrame gồm `paper_id`, `title`, `summary`, `authors`, `categories`, `primary_category`, `published`, `updated`, `age_days`, `authors_joined`, `categories_joined`, `summary_chars`, `text_for_embedding`, URL và comment |
| Module phụ thuộc | `src/ingestion/crossref.py`, `src/core/utils.py` |
| Module sử dụng output | `src/retrieval/index.py`, `src/evaluation/testset.py`, `src/observability/quality.py`, `src/pipelines/phase1.py` |
| Điều kiện lỗi cần xử lý | Thiếu ID/title, summary ngắn, ngày không parse được, author nested, giá trị trùng, thiếu category và DataFrame thiếu cột bắt buộc |

### Cách xác minh

```powershell
@'
from datetime import UTC, datetime
from core.config import load_settings
from core.utils import write_csv, write_json
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import load_raw_records

settings = load_settings()
records = load_raw_records(settings.paths.raw_records_json)
df = build_clean_dataframe(records, datetime.now(UTC))
write_csv(df, settings.paths.clean_csv)
write_json(settings.paths.clean_json, df.to_dict(orient="records"))
test_set = build_test_set(df, settings.paths.eval_testset)
print(f"Raw: {len(records)}, clean: {len(df)}, test samples: {len(test_set)}")
'@ | python -
```

- **Kết quả mong đợi:** Sinh được clean CSV/JSON và test set; ID duy nhất; summary đạt ngưỡng; ngày và embedding đúng format.
- **Kết quả thực tế:** 24 raw records, 24 clean records, 24 ID duy nhất và 3 test samples có ground-truth ID hợp lệ.
- **Artifact/log:** `data/clean/papers_clean.csv`, `data/clean/papers_clean.json`, `data/eval/test_set.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Crossref không đảm bảo mọi paper đều có `subject`, trong khi test-set starter đề xuất câu hỏi categories.
- **Các phương án đã cân nhắc:** Tạo câu hỏi category với đáp án rỗng; gán category suy đoán từ title/summary; hoặc chỉ tạo category question khi nguồn có category thật.
- **Phương án đã chọn:** Chỉ tạo câu hỏi category khi `categories_joined` có dữ liệu.
- **Lý do:** Ground truth phải truy vết được từ dữ liệu nguồn. Đáp án rỗng hoặc category suy đoán sẽ làm metric thiếu ý nghĩa và không còn là ground truth đáng tin cậy.
- **Bằng chứng quyết định phù hợp:** 24 records hiện tại đều có `categories_joined` rỗng, nên test set giữ ba loại có dữ liệu thật: summary, authors và date.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** Phiên bản cleaning ban đầu chưa loại summary dưới 100 ký tự và `text_for_embedding` dùng nhiều dòng, có thêm category, chưa khớp format bắt buộc.
- **Bước tái hiện:** Đối chiếu source code với checklist cleaning và kiểm tra trực tiếp giá trị `summary_chars`, `text_for_embedding`.
- **Nguyên nhân gốc:** Pseudo-code starter không quy định ngưỡng summary và format embedding chi tiết; yêu cầu chi tiết được bổ sung sau.
- **Cách xử lý:** Thêm điều kiện `len(summary) < 100`; đổi embedding thành `Title: ... | Authors: ... | Summary: ...`; bổ sung xử lý author nested dictionary.
- **Cách xác minh sau khi sửa:** Assert toàn bộ summary có ít nhất 100 ký tự, embedding khớp đúng chuỗi kỳ vọng và sample nested author trả `Ada Lovelace`.
- **Điều học được:** Data contract phải được kiểm tra theo yêu cầu nghiệp vụ cụ thể, không chỉ dựa trên pseudo-code hoặc việc pipeline không phát sinh exception.

## 7. Hiểu biết về luồng end-to-end

Crossref API được Role 1 gọi và lưu nguyên raw response cùng raw records. Cleaning chuyển raw records thành schema ổn định, loại dữ liệu rác, tạo freshness fields và `text_for_embedding`. Role 5 dùng clean DataFrame để tạo MiniLM embeddings và nạp vào collection ChromaDB. Evaluation set chứa câu hỏi, đáp án chuẩn và ID tài liệu chuẩn; evaluator dùng ID này để tính retrieval hit, đồng thời so sánh câu trả lời với ground truth bằng token F1 và judge.

Quality checks kiểm tra tính đầy đủ, hợp lệ và duy nhất của dữ liệu, còn freshness monitoring tập trung vào độ tuổi/ngày xuất bản của corpus. Baseline, corrupted và repaired phải dùng cùng test set để khác biệt metric phản ánh thay đổi dữ liệu, không phải thay đổi câu hỏi. Repair chỉ được xem là thành công khi dữ liệu được tái tạo từ raw snapshot, quality/freshness signals phục hồi và các metric/answer artifacts của repaired được cải thiện so với corrupted, lý tưởng là tiến gần baseline.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0 | 0.0 | 1.0 | Cùng test set cho thấy thay đổi đến từ corpus chứ không phải câu hỏi. |
| `mean_token_f1` | 1.0 | 0.0 | 1.0 | Clean/repaired answer khớp ground truth; corrupted answer không còn khớp. |
| `judge_accuracy` | 1.0 | 0.0 | 1.0 | LLM judge chạy qua OpenRouter `o4-mini`, 0/9 lượt fallback. |
| `mean_judge_score` | 5 | 1 | 5 | Answer quality phục hồi hoàn toàn sau khi build lại từ raw. |
| Quality checks | PASS | FAIL | PASS | Corrupted vi phạm uniqueness, title/summary validity, completeness và freshness. |
| Freshness status | FRESH | STALE | FRESH | Ba stale dates làm corrupted stale; clean lại khôi phục ngày nguồn. |

### Kết luận từ số liệu

`drop_latest_record` ảnh hưởng trực tiếp nhất tới bộ test hiện tại vì ba evaluation samples tham chiếu ba paper mới nhất đã bị xóa khỏi corrupted corpus. Vì document IDs không còn trong index, `retrieval_hit_rate` giảm từ 1.0 xuống 0.0; answer metrics cũng giảm theo. Các mutation blank/noisy summary và truncated title đồng thời tạo quality signals rõ ràng, giúp phân biệt lỗi dữ liệu với lỗi model.

Repair chạy lại chính cleaning contract trên raw snapshot, khôi phục 24 records, ID, title, summary, publication date và `text_for_embedding`. Trên cùng `data/eval/test_set.json`, retrieval và answer metrics trở về baseline. Điều này xác nhận clean schema và ground-truth document identity ổn định là điều kiện để comparison có ý nghĩa.

Kết quả khác kỳ vọng là cả 24 record nguồn đều thiếu category, nên baseline/repaired vẫn có một warning `categories_not_null`. Đây là warning chứ không phải error; nhóm không tự suy đoán category và không tạo category question có ground truth rỗng.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Clean schema là contract chung; thay đổi tên cột, document identity hoặc format ngày có thể làm hỏng toàn bộ index, evaluation và observability phía sau.
2. Data quality không nên chỉ kiểm tra file có tồn tại mà phải đo null, duplicate, độ dài nội dung, tính hợp lệ của ngày và freshness.
3. RAG phụ thuộc trực tiếp vào chất lượng `text_for_embedding` và sự ổn định của `paper_id`; dữ liệu nhiễu hoặc ground truth sai làm cả retrieval lẫn đánh giá mất ý nghĩa.

### Nếu có thêm thời gian

Tôi sẽ bổ sung unit tests cho cleaning với các trường hợp title chứa nested markup, ngày sai, author thiếu `given`/`family`, DOI trùng và summary đúng biên 99/100 ký tự. Test set cũng nên có thêm nhiều sample mỗi loại khi corpus lớn hơn để metric bớt nhạy với một document duy nhất.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận đã nêu đều có artifact hoặc trạng thái kiểm chứng rõ ràng.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc thành viên khác.

**Họ và tên:** Đào Thị Trang  
**Ngày xác nhận:** 2026-08-06
