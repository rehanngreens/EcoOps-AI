"""Build train/test CSVs from Google Cluster 2019 shards."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from sklearn.model_selection import train_test_split

from config import (
    DEFAULT_MAX_ROWS,
    EVENTS_FILENAME,
    METADATA_FILENAME,
    PROCESSED_DIR,
    RANDOM_STATE,
    RAW_TRACE_DIR,
    TEST_FILENAME,
    TEST_SIZE,
    TRAIN_FILENAME,
    USAGE_FILENAME,
)
from feature_mapping import FEATURE_COLUMNS, TARGET_COLUMNS, build_training_table
from load_trace import load_events_frame, load_usage_frame


def preprocess(
    events_path: Path,
    usage_path: Path,
    output_dir: Path,
    max_rows: int | None = DEFAULT_MAX_ROWS,
    test_size: float = TEST_SIZE,
    random_state: int = RANDOM_STATE,
) -> dict:
    events = load_events_frame(events_path, max_rows=max_rows)
    usage = load_usage_frame(usage_path, max_rows=max_rows)
    table, allocation_source = build_training_table(events, usage)

    if table.empty:
        raise ValueError("Preprocessing produced no training rows")

    train_df, test_df = train_test_split(
        table,
        test_size=test_size,
        random_state=random_state,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    train_path = output_dir / TRAIN_FILENAME
    test_path = output_dir / TEST_FILENAME
    metadata_path = output_dir / METADATA_FILENAME

    train_df.to_csv(train_path, index=False)
    test_df.to_csv(test_path, index=False)

    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "events_path": str(events_path),
        "usage_path": str(usage_path),
        "max_rows": max_rows,
        "events_loaded": int(len(events)),
        "usage_loaded": int(len(usage)),
        "allocation_source": allocation_source,
        "training_rows": int(len(table)),
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
        "feature_columns": FEATURE_COLUMNS,
        "target_columns": TARGET_COLUMNS,
        "limitations": [
            "Google CPU/memory values are machine fractions, not Kubernetes cores/GiB.",
            "If instance_events and instance_usage shards do not share instance IDs, allocation falls back to maximum_usage.",
            "expected_users, traffic_score, max_latency_ms, and availability_target are documented defaults.",
            "replicas is fixed at 1 because the trace has no Kubernetes replica count.",
            "application_type_code is a proxy from scheduling_class, not a labeled application type.",
        ],
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preprocess Google Cluster traces for EcoOps AI")
    parser.add_argument("--events-path", type=Path, default=RAW_TRACE_DIR / EVENTS_FILENAME)
    parser.add_argument("--usage-path", type=Path, default=RAW_TRACE_DIR / USAGE_FILENAME)
    parser.add_argument("--output-dir", type=Path, default=PROCESSED_DIR)
    parser.add_argument("--max-rows", type=int, default=DEFAULT_MAX_ROWS)
    parser.add_argument(
        "--all-rows",
        action="store_true",
        help="Read entire shards instead of --max-rows (slow, high memory)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    max_rows = None if args.all_rows else args.max_rows
    metadata = preprocess(
        events_path=args.events_path,
        usage_path=args.usage_path,
        output_dir=args.output_dir,
        max_rows=max_rows,
    )
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
