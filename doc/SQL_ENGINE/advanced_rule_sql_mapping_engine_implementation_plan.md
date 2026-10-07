# Implementation Plan — Advanced Rule SQL Mapping Engine

## 1. Scope

This implementation is **only for Advanced Data Quality Rules**.

Supported Advanced Rule types:

```text
CROSS_COLUMN
CONDITIONAL_DEPENDENCY
TEMPORAL
```

This mapper is **not** responsible for Basic Rules such as:

```text
RANGE
ALLOWED_VALUES
REGEX
DATATYPE
UNIQUENESS
```

Basic Rules should remain in a separate mapping/execution flow.

---

# 2. Goal

Implement a deterministic SQL Mapping Engine that converts the structured output of the Advanced Rule LLM into executable SQL.

Target flow:

```text
Advanced Rule LLM Output
        ↓
Contract Validation
        ↓
Condition Compiler
        ↓
Rule-specific Condition Combiner
        ↓
Violation Predicate
        ↓
SQL Query Builder
        ↓
Executable SQL
```

The LLM must describe the **valid expected rule**.

The SQL Mapping Engine must generate SQL that finds **violating rows**.

Example:

```text
LLM semantic rule:
healthcare_coverage <= healthcare_expenses
```

Mapper output:

```sql
SELECT *
FROM patients
WHERE healthcare_coverage > healthcare_expenses;
```

---

# 3. Input Contract

The Advanced Rule Mapper receives the common LLM output schema:

```json
{
  "table": "table_name",

  "columns": [
    "column_a",
    "column_b"
  ],

  "rule_type": "CROSS_COLUMN | CONDITIONAL_DEPENDENCY | TEMPORAL",

  "conditions": [
    {
    }
  ],

  "confidence": 0.95,
  "reason": "..."
}
```

Core fields used by the mapper:

```text
table
columns
rule_type
conditions[]
```

`confidence` and `reason` are metadata and do not affect SQL generation.

Important:

- `columns[]` must not be used to infer semantic direction.
- All executable rule semantics must be represented in `conditions[]`.
- Multi-column rules are represented using multiple conditions or multiple arithmetic operands.

---

# 4. Rule-to-Condition Support Matrix

The mapper must enforce which condition types are valid for each Advanced Rule.

| Condition Type | CROSS_COLUMN | CONDITIONAL_DEPENDENCY | TEMPORAL |
|---|---:|---:|---:|
| `COMPARISON` | Yes | Yes | No |
| `NULL_CHECK` | No | Yes | No |
| `SET` | No | Yes | No |
| `ARITHMETIC` | Yes | No in V1 | No |
| `TEMPORAL_ORDER` | No | No in V1 | Yes |
| `DURATION` | No | No in V1 | Yes |

V1 rule ownership:

```text
CROSS_COLUMN
├── COMPARISON
└── ARITHMETIC

CONDITIONAL_DEPENDENCY
├── COMPARISON
├── NULL_CHECK
└── SET

TEMPORAL
├── TEMPORAL_ORDER
└── DURATION
```

Do not silently accept unsupported rule/condition combinations.

Example:

```text
TEMPORAL + ARITHMETIC
```

must fail validation.

---

# 5. SQL Mapper Module Structure

Recommended module layout:

```text
advanced_rule_sql_mapper/
│
├── mapper.py
├── validator.py
├── condition_compiler.py
├── rule_compiler.py
├── operator_maps.py
├── sql_utils.py
├── compile_context.py
│
└── tests/
    ├── test_cross_column_mapper.py
    ├── test_conditional_mapper.py
    ├── test_temporal_mapper.py
    ├── test_condition_compiler.py
    └── test_validator.py
```

If equivalent modules already exist in the repository, reuse them instead of duplicating architecture.

---

# 6. Main Public API

Implement one main entry point:

```python
map_advanced_rule_to_sql(rule)
```

Input:

```python
rule: AdvancedRuleOutput
```

Output should contain at least:

```json
{
  "violation_predicate": "...",
  "sql": "...",
  "params": {}
}
```

Recommended output:

```json
{
  "rule_type": "CROSS_COLUMN",
  "table": "patients",
  "violation_predicate": "\"healthcare_coverage\" > \"healthcare_expenses\"",
  "sql": "SELECT * FROM \"patients\" WHERE \"healthcare_coverage\" > \"healthcare_expenses\"",
  "params": {}
}
```

