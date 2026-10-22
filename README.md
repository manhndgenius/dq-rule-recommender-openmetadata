# Data Quality Rule Recommender & Observability System

> **Hệ thống Tự động Gợi ý, Quản lý và Đồng bộ Data Quality Rules tích hợp OpenMetadata & LLM**  
> Phiên bản: `1.0.0` (Nhánh `feature/upgrade-advance`)

---

## 📌 Giới thiệu tổng quan

**Data Quality Rule Recommender** là giải pháp toàn diện giúp tự động hóa quá trình phát hiện, gợi ý, thẩm định và quản lý các quy tắc chất lượng dữ liệu (Data Quality Rules). Hệ thống kết hợp giữa **Heuristics / Thống kê**, **Quy tắc chuẩn hóa nghiệp vụ (NT Rules)** và **Trí tuệ nhân tạo (LLM Router & Specialized Generators)** nhằm tạo ra các bộ quy tắc chất lượng cao, có thể giải thích được và đồng bộ trực tiếp vào nền tảng siêu dữ liệu **OpenMetadata**.

### Điểm nổi bật của phiên bản Upgrade Advance:
- 🧠 **Hybrid Rule Engine**: Kết hợp Basic Engine (Not Null, Unique, Between, In-Set, Length, Row Count, Regex), Statistical Engine (Mean/Median drift), Advanced LLM Engine (Temporal, Cross-Column, Conditional Dependency) và NT Rules Engine.
- 🔄 **Tích hợp OpenMetadata Live 100%**: Đọc schema, profiling, lineage trực tiếp từ OpenMetadata API và xuất bản ngược lại dưới dạng các Test Case chuẩn hóa.
- ⚡ **Multi-Dialect SQL Transpiler & Validator**: Tự động sinh cú pháp SQL kiểm tra dữ liệu tương thích với PostgreSQL, Snowflake, BigQuery, MySQL, SQLite... cùng cơ chế kiểm định cú pháp nghiêm ngặt trước khi áp dụng.
- 👥 **Human-in-the-Loop Workflow**: Giao diện trực quan cho Data Steward/Engineer duyệt (Accept), tinh chỉnh tham số (Edit), từ chối (Reject) và theo dõi lịch sử phiên bản.
- 📊 **Benchmark & Evaluation**: Đã nghiệm thu và kiểm chứng thực tế trên bộ dữ liệu y tế **HealthCare Dataset (18 bảng, 258 cột)** với độ bao phủ (Coverage) đạt **95.35%** và tỷ lệ lỗi an toàn (Safety Violation) đạt **0.00%**.

---

## 🏗️ Kiến trúc hệ thống

```mermaid
flowchart TD
    subgraph UI ["Frontend (React 19 + Vite)"]
        FE[Web Application Dashboard]
        CP[Table Context Panel]
        RB[Recommendation Board]
        OMV[Observability & Lineage View]
        HR[Human Review Modals]
    end

    subgraph API ["Backend (FastAPI)"]
        RT[API Routers]
        ORC[Recommendation Orchestrator]
        VAL[Rule Validator & Reconciler]
        SQLM[SQL Mapper & Transpiler]
        PUB[OpenMetadata Publisher]
    end

    subgraph ENGINES ["Rule Engines"]
        BE[Basic Heuristic Engine]
        SE[Statistical Drift Engine]
        NT[NT Standard Rules Engine]
        subgraph LLM_ADV ["Advanced LLM Engine"]
            RTR[LLM Router]
            TG[Temporal Generator]
            CCG[Cross-Column Generator]
            CDG[Conditional Dependency Generator]
        end
    end

    subgraph STORAGE ["Storage & External Services"]
        OM[(OpenMetadata Live API)]
        PG[(PostgreSQL / Neon DB)]
        LLMP[(LLM: Ollama / Gemma / OpenAI Compatible)]
    end

    FE --> RT
    RT --> ORC
    ORC --> OM
    ORC --> BE
    ORC --> SE
    ORC --> NT
    ORC --> RTR
    RTR --> TG & CCG & CDG
    TG & CCG & CDG --> LLMP
    
    BE & SE & NT & TG & CCG & CDG --> VAL
    VAL --> SQLM
    SQLM --> PG
    VAL --> PG
    RT --> PUB
    PUB --> OM
```

---

