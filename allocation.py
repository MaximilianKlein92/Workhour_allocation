from config import BUCKET_NAMES
from time_utils import normalize_time_input, time_to_minutes


def allocate_exact_targets(total_minutes, active_names, percents):
    raw_values = []
    base_targets = {}

    for name, p in zip(active_names, percents):
        raw = total_minutes * p / 100
        base = int(raw)
        base_targets[name] = base
        raw_values.append((name, raw - base))

    remainder = total_minutes - sum(base_targets.values())
    raw_values.sort(key=lambda x: (-x[1], x[0]))

    for i in range(remainder):
        name = raw_values[i][0]
        base_targets[name] += 1

    return base_targets


def score_assignment(assignments, targets):
    total = 0
    for bucket in targets:
        assigned_sum = sum(day["minutes"] for day in assignments[bucket])
        total += abs(assigned_sum - targets[bucket])
    return total


def fast_distribute_days(free_days, targets, max_iterations=400):
    bucket_names = list(targets.keys())
    assignments = {b: [] for b in bucket_names}
    bucket_sums = {b: 0 for b in bucket_names}

    free_days_sorted = sorted(free_days, key=lambda d: d["minutes"], reverse=True)

    for day in free_days_sorted:
        best_bucket = None
        best_score = None

        for bucket in bucket_names:
            current_sum = bucket_sums[bucket]
            new_sum = current_sum + day["minutes"]
            target = targets[bucket]

            diff_after = abs(target - new_sum)
            penalty = 5 if current_sum >= target else 0
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
                "minutes": minutes,
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
                "Art": "fest",
            })
            assigned_days.add(d["day"])

        for d in final_assignments[name]["auto_days"]:
            day_project_rows.append({
                "Tag": d["day"],
                "Segment": d.get("segment", 1),
                "Zeit": d["time"],
                "Projekt": name,
                "Art": "auto",
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
            targets,
        ),
    }
