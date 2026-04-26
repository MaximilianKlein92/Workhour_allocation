import calendar
import csv
import random
from datetime import date
from datetime import timedelta
from pathlib import Path

import streamlit as st

MAX_DAYS = 31
MAX_BUCKETS = 10
BUCKET_NAMES = list("ABCDEFGHIJ")
DEFAULT_BUCKET_COUNT = 2
DEFAULT_PERCENT_VALUES = [20.0, 80.0] + [0.0] * 8
MAX_SEGMENTS_PER_DAY = 2


def get_current_month_info():
    today = date.today()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    return today.year, today.month, days_in_month


def get_easter_sunday(year):
    # Gauß/Oudin algorithm for Gregorian calendar
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def get_bw_public_holidays(year):
    easter = get_easter_sunday(year)

    return {
        date(year, 1, 1),   # Neujahr
        date(year, 1, 6),   # Heilige Drei Koenige (BW)
        easter - timedelta(days=2),   # Karfreitag
        easter + timedelta(days=1),   # Ostermontag
        date(year, 5, 1),   # Tag der Arbeit
        easter + timedelta(days=39),  # Christi Himmelfahrt
        easter + timedelta(days=50),  # Pfingstmontag
        easter + timedelta(days=60),  # Fronleichnam (BW)
        date(year, 10, 3),  # Tag der Deutschen Einheit
        date(year, 11, 1),  # Allerheiligen (BW)
        date(year, 12, 25), # 1. Weihnachtstag
        date(year, 12, 26), # 2. Weihnachtstag
        date(year, 12, 27), # DITF geschlossen
        date(year, 12, 28), # DITF geschlossen
        date(year, 12, 29), # DITF geschlossen
        date(year, 12, 30), # DITF geschlossen
        date(year, 12, 31), # Silvester
    }


def is_bw_public_holiday(check_date):
    return check_date in get_bw_public_holidays(check_date.year)


def is_weekday_in_current_month(day_number):
    year, month, days_in_month = get_current_month_info()
    if day_number < 1 or day_number > days_in_month:
        return False

    day_date = date(year, month, day_number)
    if is_bw_public_holiday(day_date):
        return False

    return day_date.weekday() < 5


def get_weekday_short_name(day_number):
    weekday_names = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    year, month, days_in_month = get_current_month_info()
    if day_number < 1 or day_number > days_in_month:
        return ""
    return weekday_names[date(year, month, day_number).weekday()]


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


def get_random_image_from_folder(folder_name):
    image_dir = Path(__file__).parent / folder_name
    if not image_dir.exists():
        return None

    image_files = []
    for extension in ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.gif"):
        image_files.extend(image_dir.glob(extension))

    if not image_files:
        return None

    return random.choice(image_files)


def get_random_media_image():
    return get_random_image_from_folder("Media")


def normalize_time_input(value: str) -> str:
    """
    Macht aus:
    '8'    -> '08:00'
    '08'   -> '08:00'
    '801'  -> '08:01'
    '0801' -> '08:01'
    '8:01' -> '08:01'
    '08:01'-> '08:01'
    """
    value = value.strip()

    if value == "":
        return ""

    if ":" in value:
        parts = value.split(":")
        if len(parts) != 2:
            raise ValueError("Ungültiges Zeitformat")

        h, m = parts
        if not (h.isdigit() and m.isdigit()):
            raise ValueError("Ungültiges Zeitformat")

        h = int(h)
        m = int(m)

        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError("Ungültige Uhrzeit")

        return f"{h:02d}:{m:02d}"

    if not value.isdigit():
        raise ValueError("Ungültiges Zeitformat")

    if len(value) <= 2:
        h = int(value)
        m = 0
    elif len(value) == 3:
        h = int(value[0])
        m = int(value[1:])
    elif len(value) == 4:
        h = int(value[:2])
        m = int(value[2:])
    else:
        raise ValueError("Bitte Zeit als 1 bis 4 Ziffern eingeben, z. B. 8, 801 oder 0801")

    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError("Ungültige Uhrzeit")

    return f"{h:02d}:{m:02d}"