## 🚀 Các tính năng chính

### 1. Multi-tier Rule Engines
* **Basic Rule Engine**: Tự động phát hiện các ràng buộc cơ bản dựa trên metadata và profiling (tỷ lệ null, cardinality, min/max, độ dài chuỗi, định dạng regex email/phone/date).
* **Statistical Rule Engine**: Theo dõi lịch sử profiling theo chuỗi thời gian, áp dụng thuật toán tiền lọc (Pre-filter) và LLM Reviewer để phát hiện độ lệch bất thường của Mean / Median / Standard Deviation.
* **Advanced Rule Engine (LLM-Powered)**:
  * **Router**: Phân tích ngữ cảnh bảng, tên cột, ràng buộc để định tuyến các nhóm rule tiềm năng với ngưỡng tin cậy (Confidence $\ge 0.6$).
  * **Temporal Generator**: Sinh rule kiểm tra quan hệ thời gian (ví dụ: `start_date <= end_date`, `birth_date <= death_date`).
  * **Cross-Column Generator**: Ràng buộc logic giữa nhiều cột (ví dụ: `paid_amount <= total_amount`).
  * **Conditional Dependency Generator**: Ràng buộc có điều kiện (ví dụ: `IF status = 'COMPLETED' THEN completed_at IS NOT NULL`).
* **NT Standard Rules Engine**: Khung cấu hình quy tắc chuẩn theo định dạng Declarative JSON/YAML, hỗ trợ bộ đánh giá (Evaluators) và quản lý job thực thi tự động.

### 2. Thẩm định & Đối chiếu (Validation & Reconciliation)
* **Type & Column Safety**: Kiểm tra cột tồn tại, tương thích kiểu dữ liệu (tránh áp dụng rule số cho cột văn bản).
* **Existing Rule Reconciler**: Tự động quét các Test Case đã có trên OpenMetadata để tránh trùng lặp, đánh dấu trạng thái *NEW*, *EXISTING* hoặc *MODIFIED*.
* **SQL Transpiler**: Chuyển đổi biểu thức logic sang SQL hợp lệ, tương thích với nhiều hệ quản trị cơ sở dữ liệu qua thư viện `sqlglot`.

### 3. Đồng bộ hai chiều với OpenMetadata
* Lấy danh sách Services, Databases, Schemas, Tables.
* Phân tích Schema chi tiết, Cột, Khóa chính/ngoại, Tags, Tier dữ liệu.
* Đọc Freshness và Profiling trực tiếp.
* Xuất bản (Publish) các Rule đã được phê duyệt thành các Test Case chính thức gắn vào Test Suite trên OpenMetadata.

### 4. Giao diện người dùng hiện đại (Modern Web UI)
* **Table Context Explorer**: Xem chi tiết tổng quan bảng, số dòng, số cột, freshness, lineage upstream/downstream.
* **Schema & Profiler View**: Xem phân bố dữ liệu, tỷ lệ null, distinct value trực quan.
* **Recommendation Board**: Danh sách rule được phân loại rõ ràng (Basic, Statistical, Advanced), kèm độ tin cậy (Confidence Score), lý do đề xuất (Reason) và bằng chứng định lượng (Evidence).
* **Review & Modals**: Thao tác Accept, Edit tham số trực tiếp, Reject kèm ghi chú, xem lịch sử phiên bản và thông báo đồng bộ thành công.

---

## 📁 Cấu trúc thư mục dự án

