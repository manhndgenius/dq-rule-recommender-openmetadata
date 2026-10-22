# HƯỚNG DẪN SỬ DỤNG HỆ THỐNG DATA QUALITY RULE RECOMMENDER
## Tích hợp Nền tảng OpenMetadata & Lõi AI/Heuristic Backend VSF

> **Phiên bản:** 1.0.0  
> **Áp dụng cho:** Phân hệ Backend `VSF` & Giao diện mở rộng `OpenMetadata Custom UI`

---

## 1. Giới thiệu tổng quan

Hệ thống **Data Quality Rule Recommender** là giải pháp toàn diện giúp tự động hóa quá trình phát hiện, gợi ý, thẩm định và triển khai các bài kiểm tra chất lượng dữ liệu (Data Quality Test Cases) trực tiếp trên nền tảng **OpenMetadata**.

### Phân công vai trò giữa hai cấu phần chính:

| Cấu phần | Thư mục | Công nghệ | Vai trò & Nhiệm vụ chính |
|:---|:---|:---|:---|
| **DQ Engine Backend** | `VSF/` | Python, FastAPI, Pydantic, Neon/PostgreSQL | - Kết nối OpenMetadata REST API để trích xuất Schema & Profiling.<br/>- Điều phối **4 Rule Engines**: Basic (Heuristics/Regex), Advanced (LLM Router & Generators), Statistical (Drift analysis), NT Governance.<br/>- Biên dịch logic sang SQL chuẩn hóa qua **SQL Transpiler**.<br/>- Lưu trữ Candidate Rules, lịch sử Review (Accept/Edit/Reject) và Benchmark. |
| **Data Platform & Custom UI** | `OpenMetadata/` | Java Dropwizard, React/TypeScript, Ant Design | - Cung cấp nền tảng Siêu dữ liệu doanh nghiệp (Data Catalog, Profiler, Lineage, Test Suite).<br/>- Cung cấp trang giao diện mở rộng **Rule Recommender Page** (`/rule-recommender`) cho phép Data Steward rà soát, tinh chỉnh và xuất bản Test Cases trực tiếp bằng tài khoản OpenMetadata. |

---

## 2. Kiến trúc & Luồng hoạt động tổng thể

Hệ thống vận hành thông suốt qua **4 luồng tương tác chính**:

```mermaid
flowchart TB
    %% Styling
    classDef omCore fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#0d47a1;
    classDef beCore fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#1b5e20;
    classDef uiCore fill:#fff8e1,stroke:#f57f17,stroke-width:2px,color:#e65100;
    classDef extCore fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#4a148c;

    subgraph EXT ["HỆ THỐNG BÊN NGOÀI"]
        DS[("Data Source<br/>(PostgreSQL/MySQL...)")]:::extCore
        LLM["LLM Provider<br/>(Gemma 4 / DeepSeek API)"]:::extCore
    end

    subgraph OM_PLATFORM ["OPENMETADATA CORE PLATFORM"]
        Ingestion["Profiler & Ingestion Service"]:::omCore
        OMServer["OpenMetadata Server<br/>(Port 8585 / API v1)"]:::omCore
        Ingestion -->|Quét định kỳ| DS
        Ingestion -->|Đẩy Profiling| OMServer
    end

    subgraph VSF_BACKEND ["VSF DQ BACKEND SERVICE (Port 8000)"]
        API["FastAPI App"]:::beCore
        Engines["4 Rule Engines<br/>(Basic, Advanced, Stats, NT)"]:::beCore
        SQLTranspiler["SQL Dialect Transpiler"]:::beCore
        NeonDB[("PostgreSQL / Neon DB<br/>(Rules & Review History)")]:::beCore

        API --> Engines
        Engines --> SQLTranspiler
        Engines -.->|Truy vấn suy luận| LLM
        API --- NeonDB
    end

    subgraph OM_UI ["OPENMETADATA CUSTOM UI (Port 3000)"]
        UI["Rule Recommender Page<br/>(/rule-recommender)"]:::uiCore
        DQTab["Table Data Quality Tab<br/>(/table/.../profiler/data-quality)"]:::uiCore
    end

    %% Workflow Connections
    OMServer -->|Luồng 1: Trích xuất Schema & Profiling| API
    UI <-->|Luồng 2: Sinh & Duyệt Rule (Accept/Edit/Reject)| API
    UI -->|Luồng 3: Xuất bản trực tiếp Native Test Cases| OMServer
    OMServer -.->|Luồng 4: Đồng bộ & Quan sát kết quả| DQTab
```

