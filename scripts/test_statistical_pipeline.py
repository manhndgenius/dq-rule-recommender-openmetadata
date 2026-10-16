"""
Test script to run the statistical rules pipeline end-to-end.
Run: python scripts/test_statistical_pipeline.py --table patients --llm

This script:
1. Loads table context from OpenMetadata (or mock if not available)
2. Runs prefilter
3. Builds LLM context (grouped by column)
4. (Optionally) calls LLM
5. Saves results to scripts/results/ folder:
   - <table>_llm_input.json  (LLM input)
   - <table>_llm_output.json (LLM output, if LLM called)
   - summary.json
"""

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path

# Add backend to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.integrations.openmetadata.client import openmetadata_client
from backend.engine.statistical_rules.prefilter import prefilter_table
from backend.engine.statistical_rules.llm_reviewer import (
    RULE_TYPE_TO_ALIAS,
    build_llm_context,
    get_eligible_pairs,
    SYSTEM_PROMPT,
)
from backend.engine.statistical_rules.contracts import LLMSuggestionResult


SUPPORTED_RULE_ALIASES = ("mean", "median", "stddev")


def get_table_context(table_name: str):
    """Load table context from OpenMetadata. Returns None if not found."""
    return openmetadata_client.get_table_context(table_name)


async def run_pipeline(
    table_name: str,
    use_llm: bool = False,
    results_dir: Path = None,
) -> dict:
    """
    Run the full pipeline.

    Args:
        table_name: FQN of table to process
        use_llm: Whether to call LLM (requires API key)
        results_dir: Directory to save LLM input/output files

    Returns:
        Full pipeline output as dict
    """
    print(f"\n{'='*60}")
    print(f"Running pipeline for: {table_name}")
    print(f"Use LLM: {use_llm}")
    print('='*60)

    # Step 0: Load table context from OpenMetadata
    print("\n[0/4] Loading table context from OpenMetadata...")
    table = openmetadata_client.get_table_context(table_name)

    if not table:
        return {
            "metadata": {"table_fqn": table_name, "error": "Table not found in OpenMetadata"},
            "summary": {},
            "recommendations": [],
            "skipped": [],
            "uncertain": [],
            "filtered": [],
        }

    table_fqn = f"{table.database_name}.{table.schema_name}.{table.table_name}"
    print(f"  - Table: {table_fqn}")
    print(f"  - Columns: {len(table.columns)}")

    # Step 1: Pre-filter
    print("\n[1/4] Running pre-filter...")
    prefilter_results = prefilter_table(table)

    # Build summary
    total_eligible_pairs_count = sum(len(r.eligible_rules) for r in prefilter_results)
    columns_with_pairs = sum(1 for r in prefilter_results if r.eligible_rules)

    print(f"  - Columns scanned: {len(prefilter_results)}")
    print(f"  - Columns with eligible pairs: {columns_with_pairs}")
    print(f"  - Total eligible pairs: {total_eligible_pairs_count}")

    # Step 2: Build LLM context
    print("\n[2/4] Building LLM context...")
    llm_context = build_llm_context(table, prefilter_results)

    if llm_context:
        print(f"  - Table: {llm_context.table['fqn']}")
        print(f"  - Columns: {len(llm_context.columns)}")
        all_eligible_pairs = get_eligible_pairs(prefilter_results)
        print(f"  - Candidates to review: {len(all_eligible_pairs)}")
        aliases_in_context = {
            alias
            for column in llm_context.columns
            for alias in column.rules
        }
        unsupported_aliases = sorted(aliases_in_context - set(SUPPORTED_RULE_ALIASES))
        if unsupported_aliases:
            raise RuntimeError(
                f"Unsupported rule aliases in LLM context: {unsupported_aliases}"
            )
        print(f"  - Supported rules: {', '.join(SUPPORTED_RULE_ALIASES)}")
    else:
        print("  - No eligible pairs for LLM review")
        all_eligible_pairs = []

    # Save LLM input to file (pretty-print for debug)
    if llm_context and results_dir:
        results_dir.mkdir(parents=True, exist_ok=True)
        llm_input_path = results_dir / f"{table.table_name}_llm_input.json"

        # Save full LLM input (system prompt + user context)
        llm_input = {
            "metadata": {
                "table_fqn": table_fqn,
                "timestamp": datetime.now().isoformat(),
                "system_prompt_source": "prompts/system_prompt.md",
            },
            "system_prompt": SYSTEM_PROMPT,
            "user_prompt": json.loads(llm_context.model_dump_json()),  # compact JSON
        }

        llm_input_path.write_text(json.dumps(llm_input, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n  [SAVED] LLM input -> {llm_input_path}")

    # Step 3: Call LLM (if enabled)
    llm_output = None
    llm_call_succeeded = False
    if use_llm and llm_context:
        print("\n[3/4] Calling LLM...")
        from backend.engine.advanced_llm.client import LLMClient

        llm_client = LLMClient()
        try:
            # Send compact JSON to LLM
            llm_response = await llm_client.generate_structured(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=llm_context.model_dump_json(),  # compact JSON
                response_model=LLMSuggestionResult,
            )
            llm_output = {
                "metadata": {
                    "table_fqn": table_fqn,
                    "timestamp": datetime.now().isoformat(),
                    "num_decisions": len(llm_response.decisions),
                    "expected_decisions": len(all_eligible_pairs),
                },
                "decisions": [d.model_dump() for d in llm_response.decisions],
            }
            llm_call_succeeded = True
            print(f"  - LLM response received: {len(llm_response.decisions)} decisions")
            returned_ids = {decision.candidate_id for decision in llm_response.decisions}
            expected_ids = {
                f"{column}::{RULE_TYPE_TO_ALIAS.get(rule_type, rule_type)}"
                for column, rule_type in all_eligible_pairs
            }
            missing_ids = sorted(expected_ids - returned_ids)
            unexpected_ids = sorted(returned_ids - expected_ids)
            if missing_ids:
                print(f"  - Missing decisions (will become UNCERTAIN): {missing_ids}")
            if unexpected_ids:
                print(f"  - Unexpected decisions (will be ignored): {unexpected_ids}")
            llm_output["metadata"]["missing_decisions"] = missing_ids
            llm_output["metadata"]["unexpected_decisions"] = unexpected_ids

            # Save LLM output to file
            if results_dir:
                llm_output_path = results_dir / f"{table.table_name}_llm_output.json"
                llm_output_path.write_text(json.dumps(llm_output, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"  [SAVED] LLM output -> {llm_output_path}")

        except Exception as e:
            print(f"  - LLM call failed: {e}")
            llm_output = {
                "metadata": {
                    "table_fqn": table_fqn,
                    "timestamp": datetime.now().isoformat(),
                    "error": str(e),
                },
                "decisions": [],
            }
    else:
        print("\n[3/4] Skipping LLM call (use_llm=False or no candidates)")

    # Step 4: Build final output
    print("\n[4/4] Building summary...")
    from backend.engine.statistical_rules.llm_reviewer import validate_and_convert_decisions

    # Build recommendations
    recommendations = []
    skipped = []
    uncertain = []

    if llm_output and llm_output.get("decisions"):
        from backend.engine.statistical_rules.contracts import LLMSuggestion, LLMSuggestionDecision

        # Convert to LLMSuggestionDecision objects
        decisions = [LLMSuggestionDecision(**d) for d in llm_output["decisions"]]
        candidates = validate_and_convert_decisions(decisions, all_eligible_pairs)

        for c in candidates:
            item = c.model_dump()
            if c.decision == LLMSuggestion.RECOMMEND:
                recommendations.append(item)
            elif c.decision == LLMSuggestion.SKIP:
                skipped.append(item)
            else:
                uncertain.append(item)
    else:
        # Just show eligible pairs pending review
        for col, rule in all_eligible_pairs:
            item = {
                "column": col,
                "rule_type": rule,
                "decision": "PENDING_LLM_REVIEW",
                "reason": "Pre-filter passed, awaiting LLM review",
                "evidence": {"prefilter_passed": True},
            }
            uncertain.append(item)

    decision_by_rule = {
        alias: {"RECOMMEND": 0, "SKIP": 0, "UNCERTAIN": 0}
        for alias in SUPPORTED_RULE_ALIASES
    }
    for decision_name, items in (
        ("RECOMMEND", recommendations),
        ("SKIP", skipped),
        ("UNCERTAIN", uncertain),
    ):
        for item in items:
            alias = RULE_TYPE_TO_ALIAS.get(item["rule_type"], item["rule_type"])
            if alias in decision_by_rule:
                decision_by_rule[alias][decision_name] += 1

    # Build filtered diagnostics (chỉ 1 reason_code)
    filtered = []
    for result in prefilter_results:
        if not result.eligible_rules and result.filtered_rules:
            filtered.append({
                "column": result.column_name,
                "status": "FILTERED",
                "reason_code": result.filtered_rules[0].reason_code,
                "message": f"Column filtered: {result.filtered_rules[0].reason_code}",
            })

    # Build output
    output = {
        "metadata": {
            "table_fqn": table_fqn,
            "table_name": table.table_name,
            "profile_timestamp": max(
                (
                    column.profile.profile_timestamp
                    for column in table.columns
                    if column.profile.profile_timestamp is not None
                ),
                default=None,
            ),
            "llm_requested": use_llm,
            "llm_succeeded": llm_call_succeeded,
            "supported_rules": list(SUPPORTED_RULE_ALIASES),
        },
        "summary": {
            "columns_scanned": len(table.columns),
            "eligible_columns": columns_with_pairs,
            "eligible_pairs": len(all_eligible_pairs),
            "filtered_pairs": sum(len(r.filtered_rules) for r in prefilter_results),
            "llm_calls": 1 if (use_llm and llm_output) else 0,
            "recommendations": len(recommendations),
            "skipped": len(skipped),
            "uncertain": len(uncertain),
            "decision_by_rule": decision_by_rule,
        },
        "prefilter_results": [
            {
                "column": r.column_name,
                "eligible_rules": r.eligible_rules,
                "filtered_rules": [{"rule": f.rule_type, "reason": f.reason_code} for f in r.filtered_rules],
                "reason_codes": r.reason_codes,
            }
            for r in prefilter_results
        ],
        "recommendations": recommendations,
        "skipped": skipped,
        "uncertain": uncertain,
        "filtered": filtered,
    }

    # Print summary
    print(f"\n{'='*60}")
    print("PIPELINE SUMMARY")
    print('='*60)
    print(f"Table: {table_fqn}")
    print(f"Columns scanned: {output['summary']['columns_scanned']}")
    print(f"Eligible columns: {output['summary']['eligible_columns']}")
    print(f"Eligible pairs: {output['summary']['eligible_pairs']}")
    print(f"Recommendations: {output['summary']['recommendations']}")
    print(f"Skipped: {output['summary']['skipped']}")
    print(f"Uncertain: {output['summary']['uncertain']}")
    print("Decision breakdown by rule:")
    for alias, counts in decision_by_rule.items():
        print(
            f"  - {alias}: recommend={counts['RECOMMEND']}, "
            f"skip={counts['SKIP']}, uncertain={counts['UNCERTAIN']}"
        )
    print(f"Filtered columns: {len(filtered)}")

    return output


def main():
    parser = argparse.ArgumentParser(description="Test statistical rules pipeline")
    parser.add_argument(
        "--table",
        type=str,
        default="patients",
        help="Table FQN to process (default: patients)",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Enable LLM call (requires API key)",
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default=None,
        help="Directory to save results (default: scripts/results/)",
    )
    args = parser.parse_args()

    # Create results directory
    if args.results_dir:
        results_dir = Path(args.results_dir)
    else:
        results_dir = Path(__file__).parent / "results"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = results_dir / f"run_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"Results will be saved to: {run_dir}")

    async def run():
        output = await run_pipeline(
            table_name=args.table,
            use_llm=args.llm,
            results_dir=run_dir,
        )

        # Save summary
        summary_path = run_dir / "summary.json"
        summary_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nSummary saved to: {summary_path}")

        # List all saved files
        print(f"\nSaved files in {run_dir}:")
        for f in sorted(run_dir.glob("*")):
            print(f"  - {f.name}")

    asyncio.run(run())


if __name__ == "__main__":
    main()
