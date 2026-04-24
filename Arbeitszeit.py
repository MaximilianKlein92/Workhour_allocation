import calendar
from datetime import date

import streamlit as st

MAX_DAYS = 31
MAX_BUCKETS = 10
BUCKET_NAMES = list("ABCDEFGHIJ")


def get_current_month_info():
    today = date.today()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    return today.year, today.month, days_in_month


def is_weekday_in_current_month(day_number):
    year, month, days_in_month = get_current_month_info()
    if day_number < 1 or day_number > days_in_month:
        return False
    return date(year, month, day_number).weekday() < 5


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

    for i, (time_value, fixed_bucket) in enumerate(all_day_inputs, start=1):
        time_value = time_value.strip()
        fixed_bucket = fixed_bucket.strip().upper()

        if time_value != "":
            time_value = normalize_time_input(time_value)

        if time_value == "":
            if fixed_bucket != "":
                raise ValueError(f"Tag {i} hat eine feste Kostenstelle, aber keine Zeit.")
            continue

        minutes = time_to_minutes(time_value, assume_normalized=True)
        day = {
            "day": i,
            "time": time_value,
            "minutes": minutes
        }
        all_days.append(day)

        if fixed_bucket != "":
            if fixed_bucket not in active_names:
                raise ValueError(
                    f"Ungültige feste Kostenstelle bei Tag {i}: '{fixed_bucket}'. "
                    f"Erlaubt: {', '.join(active_names)}"
                )
            fixed_assignments[fixed_bucket].append(day)
        else:
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
                "Zeit": d["time"],
                "Projekt": name,
                "Art": "fest"
            })
            assigned_days.add(d["day"])

        for d in final_assignments[name]["auto_days"]:
            day_project_rows.append({
                "Tag": d["day"],
                "Zeit": d["time"],
                "Projekt": name,
                "Art": "auto"
            })
            assigned_days.add(d["day"])

    day_project_rows = sorted(day_project_rows, key=lambda x: x["Tag"])

    leftovers = [d for d in all_days if d["day"] not in assigned_days]
    leftover_sum = sum(d["minutes"] for d in leftovers)

    return {
        "total_minutes": total_minutes,
        "active_names": active_names,
        "percents": percents,
        "targets": targets,
        "assignments": final_assignments,
        "day_project_rows": day_project_rows,
        "leftovers": leftovers,
        "leftover_sum": leftover_sum,
        "quality_score": score_assignment(
            {k: v["all_days"] for k, v in final_assignments.items()},
            targets
        )
    }


st.set_page_config(page_title="Zeitverteilung A–J", layout="wide")
st.title("Zeitverteilung auf Kostenstellen A–J")

st.markdown("Schnelle Verteilung mit fixer Zuordnung einzelner Tage und automatischer Restverteilung.")

col1, col2 = st.columns([1, 2])

with col1:
    num_buckets = st.number_input(
        "Anzahl Kostenstellen",
        min_value=1,
        max_value=10,
        value=2,
        step=1
    )

    st.subheader("Prozentverteilung")
    active_names = BUCKET_NAMES[:num_buckets]
    percents = []

    default_values = [20.0, 80.0] + [0.0] * 8
    if num_buckets > 2:
        even_value = round(100 / num_buckets, 2)
        default_values = [even_value] * num_buckets

    for i, name in enumerate(active_names):
        default = default_values[i] if i < len(default_values) else 0.0
        p = st.number_input(
            f"{name} (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(default),
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
    current_year, current_month, days_in_month = get_current_month_info()
    month_name = calendar.month_name[current_month]
    st.caption(
        f"Aktueller Monat: {month_name} {current_year}. "
        "Werktage werden hervorgehoben. Zeit als 0801, 801, 8:01 oder 08:01 eingeben. Feste Kostenstelle optional."
    )

    day_inputs = []
    days_per_row = 3
    day_validation_errors = []

    for row_start in range(0, MAX_DAYS, days_per_row):
        row_cols = st.columns(days_per_row)

        for offset, col in enumerate(row_cols):
            i = row_start + offset
            if i >= MAX_DAYS:
                continue

            with col:
                day_number = i + 1
                if is_weekday_in_current_month(day_number):
                    st.markdown(
                        f"<div style='background-color:rgba(245, 158, 11, 0.25); color:inherit; border:1px solid rgba(245, 158, 11, 0.95); padding:0.35rem 0.5rem; border-radius:0.4rem; font-weight:600;'>Tag {day_number}</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(f"**Tag {day_number}**")

                time_key = f"time_{i}"
                fixed_key = f"fixed_{i}"

                if time_key not in st.session_state:
                    st.session_state[time_key] = ""
                if fixed_key not in st.session_state:
                    st.session_state[fixed_key] = ""

                time_value = st.text_input(
                    "Zeit",
                    key=time_key,
                    placeholder="HH:MM or HMM",
                    label_visibility="collapsed",
                    on_change=normalize_time_field,
                    args=(time_key,)
                )

                fixed_bucket = st.selectbox(
                    "Fest",
                    options=[""] + active_names,
                    key=fixed_key,
                    label_visibility="collapsed"
                )

                time_error = get_time_validation_message(time_value, fixed_bucket)
                if time_error:
                    day_validation_errors.append(time_error)
                    st.error(time_error)

                day_inputs.append((time_value, fixed_bucket))

calculate_clicked = st.button("Berechnen", type="primary")

can_calculate = percent_sum_valid and len(day_validation_errors) == 0

if calculate_clicked and can_calculate:
    try:
        result = calculate_distribution(num_buckets, percents, day_inputs)

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

        st.subheader("Projektdetails")
        for name in result["active_names"]:
            info = result["assignments"][name]

            with st.expander(f"{name} — Soll {minutes_to_time(info['target'])}", expanded=True):
                if info["fixed_days"]:
                    st.write("**Fest zugeordnet:**")
                    for d in info["fixed_days"]:
                        st.write(f"- Tag {d['day']}: {d['time']}")
                    st.write(f"Fest-Summe: **{minutes_to_time(info['fixed_sum'])}**")
                else:
                    st.write("**Fest zugeordnet:** keine")

                if info["auto_days"]:
                    st.write("**Automatisch zugeordnet:**")
                    for d in info["auto_days"]:
                        st.write(f"- Tag {d['day']}: {d['time']}")
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
        st.error(str(e))
elif calculate_clicked:
    st.error("Bitte korrigiere zuerst die markierten Eingaben.")