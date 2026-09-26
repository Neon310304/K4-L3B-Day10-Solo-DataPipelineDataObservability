# Báo cáo cá nhân — Trần Quốc Vượng

## 1. Thông tin

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Trần Quốc Vượng |
| Mã học viên | 2A202602522 |
| Lớp/bài lab | K4-L3B / Day 10 |
| Tên nhóm | solo |
| Repository | [K4-L3B-Day10-Solo-DataPipelineDataObservability](https://github.com/Neon310304/K4-L3B-Day10-Solo-DataPipelineDataObservability) |
| Ngày hoàn thành phần kỹ thuật | 26/09/2026 |
| Bản báo cáo theo mã học viên | [2A202602522_TranQuocVuong.md](2A202602522_TranQuocVuong.md) |

## 2. Phạm vi công việc và đầu ra

| Phần việc | Đầu vào | Đầu ra và trạng thái |
| --- | --- | --- |
| Crossref ingestion | REST API/snapshot | [24 PaperRecord](../data/raw/crossref_records.json), hoàn thành |
| Cleaning và lineage | PaperRecord | [24 dòng sạch](../data/clean/papers_clean.csv), hoàn thành |
| Quality/freshness | DataFrame sạch/bẩn/phục hồi | [Báo cáo quality](../data/quality/baseline_quality_report.json), hoàn thành |
| Benchmark và baseline | Dữ liệu sạch + ChromaDB | [10 câu hỏi](../data/eval/test_set.json), [metrics baseline](../data/results/baseline_metrics.json), hoàn thành |
| Corruption và repair | Dữ liệu sạch + raw snapshot | [Nhật ký 24 sự kiện](../data/results/corruption_log.json), [báo cáo ba trạng thái](../data/reports/corruption_report.md), hoàn thành |

Các phần được nối bằng [phase1.py](../src/pipelines/phase1.py) và [corruption_flow.py](../src/pipelines/corruption_flow.py). Báo cáo theo mã học viên ở trên trình bày chi tiết từng hàm và artifact.

## 3. Giải thích kỹ thuật

Crossref cung cấp JSON trong `message.items`. Ingestion bóc tách DOI, tiêu đề, abstract, tác giả, category và ngày, loại thẻ HTML/XML khỏi abstract, lưu nguyên payload API và lưu riêng danh sách `PaperRecord`. Nếu API lỗi hoặc trả 429, snapshot có thể dùng để tiếp tục. Cleaning chuẩn hóa khoảng trắng/ngày, bỏ DOI trùng, tính `age_days` và ghép Title, Authors, Published, Categories, Summary thành `text_for_embedding`.

Quality gate dùng Great Expectations 1.x Ephemeral Context trên DataFrame. Bốn loại expectation kiểm số dòng, ba cột bắt buộc không null, DOI duy nhất và tóm tắt dài tối thiểu 30 ký tự. Freshness đo phần bản ghi cũ hơn 180 ngày và thất bại khi phần này vượt 25%. Bộ câu hỏi có đáp án và DOI đích; Hit Rate đo truy xuất đúng DOI, Token F1 đo trùng khớp văn bản đáp án. Ba trạng thái dùng cùng test set và ba collection ChromaDB riêng.

## 4. Quyết định và sự cố

Quyết định chính là giữ [raw response](../data/raw/crossref_response.json) độc lập với dữ liệu đã làm sạch. Nếu gọi lại Crossref để sửa lỗi, tập dữ liệu có thể thay đổi hoặc gặp rate limit; snapshot cho phép tái tạo cùng bản gốc. Pipeline xác nhận năm cột cốt lõi của dữ liệu repaired bằng baseline, rồi đánh giá lại quality và metrics.

Trong môi trường chạy hạn chế, việc nạp mô hình MiniLM từng gặp `WinError 10061` do chặn kết nối mạng. Chạy lại với quyền truy cập mạng đã cho phép hai pipeline tạo artifact. Không có khóa LLM nên judge dùng heuristic fallback; Ragas chưa chạy. Các báo cáo không ghi đây là kết quả judge từ LLM.

## 5. Kết quả kiểm chứng

```powershell
python script/run_phase1.py
python script/run_corruption_flow.py
python -m unittest discover -s tests -v
```

Hai script đã tạo [báo cáo Phase 1](../data/reports/phase1_report.md) và [báo cáo corruption/repair](../data/reports/corruption_report.md); 12 test đã qua.

| Chỉ số | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| Bản ghi lập chỉ mục | 24 | 21 | 24 |
| Số câu hỏi | 10 | 10 | 10 |
| Retrieval Hit Rate | 100% | 60% | 100% |
| Mean Token F1 | 1,000 | 0,600 | 1,000 |
| Judge accuracy (heuristic) | 100% | 60% | 100% |
| Quality gate | PASS | FAIL | PASS |
| Bản ghi cũ hơn 180 ngày | 0/24 | 8/21 | 0/24 |

Corruption gồm bỏ 5 bản ghi mới, xóa 3 tóm tắt, chèn nhiễu vào 3 tóm tắt, cắt ngắn 3 tiêu đề, làm cũ 8 ngày xuất bản và thêm 2 dòng trùng. DOI trùng và tóm tắt rỗng làm GX thất bại; 8/21 bản ghi cũ làm freshness thất bại. Sau repair, mọi phép kiểm và chỉ số trở lại mức baseline. Không thể quy phần giảm 40 điểm phần trăm Hit Rate cho riêng một lỗi vì sáu lỗi được tiêm cùng lúc.

Ở `eval_004`, Token F1 vẫn 1,000 dù truy xuất sai DOI vì category trùng nhau. Điều này cho thấy phải đo nguồn và đáp án riêng. Điểm baseline 100% cũng phụ thuộc câu hỏi có nguyên tiêu đề bài báo; cần thử câu hỏi diễn đạt lại để kiểm tra khả năng tổng quát.

## 6. Hướng cải thiện và trạng thái còn lại

Ưu tiên tạo thêm benchmark không chứa tiêu đề, chấm cả DOI trích dẫn, chạy từng corruption riêng và đối chiếu judge heuristic với LLM/Ragas khi có API key đặt trong `.env`. Demo trực tiếp và nộp LMS chưa có bằng chứng trong repository; không đánh dấu là đã hoàn tất. Thông tin email cũng chưa được cung cấp nên không suy đoán.
