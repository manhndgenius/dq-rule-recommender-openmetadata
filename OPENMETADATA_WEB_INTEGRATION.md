# Tích hợp OpenMetadata vào Web Tool

## 1. Mục tiêu

Lấy metadata và data profiling từ OpenMetadata để hiển thị trên web tool:

- Database service, database và schema.
- Danh sách bảng.
- Danh sách cột, kiểu dữ liệu và constraint.
- Table profile: số dòng, số cột và thời điểm profiling.
- Column profile: null, distinct, unique, min/max, mean, median và độ dài chuỗi.

OpenMetadata chỉ chứa metadata và kết quả profiling, không chứa raw data của bệnh nhân.

## 2. Dữ liệu hiện có

```text
healthcare_postgres                 Database Service
└── HealthCare                     Database
    └── public                     Database Schema
        ├── allergies
        ├── careplans
        ├── claims
        ├── ...
        └── supplies               Tổng cộng 18 tables
```

FQN (Fully Qualified Name) có dạng:

```text
service.database.schema.table.column
```

Ví dụ:

```text
healthcare_postgres.HealthCare.public.patients.id
```

## 3. Biến môi trường

Chỉ đặt các biến sau ở backend:

```dotenv
OM_TOKEN=eyJraWQiOiJHYjM4OWEtOWY3Ni1nZGpzLWE5MmotMDI0MmJrOTQzNTYiLCJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJvcGVuLW1ldGFkYXRhLm9yZyIsInN1YiI6ImFkbWluIiwicm9sZXMiOlsiQWRtaW4iXSwiZW1haWwiOiJhZG1pbkBvcGVuLW1ldGFkYXRhLm9yZyIsImlzQm90IjpmYWxzZSwidG9rZW5UeXBlIjoiUEVSU09OQUxfQUNDRVNTIiwidXNlcm5hbWUiOiJhZG1pbiIsInByZWZlcnJlZF91c2VybmFtZSI6ImFkbWluIiwiaWF0IjoxNzkwOTExMzAwLCJleHAiOjE3OTg2ODczMDB9.tAaDwp6b0GF9OUtDQPkM8CeWDy12xtnKJcKEXU46eOKx3nPdSt5Yi-pBNpjAYklOqP7YH55prg8MU2qJiFOI6B7_6XU-f_OFKNyt45w7iYmrA-2C1FK626Gs3xIX-bADVmPN2upeyCcURsb2ri1q3FJMlWdAo_SVcFrWvHk4uobdpkuYVKOSZDmRoZeVDJx4y44T7nkRtQSHDtP644R57eHpG5rZGLLrxNwOl3NQOgMbkvHzvHsScwInAyO9sw_4RthsI2IQH_Nve_AEpOJgdHZ_IvN3ACiaPluN22SIjfTdYbcqaPtRIxH5TqfCD63nD_G3dgbAXJBuhONgIbw8pg
OM_API=https://c3-app-009.duckdns.org/
```

REST base URL được tạo như sau:

```text
${OM_API}/v1
```

Không đặt token trong biến có prefix `NEXT_PUBLIC_`, `VITE_` hoặc bất kỳ biến nào được bundle vào frontend.

## 4. Authentication context

Mọi request gửi từ backend sang OpenMetadata dùng:

```http
Authorization: Bearer <OM_TOKEN>
Accept: application/json
```

Với request ghi dữ liệu, thêm:

```http
Content-Type: application/json
```

Ví dụ helper Node.js/TypeScript:

```ts
const OM_BASE = `${process.env.OM_API!.replace(/\/$/, "")}/v1`;

export async function callOpenMetadata<T>(
  path: string,
  query: Record<string, string | number | undefined> = {},
): Promise<T> {
  const url = new URL(`${OM_BASE}${path}`);

  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined) url.searchParams.set(key, String(value));
  }

  const response = await fetch(url, {
    headers: {
      Authorization: `Bearer ${process.env.OM_TOKEN}`,
      Accept: "application/json",
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`OpenMetadata ${response.status}: ${detail}`);
  }

  return response.json() as Promise<T>;
}
```

## 5. Các API cần gọi

### 5.1. Lấy database services

```http
GET /api/v1/services/databaseServices?limit=100
```

Response chính:

```json
{
  "data": [
    {
      "id": "uuid",
      "name": "healthcare_postgres",
      "fullyQualifiedName": "healthcare_postgres",
      "serviceType": "Postgres"
    }
  ],
  "paging": {
    "total": 1,
    "after": null
  }
}
```

### 5.2. Lấy databases của service

