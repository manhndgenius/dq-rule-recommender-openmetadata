# Implementation Plan — Advanced Data Quality Rule Recommendation

## 1. Mục tiêu

Xây dựng module **Advanced Rule Recommendation** có khả năng đề xuất các Data Quality Rule cần suy luận ngữ nghĩa/business context, thay vì chỉ dựa vào profiling đơn giản.

Phạm vi POC tập trung vào:

1. **Cross-column Rule**
   - Ví dụ: `delivery_date >= order_date`
2. **Conditional Dependency Rule**
   - Ví dụ: `IF status = 'completed' THEN completed_at IS NOT NULL`
3. **Temporal Rule**
   - Ví dụ: `end_time >= start_time`

Custom SQL **không được coi là một semantic rule type riêng**. Nó là cách biểu diễn/execution fallback khi rule không map được sang native rule của OpenMetadata.

---

# 2. Kiến trúc đề xuất

```text
OpenMetadata
    │
    ├── Table metadata
    ├── Column metadata
    ├── Description
    ├── Profiling summary
    ├── Relationships
    ├── Existing tests / constraints
    └── Glossary / tags (nếu có)
            │
            ▼
      Context Builder
            │
            ▼
     Lightweight Context
            │
            ▼
      Rule Type Router
            │
    ┌───────┼────────┐
    │       │        │
    ▼       ▼        ▼
Cross-   Conditional Temporal
column   Dependency
Generator Generator  Generator
    │       │        │
    └───────┼────────┘
            ▼
      Canonical Rule
            │
            ▼
       Rule Validator
            │
            ▼
 Duplicate / Conflict Check
            │
            ▼
        Rule Mapper
        /        \
     Native    Custom SQL
        \        /
          ▼
      Human Review
   Accept / Edit / Reject
          │
          ▼
     OpenMetadata API
```

---

# 3. Nguyên tắc thiết kế

## 3.1. Không dùng LLM cho mọi tác vụ

LLM chỉ xử lý các rule cần:

- hiểu ý nghĩa cột;
- hiểu relationship giữa nhiều cột;
- suy luận business logic;
- kết hợp description, glossary và profiling.

Các rule đơn giản như:

- NULL;
- UNIQUE;
- RANGE;
- REGEX;
- ALLOWED VALUES;

nên nằm ở **Basic Rule Engine** nếu có thể suy ra bằng profiling/heuristic.

---

## 3.2. Router là multi-label

Router không chọn đúng một rule type.

Ví dụ output hợp lệ:

```json
{
  "candidate_rule_types": [
    {
      "type": "CROSS_COLUMN",
      "confidence": 0.91,
      "evidence_columns": ["order_date", "delivery_date"]
    },
    {
      "type": "CONDITIONAL_DEPENDENCY",
      "confidence": 0.87,
      "evidence_columns": ["status", "completed_at"]
    }
  ]
}
```

Một bảng có thể đồng thời chứa nhiều loại Advanced Rule.

---

## 3.3. Không gửi raw data mặc định

Ưu tiên:

- schema;
- description;
- profiling;
- glossary;
- relationships;
- existing rules.

Sample data chỉ dùng khi:

- metadata/profiling chưa đủ bằng chứng;
- được phép truy cập;
- đã masking/anonymization nếu có dữ liệu nhạy cảm.

---

## 3.4. Phân biệt observed pattern và business constraint

Ví dụ:

```text
Observed:
min(age) = 18
```

không đồng nghĩa với:

```text
Business rule:
age >= 18
```

Profiling là **evidence**, không phải business truth.

---

# 4. Scope POC

## Phase đầu hỗ trợ 3 semantic rule type

### A. CROSS_COLUMN

Quan hệ giữa từ hai cột trở lên.

Ví dụ:

```text
delivery_date >= order_date
```

### B. CONDITIONAL_DEPENDENCY

Quan hệ IF-THEN.

Ví dụ:

```text
IF status = 'completed'
THEN completed_at IS NOT NULL
```

### C. TEMPORAL