def normalize_time_field(key):
    value = st.session_state.get(key, "").strip()
    if value == "":
        return
    try:
        st.session_state[key] = normalize_time_input(value)
    except ValueError:
        pass


def time_to_minutes(t, assume_normalized=False):
    if not assume_normalized:
        t = normalize_time_input(t)
    h, m = map(int, t.split(":"))
    return h * 60 + m


def minutes_to_time(minutes):
    sign = "-" if minutes < 0 else ""
    minutes = abs(int(minutes))
    h = minutes // 60
    m = minutes % 60
    return f"{sign}{h:02d}:{m:02d}"


def is_valid_time_format(t):
    try:
        normalize_time_input(t)
        return True
    except ValueError:
        return False


def get_time_validation_message(time_value, fixed_bucket):
    time_value = (time_value or "").strip()
    fixed_bucket = (fixed_bucket or "").strip()

    if time_value == "" and fixed_bucket != "":
        return "Eine feste Kostenstelle braucht auch eine Zeit."

    if time_value == "":
        return None

    try:
        normalize_time_input(time_value)
    except ValueError as error:
        return str(error)

    return None


def allocate_exact_targets(total_minutes, active_names, percents):
    """
    Verteilt Soll-Minuten proportional so, dass die Summe exakt total_minutes ist.
    Largest-Remainder-Verfahren (Hamilton-Methode).
    """
    raw_values = []
    base_targets = {}

    for name, p in zip(active_names, percents):
        raw = total_minutes * p / 100
        base = int(raw)
        base_targets[name] = base
        raw_values.append((name, raw - base))

    remainder = total_minutes - sum(base_targets.values())

    # Stabile Reihenfolge bei Gleichstand: Bucket-Name
    raw_values.sort(key=lambda x: (-x[1], x[0]))

    for i in range(remainder):
        name = raw_values[i][0]
        base_targets[name] += 1

    return base_targets


def score_assignment(assignments, targets):
    """
    Summe der absoluten Abweichungen.
    Kleiner = besser.
    """
    total = 0
    for bucket in targets:
        assigned_sum = sum(day["minutes"] for day in assignments[bucket])
        total += abs(assigned_sum - targets[bucket])
    return total