---

# 7. Operator Maps

Create all operator mappings centrally.

## Comparison operators

```python
SQL_OPERATORS = {
    "EQ": "=",
    "NEQ": "<>",
    "GT": ">",
    "GTE": ">=",
    "LT": "<",
    "LTE": "<=",
}
```

## Operator negation

```python
NEGATED_OPERATORS = {
    "EQ": "NEQ",
    "NEQ": "EQ",

    "GT": "LTE",
    "GTE": "LT",

    "LT": "GTE",
    "LTE": "GT",

    "IS_NULL": "IS_NOT_NULL",
    "IS_NOT_NULL": "IS_NULL",

    "IN": "NOT_IN",
    "NOT_IN": "IN",

    "BEFORE": "AFTER_EQUAL",
    "BEFORE_EQUAL": "AFTER",
    "AFTER": "BEFORE_EQUAL",
    "AFTER_EQUAL": "BEFORE",
}
```

## Arithmetic operators

```python
ARITHMETIC_OPERATORS = {
    "ADD": "+",
    "SUBTRACT": "-",
    "MULTIPLY": "*",
    "DIVIDE": "/",
}
```

## Temporal operators

```python
TEMPORAL_OPERATORS = {
    "BEFORE": "LT",
    "BEFORE_EQUAL": "LTE",
    "AFTER": "GT",
    "AFTER_EQUAL": "GTE",
}
```

---

# 8. Compile Context

Literal values must not be directly interpolated into SQL.

Create a compile context:

```python
class CompileContext:
    def __init__(self):
        self.params = {}
        self.counter = 0

    def add_param(self, value):
        self.counter += 1
        key = f"rule_param_{self.counter}"
        self.params[key] = value
        return f":{key}"
```

Example:

Input literal:

```json
{
  "type": "literal",
  "value": "US"
}
```

Generated SQL:

```sql
"country" = :rule_param_1
```

Parameters:

```json
{
  "rule_param_1": "US"
}
```

---

# 9. SQL Identifier Safety

Table and column names come from LLM output and must be validated.

Implement:

```python
quote_identifier(identifier)
```

Support:

```text
table
schema.table
```

Examples:

```text
patients
→ "patients"

public.patients
→ "public"."patients"
```

Reject unsafe identifiers.

Recommended identifier pattern:

```regex
^[A-Za-z_][A-Za-z0-9_]*$
```

Do not directly interpolate unvalidated table or column names.

---

# 10. Condition Compiler Dispatcher

Implement a generic dispatcher:

```python
compile_condition(condition, ctx, negate=False)
```

Routing:

```text
COMPARISON
    → compile_comparison()

NULL_CHECK
    → compile_null_check()

SET
    → compile_set()

ARITHMETIC
    → compile_arithmetic()

TEMPORAL_ORDER
    → compile_temporal_order()

DURATION
    → compile_duration()
```

The `negate` parameter determines whether to compile:

```text
valid condition
```

or:

```text
violation condition
```

---

# 11. CROSS_COLUMN — COMPARISON

## Supported by

```text
Rule:
CROSS_COLUMN

Condition:
COMPARISON
```

Supported operators:

```text
EQ
NEQ
GT
GTE
LT
LTE
```

Input example:

```json
{
  "type": "COMPARISON",
  "left": "healthcare_coverage",
  "operator": "LTE",
  "right": {
    "type": "column",
    "value": "healthcare_expenses"
  }
}
```

Valid semantic:

```text
healthcare_coverage <= healthcare_expenses
```

Violation:

```text
healthcare_coverage > healthcare_expenses
```

Compiler behavior:

```python
compile_comparison(condition, negate=False)
```

returns:

```sql
"healthcare_coverage" <= "healthcare_expenses"
```

while:

```python
compile_comparison(condition, negate=True)
```

returns:

```sql
"healthcare_coverage" > "healthcare_expenses"
```

---

# 12. CROSS_COLUMN — Multiple Comparisons

## Supported by

```text
Rule:
CROSS_COLUMN

Condition:
multiple COMPARISON objects
```

Example semantic:

```text
min_value <= actual_value <= max_value
```

Input:

