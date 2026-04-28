import calendar

import streamlit as st

from allocation import calculate_distribution
from config import BUCKET_NAMES, DEFAULT_BUCKET_COUNT, MAX_DAYS, MAX_SEGMENTS_PER_DAY, BUCKET_COLORS
from device_utils import detect_mobile_client
from holidays import get_current_month_info, get_weekday_short_name, is_weekday_in_current_month
from media_utils import get_random_image_from_folder, get_random_media_image
from storage import (
    cleanup_non_current_month_files,
    get_default_percents_for_bucket_count,
    get_month_key,
    load_user_month_state,
    normalize_user_code,
    reset_user_workspace_state,
    save_user_month_state,
)
from time_utils import get_time_validation_message, minutes_to_time, normalize_time_field, time_to_minutes


def has_day_input_draft():
    for day_idx in range(MAX_DAYS):
        for segment_index in range(1, MAX_SEGMENTS_PER_DAY + 1):
            time_value = str(st.session_state.get(f"time_{day_idx}_{segment_index}", "")).strip()
            fixed_value = str(st.session_state.get(f"fixed_{day_idx}_{segment_index}", "")).strip()
            if time_value or fixed_value:
                return True
    return False


def bucket_display_label(bucket_name):
    if not bucket_name:
        return ""

    color_markers = ["🔵", "🟢", "🔴", "🟡", "🟣", "🟠", "🟤", "⚫", "⚪", "🩵"]
    try:
        bucket_index = BUCKET_NAMES.index(bucket_name)
    except ValueError:
        bucket_index = 0
    marker = color_markers[bucket_index % len(color_markers)]
    return f"{marker} {bucket_name}"


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

if "_mobile_layout_initialized" not in st.session_state:
    st.session_state["mobile_layout"] = detect_mobile_client()
    st.session_state["_mobile_layout_initialized"] = True

header_col1, header_col2, header_col3 = st.columns([1.3, 1.0, 0.8])

with header_col1:
    user_input = st.text_input("Benutzerkürzel", placeholder="MaKl", key="user_initials")
    user_key = normalize_user_code(user_input)
    if user_key:
        loaded_user = st.session_state.get("_loaded_user")
        loaded_month = st.session_state.get("_loaded_month")
        if loaded_user != user_key or loaded_month != current_month_key:
            if has_day_input_draft():
                # Keep current draft and simply bind it to the entered user.
                st.session_state["_loaded_user"] = user_key
                st.session_state["_loaded_month"] = current_month_key
                st.info(f"Aktuelle Eingaben bleiben erhalten und werden für {user_key} gespeichert.")
            else:
                loaded = load_user_month_state(user_key, current_year, current_month)
                st.session_state["_loaded_user"] = user_key
                st.session_state["_loaded_month"] = current_month_key
                if loaded:
                    st.success(f"Daten für {user_key} aus {calendar.month_name[current_month]} {current_year} geladen.")
                else:
                    st.info(f"Neuer Benutzer {user_key}. Leere Monatsansicht vorbereitet.")
    else:
        # Do not clear draft inputs when user tag is empty.
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
        color = BUCKET_COLORS[i] if i < len(BUCKET_COLORS) else "#9ca3af"
        input_cols = st.columns([0.12, 1])
        with input_cols[0]:
            st.markdown(f"<div title='{name}' style='width:1.2rem;height:1.2rem;background:{color};border-radius:4px;border:1px solid rgba(0,0,0,0.08);'></div>", unsafe_allow_html=True)
        with input_cols[1]:
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
    mobile_layout = st.toggle("Mobile Ansicht", key="mobile_layout")

    day_inputs = []
    day_validation_errors = []

    if not mobile_layout:
        header_cols = st.columns([0.55, 0.85, 1.0, 1.15, 1.0, 1.15, 1.0, 0.75])
        header_cols[0].markdown("**Tag**")
        header_cols[1].markdown("**Wochentag**")
        header_cols[2].markdown("**Zeit 1**")
        header_cols[3].markdown("**Fest 1**")
        header_cols[4].markdown("**+ / Zeit 2**")
        header_cols[5].markdown("**Fest 2**")
        header_cols[6].markdown("**Aktion**")
        header_cols[7].markdown("**Status**")

    for i in range(days_in_month):
        day_number = i + 1
        weekday_name = get_weekday_short_name(day_number)
        is_weekday = is_weekday_in_current_month(day_number)

        segment_count_key = f"day_segments_{i}"
        pending_remove_key = f"remove_segment_pending_{i}"
        if segment_count_key not in st.session_state:
            st.session_state[segment_count_key] = 1

        # Apply pending remove action before widgets are created to avoid session_state conflicts.
        if st.session_state.pop(pending_remove_key, False):
            st.session_state[segment_count_key] = 1
            st.session_state[f"time_{i}_2"] = ""
            st.session_state[f"fixed_{i}_2"] = ""
            st.rerun()

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
                        format_func=bucket_display_label,
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
                            format_func=bucket_display_label,
                        )

                    time_error2 = get_time_validation_message(time_value2, fixed_bucket2)
                    if time_error2:
                        row_errors.append(f"S2: {time_error2}")
                    if time_value2 != "" or fixed_bucket2 != "":
                        filled_segment_count += 1
                    day_segments.append({"segment": 2, "time": time_value2, "fixed_bucket": fixed_bucket2})

                    remove_cols = st.columns([1, 1])
                    with remove_cols[1]:
                        if st.button("Segment 2 entfernen", key=f"remove_segment_{i}"):
                            st.session_state[pending_remove_key] = True
                            st.rerun()

                if row_errors:
                    day_validation_errors.extend(row_errors)
                    st.error(" | ".join(row_errors))
                elif filled_segment_count > 1:
                    st.caption("Status: geteilt")
                elif filled_segment_count == 1:
                    st.caption("Status: 1 Segment")
        else:
            row_cols = st.columns([0.55, 0.85, 1.0, 1.15, 1.0, 1.15, 1.0, 0.75])
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
                        ,format_func=bucket_display_label,
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
                if segment_two_visible:
                    if st.button("S2 entfernen", key=f"remove_segment_{i}"):
                        st.session_state[pending_remove_key] = True
                        st.rerun()

            with row_cols[7]:
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