def fast_distribute_days(free_days, targets, max_iterations=400):
    """
    Schnelle heuristische Verteilung:
    1. Greedy initiale Zuweisung
    2. Lokale Verbesserung durch Move und Swap

    Performance-Optimierung:
    Der Score wird inkrementell über Bucket-Summen aktualisiert,
    statt bei jedem Kandidaten die gesamte Lösung neu zu bewerten.
    """
    bucket_names = list(targets.keys())
    assignments = {b: [] for b in bucket_names}
    bucket_sums = {b: 0 for b in bucket_names}

    free_days_sorted = sorted(free_days, key=lambda d: d["minutes"], reverse=True)

    # Greedy initiale Zuweisung (mit laufenden Summen)
    for day in free_days_sorted:
        best_bucket = None
        best_score = None

        for bucket in bucket_names:
            current_sum = bucket_sums[bucket]
            new_sum = current_sum + day["minutes"]
            target = targets[bucket]

            diff_after = abs(target - new_sum)

            penalty = 0
            if current_sum >= target:
                penalty = 5

            score = diff_after + penalty

            if best_score is None or score < best_score:
                best_score = score
                best_bucket = bucket

        assignments[best_bucket].append(day)
        bucket_sums[best_bucket] += day["minutes"]

    current_score = sum(abs(bucket_sums[b] - targets[b]) for b in bucket_names)
    if current_score == 0:
        return assignments

    improved = True
    iterations = 0

    while improved and iterations < max_iterations:
        improved = False
        iterations += 1

        # Einzelne Tage verschieben
        for src in bucket_names:
            if improved:
                break

            for day in assignments[src][:]:
                day_minutes = day["minutes"]
                src_old = bucket_sums[src]
                src_new = src_old - day_minutes
                src_delta = abs(src_new - targets[src]) - abs(src_old - targets[src])

                for dst in bucket_names:
                    if src == dst:
                        continue

                    dst_old = bucket_sums[dst]
                    dst_new = dst_old + day_minutes
                    dst_delta = abs(dst_new - targets[dst]) - abs(dst_old - targets[dst])

                    delta = src_delta + dst_delta
                    if delta < 0:
                        assignments[src].remove(day)
                        assignments[dst].append(day)
                        bucket_sums[src] = src_new
                        bucket_sums[dst] = dst_new
                        current_score += delta
                        if current_score == 0:
                            return assignments
                        improved = True
                        break

                if improved:
                    break

        if improved:
            continue

        # Tage zwischen zwei Buckets tauschen
        for i, b1 in enumerate(bucket_names):
            if improved:
                break

            for b2 in bucket_names[i + 1:]:
                s1_old = bucket_sums[b1]
                s2_old = bucket_sums[b2]

                for d1 in assignments[b1][:]:
                    m1 = d1["minutes"]

                    for d2 in assignments[b2][:]:
                        m2 = d2["minutes"]

                        s1_new = s1_old - m1 + m2
                        s2_new = s2_old - m2 + m1

                        delta = (
                            abs(s1_new - targets[b1]) - abs(s1_old - targets[b1])
                            + abs(s2_new - targets[b2]) - abs(s2_old - targets[b2])
                        )

                        if delta < 0:
                            assignments[b1].remove(d1)
                            assignments[b2].remove(d2)
                            assignments[b1].append(d2)
                            assignments[b2].append(d1)

                            bucket_sums[b1] = s1_new
                            bucket_sums[b2] = s2_new
                            current_score += delta
                            if current_score == 0:
                                return assignments
                            improved = True
                            break

                    if improved:
                        break
                if improved:
                    break

    return assignments


