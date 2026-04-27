import csv
from pathlib import Path

import streamlit as st

from config import (
    BUCKET_NAMES,
    DEFAULT_BUCKET_COUNT,
    DEFAULT_PERCENT_VALUES,
    MAX_BUCKETS,
    MAX_DAYS,
    MAX_SEGMENTS_PER_DAY,
)


def normalize_user_code(value):
    return "".join(ch for ch in (value or "").strip() if ch.isalnum()).upper()


def get_month_key(year, month):
    return f"{year:04d}-{month:02d}"


def get_data_directory():
    data_dir = Path(__file__).with_name("data")
    data_dir.mkdir(exist_ok=True)
    return data_dir


def get_month_storage_path(year, month):
    return get_data_directory() / f"zeiten_{year:04d}-{month:02d}.csv"


def get_storage_fieldnames():
    return [
        "month_key",
        "initials",
        "record_type",
        "day",
        "segment",
        "time",
        "fixed_bucket",
        "num_buckets",
    ] + [f"percent_{name}" for name in BUCKET_NAMES]


def get_default_percents_for_bucket_count(num_buckets):
    if num_buckets > 2:
        even_value = round(100 / num_buckets, 2)
        return [even_value] * num_buckets
    return DEFAULT_PERCENT_VALUES[:num_buckets]


def reset_user_workspace_state():
    st.session_state["num_buckets"] = DEFAULT_BUCKET_COUNT
    for i, name in enumerate(BUCKET_NAMES):
        st.session_state[f"percent_{name}"] = DEFAULT_PERCENT_VALUES[i]
    st.session_state["_last_num_buckets"] = DEFAULT_BUCKET_COUNT

    for i in range(MAX_DAYS):
        st.session_state[f"day_segments_{i}"] = 1
        for segment_index in range(1, MAX_SEGMENTS_PER_DAY + 1):
            st.session_state[f"time_{i}_{segment_index}"] = ""
            st.session_state[f"fixed_{i}_{segment_index}"] = ""


def load_user_month_state(user_code, year, month):
    reset_user_workspace_state()

    storage_path = get_month_storage_path(year, month)
    if not storage_path.exists():
        return False

    with storage_path.open("r", newline="", encoding="utf-8") as file_handle:
        rows = list(csv.DictReader(file_handle))

    user_rows = [row for row in rows if normalize_user_code(row.get("initials")) == user_code]
    if not user_rows:
        return False

    meta_row = next((row for row in user_rows if row.get("record_type") == "meta"), None)
    if meta_row:
        raw_bucket_count = meta_row.get("num_buckets", "").strip()
        if raw_bucket_count.isdigit():
            st.session_state["num_buckets"] = max(1, min(MAX_BUCKETS, int(raw_bucket_count)))

        for name in BUCKET_NAMES:
            raw_percent = meta_row.get(f"percent_{name}", "").strip()
            if raw_percent == "":
                continue
            try:
                st.session_state[f"percent_{name}"] = float(raw_percent)
            except ValueError:
                pass

    for row in user_rows:
        if row.get("record_type") != "day":
            continue

        raw_day = row.get("day", "").strip()
        if not raw_day.isdigit():
            continue

        day_index = int(raw_day) - 1
        if not (0 <= day_index < MAX_DAYS):
            continue

        raw_segment = row.get("segment", "").strip() or row.get("segment_index", "").strip()
        if raw_segment.isdigit():
            segment_index = int(raw_segment)
        else:
            segment_index = 1

        if not (1 <= segment_index <= MAX_SEGMENTS_PER_DAY):
            continue

        st.session_state[f"time_{day_index}_{segment_index}"] = row.get("time", "").strip()
        st.session_state[f"fixed_{day_index}_{segment_index}"] = row.get("fixed_bucket", "").strip()
        st.session_state[f"day_segments_{day_index}"] = max(
            st.session_state.get(f"day_segments_{day_index}", 1),
            segment_index,
        )

    st.session_state["_last_num_buckets"] = int(st.session_state.get("num_buckets", DEFAULT_BUCKET_COUNT))

    return True


def build_user_month_rows(user_code, year, month, num_buckets, percents, all_day_inputs):
    month_key = get_month_key(year, month)
    rows = []

    meta_row = {
        "month_key": month_key,
        "initials": user_code,
        "record_type": "meta",
        "day": "",
        "time": "",
        "fixed_bucket": "",
        "num_buckets": str(num_buckets),
    }

    for name in BUCKET_NAMES:
        meta_row[f"percent_{name}"] = ""

    for name, percent in zip(BUCKET_NAMES[:num_buckets], percents):
        meta_row[f"percent_{name}"] = f"{float(percent):.2f}"

    rows.append(meta_row)

    for day_number, day_input in enumerate(all_day_inputs, start=1):
        for segment_index, segment in enumerate(day_input.get("segments", []), start=1):
            time_value = (segment.get("time") or "").strip()
            fixed_bucket = (segment.get("fixed_bucket") or "").strip().upper()

            if time_value == "":
                continue

            row = {
                "month_key": month_key,
                "initials": user_code,
                "record_type": "day",
                "day": str(day_number),
                "segment": str(segment_index),
                "time": time_value,
                "fixed_bucket": fixed_bucket,
                "num_buckets": "",
            }

            for name in BUCKET_NAMES:
                row[f"percent_{name}"] = ""

            rows.append(row)

    return rows


def save_user_month_state(user_code, year, month, num_buckets, percents, all_day_inputs):
    storage_path = get_month_storage_path(year, month)
    storage_path.parent.mkdir(exist_ok=True)

    fieldnames = get_storage_fieldnames()
    existing_rows = []
    if storage_path.exists():
        with storage_path.open("r", newline="", encoding="utf-8") as file_handle:
            existing_rows = list(csv.DictReader(file_handle))

    remaining_rows = [
        row for row in existing_rows
        if normalize_user_code(row.get("initials")) != user_code
    ]

    rows_to_write = remaining_rows + build_user_month_rows(user_code, year, month, num_buckets, percents, all_day_inputs)

    with storage_path.open("w", newline="", encoding="utf-8") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_to_write)


def cleanup_non_current_month_files(current_year, current_month):
    current_name = f"zeiten_{current_year:04d}-{current_month:02d}.csv"
    data_dir = get_data_directory()

    deleted_files = []
    for file_path in data_dir.glob("zeiten_*.csv"):
        if file_path.name != current_name:
            file_path.unlink(missing_ok=True)
            deleted_files.append(file_path.name)

    return deleted_files