is_input_valid = percent_sum_valid and len(day_validation_errors) == 0
can_calculate = is_input_valid
can_save = bool(user_key) and is_input_valid

if not user_key:
    st.info("Berechnen ist ohne Benutzerkürzel möglich (temporär). Speichern erfordert ein Benutzerkürzel.")

button_col1, button_col2 = st.columns([1, 1])
with button_col1:
    save_clicked = st.button("Speichern", disabled=not can_save)
with button_col2:
    calculate_clicked = st.button("Berechnen", type="primary", disabled=not can_calculate)

if save_clicked and can_save:
    save_user_month_state(user_key, current_year, current_month, num_buckets, percents, day_inputs)
    st.success(f"Daten für {user_key} in {calendar.month_name[current_month]} {current_year} gespeichert.")

if calculate_clicked and can_calculate:
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
        if user_key:
            save_user_month_state(user_key, current_year, current_month, num_buckets, percents, day_inputs)
        else:
            st.info("Berechnung ohne Benutzerkürzel: Ergebnis wird nicht gespeichert.")
        result = calculate_distribution(num_buckets, percents, day_inputs)
        loading_placeholder.empty()

        if user_key:
            st.success("Berechnung abgeschlossen und Ergebnis gespeichert.")
        else:
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
        # Render target_rows later after project_colors is available to show consistent swatches

        st.subheader("Tages-Graph")
        day_to_projects = {day: [] for day in range(1, days_in_month + 1)}
        day_project_minutes = {day: {} for day in range(1, days_in_month + 1)}
        day_total_minutes = {day: 0 for day in range(1, days_in_month + 1)}
        for row in result["day_project_rows"]:
            day = int(row["Tag"])
            project = str(row["Projekt"])
            minutes = time_to_minutes(str(row["Zeit"]), assume_normalized=True)
            day_to_projects.setdefault(day, []).append(project)
            day_project_minutes.setdefault(day, {})[project] = day_project_minutes.setdefault(day, {}).get(project, 0) + minutes
            day_total_minutes[day] = day_total_minutes.get(day, 0) + minutes

        leftover_day_minutes = {}
        for leftover in result.get("leftovers", []):
            day = int(leftover["day"])
            minutes = int(leftover.get("minutes", 0))
            leftover_day_minutes[day] = leftover_day_minutes.get(day, 0) + minutes

        project_colors = {
            name: BUCKET_COLORS[BUCKET_NAMES.index(name) % len(BUCKET_COLORS)]
            for name in result["active_names"]
        }

        legend_domain = list(result["active_names"]) + ["Nicht zugewiesen", "Arbeitsfrei"]
        legend_range = [project_colors[name] for name in result["active_names"]] + [
            "#9ca3af",
            "#111827",
        ]

        graph_rows = []
        for day in range(1, days_in_month + 1):
            is_non_workday = not is_weekday_in_current_month(day)
            projects = sorted(set(day_to_projects.get(day, [])))

            if is_non_workday:
                weekend_minutes = day_total_minutes.get(day, 0) + leftover_day_minutes.get(day, 0)
                graph_rows.append(
                    {
                        "Tag": day,
                        "Linie": 1,
                        "Kategorie": "Arbeitsfrei",
                        "Zuordnung": "-",
                        "Minuten": weekend_minutes,
                        "Stunden": round(weekend_minutes / 60, 2),
                    }
                )
            elif not projects:
                unassigned_minutes = leftover_day_minutes.get(day, 0)
                graph_rows.append(
                    {
                        "Tag": day,
                        "Linie": 1,
                        "Kategorie": "Nicht zugewiesen",
                        "Zuordnung": "-",
                        "Minuten": unassigned_minutes,
                        "Stunden": round(unassigned_minutes / 60, 2),
                    }
                )
            else:
                spacing = 0.028
                start = 1 - (spacing * (len(projects) - 1) / 2)
                for index, project in enumerate(projects):
                    project_minutes = day_project_minutes.get(day, {}).get(project, 0)
                    graph_rows.append(
                        {
                            "Tag": day,
                            "Linie": start + (index * spacing),
                            "Kategorie": project,
                            "Zuordnung": ", ".join(projects),
                            "Minuten": project_minutes,
                            "Stunden": round(project_minutes / 60, 2),
                        }
                    )

        max_graph_minutes = max((row["Minuten"] for row in graph_rows), default=1)
        max_graph_minutes = max(max_graph_minutes, 1)

        st.vega_lite_chart(
            {
                "data": {"values": graph_rows},
                "height": 190,
                "layer": [
                    {
                        "mark": {"type": "line", "color": "#cbd5e1", "strokeWidth": 2},
                        "encoding": {
                            "x": {
                                "field": "Tag",
                                "type": "quantitative",
                                "axis": {
                                    "tickMinStep": 1,
                                    "values": list(range(1, days_in_month + 1)),
                                    "labelAngle": 0,
                                },
                                "scale": {"domain": [1, days_in_month]},
                            },
                            "y": {
                                "field": "Linie",
                                "type": "quantitative",
                                "axis": None,
                                "scale": {"domain": [0.94, 1.06]},
                            },
                        },
                    },
                    {
                        "mark": {"type": "point", "filled": True, "size": 140},
                        "encoding": {
                            "x": {
                                "field": "Tag",
                                "type": "quantitative",
                                "axis": {
                                    "tickMinStep": 1,
                                    "values": list(range(1, days_in_month + 1)),
                                    "labelAngle": 0,
                                },
                                "scale": {"domain": [1, days_in_month]},
                            },
                            "y": {
                                "field": "Linie",
                                "type": "quantitative",
                                "axis": None,
                                "scale": {"domain": [0.94, 1.06]},
                            },
                            "color": {
                                "field": "Kategorie",
                                "type": "nominal",
                                "legend": {"title": "Status / Kostenstelle"},
                                "scale": {"domain": legend_domain, "range": legend_range},
                            },
                            "size": {
                                "field": "Minuten",
                                "type": "quantitative",
                                "legend": None,
                                "scale": {
                                    "domain": [0, max_graph_minutes],
                                    "range": [80, 1200],
                                },
                            },
                            "tooltip": [
                                {"field": "Tag", "type": "quantitative"},
                                {"field": "Kategorie", "type": "nominal"},
                                {"field": "Zuordnung", "type": "nominal"},
                                {"field": "Stunden", "type": "quantitative"},
                            ],
                        },
                    },
                ],
            },
            use_container_width=True,
        )

        # Render Ziel-Tabelle mit Farbswatches
        if target_rows:
            html = "<table style='width:100%; border-collapse:collapse;'>"
            html += "<thead><tr><th style='text-align:left;padding:6px 8px'>Projekt</th><th style='padding:6px 8px'>Prozent</th><th style='padding:6px 8px'>Soll</th><th style='padding:6px 8px'>Ist</th><th style='padding:6px 8px'>Abweichung</th></tr></thead><tbody>"
            for row in target_rows:
                name = row["Projekt"]
                color = project_colors.get(name, "#9ca3af")
                html += (
                    "<tr>"
                    f"<td style='padding:6px 8px;border-bottom:1px solid #eee'><span style=\"display:inline-block;width:1rem;height:1rem;background:{color};border-radius:3px;margin-right:8px;vertical-align:middle;\"></span>{name}</td>"
                    f"<td style='padding:6px 8px;border-bottom:1px solid #eee'>{row['Prozent']}</td>"
                    f"<td style='padding:6px 8px;border-bottom:1px solid #eee'>{row['Soll']}</td>"
                    f"<td style='padding:6px 8px;border-bottom:1px solid #eee'>{row['Ist']}</td>"
                    f"<td style='padding:6px 8px;border-bottom:1px solid #eee'>{row['Abweichung']}</td>"
                    "</tr>"
                )
            html += "</tbody></table>"
            st.markdown("**Übersicht (mit Farben)**", unsafe_allow_html=True)
            st.markdown(html, unsafe_allow_html=True)

        st.subheader("Tag → Projekt")
        if result["day_project_rows"]:
            # Render day->project table with color swatches
            html = "<table style='width:100%; border-collapse:collapse;'>"
            # determine columns from first row keys (safest minimal set)
            html += "<thead><tr><th style='text-align:left;padding:6px 8px'>Tag</th><th style='text-align:left;padding:6px 8px'>Projekt</th><th style='padding:6px 8px'>Zeit</th></tr></thead><tbody>"
            for row in result["day_project_rows"]:
                day = row.get("Tag", "")
                proj = str(row.get("Projekt", ""))
                time = row.get("Zeit", "")
                color = project_colors.get(proj, "#9ca3af")
                html += (
                    "<tr>"
                    f"<td style='padding:6px 8px;border-bottom:1px solid #eee'>{day}</td>"
                    f"<td style='padding:6px 8px;border-bottom:1px solid #eee'><span style=\"display:inline-block;width:1rem;height:1rem;background:{color};border-radius:3px;margin-right:8px;vertical-align:middle;\"></span>{proj}</td>"
                    f"<td style='padding:6px 8px;border-bottom:1px solid #eee'>{time}</td>"
                    "</tr>"
                )
            html += "</tbody></table>"
            st.markdown(html, unsafe_allow_html=True)
        else:
            st.info("Keine Zuordnung vorhanden.")

        if result.get("split_days"):
            split_label = ", ".join(str(day) for day in result["split_days"])
            st.warning(f"Geteilte Tage: {split_label}")

        st.subheader("Projektdetails")
        for name in result["active_names"]:
            info = result["assignments"][name]
            color = project_colors.get(name, "#9ca3af")

            with st.expander(f"{name} — Soll {minutes_to_time(info['target'])}", expanded=True):
                # show color swatch and heading inside the expander for consistent visual cue
                st.markdown(f"<div style='display:flex;align-items:center;margin-bottom:0.35rem;'><span style=\"display:inline-block;width:1rem;height:1rem;background:{color};border-radius:3px;margin-right:8px;\"></span><strong>{name}</strong> — Soll {minutes_to_time(info['target'])}</div>", unsafe_allow_html=True)

                if info["fixed_days"]:
                    st.write("**Fest zugeordnet:**")
                    for d in info["fixed_days"]:
                        suffix = " (geteilt)" if d["day"] in result.get("split_days", []) else ""
                        segment_label = f" / Segment {d.get('segment', 1)}" if d.get('segment', 1) else ""
                        st.write(f"- Tag {d['day']}{segment_label}: {d['time']}{suffix}")
                    st.write(f"Fest-Summe: **{minutes_to_time(info['fixed_sum'])}**")
                else:
                    st.write("**Fest zugeordnet:** keine")

                if info["auto_days"]:
                    st.write("**Automatisch zugeordnet:**")
                    for d in info["auto_days"]:
                        suffix = " (geteilt)" if d["day"] in result.get("split_days", []) else ""
                        segment_label = f" / Segment {d.get('segment', 1)}" if d.get('segment', 1) else ""
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
