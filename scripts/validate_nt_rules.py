"""Run and report all applied NT rules for one OpenMetadata table.

This is a manual validation client for the existing DQ Backend API. It does
not execute rule handlers locally; therefore it exercises the same metadata
loading, PostgreSQL configuration, handler registry, and TestCaseResult
publishing path used by the Airflow integration.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List

import requests


DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"
DEFAULT_TABLE_FQN = "healthcare_postgres.HealthCare.public.encounters"
ACTIVE_STATUSES = {"PENDING", "RUNNING"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the 15 applied NT rules for the encounters table."
    )
    parser.add_argument(
        "--backend-url",
        default=os.getenv("DQ_BACKEND_URL", DEFAULT_BACKEND_URL),
        help="DQ Backend base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--table-fqn",
        default=os.getenv("NT_TEST_TABLE_FQN", DEFAULT_TABLE_FQN),
        help="OpenMetadata table FQN (default: %(default)s)",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("DQ_BACKEND_TOKEN", ""),
        help="Optional bearer token for the DQ Backend",
    )
    parser.add_argument(
        "--expected-count",
        type=int,
        default=15,
        help="Expected applied NT Test Case count; use 0 to disable the check",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=600,
        help="Maximum seconds to wait for the run",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=1,
        help="Seconds between status requests",
    )
    parser.add_argument(
        "--output",
        help="Optional path to save the complete JSON report",
    )
    return parser.parse_args()


def api_root(backend_url: str) -> str:
    base = backend_url.rstrip("/")
    return base if base.endswith("/api/v1") else f"{base}/api/v1"


def request_json(
    method: str,
    url: str,
    headers: Dict[str, str],
    timeout: float,
    **kwargs: Any,
) -> Dict[str, Any]:
    try:
        response = requests.request(
            method,
            url,
            headers=headers,
            timeout=timeout,
            **kwargs,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Cannot call {url}: {exc}") from exc
    if not response.ok:
        detail = response.text
        try:
            payload = response.json()
            detail = payload.get("detail") or payload.get("message") or detail
        except ValueError:
            pass
        raise RuntimeError(f"{method} {url} returned HTTP {response.status_code}: {detail}")
    return response.json()


def run_validation(args: argparse.Namespace) -> Dict[str, Any]:
    root = api_root(args.backend_url)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if args.token:
        headers["Authorization"] = f"Bearer {args.token}"

    health = request_json("GET", f"{root}/health", headers, timeout=20)
    if health.get("status") != "healthy":
        raise RuntimeError(
            "DQ Backend is not healthy: "
            f"OpenMetadata={health.get('openmetadata_connected')}, "
            f"PostgreSQL={health.get('postgres_connected')}"
        )

    summary = request_json(
        "POST",
        f"{root}/nt-runs",
        headers,
        timeout=30,
        json={
            "table_fqn": args.table_fqn,
            "pipeline_id": "manual-nt-validation",
        },
    )
    run_id = summary.get("run_id")
    if not run_id:
        raise RuntimeError("DQ Backend did not return run_id")

    print(f"NT run: {run_id}")
    print(f"Table : {args.table_fqn}")
    deadline = time.monotonic() + args.timeout
    last_progress = None
    while summary.get("status") in ACTIVE_STATUSES:
        progress = (
            summary.get("processed_items", 0),
            summary.get("total_items", 0),
            summary.get("status"),
        )
        if progress != last_progress:
            print(
                f"[{progress[2]}] processed {progress[0]}/{progress[1]} rules"
            )
            last_progress = progress
        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"NT run {run_id} did not finish within {args.timeout}s"
            )
        time.sleep(args.poll_interval)
        summary = request_json(
            "GET",
            f"{root}/nt-runs/{run_id}",
            headers,
            timeout=30,
        )

    result_page = request_json(
        "GET",
        f"{root}/nt-runs/{run_id}/results",
        headers,
        timeout=30,
        params={"page": 1, "page_size": 200},
    )
    items: List[Dict[str, Any]] = result_page.get("items") or []
    report = {"summary": summary, "results": items}

    print("\nResults")
    print("-" * 100)
    for item in sorted(items, key=lambda value: value.get("definition_name", "")):
        result = item.get("result") or {}
        outcome = result.get("outcome") or "-"
        message = str(result.get("message") or item.get("error") or "")
        if len(message) > 90:
            message = message[:87] + "..."
        print(
            f"{item.get('definition_name', '-'):<30} "
            f"{item.get('status', '-'):<10} {outcome:<8} {message}"
        )
    print("-" * 100)
    print(
        "Run status: {status}; total={total}; completed={completed}; "
        "errors={errors}; outcomes={outcomes}".format(
            status=summary.get("status"),
            total=summary.get("total_items", 0),
            completed=summary.get("completed_items", 0),
            errors=summary.get("error_items", 0),
            outcomes=summary.get("outcome_counts") or {},
        )
    )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as output_file:
            json.dump(report, output_file, ensure_ascii=False, indent=2)
        print(f"Full report saved to: {args.output}")

    total = int(summary.get("total_items", 0))
    if args.expected_count and total != args.expected_count:
        raise RuntimeError(
            f"Expected {args.expected_count} applied NT Test Cases, got {total}. "
            "Check that all native NT Test Cases are applied to the table."
        )
    if summary.get("status") != "SUCCESS":
        raise RuntimeError(
            f"NT run ended with technical status {summary.get('status')}"
        )
    return report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    try:
        run_validation(args)
    except (RuntimeError, ValueError) as exc:
        print(f"\nVALIDATION FAILED: {exc}", file=sys.stderr)
        return 1
    print("\nVALIDATION PASSED: all expected NT rules completed and results were published.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