```text
├── backend/                        # Mã nguồn Backend FastAPI
│   ├── api/router/                 # Các API Endpoints (datasource, recommendation, review, test_cases...)
│   ├── config/                     # Cấu hình hệ thống (Pydantic Settings, .env)
│   ├── contracts/                  # Data models, DTOs & Schemas (Pydantic)
│   ├── datasource/                 # Kết nối nguồn dữ liệu (PostgreSQL, OpenMetadata)
│   ├── engine/                     # Các bộ sinh quy tắc (Basic, Advanced LLM, Statistical, NT Rules)
│   │   ├── adapters/               # Adapter chuẩn hóa output giữa các engine
│   │   ├── advanced_llm/           # Client LLM, Router và các Generators chuyên biệt
│   │   ├── nt_rules/               # Engine quy tắc chuẩn hóa NT
│   │   ├── prompts/                # Các file prompt Markdown tối ưu cho LLM
│   │   ├── sql_mapper/             # SQL Dialect Transpiler & Validator
│   │   └── statistical_rules/      # Engine phát hiện bất thường thống kê
│   ├── evaluation/                 # Công cụ đo lường và đánh giá chất lượng rule
│   ├── integrations/               # Tích hợp OpenMetadata (Client, Publisher, Syncer)
│   ├── repository/                 # Data access layer
│   ├── review/                     # Logic xử lý Human Review
│   ├── services/                   # Business logic services & Background Job Runners
│   ├── storage/                    # Quản lý Database PostgreSQL (Neon / Local) & Migrations
│   ├── validator/                  # Bộ lọc và đối chiếu rule (Reconciler, Schema Validator)
│   └── main.py                     # Entry point khởi chạy FastAPI app
├── frontend/                       # Mã nguồn Frontend React 19 + Vite
│   ├── src/
│   │   ├── components/             # Các components UI (Header, RecommendationBoard, Modals...)
│   │   ├── services/               # API clients giao tiếp với backend
│   │   ├── utils/                  # Hàm tiện ích (format, SQL helper...)
│   │   ├── App.jsx                 # Component chính quản lý state toàn bộ ứng dụng
│   │   └── index.css               # Hệ thống styling giao diện
│   └── package.json                # Cấu hình frontend dependencies
├── data/                           # Dataset mẫu, Golden Set đánh giá, sample profile
├── doc/ & docs/                    # Tài liệu LLD, báo cáo nghiệm thu, hướng dẫn tích hợp
├── migrations/                     # Script khởi tạo và cập nhật cấu trúc database
├── scripts/                        # Scripts tự động hóa (migration, evaluation benchmark, import dữ liệu)
├── tests/                          # Automated Unit & E2E Test Suite (pytest)
├── Dockerfile                      # Docker containerfile cho backend
├── docker-compose.local-db.yml     # Khởi chạy PostgreSQL cục bộ qua Docker
└── requirements.txt                # Danh sách thư viện Python
```

---

## ⚙️ Yêu cầu hệ thống

- **Python**: `>= 3.10` (Khuyên dùng `3.12`)
- **Node.js**: `>= 18.0.0` (Khuyên dùng `20+`)
- **Database**: PostgreSQL 15+ (Local Docker hoặc dịch vụ đám mây như Neon)
- **OpenMetadata Server**: Phiên bản 1.2+ (Đã cấu hình JWT Token)
- **LLM Endpoint**: Ollama (chạy model `gemma4-e2b`, `deepseek-coder`, ...) hoặc bất kỳ endpoint tương thích OpenAI API.

---

## 🛠️ Hướng dẫn cài đặt & Khởi chạy

### 1. Cấu hình môi trường (`.env`)

Sao chép file mẫu và điền các thông tin kết nối thực tế trong thư mục `backend/`:

```bash
cp backend/.env.example backend/.env
```

Nội dung cấu hình quan trọng trong `backend/.env`:
```ini
# OpenMetadata Connection
OM_API=https://your-openmetadata-server.com
OM_TOKEN=your-jwt-token-here
OM_TIMEOUT=30

# PostgreSQL Database (Lưu trữ Rule & Lịch sử)
DATABASE_URL=postgresql://user:password@localhost:5433/dq_rules
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=dq_rules
POSTGRES_SSLMODE=disable

# LLM Cấu hình (Ollama / Local LLM)
LLM_API=ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=gemma4-e2b
LLM_TIMEOUT_SECONDS=180

# Kích hoạt các Engine
ENABLE_ADVANCED_RULES=true
ENABLE_STATISTICAL_RULES=false
```

---

### 2. Khởi chạy Database cục bộ (Tùy chọn)

Nếu không sử dụng Neon Cloud Database, bạn có thể khởi chạy PostgreSQL cục bộ bằng Docker:

```bash
docker compose -f docker-compose.local-db.yml up -d
```
Cơ sở dữ liệu sẽ lắng nghe tại cổng `5433`.

Chạy migration để khởi tạo bảng dữ liệu:
```bash
python scripts/migrate_database.py
```

---

### 3. Cài đặt và Khởi chạy Backend