```http
GET /api/v1/databases?service=healthcare_postgres&limit=100
```

Giá trị `service` là service FQN.

### 5.3. Lấy schemas của database

```http
GET /api/v1/databaseSchemas?database=healthcare_postgres.HealthCare&limit=100
```

Giá trị `database` là database FQN.

### 5.4. Lấy tables của schema

```http
GET /api/v1/tables?databaseSchema=healthcare_postgres.HealthCare.public&limit=100
```

Giá trị `databaseSchema` là schema FQN. Response là object có `data` và `paging`.

### 5.5. Lấy chi tiết table và columns

```http
GET /api/v1/tables/{tableId}?fields=columns,owners,tags
```

Các field quan trọng:

```json
{
  "id": "table-uuid",
  "name": "patients",
  "fullyQualifiedName": "healthcare_postgres.HealthCare.public.patients",
  "tableType": "Regular",
  "columns": [
    {
      "name": "id",
      "fullyQualifiedName": "healthcare_postgres.HealthCare.public.patients.id",
      "dataType": "UUID",
      "dataTypeDisplay": "uuid",
      "constraint": "PRIMARY_KEY"
    }
  ]
}
```

### 5.6. Lấy table profile theo khoảng thời gian

`startTs` và `endTs` là Unix timestamp tính bằng milliseconds.

```http
GET /api/v1/tables/{tableId}/tableProfile?startTs=0&endTs=2000000000000
```

Response kỳ vọng:

```json
{
  "data": [
    {
      "timestamp": 1790852467000,
      "rowCount": 1234,
      "columnCount": 28
    }
  ],
  "paging": {
    "total": 1
  }
}
```

Nếu có nhiều record, chọn record có `timestamp` lớn nhất để hiển thị latest profile.

### 5.7. Lấy profile của từng column

Trên instance hiện tại, endpoint này nhận **column FQN**, không nhận table ID:

```http
GET /api/v1/tables/{encodedColumnFqn}/columnProfile?startTs=0&endTs=2000000000000
```

Ví dụ TypeScript:

```ts
const columnFqn = "healthcare_postgres.HealthCare.public.patients.id";
const path = `/tables/${encodeURIComponent(columnFqn)}/columnProfile`;

const result = await callOpenMetadata<ProfilePage<ColumnProfile>>(path, {
  startTs: 0,
  endTs: Date.now() + 86_400_000,
});
```

Response:

```json
{
  "data": [
    {
      "name": "id",
      "timestamp": 1790852467000,
      "valuesCount": 1000,
      "nullCount": 0,
      "nullProportion": 0,
      "uniqueCount": 1000,
      "uniqueProportion": 1,
      "distinctCount": 1000,
      "distinctProportion": 1,
      "min": "...",
      "max": "..."
    }
  ],
  "paging": {
    "total": 1
  }
}
```

## 6. Mapping sang model của web tool

Nên để backend chuyển response của OpenMetadata thành model ổn định sau:

```ts
export interface CatalogTable {
  id: string;
  name: string;
  fqn: string;
  type: string;
  profile: TableProfile | null;
  columns: CatalogColumn[];
}

export interface TableProfile {
  timestamp: number;
  rowCount: number;
  columnCount: number;
}

export interface CatalogColumn {
  name: string;
  fqn: string;
  dataType: string;
  constraint?: string;
  profile: ColumnProfile | null;
}

export interface ColumnProfile {
  timestamp: number;
  valuesCount?: number;
  nullCount?: number;
  nullProportion?: number;
  uniqueCount?: number;
  uniqueProportion?: number;
  distinctCount?: number;
  distinctProportion?: number;
  min?: string | number;
  max?: string | number;
  mean?: number;
  median?: number;
  minLength?: number;
  maxLength?: number;
}

export interface ProfilePage<T> {
  data: T[];
  paging: {
    total: number;
    before?: string;
    after?: string;
  };
}
```

Quy tắc hiển thị gợi ý:

```text
Null %        = nullProportion * 100
Unique %      = uniqueProportion * 100
Distinct %    = distinctProportion * 100
Completeness  = (1 - nullProportion) * 100
```

Không nhân các giá trị `*Proportion` với 100 trước khi lưu vào model; chỉ nhân lúc format UI.

## 7. Backend API đề xuất cho frontend

Frontend không cần biết cấu trúc API của OpenMetadata. Backend web tool nên expose:

```http
GET /api/catalog/databases?service=healthcare_postgres
GET /api/catalog/schemas?databaseFqn=healthcare_postgres.HealthCare
GET /api/catalog/tables?schemaFqn=healthcare_postgres.HealthCare.public
GET /api/catalog/tables/{tableId}
```