Quan hệ thứ tự thời gian.

Ví dụ:

```text
end_time >= start_time
```

---

# 5. Data Contract

## 5.1. Input từ OpenMetadata

Chuẩn hóa về một object chung:

```json
{
  "table": {
    "name": "orders",
    "description": "Stores customer orders",
    "domain": "sales"
  },
  "columns": [
    {
      "name": "order_date",
      "datatype": "TIMESTAMP",
      "description": "Time when the order was created",
      "profiling": {
        "null_ratio": 0.0,
        "distinct_ratio": 0.92
      },
      "tags": [],
      "glossary_terms": []
    }
  ],
  "relationships": [],
  "existing_rules": [],
  "constraints": []
}
```

---

## 5.2. Lightweight Router Context

Router không cần toàn bộ dữ liệu.

```json
{
  "table_name": "orders",
  "table_description": "Stores customer orders",
  "columns": [
    {
      "name": "order_date",
      "datatype": "TIMESTAMP",
      "description": "Time when the order was created",
      "profiling_summary": {
        "null_ratio": 0.0
      }
    }
  ],
  "relationships": [],
  "supported_rule_types": [
    "CROSS_COLUMN",
    "CONDITIONAL_DEPENDENCY",
    "TEMPORAL"
  ]
}
```

---

## 5.3. Canonical Rule Schema

Tất cả generator phải trả cùng một schema.

```json
{
  "rule_id": "candidate-uuid",
  "rule_category": "CROSS_COLUMN",
  "target_table": "orders",
  "columns": ["order_date", "delivery_date"],
  "condition": "delivery_date >= order_date",
  "reason": "Delivery should not occur before order creation.",
  "evidence": [
    {
      "type": "COLUMN_DESCRIPTION",
      "source": "delivery_date",
      "value": "Time when the order was delivered"
    }
  ],
  "confidence": 0.91,
  "execution_type": null,
  "status": "CANDIDATE"
}
```

---

# 6. Module Breakdown

## 6.1. OpenMetadata Client

### Nhiệm vụ

- lấy table metadata;
- lấy columns;
- lấy descriptions;
- lấy profiling;
- lấy tags/glossary;
- lấy relationships;
- lấy existing Test Cases;
- tạo Test Case sau khi user approve.

### Output

Trả raw data cho `ContextBuilder`.

### Interface gợi ý

```python
class OpenMetadataClient:
    def get_table_context(table_fqn: str) -> dict:
        ...

    def get_existing_tests(table_fqn: str) -> list:
        ...

    def create_test_case(rule: dict) -> dict:
        ...
```

---

# 6.2. Context Builder

### Nhiệm vụ

Biến OpenMetadata response thành context chuẩn.

### Các bước

1. Normalize schema.
2. Normalize profiling.
3. Attach description.
4. Attach tags/glossary.
5. Attach relationships.
6. Attach existing tests.
7. Loại dữ liệu không cần thiết.
8. Mask sample data nếu dùng.

### Output

```text
FullRuleContext
```

---

# 6.3. Candidate Column Selector

Mục tiêu: tránh gửi toàn bộ 100–500 columns vào LLM generator.

### Heuristic ban đầu

#### Temporal candidate

Nếu:

```text
datatype ∈ {DATE, DATETIME, TIMESTAMP}
```

→ ưu tiên ghép các cột có tên/description liên quan:

```text
start/end
created/completed
admission/discharge
order/delivery
from/to
```

#### Conditional candidate

Ưu tiên:

- categorical column;
- status/type/flag columns;
- nullable dependent column;
- timestamp/result/value column liên quan semantic.

### Output

```json
{
  "candidate_groups": [
    {
      "columns": ["status", "completed_at"],
      "reason": "status-like categorical column and related completion timestamp"
    }
  ]
}
```

> POC có thể dùng heuristic đơn giản trước. Sau này có thể thay bằng embedding similarity hoặc semantic retrieval.

---

# 6.4. Rule Type Router

### Nhiệm vụ

Không sinh rule.

Chỉ xác định:

