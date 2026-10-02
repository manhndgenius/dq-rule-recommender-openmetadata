# KẾ HOẠCH PHÂN CHIA CÔNG VIỆC DỰ ÁN DATA QUALITY RULE RECOMMENDER (2 NGƯỜI)
**Thời gian thực hiện:** 30/09/2026 – 18/10/2026 (3 Tuần)  
**Căn cứ:** Dựa trên [Báo cáo định nghĩa và kế hoạch xây dựng sản phẩm]

---

## 1. NGUYÊN TẮC PHÂN CHIA & KIẾN TRÚC ENGINE ĐỘC LẬP

Để cả 2 thành viên đều tham gia phát triển Core Logic của sản phẩm mà **không bao giờ bị xung đột code hay nghẽn tiến độ**, hệ thống áp dụng kiến trúc **Pluggable Engine**:

```
                          ┌──────────────────────────────────────┐
                          │         TableContext (Input)         │
                          │   (Schema, Data Types, Profiling)    │
                          └──────────────────┬───────────────────┘
                                             │
                     ┌───────────────────────┴───────────────────────┐
                     ▼                                               ▼
       ┌───────────────────────────┐                   ┌───────────────────────────┐
       │   BASIC RULE ENGINE       │                   │   ADVANCED RULE ENGINE    │
       │   (Heuristic/Profiling)   │                   │   (LLM/Semantic/Prompt)   │
       │   👉 THÀNH VIÊN A         │                   │   👉 THÀNH VIÊN B         │
       └─────────────┬─────────────┘                   └─────────────┬─────────────┘
                     │                                               │
                     │  CandidateRule[]                              │  CandidateRule[]
                     └───────────────────────┬───────────────────────┘
                                             ▼
                               ┌───────────────────────────┐
                               │      RULE VALIDATOR       │
                               │  (Dedup, Conflict, Type)  │
                               │  👉 THÀNH VIÊN B          │
                               └─────────────┬─────────────┘
                                             ▼
                               ┌───────────────────────────┐
                               │    WEB UI & HUMAN REVIEW  │
                               │  (Accept / Edit / Reject) │
                               │  👉 THÀNH VIÊN A          │
                               └─────────────┬─────────────┘
                                             ▼
                               ┌───────────────────────────┐
                               │   OPENMETADATA INTEGRATION│
                               │   (Publish Test Cases)    │
                               │   👉 THÀNH VIÊN B         │
                               └───────────────────────────┘
```

1. **Khế ước chung (Common Interface):**
   - Cả 2 Engine đều kế thừa cùng một interface `BaseRuleEngine` và nhận đầu vào thống nhất `TableContext`, xuất ra danh sách `List[CandidateRule]`.
   - Do đó, Thành viên A viết `basic_engine.py` và Thành viên B viết `advanced_engine.py` hoàn toàn độc lập, có thể chạy song song hoặc chạy riêng rẽ từng module mà không ảnh hưởng lẫn nhau.
2. **Phát triển dựa trên Mock Data:**
   - Thành viên A có thể dựng UI và test luồng hiển thị bằng mock rules ngay từ đầu.
   - Thành viên B có thể test prompt và LLM generation qua CLI / Unit test với mock table context.

---

## 2. PHÂN VAI & TRÁCH NHIỆM CHÍNH (ROLE DEFINITION)

| Tiêu chí | **Thành viên A** | **Thành viên B** |
| :--- | :--- | :--- |
| **Phân bổ Engine** | **BASIC RULE ENGINE (Heuristic & Profiling-based)** | **ADVANCED RULE ENGINE (LLM & Semantic-based)** |
| **Các mảng phụ trách khác** | - **Web Frontend (UI/UX):** Màn hình chọn bảng, dashboard profiling, danh sách Rule Cards.<br>- **Human Review Flow:** Cơ chế tương tác Accept, Edit (chỉnh sửa tham số), Reject.<br>- **Quản lý trạng thái Candidate:** Lưu trữ tạm thời trạng thái review trước khi xuất bản.<br>- **Kịch bản Demo & Slide báo cáo:** Xây dựng luồng trải nghiệm người dùng cuối. | - **Database & Data Context Builder:** Setup DB (PostgreSQL, SQL Server), module đọc schema + tính profiling metrics.<br>- **Rule Validator:** Bộ lọc deduplication, kiểm tra type compatibility, phát hiện conflict giữa các rule.<br>- **Tích hợp OpenMetadata:** SDK/API chuyển đổi rule đã duyệt thành Test Case / Test Suite trên OpenMetadata.<br>- **Bộ dữ liệu kiểm nghiệm & Đánh giá:** Đo lường độ chính xác và tỷ lệ chấp nhận rule. |
| **Thư mục làm chủ** | `frontend/`, `backend/engine/basic_engine.py`, `backend/api/routes_ui.py` | `backend/engine/advanced_engine.py`, `backend/profiler/`, `backend/validator/`, `backend/integrations/openmetadata/`, `infra/` |
| **Công nghệ chính** | React / Next.js / Vanilla JS-CSS, Python (Heuristic rules logic) | Python (FastAPI, LangChain/OpenAI/Gemini API, OpenMetadata Python SDK, SQLAlchemy) |