```json
{
  "rule_type": "CROSS_COLUMN",
  "conditions": [
    {
      "type": "COMPARISON",
      "left": "min_value",
      "operator": "LTE",
      "right": {
        "type": "column",
        "value": "actual_value"
      }
    },
    {
      "type": "COMPARISON",
      "left": "actual_value",
      "operator": "LTE",
      "right": {
        "type": "column",
        "value": "max_value"
      }
    }
  ]
}
```

Valid:

```text
A AND B
```

Violation:

```text
NOT(A AND B)
```

which becomes:

```text
NOT A OR NOT B
```

Generated predicate:

```sql
("min_value" > "actual_value")
OR
("actual_value" > "max_value")
```

This same logic must work for 3, 4, or more columns.

---

# 13. CROSS_COLUMN — ARITHMETIC

## Supported by

```text
Rule:
CROSS_COLUMN

Condition:
ARITHMETIC
```

Supported arithmetic operators:

```text
ADD
SUBTRACT
MULTIPLY
DIVIDE
```

Supported final comparison operators:

```text
EQ
NEQ
GT
GTE
LT
LTE
```

Example:

```text
total = quantity * price
```

Input:

```json
{
  "type": "ARITHMETIC",

  "target": "total",

  "comparison_operator": "EQ",

  "expression": {
    "operator": "MULTIPLY",
    "operands": [
      "quantity",
      "price"
    ]
  }
}
```

Valid SQL:

```sql
"total" = ("quantity" * "price")
```

Violation:

```sql
"total" <> ("quantity" * "price")
```

---

# 14. CROSS_COLUMN — Arithmetic with 3+ Columns

Example:

```text
total = subtotal + tax + shipping
```

Input:

```json
{
  "type": "ARITHMETIC",
  "target": "total",
  "comparison_operator": "EQ",
  "expression": {
    "operator": "ADD",
    "operands": [
      "subtotal",
      "tax",
      "shipping"
    ]
  }
}
```

Generated violation:

```sql
"total" <> (
    "subtotal"
    + "tax"
    + "shipping"
)
```

Rules:

- `ADD` may have 2+ operands.
- `MULTIPLY` may have 2+ operands.
- `SUBTRACT` must preserve operand order.
- `DIVIDE` must preserve operand order.

---

# 15. Safe Division

For PostgreSQL V1, division should avoid divide-by-zero errors.

Example:

```text
ratio = numerator / denominator
```

Prefer:

```sql
"ratio" <> (
    "numerator" / NULLIF("denominator", 0)
)
```

For multiple divide operands, preserve left-to-right order.

---

# 16. CONDITIONAL_DEPENDENCY — Rule Semantics

Conditional rules are different from Cross-column and Temporal.

Conditions contain:

```text
role = IF
```

or:

```text
role = THEN
```

Mapper behavior:

```text
IF_GROUP =
    all role=IF conditions joined by AND

THEN_GROUP =
    all role=THEN conditions joined by AND
```

Valid semantic:

```text
IF_GROUP → THEN_GROUP
```

Violation:

```text
IF_GROUP
AND
NOT(THEN_GROUP)
```

If THEN has multiple conditions:

```text
NOT(B AND C)
=
NOT(B) OR NOT(C)
```

---

# 17. CONDITIONAL_DEPENDENCY — COMPARISON

## Supported by

```text
Rule:
CONDITIONAL_DEPENDENCY

Condition:
COMPARISON
```

Can be used in both:

```text
IF
THEN
```

Example:

```text
IF quantity > 0
THEN amount > 0
```

Input:

```json
{
  "conditions": [
    {
      "role": "IF",
      "type": "COMPARISON",
      "left": "quantity",
      "operator": "GT",
      "right": {
        "type": "literal",
        "value": 0
      }
    },
    {
      "role": "THEN",
      "type": "COMPARISON",
      "left": "amount",
      "operator": "GT",
      "right": {
        "type": "literal",
        "value": 0
      }
    }
  ]
}
```

Generated violation:

```sql
("quantity" > :rule_param_1)
AND
("amount" <= :rule_param_2)
```

---

# 18. CONDITIONAL_DEPENDENCY — Column-to-Column Comparison

## Supported by

```text
Rule:
CONDITIONAL_DEPENDENCY

Condition:
COMPARISON
```

Example:

```text
IF status = 'COMPLETED'
THEN paid_amount = total_amount
```

