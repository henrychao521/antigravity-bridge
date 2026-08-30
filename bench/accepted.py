from datetime import date


def iso_week_range(year: int, week: int) -> tuple[date, date]:
    return (
        date.fromisocalendar(year, week, 1),
        date.fromisocalendar(year, week, 7),
    )
