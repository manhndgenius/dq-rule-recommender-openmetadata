# Advanced Rule Output Contract for SQL Mapping Engine

## 1. Purpose

This document defines the **LLM output contract** used by the Advanced Data Quality Rule system before SQL generation.

The contract is designed so that:

- the LLM outputs only structured rule semantics;
- the SQL Mapping Engine does not need to infer rule meaning;
- the mapper can deterministically convert the LLM output into SQL;
- rules involving 2 columns or more than 2 columns use the same overall schema;
- all rule logic is represented inside a unified `conditions` list.

Supported rule types in V1:

```text
CROSS_COLUMN
CONDITIONAL_DEPENDENCY
TEMPORAL
```

The SQL Mapping Engine should generate SQL that finds **rows violating the rule**.

---

# 2. Common Rule Schema

Every advanced rule must follow this top-level structure:

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
  "reason": "Explanation of why this rule is plausible."
}
```

## Field definitions

| Field | Required | Description |
|---|---:|---|
| `table` | Yes | Table where the rule will be executed |
| `columns` | Yes | All columns involved in the rule |
| `rule_type` | Yes | Main rule category |
| `conditions` | Yes | List containing all semantic conditions required to build SQL |
| `confidence` | Recommended | LLM confidence score |
| `reason` | Recommended | Explanation for the suggested rule |

Important:

- `columns` is mainly for metadata, display, logging, and evaluation.
- The SQL Mapper **must not infer semantic relationships from the order of `columns`**.
- Actual semantic meaning must be fully represented inside `conditions`.
- Rules involving more columns are represented by adding more objects to `conditions`.

---

# 3. Supported Condition Types

V1 supports the following condition types:

```text
COMPARISON
NULL_CHECK
SET
ARITHMETIC
TEMPORAL_ORDER
DURATION
```

These condition objects are reused across rule types where appropriate.

---

# 4. COMPARISON Condition

Used for comparing:

- column to column;
- column to literal.

Supported operators:

```text
EQ
NEQ
GT
GTE
LT
LTE
```

## Schema

```json
{
  "type": "COMPARISON",

  "role": "IF | THEN | null",

  "left": "column_name",

  "operator": "EQ | NEQ | GT | GTE | LT | LTE",

  "right": {
    "type": "column | literal",
    "value": "..."
  }
}
```

`role` is only required for `CONDITIONAL_DEPENDENCY`.

For `CROSS_COLUMN` and `TEMPORAL`, it may be omitted or `null`.

---

## Column-to-column example

Semantic rule:

```text
healthcare_coverage <= healthcare_expenses
```

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

---

## Column-to-literal example

Semantic rule:

```text
age >= 18
```

```json
{
  "type": "COMPARISON",
  "left": "age",
  "operator": "GTE",
  "right": {
    "type": "literal",
    "value": 18
  }
}
```

---

# 5. NULL_CHECK Condition

Used for:

```text
IS NULL
IS NOT NULL
```

## Schema

```json
{
  "type": "NULL_CHECK",

  "role": "IF | THEN | null",

  "column": "column_name",

  "operator": "IS_NULL | IS_NOT_NULL"
}
```

Example:

```json
{
  "type": "NULL_CHECK",
  "role": "THEN",
  "column": "deathdate",
  "operator": "IS_NOT_NULL"
}
```

Semantic:

```text
deathdate IS NOT NULL
```

---

# 6. SET Condition

Used for:

```text
IN
NOT IN
```

## Schema

```json
{
  "type": "SET",

  "role": "IF | THEN | null",

  "left": "column_name",

  "operator": "IN | NOT_IN",

  "values": [
    "value_1",
    "value_2"
  ]
}
```

Example:

```json
{
  "type": "SET",
  "role": "THEN",
  "left": "currency",
  "operator": "IN",
  "values": [
    "USD",
    "USN"
  ]
}
```

Semantic:

```text
currency IN ('USD', 'USN')
```

---

# 7. ARITHMETIC Condition

Used for arithmetic relationships between multiple columns.

Supported arithmetic operators:

```text
ADD
SUBTRACT
MULTIPLY
DIVIDE
```

Supported comparison operators:

```text
EQ
NEQ
GT
GTE
LT
LTE
```

## Schema

```json
{
  "type": "ARITHMETIC",

  "target": "target_column",

  "comparison_operator": "EQ | NEQ | GT | GTE | LT | LTE",

  "expression": {
    "operator": "ADD | SUBTRACT | MULTIPLY | DIVIDE",

    "operands": [
      "column_a",
      "column_b"
    ]
  }
}
```

Semantic form:

```text
target comparison_operator arithmetic_expression
```

---

## Example: multiplication

```text
total = quantity * price
```

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

---

## Example: more than two columns

```text
total = subtotal + tax + shipping
```

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

Notes:

- `ADD` and `MULTIPLY` naturally support multiple operands.
- For `SUBTRACT` and `DIVIDE`, operand order is significant.
- The mapper must preserve the order in `operands`.

Example:

```json
{
  "operator": "SUBTRACT",
  "operands": [
    "gross_amount",
    "discount",
    "refund"
  ]
}
```

means:

```text
gross_amount - discount - refund
```

---

# 8. TEMPORAL_ORDER Condition

Used for ordering relationships between date/time columns.

Supported operators:

```text
BEFORE
BEFORE_EQUAL
AFTER
AFTER_EQUAL
```

## Schema

```json
{
  "type": "TEMPORAL_ORDER",

  "left": "column_name",

  "operator": "BEFORE | BEFORE_EQUAL | AFTER | AFTER_EQUAL",

  "right": "column_name"
}
```

Semantic mapping:

| Operator | Meaning |
|---|---|
| `BEFORE` | `left < right` |
| `BEFORE_EQUAL` | `left <= right` |
| `AFTER` | `left > right` |
| `AFTER_EQUAL` | `left >= right` |

Example:

```json
{
  "type": "TEMPORAL_ORDER",
  "left": "birthdate",
  "operator": "BEFORE_EQUAL",
  "right": "deathdate"
}
```

Semantic:

```text
birthdate <= deathdate
```

---

# 9. DURATION Condition

Used for constraints on the duration between two temporal columns.

Supported comparison operators:

```text
GT
GTE
LT
LTE
```

Supported units in V1:

```text
MINUTE
HOUR
DAY
```

## Schema

```json
{
  "type": "DURATION",

  "start_column": "start_time",

  "end_column": "end_time",

  "operator": "GT | GTE | LT | LTE",

  "value": 30,

  "unit": "MINUTE | HOUR | DAY"
}
```

Semantic form:

```text
(end_column - start_column) operator duration
```

Example:

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

Semantic:

```text
end_time - start_time <= 30 DAY
```

---

# 10. CROSS_COLUMN Rule Contract

`CROSS_COLUMN` uses the common schema and stores all relationships inside `conditions`.

Valid condition types:

```text
COMPARISON
ARITHMETIC
```

Multiple conditions are allowed.

By default, multiple valid conditions are combined using:

```text
AND
```

The SQL Mapper should generate the violation of the combined valid condition.

---

## Example: two-column comparison

```json
{
  "table": "patients",

  "columns": [
    "healthcare_coverage",
    "healthcare_expenses"
  ],

  "rule_type": "CROSS_COLUMN",

  "conditions": [
    {
      "type": "COMPARISON",
      "left": "healthcare_coverage",
      "operator": "LTE",
      "right": {
        "type": "column",
        "value": "healthcare_expenses"
      }
    }
  ],

  "confidence": 0.95,
  "reason": "Coverage should not exceed total healthcare expenses."
}
```

Valid condition:

```text
healthcare_coverage <= healthcare_expenses
```

Violation condition:

```text
healthcare_coverage > healthcare_expenses
```

---

## Example: three-column chain

Semantic:

```text
min_value <= actual_value <= max_value
```

```json
{
  "table": "measurements",

  "columns": [
    "min_value",
    "actual_value",
    "max_value"
  ],

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

Valid condition:

```text
min_value <= actual_value
AND
actual_value <= max_value
```

Violation:

```text
min_value > actual_value
OR
actual_value > max_value
```

---

# 11. CONDITIONAL_DEPENDENCY Rule Contract

All conditional rules use the same top-level structure.

Every condition must contain:

```text
role = IF
```

or:

```text
role = THEN
```

Supported condition types:

```text
COMPARISON
NULL_CHECK
SET
```

The mapper should group conditions by role.

Conceptually:

```text
IF_GROUP = all role=IF conditions
THEN_GROUP = all role=THEN conditions
```

By default:

```text
IF_GROUP   = condition1 AND condition2 AND ...
THEN_GROUP = condition1 AND condition2 AND ...
```

The valid rule is:

```text
IF_GROUP → THEN_GROUP
```

The violation is:

```text
IF_GROUP AND NOT(THEN_GROUP)
```

If multiple THEN conditions are joined by `AND`, negation follows De Morgan's law:

```text
NOT(B AND C)
=
NOT(B) OR NOT(C)
```

---

## Example: IF → NULL

Semantic:

```text
IF total_orders = 0
THEN last_order_date IS NULL
```

```json
{
  "table": "customers",

  "columns": [
    "total_orders",
    "last_order_date"
  ],

  "rule_type": "CONDITIONAL_DEPENDENCY",

  "conditions": [
    {
      "role": "IF",
      "type": "COMPARISON",
      "left": "total_orders",
      "operator": "EQ",
      "right": {
        "type": "literal",
        "value": 0
      }
    },
    {
      "role": "THEN",
      "type": "NULL_CHECK",
      "column": "last_order_date",
      "operator": "IS_NULL"
    }
  ]
}
```

Violation:

```text
total_orders = 0
AND
last_order_date IS NOT NULL
```

---

## Example: multiple IF conditions

Semantic:

```text
IF age >= 18
AND country = 'US'
THEN ssn IS NOT NULL
```

```json
{
  "table": "customers",

  "columns": [
    "age",
    "country",
    "ssn"
  ],

  "rule_type": "CONDITIONAL_DEPENDENCY",

  "conditions": [
    {
      "role": "IF",
      "type": "COMPARISON",
      "left": "age",
      "operator": "GTE",
      "right": {
        "type": "literal",
        "value": 18
      }
    },
    {
      "role": "IF",
      "type": "COMPARISON",
      "left": "country",
      "operator": "EQ",
      "right": {
        "type": "literal",
        "value": "US"
      }
    },
    {
      "role": "THEN",
      "type": "NULL_CHECK",
      "column": "ssn",
      "operator": "IS_NOT_NULL"
    }
  ]
}
```

Violation:

```text
age >= 18
AND country = 'US'
AND ssn IS NULL
```

---

## Example: multiple THEN conditions

Semantic:

```text
IF status = 'COMPLETED'
THEN completed_at IS NOT NULL
AND amount > 0
```

```json
{
  "table": "orders",

  "columns": [
    "status",
    "completed_at",
    "amount"
  ],

  "rule_type": "CONDITIONAL_DEPENDENCY",

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
      "type": "NULL_CHECK",
      "column": "completed_at",
      "operator": "IS_NOT_NULL"
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

Violation:

```text
status = 'COMPLETED'
AND
(
    completed_at IS NULL
    OR amount <= 0
)
```

---

## Example: IF → IN

Semantic:

```text
IF country = 'US'
THEN currency IN ('USD', 'USN')
```

```json
{
  "table": "transactions",

  "columns": [
    "country",
    "currency"
  ],

  "rule_type": "CONDITIONAL_DEPENDENCY",

  "conditions": [
    {
      "role": "IF",
      "type": "COMPARISON",
      "left": "country",
      "operator": "EQ",
      "right": {
        "type": "literal",
        "value": "US"
      }
    },
    {
      "role": "THEN",
      "type": "SET",
      "left": "currency",
      "operator": "IN",
      "values": [
        "USD",
        "USN"
      ]
    }
  ]
}
```

---

## Example: conditional column-to-column comparison

Semantic:

```text
IF status = 'COMPLETED'
THEN paid_amount = total_amount
```

```json
{
  "table": "orders",

  "columns": [
    "status",
    "paid_amount",
    "total_amount"
  ],

  "rule_type": "CONDITIONAL_DEPENDENCY",

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

---

# 12. TEMPORAL Rule Contract

`TEMPORAL` uses:

```text
TEMPORAL_ORDER
DURATION
```

Multiple temporal conditions are allowed.

By default, all valid temporal conditions are combined using:

```text
AND
```

The mapper generates the negation of the valid combined condition to find violating rows.

---

## Example: two-column ordering

Semantic:

```text
birthdate <= deathdate
```

```json
{
  "table": "patients",

  "columns": [
    "birthdate",
    "deathdate"
  ],

  "rule_type": "TEMPORAL",

  "conditions": [
    {
      "type": "TEMPORAL_ORDER",
      "left": "birthdate",
      "operator": "BEFORE_EQUAL",
      "right": "deathdate"
    }
  ],

  "confidence": 0.98,
  "reason": "Death date cannot precede birth date."
}
```

---

## Example: temporal sequence with more than two columns

Semantic:

```text
created_at <= processed_at <= completed_at
```

```json
{
  "table": "orders",

  "columns": [
    "created_at",
    "processed_at",
    "completed_at"
  ],

  "rule_type": "TEMPORAL",

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

Valid condition:

```text
created_at <= processed_at
AND
processed_at <= completed_at
```

Violation:

```text
created_at > processed_at
OR
processed_at > completed_at
```

This structure also allows mixed temporal operators.

Example:

```text
created_at < approved_at <= completed_at
```

can be represented using two separate `TEMPORAL_ORDER` conditions.

---

## Example: duration

Semantic:

```text
end_time - start_time <= 30 DAY
```

```json
{
  "table": "encounters",

  "columns": [
    "start_time",
    "end_time"
  ],

  "rule_type": "TEMPORAL",

  "conditions": [
    {
      "type": "DURATION",
      "start_column": "start_time",
      "end_column": "end_time",
      "operator": "LTE",
      "value": 30,
      "unit": "DAY"
    }
  ]
}
```

---

# 13. Rule Combination Semantics

The SQL Mapping Engine must interpret the condition list according to `rule_type`.

## CROSS_COLUMN

Valid state:

```text
condition_1
AND condition_2
AND ...
```

Violation:

```text
NOT(valid_state)
```

Therefore:

```text
NOT(A AND B)
=
NOT(A) OR NOT(B)
```

---

## TEMPORAL

Valid state:

```text
condition_1
AND condition_2
AND ...
```

Violation:

```text
NOT(valid_state)
```

---

## CONDITIONAL_DEPENDENCY

Group conditions by role:

```text
IF_GROUP =
    all role=IF conditions joined with AND

THEN_GROUP =
    all role=THEN conditions joined with AND
```

Valid semantic rule:

```text
IF_GROUP → THEN_GROUP
```

Violation:

```text
IF_GROUP
AND
NOT(THEN_GROUP)
```

---

# 14. Operator Negation Mapping

The SQL Mapper should centrally define the inverse of each operator.

## Comparison

| Valid operator | Violation operator |
|---|---|
| `EQ` | `NEQ` |
| `NEQ` | `EQ` |
| `GT` | `LTE` |
| `GTE` | `LT` |
| `LT` | `GTE` |
| `LTE` | `GT` |

## Null

| Valid operator | Violation operator |
|---|---|
| `IS_NULL` | `IS_NOT_NULL` |
| `IS_NOT_NULL` | `IS_NULL` |

## Set

| Valid operator | Violation operator |
|---|---|
| `IN` | `NOT_IN` |
| `NOT_IN` | `IN` |

## Temporal

| Valid operator | Violation operator |
|---|---|
| `BEFORE` | `AFTER_EQUAL` |
| `BEFORE_EQUAL` | `AFTER` |
| `AFTER` | `BEFORE_EQUAL` |
| `AFTER_EQUAL` | `BEFORE` |

---

# 15. Final V1 Contract Summary

```text
ADVANCED_RULE
│
├── table
├── columns[]
├── rule_type
├── conditions[]
├── confidence
└── reason
```

Supported `rule_type`:

```text
CROSS_COLUMN
CONDITIONAL_DEPENDENCY
TEMPORAL
```

Supported `condition.type`:

```text
COMPARISON
NULL_CHECK
SET
ARITHMETIC
TEMPORAL_ORDER
DURATION
```

Supported comparison operators:

```text
EQ
NEQ
GT
GTE
LT
LTE
```

Supported null operators:

```text
IS_NULL
IS_NOT_NULL
```

Supported set operators:

```text
IN
NOT_IN
```

Supported arithmetic operators:

```text
ADD
SUBTRACT
MULTIPLY
DIVIDE
```

Supported temporal operators:

```text
BEFORE
BEFORE_EQUAL
AFTER
AFTER_EQUAL
```

Supported duration units:

```text
MINUTE
HOUR
DAY
```

Conditional roles:

```text
IF
THEN
```

---

# 16. Key Design Rules

1. All rule semantics must be inside `conditions`.
2. `columns` must not be used to infer relationship direction.
3. The LLM must explicitly identify operand roles.
4. The LLM must describe the **valid expected state**, not the violation.
5. The SQL Mapper is responsible for negating the valid rule to find violations.
6. Multi-column rules are represented using multiple conditions or multiple arithmetic operands.
7. Do not create different top-level schemas for every rule subtype.
8. SQL generation must be deterministic and must not require additional LLM reasoning.
9. Unsupported relationships should not be forced into this contract.
10. The contract should remain independent from PostgreSQL/Trino SQL syntax; SQL dialect handling belongs to the mapping engine.

