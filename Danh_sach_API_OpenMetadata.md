# DANH SÁCH CÁC API LIÊN QUAN ĐẾN OPENMETADATA TRONG HỆ THỐNG

Tài liệu này tổng hợp toàn bộ các API liên quan đến **OpenMetadata** mà ứng dụng Web và Backend đang sử dụng, bao gồm:
1. **OpenMetadata Native REST APIs**: Các API chuẩn do server OpenMetadata cung cấp mà Backend gọi trực tiếp.
2. **Backend Gateway/Proxy APIs**: Các API do FastAPI Backend (`http://localhost:8000/api/v1`) cung cấp để Web Frontend giao tiếp với dữ liệu OpenMetadata.
3. **Luồng tương tác dữ liệu từ Web Frontend**: Cách giao diện người dùng tiêu thụ các API này.

---

## 1. TỔNG QUAN KIẾN TRÚC KẾT NỐI

```
+-------------------------------------------------------------+
|                     Web Frontend (React)                    |
|                http://localhost:5173                        |
+-------------------------------------------------------------+
                              |
                              | HTTP / REST (api.js / App.jsx)
                              v
+-------------------------------------------------------------+
|                    Backend API (FastAPI)                    |
|                http://localhost:8000/api/v1                 |
|             (backend/main.py & config.py)                   |
+-------------------------------------------------------------+
                              |
                              | OpenMetadataClient (requests + Bearer Token)
                              v
+-------------------------------------------------------------+
|                 OpenMetadata REST API Server                |
|        http://localhost:8585/api/v1 (mặc định)              |
+-------------------------------------------------------------+
```

---

## 2. CÁC API OPENMETADATA GỐC (OPENMETADATA REST API)