Input:

```json
{
  "conditions": [
    {
      "role": "IF",
      "type": "COMPARISON",
      "left": "status",
      "operator": "EQ",
      "right": {
        "type": "literal",
        "value": "COMPLETED"
      }
    },
    {
      "role": "THEN",
      "type": "COMPARISON",
      "left": "paid_amount",
      "operator": "EQ",
      "right": {
        "type": "column",
        "value": "total_amount"
      }
    }
  ]
}
```

Violation:

```sql
("status" = :rule_param_1)
AND
("paid_amount" <> "total_amount")
```

---

# 19. CONDITIONAL_DEPENDENCY — NULL_CHECK

## Supported by

```text
Rule:
CONDITIONAL_DEPENDENCY

Condition:
NULL_CHECK
```

Supported operators:

```text
IS_NULL
IS_NOT_NULL
```

Example:

```text
IF total_orders = 0
THEN last_order_date IS NULL
```

Violation:

```sql
("total_orders" = :rule_param_1)
AND
("last_order_date" IS NOT NULL)
```

Example:

```text
IF status = 'DECEASED'
THEN deathdate IS NOT NULL
```

Violation:

```sql
("status" = :rule_param_1)
AND
("deathdate" IS NULL)
```

---

# 20. CONDITIONAL_DEPENDENCY — SET

## Supported by

```text
Rule:
CONDITIONAL_DEPENDENCY

Condition:
SET
```

Supported operators:

```text
IN
NOT_IN
```

Example:

```text
IF country = 'US'
THEN currency IN ('USD', 'USN')
```

Violation:

```sql
("country" = :rule_param_1)
AND
(
    "currency" NOT IN (
        :rule_param_2,
        :rule_param_3
    )
)
```

---

# 21. CONDITIONAL_DEPENDENCY — Multiple IF Conditions

Example:

```text
IF age >= 18
AND country = 'US'
THEN ssn IS NOT NULL
```

Generated violation:

```sql
(
    ("age" >= :rule_param_1)
    AND
    ("country" = :rule_param_2)
)
AND
(
    "ssn" IS NULL
)
```

Implementation:

```python
if_group = combine_and(
    compile_condition(c, negate=False)
    for c in if_conditions
)
```

---

# 22. CONDITIONAL_DEPENDENCY — Multiple THEN Conditions

Example:

```text
IF status = 'COMPLETED'
THEN completed_at IS NOT NULL
AND amount > 0
```

Valid THEN:

```text
B AND C
```

Violation THEN:

```text
NOT B OR NOT C
```

Generated:

```sql
("status" = :rule_param_1)
AND
(
    ("completed_at" IS NULL)
    OR
    ("amount" <= :rule_param_2)
)
```

Implementation:

```python
then_violation_group = combine_or(
    compile_condition(c, negate=True)
    for c in then_conditions
)
```

---

# 23. TEMPORAL — TEMPORAL_ORDER

## Supported by

```text
Rule:
TEMPORAL

Condition:
TEMPORAL_ORDER
```

Supported operators:

```text
BEFORE
BEFORE_EQUAL
AFTER
AFTER_EQUAL
```

Semantic mapping:

```text
BEFORE
→ <

BEFORE_EQUAL
→ <=

AFTER
→ >

AFTER_EQUAL
→ >=
```

Example:

```text
birthdate <= deathdate
```

Input:

```json
{
  "type": "TEMPORAL_ORDER",
  "left": "birthdate",
  "operator": "BEFORE_EQUAL",
  "right": "deathdate"
}
```

Violation:

```sql
"birthdate" > "deathdate"
```

---

# 24. TEMPORAL — Multiple Temporal Conditions

Example:

```text
created_at <= processed_at <= completed_at
```

Input:

```json
{
  "conditions": [
    {
      "type": "TEMPORAL_ORDER",
      "left": "created_at",
      "operator": "BEFORE_EQUAL",
      "right": "processed_at"
    },
    {
      "type": "TEMPORAL_ORDER",
      "left": "processed_at",
      "operator": "BEFORE_EQUAL",
      "right": "completed_at"
    }
  ]
}
```

Valid:

```text
A AND B
```

Violation:

```text
NOT A OR NOT B
```

Generated:

```sql
("created_at" > "processed_at")
OR
("processed_at" > "completed_at")
```

