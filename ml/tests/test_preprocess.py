from pathlib import Path

from feature_mapping import (
    OUTPUT_COLUMNS,
    add_utilization_targets,
    build_training_table,
    latest_allocations,
)
from load_trace import load_events_frame, load_usage_frame
from preprocess import preprocess


def test_latest_allocations_keeps_newest_request(fixtures_dir) -> None:
    events = load_events_frame(fixtures_dir / "instance_events.jsonl")
    allocations = latest_allocations(events)
    row = allocations.set_index(["collection_id", "instance_index"]).loc[("1", "10")]
    assert row["cpu_request"] == 1.0
    assert row["memory_request"] == 0.5


def test_latest_allocations_drops_missing_request(fixtures_dir) -> None:
    events = load_events_frame(fixtures_dir / "instance_events.jsonl")
    allocations = latest_allocations(events)
    keys = set(zip(allocations["collection_id"], allocations["instance_index"], strict=True))
    assert ("3", "30") not in keys


def test_utilization_is_usage_over_request(fixtures_dir) -> None:
    frame = add_utilization_targets(
        load_usage_frame(fixtures_dir / "instance_usage.jsonl").assign(
            cpu_request=1.0,
            memory_request=0.5,
        )
    )
    first = frame.iloc[0]
    assert first["cpu_utilization"] == 0.4
    assert first["memory_utilization"] == 0.4


def test_build_training_table_joins_matching_ids(fixtures_dir) -> None:
    events = load_events_frame(fixtures_dir / "instance_events.jsonl")
    usage = load_usage_frame(fixtures_dir / "instance_usage.jsonl")
    table, source = build_training_table(events, usage)
    assert source == "instance_events.resource_request"
    assert list(table.columns) == OUTPUT_COLUMNS
    assert len(table) == 2
    matched = table.sort_values("cpu").reset_index(drop=True)
    assert matched.iloc[1]["cpu"] == 1.0
    assert matched.iloc[1]["cpu_utilization"] == 0.4
    assert matched.iloc[1]["replicas"] == 1
    assert matched.iloc[1]["expected_users"] == 1000
    assert int(matched.iloc[0]["application_type_code"]) == 8  # scheduling_class 2 -> batch


def test_build_training_table_falls_back_when_shards_do_not_join(fixtures_dir) -> None:
    events = load_events_frame(fixtures_dir / "instance_events_unmatched.jsonl")
    usage = load_usage_frame(fixtures_dir / "instance_usage_unmatched.jsonl")
    table, source = build_training_table(events, usage)
    assert source == "instance_usage.maximum_usage_fallback"
    assert len(table) == 2
    # second row prefers assigned_memory=0.25 over memory_max=0.1
    by_cpu = table.set_index("cpu")
    assert by_cpu.loc[0.2]["memory_gb"] == 0.25
    assert by_cpu.loc[0.2]["memory_utilization"] == 0.05 / 0.25


def test_preprocess_writes_split_files(tmp_path: Path, fixtures_dir) -> None:
    metadata = preprocess(
        events_path=fixtures_dir / "instance_events.jsonl",
        usage_path=fixtures_dir / "instance_usage.jsonl",
        output_dir=tmp_path,
        max_rows=None,
        test_size=0.5,
        random_state=42,
    )
    assert metadata["train_rows"] + metadata["test_rows"] == metadata["training_rows"]
    assert (tmp_path / "train.csv").exists()
    assert (tmp_path / "test.csv").exists()
    assert (tmp_path / "metadata.json").exists()
    assert metadata["allocation_source"] == "instance_events.resource_request"
