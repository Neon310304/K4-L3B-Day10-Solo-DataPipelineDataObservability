# Báo cáo thực hiện — Data Pipeline & Data Observability for RAG

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Trần Quốc Vượng |
| Mã học viên | 2A202602522 |
| Tên nhóm | solo |
| Repository | [K4-L3B-Day10-Solo-DataPipelineDataObservability](https://github.com/Neon310304/K4-L3B-Day10-Solo-DataPipelineDataObservability) |
| Ngày hoàn thành | 26/09/2026 |
| Phạm vi | Thu thập và làm sạch dữ liệu, kiểm định chất lượng, đánh giá RAG, mô phỏng lỗi và phục hồi |

## Công việc và sản phẩm

| Thành phần | Đầu vào và xử lý | Sản phẩm kiểm chứng |
| --- | --- | --- |
| Crossref | Gọi REST API; bóc tách DOI, tiêu đề, tóm tắt, tác giả, lĩnh vực, ngày xuất bản; dùng snapshot khi API lỗi | [JSON gốc](../data/raw/crossref_response.json), [24 PaperRecord](../data/raw/crossref_records.json) |
| Làm sạch | Chuẩn hóa văn bản/ngày, tính `age_days`, ghép năm trường vào `text_for_embedding`, loại DOI trùng | [24 dòng sạch](../data/clean/papers_clean.csv) |
| Kiểm định | Great Expectations 1.x Ephemeral Context cùng freshness SLA | [Báo cáo quality baseline](../data/quality/baseline_quality_report.json) |
| Benchmark và truy xuất | Sinh 10 câu hỏi thuộc bốn dạng; embedding MiniLM và lưu ChromaDB; đo Hit Rate, Token F1 | [Test set](../data/eval/test_set.json), [metrics baseline](../data/results/baseline_metrics.json) |
| Thí nghiệm lỗi | Tiêm sáu loại lỗi vào dữ liệu đã làm sạch; đánh giá trên cùng benchmark | [Nhật ký lỗi](../data/results/corruption_log.json), [metrics corrupted](../data/results/corrupted_metrics.json) |
| Phục hồi | Tái tạo dữ liệu từ JSON gốc, đối chiếu với baseline và đánh giá lại | [Metrics repaired](../data/results/repaired_metrics.json), [báo cáo ba trạng thái](../data/reports/corruption_report.md) |

Các hàm thực hiện nằm ở [crossref.py](../src/ingestion/crossref.py), [cleaning.py](../src/ingestion/cleaning.py), [corruption.py](../src/ingestion/corruption.py), [quality.py](../src/observability/quality.py), [testset.py](../src/evaluation/testset.py), [phase1.py](../src/pipelines/phase1.py) và [corruption_flow.py](../src/pipelines/corruption_flow.py).

## Thiết kế và luồng dữ liệu

Crossref trả về `message.items`. Mỗi mục hợp lệ được đổi thành `PaperRecord` với DOI làm `paper_id`; thẻ HTML/XML trong abstract được gỡ bỏ. Nếu `subject` vắng mặt, trường `type` của Crossref được dùng làm `categories`, nên lĩnh vực trong vài câu hỏi chỉ phản ánh loại ấn phẩm. Payload API được lưu thành byte gốc trước khi các bản ghi bóc tách được ghi ra tệp khác. Khi cần chạy lại, pipeline có thể đọc snapshot và tránh gọi API thêm.

Hàm làm sạch loại khoảng trắng thừa, chuẩn hóa ngày thành `YYYY-MM-DD`, tính `age_days = (run_date - published).days` và bỏ DOI trùng. `text_for_embedding` gồm Title, Authors, Published, Categories và Summary. DataFrame sạch là đầu vào của quality gate, bộ câu hỏi và vector index.

Quality gate dùng `gx.get_context(mode="ephemeral")` trên Pandas DataFrame. Sáu phép kiểm cụ thể thuộc bốn loại expectation: số dòng từ 5 đến 5.000; các cột `paper_id`, `title`, `text_for_embedding` không null; `paper_id` duy nhất; `summary` dài tối thiểu 30 ký tự. Freshness đánh dấu lỗi khi hơn 25% bản ghi có `age_days > 180`. Chỉ khi baseline đạt kiểm định mới tiếp tục lập chỉ mục và đánh giá.

Bộ 10 câu hỏi có `ground_truth_doc_ids` là DOI và phân bố theo `summary`, `authors`, `date`, `categories`. Cùng một test set được dùng ở cả ba trạng thái; báo cáo Phase 2 ghi SHA-256 của tệp benchmark để đối chiếu. Mỗi trạng thái dùng collection ChromaDB riêng để tránh dữ liệu của thí nghiệm này lẫn vào thí nghiệm khác.

## Quyết định kỹ thuật

Giữ snapshot API độc lập với dữ liệu đã chuẩn hóa là điểm tựa phục hồi. Phương án gọi lại Crossref sau khi dữ liệu hỏng phụ thuộc mạng, có thể bị giới hạn truy cập và có thể nhận tập bài báo đã thay đổi. Đọc snapshot cho phép tái tạo cùng tập DOI, so sánh các trường `paper_id`, `title`, `summary`, `published`, `text_for_embedding` với baseline rồi mới xác nhận phục hồi. Kết quả kiểm định sau phục hồi là PASS và 24/24 bản ghi quay lại chỉ mục.

## Cách chạy và bằng chứng

```powershell
python script/run_phase1.py
python script/run_corruption_flow.py
python -m unittest discover -s tests -v
```

Hai script đã sinh [báo cáo Phase 1](../data/reports/phase1_report.md) và [báo cáo corruption/repair](../data/reports/corruption_report.md). Bộ kiểm thử có 12 test đã qua. Phase 1 đọc 24 bản ghi, tạo 24 dòng sạch và 10 câu hỏi; Phase 2 tạo 21 dòng trong trạng thái corrupted rồi khôi phục 24 dòng.

Trong lúc chạy, quá trình tải mô hình embedding bị chặn bởi kết nối mạng trong môi trường thực thi hạn chế (`WinError 10061`). Chạy lại pipeline với quyền truy cập mạng đã cho phép nạp mô hình và tạo đủ artifact. Chưa cấu hình `GOOGLE_API_KEY`, nên điểm judge hiện tại dùng heuristic fallback; Ragas chưa được bật. Những điểm này được ghi rõ để không hiểu nhầm điểm judge là kết quả từ LLM.

## Kết quả và phân tích

| Chỉ số | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| Số câu hỏi | 10 | 10 | 10 |
| Bản ghi lập chỉ mục | 24 | 21 | 24 |
| Retrieval Hit Rate | 100% | 60% | 100% |
| Mean Token F1 | 1.000 | 0.600 | 1.000 |
| Judge accuracy (heuristic) | 100% | 60% | 100% |
| Mean judge score (1–5) | 5.00 | 3.40 | 5.00 |
| Quality gate | PASS | FAIL | PASS |
| Dòng cũ hơn 180 ngày | 0/24 | 8/21 | 0/24 |
| Freshness SLA | PASS | FAIL | PASS |

Nhật ký lỗi ghi 5 dòng bị bỏ vì mới nhất, 3 tóm tắt bị xóa, 3 tóm tắt bị chèn nhiễu, 3 tiêu đề bị cắt ngắn, 8 ngày xuất bản bị làm cũ và 2 dòng bị nhân đôi. Sau tiêm lỗi, expectation về DOI duy nhất và độ dài tóm tắt thất bại; tỉ lệ bản ghi cũ là 38,1%, vượt ngưỡng 25%. Hit Rate và Token F1 cùng giảm từ 1,0 xuống 0,6. Sau tái tạo từ snapshot, quality/freshness đều PASS và hai chỉ số cùng trở về 1,0.

`eval_004` là ví dụ của silent failure: retrieval không lấy được DOI cần thiết nhưng Token F1 vẫn bằng 1,0 do văn bản category của nguồn sai trùng với đáp án chuẩn. Vì vậy, Token F1 riêng lẻ không đủ xác nhận câu trả lời có đúng nguồn. Sáu lỗi đều được ghi vào log, còn số liệu hiện tại không tách riêng tác động của từng lỗi; không thể kết luận lỗi nào gây suy giảm mạnh nhất chỉ từ phép đo tổng hợp này.

Điểm baseline cao còn phụ thuộc cách xây benchmark: câu hỏi nêu chính xác tiêu đề và đường trả lời ưu tiên tra cứu tiêu đề, sau đó trích metadata đã lập chỉ mục. Kết quả xác nhận pipeline hoạt động và phục hồi nhất quán trên bài lab; chưa đánh giá khả năng tổng quát với câu hỏi diễn đạt lại hoặc không nêu tiêu đề.

## Hướng cải thiện

Tạo thêm câu hỏi diễn đạt lại, không chứa tiêu đề chính xác; chấm đồng thời độ đúng câu trả lời và DOI nguồn; đo tác động từng loại lỗi trong các lượt chạy riêng. Khi có API key phù hợp, chạy thêm LLM judge và Ragas để đối chiếu với heuristic hiện tại. Mọi khóa truy cập chỉ đặt trong `.env`, không ghi vào tài liệu hay artifact.
