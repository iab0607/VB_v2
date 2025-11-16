"""Datetime utility functions."""
import re
from datetime import datetime, timezone

def normalize_iso_datetime(dt_str: str) -> str:
    """Normalize various ISO datetime formats to consistent format with Z suffix."""
    if not dt_str:
        return dt_str
    dt_str = dt_str.replace(" ", "T")
    dt_str = re.sub(r'(\.\d{1,6})?\+00:00$', 'Z', dt_str)
    dt_str = re.sub(r'(\.\d{1,6})?\+0000$', 'Z', dt_str)
    if dt_str.endswith('+00:00'):
        dt_str = dt_str[:-6] + 'Z'
    elif dt_str.endswith('+0000'):
        dt_str = dt_str[:-5] + 'Z'
    if dt_str and dt_str[-1].lower() == 'z':
        return dt_str[:-1] + 'Z'
    return dt_str

def parse_datetime(dt_str: str) -> datetime:
    """Parse ISO datetime string to datetime object."""
    if dt_str.endswith("Z"):
        dt_str = dt_str[:-1]
    dt = datetime.fromisoformat(dt_str)
    return dt.replace(tzinfo=timezone.utc)

def within_time_window(dt1: datetime, dt2: datetime, minutes: int) -> bool:
    """Check if two datetimes are within specified minutes of each other."""
    return abs((dt1 - dt2).total_seconds()) <= minutes * 60