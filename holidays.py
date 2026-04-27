import calendar
from datetime import date, timedelta


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
        date(year, 1, 1),
        date(year, 1, 6),
        easter - timedelta(days=2),
        easter + timedelta(days=1),
        date(year, 5, 1),
        easter + timedelta(days=39),
        easter + timedelta(days=50),
        easter + timedelta(days=60),
        date(year, 10, 3),
        date(year, 11, 1),
        date(year, 12, 25),
        date(year, 12, 26),
        date(year, 12, 27),
        date(year, 12, 28),
        date(year, 12, 29),
        date(year, 12, 30),
        date(year, 12, 31),
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