This must support any number of temporal columns.

---

# 25. TEMPORAL — DURATION

## Supported by

```text
Rule:
TEMPORAL

Condition:
DURATION
```

Supported comparison operators:

```text
GT
GTE
LT
LTE
```

Supported units:

```text
MINUTE
HOUR
DAY
```

Example:

```text
end_time - start_time <= 30 DAY
```

Input:

```json
{
  "type": "DURATION",
  "start_column": "start_time",
  "end_column": "end_time",
  "operator": "LTE",
  "value": 30,
  "unit": "DAY"
}
```

Compile valid semantic as:

```sql
"end_time"
<=
"start_time" + INTERVAL '30 DAY'
```

Violation:

```sql
"end_time"
>
"start_time" + INTERVAL '30 DAY'
```

Duration unit must be validated against a whitelist.

---

# 26. Standard Rule Combiner

`CROSS_COLUMN` and `TEMPORAL` use the same combination strategy.

LLM conditions describe the valid state:

```text
C1 AND C2 AND ... AND Cn
```

Violation is:

```text
NOT(C1 AND C2 AND ... AND Cn)
```

Equivalent:

```text
NOT C1
OR NOT C2
OR ...
OR NOT Cn
```

Implementation:

```python
def compile_standard_rule(conditions, ctx):
    violations = [
        compile_condition(
            condition,
            ctx,
            negate=True
        )
        for condition in conditions
    ]

    return combine_or(violations)
```

Used by:

```text
CROSS_COLUMN
TEMPORAL
```

---

# 27. Conditional Rule Combiner

Used only by:

```text
CONDITIONAL_DEPENDENCY
```

Implementation concept:

```python
def compile_conditional_rule(conditions, ctx):
    if_conditions = [
        c for c in conditions
        if c.get("role") == "IF"
    ]

    then_conditions = [
        c for c in conditions
        if c.get("role") == "THEN"
    ]

    if_group = combine_and([
        compile_condition(c, ctx, negate=False)
        for c in if_conditions
    ])

    then_violation_group = combine_or([
        compile_condition(c, ctx, negate=True)
        for c in then_conditions
    ])

    return (
        f"({if_group}) "
        f"AND "
        f"({then_violation_group})"
    )
```

---

# 28. Main Rule Dispatcher

Implement:

```python
def build_violation_predicate(rule, ctx):
    if rule["rule_type"] == "CROSS_COLUMN":
        return compile_standard_rule(
            rule["conditions"],
            ctx
        )

    if rule["rule_type"] == "TEMPORAL":
        return compile_standard_rule(
            rule["conditions"],
            ctx
        )

    if rule["rule_type"] == "CONDITIONAL_DEPENDENCY":
        return compile_conditional_rule(
            rule["conditions"],
            ctx
        )

    raise UnsupportedRuleType(...)
```

---

# 29. SQL Query Builder

After generating the violation predicate:

```python
def build_sql(table, violation_predicate):
    table_sql = quote_identifier(table)

    return (
        f"SELECT * "
        f"FROM {table_sql} "
        f"WHERE {violation_predicate}"
    )
```

Recommended future extension:

```text
SELECT COUNT(*)
SELECT violating rows
SELECT violation ratio
```

Keep query building separate from condition compilation.

---

# 30. Validation Layer

Validation must run before compilation.

## Common validation

Check:

```text
table exists and is safe
rule_type supported
conditions is not empty
columns is not empty
all referenced columns are valid
condition.type supported
operators supported
```

---

# 31. CROSS_COLUMN Validation

Allowed:

```text
COMPARISON
ARITHMETIC
```

Reject:

```text
NULL_CHECK
SET
TEMPORAL_ORDER
DURATION
```

Validation rules:

### COMPARISON

Require:

```text
left
operator
right
```

### ARITHMETIC

Require:

```text
target
comparison_operator
expression.operator
expression.operands >= 2
```

All operands must reference columns in the rule/table metadata.

---

# 32. CONDITIONAL_DEPENDENCY Validation

Allowed:

```text
COMPARISON
NULL_CHECK
SET
```

Every condition must contain:

```text
role = IF
```

or:

```text
role = THEN
```

Require:

```text
at least 1 IF
at least 1 THEN
```

Reject unknown roles.

---

# 33. TEMPORAL Validation

Allowed:

