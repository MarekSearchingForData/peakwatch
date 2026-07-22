"""Calendar/season feature builder: holidays, day-type, seasonal harmonics,
and sunset hour (drives winter peak timing — the evening peak rides sunset).

Sunset uses the compact NOAA solar-geometry approximation — deterministic,
no API, accurate to a couple of minutes, which is plenty for an hour-grain
feature.
"""
import math
from datetime import date, timedelta

import holidays as holidays_lib
import pandas as pd

from .store import connect

LAT, LON = 42.3, -71.8  # central MA reference point
US_MA_HOLIDAYS = holidays_lib.country_holidays("US", subdiv="MA")


def sunset_hour_local(d: date, lat=LAT, lon=LON) -> float:
    """Local (Eastern, DST-aware) sunset hour via NOAA approximation."""
    doy = d.timetuple().tm_yday
    decl = math.radians(-23.44) * math.cos(math.radians(360 / 365 * (doy + 10)))
    lat_r = math.radians(lat)
    cos_ha = -math.tan(lat_r) * math.tan(decl)
    cos_ha = max(-1, min(1, cos_ha))
    ha = math.degrees(math.acos(cos_ha))  # degrees of hour angle at sunset
    # solar noon in UTC hours (longitude correction; equation of time ~ignored)
    solar_noon_utc = 12 - lon / 15
    sunset_utc = solar_noon_utc + ha / 15
    # Eastern offset: DST second Sunday March .. first Sunday November
    dst_start = _nth_weekday(d.year, 3, 6, 2)
    dst_end = _nth_weekday(d.year, 11, 6, 1)
    offset = -4 if dst_start <= d < dst_end else -5
    return sunset_utc + offset


def _nth_weekday(year, month, weekday, n):
    d = date(year, month, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def build(start=date(2022, 1, 1), end=None):
    end = end or (date.today() + timedelta(days=14))
    rows = []
    days = pd.date_range(start, end, freq="D").date
    for d in days:
        name = US_MA_HOLIDAYS.get(d)
        adjacent = int(bool(
            US_MA_HOLIDAYS.get(d - timedelta(days=1))
            or US_MA_HOLIDAYS.get(d + timedelta(days=1))))
        doy = d.timetuple().tm_yday
        rows.append((
            d.isoformat(), d.weekday(), int(d.weekday() >= 5),
            int(name is not None), name, adjacent,
            math.sin(2 * math.pi * doy / 365.25),
            math.cos(2 * math.pi * doy / 365.25),
            round(sunset_hour_local(d), 2),
        ))
    con = connect()
    con.executemany(
        "INSERT OR REPLACE INTO feature_calendar VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows)
    con.commit()
    con.close()
    return len(rows)
