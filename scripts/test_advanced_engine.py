"""Test script for Advanced Rule Engine with result saving.

Usage:
    # Generate rules (individual generators)
    python scripts/test_advanced_engine.py --table patients --cross-column
    python scripts/test_advanced_engine.py --table patients --temporal
    python scripts/test_advanced_engine.py --table patients --conditional

    # Full pipeline: Router → Generator (LLM)
    python scripts/test_advanced_engine.py --table patients

    # Full pipeline: Router → Generator → SQL Mapper (COMPLETE)
    python scripts/test_advanced_engine.py --table patients --full-pipeline-sql

    # Test SQL mapper với saved results
    python scripts/test_advanced_engine.py --sql-map --table patients
    python scripts/test_advanced_engine.py --sql-latest --table patients

Output:
    scripts/results/<table>_<component>_<timestamp>/
        - raw_response.json     # Generated rules (JSON)
        - full_result.json      # Full pipeline result với SQL
        - summary.json         # Summary
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Configure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.integrations.openmetadata.client import OpenMetadataClient
from backend.engine.advanced_rule_service import AdvancedRuleService
from backend.engine.advanced_llm.client import LLMClient, LLMConfig
from backend.engine.advanced_llm.router import AdvancedRuleRouter
from backend.engine.advanced_llm.temporal_generator import TemporalGenerator
from backend.engine.advanced_llm.cross_column_generator import CrossColumnGenerator
from backend.engine.advanced_llm.conditional_dependency_generator import ConditionalDependencyGenerator
from backend.engine.sql_mapper import map_advanced_rule_to_sql
from dotenv import load_dotenv


# Output directory
RESULTS_DIR = Path(__file__).parent / "results"


def setup_llm():
    """Setup LLM client."""
    load_dotenv(Path(__file__).resolve().parents[1] / "backend" / ".env")

    import os
    return LLMClient(LLMConfig(
        api_key=os.getenv("LLM_API", ""),
        base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
        model=os.getenv("LLM_MODEL", "deepseek-flash"),
    ))


def rules_to_dicts(rules) -> list[dict]:
    """Convert GeneratedRule objects to dicts for JSON serialization."""
    result = []
    for rule in rules:
        result.append({
            "rule_type": rule.rule_type,
            "target_table": rule.target_table,
            "columns": rule.columns,
            "conditions": rule.conditions,
            "condition": rule.condition,
            "reason": rule.reason,
            "confidence": rule.confidence,
            "evidence": rule.evidence,
        })
    return result


def save_result(output_dir: Path, component: str, context: dict, raw_response: str, candidates: list, prompt_file: str = None):
    """Save test result to folder."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save router context (input)
    with open(output_dir / "router_context.json", "w", encoding="utf-8") as f:
        json.dump(context, f, indent=2, ensure_ascii=False, default=str)

    # Save raw response - parse if it's JSON string
    try:
        # Try to parse as JSON first
        raw_data = json.loads(raw_response)
    except (json.JSONDecodeError, TypeError):
        # Fallback: save as-is
        raw_data = raw_response
    with open(output_dir / "raw_response.json", "w", encoding="utf-8") as f:
        json.dump({"raw": raw_data}, f, indent=2, ensure_ascii=False, default=str)

    # Save parsed candidates
    candidates_data = []
    for c in candidates:
        candidates_data.append({
            "rule_type": c.rule_type,
            "relevant_columns": c.relevant_columns,
            "confidence": c.confidence,
            "reason": c.reason,
        })
    with open(output_dir / "candidates.json", "w", encoding="utf-8") as f:
        json.dump(candidates_data, f, indent=2, ensure_ascii=False)

    # Save summary
    summary = {
        "table": context.get("table", {}).get("name", "unknown"),
        "component": component,
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "prompt_file": prompt_file,
        "candidates_count": len(candidates),
        "columns_count": len(context.get("columns", [])),
        "primary_keys": context.get("primary_keys", []),
    }
    with open(output_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    return output_dir


def create_output_dir(table_name: str, component: str) -> Path:
    """Create output directory with timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_name = f"{table_name}_{component}_{timestamp}"
    return RESULTS_DIR / dir_name


async def test_router(table_name: str, save: bool = True) -> tuple:
    """Test Router only."""
    print(f"\n{'=' * 60}")
    print(f"TEST: Router for table '{table_name}'")
    print(f"{'=' * 60}")

    llm = setup_llm()
    router = AdvancedRuleRouter(llm)
    om = OpenMetadataClient()
    ctx = om.get_table_context(table_name)

    # Build context
    context = router._build_router_context(ctx)

    print(f"\nTable: {ctx.table_name}")
    print(f"Columns: {len(ctx.columns)}")
    print(f"Primary Keys: {ctx.primary_keys}")
    print(f"Prompt file: backend/engine/prompts/{router._prompt_file}")

    # Run router
    result = await router.route(ctx)

    print(f"\n[RESULT] Router found {len(result.candidates)} candidates:")
    for i, c in enumerate(result.candidates, 1):
        print(f"\n  [{i}] {c.rule_type}")
        print(f"      Columns: {c.relevant_columns}")
        print(f"      Confidence: {c.confidence}")

    # Save result
    if save:
        output_dir = create_output_dir(table_name, "router")
        # Get raw response from last call
        raw_response = getattr(router._llm, '_last_response', str(result))
        save_result(output_dir, "router", context, str(raw_response), result.candidates, router._prompt_file)
        print(f"\n[Saved] {output_dir}")

    return result, context


async def test_temporal_generator(table_name: str, save: bool = True):
    """Test Temporal Generator."""
    print(f"\n{'=' * 60}")
    print(f"TEST: Temporal Generator for table '{table_name}'")
    print(f"{'=' * 60}")

    llm = setup_llm()
    router = AdvancedRuleRouter(llm)
    om = OpenMetadataClient()
    ctx = om.get_table_context(table_name)

    # Get TEMPORAL candidates
    router_result = await router.route(ctx)
    temporal_candidates = [c for c in router_result.candidates if c.rule_type == "TEMPORAL"]

    if not temporal_candidates:
        print("No TEMPORAL candidates found.")
        return []

    print(f"\nFound {len(temporal_candidates)} TEMPORAL candidate(s)")

    generator = TemporalGenerator(llm)
    print(f"Prompt file: backend/engine/prompts/{generator._prompt_file}")
    all_rules = []
    context = router._build_router_context(ctx)

    for candidate in temporal_candidates:
        print(f"\n  Processing: {candidate.relevant_columns}")
        result = await generator.generate(ctx, candidate)
        all_rules.extend(result.rules)

        print(f"  Generated {len(result.rules)} rules:")
        for rule in result.rules:
            print(f"    - Conditions: {rule.conditions}")
            print(f"      Confidence: {rule.confidence}")

    # Save result
    if save:
        output_dir = create_output_dir(table_name, "temporal")
        rules_json = json.dumps(rules_to_dicts(all_rules), indent=2, default=str)
        save_result(output_dir, "temporal", context, rules_json, temporal_candidates, generator._prompt_file)
        print(f"\n[Saved] {output_dir}")

    return all_rules


async def test_cross_column_generator(table_name: str, save: bool = True):
    """Test Cross-Column Generator."""
    print(f"\n{'=' * 60}")
    print(f"TEST: Cross-Column Generator for table '{table_name}'")
    print(f"{'=' * 60}")

    llm = setup_llm()
    router = AdvancedRuleRouter(llm)
    om = OpenMetadataClient()
    ctx = om.get_table_context(table_name)

    # Get CROSS_COLUMN candidates
    router_result = await router.route(ctx)
    cross_candidates = [c for c in router_result.candidates if c.rule_type == "CROSS_COLUMN"]

    if not cross_candidates:
        print("No CROSS_COLUMN candidates found.")
        return []

    print(f"\nFound {len(cross_candidates)} CROSS_COLUMN candidate(s)")

    generator = CrossColumnGenerator(llm)
    print(f"Prompt file: backend/engine/prompts/{generator._prompt_file}")
    all_rules = []
    context = router._build_router_context(ctx)

    for candidate in cross_candidates:
        print(f"\n  Processing: {candidate.relevant_columns}")
        result = await generator.generate(ctx, candidate)
        all_rules.extend(result.rules)

        print(f"  Generated {len(result.rules)} rules:")
        for rule in result.rules:
            print(f"    - Conditions: {rule.conditions}")
            print(f"      Confidence: {rule.confidence}")

    # Save result
    if save:
        output_dir = create_output_dir(table_name, "cross_column")
        rules_json = json.dumps(rules_to_dicts(all_rules), indent=2, default=str)
        save_result(output_dir, "cross_column", context, rules_json, cross_candidates, generator._prompt_file)
        print(f"\n[Saved] {output_dir}")

    return all_rules


async def test_conditional_generator(table_name: str, save: bool = True):
    """Test Conditional Dependency Generator."""
    print(f"\n{'=' * 60}")
    print(f"TEST: Conditional Dependency Generator for table '{table_name}'")
    print(f"{'=' * 60}")

    llm = setup_llm()
    router = AdvancedRuleRouter(llm)
    om = OpenMetadataClient()
    ctx = om.get_table_context(table_name)

    # Get CONDITIONAL_DEPENDENCY candidates
    router_result = await router.route(ctx)
    cond_candidates = [c for c in router_result.candidates if c.rule_type == "CONDITIONAL_DEPENDENCY"]

    if not cond_candidates:
        print("No CONDITIONAL_DEPENDENCY candidates found.")
        return []

    print(f"\nFound {len(cond_candidates)} CONDITIONAL_DEPENDENCY candidate(s)")

    generator = ConditionalDependencyGenerator(llm)
    print(f"Prompt file: backend/engine/prompts/{generator._prompt_file}")
    all_rules = []
    context = router._build_router_context(ctx)

    for candidate in cond_candidates:
        print(f"\n  Processing: {candidate.relevant_columns}")
        result = await generator.generate(ctx, candidate)
        all_rules.extend(result.rules)

        print(f"  Generated {len(result.rules)} rules:")
        for rule in result.rules:
            print(f"    - Conditions: {rule.conditions}")
            print(f"      Confidence: {rule.confidence}")

    # Save result
    if save:
        output_dir = create_output_dir(table_name, "conditional")
        rules_json = json.dumps(rules_to_dicts(all_rules), indent=2, default=str)
        save_result(output_dir, "conditional", context, rules_json, cond_candidates, generator._prompt_file)
        print(f"\n[Saved] {output_dir}")

    return all_rules


async def test_full_pipeline_with_sql(table_name: str, min_confidence: float = 0.6, save: bool = True):
    """Test full pipeline: Router → Generator → SQL Mapper.

    Pipeline hoàn chỉnh:
    1. Router phát hiện candidates
    2. Generators tạo rules
    3. SQL Mapper chuyển rules thành SQL
    """
    print(f"\n{'=' * 60}")
    print(f"TEST: Full Pipeline with SQL for table '{table_name}'")
    print(f"{'=' * 60}")

    llm = setup_llm()
    service = AdvancedRuleService(llm_client=llm, min_confidence=min_confidence)
    om = OpenMetadataClient()
    ctx = om.get_table_context(table_name)

    print(f"\nTable: {ctx.table_name}")
    print(f"Columns: {len(ctx.columns)}")
    print(f"Min Confidence: {min_confidence}")
    print(f"\nRunning pipeline: Router → Generator → SQL Mapper...")

    # Run full pipeline with SQL
    result = await service.recommend_with_sql(ctx)

    print(f"\n{'=' * 60}")
    print(f"RESULT")
    print(f"{'=' * 60}")

    print(f"\nCandidates: {result.total_candidates}")
    print(f"Rules Generated: {result.total_rules_generated}")
    print(f"SQL Mapped: {result.total_sql_mapped}")
    print(f"SQL Failed: {result.total_sql_failed}")

    if result.errors:
        print(f"\nErrors:")
        for err in result.errors:
            print(f"  - {err}")

    print(f"\n{'=' * 60}")
    print(f"RULES WITH SQL")
    print(f"{'=' * 60}")

    for i, rule in enumerate(result.rules, 1):
        print(f"\n[{i}] {rule.rule_type}")
        print(f"    Table: {rule.table}")
        print(f"    Columns: {rule.columns}")
        print(f"    Confidence: {rule.confidence}")

        if rule.sql_error:
            print(f"    SQL Error: {rule.sql_error}")
        else:
            print(f"    Violation Predicate: {rule.violation_predicate}")
            print(f"    SQL: {rule.sql}")
            if rule.params:
                print(f"    Params: {rule.params}")

    # Save result
    if save:
        output_dir = create_output_dir(table_name, "full_pipeline_sql")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save full result as JSON
        with open(output_dir / "full_result.json", "w", encoding="utf-8") as f:
            json.dump(result.model_dump(), f, indent=2, ensure_ascii=False, default=str)

        # Save summary
        summary = {
            "table": table_name,
            "component": "full_pipeline_sql",
            "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "min_confidence": min_confidence,
            "total_candidates": result.total_candidates,
            "total_rules": result.total_rules_generated,
            "total_sql_mapped": result.total_sql_mapped,
            "total_sql_failed": result.total_sql_failed,
            "rules": [
                {
                    "rule_type": r.rule_type,
                    "table": r.table,
                    "columns": r.columns,
                    "confidence": r.confidence,
                    "sql": r.sql,
                    "violation_predicate": r.violation_predicate,
                    "params": r.params,
                    "error": r.sql_error,
                }
                for r in result.rules
            ]
        }
        with open(output_dir / "summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        print(f"\n[Saved] {output_dir}")

    return result


async def test_full_pipeline(table_name: str, min_confidence: float = 0.6, save: bool = True):
    """Test full AdvancedRuleService pipeline."""
    print(f"\n{'=' * 60}")
    print(f"TEST: Full Pipeline for table '{table_name}'")
    print(f"{'=' * 60}")

    llm = setup_llm()
    service = AdvancedRuleService(llm_client=llm, min_confidence=min_confidence)
    om = OpenMetadataClient()
    ctx = om.get_table_context(table_name)

    print(f"\nTable: {ctx.table_name}")
    print(f"Columns: {len(ctx.columns)}")
    print(f"Min Confidence: {min_confidence}")

    # Run full pipeline
    router_result, rules = await service.recommend(ctx)

    print(f"\n[RESULT]")
    print(f"  Router candidates: {len(router_result.candidates)}")
    print(f"  Selected (>= {min_confidence}): {sum(1 for c in router_result.candidates if c.confidence >= min_confidence)}")
    print(f"  Generated rules: {len(rules)}")

    # Summary by type
    by_type = {}
    for rule in rules:
        t = rule.rule_type
        by_type[t] = by_type.get(t, 0) + 1

    print(f"\n  Rules by type:")
    for t, count in sorted(by_type.items()):
        print(f"    {t}: {count}")

    # Save result
    if save:
        output_dir = create_output_dir(table_name, "full_pipeline")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Build context
        router = AdvancedRuleRouter(llm)
        context = router._build_router_context(ctx)

        # Save router context
        with open(output_dir / "router_context.json", "w", encoding="utf-8") as f:
            json.dump(context, f, indent=2, ensure_ascii=False, default=str)

        # Save router result
        router_data = []
        for c in router_result.candidates:
            router_data.append({
                "rule_type": c.rule_type,
                "relevant_columns": c.relevant_columns,
                "confidence": c.confidence,
                "reason": c.reason,
            })
        with open(output_dir / "router_result.json", "w", encoding="utf-8") as f:
            json.dump(router_data, f, indent=2, ensure_ascii=False)

        # Save generated rules
        rules_data = []
        for rule in rules:
            rules_data.append({
                "rule_type": rule.rule_type,
                "target_table": rule.target_table,
                "columns": rule.columns,
                "condition": rule.condition,
                "reason": rule.reason,
                "confidence": rule.confidence,
                "evidence": rule.evidence,
            })
        with open(output_dir / "generated_rules.json", "w", encoding="utf-8") as f:
            json.dump(rules_data, f, indent=2, ensure_ascii=False)

        # Save summary
        summary = {
            "table": table_name,
            "component": "full_pipeline",
            "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "min_confidence": min_confidence,
            "prompt_files": {
                "router": "advanced_router.md",
                "generators": ["temporal.md", "cross_column.md", "conditional_dependency.md"]
            },
            "router_candidates": len(router_result.candidates),
            "generated_rules": len(rules),
            "rules_by_type": by_type,
        }
        with open(output_dir / "summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        print(f"\n[Saved] {output_dir}")

    return router_result, rules


def test_sql_engine_from_result(result_dir: Path):
    """Test SQL Mapper với kết quả đã generate từ LLM.

    Đọc raw_response.json từ result directory và map thành SQL.

    Args:
        result_dir: Path đến result directory chứa raw_response.json
    """
    print(f"\n{'=' * 60}")
    print(f"SQL MAPPER TEST")
    print(f"Result: {result_dir.name}")
    print(f"{'=' * 60}")

    raw_response_file = result_dir / "raw_response.json"
    if not raw_response_file.exists():
        print(f"  [ERROR] raw_response.json not found in {result_dir}")
        return []

    # Load raw response
    with open(raw_response_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        rules = data.get("raw", [])

    if not rules:
        print(f"  [WARN] No rules found in raw_response.json")
        return []

    print(f"\n  Found {len(rules)} rule(s) to map")
    results = []

    for i, rule_dict in enumerate(rules, 1):
        print(f"\n  [{i}] Rule Type: {rule_dict.get('rule_type', 'N/A')}")
        print(f"      Table: {rule_dict.get('target_table', 'N/A')}")
        print(f"      Columns: {rule_dict.get('columns', [])}")
        print(f"      Confidence: {rule_dict.get('confidence', 'N/A')}")

        # Build rule dict for SQL Mapper
        rule = {
            "rule_type": rule_dict.get("rule_type"),
            "table": rule_dict.get("target_table"),
            "columns": rule_dict.get("columns", []),
            "conditions": rule_dict.get("conditions", []),
            "confidence": rule_dict.get("confidence", 0.8),
            "reason": rule_dict.get("reason", ""),
        }

        # Skip if no conditions
        if not rule["conditions"]:
            print(f"      [SKIP] No conditions found")
            continue

        try:
            # Map to SQL
            sql_result = map_advanced_rule_to_sql(rule)

            print(f"\n      --- SQL Mapper Result ---")
            print(f"      Violation Predicate:")
            print(f"        {sql_result['violation_predicate']}")
            print(f"      Full SQL:")
            print(f"        {sql_result['sql']}")
            if sql_result['params']:
                print(f"      Parameters:")
                for k, v in sql_result['params'].items():
                    print(f"        {k}: {v}")

            results.append(sql_result)

        except Exception as e:
            print(f"      [ERROR] SQL Mapping failed: {e}")

    return results


def find_latest_result_dir(table_name: str, component: str) -> Path | None:
    """Tìm result directory mới nhất cho table và component.

    Args:
        table_name: Tên bảng (VD: patients)
        component: Component (VD: cross_column, temporal, conditional)

    Returns:
        Path đến directory mới nhất, hoặc None nếu không tìm thấy
    """
    pattern = f"{table_name}_{component}_*"
    dirs = sorted(
        RESULTS_DIR.glob(pattern),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    return dirs[0] if dirs else None


async def main():
    parser = argparse.ArgumentParser(description="Test Advanced Rule Engine")
    parser.add_argument("--table", default="patients", help="Table name")
    parser.add_argument("--min-confidence", type=float, default=0.6, help="Min confidence threshold")
    parser.add_argument("--router-only", action="store_true", help="Test router only")
    parser.add_argument("--temporal", action="store_true", help="Test temporal generator")
    parser.add_argument("--cross-column", action="store_true", help="Test cross-column generator")
    parser.add_argument("--conditional", action="store_true", help="Test conditional generator")
    parser.add_argument("--all", action="store_true", help="Test all components")
    parser.add_argument("--no-save", action="store_true", help="Do not save results")
    parser.add_argument("--full-pipeline-sql", action="store_true",
                        help="Test full pipeline: Router → Generator → SQL Mapper")

    # SQL Mapper options
    parser.add_argument("--sql-map", action="store_true", help="Test SQL mapper with generated rules")
    parser.add_argument("--sql-result-dir", type=str, help="Specific result directory to map")
    parser.add_argument("--sql-latest", action="store_true", help="Use latest result directory for SQL mapping")

    args = parser.parse_args()
    save = not args.no_save

    print(f"\n{'=' * 60}")
    print(f"ADVANCED RULE ENGINE TEST")
    print(f"Table: {args.table}")
    print(f"{'=' * 60}")

    # SQL Mapper mode
    if args.sql_map or args.sql_result_dir or args.sql_latest:
        # Determine result directory
        if args.sql_result_dir:
            result_dir = Path(args.sql_result_dir)
        elif args.sql_latest:
            # Try to find latest based on table
            for component in ["cross_column", "temporal", "conditional", "full_pipeline"]:
                result_dir = find_latest_result_dir(args.table, component)
                if result_dir:
                    break
            if not result_dir:
                print(f"[ERROR] No result directory found for table '{args.table}'")
                return
        else:
            # Default: find latest for each component
            print("\n[SQL MAPPER] Testing all available results...\n")
            for component in ["cross_column", "temporal", "conditional"]:
                result_dir = find_latest_result_dir(args.table, component)
                if result_dir:
                    test_sql_engine_from_result(result_dir)
                else:
                    print(f"\n[SQL MAPPER] No {component} result found for {args.table}")
            return

        test_sql_engine_from_result(result_dir)
        return

    if args.router_only:
        await test_router(args.table, save)
    elif args.temporal:
        await test_temporal_generator(args.table, save)
    elif args.cross_column:
        await test_cross_column_generator(args.table, save)
    elif args.conditional:
        await test_conditional_generator(args.table, save)
    elif args.full_pipeline_sql:
        await test_full_pipeline_with_sql(args.table, args.min_confidence, save)
    elif args.all:
        await test_router(args.table, save)
        await test_temporal_generator(args.table, save)
        await test_cross_column_generator(args.table, save)
        await test_conditional_generator(args.table, save)
        await test_full_pipeline(args.table, args.min_confidence, save)
    else:
        await test_full_pipeline(args.table, args.min_confidence, save)

    if save:
        print(f"\n{'=' * 60}")
        print(f"Results saved to: scripts/results/")
        print(f"{'=' * 60}")

    print(f"\n{'=' * 60}")
    print("TEST COMPLETE")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())
