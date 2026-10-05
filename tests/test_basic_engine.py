import pytest
from backend.contracts.table_context import TableContext, ColumnContext, ColumnProfile
from backend.engine.basic_engine import BasicRuleEngine

@pytest.fixture
def sample_table_context() -> TableContext:
    return TableContext(
        datasource_id="postgres-test",
        database_name="ecommerce_db",
        schema_name="public",
        table_name="orders",
        row_count=1000,
        columns=[
            ColumnContext(
                name="order_id",
                data_type="VARCHAR(64)",
                nullable=False,
                is_primary_key=True,
                profile=ColumnProfile(
                    row_count=1000,
                    null_count=0,
                    null_ratio=0.0,
                    distinct_count=1000,
                    distinct_ratio=1.0,
                    min_length=10,
                    max_length=10
                )
            ),
            ColumnContext(
                name="total_amount",
                data_type="NUMERIC(12,2)",
                nullable=False,
                profile=ColumnProfile(
                    row_count=1000,
                    null_count=0,
                    null_ratio=0.0,
                    distinct_count=850,
                    distinct_ratio=0.85,
                    min_value=100.0,
                    max_value=50000.0
                )
            ),
            ColumnContext(
                name="order_status",
                data_type="VARCHAR(20)",
                nullable=False,
                profile=ColumnProfile(
                    row_count=1000,
                    null_count=0,
                    null_ratio=0.0,
                    distinct_count=4,
                    distinct_ratio=0.004,
                    min_length=6,
                    max_length=9,
                    top_values=[
                        {"value": "PENDING", "count": 200},
                        {"value": "SHIPPED", "count": 500},
                        {"value": "COMPLETED", "count": 250},
                        {"value": "CANCELLED", "count": 50}
                    ]
                )
            ),
            ColumnContext(
                name="notes",
                data_type="TEXT",
                nullable=True,
                profile=ColumnProfile(
                    row_count=1000,
                    null_count=450,
                    null_ratio=0.45,
                    distinct_count=300,
                    distinct_ratio=0.30
                )
            )
        ]
    )

def test_generate_not_null_rule_positive(sample_table_context):
    engine = BasicRuleEngine()
    candidates = engine.generate_candidates(sample_table_context)
    
    not_null_rules = [c for c in candidates if c.rule_type == "columnValuesToBeNotNull"]
    target_cols = [c.target_columns[0] for c in not_null_rules]
    
    # order_id, total_amount, order_status có null_count = 0 -> Phải sinh NOT NULL
    assert "order_id" in target_cols
    assert "total_amount" in target_cols
    assert "order_status" in target_cols
    
    # notes có null_count = 450 -> KHÔNG được sinh NOT NULL
    assert "notes" not in target_cols

def test_generate_unique_rule(sample_table_context):
    engine = BasicRuleEngine()
    candidates = engine.generate_candidates(sample_table_context)
    
    unique_rules = [c for c in candidates if c.rule_type == "columnValuesToBeUnique"]
    target_cols = [c.target_columns[0] for c in unique_rules]
    
    # order_id là PK và có distinct_ratio = 1.0 -> Phải sinh UNIQUE
    assert "order_id" in target_cols
    # order_status chỉ có 4 giá trị -> KHÔNG được sinh UNIQUE
    assert "order_status" not in target_cols

def test_generate_value_between_rule(sample_table_context):
    engine = BasicRuleEngine()
    candidates = engine.generate_candidates(sample_table_context)
    
    between_rules = [c for c in candidates if c.rule_type == "columnValuesToBeBetween"]
    amount_rule = next((c for c in between_rules if "total_amount" in c.target_columns), None)
    
    assert amount_rule is not None
    assert amount_rule.parameters["minValue"] == 100.0
    assert amount_rule.parameters["maxValue"] == 50000.0

def test_generate_values_in_set_rule(sample_table_context):
    engine = BasicRuleEngine()
    candidates = engine.generate_candidates(sample_table_context)
    
    in_set_rules = [c for c in candidates if c.rule_type == "columnValuesToBeInSet"]
    status_rule = next((c for c in in_set_rules if "order_status" in c.target_columns), None)
    
    assert status_rule is not None
    assert set(status_rule.parameters["allowedValues"]) == {"PENDING", "SHIPPED", "COMPLETED", "CANCELLED"}

def test_generate_length_between_rule(sample_table_context):
    engine = BasicRuleEngine()
    candidates = engine.generate_candidates(sample_table_context)
    
    length_rules = [c for c in candidates if c.rule_type == "columnValuesLengthToBeBetween"]
    order_id_rule = next((c for c in length_rules if "order_id" in c.target_columns), None)
    
    assert order_id_rule is not None
    assert order_id_rule.parameters["minLength"] == 10
    assert order_id_rule.parameters["maxLength"] == 10

def test_row_count_rule_disabled(sample_table_context):
    engine = BasicRuleEngine()
    candidates = engine.generate_candidates(sample_table_context)
    
    # Xác nhận rule tableRowCountToBeBetween đã được tắt theo yêu cầu
    row_count_rules = [c for c in candidates if c.rule_type == "tableRowCountToBeBetween"]
    assert len(row_count_rules) == 0

def test_empty_table_context():
    engine = BasicRuleEngine()
    empty_context = TableContext(
        datasource_id="empty-db",
        database_name="test",
        schema_name="public",
        table_name="empty",
        row_count=0,
        columns=[]
    )
    candidates = engine.generate_candidates(empty_context)
    assert len(candidates) == 0