- rule type nào đáng xét;
- candidate columns nào liên quan;
- confidence;
- reason ngắn.

### Input

- table name/description;
- column name;
- datatype;
- description;
- lightweight profiling;
- relationships;
- supported rule types.

### Output

```json
{
  "candidate_rule_types": [
    {
      "type": "CROSS_COLUMN",
      "confidence": 0.91,
      "evidence_columns": [
        "order_date",
        "delivery_date"
      ],
      "reason": "Related lifecycle timestamp columns."
    }
  ]
}
```

### Rule

- chọn ZERO / ONE / MULTIPLE;
- không được tạo actual condition;
- không được chọn rule ngoài danh sách supported.

---

# 7. Specialized Generators

## 7.1. Cross-column Generator

### Input

Chỉ nhận:

- candidate columns;
- descriptions;
- datatypes;
- profiling;
- relationships;
- glossary/documentation liên quan.

### Task

Tìm relationship hợp lý giữa nhiều cột.

### Ví dụ output

```json
{
  "rule_category": "CROSS_COLUMN",
  "columns": ["order_date", "delivery_date"],
  "condition": "delivery_date >= order_date",
  "reason": "Delivery logically occurs after order creation.",
  "confidence": 0.92
}
```

---

## 7.2. Conditional Dependency Generator

### Input

Ví dụ:

```text
status
completed_at
```

### Task

Sinh IF-THEN constraint.

### Output

```json
{
  "rule_category": "CONDITIONAL_DEPENDENCY",
  "columns": ["status", "completed_at"],
  "condition": "IF status = 'completed' THEN completed_at IS NOT NULL",
  "reason": "Completed orders should have a completion timestamp.",
  "confidence": 0.88
}
```

---

## 7.3. Temporal Generator

### Task

Sinh rule về thứ tự thời gian.

### Output

```json
{
  "rule_category": "TEMPORAL",
  "columns": ["start_time", "end_time"],
  "condition": "end_time >= start_time",
  "reason": "An event should not end before it starts.",
  "confidence": 0.94
}
```

---

# 8. Prompt Management

Tách prompt thành file riêng.

```text
prompts/
├── router.txt
├── cross_column.txt
├── conditional_dependency.txt
└── temporal.txt
```

Không hard-code prompt trực tiếp trong service.

Mỗi prompt cần:

- role;
- supported task;
- input context;
- constraints;
- anti-hallucination instruction;
- JSON schema;
- examples tối thiểu;
- rule: không đủ evidence thì trả empty list.

---

# 9. Rule Validator

Validator phải deterministic càng nhiều càng tốt.

## 9.1. Schema Validation

Kiểm tra:

- table tồn tại;
- column tồn tại;
- field output đầy đủ;
- đúng JSON schema.

---

## 9.2. Datatype Validation

Ví dụ reject:

```text
customer_name > delivery_date
```

nếu datatype không phù hợp.

---

## 9.3. Semantic Sanity Check

POC:

- heuristic;
- hoặc optional LLM-as-judge ở phase sau.

Không để LLM-as-judge là validator duy nhất.

---

## 9.4. Duplicate Check

So sánh với:

```text
existing_rules
existing_test_cases
```

Phân loại:

```text
NEW
DUPLICATE
POSSIBLE_CONFLICT
```

---

## 9.5. Confidence Gate

POC có thể:

```text
confidence >= 0.80
→ show recommendation

0.60 <= confidence < 0.80
→ show as low confidence

confidence < 0.60
→ hide / debug only
```

> Đây là target ban đầu, cần hiệu chỉnh sau evaluation.

---

# 10. Rule Mapper

## 10.1. Native OpenMetadata Mapping

Kiểm tra candidate rule có map được native Test Definition không.

Nếu có:

```text
Canonical Rule
→ OpenMetadata Test Case Payload
```

---

## 10.2. Custom SQL Fallback

Nếu không có native representation:

```text
Canonical Rule
→ SQL Generator
→ SQL Safety Validator
→ Custom SQL Test
```

Ví dụ:

