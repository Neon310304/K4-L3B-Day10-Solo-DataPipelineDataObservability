# Thông tin nhóm và phân công — Day 10

| Thông tin | Nội dung |
| --- | --- |
| Tên nhóm | Solo |
| Lớp/bài lab | K4-L3B / Day 10 |
| Người thực hiện | Trần Quốc Vượng |
| Mã học viên | 2A202602522 |
| Email | Chưa cung cấp |
| Repository | [K4-L3B-Day10-Solo-DataPipelineDataObservability](https://github.com/Neon310304/K4-L3B-Day10-Solo-DataPipelineDataObservability) |
| Báo cáo cá nhân | [2A202602522_TranQuocVuong.md](../report/2A202602522_TranQuocVuong.md) |
| Báo cáo theo đường dẫn Bước 9 | [individual_2A202602522_TranQuocVuong.md](../reports/individual_2A202602522_TranQuocVuong.md) |

## Tỷ lệ đóng góp tự khai

| Thành viên | Mã học viên | Tỷ lệ | Phạm vi |
| --- | --- | ---: | --- |
| Trần Quốc Vượng | 2A202602522 | 100% | Ingestion, cleaning, quality gate, benchmark, pipeline, corruption/repair và tài liệu |

Tỷ lệ trên được khai theo danh sách thành viên hiện có của nhóm **Solo**. Lịch sử commit trên GitHub là bằng chứng bổ sung khi kiểm tra bài nộp.

## Phạm vi và kết quả

| Mốc | Công việc | Bằng chứng |
| --- | --- | --- |
| CP0–CP1 | Cấu hình môi trường, lấy 24 bản ghi Crossref, lưu snapshot, làm sạch 24 dòng, kiểm định GX và freshness | [Raw records](../data/raw/crossref_records.json), [dữ liệu sạch](../data/clean/papers_clean.csv), [quality baseline](../data/quality/baseline_quality_report.json) |
| CP2–CP3 | Lập chỉ mục ChromaDB, sinh 10 câu hỏi, chạy baseline và xuất báo cáo | [Test set](../data/eval/test_set.json), [metrics baseline](../data/results/baseline_metrics.json), [báo cáo Phase 1](../data/reports/phase1_report.md) |
| CP4–CP5 | Tiêm sáu loại lỗi, đo suy giảm, phục hồi từ snapshot gốc và đối chiếu ba trạng thái | [Nhật ký lỗi](../data/results/corruption_log.json), [báo cáo đối chiếu](../data/reports/corruption_report.md) |
| CP6 | Tài liệu và artifact đã chuẩn bị; demo trực tiếp và nộp link LMS | Chưa có bằng chứng xác nhận hoàn tất ngoài repository |

Kết quả kiểm chứng: Retrieval Hit Rate và Mean Token F1 lần lượt là **1,0 → 0,6 → 1,0** ở ba trạng thái baseline, corrupted, repaired. Quality gate tương ứng **PASS → FAIL → PASS**. Điểm judge hiện dùng heuristic fallback do chưa cấu hình API key cho LLM evaluator; Ragas chưa chạy. Các kết quả này được mô tả chi tiết trong [báo cáo thực hiện](../report/2A202602522_TranQuocVuong.md).