### Chi tiết 4 luồng tích hợp:
1. **Luồng 1 (Trích xuất Metadata & Profiling):** Backend `VSF` gọi OpenMetadata Server để lấy cấu trúc bảng, kiểu dữ liệu, ràng buộc và các chỉ số thống kê (null count, distinct, min, max, mean, stddev). Backend chỉ đọc metadata và kết quả profiling sẵn có, **không truy cập dữ liệu thô (raw patient data)** nhằm đảm bảo an toàn bảo mật.
2. **Luồng 2 (Sinh & Duyệt quy tắc):** Giao diện Custom UI gửi yêu cầu phân tích kèm `tableFqn`. Backend điều phối các Engine tính toán, tạo danh sách `CandidateRule` kèm Điểm tin cậy (Confidence) và Lý do (Rationale). Khi người dùng thực hiện Duyệt (Accept), Sửa (Edit) hoặc Từ chối (Reject), trạng thái được lưu vào Neon DB.
3. **Luồng 3 (Xuất bản Test Cases trực tiếp):** Giao diện UI chuyển đổi các rule đã duyệt thành thực thể `TestCase` chuẩn của OpenMetadata (`columnValuesToBeBetween`, `columnValuesToBeNotNull`, `tableCustomSQLQuery`...) và gửi trực tiếp sang OpenMetadata Server bằng JWT Token phiên làm việc của người dùng.
4. **Luồng 4 (Đồng bộ giám sát):** Sau khi xuất bản, người dùng có thể điều hướng trực tiếp sang tab **Profiler & Data Quality** của bảng trên OpenMetadata để xem lịch sử chạy test và cảnh báo vi phạm.

---

## 3. Cài đặt và Khởi chạy Hệ thống

### 3.1. Khởi động Backend `VSF`