```text
delivery_date >= order_date
```

→

```sql
SELECT COUNT(*)
FROM orders
WHERE delivery_date < order_date
```

Expected:

```text
COUNT = 0
```

---

# 11. SQL Safety

Custom SQL chỉ được phép:

```text
SELECT
```

Reject:

```text
INSERT
UPDATE
DELETE
DROP
ALTER
CREATE
TRUNCATE
```

Yêu cầu:

- SQL parser / AST validation;
- read-only DB account;
- timeout;
- resource limit;
- query row/scan limit nếu hỗ trợ;
- không execute trực tiếp bằng credential có quyền ghi.

---

# 12. Human Review

UI/API phải hỗ trợ:

```text
Accept
Edit
Reject
```

Mỗi recommendation hiển thị:

- rule type;
- condition;
- target columns;
- reason;
- evidence;
- confidence;
- execution type;
- duplicate/conflict status.

### Feedback lưu lại

```json
{
  "suggestion_id": "...",
  "decision": "ACCEPT",
  "original_rule": {},
  "edited_rule": null,
  "reviewed_at": "..."
}
```

---

# 13. API Design

## POST `/advanced-rules/recommend`

### Request

```json
{
  "table_fqn": "service.database.schema.orders"
}
```

### Response

```json
{
  "table_fqn": "...",
  "recommendations": [],
  "router_result": {},
  "processing_summary": {
    "selected_rule_types": 2,
    "generated_candidates": 4,
    "validated_candidates": 3
  }
}
```

---

## POST `/advanced-rules/{id}/approve`

```json
{
  "action": "ACCEPT"
}
```

---

## POST `/advanced-rules/{id}/edit`

```json
{
  "action": "EDIT",
  "rule": {}
}
```

---

## POST `/advanced-rules/{id}/reject`

```json
{
  "action": "REJECT",
  "reason": "Not a valid business constraint"
}
```

---

# 14. Suggested Project Structure

```text
app/
├── api/
│   └── advanced_rules.py
│
├── clients/
│   └── openmetadata_client.py
│
├── context/
│   ├── context_builder.py
│   └── candidate_selector.py
│
├── llm/
│   ├── client.py
│   ├── router.py
│   └── generators/
│       ├── cross_column.py
│       ├── conditional_dependency.py
│       └── temporal.py
│
├── validation/
│   ├── schema_validator.py
│   ├── datatype_validator.py
│   ├── duplicate_checker.py
│   └── sql_validator.py
│
├── mapping/
│   ├── native_mapper.py
│   └── custom_sql_mapper.py
│
├── models/
│   ├── context.py
│   ├── router.py
│   └── rule.py
│
├── services/
│   └── advanced_rule_service.py
│
├── prompts/
│   ├── router.txt
│   ├── cross_column.txt
│   ├── conditional_dependency.txt
│   └── temporal.txt
│
└── tests/
```

---

# 15. Implementation Phases

## Phase 1 — Data Contract + OpenMetadata Context

### Tasks

- [ ] Define Pydantic models.
- [ ] Implement OpenMetadata client.
- [ ] Fetch table/column metadata.
- [ ] Fetch profiling.
- [ ] Fetch descriptions.
- [ ] Fetch existing tests.
- [ ] Fetch relationships nếu có.
- [ ] Build normalized context.

### Deliverable

```text
table_fqn
→ FullRuleContext JSON
```

### Done khi

Một table thực tế từ OpenMetadata có thể được convert ổn định sang context chuẩn.

---

# Phase 2 — Router POC

### Tasks

- [ ] Define supported Advanced Rule Types.
- [ ] Viết router prompt.
- [ ] Enforce JSON output.
- [ ] Implement multi-label selection.
- [ ] Return evidence columns.
- [ ] Add confidence.
- [ ] Add empty-result behavior.

### Deliverable

```text
FullRuleContext
→ RouterResult
```

### Done khi

Router nhận diện hợp lý các nhóm:

- Cross-column;
- Conditional;
- Temporal;

trên bộ test tables.

---

