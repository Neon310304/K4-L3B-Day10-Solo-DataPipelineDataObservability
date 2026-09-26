# Data Pipeline & Data Observability for RAG

| Thông tin | Nội dung |
| --- | --- |
| Người thực hiện | Trần Quốc Vượng |
| Mã học viên | 2A202602522 |
| Tên nhóm | solo |
| Ngày hoàn thành | 26/09/2026 |

Dự án thu thập metadata bài báo từ Crossref, lưu bản gốc để truy vết, chuẩn hóa dữ liệu, lập chỉ mục ChromaDB và đánh giá chất lượng truy xuất/câu trả lời. Thí nghiệm tiêm sáu loại lỗi dữ liệu cho thấy hiệu năng giảm; pipeline sau đó phục hồi từ snapshot gốc và đo lại bằng cùng bộ câu hỏi.

## Luồng xử lý

```text
Crossref REST API hoặc snapshot offline
  → JSON gốc + PaperRecord
  → làm sạch, khử trùng lặp, tính age_days
  → Great Expectations 1.x + freshness SLA
  → embedding MiniLM / ChromaDB
  → bộ 10 câu hỏi ground truth
  → Baseline → Corrupted → Repaired
  → metrics, nhật ký lỗi, báo cáo
```

Snapshot tại `data/raw/crossref_response.json` giữ nguyên JSON API. Khi API lỗi hoặc bị giới hạn truy cập, bước ingest có thể dùng snapshot này. Bản ghi đã bóc tách được lưu riêng tại `data/raw/crossref_records.json`.

## Cài đặt và chạy

Yêu cầu Python 3.11–3.13. Tại thư mục gốc dự án, dùng một trong hai cách:

```powershell
uv sync --locked
```

Hoặc tạo môi trường ảo và cài package ở chế độ phát triển:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Trên Linux/macOS, thay lệnh kích hoạt bằng `source .venv/bin/activate`. Sao chép `.env.example` thành `.env` để cấu hình riêng; không đưa API key vào repository. Hai pipeline và bộ kiểm thử chạy bằng:

```powershell
python script/run_phase1.py
python script/run_corruption_flow.py
python -m unittest discover -s tests -v
```

Chạy Phase 1 trước Phase 2. Hai bước đo lường đã chạy với chế độ judge heuristic khi chưa cấu hình khóa LLM; Ragas chỉ chạy khi bật `RUN_RAGAS=1` và có cấu hình phù hợp.

ChromaDB lưu chỉ mục cục bộ trong `data/chroma/`. Các file cơ sở dữ liệu sinh khi chạy được Git bỏ qua; chạy lại Phase 1 và Phase 2 sẽ tạo lại các collection từ dữ liệu đã lưu.

## Kết quả đã ghi nhận

| Chỉ số | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| Bản ghi lập chỉ mục | 24 | 21 | 24 |
| Câu hỏi benchmark | 10 | 10 | 10 |
| Retrieval Hit Rate | 100% | 60% | 100% |
| Mean Token F1 | 1.000 | 0.600 | 1.000 |
| Judge accuracy (heuristic) | 100% | 60% | 100% |
| Quality gate | PASS | FAIL | PASS |
| Bản ghi cũ hơn 180 ngày | 0/24 | 8/21 | 0/24 |

Sáu lỗi được mô phỏng gồm bỏ bài báo mới nhất, xóa tóm tắt, chèn nhiễu, cắt ngắn tiêu đề, làm cũ ngày xuất bản và nhân đôi dòng. Quality gate kiểm tra số lượng dòng, giá trị bắt buộc, DOI duy nhất, độ dài tóm tắt và tỉ lệ dữ liệu cũ tối đa 25%. Sau phục hồi, dữ liệu sạch và các chỉ số trở về mức baseline. Bộ kiểm thử hiện có 12 test đã chạy thành công.

Benchmark đặt tiêu đề bài báo trong câu hỏi và đường trả lời ưu tiên tra cứu tiêu đề chính xác. Vì vậy, điểm 100% xác nhận luồng xử lý và tính nhất quán metadata của bài lab; chưa chứng minh hiệu năng trên câu hỏi chưa từng thấy. Câu `eval_004` ở trạng thái corrupted có Token F1 bằng 1 dù truy xuất sai DOI, cho thấy cần đọc cả chỉ số retrieval và chất lượng câu trả lời.

## Artifact và tài liệu

| Nội dung | Đường dẫn |
| --- | --- |
| Dữ liệu sạch | [papers_clean.csv](data/clean/papers_clean.csv) |
| Bộ câu hỏi kiểm thử | [test_set.json](data/eval/test_set.json) |
| Kết quả baseline | [baseline_metrics.json](data/results/baseline_metrics.json) |
| Nhật ký lỗi | [corruption_log.json](data/results/corruption_log.json) |
| Báo cáo Phase 1 | [phase1_report.md](data/reports/phase1_report.md) |
| Báo cáo đối chiếu ba trạng thái | [corruption_report.md](data/reports/corruption_report.md) |
| Báo cáo thực hiện | [2A202602522_TranQuocVuong.md](report/2A202602522_TranQuocVuong.md) |
| Báo cáo cá nhân theo Bước 9 | [individual_2A202602522_TranQuocVuong.md](reports/individual_2A202602522_TranQuocVuong.md) |
| Thông tin nhóm | [TEAM.md](docs/TEAM.md) |
| Báo cáo dự án | [group_report.md](report/group_report.md) |

Mã nguồn chính nằm trong `src/ingestion/`, `src/observability/`, `src/evaluation/` và `src/pipelines/`. Các tệp `.env` và khóa truy cập phải được giữ riêng trên máy chạy.