1. Tạo và kích hoạt môi trường ảo:
   ```bash
   # Windows (PowerShell)
   python -m venv .venv
   .venv\Scripts\activate

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Cài đặt các thư viện phụ thuộc:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. Khởi chạy server FastAPI:
   ```bash
   python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
   ```
   * Tài liệu Swagger API tương tác: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
   * Redoc API: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

### 4. Cài đặt và Khởi chạy Frontend

Mở một cửa sổ terminal mới:

1. Di chuyển vào thư mục `frontend`:
   ```bash
   cd frontend
   ```

2. Cài đặt Node modules:
   ```bash
   npm install
   ```

3. Khởi chạy Vite Dev Server:
   ```bash
   npm run dev
   ```
   * Ứng dụng sẽ mở tại địa chỉ: [http://localhost:5173](http://localhost:5173)

---

## 🧪 Kiểm thử & Đo lường chất lượng (Testing & Benchmark)

### 1. Chạy Automated Unit & Integration Tests

Hệ thống có bộ test tự động kiểm tra toàn bộ luồng từ Engine đến API:

```bash
python -m pytest tests/ -v
```

Kiểm tra riêng các module trọng tâm:
```bash
# Kiểm thử Basic Engine & E2E flow
python -m pytest tests/test_basic_engine.py tests/test_end_to_end_flow.py -v

# Kiểm thử Advanced Rule LLM Router & Generators
python -m pytest tests/advanced_rules/ -v

# Kiểm thử SQL Dialect Transpiler
python -m pytest tests/sql_mapper/ -v

# Kiểm thử NT Rules Engine
python -m pytest tests/test_nt_phase_c.py -v
```

### 2. Chạy Benchmark Evaluation trên 18 bảng HealthCare

Đo lường độ bao phủ (Coverage) và tỷ lệ an toàn (Safety) trên bộ dữ liệu chuẩn:

```bash
python scripts/run_evaluation_8_tables.py
```

Kết quả đo lường thực tế:
- **Coverage**: **95.35%** (246/258 cột có rule kiểm định)
- **Invalid Column Rate**: **0.00%** (Không có rule sinh sai tên cột)
- **Duplicate Candidate Rate**: **0.00%** (Không có rule trùng lặp)
- **Type Validation Failure Rate**: **0.00%** (100% rule khớp kiểu dữ liệu)

---

## 📡 Danh sách API Endpoints chính

| Phương thức | Đường dẫn | Chức năng |
|:---|:---|:---|
| `GET` | `/api/v1/health` | Kiểm tra trạng thái hệ thống và kết nối OpenMetadata |
| `GET` | `/api/v1/catalog/tables` | Lấy danh sách bảng từ OpenMetadata |
| `GET` | `/api/v1/context/{table_fqn}` | Lấy chi tiết schema, column profile, lineage của bảng |
| `POST` | `/api/v1/recommendations/generate` | Sinh danh sách rule gợi ý (Basic + Advanced) |
| `POST` | `/api/v1/review/{candidate_id}` | Thực hiện hành động Review: `ACCEPT`, `EDIT`, `REJECT` |
| `POST` | `/api/v1/test-cases/publish` | Đẩy các rule đã duyệt lên OpenMetadata dưới dạng Test Cases |
| `GET` | `/api/v1/evaluation/summary` | Lấy báo cáo thống kê benchmark chất lượng rule |
| `POST` | `/api/v1/jobs/generation` | Tạo và quản lý background job sinh rule cho nhiều bảng |
| `GET` | `/api/v1/nt-rules` | Danh sách và trạng thái cấu hình bộ quy tắc chuẩn NT |

---

## 👥 Phân công & Đóng góp (Team)

Dự án được xây dựng và phát triển bởi:
* **Member A**: Thiết kế kiến trúc tổng thể, phát triển Backend Core, Basic Engine, Advanced LLM Engine, SQL Mapper/Transpiler, Quản lý Database & Migrations, Benchmark Evaluation.
* **Member B**: Thiết kế và hoàn thiện Frontend Dashboard (React + Vite), kết nối REST API, quản lý State, xây dựng các View Observability, Lineage, Profiler chi tiết và tích hợp luồng Human Review.

---

## 📄 Bản quyền & Giấy phép

Dự án được phát hành dưới giấy phép mã nguồn mở nội bộ phục vụ mục đích nghiên cứu và phát triển giải pháp Quản trị Chất lượng Dữ liệu (Data Quality & Observability).
