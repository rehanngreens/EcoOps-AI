"""Load Google Cluster 2019 newline-delimited JSON shards."""

from __future__ import annotations

import gzip
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, TextIO

import pandas as pd


def load_json_records(path: Path, max_rows: int | None = None) -> list[dict[str, Any]]:
    """Load records from a .json.gz or .jsonl file."""
    records: list[dict[str, Any]] = []
    with _open_text(path) as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            records.append(json.loads(stripped))
            if max_rows is not None and len(records) >= max_rows:
                break
    return records


def load_events_frame(path: Path, max_rows: int | None = None) -> pd.DataFrame:
    records = load_json_records(path, max_rows=max_rows)
    rows = [_flatten_event(record) for record in records]
    return pd.DataFrame(rows)


def load_usage_frame(path: Path, max_rows: int | None = None) -> pd.DataFrame:
    records = load_json_records(path, max_rows=max_rows)
    rows = [_flatten_usage(record) for record in records]
    return pd.DataFrame(rows)


def _open_text(path: Path) -> TextIO:
    suffix = "".join(path.suffixes).lower()
    if suffix.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("rt", encoding="utf-8")


def _flatten_event(record: dict[str, Any]) -> dict[str, Any]:
    request = record.get("resource_request") or {}
    return {
        "collection_id": _as_str(record.get("collection_id")),
        "instance_index": _as_str(record.get("instance_index")),
        "time": _as_int(record.get("time")),
        "event_type": _as_str(record.get("type")),
        "priority": _as_int(record.get("priority")),
        "scheduling_class": _as_str(record.get("scheduling_class")),
        "cpu_request": _as_float(_nested_get(request, "cpus")),
        "memory_request": _as_float(_nested_get(request, "memory")),
    }


def _flatten_usage(record: dict[str, Any]) -> dict[str, Any]:
    average = record.get("average_usage") or {}
    maximum = record.get("maximum_usage") or {}
    return {
        "collection_id": _as_str(record.get("collection_id")),
        "instance_index": _as_str(record.get("instance_index")),
        "start_time": _as_int(record.get("start_time")),
        "cpu_usage": _as_float(_nested_get(average, "cpus")),
        "memory_usage": _as_float(_nested_get(average, "memory")),
        "cpu_max": _as_float(_nested_get(maximum, "cpus")),
        "memory_max": _as_float(_nested_get(maximum, "memory")),
        "assigned_memory": _as_float(record.get("assigned_memory")),
    }


def _nested_get(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return None


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def iter_json_records(path: Path) -> Iterator[dict[str, Any]]:
    with _open_text(path) as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                yield json.loads(stripped)