# Phase 3 — Specialized Generators

### Tasks

- [ ] Cross-column prompt.
- [ ] Conditional prompt.
- [ ] Temporal prompt.
- [ ] Pydantic output schema.
- [ ] Empty output nếu không đủ evidence.
- [ ] Canonical Rule conversion.

### Deliverable

```text
RouterResult
→ CanonicalRule[]
```

### Done khi

Mỗi generator có thể chạy độc lập và trả structured JSON hợp lệ.

---

# Phase 4 — Validator

### Tasks

- [ ] JSON/schema validation.
- [ ] Column existence validation.
- [ ] Datatype compatibility.
- [ ] Duplicate detection.
- [ ] Conflict flagging.
- [ ] Confidence gate.

### Deliverable

```text
CanonicalRule[]
→ ValidatedRule[]
```

### Done khi

Rule hallucinated/sai column/sai datatype bị reject hoặc flag.

---

# Phase 5 — OpenMetadata Mapper

### Tasks

- [ ] Determine native rule support.
- [ ] Native mapping.
- [ ] Custom SQL fallback.
- [ ] SQL AST validation.
- [ ] Read-only execution test.
- [ ] Build OpenMetadata Test Case payload.

### Deliverable

```text
ValidatedRule
→ Executable OpenMetadata rule
```

---

# Phase 6 — Human Review Flow

### Tasks

- [ ] Recommendation endpoint.
- [ ] Accept/Edit/Reject.
- [ ] Persist feedback.
- [ ] Only create Test Case after approval.

### Deliverable

```text
Suggestion
→ Human Review
→ OpenMetadata Test Case
```

---

# Phase 7 — Evaluation

## 7.1. Benchmark Dataset

Tạo tập tables có Ground Truth Advanced Rules.

Ví dụ:

```text
orders
patients
payments
events
customers
```

Ground truth do developer/mentor xác nhận trước.

---

## 7.2. Metrics

### Router Recall

Router có chọn đúng loại rule cần thiết không?

```text
correct rule types selected
---------------------------
ground truth rule types
```

---

### Rule Precision

```text
correct generated rules
-----------------------
all generated rules
```

---

### Rule Recall

```text
correct generated rules
-----------------------
ground truth rules
```

---

### Semantic Correctness

Manual review:

```text
CORRECT
PARTIALLY_CORRECT
INCORRECT
```

---

### Executability

```text
rules that execute successfully
-------------------------------
rules mapped for execution
```

---

### Acceptance Rate

```text
accepted suggestions
--------------------
all suggestions
```

---

### Utilization Rate

```text
accepted + edited
-----------------
all suggestions
```

---

# 16. Comparison Experiment

POC nên so sánh:

## A. Sequential All-Rule-Type Calls

```text
Context
→ Cross-column prompt
→ Conditional prompt
→ Temporal prompt
```

## B. Router + Specialized Generator

```text
Context
→ Router
→ Selected Generators
```

### So sánh theo

- Precision;
- Recall;
- Router Recall;
- token usage;
- LLM calls/table;
- latency;
- invalid suggestions.

Mục tiêu: kiểm chứng Router có giảm cost/noise mà không làm giảm Recall quá nhiều hay không.

---

# 17. Security Requirements

## Sensitive Data

Không gửi raw PII/PHI vào LLM nếu không cần.

Ưu tiên:

```text
metadata
profiling
description
relationship
glossary
```

Sample data:

- optional;
- masked;
- limited.

---

## Prompt Injection

Metadata/description/documentation được coi là untrusted input.

Không cho context override system instruction.

---

## Credentials

- OpenMetadata token không hard-code.
- LLM API key không log.
- DB credentials dùng secret/environment.
- Least privilege.

---

## Custom SQL

- read-only;
- AST validation;
- timeout;
- resource limits.

---

# 18. Logging & Observability

Mỗi request nên lưu:

```text
request_id
table_fqn
router_output
selected_generators
generated_rule_count
validation_result
latency
token_usage
final_decision
```

Không log:

```text
API key
Authorization header
raw sensitive sample
full patient/customer identifiers
```

---

# 19. Acceptance Criteria cho POC

POC được coi là hoàn thành khi:

- [ ] Lấy được context từ OpenMetadata.
- [ ] Router hoạt động multi-label.
- [ ] Hỗ trợ 3 Advanced Rule Types.
- [ ] Tất cả LLM output theo structured JSON.
- [ ] Có canonical rule schema.
- [ ] Có validator.
- [ ] Có duplicate check.
- [ ] Có Native/Custom SQL mapping.
- [ ] Custom SQL read-only + validated.
- [ ] Có Accept/Edit/Reject.
- [ ] Tạo được Test Case sau approval.
- [ ] Có benchmark nhỏ.
- [ ] Có Precision/Recall và Router Recall.
- [ ] Có comparison Router vs Sequential calls.

---

# 20. Thứ tự ưu tiên triển khai

```text
P0 — Must Have
1. Context Builder
2. Router
3. Cross-column Generator
4. Conditional Generator
5. Canonical Rule Schema
6. Validator

P1 — Important
7. Temporal Generator
8. Duplicate Check
9. Native Mapper
10. Custom SQL Fallback
11. Human Review

P2 — Evaluation / Improvement
12. Benchmark
13. Router vs Sequential experiment
14. Feedback Store
15. Semantic Search / RAG
```

---

# 21. Future Work

Không đưa vào scope POC đầu:

- semantic search/RAG trên business documents;
- embedding-based candidate column selection;
- cross-table rule generation;
- historical user feedback learning;
- confidence calibration;
- automatic rule ranking;
- domain-specific rule packs;
- fine-tuning model;
- autonomous rule publishing.

---

# 22. End-to-End Pseudocode

```python
def recommend_advanced_rules(table_fqn: str):

    raw_context = openmetadata.get_table_context(table_fqn)

    context = context_builder.build(raw_context)

    router_context = context_builder.build_router_context(context)

    router_result = router.route(router_context)

    candidates = []

    for selected in router_result.candidate_rule_types:

        generator = generator_registry.get(selected.type)

        generator_context = context_builder.build_generator_context(
            context=context,
            evidence_columns=selected.evidence_columns
        )

        rules = generator.generate(generator_context)

        candidates.extend(rules)

    canonical_rules = normalize_rules(candidates)

    validated_rules = validator.validate(
        canonical_rules,
        context=context
    )

    mapped_rules = rule_mapper.map(validated_rules)

    return mapped_rules
```

---

# 23. Kết quả cuối mong đợi

Input:

```text
Table: orders
```

Output:

```json
[
  {
    "rule_category": "CROSS_COLUMN",
    "columns": ["order_date", "delivery_date"],
    "condition": "delivery_date >= order_date",
    "confidence": 0.92,
    "execution_type": "CUSTOM_SQL",
    "status": "READY_FOR_REVIEW"
  },
  {
    "rule_category": "CONDITIONAL_DEPENDENCY",
    "columns": ["status", "completed_at"],
    "condition": "IF status = 'completed' THEN completed_at IS NOT NULL",
    "confidence": 0.88,
    "execution_type": "CUSTOM_SQL",
    "status": "READY_FOR_REVIEW"
  }
]
```

Sau đó:

```text
Human Review
→ Accept
→ Create OpenMetadata Test Case
→ Execute
→ PASS / FAIL
```

---

# 24. Definition of Done

Advanced Rule module đạt Definition of Done khi có thể thực hiện hoàn chỉnh flow:

```text
OpenMetadata Table
→ Context Retrieval
→ Router
→ Specialized Generator
→ Canonical Rule
→ Validation
→ Mapping
→ Human Review
→ OpenMetadata Test Case
```

và có dữ liệu evaluation đủ để trả lời:

1. Rule sinh ra đúng bao nhiêu?
2. Router có bỏ sót rule type không?
3. Router có giảm LLM calls/token so với gọi lần lượt không?
4. Rule có execute được không?
5. User có chấp nhận recommendation không?