1. **Chuẩn bị cấu hình môi trường ([backend/.env](file:///d:/VSF/backend/.env)):**
   Tạo hoặc chỉnh sửa file `backend/.env` với các tham số kết nối cần thiết:
   ```ini
   # 1. Kết nối OpenMetadata Server
   OM_API=https://c3-app-009.duckdns.org/
   OM_TOKEN=<YOUR_ADMIN_PERSONAL_ACCESS_TOKEN>
   BOT_TOKEN=<YOUR_BOT_JWT_TOKEN>
   OM_TIMEOUT=30

   # 2. Kết nối Database PostgreSQL (Lưu trữ Rule & Review)
   DATABASE_URL=postgresql://neondb_owner:...@ep-cold-morning-...aws.neon.tech/neondb?sslmode=require
   POSTGRES_HOST=ep-cold-morning-...aws.neon.tech
   POSTGRES_PORT=5432
   POSTGRES_USER=neondb_owner
   POSTGRES_PASSWORD=...
   POSTGRES_DB=neondb
   POSTGRES_SSLMODE=require

   # 3. Cấu hình LLM Provider (Gemma 4 qua Codespaces hoặc DeepSeek Cloud)
   LLM_API=ollama
   LLM_BASE_URL=http://127.0.0.1:11435/v1
   LLM_MODEL=gemma4:e2b
   LLM_TIMEOUT_SECONDS=600
   LLM_MAX_RETRIES=1
   LLM_MAX_TOKENS=8192
   ROUTER_PROMPT_FILE=advanced_router_2.md

   # 4. Phạm vi dữ liệu mặc định
   FQN=healthcare_postgres.HealthCare.public
   ENABLE_ADVANCED_RULES=true
   ENABLE_STATISTICAL_RULES=false
   ```

2. **Chạy Migration Database:**
   ```powershell
   cd d:\VSF
   python scripts/migrate_database.py
   ```

3. **Khởi chạy FastAPI Backend Server:**
   ```powershell
   python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
   ```
   * Kiểm tra tình trạng kết nối: Truy cập [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health) (phải trả về `"status": "ok", "openmetadata_connected": true`).
   * Xem tài liệu Swagger API: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

---

### 3.2. Cấu hình Tunnel cho Local LLM (Nếu chạy Gemma trên Codespaces)

Nếu bạn chạy mô hình `gemma4:e2b` trên máy ảo GitHub Codespaces, cần mở đường truyền chuyển tiếp cổng từ Codespaces về máy Windows local:
```powershell
gh codespace ports forward 11434:11435 -c <ten-codespace-cua-ban>
```
* Cổng `11434` của Codespaces sẽ được ánh xạ về cổng cục bộ `127.0.0.1:11435`.
* Kiểm tra kết nối nhanh: Truy cập `http://127.0.0.1:11435/api/tags` thấy trả về `gemma4:e2b` là thành công.

---

### 3.3. Khởi động Giao diện Custom `OpenMetadata UI`

1. **Di chuyển vào thư mục mã nguồn UI:**
   ```powershell
   cd D:\OpenMetadata\openmetadata-ui\src\main\resources\ui
   ```

2. **Cài đặt thư viện phụ thuộc (lần đầu):**
   ```powershell
   yarn install
   ```

3. **Khởi chạy giao diện OpenMetadata:**
   ```powershell
   yarn start
   ```
   * Trình duyệt sẽ tự động mở trang chủ OpenMetadata tại: `http://localhost:3000`.

---

## 4. Hướng dẫn Thao tác Sử dụng trên Giao diện Web (Step-by-Step)

### Bước 1: Truy cập Phân hệ Rule Recommender
* Mở trình duyệt tại `http://localhost:3000`. Đăng nhập bằng tài khoản OpenMetadata của bạn.
* Trên thanh menu chính bên trái (Sidebar), tìm và nhấn chọn mục **Rule Recommender** (hoặc truy cập trực tiếp đường dẫn `http://localhost:3000/rule-recommender`).
* Giao diện làm việc tập trung xuất hiện với:
  * **Cây phân cấp dữ liệu (Rule Target Tree)** ở cột bên trái.
  * **Thanh tác vụ hàng loạt (Batch Operations Panel)** ở phía trên.
  * **Bảng danh sách quy tắc gợi ý (Recommendation Candidate Board)** ở trung tâm.

---

### Bước 2: Chọn Phạm vi Dữ liệu Mục tiêu (Target Scope)
Tại cây phân cấp bên trái, người dùng có thể linh hoạt chọn:
1. **Theo từng Bảng cụ thể (Table Scope):**
   * Mở rộng: `healthcare_postgres` $\rightarrow$ `HealthCare` $\rightarrow$ `public` $\rightarrow$ Chọn bảng (ví dụ: `patients`, `encounters`, `claims`...).
2. **Theo Schema hoặc Database (Bulk Scope):**
   * Tích chọn toàn bộ schema `public` để áp dụng quét hàng loạt cho tất cả các bảng.

---

### Bước 3: Kích hoạt Sinh quy tắc tự động (Rule Generation)

1. Chọn các bộ sinh quy tắc (Engine):
   * **Basic Rules (Khuyên dùng):** Tự động phát hiện các ràng buộc Not Null, Unique, Between/Range, In-Set, Length, Regex cho từng cột.
   * **Advanced Rules (LLM-powered):** Sử dụng LLM để phát hiện các ràng buộc logic phức tạp giữa nhiều cột:
     * *Temporal:* Quan hệ thời gian (ví dụ: `start_date <= end_date`, `birthdate <= deathdate`).
     * *Cross-Column:* Quan hệ số học/logic giữa hai cột (ví dụ: `healthcare_coverage <= healthcare_expenses`).
     * *Conditional Dependency:* Điều kiện phụ thuộc (ví dụ: `IF marital_status = 'M' THEN spouse_name IS NOT NULL`).
2. Thiết lập **Ngưỡng tin cậy tối thiểu (Min Confidence Threshold):** Mặc định là `0.6` (chỉ hiển thị các quy tắc có độ chắc chắn $\ge 60\%$).
3. Nhấn nút **"Generate Rules"**.
   * Hệ thống sẽ hiển thị biểu tượng tải dữ liệu. Khi hoàn tất, danh sách các **Candidate Rules** sẽ được điền vào bảng.

---

### Bước 4: Thẩm định & Tinh chỉnh Quy tắc (Human-in-the-Loop Review)

Mỗi hàng trong bảng quy tắc cung cấp đầy đủ thông tin minh bạch giúp người dùng dễ dàng ra quyết định:
* **Rule Type & Scope:** Tên loại bài kiểm tra OpenMetadata và phạm vi tác động (Bảng hay Cột).
* **Target Columns:** Danh sách các cột dữ liệu được kiểm tra.
* **Confidence:** Điểm tin cậy từ 0% đến 100%.
* **Reason (Lý do gợi ý):** Giải thích rõ ràng tại sao hệ thống đề xuất quy tắc này.
* **Evidence (Bằng chứng số liệu):** Các chỉ số thực tế trích xuất từ dữ liệu (ví dụ: `Null Count = 0`, `Min = 18`, `Max = 95`, `Distinct = 120`).
* **SQL Query (Câu lệnh kiểm tra vi phạm):** Câu truy vấn SQL biên dịch sẵn để kiểm tra các bản ghi lỗi.

#### 3 Thao tác Phê duyệt:
1. **Duyệt chấp thuận (Accept - Nút xanh lá có biểu tượng Check):**
   * Đồng ý với toàn bộ tham số do hệ thống đề xuất.
   * Quy tắc chuyển sang trạng thái `ACCEPTED`.
2. **Hiệu chỉnh tham số (Edit - Nút xanh dương có biểu tượng Cây bút):**
   * Cho phép Data Steward tự tay sửa đổi các tham số thực tế trước khi áp dụng:
     * Điều chỉnh ngưỡng `minValue`, `maxValue`.
     * Thêm/bớt các giá trị trong danh sách hợp lệ `allowedValues`.
     * Chỉnh sửa biểu thức Regex hoặc câu lệnh SQL vi phạm.
   * Nhấn **Save**, quy tắc chuyển sang trạng thái `EDITED`.
3. **Từ chối (Reject - Nút đỏ có biểu tượng Dấu gạch chéo):**
   * Bác bỏ các gợi ý không phù hợp với thực tế kinh doanh.
   * Quy tắc chuyển sang trạng thái `REJECTED` (không bị xuất bản lên hệ thống).

---

### Bước 5: Xuất bản trực tiếp Test Cases lên OpenMetadata (Direct Publish)

1. Tích chọn các quy tắc đã được phê duyệt (`ACCEPTED` hoặc `EDITED`).
2. Nhấn nút **"Publish to OpenMetadata"** ở góc trên bên phải bảng.
3. **Quá trình xuất bản tự động diễn ra:**
   * Giao diện UI ánh xạ chính xác quy tắc sang định nghĩa kiểm thử Native của OpenMetadata:
     * *Not Null* $\rightarrow$ `columnValuesToBeNotNull`
     * *Unique* $\rightarrow$ `columnValuesToBeUnique`
     * *Between/Range* $\rightarrow$ `columnValuesToBeBetween`
     * *Regex* $\rightarrow$ `columnValuesToMatchRegex`
     * *Length* $\rightarrow$ `columnValueLengthsToBeBetween`
     * *Advanced / Cross-Column* $\rightarrow$ `tableCustomSQLQuery`
   * Tự động gắn vào đúng `entityLink` của bảng hoặc cột (`<#E::table::{tableFqn}::columns::{column}>`).
   * Gắn trực tiếp vào **Test Suite** của bảng đó.
4. Trạng thái quy tắc trên bảng cập nhật thành **`APPLIED`**.

---

### Bước 6: Theo dõi và Kiểm tra Kết quả trên OpenMetadata

1. Sau khi xuất bản, nhấp vào liên kết điều hướng nhanh được cung cấp hoặc truy cập đường dẫn:
   ```text
   http://localhost:3000/table/{tableFqn}/profiler/data-quality
   ```
2. Toàn bộ các Test Cases vừa tạo sẽ xuất hiện ngay trong tab **Profiler & Data Quality** của bảng.
3. OpenMetadata sẽ tự động thực thi các Test Cases này theo lịch trình Ingestion Pipeline và thông báo cảnh báo khi có dữ liệu vi phạm.

---

### Bước 7: Quản trị Bộ Quy tắc Tiêu chuẩn (NT Governance)

* Nhấn nút **"NT Governance"** trên thanh công cụ để mở cửa sổ quản lý bộ quy chuẩn ngành (NT1 đến NT16).
* Data Steward có thể xem trạng thái tuân thủ, cấu hình tham số đặc thù cho từng quy tắc NT và kích hoạt kiểm tra độ phủ chất lượng dữ liệu.

---

## 5. Hướng dẫn Vận hành & Kiểm thử qua Dòng lệnh (CLI Scripts)

Dành cho Data Engineers muốn kiểm tra tính năng tự động từ thư mục `d:\VSF`:

```powershell
# 1. Chạy kiểm thử toàn bộ Basic Engine và luồng End-to-End
python -m pytest tests/test_basic_engine.py tests/test_end_to_end_flow.py -v

# 2. Kiểm thử riêng lẻ Advanced Rule Engine cho bảng patients
# 2.1. Kiểm tra Router phân tích candidates
python scripts/test_advanced_engine.py --table patients --router-only

# 2.2. Kiểm tra sinh rule quan hệ chéo cột (Cross-Column)
python scripts/test_advanced_engine.py --table patients --cross-column

# 2.3. Kiểm tra sinh rule quan hệ thời gian (Temporal)
python scripts/test_advanced_engine.py --table patients --temporal

# 2.4. Kiểm tra toàn bộ pipeline sinh rule kèm chuyển đổi câu truy vấn SQL
python scripts/test_advanced_engine.py --table patients --full-pipeline-sql

# 3. Chạy toàn bộ bộ test tự động (Automated Test Suite)
python -m pytest tests/ -v
```

---

## 6. Danh mục API Endpoints cốt lõi của Backend VSF

| Phương thức | Đường dẫn API | Mục đích sử dụng |
|:---|:---|:---|
| `GET` | `/api/v1/health` | Kiểm tra tình trạng server và kết nối OpenMetadata Live. |
| `GET` | `/api/v1/catalog/tables` | Lấy danh sách toàn bộ các bảng dữ liệu từ OpenMetadata. |
| `GET` | `/api/v1/context/{table_fqn}` | Lấy chi tiết metadata, kiểu dữ liệu, profiling và lineage của bảng. |
| `POST` | `/api/v1/recommendations/generate` | Sinh danh sách rule gợi ý (Basic + Advanced) cho 1 bảng. |
| `POST` | `/api/v1/review/{candidate_id}` | Gửi kết quả review của người dùng (`ACCEPT`, `EDIT`, `REJECT`). |
| `POST` | `/api/v1/test-cases/publish` | Xuất bản danh sách rule đã duyệt sang OpenMetadata Test Cases. |
| `POST` | `/api/v1/jobs/generation` | Khởi tạo tác vụ quét và sinh rule nền (Batch Job) cho nhiều bảng. |
| `GET` | `/api/v1/nt-rules` | Lấy danh sách và cấu hình bộ quy tắc chuẩn quản trị NT. |

---

## 7. Xử lý Sự cố Thường gặp (Troubleshooting)

### 1. Lỗi `401 Unauthorized` hoặc `Token Expired` khi gọi OpenMetadata
* **Hiện tượng:** Backend báo lỗi `OpenMetadata 401: Unauthorized`.
* **Khắc phục:** Đăng nhập vào OpenMetadata Web $\rightarrow$ Nhấp vào ảnh đại diện $\rightarrow$ **Settings** $\rightarrow$ **Users/Bots** $\rightarrow$ Tạo lại Personal Access Token. Cập nhật mã token mới vào biến `OM_TOKEN` trong file [backend/.env](file:///d:/VSF/backend/.env) và khởi động lại Backend.

### 2. Lỗi `Connection Refused: 127.0.0.1:11435` khi gọi LLM
* **Hiện tượng:** Backend không kết nối được tới mô hình Gemma trên Codespaces.
* **Khắc phục:** Tiến trình forward cổng bị đóng. Mở terminal Windows chạy lại lệnh:
  ```powershell
  gh codespace ports forward 11434:11435 -c <ten-codespace>
  ```

### 3. Lỗi LLM Router trả về `Invalid JSON response: ""`
* **Hiện tượng:** Suy luận bị ngắt giữa chừng hoặc trả về chuỗi rỗng do mô hình sinh quá nhiều token suy nghĩ (reasoning tokens) dẫn đến cạn kiệt context window.
* **Khắc phục:**
  1. Trong file [backend/.env](file:///d:/VSF/backend/.env), đảm bảo sử dụng file prompt rút gọn: `ROUTER_PROMPT_FILE=advanced_router_2.md`.
  2. Nâng kích thước ngữ cảnh của Ollama trên Codespaces lên 16k tokens (`PARAMETER num_ctx 16384`).

### 4. Giao diện OpenMetadata UI không hiển thị danh sách Rule
* **Hiện tượng:** Bấm "Generate Rules" nhưng không thấy kết quả hoặc báo lỗi mạng trên trình duyệt.
* **Khắc phục:**
  1. Kiểm tra Backend FastAPI đã chạy tại cổng 8000 hay chưa (`curl http://localhost:8000/api/v1/health`).
  2. Kiểm tra cấu hình kết nối API trong file `D:\OpenMetadata\openmetadata-ui\src\main\resources\ui\src\services\ruleRecommenderAPI.ts` đảm bảo trỏ đúng base URL `http://localhost:8000/api/v1`.
