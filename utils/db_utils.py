from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def apply_time_filter(statement, column, tz_name: str, days: int | None):
    """
    Apply a calendar-based time filter using the user's timezone.

    Args:
        statement: SQL query object.
        column: UTC timestamp column to filter on.
        tz_name: IANA timezone string (e.g., "Asia/Ho_Chi_Minh").
        days:
            - None → no filtering (all time)
            - 0 → today (from local midnight to now)
            - N → last N calendar days (from midnight N days ago to now)

    Notes:
        - Uses calendar days (not rolling 24h windows).
        - All calculations are done in local time, then converted to UTC
          to match how timestamps are stored in the database.
    """
    if days is None:
        return statement

    tz = ZoneInfo(tz_name)
    now_local = datetime.now(tz)

    # Local midnight (start of today in user's timezone)
    today_start_local = now_local.replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    if days == 0:
        # Today: from today's midnight → now
        start_local = today_start_local
    else:
        # Last N days: go back N midnights
        start_local = today_start_local - timedelta(days=days)

    # Convert to UTC for database comparison
    start_utc = start_local.astimezone(timezone.utc)

    return statement.where(column >= start_utc)
