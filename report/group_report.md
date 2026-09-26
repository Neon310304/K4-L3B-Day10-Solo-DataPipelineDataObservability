# Báo cáo dự án — nhóm solo

## 1. Thông tin bài nộp

| Thông tin | Nội dung |
| --- | --- |
| Lớp/bài lab | K4-L3B / Day 10 |
| Tên nhóm | solo |
| Thành viên | Trần Quốc Vượng — 2A202602522 |
| Repository | [K4-L3B-Day10-Solo-DataPipelineDataObservability](https://github.com/Neon310304/K4-L3B-Day10-Solo-DataPipelineDataObservability) |
| Ngày hoàn thành phần kỹ thuật | 26/09/2026 |
| Báo cáo cá nhân | [2A202602522_TranQuocVuong.md](2A202602522_TranQuocVuong.md) |

## 2. Tóm tắt kết quả

Pipeline đã lấy và bảo toàn 24 bản ghi học thuật từ Crossref, chuẩn hóa thành 24 dòng sạch, tạo embedding MiniLM và lập chỉ mục ChromaDB. Bộ benchmark gồm 10 câu hỏi ở bốn dạng `summary`, `authors`, `date`, `categories`. Phase 1 ghi Retrieval Hit Rate 100% và Mean Token F1 1,000; quality gate Great Expectations 1.x và freshness đều đạt. Phase 2 tiêm sáu dạng lỗi có nhật ký theo DOI, tạo tập corrupted 21 dòng. Khi đánh giá bằng cùng benchmark, Hit Rate còn 60% và Token F1 còn 0,600. Quality gate phát hiện DOI trùng, tóm tắt quá ngắn và tỉ lệ bài báo cũ 8/21 = 38,1%, vượt SLA 25%. Phục hồi từ snapshot API ban đầu đưa dữ liệu về 24 dòng; các chỉ số trở lại 100% và 1,000, quality/freshness đều đạt. Kết quả judge hiện là heuristic fallback vì chưa cấu hình API key; Ragas chưa được bật. Bộ câu hỏi nêu chính xác tiêu đề bài báo nên điểm baseline chỉ chứng minh luồng xử lý và tính nhất quán metadata của bài lab, chưa phản ánh khả năng tổng quát trên câu hỏi mới.

## 3. Kiến trúc và trách nhiệm các khối

```text
Crossref REST API / snapshot
  → raw response + PaperRecord
  → clean DataFrame + age_days + text_for_embedding
  → Great Expectations + freshness SLA
  → MiniLM embeddings + ChromaDB
  → benchmark 10 câu + baseline metrics
  → corruption + đánh giá lại
  → repair từ raw response + đối chiếu ba trạng thái
```

| Khối | Input → xử lý | Output |
| --- | --- | --- |
| Ingestion | Crossref `message.items` → parse DOI, tiêu đề, abstract, tác giả, loại ấn phẩm, ngày | [API JSON](../data/raw/crossref_response.json), [PaperRecord JSON](../data/raw/crossref_records.json) |
| Cleaning | PaperRecord → bỏ HTML/XML, chuẩn hóa ngày/khoảng trắng, loại DOI trùng | [papers_clean.csv](../data/clean/papers_clean.csv) |
| Observability | DataFrame → 6 phép kiểm GX và freshness SLA | [baseline quality](../data/quality/baseline_quality_report.json) |
| Index/evaluation | 24 dòng sạch → MiniLM/ChromaDB, 10 câu hỏi và metrics | [test_set.json](../data/eval/test_set.json), [baseline_metrics.json](../data/results/baseline_metrics.json) |
| Corruption/repair | Dữ liệu sạch → sáu lỗi; snapshot API → phục hồi | [corruption_log.json](../data/results/corruption_log.json), [repaired_metrics.json](../data/results/repaired_metrics.json) |
| Orchestration/reporting | Chạy Phase 1 rồi Phase 2 | [phase1_report.md](../data/reports/phase1_report.md), [corruption_report.md](../data/reports/corruption_report.md) |

Các khối trên được tích hợp trong repository của Trần Quốc Vượng; thông tin phân công và đường dẫn bằng chứng nằm tại [TEAM.md](../docs/TEAM.md).

## 4. Cấu hình và lệnh tái hiện

| Cấu hình | Giá trị đã dùng |
| --- | --- |
| Python | 3.12.6; project hỗ trợ 3.11–3.13 |
| Package | `uv sync --locked` |
| `LLM_PROVIDER` / `LLM_MODEL` | `gemini` / `gemini-2.5-flash` trong `.env.example`; không có khóa LLM để gọi judge |
| Judge thực tế | Heuristic fallback |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Crossref query | `agentic retrieval augmented generation large language model` |
| Số bản ghi tối đa / `top_k` | 24 / 4 |
| Freshness SLA | Cũ hơn 180 ngày; tối đa 25% |
| Random seed | Không dùng; chọn bản ghi/lỗi theo thứ tự ổn định |

```powershell
uv sync --locked
python script/run_phase1.py
python script/run_corruption_flow.py
python -m unittest discover -s tests -v
```

Phase 1 và Phase 2 đã chạy thành công, tạo các artifact liên kết ở trên; 12 test đã qua. [Báo cáo Phase 1](../data/reports/phase1_report.md) ghi thời điểm 2026-09-26 04:57:42 UTC; [báo cáo Phase 2](../data/reports/corruption_report.md) ghi 2026-09-26 05:08:42 UTC. `.env` và khóa truy cập không được đưa vào báo cáo.

## 5. Nguồn dữ liệu, schema và quy tắc làm sạch

Nguồn là Crossref REST API `https://api.crossref.org/works`, với truy vấn trên và bộ lọc bài có abstract xuất bản trong 180 ngày gần thời điểm chạy. Client thử tối đa ba lần cho lỗi 429/5xx có backoff, rồi đọc snapshot nếu có. Payload gốc được lưu riêng; 24 bản ghi bóc tách thành `PaperRecord`. Ngày xuất bản lấy từ các trường `published`, `published-online`, `published-print`, `issued` hoặc `created` theo thứ tự ưu tiên.

| Trường | Quy tắc |
| --- | --- |
| `paper_id` | DOI bắt buộc; dùng làm ID tài liệu và khóa khử trùng lặp, không phân biệt hoa/thường |
| `title`, `summary` | Văn bản bắt buộc; bỏ tag HTML/XML và chuẩn hóa khoảng trắng |
| `authors`, `categories` | Danh sách văn bản; khi Crossref không có `subject`, dùng `type` cho categories |
| `published` | Ngày ISO `YYYY-MM-DD`; bản ghi ngày không hợp lệ bị bỏ |
| `age_days` | Số ngày giữa thời điểm chạy UTC và ngày xuất bản |
| `text_for_embedding` | Nối Title, Authors, Published, Categories, Summary theo năm dòng có nhãn |

Tập đang dùng có 24 raw records và 24 dòng sạch, tức không có dòng bị loại ở lượt baseline này. Có thể đối chiếu bằng [raw records](../data/raw/crossref_records.json) và [clean dataset](../data/clean/papers_clean.csv).

## 6. Thiết lập đánh giá

Bộ [test_set.json](../data/eval/test_set.json) có 10 câu hỏi: 3 summary, 3 authors, 2 date, 2 categories. Mỗi câu có `ground_truth_doc_ids` chứa DOI của bài báo đích. Truy xuất dùng `top_k=4`; Hit Rate đo DOI đích có xuất hiện trong tài liệu tìm được hay không, Token F1 đo độ trùng từ giữa câu trả lời và đáp án. Ba collection ChromaDB `papers-baseline`, `papers-corrupted`, `papers-repaired` tách dữ liệu của ba trạng thái. Cùng một test set được dùng xuyên suốt; SHA-256 của nó được ghi trong [báo cáo đối chiếu](../data/reports/corruption_report.md) để kiểm soát thay đổi benchmark.

## 7. Kết quả baseline

| Metric | Giá trị | Bằng chứng |
| --- | ---: | --- |
| Số bản ghi sạch/lập chỉ mục | 24/24 | [Phase 1 report](../data/reports/phase1_report.md) |
| Retrieval Hit Rate | 1,000 | [baseline metrics](../data/results/baseline_metrics.json) |
| Mean Token F1 | 1,000 | [baseline metrics](../data/results/baseline_metrics.json) |
| Judge accuracy / mean score | 1,000 / 5,00 | [baseline metrics](../data/results/baseline_metrics.json); heuristic fallback |
| Ragas | Chưa chạy | `RUN_RAGAS=1` chưa được bật |

## 8. Data quality và freshness

| Phép kiểm | Ngưỡng | Baseline | Corrupted | Repaired |
| --- | --- | --- | --- | --- |
| Số dòng | 5–5.000 | PASS | PASS | PASS |
| `paper_id`, `title`, `text_for_embedding` không null | 100% | PASS | PASS | PASS |
| `paper_id` duy nhất | 100% | PASS | FAIL | PASS |
| `summary` dài ít nhất 30 ký tự | 100% | PASS | FAIL | PASS |
| Freshness | Tỉ lệ `age_days > 180` ≤ 25% | PASS, 0/24 | FAIL, 8/21 | PASS, 0/24 |

Nguồn số liệu: [quality baseline](../data/quality/baseline_quality_report.json), [quality corrupted](../data/quality/corrupted_quality_report.json), [quality repaired](../data/quality/repaired_quality_report.json). Ngày xuất bản mới nhất ở baseline là 2026-09-15. Quality gate được chạy trước khi index baseline; collection corrupted vẫn được lập chỉ mục có chủ đích để đo ảnh hưởng của dữ liệu lỗi.

## 9. Tiêm lỗi và phục hồi

| Lỗi | Cách tạo | Số sự kiện |
| --- | --- | ---: |
| `drop_latest_records` | Bỏ 20% bài mới nhất, làm tròn lên | 5 |
| `blank_summary` | Xóa tóm tắt | 3 |
| `inject_noise` | Chèn token rác vào tóm tắt | 3 |
| `truncate_title` | Cắt tiêu đề còn tối đa 7 ký tự | 3 |
| `stale_date` | Lùi ngày xuất bản 365 ngày | 8 |
| `duplicate_rows` | Nhân đôi dòng | 2 |

[Nhật ký corruption](../data/results/corruption_log.json) ghi 24 sự kiện theo DOI, vị trí dòng và giá trị trước/sau. Tập bẩn có 21 dòng do bỏ 5 và thêm 2 dòng trùng. Hàm `repair_from_raw_snapshot()` parse lại [Crossref response gốc](../data/raw/crossref_response.json), làm sạch và ghi [dữ liệu repaired](../data/clean/papers_clean_repaired.csv). Pipeline so sánh các cột DOI, title, summary, published và embedding text với baseline, sau đó chạy lại quality, index và benchmark.

## 10. So sánh ba trạng thái

| Metric/signal | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| Số câu hỏi | 10 | 10 | 10 |
| Số bản ghi lập chỉ mục | 24 | 21 | 24 |
| Retrieval Hit Rate | 100% | 60% | 100% |
| Mean Token F1 | 1,000 | 0,600 | 1,000 |
| Judge accuracy (heuristic) | 100% | 60% | 100% |
| Mean judge score | 5,00 | 3,40 | 5,00 |
| Quality gate | PASS | FAIL | PASS |
| Freshness SLA | PASS | FAIL | PASS |

Corruption làm Hit Rate giảm 40 điểm phần trăm và Token F1 giảm 0,400; repair đưa hai chỉ số trở lại baseline. Các lỗi được tiêm cùng lúc nên số liệu tổng hợp không tách được mức đóng góp của từng lỗi. `eval_004` là trường hợp cần lưu ý: DOI đích không được truy xuất nhưng Token F1 vẫn 1,000 vì category từ nguồn sai trùng đáp án. Chỉ số câu trả lời phải được đọc cùng chỉ số nguồn.

## 11. Vấn đề tích hợp đã xử lý

Khi chạy pipeline trong môi trường thực thi hạn chế, tải mô hình embedding gặp `WinError 10061` do kết nối mạng bị chặn. Chạy lại với quyền truy cập mạng cho phép mô hình được nạp và cả hai script hoàn tất; bằng chứng là các tệp báo cáo/metrics đã sinh. Đây là lỗi môi trường, không phải lỗi dữ liệu. Judge LLM vẫn chưa được chạy vì không có API key; kết quả hiện tại được ghi rõ là heuristic.

## 12. Giới hạn và hướng cải thiện

| Giới hạn | Ảnh hưởng | Hướng kiểm chứng tiếp |
| --- | --- | --- |
| Câu hỏi nêu đúng tiêu đề và đường QA ưu tiên tra cứu tiêu đề | Điểm cao chưa cho thấy khả năng tổng quát | Tạo câu hỏi diễn đạt lại, che tiêu đề/DOI rồi đo lại |
| Một số `categories` lấy từ Crossref `type` | Trả lời phản ánh loại ấn phẩm thay vì chuyên ngành | Bổ sung taxonomy nguồn và đánh giá thủ công |
| Judge dùng heuristic; Ragas chưa chạy | Chưa có kiểm định bằng LLM | Cấu hình khóa riêng trong `.env`, bật Ragas và đối chiếu |
| Sáu lỗi được tiêm trong một lượt | Không quy được mức giảm cho từng lỗi | Chạy ablation từng lỗi trên cùng test set |

## 13. Trạng thái nộp bài

Các lệnh pipeline, artifact, metrics, quality reports và tài liệu đã được kiểm tra tại workspace. Trạng thái commit/push được xác nhận bằng lịch sử `main` trên GitHub khi nộp bài. Chưa có bằng chứng về demo trực tiếp hoặc nộp đường link lên VLearn LMS; hai việc này cần được thực hiện và xác nhận riêng. Không đưa `.env` hay khóa truy cập vào tài liệu.
