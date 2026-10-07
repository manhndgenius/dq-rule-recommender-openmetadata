"""SQL Mapper cho Advanced Data Quality Rules.

Module này chuyển đổi structured rule output từ LLM thành executable SQL.

Target flow:
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
"""

from backend.engine.sql_mapper.mapper import map_advanced_rule_to_sql, AdvancedRuleMapper, MapperError
from backend.engine.sql_mapper.compile_context import CompileContext

__all__ = [
    "map_advanced_rule_to_sql",
    "AdvancedRuleMapper",
    "CompileContext",
    "MapperError",
]
