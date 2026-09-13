from load_trace import load_events_frame, load_json_records, load_usage_frame


def test_load_json_records_from_jsonl(fixtures_dir) -> None:
    records = load_json_records(fixtures_dir / "instance_events.jsonl")
    assert len(records) == 4
    assert records[0]["collection_id"] == "1"


def test_load_json_records_respects_max_rows(fixtures_dir) -> None:
    records = load_json_records(fixtures_dir / "instance_events.jsonl", max_rows=2)
    assert len(records) == 2


def test_flatten_events_resource_request(fixtures_dir) -> None:
    frame = load_events_frame(fixtures_dir / "instance_events.jsonl")
    first = frame.iloc[0]
    assert first["cpu_request"] == 0.5
    assert first["memory_request"] == 0.25
    assert first["scheduling_class"] == "0"


def test_flatten_usage_nested_fields(fixtures_dir) -> None:
    frame = load_usage_frame(fixtures_dir / "instance_usage.jsonl")
    first = frame.iloc[0]
    assert first["cpu_usage"] == 0.4
    assert first["memory_usage"] == 0.2
    assert first["cpu_max"] == 0.8
    assert first["memory_max"] == 0.4