---

## 3. CẤU TRÚC CODEBASE ĐỀ XUẤT ĐỂ TRÁNH XUNG ĐỘT

```text
data-quality-recommender/
├── contracts/                            <-- CHUNG (Ngày 1 cùng thống nhất)
│   ├── table_context.schema.json         # Định dạng chuẩn đầu vào Context
│   └── candidate_rule.schema.json        # Định dạng chuẩn đầu ra Candidate Rule
│
├── frontend/                             <-- THÀNH VIÊN A TOÀN QUYỀN
│   ├── src/
│   │   ├── components/                   # TableSelector, ProfilingStats, RuleCard, ReviewModal
│   │   ├── pages/                        # Home, Explore, ReviewDashboard, Evaluation
│   │   └── services/                     # Gọi API backend hoặc Mock data
│   └── package.json
│
├── backend/
│   ├── api/
│   │   ├── routes_ui.py                  <-- THÀNH VIÊN A (API quản lý review state: Accept/Edit/Reject)
│   │   └── routes_engine.py              <-- THÀNH VIÊN B (API context, orchestrate generate & OM push)
│   ├── profiler/                         <-- THÀNH VIÊN B (Context Builder đọc schema + metrics từ Postgres/SQL Server)
│   ├── engine/                           <-- CHIA RÕ MỖI NGƯỜI 1 FILE
│   │   ├── base.py                       # Interface BaseRuleEngine (chung)
│   │   ├── basic_engine.py               <-- THÀNH VIÊN A LÀM CHỦ (Thuật toán Heuristic / Profiling)
│   │   ├── advanced_engine.py            <-- THÀNH VIÊN B LÀM CHỦ (Prompt Engineering / LLM Output)
│   │   └── prompts/                      <-- THÀNH VIÊN B (System prompts, Few-shot templates)
│   ├── validator/                        <-- THÀNH VIÊN B (Dedup, Conflict, Column/Type validator)
│   └── integrations/
│       └── openmetadata/                 <-- THÀNH VIÊN B (Client map & push Test Case sang OpenMetadata)
│
├── infra/                                <-- THÀNH VIÊN B (Docker Compose: PostgreSQL, SQL Server test data)
└── tests/
    ├── test_basic_engine.py              <-- THÀNH VIÊN A viết test cho Basic Engine
    ├── test_advanced_engine.py           <-- THÀNH VIÊN B viết test cho Advanced Engine
    └── test_integration.py               <-- CẢ HAI phối hợp test khi ghép nối
```

---

## 4. CHI TIẾT KẾ HOẠCH THEO TIẾN ĐỘ 3 TUẦN (30/09 – 18/10/2026)

### GIAI ĐOÀN 1: NỀN TẢNG, DATA CONTEXT & BASIC RULE ENGINE (30/09 – 04/10/2026)
*Mục tiêu mốc M1: Cuối Tuần 1, chọn table/context $\rightarrow$ sinh và hiển thị được Basic Rule trên Web UI.*