def calculate_distribution(num_buckets, percents, all_day_inputs):
    active_names = BUCKET_NAMES[:num_buckets]

    total_percent = sum(percents)
    if abs(total_percent - 100.0) > 0.001:
        raise ValueError(f"Die Prozente müssen zusammen 100 ergeben. Aktuell: {total_percent:.2f}")

    all_days = []
    fixed_assignments = {name: [] for name in active_names}
    free_days = []

    for i, day_input in enumerate(all_day_inputs, start=1):
        segments = day_input.get("segments", [])
        for segment_index, segment in enumerate(segments, start=1):
            time_value = (segment.get("time") or "").strip()
            fixed_bucket = (segment.get("fixed_bucket") or "").strip().upper()

            if time_value != "":
                time_value = normalize_time_input(time_value)

            if time_value == "":
                if fixed_bucket != "":
                    raise ValueError(
                        f"Tag {i}, Segment {segment_index} hat eine feste Kostenstelle, aber keine Zeit."
                    )
                continue

            minutes = time_to_minutes(time_value, assume_normalized=True)
            day = {
                "day": i,
                "segment": segment_index,
                "time": time_value,
                "minutes": minutes
            }
            all_days.append(day)

            if fixed_bucket != "":
                if fixed_bucket not in active_names:
                    raise ValueError(
                        f"Ungültige feste Kostenstelle bei Tag {i}, Segment {segment_index}: '{fixed_bucket}'. "
                        f"Erlaubt: {', '.join(active_names)}"
                    )
                day["fixed_bucket"] = fixed_bucket
                fixed_assignments[fixed_bucket].append(day)
            else:
                day["fixed_bucket"] = ""
                free_days.append(day)

    if not all_days:
        raise ValueError("Bitte mindestens eine Zeit eintragen.")

    total_minutes = sum(d["minutes"] for d in all_days)

    targets = allocate_exact_targets(total_minutes, active_names, percents)
    remaining_targets = {}

    for name in active_names:
        target = targets[name]
        fixed_sum = sum(d["minutes"] for d in fixed_assignments[name])
        remaining_targets[name] = max(0, target - fixed_sum)

    auto_assignments = fast_distribute_days(free_days, remaining_targets)

    final_assignments = {}
    for name in active_names:
        combined = fixed_assignments[name] + auto_assignments[name]
        combined = sorted(combined, key=lambda x: x["day"])

        fixed_sum = sum(d["minutes"] for d in fixed_assignments[name])
        auto_sum = sum(d["minutes"] for d in auto_assignments[name])
        total_sum = sum(d["minutes"] for d in combined)

        final_assignments[name] = {
            "fixed_days": fixed_assignments[name],
            "auto_days": auto_assignments[name],
            "all_days": combined,
            "fixed_sum": fixed_sum,
            "auto_sum": auto_sum,
            "sum": total_sum,
            "target": targets[name],
            "diff": abs(total_sum - targets[name]),
        }

    day_project_rows = []
    assigned_days = set()

    for name in active_names:
        for d in final_assignments[name]["fixed_days"]:
            day_project_rows.append({
                "Tag": d["day"],
                "Segment": d.get("segment", 1),
                "Zeit": d["time"],
                "Projekt": name,
                "Art": "fest"
            })
            assigned_days.add(d["day"])

        for d in final_assignments[name]["auto_days"]:
            day_project_rows.append({
                "Tag": d["day"],
                "Segment": d.get("segment", 1),
                "Zeit": d["time"],
                "Projekt": name,
                "Art": "auto"
            })
            assigned_days.add(d["day"])

    day_project_rows = sorted(day_project_rows, key=lambda x: (x["Tag"], x.get("Segment", 1)))

    day_assignment_counts = {}
    for row in day_project_rows:
        day_assignment_counts[row["Tag"]] = day_assignment_counts.get(row["Tag"], 0) + 1

    split_days = sorted(day for day, count in day_assignment_counts.items() if count > 1)

    for row in day_project_rows:
        row["Geteilt"] = "Ja" if row["Tag"] in split_days else "Nein"

    leftovers = [d for d in all_days if d["day"] not in assigned_days]
    leftover_sum = sum(d["minutes"] for d in leftovers)

    return {
        "total_minutes": total_minutes,
        "active_names": active_names,
        "percents": percents,
        "targets": targets,
        "assignments": final_assignments,
        "day_project_rows": day_project_rows,
        "split_days": split_days,
        "leftovers": leftovers,
        "leftover_sum": leftover_sum,
        "quality_score": score_assignment(
            {k: v["all_days"] for k, v in final_assignments.items()},
            targets
        )
    }


st.set_page_config(page_title="Zeitverteilung A–J", layout="wide")

header_image = get_random_image_from_folder("Media/Headder")
if header_image is not None:
    st.image(str(header_image))

st.title("Zeitverteilung auf Kostenstellen A–J")

st.markdown("Schnelle Verteilung mit fixer Zuordnung einzelner Tage und automatischer Restverteilung.")

current_year, current_month, days_in_month = get_current_month_info()
current_month_key = get_month_key(current_year, current_month)

cleanup_key = f"{current_year:04d}-{current_month:02d}"
if st.session_state.get("_cleanup_done_for_month") != cleanup_key:
    cleanup_non_current_month_files(current_year, current_month)
    st.session_state["_cleanup_done_for_month"] = cleanup_key

header_col1, header_col2, header_col3 = st.columns([1.3, 1.0, 0.8])