Response của endpoint cuối:

```json
{
  "id": "table-uuid",
  "name": "patients",
  "fqn": "healthcare_postgres.HealthCare.public.patients",
  "type": "Regular",
  "profile": {
    "timestamp": 1790852467000,
    "rowCount": 1000,
    "columnCount": 28
  },
  "columns": [
    {
      "name": "id",
      "fqn": "healthcare_postgres.HealthCare.public.patients.id",
      "dataType": "UUID",
      "constraint": "PRIMARY_KEY",
      "profile": {
        "timestamp": 1790852467000,
        "valuesCount": 1000,
        "nullCount": 0,
        "nullProportion": 0,
        "distinctCount": 1000,
        "distinctProportion": 1
      }
    }
  ]
}
```

## 8. Lưu ý về table profile trên instance hiện tại

Đã kiểm tra trực tiếp instance ngày 02/10/2026:

- Database, schema và 18 tables đọc được bình thường.
- Column profile đọc được bằng column FQN.
- `GET /tables/{tableId}/tableProfile?...` hiện trả về `data: []`.
- `GET /tables/{tableId}/tableProfile/latest` hiện trả về HTTP 404.

Đây là lỗi đã được ghi nhận ở một số phiên bản OpenMetadata 1.13.x. Trong lúc chưa nâng cấp hoặc vá server, dùng fallback:

```ts
function deriveTableProfile(
  columns: CatalogColumn[],
): TableProfile | null {
  const profiles = columns
    .map((column) => column.profile)
    .filter((profile): profile is ColumnProfile => profile !== null);

  if (profiles.length === 0) return null;

  const rowCounts = profiles
    .map((profile) =>
      profile.valuesCount !== undefined && profile.nullCount !== undefined
        ? profile.valuesCount + profile.nullCount
        : undefined,
    )
    .filter((value): value is number => value !== undefined);

  return {
    timestamp: Math.max(...profiles.map((profile) => profile.timestamp)),
    rowCount: rowCounts.length > 0 ? Math.max(...rowCounts) : 0,
    columnCount: columns.length,
  };
}
```

Fallback khác là đọc `healthcare_profile.json` từ backend. Không đọc file này trực tiếp từ browser nếu sau này file có thêm thông tin nhạy cảm.

## 9. Pagination và hiệu năng

Các API list trả về:

```json
{
  "data": [],
  "paging": {
    "total": 18,
    "after": "cursor"
  }
}
```

Nếu `paging.after` có giá trị, gọi trang tiếp theo bằng:

```http
GET /api/v1/tables?...&after={urlEncodedCursor}
```

Không gọi profile cho toàn bộ columns mỗi lần mở trang danh sách. Luồng đề xuất:

1. Trang danh sách chỉ lấy databases, schemas và tables.
2. Khi người dùng mở một table, lấy table detail và profile của các columns.
3. Cache kết quả profile ở backend từ 1 đến 5 phút.
4. Giới hạn concurrency khoảng 5 đến 10 request khi lấy nhiều column profiles.

## 10. Xử lý lỗi

```text
400  Sai FQN hoặc query parameter.
401  Token thiếu, sai hoặc hết hạn.
403  Token không có quyền đọc entity/profile.
404  Entity không tồn tại hoặc lỗi tableProfile/latest nêu trên.
429  Gọi quá nhiều request; cần retry có backoff.
5xx  Lỗi OpenMetadata; log status và request path, không log token.
```

Backend không được trả `OM_TOKEN` hoặc nguyên header `Authorization` về frontend/log.

## 11. Checklist nghiệm thu

- [ ] Backend đọc `OM_API` và `OM_TOKEN` từ environment.
- [ ] Frontend không chứa OpenMetadata token.
- [ ] Hiển thị đúng `HealthCare/public` và đủ 18 tables.
- [ ] Mở table thấy đúng tên, kiểu và constraint của columns.
- [ ] Column profiling hiển thị đúng timestamp và các metric.
- [ ] Table row count dùng API khi hoạt động, nếu không thì dùng fallback.
- [ ] Có xử lý pagination.
- [ ] Có loading, empty state và error state trên UI.
- [ ] Không ghi token vào log hoặc response frontend.

## 12. Tài liệu tham khảo

- Database hierarchy: https://docs.open-metadata.org/v1.12.x/api-reference/data-assets/databases-overview
- Tables API: https://docs.open-metadata.org/v1.12.x/api-reference/data-assets/tables
- Table profile issue: https://github.com/open-metadata/OpenMetadata/issues/30208