| Thời gian | Thành viên A (UI & Basic Engine) | Thành viên B (Data Context, Advanced Engine & Infra) | Điểm chạm / Giao tiếp (Touchpoints) |
| :--- | :--- | :--- | :--- |
| **Ngày 30/09**<br>*(Khởi động)* | - Cùng chốt `candidate_rule.schema.json`.<br>- Thiết kế Wireframe/UI Flow cho Web UI (Chọn bảng $\rightarrow$ Xem Profiling $\rightarrow$ Sinh Rule $\rightarrow$ Review).<br>- Tạo mock data `mock_rules.json`. | - Cùng chốt `table_context.schema.json`.<br>- Setup Docker chạy PostgreSQL và SQL Server kèm dữ liệu mẫu thử nghiệm.<br>- Khởi tạo khung backend `FastAPI` và định nghĩa abstract class `BaseRuleEngine`. | **Họp chốt Contract chung:** Thống nhất 100% định dạng JSON Schema đầu vào/đầu ra trước khi code. |
| **Ngày 01-02/10**<br>*(Xây UI & Context)* | - Khởi tạo project Web Frontend (`frontend/`).<br>- Dựng UI Component: Chọn Database/Table, hiển thị Schema và thẻ thống kê Profiling metrics (dùng mock).<br>- Thiết kế giao diện danh sách thẻ Rule Candidate (Rule name, Column, Threshold, Reason, Evidence badge). | - Xây dựng **Context Builder** (`backend/profiler/`):<br>  + Kết nối PostgreSQL / SQL Server trích xuất schema (tên bảng, cột, datatype, nullable, description).<br>  + Tính toán metrics cơ bản (null_count, distinct_count, min, max, row_count).<br>- Mở endpoint API trả về `TableContext`. | Thành viên B bàn giao API lấy Table Context cho Thành viên A. Thành viên A kết nối UI với API thật. |
| **Ngày 03/10**<br>*(Basic Engine)* | - Xây dựng **Basic Rule Engine** (`basic_engine.py`):<br>  + Logic sinh `columnValuesToBeNotNull` (khi null_count = 0).<br>  + Logic sinh `columnValuesToBeUnique` (khi distinct_count = row_count).<br>  + Logic sinh `columnValuesToBeBetween` (min, max).<br>  + Logic sinh `columnValuesToBeInSet` (low cardinality).<br>  + Logic sinh `tableRowCountToBeBetween`.<br>- Tự sinh lý do (Reason) và bằng chứng (Evidence) cho mỗi rule. | - Nghiên cứu và thiết kế Prompt Template cho **Advanced Rule Engine**.<br>- Thử nghiệm prompt trên LLM API (OpenAI/Gemini) với context mẫu.<br>- Chuẩn bị schema structured output (JSON schema) cho LLM. | Thành viên A viết xong Basic Engine, tự nối trực tiếp vào Web UI để kiểm thử ngay. |
| **Ngày 04/10**<br>*(Milestone M1)* | **Kiểm tra mốc M1:** Web UI kết nối Backend, chọn bảng thật từ DB $\rightarrow$ hiển thị Profiling $\rightarrow$ bấm Generate $\rightarrow$ Basic Rule Engine sinh các candidate chuẩn xác trên giao diện. |  |

---

### GIAI ĐOÀN 2: ADVANCED RULE (LLM), VALIDATION & HUMAN REVIEW (05/10 – 11/10/2026)
*Mục tiêu mốc M2: Cuối Tuần 2, sản phẩm hoàn chỉnh end-to-end với Basic + Advanced + Validation + Review và Publish lên OpenMetadata.*

