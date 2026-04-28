from datetime import date, datetime

o = date(2026, 4, 1).isoformat()
# "2026-04-01"
print(o)

o = datetime(2026, 4, 1, 10, 30).isoformat()
# "2026-04-01T10:30:00"
print(o)
