"""Publish four deterministic CSV profile snapshots to OpenMetadata.

The snapshots use cumulative prefixes of each CSV: 40%, 60%, 80%, and 100%.
The published column metrics mirror the repository's historical healthcare
profile fixture: counts, null/distinct/unique/duplicate proportions, min/max,
text lengths, and numeric mean/median/population standard deviation (ddof=0).

Nothing from this script is sent to the LLM.

Examples:
    # Validate inputs and preview payloads without changing OpenMetadata
    python scripts/publish_csv_profile_history.py

    # Publish snapshots ending today (Asia/Bangkok)
    python scripts/publish_csv_profile_history.py --push

    # Use four fixed dates ending on 2026-10-13
    python scripts/publish_csv_profile_history.py --push --end-date 2026-10-13

    # Delete only those four dates first, then republish them
    python scripts/publish_csv_profile_history.py --push --replace --end-date 2026-10-13
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import requests


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.config.settings import settings  # noqa: E402


TABLE_FQN_PREFIX = "healthcare_postgres.HealthCare.public"
FRACTIONS = (0.40, 0.60, 0.80, 1.00)
TIMEZONE = ZoneInfo("Asia/Bangkok")

# Explicit mappings are intentional. Columns such as CODE, ZIP, FIPS, and
# REASONCODE look numeric in CSV but are text identifiers in OpenMetadata.
COLUMN_MAPS: dict[str, dict[str, str]] = {
    "devices": {
        "start_at": "START",
        "stop_at": "STOP",
        "patient": "PATIENT",
        "encounter": "ENCOUNTER",
        "code": "CODE",
        "description": "DESCRIPTION",
        "udi": "UDI",
    },
    "encounters": {
        "id": "Id",
        "start_at": "START",
        "stop_at": "STOP",
        "patient": "PATIENT",
        "organization": "ORGANIZATION",
        "provider": "PROVIDER",
        "payer": "PAYER",
        "encounter_class": "ENCOUNTERCLASS",
        "code": "CODE",
        "description": "DESCRIPTION",
        "base_encounter_cost": "BASE_ENCOUNTER_COST",
        "total_claim_cost": "TOTAL_CLAIM_COST",
        "payer_coverage": "PAYER_COVERAGE",
        "reason_code": "REASONCODE",
        "reason_description": "REASONDESCRIPTION",
    },
    "medications": {
        "start_at": "START",
        "stop_at": "STOP",
        "patient": "PATIENT",
        "payer": "PAYER",
        "encounter": "ENCOUNTER",
        "code": "CODE",
        "description": "DESCRIPTION",
        "base_cost": "BASE_COST",
        "payer_coverage": "PAYER_COVERAGE",
        "dispenses": "DISPENSES",
        "total_cost": "TOTALCOST",
        "reason_code": "REASONCODE",
        "reason_description": "REASONDESCRIPTION",
    },
    "observations": {
        "observation_date": "DATE",
        "patient": "PATIENT",
        "encounter": "ENCOUNTER",
        "category": "CATEGORY",
        "code": "CODE",
        "description": "DESCRIPTION",
        "value": "VALUE",
        "units": "UNITS",
        "type": "TYPE",
    },
    "patients": {
        "id": "Id",
        "birthdate": "BIRTHDATE",
        "deathdate": "DEATHDATE",
        "ssn": "SSN",
        "drivers": "DRIVERS",
        "passport": "PASSPORT",
        "prefix": "PREFIX",
        "first_name": "FIRST",
        "middle_name": "MIDDLE",
        "last_name": "LAST",
        "suffix": "SUFFIX",
        "maiden": "MAIDEN",
        "marital": "MARITAL",
        "race": "RACE",
        "ethnicity": "ETHNICITY",
        "gender": "GENDER",
        "birthplace": "BIRTHPLACE",
        "address": "ADDRESS",
        "city": "CITY",
        "state": "STATE",
        "county": "COUNTY",
        "fips": "FIPS",
        "zip": "ZIP",
        "lat": "LAT",
        "lon": "LON",
        "healthcare_expenses": "HEALTHCARE_EXPENSES",
        "healthcare_coverage": "HEALTHCARE_COVERAGE",
        "income": "INCOME",
    },
}

NUMERIC_COLUMNS: dict[str, set[str]] = {
    "devices": set(),
    "encounters": {
        "base_encounter_cost",
        "total_claim_cost",
        "payer_coverage",
    },
    "medications": {"base_cost", "payer_coverage", "dispenses", "total_cost"},
    "observations": set(),
    "patients": {
        "lat",
        "lon",
        "healthcare_expenses",
        "healthcare_coverage",
        "income",
    },
}

TEXT_OM_TYPES = {"text", "varchar", "char", "character varying", "string"}

NUMERIC_OM_TYPES = {
    "tinyint",
    "smallint",
    "integer",
    "int",
    "bigint",
    "float",
    "double",
    "double precision",
    "real",
    "decimal",
    "numeric",
    "number",
}


@dataclass(frozen=True)
class Snapshot:
    fraction: float
    timestamp: int
    local_date: date


class OpenMetadataProfilePublisher:
    def __init__(self) -> None:
        self.base_url = settings.openmetadata_base_url.rstrip("/")
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if settings.openmetadata_jwt_token:
            self.headers["Authorization"] = (
                f"Bearer {settings.openmetadata_jwt_token}"
            )

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        response = requests.request(
            method,
            f"{self.base_url}/{path.lstrip('/')}",
            headers=self.headers,
            timeout=30,
            **kwargs,
        )
        if not response.ok:
            detail = response.text[:2000]
            raise RuntimeError(
                f"OpenMetadata {method} {path} failed: "
                f"HTTP {response.status_code}: {detail}"
            )
        return response

    def get_table(self, table_fqn: str) -> dict[str, Any]:
        encoded = urllib.parse.quote(table_fqn, safe="")
        return self._request(
            "GET", f"tables/name/{encoded}?fields=columns"
        ).json()

    def publish(self, table_id: str, payload: dict[str, Any]) -> None:
        self._request("PUT", f"tables/{table_id}/tableProfile", json=payload)

    def delete_profile(
        self, entity_type: str, entity_fqn: str, timestamp: int
    ) -> None:
        encoded = urllib.parse.quote(entity_fqn, safe="")
        self._request(
            "DELETE",
            f"tables/{encoded}/{entity_type}/{timestamp}/profile",
        )

    def get_column_profiles(
        self, column_fqn: str, start_ts: int, end_ts: int
    ) -> list[dict[str, Any]]:
        encoded = urllib.parse.quote(column_fqn, safe="")
        body = self._request(
            "GET",
            f"tables/{encoded}/columnProfile?startTs={start_ts}&endTs={end_ts}",
        ).json()
        return body.get("data", [])

    def get_table_profiles(
        self, table_fqn: str, start_ts: int, end_ts: int
    ) -> list[dict[str, Any]]:
        encoded = urllib.parse.quote(table_fqn, safe="")
        body = self._request(
            "GET",
            f"tables/{encoded}/tableProfile?startTs={start_ts}&endTs={end_ts}",
        ).json()
        return body.get("data", [])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish 40/60/80/100 percent CSV profiles to OpenMetadata."
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Actually write to OpenMetadata. Without this flag, run as preview.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help=(
            "Delete profiles at the four requested timestamps before publishing. "
            "Requires --push; profiles at all other timestamps are untouched."
        ),
    )
    parser.add_argument(
        "--end-date",
        type=date.fromisoformat,
        default=datetime.now(TIMEZONE).date(),
        help="Date of the 100%% snapshot (YYYY-MM-DD, default: today).",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=ROOT_DIR / "scripts" / "results",
        help="Directory for the generated audit JSON.",
    )
    return parser.parse_args()


def build_snapshots(end_date: date) -> list[Snapshot]:
    snapshots: list[Snapshot] = []
    for index, fraction in enumerate(FRACTIONS):
        local_date = end_date - timedelta(days=len(FRACTIONS) - index - 1)
        local_datetime = datetime.combine(local_date, time.min, tzinfo=TIMEZONE)
        snapshots.append(
            Snapshot(
                fraction=fraction,
                timestamp=int(local_datetime.timestamp() * 1000),
                local_date=local_date,
            )
        )
    return snapshots


def normalized_om_type(column: dict[str, Any]) -> str:
    return str(column.get("dataTypeDisplay") or column.get("dataType") or "").lower()


def validate_columns(
    table_name: str,
    frame: pd.DataFrame,
    table: dict[str, Any],
) -> None:
    om_columns = {column["name"]: column for column in table.get("columns", [])}
    expected_om_names = set(COLUMN_MAPS[table_name])
    actual_om_names = set(om_columns)
    if expected_om_names != actual_om_names:
        raise ValueError(
            f"{table_name}: column mapping differs from OpenMetadata schema; "
            f"missing={sorted(actual_om_names - expected_om_names)}, "
            f"extra={sorted(expected_om_names - actual_om_names)}"
        )

    for om_name, csv_name in COLUMN_MAPS[table_name].items():
        if csv_name not in frame.columns:
            raise ValueError(f"{table_name}: CSV column {csv_name!r} does not exist")
        if om_name in NUMERIC_COLUMNS[table_name] and not is_numeric_om_column(
            om_columns[om_name]
        ):
            om_type = normalized_om_type(om_columns[om_name])
            raise ValueError(
                f"{table_name}.{om_name}: expected numeric OpenMetadata type, "
                f"found {om_type!r}"
            )


def is_numeric_om_column(column: dict[str, Any]) -> bool:
    om_type = normalized_om_type(column)
    return any(
        om_type == numeric_type or om_type.startswith(f"{numeric_type}(")
        for numeric_type in NUMERIC_OM_TYPES
    )


def is_text_om_column(column: dict[str, Any]) -> bool:
    om_type = normalized_om_type(column)
    return any(
        om_type == text_type or om_type.startswith(f"{text_type}(")
        for text_type in TEXT_OM_TYPES
    )


def finite_float(value: Any) -> float | None:
    result = float(value)
    return result if math.isfinite(result) else None


def scalar(value: Any) -> Any:
    """Convert pandas/numpy scalars into JSON-safe Python scalars."""
    if pd.isna(value):
        return None
    return value.item() if hasattr(value, "item") else value


def build_column_profile(
    om_name: str,
    csv_name: str,
    raw_series: pd.Series,
    om_column: dict[str, Any],
    timestamp: int,
    row_count: int,
) -> dict[str, Any]:
    non_null = raw_series.dropna()
    values_count = int(non_null.size)
    null_count = int(row_count - values_count)
    value_counts = non_null.value_counts(dropna=True)
    distinct_count = int(non_null.nunique(dropna=True))
    unique_count = int((value_counts == 1).sum())

    profile: dict[str, Any] = {
        "name": om_name,
        "timestamp": timestamp,
        "valuesCount": float(values_count),
        "nullCount": float(null_count),
        "nullProportion": null_count / row_count if row_count else 0.0,
        "uniqueCount": float(unique_count),
        "uniqueProportion": unique_count / values_count if values_count else 0.0,
        "distinctCount": float(distinct_count),
        "distinctProportion": distinct_count / values_count if values_count else 0.0,
        # This matches the historical healthcare profile fixture's semantics.
        "duplicateCount": float(values_count - unique_count),
    }

    if values_count:
        if is_numeric_om_column(om_column):
            numeric = pd.to_numeric(non_null, errors="coerce").dropna()
            if not numeric.empty:
                profile.update(
                    {
                        "min": finite_float(numeric.min()),
                        "max": finite_float(numeric.max()),
                        "mean": finite_float(numeric.mean()),
                        "median": finite_float(numeric.median()),
                        "stddev": finite_float(numeric.std(ddof=0)),
                    }
                )
        else:
            # CSV is loaded as strings so identifiers keep leading zeroes.
            profile["min"] = scalar(non_null.min())
            profile["max"] = scalar(non_null.max())

        if is_text_om_column(om_column):
            lengths = non_null.astype(str).str.len()
            profile["minLength"] = float(lengths.min())
            profile["maxLength"] = float(lengths.max())

    return {key: value for key, value in profile.items() if value is not None}


def build_payload(
    table_name: str,
    frame: pd.DataFrame,
    table: dict[str, Any],
    snapshot: Snapshot,
) -> dict[str, Any]:
    # ceil ensures each prefix contains at least the requested percentage.
    row_count = min(len(frame), max(1, math.ceil(len(frame) * snapshot.fraction)))
    sample = frame.iloc[:row_count]
    column_profiles: list[dict[str, Any]] = []
    om_columns = {column["name"]: column for column in table.get("columns", [])}

    for om_name, csv_name in COLUMN_MAPS[table_name].items():
        column_profiles.append(
            build_column_profile(
                om_name=om_name,
                csv_name=csv_name,
                raw_series=sample[csv_name],
                om_column=om_columns[om_name],
                timestamp=snapshot.timestamp,
                row_count=row_count,
            )
        )

    return {
        "tableProfile": {
            "timestamp": snapshot.timestamp,
            "rowCount": float(row_count),
            "columnCount": float(len(table.get("columns", []))),
            "profileSample": snapshot.fraction * 100,
        },
        "columnProfile": column_profiles,
    }


def verify_published_profiles(
    publisher: OpenMetadataProfilePublisher,
    table_name: str,
    snapshots: list[Snapshot],
) -> dict[str, Any]:
    expected = {snapshot.timestamp for snapshot in snapshots}
    table_fqn = f"{TABLE_FQN_PREFIX}.{table_name}"
    table_profiles = publisher.get_table_profiles(
        table_fqn,
        min(expected),
        max(expected),
    )
    table_timestamps = sorted(
        int(profile["timestamp"])
        for profile in table_profiles
        if int(profile.get("timestamp", -1)) in expected
    )
    if set(table_timestamps) != expected:
        missing = sorted(expected - set(table_timestamps))
        raise RuntimeError(
            f"Verification failed for {table_fqn}; missing table timestamps: {missing}"
        )
    if len(table_timestamps) != len(expected):
        raise RuntimeError(
            f"Verification failed for {table_fqn}; duplicate table profiles found "
            f"for the requested timestamps"
        )

    found: dict[str, list[int]] = {}
    for column_name in COLUMN_MAPS[table_name]:
        column_fqn = f"{TABLE_FQN_PREFIX}.{table_name}.{column_name}"
        profiles = publisher.get_column_profiles(
            column_fqn,
            min(expected),
            max(expected),
        )
        required_metrics = {
            "valuesCount",
            "nullCount",
            "nullProportion",
            "uniqueCount",
            "uniqueProportion",
            "distinctCount",
            "distinctProportion",
            "duplicateCount",
        }
        if column_name in NUMERIC_COLUMNS[table_name]:
            required_metrics.update({"mean", "median", "stddev", "min", "max"})
        matching = sorted(
            int(profile["timestamp"])
            for profile in profiles
            if int(profile.get("timestamp", -1)) in expected
            and required_metrics.issubset(profile)
        )
        if set(matching) != expected:
            missing = sorted(expected - set(matching))
            raise RuntimeError(
                f"Verification failed for {column_fqn}; missing timestamps: {missing}"
            )
        if len(matching) != len(expected):
            raise RuntimeError(
                f"Verification failed for {column_fqn}; duplicate column profiles "
                f"found for the requested timestamps"
            )
        found[column_name] = matching
    return {
        "tableTimestamps": table_timestamps,
        "columnTimestamps": found,
    }


def main() -> int:
    args = parse_args()
    if args.replace and not args.push:
        raise SystemExit("--replace requires --push")
    publisher = OpenMetadataProfilePublisher()
    snapshots = build_snapshots(args.end_date)
    audit: dict[str, Any] = {
        "mode": "push" if args.push else "preview",
        "generatedAt": datetime.now(TIMEZONE).isoformat(),
        "endDate": args.end_date.isoformat(),
        "fractions": list(FRACTIONS),
        "tables": {},
    }

    for table_name in COLUMN_MAPS:
        csv_path = ROOT_DIR / "data" / f"{table_name}.csv"
        frame = pd.read_csv(csv_path, dtype=str, low_memory=False)
        table_fqn = f"{TABLE_FQN_PREFIX}.{table_name}"
        table = publisher.get_table(table_fqn)
        validate_columns(table_name, frame, table)

        table_audit: dict[str, Any] = {
            "tableFqn": table_fqn,
            "csvRows": len(frame),
            "profiledColumns": list(COLUMN_MAPS[table_name]),
            "numericColumns": sorted(NUMERIC_COLUMNS[table_name]),
            "snapshots": [],
        }
        print(
            f"\n{table_fqn}: {len(frame)} CSV rows, "
            f"{len(COLUMN_MAPS[table_name])} profile columns "
            f"({len(NUMERIC_COLUMNS[table_name])} numeric)"
        )

        if args.replace:
            print("  deleting only the four requested timestamps before republish")
            delete_targets = [
                ("column", f"{table_fqn}.{column_name}", snapshot.timestamp)
                for snapshot in snapshots
                for column_name in COLUMN_MAPS[table_name]
            ] + [
                ("table", table_fqn, snapshot.timestamp)
                for snapshot in snapshots
            ]
            with ThreadPoolExecutor(max_workers=8) as executor:
                list(executor.map(lambda target: publisher.delete_profile(*target), delete_targets))
        existing_table_timestamps = {
            int(profile["timestamp"])
            for profile in publisher.get_table_profiles(
                table_fqn,
                snapshots[0].timestamp,
                snapshots[-1].timestamp,
            )
        }

        for snapshot in snapshots:
            payload = build_payload(table_name, frame, table, snapshot)
            row_count = int(payload["tableProfile"]["rowCount"])
            print(
                f"  {snapshot.local_date}  {snapshot.fraction:.0%}: "
                f"{row_count} rows, {len(payload['columnProfile'])} column profiles"
            )
            already_exists = snapshot.timestamp in existing_table_timestamps
            if args.push and already_exists:
                print("    skipped: timestamp already exists")
            elif args.push:
                publisher.publish(table["id"], payload)
            table_audit["snapshots"].append(
                {
                    "date": snapshot.local_date.isoformat(),
                    "fraction": snapshot.fraction,
                    "action": (
                        "previewed"
                        if not args.push
                        else ("skipped" if already_exists else "published")
                    ),
                    "payload": payload,
                }
            )

        if args.push:
            table_audit["verification"] = verify_published_profiles(
                publisher, table_name, snapshots
            )
            print("  verified against OpenMetadata")
        audit["tables"][table_name] = table_audit

    args.results_dir.mkdir(parents=True, exist_ok=True)
    suffix = "pushed" if args.push else "preview"
    output_path = args.results_dir / (
        f"csv_profile_history_{args.end_date.isoformat()}_{suffix}.json"
    )
    output_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nAudit written to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