with header_col1:
    user_input = st.text_input("Benutzerkürzel", placeholder="MaKl", key="user_initials")
    user_key = normalize_user_code(user_input)
    if user_key:
        loaded_user = st.session_state.get("_loaded_user")
        loaded_month = st.session_state.get("_loaded_month")
        if loaded_user != user_key or loaded_month != current_month_key:
            loaded = load_user_month_state(user_key, current_year, current_month)
            st.session_state["_loaded_user"] = user_key
            st.session_state["_loaded_month"] = current_month_key
            if loaded:
                st.success(f"Daten für {user_key} aus {calendar.month_name[current_month]} {current_year} geladen.")
            else:
                st.info(f"Neuer Benutzer {user_key}. Leere Monatsansicht vorbereitet.")
    else:
        if st.session_state.get("_loaded_user"):
            reset_user_workspace_state()
        st.session_state["_loaded_user"] = ""
        st.session_state["_loaded_month"] = current_month_key

if st.session_state.get("_pending_reset"):
    if user_key:
        reset_user_workspace_state()
        st.session_state["_loaded_user"] = user_key
        st.session_state["_loaded_month"] = current_month_key
        st.success("Eingaben wurden zurückgesetzt.")
    st.session_state["_pending_reset"] = False

with header_col2:
    st.info(f"Monat: {calendar.month_name[current_month]} {current_year}")

with header_col3:
    reset_clicked = st.button("Reset", disabled=not bool(user_key))

if reset_clicked and user_key:
    st.session_state["_pending_reset"] = True
    st.rerun()

col1, col2 = st.columns([1, 2])

with col1:
    num_buckets = int(st.number_input(
        "Anzahl Kostenstellen",
        min_value=1,
        max_value=10,
        value=st.session_state.get("num_buckets", DEFAULT_BUCKET_COUNT),
        step=1
    ))

    previous_bucket_count = st.session_state.get("_last_num_buckets")
    if previous_bucket_count != num_buckets:
        new_defaults = get_default_percents_for_bucket_count(num_buckets)
        for i, name in enumerate(BUCKET_NAMES[:num_buckets]):
            st.session_state[f"percent_{name}"] = new_defaults[i]
        st.session_state["_last_num_buckets"] = num_buckets
    else:
        stable_defaults = get_default_percents_for_bucket_count(num_buckets)
        for i, name in enumerate(BUCKET_NAMES[:num_buckets]):
            key = f"percent_{name}"
            if key not in st.session_state:
                st.session_state[key] = stable_defaults[i]

    st.subheader("Prozentverteilung")
    active_names = BUCKET_NAMES[:num_buckets]
    percents = []

    for i, name in enumerate(active_names):
        p = st.number_input(
            f"{name} (%)",
            min_value=0.0,
            max_value=100.0,
            step=1.0,
            key=f"percent_{name}"
        )
        percents.append(p)

    percent_sum = sum(percents)
    st.caption(f"Summe: {percent_sum:.2f} %")
    percent_sum_valid = abs(percent_sum - 100.0) <= 0.001
    if not percent_sum_valid:
        st.error("Die Prozente müssen zusammen 100 % ergeben.")
    else:
        st.success("Prozentverteilung ist gültig.")

