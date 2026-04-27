import streamlit as st


def normalize_time_input(value: str) -> str:
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