```text
TEMPORAL_ORDER
DURATION
```

### TEMPORAL_ORDER

Require:

```text
left
right
operator
```

Both referenced columns should be temporal-compatible according to available metadata.

### DURATION

Require:

```text
start_column
end_column
operator
value
unit
```

Require:

```text
value > 0
```

Unit must be one of:

```text
MINUTE
HOUR
DAY
```

---

# 34. NULL Semantics for V1

For V1:

```text
COMPARISON
ARITHMETIC
TEMPORAL_ORDER
DURATION
```

should follow normal SQL NULL behavior.

That means:

```text
NULL comparison result = UNKNOWN
```

and is not automatically treated as a violation.

If NULL itself must be checked, the LLM should generate an explicit:

```text
NULL_CHECK
```

condition where supported.

Do not add a `null_policy` field in V1 unless the existing project already requires it.

---

# 35. Main Mapper Implementation

Conceptual implementation:

```python
def map_advanced_rule_to_sql(rule):
    validate_advanced_rule(rule)

    ctx = CompileContext()

    violation_predicate = build_violation_predicate(
        rule,
        ctx
    )

    sql = build_sql(
        rule["table"],
        violation_predicate
    )

    return {
        "rule_type": rule["rule_type"],
        "table": rule["table"],
        "violation_predicate": violation_predicate,
        "sql": sql,
        "params": ctx.params,
    }
```

---

# 36. Implementation Order

Implement in this order.

## Phase 1 — SQL Utilities

Implement:

```text
quote_identifier()
CompileContext
combine_and()
combine_or()
operator maps
```

Acceptance:

```text
safe table/column quoting works
literal parameters are bound
```

---

## Phase 2 — CROSS_COLUMN / COMPARISON

Implement:

```text
compile_operand()
compile_comparison()
compile_condition()
```

Support:

```text
EQ
NEQ
GT
GTE
LT
LTE
```

Test both:

```text
column ↔ column
column ↔ literal
```

Acceptance:

```text
CROSS_COLUMN comparison rule
→ correct violation SQL
```

---

## Phase 3 — CROSS_COLUMN / ARITHMETIC

Implement:

```text
ADD
SUBTRACT
MULTIPLY
DIVIDE
```

Support 2+ operands.

Implement safe divide behavior.

Acceptance examples:

```text
total = quantity * price
total = subtotal + tax + shipping
remaining = total - used
ratio = numerator / denominator
```

---

## Phase 4 — CONDITIONAL_DEPENDENCY

Implement:

```text
role = IF
role = THEN
```

Condition types:

```text
COMPARISON
NULL_CHECK
SET
```

Support:

```text
single IF
multiple IF

single THEN
multiple THEN

literal comparison
column comparison
NULL / NOT NULL
IN / NOT IN
```

Acceptance:

```text
IF A THEN B
→ A AND NOT B

IF A AND B THEN C
→ A AND B AND NOT C

IF A THEN B AND C
→ A AND (NOT B OR NOT C)
```

---

## Phase 5 — TEMPORAL / TEMPORAL_ORDER

Implement:

```text
BEFORE
BEFORE_EQUAL
AFTER
AFTER_EQUAL
```

Support multiple temporal conditions.

Acceptance:

```text
birthdate <= deathdate

created_at <= processed_at <= completed_at
```

---

## Phase 6 — TEMPORAL / DURATION

Implement:

```text
GT
GTE
LT
LTE
```

Units:

```text
MINUTE
HOUR
DAY
```

Acceptance:

```text
duration <= 30 DAY
duration >= 1 HOUR
```

---

## Phase 7 — Full Validator

Implement rule/condition compatibility validation.

Reject invalid examples:

```text
CROSS_COLUMN + DURATION

TEMPORAL + ARITHMETIC

CONDITIONAL_DEPENDENCY without IF

CONDITIONAL_DEPENDENCY without THEN

unsupported operator

unknown column

unsafe identifier

invalid duration unit
```

---

## Phase 8 — Integration

Connect:

```text
Advanced Rule LLM output
→ validate
→ SQL Mapper
→ generated SQL
```

Do not modify LLM semantic reasoning beyond what is required to conform to the agreed contract.

---

# 37. Minimum Unit Tests

## CROSS_COLUMN

### Comparison EQ

Valid:

```text
A = B
```