| Thời gian | Thành viên A (UI & Basic Engine) | Thành viên B (Data Context, Advanced Engine & Infra) | Điểm chạm / Giao tiếp (Touchpoints) |
| :--- | :--- | :--- | :--- |
| **Ngày 05-06/10**<br>*(Advanced Engine & Review UI)* | - Xây dựng tính năng **Human Review** trên Web UI:<br>  + Nút thao tác: `Accept` (xanh), `Reject` (đỏ), `Edit` (vàng).<br>  + Modal Dialog chỉnh sửa tham số của Rule (ngưỡng min, max, custom SQL expression) trước khi duyệt.<br>  + Quản lý trạng thái: `DRAFT`, `ACCEPTED`, `REJECTED`, `EDITED`.<br>  + Viết API lưu trữ trạng thái review tạm thời (`routes_ui.py`). | - Hoàn thiện **Advanced Rule Engine** (`advanced_engine.py`):<br>  + Gọi LLM sinh rule theo từng nhóm rule type.<br>  + Suy luận semantic từ tên cột, mô tả bảng.<br>  + Sinh Temporal / Cross-column rule (vd: `end_date >= start_date`).<br>  + Sinh Conditional Dependency (vd: `if status = 'PAID' then payment_date is not null`).<br>  + Bắt buộc LLM trả về Structured Output theo đúng `CandidateRule` schema. | Thành viên B cấp mock output hoặc test script của Advanced Engine để Thành viên A kiểm tra hiển thị cross-column rule trên UI. |
| **Ngày 07/10**<br>*(Validator)* | - Cập nhật giao diện Rule Card để hiển thị các huy hiệu/cảnh báo từ Validator (Huy hiệu `Validated`, `Warning: Trùng lặp`, `Conflict detected`).<br>- Thêm bộ lọc: Xem riêng Basic Rules, Advanced Rules, hoặc chỉ các Rule đã Accept. | - Xây dựng **Rule Validator** (`backend/validator/`):<br>  + Kiểm tra cột trong rule có tồn tại trong Schema không.<br>  + Kiểm tra tính tương thích kiểu dữ liệu (vd: rule số học không gắn cho cột chuỗi).<br>  + Khử trùng lặp (Deduplication) giữa Basic Engine và Advanced Engine.<br>  + Phát hiện xung đột logic giữa các candidate rules. | Thành viên B tích hợp Validator vào luồng tổng hợp candidate trước khi trả về cho UI. |
| **Ngày 08/10**<br>*(Tích hợp OpenMetadata)* | - Thiết kế màn hình tổng kết các Rule đã `ACCEPTED` kèm nút `Publish to OpenMetadata`.<br>- Hiển thị trạng thái phản hồi sau khi publish (thành công / lỗi kèm link tới Test Suite trên OpenMetadata). | - Xây dựng module **OpenMetadata Publisher** (`integrations/openmetadata/`):<br>  + Sử dụng OpenMetadata Python SDK / REST API.<br>  + Map các Rule đã Accept sang đúng định dạng `TestCase` của OpenMetadata (vd: `columnValuesToBeBetween`, `tableCustomSQLQuery`).<br>  + API endpoint `/api/rules/publish-to-openmetadata`. | Hai người test chung luồng: Review trên Web UI $\rightarrow$ Bấm Publish $\rightarrow$ Kiểm tra Test Case đã hiển thị trên giao diện OpenMetadata. |
| **Ngày 09-10/10**<br>*(Ghép nối E2E - M2)* | **Ghép toàn bộ luồng End-to-End:**<br>Web UI $\rightarrow$ Chọn Table $\rightarrow$ Kích hoạt cả Basic + Advanced Engine $\rightarrow$ Validator lọc $\rightarrow$ Human Review $\rightarrow$ Push OpenMetadata thành công.<br>Cùng nhau debug và tối ưu hóa trải nghiệm luồng chính. |  |

---

### GIAI ĐOÀN 3: ĐÁNH GIÁ, TỐI ƯU HÓA, HOÀN THIỆN DEMO & TÀI LIỆU (12/10 – 18/10/2026)
*Mục tiêu mốc M3: Đánh giá chất lượng rule trên nhiều bảng, bản demo mượt mà, slide báo cáo và kế hoạch bàn giao.*

| Thời gian | Thành viên A (UI & Basic Engine) | Thành viên B (Data Context, Advanced Engine & Infra) | Điểm chạm / Giao tiếp (Touchpoints) |
| :--- | :--- | :--- | :--- |
| **Ngày 12-13/10**<br>*(Evaluation & Testing)* | - Xây dựng trang Dashboard thống kê đánh giá (Tỷ lệ Accept %, Edit %, Reject % cho từng loại rule Basic vs Advanced).<br>- Test thao tác review trên 5-10 bảng dữ liệu thử nghiệm khác nhau, ghi nhận phản hồi UX. | - Chuẩn bị 5-10 bảng dữ liệu test phong phú (e-commerce, log, tài chính) trên PostgreSQL/SQL Server.<br>- Thống kê chất lượng LLM: Tỷ lệ rule sai ngữ nghĩa (hallucination), tỷ lệ candidate bị reject, thời gian phản hồi của LLM. | Họp đánh giá: So sánh hiệu quả giữa Basic Heuristic Engine và Advanced LLM Engine. |
| **Ngày 14/10**<br>*(Tối ưu 2 Engine)* | - Tối ưu hóa **Basic Rule Engine**: Tinh chỉnh các ngưỡng heuristic (thresholds) cho khoảng min/max và độ phủ null.<br>- Hoàn thiện UI micro-interactions, thông báo toast, loading animation. | - Tối ưu hóa **Advanced Rule Engine**: Refine Prompt template, bổ sung Few-shot examples để giảm tỷ lệ rule bị reject.<br>- Tối ưu bộ Rule Validator và xử lý ngoại lệ API (retry, timeout cho LLM). | Đo lại tỷ lệ Accept sau khi cả hai tối ưu 2 engine. |
| **Ngày 15-16/10**<br>*(Demo & Báo cáo)* | - Chuẩn bị kịch bản Demo hoàn chỉnh theo User Journey.<br>- Quay video demo dự phòng (backup walkthrough).<br>- Viết tài liệu hướng dẫn sử dụng giao diện người dùng. | - Hoàn thiện Logging chi tiết (thời gian chạy profiling, thời gian chạy LLM, rule sinh ra).<br>- Viết tài liệu kỹ thuật về cơ chế hoạt động của Advanced Engine, Validator và OpenMetadata mapping.<br>- Tổng hợp Limitations & hướng mở rộng. | Chạy thử nghiệm kịch bản Demo end-to-end ít nhất 2 lần cùng nhau. |
| **Ngày 17-18/10**<br>*(Nghiệm thu)* | **Tổng kết dự án:** Hoàn thiện Báo cáo tổng kết 3 tuần, hoàn thiện Slide thuyết trình và bàn giao source code. |  |