with col2:
    st.subheader("Tageszeiten")
    month_name = calendar.month_name[current_month]
    st.caption(
        f"Aktueller Monat: {month_name} {current_year}. "
        "Pro Tag sind bis zu zwei Segmente möglich. Werktage werden hervorgehoben. "
        "BW- und DITF-Feiertage werden wie Wochenende behandelt. Zeit als 0801, 801, 8:01 oder 08:01 eingeben. Feste Kostenstelle optional."
    )
    mobile_layout = st.toggle("Mobile Ansicht", value=True, key="mobile_layout")

    day_inputs = []
    day_validation_errors = []

    if not mobile_layout:
        header_cols = st.columns([0.55, 0.85, 1.0, 1.15, 1.0, 1.15, 1.0])
        header_cols[0].markdown("**Tag**")
        header_cols[1].markdown("**Wochentag**")
        header_cols[2].markdown("**Zeit 1**")
        header_cols[3].markdown("**Fest 1**")
        header_cols[4].markdown("**+ / Zeit 2**")
        header_cols[5].markdown("**Fest 2**")
        header_cols[6].markdown("**Status**")

    for i in range(days_in_month):
        day_number = i + 1
        weekday_name = get_weekday_short_name(day_number)
        is_weekday = is_weekday_in_current_month(day_number)

        segment_count_key = f"day_segments_{i}"
        if segment_count_key not in st.session_state:
            st.session_state[segment_count_key] = 1

        segment_inputs = []
        for segment_index in range(1, MAX_SEGMENTS_PER_DAY + 1):
            time_key = f"time_{i}_{segment_index}"
            fixed_key = f"fixed_{i}_{segment_index}"

            if time_key not in st.session_state:
                st.session_state[time_key] = ""
            if fixed_key not in st.session_state:
                st.session_state[fixed_key] = ""

            segment_inputs.append((time_key, fixed_key))

        segment_two_visible = st.session_state.get(segment_count_key, 1) >= 2
        day_segments = []
        row_errors = []
        filled_segment_count = 0

        if mobile_layout:
            with st.container(border=True):
                top_cols = st.columns([1.0, 1.0])
                with top_cols[0]:
                    st.markdown(f"**Tag {day_number}**")
                with top_cols[1]:
                    if is_weekday:
                        st.markdown(
                            f"<div style='display:inline-block; background-color:rgba(245, 158, 11, 0.25); color:inherit; border:1px solid rgba(245, 158, 11, 0.95); padding:0.18rem 0.45rem; border-radius:0.35rem; font-weight:600;'>{weekday_name}</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(f"**{weekday_name}**")

                seg1_cols = st.columns([1, 1])
                with seg1_cols[0]:
                    time_value = st.text_input(
                        "Zeit 1",
                        key=segment_inputs[0][0],
                        placeholder="HH:MM",
                        on_change=normalize_time_field,
                        args=(segment_inputs[0][0],),
                    )
                with seg1_cols[1]:
                    fixed_bucket = st.selectbox(
                        "Fest 1",
                        options=[""] + active_names,
                        key=segment_inputs[0][1],
                    )

                if not segment_two_visible:
                    add_cols = st.columns([1, 1])
                    with add_cols[1]:
                        if st.button("+", key=f"add_segment_{i}", help="Zweite Zeit hinzufügen"):
                            st.session_state[segment_count_key] = 2
                            st.rerun()

                time_error = get_time_validation_message(time_value, fixed_bucket)
                if time_error:
                    row_errors.append(f"S1: {time_error}")
                if time_value != "" or fixed_bucket != "":
                    filled_segment_count += 1
                day_segments.append({"segment": 1, "time": time_value, "fixed_bucket": fixed_bucket})

                if segment_two_visible:
                    seg2_cols = st.columns([1, 1])
                    with seg2_cols[0]:
                        time_value2 = st.text_input(
                            "Zeit 2",
                            key=segment_inputs[1][0],
                            placeholder="HH:MM",
                            on_change=normalize_time_field,
                            args=(segment_inputs[1][0],),
                        )
                    with seg2_cols[1]:
                        fixed_bucket2 = st.selectbox(
                            "Fest 2",
                            options=[""] + active_names,
                            key=segment_inputs[1][1],
                        )

                    time_error2 = get_time_validation_message(time_value2, fixed_bucket2)
                    if time_error2:
                        row_errors.append(f"S2: {time_error2}")
                    if time_value2 != "" or fixed_bucket2 != "":
                        filled_segment_count += 1
                    day_segments.append({"segment": 2, "time": time_value2, "fixed_bucket": fixed_bucket2})

                if row_errors:
                    day_validation_errors.extend(row_errors)
                    st.error(" | ".join(row_errors))
                elif filled_segment_count > 1:
                    st.caption("Status: geteilt")
                elif filled_segment_count == 1:
                    st.caption("Status: 1 Segment")
        else:
            row_cols = st.columns([0.55, 0.85, 1.0, 1.15, 1.0, 1.15, 1.0])

            with row_cols[0]:
                st.write(day_number)

            with row_cols[1]:
                if is_weekday:
                    st.markdown(
                        f"<div style='display:inline-block; background-color:rgba(245, 158, 11, 0.25); color:inherit; border:1px solid rgba(245, 158, 11, 0.95); padding:0.18rem 0.45rem; border-radius:0.35rem; font-weight:600;'>"
                        f"{weekday_name}</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.write(weekday_name)

            for segment_index, (time_key, fixed_key) in enumerate(segment_inputs, start=1):
                if segment_index == 2 and not segment_two_visible:
                    continue

                time_col = row_cols[2] if segment_index == 1 else row_cols[4]
                fixed_col = row_cols[3] if segment_index == 1 else row_cols[5]

                with time_col:
                    time_value = st.text_input(
                        f"Zeit {segment_index}",
                        key=time_key,
                        placeholder="HH:MM",
                        label_visibility="collapsed",
                        on_change=normalize_time_field,
                        args=(time_key,)
                    )

                with fixed_col:
                    fixed_bucket = st.selectbox(
                        f"Fest {segment_index}",
                        options=[""] + active_names,
                        key=fixed_key,
                        label_visibility="collapsed"
                    )

                time_error = get_time_validation_message(time_value, fixed_bucket)
                if time_error:
                    row_errors.append(f"S{segment_index}: {time_error}")

                if time_value != "" or fixed_bucket != "":
                    filled_segment_count += 1

                day_segments.append({
                    "segment": segment_index,
                    "time": time_value,
                    "fixed_bucket": fixed_bucket,
                })

            with row_cols[4]:
                if segment_two_visible:
                    st.markdown("<span style='color:#6b7280; font-weight:600;'>2. Zeit</span>", unsafe_allow_html=True)
                else:
                    if st.button(
                        "+",
                        key=f"add_segment_{i}",
                        help="Zweite Zeit hinzufügen",
                    ):
                        st.session_state[segment_count_key] = 2
                        st.rerun()

            with row_cols[5]:
                if segment_two_visible:
                    st.markdown("<span style='color:#6b7280; font-weight:600;'>optional</span>", unsafe_allow_html=True)

            with row_cols[6]:
                if row_errors:
                    day_validation_errors.extend(row_errors)
                    st.markdown(
                        "<span style='color:#dc2626; font-weight:600;'>" + "<br>".join(row_errors) + "</span>",
                        unsafe_allow_html=True,
                    )
                elif filled_segment_count > 1:
                    st.markdown("<span style='color:#d97706; font-weight:700;'>geteilt</span>", unsafe_allow_html=True)
                elif filled_segment_count == 1:
                    st.markdown("<span style='color:#6b7280;'>1 Segment</span>", unsafe_allow_html=True)
                else:
                    st.write("")

        day_inputs.append({"day": day_number, "segments": day_segments})

if day_validation_errors:
    unique_errors = list(dict.fromkeys(day_validation_errors))
    st.warning("Bitte prüfe die markierten Zeilen: " + " | ".join(unique_errors))

can_submit = bool(user_key) and percent_sum_valid and len(day_validation_errors) == 0

button_col1, button_col2 = st.columns([1, 1])
with button_col1:
    save_clicked = st.button("Speichern", disabled=not can_submit)
with button_col2:
    calculate_clicked = st.button("Berechnen", type="primary", disabled=not can_submit)

if save_clicked and can_submit:
    save_user_month_state(user_key, current_year, current_month, num_buckets, percents, day_inputs)
    st.success(f"Daten für {user_key} in {calendar.month_name[current_month]} {current_year} gespeichert.")

if calculate_clicked and can_submit:
    loading_placeholder = st.empty()
    try:
        random_image = get_random_media_image()
        if random_image is not None:
            st.subheader("Warte-Meme")
            image_col_left, image_col_center, image_col_right = st.columns([1, 1, 1])
            with image_col_center:
                st.image(str(random_image), width=400)
        else:
            st.info("Kein Bild im Media-Ordner gefunden.")

        loading_placeholder.caption("Berechnung läuft ...")
        save_user_month_state(user_key, current_year, current_month, num_buckets, percents, day_inputs)
        result = calculate_distribution(num_buckets, percents, day_inputs)
        loading_placeholder.empty()

        st.success("Berechnung abgeschlossen.")

        st.subheader("Übersicht")
        st.write(f"**Gesamtzeit:** {minutes_to_time(result['total_minutes'])}")
        st.write(f"**Gesamtabweichung:** {minutes_to_time(result['quality_score'])}")

        target_rows = []
        for name, p in zip(result["active_names"], result["percents"]):
            info = result["assignments"][name]
            target_rows.append({
                "Projekt": name,
                "Prozent": f"{p:.1f} %",
                "Soll": minutes_to_time(result["targets"][name]),
                "Ist": minutes_to_time(info["sum"]),
                "Abweichung": minutes_to_time(info["diff"])
            })
        st.table(target_rows)

        st.subheader("Tag → Projekt")
        if result["day_project_rows"]:
            st.dataframe(result["day_project_rows"], use_container_width=True, hide_index=True)
        else:
            st.info("Keine Zuordnung vorhanden.")

        if result.get("split_days"):
            split_label = ", ".join(str(day) for day in result["split_days"])
            st.warning(f"Geteilte Tage: {split_label}")

        st.subheader("Projektdetails")
        for name in result["active_names"]:
            info = result["assignments"][name]

            with st.expander(f"{name} — Soll {minutes_to_time(info['target'])}", expanded=True):
                if info["fixed_days"]:
                    st.write("**Fest zugeordnet:**")
                    for d in info["fixed_days"]:
                        suffix = " (geteilt)" if d["day"] in result.get("split_days", []) else ""
                        segment_label = f" / Segment {d.get('segment', 1)}" if d.get("segment", 1) else ""
                        st.write(f"- Tag {d['day']}{segment_label}: {d['time']}{suffix}")
                    st.write(f"Fest-Summe: **{minutes_to_time(info['fixed_sum'])}**")
                else:
                    st.write("**Fest zugeordnet:** keine")

                if info["auto_days"]:
                    st.write("**Automatisch zugeordnet:**")
                    for d in info["auto_days"]:
                        suffix = " (geteilt)" if d["day"] in result.get("split_days", []) else ""
                        segment_label = f" / Segment {d.get('segment', 1)}" if d.get("segment", 1) else ""
                        st.write(f"- Tag {d['day']}{segment_label}: {d['time']}{suffix}")
                    st.write(f"Auto-Summe: **{minutes_to_time(info['auto_sum'])}**")
                else:
                    st.write("**Automatisch zugeordnet:** keine")

                st.write(f"**Gesamt:** {minutes_to_time(info['sum'])}")
                st.write(f"**Abweichung:** {minutes_to_time(info['diff'])}")

        st.subheader("Nicht zugewiesene Tage")
        if result["leftovers"]:
            leftover_rows = [
                {"Tag": d["day"], "Zeit": d["time"]}
                for d in result["leftovers"]
            ]
            st.table(leftover_rows)
            st.write(f"**Rest-Summe:** {minutes_to_time(result['leftover_sum'])}")
        else:
            st.write("Keine")

    except ValueError as e:
        loading_placeholder.empty()
        st.error(str(e))