Violation:

```text
A <> B
```

### Comparison LTE

Valid:

```text
A <= B
```

Violation:

```text
A > B
```

### Multiple comparisons

Valid:

```text
A <= B
AND B <= C
```

Violation:

```text
A > B
OR B > C
```

### Arithmetic multiply

Valid:

```text
total = quantity * price
```

Violation:

```text
total <> quantity * price
```

### Arithmetic 3+ operands

Valid:

```text
total = subtotal + tax + shipping
```

Violation:

```text
total <> subtotal + tax + shipping
```

---

# 38. CONDITIONAL_DEPENDENCY Tests

### IF → comparison

```text
IF quantity > 0
THEN amount > 0
```

Expected:

```text
quantity > 0
AND amount <= 0
```

### IF → NULL

```text
IF total_orders = 0
THEN last_order_date IS NULL
```

Expected:

```text
total_orders = 0
AND last_order_date IS NOT NULL
```

### IF → NOT NULL

```text
IF status = 'DECEASED'
THEN deathdate IS NOT NULL
```

Expected:

```text
status = 'DECEASED'
AND deathdate IS NULL
```

### IF → IN

```text
IF country = 'US'
THEN currency IN ('USD', 'USN')
```

Expected:

```text
country = 'US'
AND currency NOT IN ('USD', 'USN')
```

### Multiple IF

```text
IF A AND B
THEN C
```

Expected:

```text
A AND B AND NOT C
```

### Multiple THEN

```text
IF A
THEN B AND C
```

Expected:

```text
A AND (NOT B OR NOT C)
```

---

# 39. TEMPORAL Tests

### BEFORE

Valid:

```text
A < B
```

Violation:

```text
A >= B
```

### BEFORE_EQUAL

Valid:

```text
A <= B
```

Violation:

```text
A > B
```

### AFTER

Valid:

```text
A > B
```

Violation:

```text
A <= B
```

### AFTER_EQUAL

Valid:

```text
A >= B
```

Violation:

```text
A < B
```

### Temporal sequence

Valid:

```text
A <= B
AND B <= C
```

Violation:

```text
A > B
OR B > C
```

### Duration

Valid:

```text
end - start <= 30 DAY
```

Violation:

```text
end > start + INTERVAL '30 DAY'
```

---

# 40. Definition of Done

The Advanced Rule SQL Mapping Engine is complete when:

```text
✓ Supports CROSS_COLUMN
  ✓ COMPARISON
  ✓ ARITHMETIC
  ✓ 2-column rules
  ✓ 3+ column rules

✓ Supports CONDITIONAL_DEPENDENCY
  ✓ COMPARISON
  ✓ NULL_CHECK
  ✓ SET
  ✓ multiple IF conditions
  ✓ multiple THEN conditions
  ✓ literal RHS
  ✓ column RHS

✓ Supports TEMPORAL
  ✓ TEMPORAL_ORDER
  ✓ BEFORE
  ✓ BEFORE_EQUAL
  ✓ AFTER
  ✓ AFTER_EQUAL
  ✓ multiple temporal conditions
  ✓ DURATION

✓ SQL generation is deterministic

✓ No LLM is used inside SQL generation

✓ Literal values use bound parameters

✓ Table/column identifiers are validated and quoted

✓ Invalid rule/condition combinations are rejected

✓ Mapper generates violation SQL

✓ Unit tests cover every supported operator and rule type
```

---

# 41. Final Architecture

```text
                Advanced Rule LLM
                        │
                        ▼
               Structured Contract
                        │
                        ▼
              ┌──────────────────┐
              │     Validator    │
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
              │ Condition Mapper │
              │                  │
              │ COMPARISON       │
              │ NULL_CHECK       │
              │ SET              │
              │ ARITHMETIC       │
              │ TEMPORAL_ORDER   │
              │ DURATION         │
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
              │  Rule Combiner   │
              │                  │
              │ CROSS_COLUMN     │
              │ TEMPORAL         │
              │ CONDITIONAL      │
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
              │ SQL Query Builder│
              └────────┬─────────┘
                       │
                       ▼
             SELECT ... WHERE violation
```

The SQL Mapping Engine must remain independent from the LLM model. Changing DeepSeek or any future local model should not require changes to the mapper as long as the output follows the agreed Advanced Rule contract.