Được triển khai trong mã nguồn tại: [`backend/integrations/openmetadata_client.py`](file:///d:/VSF/backend/integrations/openmetadata_client.py).

| STT | Phương thức | Endpoint OpenMetadata | Mục đích trong hệ thống | Tham số & Header | Dữ liệu trả về |
|:---:|:---:|:---|:---|:---|:---|
| **1** | `GET` | `/system/version` | **Kiểm tra trạng thái kết nối (Health Check / Ping)** đến máy chủ OpenMetadata. | - Header: `Authorization: Bearer <TOKEN>`<br>- Timeout: 5s | Version info JSON (HTTP 200 OK) |
| **2** | `GET` | `/tables?limit=50&fields=columns` | **Lấy danh sách các bảng** đã được catalog trong OpenMetadata để hiển thị lên dropdown chọn bảng trên Header Web. | - Query: `limit=50`, `fields=columns`<br>- Header: `Authorization` | Danh sách các bảng kèm metadata cơ bản (name, fullyQualifiedName, description) |
| **3** | `GET` | `/tables/name/{table_name}?fields=columns,profile,tableProfilerConfig` | **Trích xuất toàn bộ Schema cột và kết quả Data Profiling** (số dòng, tỷ lệ null, số lượng distinct, min, max, top values) của bảng mục tiêu. | - Path: `{table_name}` (ví dụ: `orders` hoặc FQN)<br>- Query: `fields=columns,profile,tableProfilerConfig` | JSON chứa cấu trúc cột và object `profile` do OpenMetadata Profiler tính toán |
| **4** *(Quy hoạch)* | `POST` | `/dataQuality/testSuites` | **Tạo hoặc gán Test Suite** cho bảng mục tiêu khi người dùng nhấn nút *"Xuất bản (Publish)"* trên Web. | - Body: `name`, `basic`, `executableEntityReference` | Thông tin Test Suite đã tạo |
| **5** *(Quy hoạch)* | `POST` | `/dataQuality/testCases` | **Đăng ký các Data Quality Rules đã duyệt** (ACCEPTED/EDITED) thành các Test Cases chính thức chạy định kỳ trên OpenMetadata. | - Body: `name`, `testDefinition`, `testSuite`, `parameterValues` | Test Case Entity |

---

## 3. CÁC API BACKEND CỦA DỰ ÁN (FASTAPI BACKEND GATEWAY)

Được triển khai trong mã nguồn tại: [`backend/main.py`](file:///d:/VSF/backend/main.py).

Các API này đóng vai trò cầu nối: đóng gói logic nghiệp vụ, chuẩn hóa format JSON và kích hoạt **Rule Engine** trước khi trả kết quả cho giao diện Web.

### 3.1. `GET /api/v1/health`
- **Mục đích**: Kiểm tra tình trạng hoạt động của Backend và kiểm tra tính sẵn sàng của kết nối tới OpenMetadata.
- **Tương tác OpenMetadata**: Gọi `openmetadata_client.check_connection()`.
- **Response mẫu**:
```json
{
  "status": "healthy",
  "openmetadata_connected": true,
  "openmetadata_url": "http://localhost:8585/api/v1"
}
```

---

### 3.2. `GET /api/v1/tables`
- **Mục đích**: Cung cấp danh sách bảng cho Web Frontend.
- **Tương tác OpenMetadata**: Gọi `openmetadata_client.list_tables()`.
- **Response mẫu**:
```json
{
  "tables": [
    {
      "name": "orders",
      "fullyQualifiedName": "postgres.ecommerce_db.public.orders",
      "description": "Bảng thông tin đơn hàng e-commerce"
    },
    {
      "name": "customers",
      "fullyQualifiedName": "postgres.ecommerce_db.public.customers",
      "description": "Danh sách khách hàng đăng ký"
    }
  ]
}
```

---

### 3.3. `GET /api/v1/context/{table_name}`
- **Mục đích**: Cung cấp bảng điều khiển bên trái Web (Context Panel) gồm: Tổng số dòng, số cột, loại dữ liệu từng cột, tỷ lệ null (%), số distinct (%).
- **Tương tác OpenMetadata**: Gọi `openmetadata_client.get_table_context(table_name)` để đọc `profile.columnProfile`.
- **Response mẫu**:
```json
{
  "datasource_id": "openmetadata-live",
  "database_name": "ecommerce_db",
  "schema_name": "public",
  "table_name": "orders",
  "table_description": "Bảng lưu trữ thông tin đơn hàng...",
  "row_count": 15420,
  "columns": [
    {
      "name": "order_id",
      "data_type": "VARCHAR(64)",
      "nullable": false,
      "is_primary_key": true,
      "profile": {
        "row_count": 15420,
        "null_count": 0,
        "null_ratio": 0.0,
        "distinct_count": 15420,
        "distinct_ratio": 1.0
      }
    }
  ]
}
```

---

### 3.4. `POST /api/v1/recommendations/generate`
- **Mục đích**: Được gọi khi người dùng bấm nút **"Gợi ý luật DQ (Generate Rules)"** trên Web.
- **Tương tác OpenMetadata**: Lấy profiling metrics của bảng từ OpenMetadata, sau đó đưa vào `BasicRuleEngine` để tự động sinh ra các Candidate Rules kèm bằng chứng (*evidence*).
- **Request Body**:
```json
{
  "table_name": "orders",
  "datasource_id": "openmetadata",
  "engines": ["BASIC", "ADVANCED"]
}
```
- **Response mẫu**: Trả về mảng các candidate rules kèm thông tin độ tin cậy (*confidence*), lý do (*reason*), và chỉ số vi phạm (*evidence*).

---

### 3.5. `POST /api/v1/rules/{rule_id}/review`
- **Mục đích**: Đồng bộ trạng thái duyệt luật từ người dùng khi thao tác trên Web (Chấp thuận, Từ chối, hoặc Sửa tham số luật).
- **Request Body**:
```json
{
  "action": "ACCEPTED", // "ACCEPTED" | "REJECTED" | "EDITED"
  "edited_parameters": { "minValue": 0, "maxValue": 100000000 }
}
```

---

## 4. CHI TIẾT CÁC CHỈ SỐ PROFILING MÀ HỆ THỐNG ĐỌC TỪ OPENMETADATA

Hệ thống map trực tiếp các trường trong `profile.columnProfile` của OpenMetadata sang định dạng nội bộ để làm căn cứ suy luận:

| Trường của OpenMetadata | Tên thuộc tính trong hệ thống | Ứng dụng để sinh Rule |
|:---|:---|:---|
| `columnProfile.nullCount` & `nullProportion` | `null_count`, `null_ratio` | Sinh luật **`columnValuesToBeNotNull`** nếu `null_count == 0` |
| `columnProfile.distinctCount` & `distinctProportion` | `distinct_count`, `distinct_ratio` | Sinh luật **`columnValuesToBeUnique`** nếu `distinct_ratio == 1.0` |
| `columnProfile.min` & `columnProfile.max` | `min_value`, `max_value` | Sinh luật **`columnValuesToBeBetween`** cho các cột số (NUMERIC, INT) |
| `columnProfile.valuesCount` | `top_values` / `sample_values` | Sinh luật **`columnValuesToBeInSet`** cho cột phân loại có cardinality thấp |
| `columnProfile.minLength` & `maxLength` | `min_length`, `max_length` | Sinh luật **`columnValueLengthsToBeBetween`** cho cột chuỗi (mã, định danh) |

---

## 5. CƠ CHẾ DỰ PHÒNG (SMART FALLBACK)

Khi máy chủ OpenMetadata chưa được bật hoặc chưa cấu hình token:
1. **Tại Backend** ([`backend/integrations/openmetadata_client.py`](file:///d:/VSF/backend/integrations/openmetadata_client.py)):
   - Hàm `get_table_context` sẽ tự động bắt ngoại lệ timeout / connection error và chuyển sang `_get_fallback_context(table_name)`.
   - Cung cấp sẵn profile chuẩn của 2 bảng `orders` (15,420 dòng) và `customers` (8,920 dòng).
2. **Tại Web Frontend** ([`frontend/src/App.jsx`](file:///d:/VSF/frontend/src/App.jsx)):
   - Nếu Backend API chưa bật, Web Frontend tự động dùng dữ liệu tĩnh trong [`frontend/src/services/mockData.js`](file:///d:/VSF/frontend/src/services/mockData.js) để giao diện vẫn hoạt động mượt mà cho việc demo và phát triển giao diện.

---

## 6. CẤU HÌNH BIẾN MÔI TRƯỜNG KẾT NỐI OPENMETADATA

File cấu hình tại [`backend/config.py`](file:///d:/VSF/backend/config.py):

```bash
# URL của OpenMetadata Server
OPENMETADATA_SERVER_URL=http://localhost:8585/api/v1

# JWT Bot Token được tạo từ OpenMetadata Settings -> Bots
OPENMETADATA_JWT_TOKEN=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
```