---

## 5. BẢNG PHÂN CÔNG CHI TIẾT THEO TÍNH NĂNG (RACI MATRIX)

*R (Responsible): Người trực tiếp thực hiện | A (Accountable): Người chịu trách nhiệm chính | C (Consulted): Người tham vấn đóng góp | I (Informed): Người nhận thông tin*

| Hạng mục công việc (Task) | Thành viên A | Thành viên B | Deliverable bàn giao |
| :--- | :---: | :---: | :--- |
| **1. Khế ước chung (JSON Schemas & BaseEngine)** | **A / R** | **R** | `table_context.schema.json`, `candidate_rule.schema.json`, `base.py` |
| **2. Database & Data Context Builder** | I | **A / R** | Docker PostgreSQL, SQL Server + module đọc metadata & profiling |
| **3. BASIC RULE ENGINE (Heuristic/Profiling)** | **A / R** | C | Module sinh Not Null, Unique, Between, In-set, Row Count |
| **4. ADVANCED RULE ENGINE (LLM/Semantic)** | C | **A / R** | Prompt templates, LLM Structured Output sinh Cross-column, Temporal |
| **5. Rule Validator (Dedup & Conflict)** | C | **A / R** | Module kiểm tra cột, type compatibility, dedup & conflict |
| **6. Web Frontend (Table Selector & Profiling UI)** | **A / R** | I | Màn hình chọn bảng, hiển thị schema và thẻ chỉ số profiling |
| **7. Web Frontend (Rule Cards & Badges)** | **A / R** | I | Thẻ hiển thị rule, reason, evidence và cảnh báo validation |
| **8. Cơ chế Human Review (Accept/Edit/Reject)** | **A / R** | C | Dialog chỉnh sửa param, quản lý trạng thái review |
| **9. Tích hợp Push Rule lên OpenMetadata** | C | **A / R** | SDK script map rule thành OpenMetadata Test Case qua API |
| **10. Đánh giá chất lượng (Evaluation)** | **R** | **A / R** | Số liệu so sánh tỷ lệ Accept/Reject giữa Basic vs Advanced Engine |
| **11. Kịch bản Demo, Slide & Báo cáo** | **A / R** | **R** | Kịch bản demo, video dự phòng, slide thuyết trình và tài liệu kỹ thuật |

---

## 6. QUY TẮC LÀM VIỆC ĐỂ TRÁNH MÂU THUẪN KỸ THUẬT

1. **Tuân thủ Interface `BaseRuleEngine`:**  
   - Cả Thành viên A (`basic_engine.py`) và Thành viên B (`advanced_engine.py`) đều triển khai hàm:
     ```python
     def generate_candidates(self, context: TableContext) -> List[CandidateRule]:
         pass
     ```
   - Điều này đảm bảo khi ghép vào bộ điều phối chung (`routes_engine.py` hoặc `orchestrator.py`), hệ thống chỉ cần gọi song song cả hai engine mà không bao giờ bị lỗi sai định dạng dữ liệu.
2. **Không sửa đè file của nhau:**  
   - Thành viên A toàn quyền trong `frontend/`, `backend/engine/basic_engine.py`, `backend/api/routes_ui.py`.
   - Thành viên B toàn quyền trong `backend/engine/advanced_engine.py`, `backend/profiler/`, `backend/validator/`, `backend/integrations/openmetadata/`, `infra/`.
3. **Daily Sync 15 phút đầu ngày:**  
   - Cập nhật tiến độ 2 engine và thống nhất tham số cho các rule đặc biệt.
4. **Quy định bàn giao (Hand-off Gate):**  
   - Basic Engine và Advanced Engine đều phải có Unit Test riêng chạy độc lập với mock `TableContext` trước khi merge vào nhánh chung `dev`.
